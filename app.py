import io
from pathlib import Path
import re

import geopandas as gpd
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import rasterio
from rasterio.features import geometry_mask, rasterize
from shapely.geometry import LineString, MultiPolygon, Polygon
from shapely.ops import unary_union
import streamlit as st

st.set_page_config(page_title="Analise MDT - Agricultura de Precisao", layout="wide")

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
GEO_DIR = DATA_DIR / "geospatial"
TELEMETRY_RAW_DIR = DATA_DIR / "telemetry" / "raw"
TELEMETRY_PROCESSED_DIR = DATA_DIR / "telemetry" / "processed"
GEE_DATA_DIR = DATA_DIR / "gee"
RESULTS_DIR = BASE_DIR / "results" / "analises_resultados"

DATA_FILES = {
    "MDT (Elevacao)": GEO_DIR / "mdt_nasadem_area_talhoes.tif",
    "Declividade": GEO_DIR / "declividade_area_talhoes.tif",
    "Diferenca de Elevacao Media": GEO_DIR / "diferenca_elevacao_media_area_talhoes.tif",
}
DEFAULT_OPERATION_FILE = TELEMETRY_RAW_DIR / "13-04-2026_17_26.csv"
TELEMETRY_PROCESS_FILE = TELEMETRY_PROCESSED_DIR / "consolidado_telemetria_colheita.csv"
ML_RESULTS_DIR = RESULTS_DIR / "ml"
FIELDS_FILE = GEO_DIR / "fields.mbtiles"
NDVI_FILE = GEO_DIR / "ndvi_recente.tif"
IMAGERY_FILE = GEO_DIR / "imagem_recente.tif"
GEE_DECISION_PREFIXES = {
    "talhoes_stats": "DECISION_talhoes_stats_",
    "talhoes_indices_ts": "DECISION_talhoes_indices_timeseries_",
    "fazenda_rain_daily": "DECISION_fazenda_rain_daily_",
    "fazenda_climate_daily": "DECISION_fazenda_climate_daily_",
}


def infer_background_mask(arr: np.ndarray) -> np.ndarray:
    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        return np.zeros_like(arr, dtype=bool)

    if np.nanmin(finite) != 0:
        return np.zeros_like(arr, dtype=bool)

    positive = finite[finite > 0]
    if positive.size == 0:
        return np.zeros_like(arr, dtype=bool)

    if np.nanpercentile(positive, 5) <= 0:
        return np.zeros_like(arr, dtype=bool)

    border = np.concatenate([arr[0, :], arr[-1, :], arr[:, 0], arr[:, -1]])
    if np.count_nonzero(border == 0) == 0:
        return np.zeros_like(arr, dtype=bool)

    return arr == 0


def approximate_meter_resolution(transform, bounds):
    xres_deg = abs(transform.a)
    yres_deg = abs(transform.e)
    lat = (bounds.top + bounds.bottom) / 2.0
    lat_rad = np.deg2rad(lat)
    meters_per_deg_lat = 111132.92 - 559.82 * np.cos(2 * lat_rad) + 1.175 * np.cos(4 * lat_rad)
    meters_per_deg_lon = 111412.84 * np.cos(lat_rad) - 93.5 * np.cos(3 * lat_rad)
    return xres_deg * meters_per_deg_lon, yres_deg * meters_per_deg_lat


def read_raster(path: Path, mask_zeros: bool = False):
    with rasterio.open(path) as src:
        arr = src.read(1).astype("float64")
        nodata = src.nodata
        if nodata is not None:
            arr = np.where(arr == nodata, np.nan, arr)
        if mask_zeros:
            arr = np.where(infer_background_mask(arr), np.nan, arr)
        bounds = src.bounds
        transform = src.transform
        crs = src.crs
        res = src.res
    return arr, bounds, transform, crs, res


def raster_stats(arr: np.ndarray):
    valid = arr[np.isfinite(arr)]
    if valid.size == 0:
        return {
            "Minimo": np.nan,
            "Maximo": np.nan,
            "Media": np.nan,
            "Mediana": np.nan,
            "Desvio padrao": np.nan,
            "P05": np.nan,
            "P95": np.nan,
            "Pixels validos": 0,
        }
    return {
        "Minimo": float(np.nanmin(valid)),
        "Maximo": float(np.nanmax(valid)),
        "Media": float(np.nanmean(valid)),
        "Mediana": float(np.nanmedian(valid)),
        "Desvio padrao": float(np.nanstd(valid)),
        "P05": float(np.nanpercentile(valid, 5)),
        "P95": float(np.nanpercentile(valid, 95)),
        "Pixels validos": int(valid.size),
    }


def normalize(arr: np.ndarray):
    valid = arr[np.isfinite(arr)]
    if valid.size == 0:
        return np.full_like(arr, np.nan)

    vmin = np.nanpercentile(valid, 2)
    vmax = np.nanpercentile(valid, 98)
    return np.clip((arr - vmin) / (vmax - vmin + 1e-12), 0, 1)


def hillshade(elevation: np.ndarray, transform, bounds, azimuth=315, altitude=45):
    valid = np.isfinite(elevation)
    if not np.any(valid):
        return np.full_like(elevation, np.nan, dtype="float64")

    filled = np.where(valid, elevation, np.nanmedian(elevation[valid]))
    xres, yres = approximate_meter_resolution(transform, bounds)
    dy, dx = np.gradient(filled, yres, xres)
    slope = np.pi / 2.0 - np.arctan(np.sqrt(dx * dx + dy * dy))
    aspect = np.arctan2(-dx, dy)

    az_rad = np.deg2rad(azimuth)
    alt_rad = np.deg2rad(altitude)

    shaded = (
        np.sin(alt_rad) * np.sin(slope)
        + np.cos(alt_rad) * np.cos(slope) * np.cos(az_rad - aspect)
    )
    shaded = np.where(valid, shaded, np.nan)
    return normalize(shaded)


def raster_coordinates(bounds, shape):
    rows, cols = shape
    x = np.linspace(bounds.left, bounds.right, cols)
    y = np.linspace(bounds.top, bounds.bottom, rows)
    return x, y


def build_raster_figure(arr: np.ndarray, bounds, title: str, colorscale, zmin=None, zmax=None):
    x, y = raster_coordinates(bounds, arr.shape)
    fig = go.Figure(
        data=go.Heatmap(
            z=arr,
            x=x,
            y=y,
            colorscale=colorscale,
            zmin=zmin,
            zmax=zmax,
            hoverongaps=False,
            colorbar=dict(title="Valor"),
        )
    )
    fig.update_yaxes(autorange="reversed", scaleanchor="x", scaleratio=1)
    fig.update_layout(
        title=title,
        height=550,
        margin=dict(l=10, r=10, t=40, b=10),
        xaxis_title="Longitude",
        yaxis_title="Latitude",
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def classify_slope(arr: np.ndarray):
    bins = [0, 3, 8, 20, 45, np.inf]
    labels = [
        "Plano (0-3%)",
        "Suave ondulado (3-8%)",
        "Ondulado (8-20%)",
        "Forte ondulado (20-45%)",
        "Montanhoso (>45%)",
    ]

    valid = arr[np.isfinite(arr)]
    if valid.size == 0:
        return pd.DataFrame(columns=["Classe", "Area relativa (%)", "Pixels"])

    clipped = np.clip(valid, 0, np.inf)
    classes = pd.cut(clipped, bins=bins, labels=labels, right=False)
    counts = pd.Series(classes).value_counts(sort=False)
    df = pd.DataFrame(
        {
            "Classe": counts.index.astype(str),
            "Pixels": counts.values,
        }
    )
    df["Area relativa (%)"] = (df["Pixels"] / df["Pixels"].sum() * 100).round(2)
    return df


@st.cache_data(show_spinner=False)
def load_fields_map(path: Path) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(path)
    gdf = gdf[gdf.geometry.notna()].copy()
    return gdf


def clip_array_to_geometry(arr: np.ndarray, transform, geom) -> np.ndarray:
    mask = geometry_mask(
        [geom],
        out_shape=arr.shape,
        transform=transform,
        invert=True,
        all_touched=False,
    )
    return np.where(mask, arr, np.nan)


def build_talhao_classification(
    decliv_arr: np.ndarray,
    elev_arr: np.ndarray,
    runoff_arr: np.ndarray | None,
    transform,
    res_xy_m,
    talhoes_gdf: gpd.GeoDataFrame,
    ndvi_arr: np.ndarray | None = None,
) -> pd.DataFrame:
    if talhoes_gdf.empty:
        return pd.DataFrame()

    ids = talhoes_gdf["talhao_label"].astype(str).tolist()
    talhao_num = pd.to_numeric(talhoes_gdf.get("TALHAO"), errors="coerce") if "TALHAO" in talhoes_gdf.columns else pd.Series([np.nan] * len(ids))
    zone_pairs = [
        (geom, idx)
        for idx, geom in enumerate(talhoes_gdf.geometry.tolist(), start=1)
        if geom is not None and not geom.is_empty
    ]
    if not zone_pairs:
        return pd.DataFrame()

    zones = rasterize(
        zone_pairs,
        out_shape=decliv_arr.shape,
        transform=transform,
        fill=0,
        dtype="int32",
    )

    bins = [0, 3, 8, 20, 45, np.inf]
    labels = ["Plano 0-3%", "Suave 3-8%", "Ondulado 8-20%", "Forte 20-45%", "Montanhoso >45%"]
    pixel_area_ha = (res_xy_m[0] * res_xy_m[1]) / 10000.0
    out_rows = []

    for zone_id in range(1, len(ids) + 1):
        zone_mask = zones == zone_id
        if not np.any(zone_mask):
            continue

        dvals = decliv_arr[zone_mask]
        evals = elev_arr[zone_mask]
        rvals = runoff_arr[zone_mask] if runoff_arr is not None else np.full(np.count_nonzero(zone_mask), np.nan)
        nvals = ndvi_arr[zone_mask] if ndvi_arr is not None and ndvi_arr.shape == decliv_arr.shape else np.full(np.count_nonzero(zone_mask), np.nan)
        valid_d = dvals[np.isfinite(dvals)]
        valid_e = evals[np.isfinite(evals)]
        valid_r = rvals[np.isfinite(rvals)]
        valid_n = nvals[np.isfinite(nvals)]
        if valid_d.size == 0:
            continue

        classes = pd.cut(np.clip(valid_d, 0, np.inf), bins=bins, labels=labels, right=False)
        class_share = pd.Series(classes).value_counts(normalize=True, sort=False).reindex(labels, fill_value=0.0)
        dominant = class_share.idxmax()

        out_rows.append(
            {
                "Talhao": ids[zone_id - 1],
                "TALHAO_NUM": float(talhao_num.iloc[zone_id - 1]) if zone_id - 1 < len(talhao_num) else np.nan,
                "Pixels validos": int(valid_d.size),
                "Area estimada (ha)": float(valid_d.size * pixel_area_ha),
                "Declividade media (%)": float(np.nanmean(valid_d)),
                "Declividade P95 (%)": float(np.nanpercentile(valid_d, 95)),
                "Elevacao media (m)": float(np.nanmean(valid_e)) if valid_e.size else np.nan,
                "Runoff medio (0-1)": float(np.nanmean(valid_r)) if valid_r.size else np.nan,
                "NDVI medio": float(np.nanmean(valid_n)) if valid_n.size else np.nan,
                "Classe predominante": dominant,
                **{f"{k} (%)": float(v * 100.0) for k, v in class_share.items()},
            }
        )

    if not out_rows:
        return pd.DataFrame()

    df = pd.DataFrame(out_rows).sort_values("Declividade media (%)", ascending=False).reset_index(drop=True)
    return df


def classify_declividade_array(decliv_arr: np.ndarray) -> np.ndarray:
    classes = np.full(decliv_arr.shape, np.nan, dtype="float64")
    valid = np.isfinite(decliv_arr)
    if not np.any(valid):
        return classes

    vals = np.clip(decliv_arr[valid], 0, np.inf)
    bins = [0, 3, 8, 20, 45, np.inf]
    idx = np.digitize(vals, bins, right=False) - 1
    idx = np.clip(idx, 0, 4)
    classes[valid] = idx
    return classes


def d8_flow_accumulation(elevation: np.ndarray, xres_m: float, yres_m: float):
    rows, cols = elevation.shape
    valid = np.isfinite(elevation)
    n = rows * cols
    elev_flat = elevation.reshape(-1)
    valid_flat = valid.reshape(-1)

    receiver = np.full(n, -1, dtype=np.int32)
    sqrt2 = np.sqrt(2.0)
    neighbors = [
        (-1, -1, sqrt2),
        (-1, 0, 1.0),
        (-1, 1, sqrt2),
        (0, -1, 1.0),
        (0, 1, 1.0),
        (1, -1, sqrt2),
        (1, 0, 1.0),
        (1, 1, sqrt2),
    ]

    for r in range(rows):
        for c in range(cols):
            i = r * cols + c
            if not valid_flat[i]:
                continue

            z0 = elev_flat[i]
            best_slope = 0.0
            best_j = -1
            for dr, dc, dist_factor in neighbors:
                rn = r + dr
                cn = c + dc
                if rn < 0 or rn >= rows or cn < 0 or cn >= cols:
                    continue
                j = rn * cols + cn
                if not valid_flat[j]:
                    continue
                dz = z0 - elev_flat[j]
                if dz <= 0:
                    continue
                dist_m = np.hypot(xres_m * dc, yres_m * dr) if dist_factor == sqrt2 else (xres_m if dc != 0 else yres_m)
                slope = dz / (dist_m + 1e-12)
                if slope > best_slope:
                    best_slope = slope
                    best_j = j
            receiver[i] = best_j

    acc = np.zeros(n, dtype="float64")
    acc[valid_flat] = 1.0
    order = np.argsort(np.where(valid_flat, elev_flat, -np.inf))[::-1]
    for i in order:
        if not valid_flat[i]:
            continue
        j = receiver[i]
        if j >= 0:
            acc[j] += acc[i]

    out = acc.reshape(rows, cols)
    out[~valid] = np.nan
    return out, receiver.reshape(rows, cols)


def compute_runoff_layers(mdt_arr: np.ndarray, decliv_arr: np.ndarray, transform, bounds):
    if not np.isfinite(mdt_arr).any():
        nan_map = np.full_like(mdt_arr, np.nan, dtype="float64")
        return nan_map, nan_map, np.full_like(mdt_arr, -1, dtype="int32")

    xres_m, yres_m = approximate_meter_resolution(transform, bounds)
    flow_acc, receiver = d8_flow_accumulation(mdt_arr, xres_m, yres_m)

    slope_clip = np.clip(decliv_arr, 0, 45)
    slope_norm = np.where(np.isfinite(slope_clip), slope_clip / 45.0, np.nan)
    acc_norm = normalize(np.log1p(flow_acc))
    runoff = normalize((0.65 * slope_norm) + (0.35 * acc_norm))
    return flow_acc, runoff, receiver


def read_optional_singleband_raster(path: Path):
    if not path.exists():
        return None
    with rasterio.open(path) as src:
        arr = src.read(1).astype("float64")
        nodata = src.nodata
        if nodata is not None:
            arr = np.where(arr == nodata, np.nan, arr)
        return {
            "arr": arr,
            "transform": src.transform,
            "crs": src.crs,
            "bounds": src.bounds,
            "count": src.count,
        }


def read_optional_rgb_raster(path: Path):
    if not path.exists():
        return None
    with rasterio.open(path) as src:
        if src.count < 3:
            return None
        rgb = src.read([1, 2, 3]).astype("float64")
        nodata = src.nodata
        if nodata is not None:
            rgb = np.where(rgb == nodata, np.nan, rgb)
        return {
            "arr": np.moveaxis(rgb, 0, -1),
            "transform": src.transform,
            "crs": src.crs,
            "bounds": src.bounds,
            "count": src.count,
        }


def normalize_rgb_to_gray(rgb_arr: np.ndarray) -> np.ndarray:
    if rgb_arr.ndim != 3 or rgb_arr.shape[2] < 3:
        return normalize(rgb_arr)
    r = rgb_arr[:, :, 0]
    g = rgb_arr[:, :, 1]
    b = rgb_arr[:, :, 2]
    gray = 0.2989 * r + 0.5870 * g + 0.1140 * b
    return normalize(gray)


def build_decliv_overlay_figure(base_arr: np.ndarray, class_arr: np.ndarray, bounds, title: str):
    x, y = raster_coordinates(bounds, base_arr.shape)
    class_labels = ["Plano 0-3%", "Suave 3-8%", "Ondulado 8-20%", "Forte 20-45%", "Montanhoso >45%"]
    colors = ["#1f77b4", "#7fc8f8", "#f4a261", "#e76f51", "#7f5539"]
    scale = []
    for i, c in enumerate(colors):
        v0 = i / 4.0
        v1 = min((i + 0.999) / 4.0, 1.0)
        scale.append([v0, c])
        scale.append([v1, c])

    fig = go.Figure()
    fig.add_trace(
        go.Heatmap(
            z=base_arr,
            x=x,
            y=y,
            colorscale="gray",
            zmin=0,
            zmax=1,
            showscale=False,
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Heatmap(
            z=class_arr,
            x=x,
            y=y,
            colorscale=scale,
            zmin=0,
            zmax=4,
            opacity=0.48,
            colorbar=dict(
                title="Classe de declividade",
                tickvals=[0, 1, 2, 3, 4],
                ticktext=class_labels,
            ),
            hoverongaps=False,
        )
    )
    fig.update_yaxes(autorange="reversed", scaleanchor="x", scaleratio=1)
    fig.update_layout(
        title=title,
        height=560,
        margin=dict(l=10, r=10, t=42, b=10),
        xaxis_title="Longitude",
        yaxis_title="Latitude",
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def build_flow_direction_figure(base_arr: np.ndarray, receiver_2d: np.ndarray, bounds, title: str, step: int = 14):
    x, y = raster_coordinates(bounds, base_arr.shape)
    fig = go.Figure()
    fig.add_trace(
        go.Heatmap(
            z=base_arr,
            x=x,
            y=y,
            colorscale="gray",
            zmin=0,
            zmax=1,
            showscale=False,
            hoverinfo="skip",
        )
    )

    rows, cols = receiver_2d.shape
    xs = []
    ys = []
    for r in range(step, rows - step, step):
        for c in range(step, cols - step, step):
            j = int(receiver_2d[r, c])
            if j < 0:
                continue
            rn = j // cols
            cn = j % cols
            if rn == r and cn == c:
                continue
            xs.extend([x[c], x[cn], None])
            ys.extend([y[r], y[rn], None])

    fig.add_trace(
        go.Scatter(
            x=xs,
            y=ys,
            mode="lines",
            line=dict(color="#00d4ff", width=1.2),
            opacity=0.75,
            showlegend=False,
            hoverinfo="skip",
        )
    )
    fig.update_yaxes(autorange="reversed", scaleanchor="x", scaleratio=1)
    fig.update_layout(
        title=title,
        height=560,
        margin=dict(l=10, r=10, t=42, b=10),
        xaxis_title="Longitude",
        yaxis_title="Latitude",
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def read_uploaded_table(uploaded_file):
    if uploaded_file is None:
        return None
    data = uploaded_file.getvalue()
    name = uploaded_file.name.lower()
    try:
        if name.endswith(".parquet"):
            return pd.read_parquet(io.BytesIO(data))
        return pd.read_csv(io.BytesIO(data), sep=";", low_memory=False)
    except Exception:
        return pd.read_csv(io.BytesIO(data), low_memory=False)


def load_local_table(path: Path):
    if not path.exists():
        return None
    try:
        df = pd.read_csv(path, sep=";", low_memory=False)
        if len(df.columns) <= 1:
            df = pd.read_csv(path, low_memory=False)
        return df
    except Exception:
        try:
            return pd.read_csv(path, low_memory=False)
        except Exception:
            return None


def find_latest_csv_by_prefix(prefix: str):
    candidates = sorted(GEE_DATA_DIR.glob(f"{prefix}*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def load_gee_decision_exports():
    loaded = {}
    sources = {}
    for key, prefix in GEE_DECISION_PREFIXES.items():
        latest = find_latest_csv_by_prefix(prefix)
        if latest is None:
            loaded[key] = None
            continue
        df = load_local_table(latest)
        loaded[key] = df
        sources[key] = latest.name
    loaded["sources"] = sources
    return loaded


def infer_column(df: pd.DataFrame, patterns: list[str]):
    cols = list(df.columns)
    for p in patterns:
        regex = re.compile(p, flags=re.IGNORECASE)
        for c in cols:
            if regex.search(str(c)):
                return c
    return None


def first_existing_column(df: pd.DataFrame, candidates: list[str]):
    col_map = {str(c).lower(): c for c in df.columns}
    for c in candidates:
        if c.lower() in col_map:
            return col_map[c.lower()]
    return None


def enrich_priority_with_gee(priority_df: pd.DataFrame, gee_talhoes_stats: pd.DataFrame | None) -> pd.DataFrame:
    if priority_df is None or priority_df.empty:
        return pd.DataFrame()
    if gee_talhoes_stats is None or gee_talhoes_stats.empty:
        return priority_df.copy()

    out = priority_df.copy()
    out["TALHAO_NUM"] = pd.to_numeric(out.get("TALHAO_NUM"), errors="coerce")
    gee = gee_talhoes_stats.copy()
    talhao_col = first_existing_column(gee, ["TALHAO"])
    if talhao_col is None:
        return out

    gee["TALHAO_NUM"] = pd.to_numeric(gee[talhao_col], errors="coerce")
    select_cols = ["TALHAO_NUM"]
    metric_map = {
        "STRESS_INDEX_mean": "Stress GEE medio (0-1)",
        "NDVI_SEASON_MEDIAN_mean": "NDVI GEE safra medio",
        "NDVI_DIFF_JAN_MAR_mean": "NDVI GEE dif Jan-Mar",
        "TEMP_MAX_C_mean": "Temp max GEE media (C)",
        "RAIN_SUM_MM_mean": "Chuva GEE acumulada (mm)",
    }
    for src, _ in metric_map.items():
        col = first_existing_column(gee, [src])
        if col is not None:
            select_cols.append(col)

    gee = gee[select_cols].dropna(subset=["TALHAO_NUM"])
    if gee.empty:
        return out

    rename_map = {}
    for src, dst in metric_map.items():
        col = first_existing_column(gee, [src])
        if col is not None:
            rename_map[col] = dst
    gee = gee.rename(columns=rename_map)
    gee_group = gee.groupby("TALHAO_NUM", as_index=False).mean(numeric_only=True)
    out = out.merge(gee_group, on="TALHAO_NUM", how="left")

    gee_risk_parts = []
    if "Stress GEE medio (0-1)" in out.columns and out["Stress GEE medio (0-1)"].notna().any():
        gee_risk_parts.append(minmax_norm_series(out["Stress GEE medio (0-1)"]).to_numpy())
    if "NDVI GEE safra medio" in out.columns and out["NDVI GEE safra medio"].notna().any():
        gee_risk_parts.append(1.0 - minmax_norm_series(out["NDVI GEE safra medio"]).to_numpy())
    if "Temp max GEE media (C)" in out.columns and out["Temp max GEE media (C)"].notna().any():
        gee_risk_parts.append(minmax_norm_series(out["Temp max GEE media (C)"]).to_numpy())
    if "Chuva GEE acumulada (mm)" in out.columns and out["Chuva GEE acumulada (mm)"].notna().any():
        gee_risk_parts.append(1.0 - minmax_norm_series(out["Chuva GEE acumulada (mm)"]).to_numpy())

    if gee_risk_parts:
        gee_risk = np.nanmean(np.vstack(gee_risk_parts), axis=0)
        out["Risco GEE (0-100)"] = (gee_risk * 100.0).round(1)
        if "Score de prioridade (0-100)" in out.columns:
            out["Score integrado (0-100)"] = (
                0.80 * pd.to_numeric(out["Score de prioridade (0-100)"], errors="coerce")
                + 0.20 * pd.to_numeric(out["Risco GEE (0-100)"], errors="coerce")
            ).round(1)
            out["Prioridade integrada"] = out["Score integrado (0-100)"].apply(priority_class)

    return out


def summarize_rain_climate(df: pd.DataFrame):
    if df is None or df.empty:
        return None, "sem_dados"
    date_col = infer_column(df, [r"data|date|dt"])
    rain_col = infer_column(df, [r"chuva|rain|precip"])
    temp_col = infer_column(df, [r"temperatura|temp"])
    hum_col = infer_column(df, [r"umidade|humidity"])
    wind_col = infer_column(df, [r"vento|wind"])

    out = df.copy()
    if date_col:
        out[date_col] = pd.to_datetime(out[date_col], errors="coerce")
    for c in [rain_col, temp_col, hum_col, wind_col]:
        if c:
            out[c] = pd.to_numeric(out[c], errors="coerce")
    return {
        "df": out,
        "date_col": date_col,
        "rain_col": rain_col,
        "temp_col": temp_col,
        "hum_col": hum_col,
        "wind_col": wind_col,
    }, "ok"


def inject_modern_css():
    st.markdown(
        """
<style>
    .stApp {
        background:
            radial-gradient(circle at 15% -10%, #d9efff 0, rgba(217,239,255,0) 45%),
            radial-gradient(circle at 90% 0%, #d8f6eb 0, rgba(216,246,235,0) 40%),
            linear-gradient(180deg, #f8fafc 0%, #eef3f9 100%);
    }
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    .hero-panel {
        border: 1px solid #dbe4f0;
        border-radius: 18px;
        padding: 1.1rem 1.2rem;
        background: linear-gradient(120deg, rgba(9,62,117,0.95), rgba(10,113,122,0.88));
        box-shadow: 0 14px 34px rgba(15,42,66,0.2);
        color: #f8fbff;
        margin-bottom: 0.9rem;
    }
    .hero-panel h2 {
        margin: 0;
        font-size: 1.65rem;
        line-height: 1.2;
        letter-spacing: 0.1px;
    }
    .hero-panel p {
        margin: 0.5rem 0 0 0;
        font-size: 0.97rem;
        opacity: 0.95;
    }
    .kpi-card {
        border: 1px solid #dde7f3;
        border-radius: 14px;
        padding: 0.85rem 0.95rem;
        min-height: 92px;
        background: rgba(255,255,255,0.8);
        box-shadow: 0 8px 22px rgba(22,53,87,0.08);
    }
    .kpi-label {
        font-size: 0.78rem;
        color: #58718b;
        letter-spacing: 0.4px;
        text-transform: uppercase;
        font-weight: 600;
    }
    .kpi-value {
        margin-top: 0.15rem;
        font-size: 1.35rem;
        font-weight: 700;
        color: #0d2942;
        line-height: 1.1;
    }
    .kpi-sub {
        margin-top: 0.25rem;
        font-size: 0.82rem;
        color: #54708a;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.55rem;
        margin-bottom: 0.65rem;
    }
    .stTabs [data-baseweb="tab"] {
        background: rgba(255,255,255,0.75);
        border: 1px solid #dce6f1;
        border-radius: 999px;
        color: #1b3a56;
        padding: 0.45rem 1rem;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #0d5e95, #0b8f9e);
        color: #ffffff !important;
        border-color: transparent;
    }
    .control-panel {
        border: 1px solid #dce6f1;
        border-radius: 14px;
        padding: 0.9rem 1rem;
        background: rgba(255,255,255,0.86);
        box-shadow: 0 8px 24px rgba(22,53,87,0.08);
    }
    .stDataFrame, .stPlotlyChart, .stAlert {
        border-radius: 14px;
    }
</style>
        """,
        unsafe_allow_html=True,
    )


def kpi_card(label: str, value: str, sub: str = ""):
    st.markdown(
        f"""
<div class="kpi-card">
  <div class="kpi-label">{label}</div>
  <div class="kpi-value">{value}</div>
  <div class="kpi-sub">{sub}</div>
</div>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(show_spinner=False)
def load_operation_data(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, sep=";", low_memory=False)
    if df.shape[1] == 1:
        df = pd.read_csv(path, low_memory=False)

    for col in df.columns:
        if col.startswith("vl_") or col in {
            "latitude_interpolacao",
            "longitude_interpolacao",
            "vl_latitude_inicial",
            "vl_longitude_inicial",
            "vl_latitude_final",
            "vl_longitude_final",
        }:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "dt_hr_local_inicial" in df.columns:
        df["dt_hr_local_inicial"] = pd.to_datetime(df["dt_hr_local_inicial"], errors="coerce")

    return df


@st.cache_data(show_spinner=False)
def load_process_telemetry_data(path: Path) -> pd.DataFrame:
    df = load_operation_data(path)
    required = {"dt_hr_local_inicial", "vl_tempo_segundos", "cd_estado", "cd_equipamento", "desc_parada"}
    if not required.issubset(df.columns):
        return pd.DataFrame()

    out = df.copy()
    out["vl_tempo_segundos"] = pd.to_numeric(out["vl_tempo_segundos"], errors="coerce").fillna(0).clip(lower=0)
    out = out.dropna(subset=["dt_hr_local_inicial"]).copy()
    if out.empty:
        return out

    out["dt_hr_fim"] = out["dt_hr_local_inicial"] + pd.to_timedelta(out["vl_tempo_segundos"], unit="s")
    out["data"] = out["dt_hr_local_inicial"].dt.date
    out["hora"] = out["dt_hr_local_inicial"].dt.hour
    out["cd_equipamento"] = out["cd_equipamento"].astype(str)
    out["desc_parada"] = out["desc_parada"].fillna("*NAO_DEFINIDO*").astype(str)
    out["estado_raw"] = out["cd_estado"].astype(str).str.upper().str.strip()

    estado_map = {
        "E": "Efetivo",
        "P": "Parada",
        "F": "Parada",
        "M": "Manobra",
        "D": "Deslocamento",
    }
    out["estado_processo"] = out["estado_raw"].map(estado_map).fillna("Outros")
    out["is_parada"] = out["estado_processo"].eq("Parada")
    return out


@st.cache_data(show_spinner=False)
def load_professional_ops_dataset(
    telemetry_path: Path,
    decliv_path: Path,
    fields_path: Path,
) -> pd.DataFrame:
    if not telemetry_path.exists():
        return pd.DataFrame()
    if not decliv_path.exists():
        return pd.DataFrame()

    df = load_operation_data(telemetry_path)
    required = {
        "dt_hr_local_inicial",
        "cd_equipamento",
        "cd_estado",
        "vl_tempo_segundos",
        "vl_consumo_instantaneo",
        "latitude_interpolacao",
        "longitude_interpolacao",
    }
    if not required.issubset(df.columns):
        return pd.DataFrame()

    out = df.copy()
    out["cd_equipamento"] = out["cd_equipamento"].astype(str)
    out["cd_estado"] = out["cd_estado"].astype(str).str.upper().str.strip()
    out["desc_parada"] = out.get("desc_parada", "").fillna("*NAO_DEFINIDO*").astype(str).str.strip()
    out["desc_operador"] = out.get("desc_operador", "").fillna("*NAO_DEFINIDO*").astype(str).str.strip()
    out["cd_operador"] = out.get("cd_operador", "").astype(str).str.strip()

    out = out.dropna(subset=["dt_hr_local_inicial"]).copy()
    out["vl_tempo_segundos"] = pd.to_numeric(out["vl_tempo_segundos"], errors="coerce")
    out["vl_consumo_instantaneo"] = pd.to_numeric(out["vl_consumo_instantaneo"], errors="coerce")
    if "vl_hectares_hora" in out.columns:
        out["vl_hectares_hora"] = pd.to_numeric(out["vl_hectares_hora"], errors="coerce")
    if "vl_latitude_inicial" in out.columns:
        out["vl_latitude_inicial"] = pd.to_numeric(out["vl_latitude_inicial"], errors="coerce")
    if "vl_longitude_inicial" in out.columns:
        out["vl_longitude_inicial"] = pd.to_numeric(out["vl_longitude_inicial"], errors="coerce")
    if "vl_latitude_final" in out.columns:
        out["vl_latitude_final"] = pd.to_numeric(out["vl_latitude_final"], errors="coerce")
    if "vl_longitude_final" in out.columns:
        out["vl_longitude_final"] = pd.to_numeric(out["vl_longitude_final"], errors="coerce")
    if "vl_velocidade" in out.columns:
        out["vl_velocidade"] = pd.to_numeric(out["vl_velocidade"], errors="coerce")

    out = out[
        out["latitude_interpolacao"].between(-90, 90)
        & out["longitude_interpolacao"].between(-180, 180)
        & out["vl_tempo_segundos"].between(1, 7200)
        & out["vl_consumo_instantaneo"].between(0, 120)
    ].copy()

    if out.empty:
        return out

    estado_map = {
        "E": "Efetivo",
        "P": "Parada",
        "F": "Parada",
        "M": "Manobra",
        "D": "Deslocamento",
    }
    out["estado_processo"] = out["cd_estado"].map(estado_map).fillna("Outros")
    out["data"] = out["dt_hr_local_inicial"].dt.date
    out["hora"] = out["dt_hr_local_inicial"].dt.hour
    out["horas_evento"] = out["vl_tempo_segundos"] / 3600.0
    out["consumo_l_estimado"] = out["vl_consumo_instantaneo"] * out["horas_evento"]

    if "vl_hectares_hora" in out.columns:
        out["hectares_evento"] = out["vl_hectares_hora"].fillna(0) * out["horas_evento"]
    else:
        out["hectares_evento"] = 0.0

    # Amostra raster de declividade por ponto.
    with rasterio.open(decliv_path) as src:
        slope_arr = src.read(1).astype("float64")
        nodata = src.nodata
        if nodata is not None:
            slope_arr = np.where(slope_arr == nodata, np.nan, slope_arr)
        inv = ~src.transform
        cols_f, rows_f = inv * (
            out["longitude_interpolacao"].to_numpy(),
            out["latitude_interpolacao"].to_numpy(),
        )
        rows = np.floor(rows_f).astype(int)
        cols = np.floor(cols_f).astype(int)
        inside = (
            (rows >= 0)
            & (rows < slope_arr.shape[0])
            & (cols >= 0)
            & (cols < slope_arr.shape[1])
        )
        slope = np.full(len(out), np.nan)
        slope[inside] = slope_arr[rows[inside], cols[inside]]

    out["declividade_pct"] = slope
    out = out[out["declividade_pct"].between(0, 80)].copy()
    if out.empty:
        return out

    slope_bins = [0, 3, 8, 20, 45, np.inf]
    slope_labels = ["0-3%", "3-8%", "8-20%", "20-45%", ">45%"]
    out["classe_decliv"] = pd.cut(
        out["declividade_pct"], bins=slope_bins, labels=slope_labels, right=False
    ).astype(str)

    # Join espacial com talhões.
    if fields_path.exists():
        points = gpd.GeoDataFrame(
            out,
            geometry=gpd.points_from_xy(out["longitude_interpolacao"], out["latitude_interpolacao"]),
            crs="EPSG:4326",
        )
        fields = load_fields_map(fields_path)
        if fields.crs is None:
            fields = fields.set_crs("EPSG:4326")
        elif str(fields.crs) != "EPSG:4326":
            fields = fields.to_crs("EPSG:4326")
        keep_cols = [
            c for c in ["DESC_TALHA", "TALHAO", "NOME_FAZ", "FAZENDA", "ZONA", "AREA_TOTAL"] if c in fields.columns
        ]
        points = gpd.sjoin(points, fields[keep_cols + ["geometry"]], how="left", predicate="within")
        points["talhao_label"] = points.get("DESC_TALHA", pd.Series(index=points.index)).fillna("SEM_TALHAO").astype(str)
        out = pd.DataFrame(points.drop(columns=["geometry"], errors="ignore"))
    else:
        out["talhao_label"] = "SEM_TALHAO"

    # Sem apontamento (regra operacional).
    out["sem_apontamento"] = (
        out["desc_parada"].str.upper().eq("*NAO_DEFINIDO*")
        | out["desc_operador"].str.upper().eq("*NAO_DEFINIDO*")
        | out["cd_operador"].eq("-1")
    )

    # Direção operacional por bearing.
    has_seg = {"vl_latitude_inicial", "vl_longitude_inicial", "vl_latitude_final", "vl_longitude_final"}.issubset(out.columns)
    out["bearing_deg"] = np.nan
    out["dist_m"] = np.nan
    out["speed_m_s_impl"] = np.nan
    out["direcao_setor"] = np.nan
    out["dir_valida"] = False
    if has_seg:
        lat1 = out["vl_latitude_inicial"]
        lon1 = out["vl_longitude_inicial"]
        lat2 = out["vl_latitude_final"]
        lon2 = out["vl_longitude_final"]
        seg_ok = (
            lat1.between(-90, 90)
            & lat2.between(-90, 90)
            & lon1.between(-180, 180)
            & lon2.between(-180, 180)
        )
        if seg_ok.any():
            lat1r = np.deg2rad(lat1)
            lat2r = np.deg2rad(lat2)
            dlon = np.deg2rad(lon2 - lon1)
            y = np.sin(dlon) * np.cos(lat2r)
            x = np.cos(lat1r) * np.sin(lat2r) - np.sin(lat1r) * np.cos(lat2r) * np.cos(dlon)
            bearing = (np.degrees(np.arctan2(y, x)) + 360) % 360
            out.loc[seg_ok, "bearing_deg"] = bearing[seg_ok]

            # Haversine para distância e velocidade implícita.
            radius = 6371000.0
            dphi = np.deg2rad(lat2 - lat1)
            dlam = np.deg2rad(lon2 - lon1)
            a = np.sin(dphi / 2.0) ** 2 + np.cos(lat1r) * np.cos(lat2r) * np.sin(dlam / 2.0) ** 2
            c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
            dist = radius * c
            out.loc[seg_ok, "dist_m"] = dist[seg_ok]
            out.loc[seg_ok, "speed_m_s_impl"] = out.loc[seg_ok, "dist_m"] / out.loc[seg_ok, "vl_tempo_segundos"]

            labels = np.array(["N", "NE", "E", "SE", "S", "SW", "W", "NW"], dtype=object)
            sectors = ((out["bearing_deg"] + 22.5) // 45) % 8
            out.loc[seg_ok, "direcao_setor"] = sectors[seg_ok].map({i: labels[i] for i in range(8)})
            out["dir_valida"] = seg_ok & out["dist_m"].ge(5) & out["speed_m_s_impl"].le(20)

    return out.reset_index(drop=True)


def _utm_epsg_from_lonlat(lon: float, lat: float) -> int:
    zone = int(np.floor((lon + 180.0) / 6.0) + 1)
    zone = min(max(zone, 1), 60)
    return 32600 + zone if lat >= 0 else 32700 + zone


@st.cache_data(show_spinner=False)
def estimate_overlap_by_machine_day(df: pd.DataFrame, max_points_per_group: int = 3000) -> pd.DataFrame:
    required = {
        "data",
        "cd_equipamento",
        "dt_hr_local_inicial",
        "latitude_interpolacao",
        "longitude_interpolacao",
        "vl_largura_implemento",
    }
    if df is None or df.empty or not required.issubset(df.columns):
        return pd.DataFrame()

    use = df.copy()
    use = use.dropna(subset=["latitude_interpolacao", "longitude_interpolacao", "vl_largura_implemento"]).copy()
    use = use[
        use["latitude_interpolacao"].between(-90, 90)
        & use["longitude_interpolacao"].between(-180, 180)
        & use["vl_largura_implemento"].between(0.5, 30.0)
    ].copy()
    if use.empty:
        return pd.DataFrame()

    lon0 = float(use["longitude_interpolacao"].median())
    lat0 = float(use["latitude_interpolacao"].median())
    epsg = _utm_epsg_from_lonlat(lon0, lat0)

    points = gpd.GeoDataFrame(
        use,
        geometry=gpd.points_from_xy(use["longitude_interpolacao"], use["latitude_interpolacao"]),
        crs="EPSG:4326",
    ).to_crs(epsg=epsg)

    rows = []
    for (day, equip), grp in points.groupby(["data", "cd_equipamento"], sort=False):
        grp = grp.sort_values("dt_hr_local_inicial")
        if len(grp) < 3:
            continue
        if len(grp) > max_points_per_group:
            stride = int(np.ceil(len(grp) / max_points_per_group))
            grp = grp.iloc[::stride, :]
        if len(grp) < 3:
            continue

        coords = np.array([(g.x, g.y) for g in grp.geometry])
        seg = coords[1:] - coords[:-1]
        seg_dist = np.sqrt((seg[:, 0] ** 2) + (seg[:, 1] ** 2))
        seg_dist = seg_dist[np.isfinite(seg_dist)]
        seg_dist = seg_dist[seg_dist > 0.5]
        if seg_dist.size == 0:
            continue

        width_m = float(np.nanmedian(grp["vl_largura_implemento"]))
        if not np.isfinite(width_m) or width_m <= 0:
            continue

        # Área teórica = soma(distância * largura).
        theoretical_m2 = float(seg_dist.sum() * width_m)
        if theoretical_m2 <= 0:
            continue

        from shapely.geometry import LineString

        line = LineString(coords.tolist())
        swept = line.buffer(width_m / 2.0, cap_style=2, join_style=2)
        unique_m2 = float(swept.area) if swept is not None else np.nan
        if not np.isfinite(unique_m2) or unique_m2 <= 0:
            continue

        overlap_m2 = max(theoretical_m2 - unique_m2, 0.0)
        overlap_pct = (overlap_m2 / theoretical_m2) * 100.0
        center = swept.centroid

        rows.append(
            {
                "data": day,
                "cd_equipamento": str(equip),
                "largura_media_m": width_m,
                "area_teorica_ha": theoretical_m2 / 10000.0,
                "area_unica_ha": unique_m2 / 10000.0,
                "area_sobreposicao_ha": overlap_m2 / 10000.0,
                "sobreposicao_pct": overlap_pct,
                "pts_usados": int(len(grp)),
                "center_x": center.x,
                "center_y": center.y,
            }
        )

    if not rows:
        return pd.DataFrame()

    out = pd.DataFrame(rows)
    centers = gpd.GeoDataFrame(
        out,
        geometry=gpd.points_from_xy(out["center_x"], out["center_y"]),
        crs=f"EPSG:{epsg}",
    ).to_crs("EPSG:4326")
    out["center_lon"] = centers.geometry.x
    out["center_lat"] = centers.geometry.y
    return out.drop(columns=["center_x", "center_y"])


@st.cache_data(show_spinner=False)
def build_machine_coverage_polygons(
    df: pd.DataFrame,
    max_points_per_machine: int = 3000,
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    required = {
        "cd_equipamento",
        "dt_hr_local_inicial",
        "latitude_interpolacao",
        "longitude_interpolacao",
        "vl_largura_implemento",
    }
    empty = gpd.GeoDataFrame(columns=["cd_equipamento", "area_ha", "theoretical_ha", "overlap_pct_theoretical", "geometry"], geometry="geometry", crs="EPSG:4326")
    if df is None or df.empty or not required.issubset(df.columns):
        return empty, empty

    use = df.copy()
    use = use.dropna(subset=["latitude_interpolacao", "longitude_interpolacao", "vl_largura_implemento"]).copy()
    use = use[
        use["latitude_interpolacao"].between(-90, 90)
        & use["longitude_interpolacao"].between(-180, 180)
        & use["vl_largura_implemento"].between(0.5, 30.0)
    ].copy()
    if use.empty:
        return empty, empty

    lon0 = float(use["longitude_interpolacao"].median())
    lat0 = float(use["latitude_interpolacao"].median())
    epsg = _utm_epsg_from_lonlat(lon0, lat0)

    points = gpd.GeoDataFrame(
        use,
        geometry=gpd.points_from_xy(use["longitude_interpolacao"], use["latitude_interpolacao"]),
        crs="EPSG:4326",
    ).to_crs(epsg=epsg)

    rows = []
    for equip, grp in points.groupby("cd_equipamento", sort=False):
        grp = grp.sort_values("dt_hr_local_inicial")
        if len(grp) < 3:
            continue
        if len(grp) > max_points_per_machine:
            stride = int(np.ceil(len(grp) / max_points_per_machine))
            grp = grp.iloc[::stride, :]
        if len(grp) < 3:
            continue

        coords = np.array([(g.x, g.y) for g in grp.geometry])
        seg = coords[1:] - coords[:-1]
        seg_dist = np.sqrt((seg[:, 0] ** 2) + (seg[:, 1] ** 2))
        seg_dist = seg_dist[np.isfinite(seg_dist)]
        seg_dist = seg_dist[seg_dist > 0.5]
        if seg_dist.size == 0:
            continue

        width_m = float(np.nanmedian(grp["vl_largura_implemento"]))
        if not np.isfinite(width_m) or width_m <= 0:
            continue

        line = LineString(coords.tolist())
        poly = line.buffer(width_m / 2.0, cap_style=2, join_style=2)
        if poly.is_empty:
            continue
        theoretical_m2 = float(seg_dist.sum() * width_m)
        unique_m2 = float(poly.area)
        overlap_pct = ((theoretical_m2 - unique_m2) / theoretical_m2 * 100.0) if theoretical_m2 > 0 else np.nan

        rows.append(
            {
                "cd_equipamento": str(equip),
                "area_ha": unique_m2 / 10000.0,
                "theoretical_ha": theoretical_m2 / 10000.0,
                "overlap_pct_theoretical": overlap_pct,
                "geometry": poly,
            }
        )

    if not rows:
        return empty, empty

    gdf_utm = gpd.GeoDataFrame(rows, geometry="geometry", crs=f"EPSG:{epsg}")
    gdf_ll = gdf_utm.to_crs("EPSG:4326")
    return gdf_ll, gdf_utm


def build_overlap_polygon(gdf_utm: gpd.GeoDataFrame) -> Polygon | MultiPolygon | None:
    if gdf_utm is None or gdf_utm.empty or len(gdf_utm) < 2:
        return None
    polys = [g for g in gdf_utm.geometry if g is not None and not g.is_empty]
    if len(polys) < 2:
        return None
    inters = []
    for i in range(len(polys)):
        for j in range(i + 1, len(polys)):
            inter = polys[i].intersection(polys[j])
            if inter is not None and not inter.is_empty and inter.area > 0:
                inters.append(inter)
    if not inters:
        return None
    return unary_union(inters)


def add_polygon_to_mapbox(
    fig: go.Figure,
    geom,
    name: str,
    line_color: str,
    fill_color: str,
    line_width: float = 1.5,
    showlegend: bool = True,
):
    if geom is None:
        return
    geoms = []
    if isinstance(geom, Polygon):
        geoms = [geom]
    elif isinstance(geom, MultiPolygon):
        geoms = list(geom.geoms)
    else:
        try:
            geoms = [g for g in geom.geoms if isinstance(g, Polygon)]
        except Exception:
            geoms = []
    first = True
    for poly in geoms:
        if poly.is_empty:
            continue
        x, y = poly.exterior.xy
        fig.add_trace(
            go.Scattermapbox(
                lon=list(x),
                lat=list(y),
                mode="lines",
                line=dict(color=line_color, width=line_width),
                fill="toself",
                fillcolor=fill_color,
                name=name,
                showlegend=showlegend and first,
                hoverinfo="skip",
            )
        )
        first = False


@st.cache_data(show_spinner=False)
def build_swath_segment_polygons(
    df: pd.DataFrame,
    max_segments_per_machine: int = 700,
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    required = {
        "cd_equipamento",
        "dt_hr_local_inicial",
        "latitude_interpolacao",
        "longitude_interpolacao",
        "vl_largura_implemento",
    }
    empty = gpd.GeoDataFrame(columns=["cd_equipamento", "segment_len_m", "width_m", "geometry"], geometry="geometry", crs="EPSG:4326")
    if df is None or df.empty or not required.issubset(df.columns):
        return empty, empty

    use = df.copy()
    use = use.dropna(subset=["latitude_interpolacao", "longitude_interpolacao", "vl_largura_implemento"]).copy()
    use = use[
        use["latitude_interpolacao"].between(-90, 90)
        & use["longitude_interpolacao"].between(-180, 180)
        & use["vl_largura_implemento"].between(0.5, 30.0)
    ].copy()
    if use.empty:
        return empty, empty

    lon0 = float(use["longitude_interpolacao"].median())
    lat0 = float(use["latitude_interpolacao"].median())
    epsg = _utm_epsg_from_lonlat(lon0, lat0)
    pts = gpd.GeoDataFrame(
        use,
        geometry=gpd.points_from_xy(use["longitude_interpolacao"], use["latitude_interpolacao"]),
        crs="EPSG:4326",
    ).to_crs(epsg=epsg)

    rows = []
    for equip, grp in pts.groupby("cd_equipamento", sort=False):
        grp = grp.sort_values("dt_hr_local_inicial")
        if len(grp) < 2:
            continue
        if len(grp) > (max_segments_per_machine + 1):
            stride = int(np.ceil(len(grp) / float(max_segments_per_machine + 1)))
            grp = grp.iloc[::stride, :]
        if len(grp) < 2:
            continue

        coords = np.array([(g.x, g.y) for g in grp.geometry])
        widths = grp["vl_largura_implemento"].to_numpy()
        for i in range(1, len(coords)):
            p0 = coords[i - 1]
            p1 = coords[i]
            seg_len = float(np.hypot(*(p1 - p0)))
            if not np.isfinite(seg_len) or seg_len < 0.5:
                continue
            width_m = float(np.nanmedian([widths[i - 1], widths[i]]))
            if not np.isfinite(width_m) or width_m <= 0:
                continue
            seg_line = LineString([tuple(p0), tuple(p1)])
            seg_poly = seg_line.buffer(width_m / 2.0, cap_style=2, join_style=2)
            if seg_poly.is_empty:
                continue
            rows.append(
                {
                    "cd_equipamento": str(equip),
                    "segment_len_m": seg_len,
                    "width_m": width_m,
                    "geometry": seg_poly,
                }
            )

    if not rows:
        return empty, empty

    gdf_utm = gpd.GeoDataFrame(rows, geometry="geometry", crs=f"EPSG:{epsg}")
    gdf_ll = gdf_utm.to_crs("EPSG:4326")
    return gdf_ll, gdf_utm


def infer_coordinate_columns(df: pd.DataFrame):
    if {"latitude_interpolacao", "longitude_interpolacao"}.issubset(df.columns):
        return "latitude_interpolacao", "longitude_interpolacao"
    if {"vl_latitude_inicial", "vl_longitude_inicial"}.issubset(df.columns):
        return "vl_latitude_inicial", "vl_longitude_inicial"
    return None, None


def sample_raster_values(arr: np.ndarray, transform, lons: np.ndarray, lats: np.ndarray) -> np.ndarray:
    if len(lons) == 0:
        return np.array([], dtype="float64")

    inv = ~transform
    cols_f, rows_f = inv * (lons, lats)
    rows = np.floor(rows_f).astype(int)
    cols = np.floor(cols_f).astype(int)

    out = np.full(len(lons), np.nan, dtype="float64")
    inside = (rows >= 0) & (rows < arr.shape[0]) & (cols >= 0) & (cols < arr.shape[1])
    out[inside] = arr[rows[inside], cols[inside]]
    return out


def build_operation_terrain_df(df_op: pd.DataFrame, rasters_dict: dict) -> pd.DataFrame:
    lat_col, lon_col = infer_coordinate_columns(df_op)
    if not lat_col or not lon_col:
        return pd.DataFrame()

    out = df_op.copy()
    coords_ok = out[lat_col].between(-90, 90) & out[lon_col].between(-180, 180)
    out = out.loc[coords_ok].copy()
    out["elevacao_mdt"] = sample_raster_values(
        rasters_dict["MDT (Elevacao)"]["arr"],
        rasters_dict["MDT (Elevacao)"]["transform"],
        out[lon_col].to_numpy(),
        out[lat_col].to_numpy(),
    )
    out["declividade_pct"] = sample_raster_values(
        rasters_dict["Declividade"]["arr"],
        rasters_dict["Declividade"]["transform"],
        out[lon_col].to_numpy(),
        out[lat_col].to_numpy(),
    )

    if {"vl_consumo_instantaneo", "vl_rpm", "vl_velocidade"}.issubset(out.columns):
        speed = out["vl_velocidade"].clip(lower=0.1)
        slope_factor = 1 + out["declividade_pct"].fillna(0).clip(lower=0) / 100.0
        out["indice_esforco_relativo"] = (out["vl_consumo_instantaneo"] * out["vl_rpm"] / speed) * slope_factor

    return out


def add_linear_trendline(fig, x: np.ndarray, y: np.ndarray, name: str = "Tendencia linear"):
    valid = np.isfinite(x) & np.isfinite(y)
    if valid.sum() < 2:
        return fig

    x_fit = x[valid]
    y_fit = y[valid]
    coef = np.polyfit(x_fit, y_fit, 1)
    x_line = np.linspace(np.nanmin(x_fit), np.nanmax(x_fit), 100)
    y_line = coef[0] * x_line + coef[1]
    fig.add_trace(
        go.Scatter(
            x=x_line,
            y=y_line,
            mode="lines",
            name=name,
            line=dict(color="#d1495b", width=2.4),
        )
    )
    return fig


def classify_correlation(value: float) -> str:
    if pd.isna(value):
        return "indefinida"
    strength = abs(value)
    if strength < 0.2:
        band = "muito fraca"
    elif strength < 0.4:
        band = "fraca"
    elif strength < 0.6:
        band = "moderada"
    elif strength < 0.8:
        band = "forte"
    else:
        band = "muito forte"
    direction = "positiva" if value >= 0 else "negativa"
    return f"{band} e {direction}"


def pct_change(base: float, new: float) -> float:
    if pd.isna(base) or pd.isna(new) or base == 0:
        return np.nan
    return (new / base - 1.0) * 100.0


def minutes_to_hhmm(value: float) -> str:
    if pd.isna(value):
        return "n/d"
    total = int(round(float(value)))
    hh = total // 60
    mm = total % 60
    return f"{hh:02d}:{mm:02d}"


def compress_process_intervals(df: pd.DataFrame, gap_seconds: int = 30) -> pd.DataFrame:
    required = {
        "data",
        "cd_equipamento",
        "estado_processo",
        "dt_hr_local_inicial",
        "dt_hr_fim",
    }
    if df is None or df.empty or not required.issubset(df.columns):
        return pd.DataFrame()

    work = df.copy()
    work = work.sort_values(["data", "cd_equipamento", "dt_hr_local_inicial"])
    out_rows = []
    max_gap = pd.Timedelta(seconds=gap_seconds)

    for (day, equip), grp in work.groupby(["data", "cd_equipamento"], sort=False):
        current_state = None
        current_start = None
        current_end = None

        for row in grp.itertuples(index=False):
            row_state = str(getattr(row, "estado_processo"))
            row_start = getattr(row, "dt_hr_local_inicial")
            row_end = getattr(row, "dt_hr_fim")
            if pd.isna(row_start) or pd.isna(row_end):
                continue

            if current_state is None:
                current_state = row_state
                current_start = row_start
                current_end = row_end
                continue

            same_state = row_state == current_state
            near_enough = row_start <= (current_end + max_gap)
            if same_state and near_enough:
                if row_end > current_end:
                    current_end = row_end
            else:
                out_rows.append(
                    {
                        "data": day,
                        "cd_equipamento": str(equip),
                        "estado_processo": current_state,
                        "dt_inicio": current_start,
                        "dt_fim": current_end,
                    }
                )
                current_state = row_state
                current_start = row_start
                current_end = row_end

        if current_state is not None:
            out_rows.append(
                {
                    "data": day,
                    "cd_equipamento": str(equip),
                    "estado_processo": current_state,
                    "dt_inicio": current_start,
                    "dt_fim": current_end,
                }
            )

    if not out_rows:
        return pd.DataFrame()

    out = pd.DataFrame(out_rows)
    out["data_str"] = pd.to_datetime(out["data"]).dt.strftime("%Y-%m-%d")
    out["start_min"] = (
        out["dt_inicio"].dt.hour * 60 + out["dt_inicio"].dt.minute + out["dt_inicio"].dt.second / 60.0
    )
    out["end_min"] = out["dt_fim"].dt.hour * 60 + out["dt_fim"].dt.minute + out["dt_fim"].dt.second / 60.0
    cross_midnight = out["dt_fim"].dt.date != out["dt_inicio"].dt.date
    out.loc[cross_midnight, "end_min"] = 24 * 60 - 0.01
    out["start_min"] = out["start_min"].clip(lower=0, upper=24 * 60 - 0.01)
    out["end_min"] = out["end_min"].clip(lower=0, upper=24 * 60 - 0.01)
    out["dur_min"] = (out["end_min"] - out["start_min"]).clip(lower=0.01)
    out["inicio_hhmm"] = out["dt_inicio"].dt.strftime("%H:%M:%S")
    out["fim_hhmm"] = out["dt_fim"].dt.strftime("%H:%M:%S")
    out["dur_h"] = out["dur_min"] / 60.0
    return out


def minmax_norm_series(series: pd.Series) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce")
    smin = s.min(skipna=True)
    smax = s.max(skipna=True)
    if pd.isna(smin) or pd.isna(smax) or smax <= smin:
        return pd.Series(np.zeros(len(s)), index=s.index, dtype="float64")
    return (s - smin) / (smax - smin)


def priority_class(score: float) -> str:
    if pd.isna(score):
        return "Sem dados"
    if score >= 70:
        return "Critica"
    if score >= 50:
        return "Alta"
    if score >= 30:
        return "Moderada"
    return "Baixa"


def build_action_recommendation(row: pd.Series) -> str:
    points = []
    if row.get("Declividade P95 (%)", np.nan) >= 20:
        points.append("alta declividade")
    if row.get("Runoff medio (0-1)", np.nan) >= 0.6:
        points.append("escoamento concentrado")
    if row.get("Esforco medio op.", np.nan) >= row.get("_p75_esforco", np.inf):
        points.append("esforco operacional elevado")
    if row.get("NDVI medio", np.nan) <= row.get("_p25_ndvi", -np.inf):
        points.append("vigor vegetal baixo")
    if not points:
        return "Manter manejo atual e monitoramento de rotina."
    return "Priorizar manejo em: " + ", ".join(points) + "."


def build_specialist_priority_table(talhoes_df: pd.DataFrame, op_terrain_df: pd.DataFrame | None) -> pd.DataFrame:
    if talhoes_df is None or talhoes_df.empty:
        return pd.DataFrame()

    base = talhoes_df.copy()
    if "TALHAO_NUM" in base.columns:
        base["TALHAO_NUM"] = pd.to_numeric(base["TALHAO_NUM"], errors="coerce")

    if op_terrain_df is not None and not op_terrain_df.empty and "cd_talhao" in op_terrain_df.columns:
        op = op_terrain_df.copy()
        op["cd_talhao"] = pd.to_numeric(op["cd_talhao"], errors="coerce")
        if "cd_estado" in op.columns:
            op = op[op["cd_estado"].astype(str).isin(["E", "M"])].copy()
        if "indice_esforco_relativo" in op.columns:
            op_group = (
                op.dropna(subset=["cd_talhao", "indice_esforco_relativo"])
                .groupby("cd_talhao", as_index=False)["indice_esforco_relativo"]
                .mean()
                .rename(columns={"indice_esforco_relativo": "Esforco medio op."})
            )
            base = base.merge(op_group, how="left", left_on="TALHAO_NUM", right_on="cd_talhao")
            if "cd_talhao" in base.columns:
                base = base.drop(columns=["cd_talhao"])

    components = []
    weight_map = {
        "Declividade media (%)": 0.30,
        "Declividade P95 (%)": 0.20,
        "Runoff medio (0-1)": 0.25,
        "Esforco medio op.": 0.25,
    }
    for col in weight_map:
        if col in base.columns and base[col].notna().any():
            components.append(col)

    if not components:
        base["Score de prioridade (0-100)"] = np.nan
        base["Prioridade"] = "Sem dados"
        base["Recomendacao"] = "Dados insuficientes para score."
        return base

    total_w = sum(weight_map[c] for c in components)
    score = np.zeros(len(base), dtype="float64")
    for col in components:
        score += (weight_map[col] / total_w) * minmax_norm_series(base[col]).to_numpy()

    if "NDVI medio" in base.columns and base["NDVI medio"].notna().any():
        ndvi_risk = 1.0 - minmax_norm_series(base["NDVI medio"]).to_numpy()
        score = (0.9 * score) + (0.1 * ndvi_risk)

    base["Score de prioridade (0-100)"] = (score * 100.0).round(1)
    base["Prioridade"] = base["Score de prioridade (0-100)"].apply(priority_class)

    p75_esforco = base["Esforco medio op."].quantile(0.75) if "Esforco medio op." in base.columns else np.nan
    p25_ndvi = base["NDVI medio"].quantile(0.25) if "NDVI medio" in base.columns else np.nan
    base["_p75_esforco"] = p75_esforco
    base["_p25_ndvi"] = p25_ndvi
    base["Recomendacao"] = base.apply(build_action_recommendation, axis=1)
    base = base.drop(columns=["_p75_esforco", "_p25_ndvi"])

    return base.sort_values("Score de prioridade (0-100)", ascending=False).reset_index(drop=True)


inject_modern_css()

missing = [name for name, file in DATA_FILES.items() if not file.exists()]
if missing:
    st.error(f"Arquivos ausentes: {', '.join(missing)}")
    st.stop()

rasters_full = {}
meta_rows = []
for name, path in DATA_FILES.items():
    arr, bounds, transform, crs, res = read_raster(path, mask_zeros=name == "MDT (Elevacao)")
    display_res = approximate_meter_resolution(transform, bounds) if str(crs).upper() == "EPSG:4326" else res
    rasters_full[name] = {
        "arr": arr,
        "bounds": bounds,
        "transform": transform,
        "crs": crs,
        "res": res,
        "display_res": display_res,
    }
    stats = raster_stats(arr)
    meta_rows.append(
        {
            "Camada": name,
            "Arquivo": str(path),
            "CRS": str(crs),
            "Resolucao X (m)": round(display_res[0], 3),
            "Resolucao Y (m)": round(display_res[1], 3),
            **{k: round(v, 3) if isinstance(v, float) else v for k, v in stats.items()},
        }
    )

rasters = {k: v.copy() for k, v in rasters_full.items()}
fields_gdf = None
farm_gdf = None
selected_farm_name = None
selected_farm_id = None
farm_limit = None

if FIELDS_FILE.exists():
    try:
        fields_gdf = load_fields_map(FIELDS_FILE)
        target_crs = rasters_full["MDT (Elevacao)"]["crs"]
        fields_gdf = fields_gdf.to_crs(target_crs)
        fields_gdf["farm_label"] = fields_gdf["NOME_FAZ"].astype(str) + " (ID " + fields_gdf["FAZENDA"].astype(str) + ")"
        farm_options = (
            fields_gdf[["farm_label", "NOME_FAZ", "FAZENDA"]].drop_duplicates().sort_values("farm_label").reset_index(drop=True)
        )

        default_idx = 0
        if DEFAULT_OPERATION_FILE.exists():
            op_seed = load_operation_data(DEFAULT_OPERATION_FILE)
            if "cd_fazenda" in op_seed.columns:
                faz_vals = pd.to_numeric(op_seed["cd_fazenda"], errors="coerce").dropna().astype(int).unique().tolist()
                if faz_vals:
                    match_idx = farm_options.index[farm_options["FAZENDA"].astype(int) == int(faz_vals[0])]
                    if len(match_idx) > 0:
                        default_idx = int(match_idx[0])

        with st.container():
            st.markdown("#### Recorte espacial")
            selected_farm_label = st.selectbox(
                "Fazenda para recorte dos rasters",
                farm_options["farm_label"].tolist(),
                index=default_idx,
            )

        selected_row = farm_options.loc[farm_options["farm_label"] == selected_farm_label].iloc[0]
        selected_farm_name = str(selected_row["NOME_FAZ"])
        selected_farm_id = int(selected_row["FAZENDA"])
        farm_gdf = fields_gdf.loc[fields_gdf["FAZENDA"].astype(int) == selected_farm_id].copy()
        farm_limit = farm_gdf.geometry.union_all() if hasattr(farm_gdf.geometry, "union_all") else farm_gdf.unary_union

        for name in list(rasters.keys()):
            clipped = clip_array_to_geometry(rasters[name]["arr"], rasters[name]["transform"], farm_limit)
            rasters[name] = {**rasters[name], "arr": clipped}
    except Exception as exc:
        st.warning(f"Nao foi possivel aplicar recorte com fields.mbtiles: {exc}")

flow_acc_arr, runoff_idx_arr, flow_receiver_arr = compute_runoff_layers(
    rasters["MDT (Elevacao)"]["arr"],
    rasters["Declividade"]["arr"],
    rasters["MDT (Elevacao)"]["transform"],
    rasters["MDT (Elevacao)"]["bounds"],
)
rasters["Acumulacao de fluxo (D8)"] = {
    **rasters["MDT (Elevacao)"],
    "arr": flow_acc_arr,
}
rasters["Indice de escoamento"] = {
    **rasters["MDT (Elevacao)"],
    "arr": runoff_idx_arr,
}

ndvi_layer = read_optional_singleband_raster(NDVI_FILE)
if ndvi_layer and farm_limit is not None:
    try:
        if str(ndvi_layer["crs"]) != str(rasters["MDT (Elevacao)"]["crs"]):
            st.warning("`ndvi_recente.tif` possui CRS diferente do raster base e nao foi recortado automaticamente.")
        else:
            ndvi_layer["arr"] = clip_array_to_geometry(ndvi_layer["arr"], ndvi_layer["transform"], farm_limit)
    except Exception as exc:
        st.warning(f"Nao foi possivel recortar NDVI: {exc}")

rgb_layer = read_optional_rgb_raster(IMAGERY_FILE)
if rgb_layer and farm_limit is not None:
    try:
        if str(rgb_layer["crs"]) != str(rasters["MDT (Elevacao)"]["crs"]):
            st.warning("`imagem_recente.tif` possui CRS diferente do raster base e nao foi recortada automaticamente.")
        else:
            mask_img = geometry_mask(
                [farm_limit],
                out_shape=rgb_layer["arr"].shape[:2],
                transform=rgb_layer["transform"],
                invert=True,
                all_touched=False,
            )
            rgb_layer["arr"] = np.where(mask_img[:, :, None], rgb_layer["arr"], np.nan)
    except Exception as exc:
        st.warning(f"Nao foi possivel recortar imagem recente: {exc}")

meta_df = pd.DataFrame(
    [
        {
            "Camada": name,
            "Arquivo": str(DATA_FILES[name]) if name in DATA_FILES else "calculado_em_memoria",
            "CRS": str(layer["crs"]),
            "Resolucao X (m)": round(layer["display_res"][0], 3),
            "Resolucao Y (m)": round(layer["display_res"][1], 3),
            **{
                k: round(v, 3) if isinstance(v, float) else v
                for k, v in raster_stats(layer["arr"]).items()
            },
        }
        for name, layer in rasters.items()
    ]
)
mdt_row = meta_df.loc[meta_df["Camada"] == "MDT (Elevacao)"].iloc[0]
declividade_row = meta_df.loc[meta_df["Camada"] == "Declividade"].iloc[0]
amplitude = mdt_row["Maximo"] - mdt_row["Minimo"]

operation_df_global = None
operation_terrain_global = None
if DEFAULT_OPERATION_FILE.exists():
    try:
        operation_df_global = load_operation_data(DEFAULT_OPERATION_FILE)
        operation_terrain_global = build_operation_terrain_df(operation_df_global, rasters)
    except Exception as exc:
        st.warning(f"Falha ao carregar dados de operacao: {exc}")

process_telemetry_global = pd.DataFrame()
process_telemetry_source = None
for candidate in [TELEMETRY_PROCESS_FILE, DEFAULT_OPERATION_FILE]:
    if not candidate.exists():
        continue
    try:
        telemetry_df = load_process_telemetry_data(candidate)
        if telemetry_df is not None and not telemetry_df.empty:
            process_telemetry_global = telemetry_df
            process_telemetry_source = candidate
            break
    except Exception as exc:
        st.warning(f"Falha ao carregar telemetria de processo ({candidate.name}): {exc}")

professional_ops_global = pd.DataFrame()
professional_source = None
for candidate in [TELEMETRY_PROCESS_FILE, DEFAULT_OPERATION_FILE]:
    if not candidate.exists():
        continue
    try:
        prof_df = load_professional_ops_dataset(candidate, DATA_FILES["Declividade"], FIELDS_FILE)
        if prof_df is not None and not prof_df.empty:
            professional_ops_global = prof_df
            professional_source = candidate
            break
    except Exception as exc:
        st.warning(f"Falha ao montar dataset profissional ({candidate.name}): {exc}")

ndvi_for_talhoes = None
if ndvi_layer is not None and ndvi_layer["arr"].shape == rasters["Declividade"]["arr"].shape:
    ndvi_for_talhoes = ndvi_layer["arr"]

talhoes_summary_global = pd.DataFrame()
if farm_gdf is not None and not farm_gdf.empty:
    farm_gdf = farm_gdf.copy()
    farm_gdf["talhao_label"] = farm_gdf["DESC_TALHA"].fillna(farm_gdf["TALHAO"].astype(str)).astype(str)
    talhoes_summary_global = build_talhao_classification(
        rasters["Declividade"]["arr"],
        rasters["MDT (Elevacao)"]["arr"],
        rasters["Indice de escoamento"]["arr"],
        rasters["Declividade"]["transform"],
        rasters["Declividade"]["display_res"],
        farm_gdf,
        ndvi_arr=ndvi_for_talhoes,
    )

priority_df_global = build_specialist_priority_table(talhoes_summary_global, operation_terrain_global)
gee_exports_global = load_gee_decision_exports()
priority_gee_global = enrich_priority_with_gee(priority_df_global, gee_exports_global.get("talhoes_stats"))

tab0, tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs(
    [
        "Painel Especialista",
        "Visao Geral",
        "Declividade",
        "Relevo e Exportacao",
        "Operacao x Terreno",
        "Talhoes",
        "Hidrologia e NDVI",
        "Chuva, Clima e Colheita",
        "Telemetria Colheita",
        "Dashboard Operacional PRO",
    ]
)

with tab0:
    st.markdown(
        """
<div class="hero-panel">
  <h2>Painel Especialista de Decisao</h2>
  <p>Leitura priorizada para dimensionamento de carga no talhao: combinando declividade, escoamento, vigor e esforco operacional.</p>
</div>
        """,
        unsafe_allow_html=True,
    )
    if selected_farm_name:
        st.caption(f"Escopo atual: {selected_farm_name} (ID {selected_farm_id})")

    has_gee_score = (
        not priority_gee_global.empty
        and "Score integrado (0-100)" in priority_gee_global.columns
        and priority_gee_global["Score integrado (0-100)"].notna().any()
    )
    use_gee_score = False
    if has_gee_score:
        use_gee_score = st.toggle(
            "Integrar sinais GEE (stress, NDVI, chuva e temperatura) no ranking",
            value=True,
        )
        sources = gee_exports_global.get("sources", {})
        if "talhoes_stats" in sources:
            st.caption(f"Fonte GEE detectada: `{sources['talhoes_stats']}`")

    priority_view_df = priority_gee_global if (use_gee_score and has_gee_score) else priority_df_global
    score_col = "Score integrado (0-100)" if (use_gee_score and has_gee_score) else "Score de prioridade (0-100)"
    priority_col = "Prioridade integrada" if (use_gee_score and has_gee_score) else "Prioridade"

    if priority_view_df.empty:
        st.info(
            "Ainda nao ha dados suficientes para o ranking especialista. Verifique se os talhoes e os rasters estao "
            "com interseccao valida."
        )
    else:
        critical_count = int((priority_view_df[priority_col] == "Critica").sum())
        high_count = int((priority_view_df[priority_col] == "Alta").sum())
        mean_score = priority_view_df[score_col].mean()
        top_name = str(priority_view_df.iloc[0]["Talhao"])

        s1, s2, s3, s4 = st.columns(4)
        with s1:
            kpi_card("Talhoes criticos", str(critical_count), "acao imediata")
        with s2:
            kpi_card("Talhoes alta prioridade", str(high_count), "plano de mitigacao")
        with s3:
            kpi_card("Score medio da fazenda", f"{mean_score:.1f}", "0 a 100")
        with s4:
            kpi_card("Talhao mais sensivel", top_name, "maior score atual")

        pleft, pright = st.columns([1.6, 1])
        with pleft:
            show_cols = [
                c
                for c in [
                    "Talhao",
                    "Score integrado (0-100)",
                    "Score de prioridade (0-100)",
                    "Prioridade integrada",
                    "Prioridade",
                    "Declividade media (%)",
                    "Declividade P95 (%)",
                    "Runoff medio (0-1)",
                    "Esforco medio op.",
                    "NDVI medio",
                    "Stress GEE medio (0-1)",
                    "NDVI GEE safra medio",
                    "Temp max GEE media (C)",
                    "Chuva GEE acumulada (mm)",
                    "Classe predominante",
                    "Recomendacao",
                ]
                if c in priority_view_df.columns
            ]
            st.dataframe(priority_view_df[show_cols], use_container_width=True, height=420)

        with pright:
            prior_count = (
                priority_view_df[priority_col]
                .value_counts()
                .rename_axis("Prioridade")
                .reset_index(name="Talhoes")
            )
            color_map = {
                "Critica": "#c1121f",
                "Alta": "#f77f00",
                "Moderada": "#fcbf49",
                "Baixa": "#2a9d8f",
                "Sem dados": "#7b8ea3",
            }
            prior_pie = px.pie(
                prior_count,
                names="Prioridade",
                values="Talhoes",
                title="Distribuicao de prioridade",
                color="Prioridade",
                color_discrete_map=color_map,
            )
            prior_pie.update_layout(
                template="plotly_white",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=380,
                margin=dict(l=10, r=10, t=40, b=10),
            )
            st.plotly_chart(prior_pie, use_container_width=True)

            top10 = priority_view_df.head(10)
            bar_priority = px.bar(
                top10,
                x="Talhao",
                y=score_col,
                color=priority_col,
                color_discrete_map=color_map,
                title="Top 10 talhoes por risco operacional-terreno",
            )
            bar_priority.update_layout(
                template="plotly_white",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=330,
                margin=dict(l=10, r=10, t=40, b=10),
                xaxis_title="Talhao",
                yaxis_title="Score",
            )
            st.plotly_chart(bar_priority, use_container_width=True)

with tab1:
    st.markdown(
        """
<div class="hero-panel">
  <h2>MDT e Declividade - Unidade de Avaliacao</h2>
  <p>Painel inicial para leitura rapida de altimetria, comparacao de camadas e preparacao da integracao com telemetria operacional.</p>
</div>
        """,
        unsafe_allow_html=True,
    )

    kc1, kc2, kc3, kc4 = st.columns(4)
    with kc1:
        kpi_card("Pixels validos MDT", f"{int(mdt_row['Pixels validos']):,}".replace(",", "."), "area util do recorte")
    with kc2:
        kpi_card("Amplitude elevacao", f"{amplitude:.1f} m", "maximo - minimo")
    with kc3:
        kpi_card("P95 declividade", f"{declividade_row['P95']:.2f} %", "limiar alto da area")
    with kc4:
        kpi_card(
            "Resolucao media",
            f"{(mdt_row['Resolucao X (m)'] + mdt_row['Resolucao Y (m)']) / 2:.1f} m",
            "aprox. por pixel",
        )

    st.subheader("Resumo das camadas")
    if selected_farm_name:
        st.caption(f"Rasters recortados pelo limite da fazenda: {selected_farm_name} (ID {selected_farm_id})")
    st.dataframe(meta_df, use_container_width=True)

    map_col, control_col = st.columns([2.2, 1], gap="large")
    with control_col:
        st.markdown('<div class="control-panel">', unsafe_allow_html=True)
        st.markdown("#### Controles do mapa")
        selected_layer = st.selectbox("Camada para mapa", list(rasters.keys()))
        percentile_cut = st.slider("Recorte para contraste (%)", 0, 20, 2)
        st.markdown("</div>", unsafe_allow_html=True)

    arr = rasters[selected_layer]["arr"]
    valid = arr[np.isfinite(arr)]
    vmin = np.nanpercentile(valid, percentile_cut)
    vmax = np.nanpercentile(valid, 100 - percentile_cut)

    with map_col:
        fig = build_raster_figure(
            arr,
            rasters[selected_layer]["bounds"],
            title=f"Mapa raster: {selected_layer}",
            colorscale="Viridis",
            zmin=vmin,
            zmax=vmax,
        )
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Distribuicao dos valores")
    fig_hist = go.Figure()
    fig_hist.add_trace(go.Histogram(x=valid, nbinsx=60, marker_color="#0f8f8c", opacity=0.85))
    fig_hist.update_layout(
        height=320,
        margin=dict(l=10, r=10, t=10, b=10),
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig_hist, use_container_width=True)

with tab2:
    st.subheader("Declividade por classe")
    slope_arr = rasters["Declividade"]["arr"]
    slope_table = classify_slope(slope_arr)
    left, right = st.columns([1.2, 1])
    with left:
        st.dataframe(slope_table, use_container_width=True)
    with right:
        if not slope_table.empty:
            pie = px.pie(
                slope_table,
                names="Classe",
                values="Pixels",
                title="Participacao por classe de declividade",
                color_discrete_sequence=["#176ab8", "#4a9dd8", "#f18f01", "#db3a34", "#4e5d6c"],
            )
            pie.update_layout(
                height=360,
                margin=dict(l=10, r=10, t=45, b=10),
                template="plotly_white",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(pie, use_container_width=True)

with tab3:
    st.subheader("Visualizacao de relevo (hillshade)")
    mdt_arr = rasters["MDT (Elevacao)"]["arr"]
    hs = hillshade(
        mdt_arr,
        rasters["MDT (Elevacao)"]["transform"],
        rasters["MDT (Elevacao)"]["bounds"],
    )
    fig_hs = build_raster_figure(
        hs,
        rasters["MDT (Elevacao)"]["bounds"],
        title="Visualizacao de relevo (hillshade)",
        colorscale="gray",
    )
    fig_hs.update_layout(height=500)
    st.plotly_chart(fig_hs, use_container_width=True)

    st.subheader("Exportar estatisticas (CSV)")
    csv_bytes = meta_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Baixar resumo das camadas",
        data=csv_bytes,
        file_name="resumo_rasters_mdt_declividade.csv",
        mime="text/csv",
    )

    st.info(
        "Proximo passo sugerido: anexar telemetria georreferenciada (CSV/Parquet com latitude/longitude e VRPM), "
        "realizar amostragem espacial no MDT/declividade e gerar analises por talhao/rota."
    )

with tab4:
    st.subheader("Correlacao entre operacao de pulverizacao e terreno")
    st.caption(
        "Objetivo: identificar como os atributos operacionais variam com elevacao/declividade para apoiar o "
        "dimensionamento da carga de forca no talhao."
    )

    if operation_df_global is None or operation_terrain_global is None:
        st.warning(f"Arquivo de operacao nao encontrado: {DEFAULT_OPERATION_FILE.name}")
    else:
        op_df = operation_df_global
        terrain_df = operation_terrain_global.copy()

        if terrain_df.empty:
            st.error("Nao foi possivel inferir colunas de latitude/longitude no arquivo de operacao.")
        else:
            selected_state = st.multiselect(
                "Filtrar por estado operacional (cd_estado)",
                sorted(terrain_df["cd_estado"].dropna().astype(str).unique().tolist()),
                default=["E"] if "E" in terrain_df["cd_estado"].astype(str).unique() else None,
            )
            if selected_state:
                terrain_df = terrain_df[terrain_df["cd_estado"].astype(str).isin(selected_state)].copy()

            available_metrics = [
                c
                for c in [
                    "vl_velocidade",
                    "vl_rpm",
                    "vl_consumo_instantaneo",
                    "vl_pressao_bomba (kPa)",
                    "vl_vazao_litros_ha",
                    "vl_vazao_litros_min",
                    "vl_hectares_hora",
                    "indice_esforco_relativo",
                ]
                if c in terrain_df.columns
            ]
            selected_metric = st.selectbox(
                "Atributo operacional para analisar vs terreno",
                available_metrics,
                index=available_metrics.index("indice_esforco_relativo")
                if "indice_esforco_relativo" in available_metrics
                else 0,
            )

            analysis_cols = [selected_metric, "declividade_pct", "elevacao_mdt"]
            analysis_df = terrain_df[analysis_cols].replace([np.inf, -np.inf], np.nan).dropna()

            kc1, kc2, kc3 = st.columns(3)
            with kc1:
                kpi_card("Registros operacionais", f"{len(op_df):,}".replace(",", "."), "linhas brutas no CSV")
            with kc2:
                kpi_card(
                    "Registros georreferenciados",
                    f"{len(analysis_df):,}".replace(",", "."),
                    "com metrica + relevo validos",
                )
            with kc3:
                pearson_decl = analysis_df[selected_metric].corr(analysis_df["declividade_pct"])
                kpi_card(
                    "Correlacao (metrica x declividade)",
                    f"{pearson_decl:.3f}" if pd.notna(pearson_decl) else "n/a",
                    "coef. Pearson",
                )

            if analysis_df.empty:
                st.warning("Nao ha dados suficientes apos os filtros para avaliar relacao com terreno.")
            else:
                scatter_left, scatter_right = st.columns(2)
                with scatter_left:
                    fig_slope = px.scatter(
                        analysis_df,
                        x="declividade_pct",
                        y=selected_metric,
                        opacity=0.65,
                        title=f"{selected_metric} vs Declividade (%)",
                    )
                    fig_slope = add_linear_trendline(
                        fig_slope,
                        analysis_df["declividade_pct"].to_numpy(),
                        analysis_df[selected_metric].to_numpy(),
                    )
                    fig_slope.update_layout(
                        template="plotly_white",
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        height=430,
                        margin=dict(l=10, r=10, t=42, b=10),
                    )
                    st.plotly_chart(fig_slope, use_container_width=True)

                with scatter_right:
                    fig_elev = px.scatter(
                        analysis_df,
                        x="elevacao_mdt",
                        y=selected_metric,
                        opacity=0.65,
                        title=f"{selected_metric} vs Elevacao (m)",
                    )
                    fig_elev = add_linear_trendline(
                        fig_elev,
                        analysis_df["elevacao_mdt"].to_numpy(),
                        analysis_df[selected_metric].to_numpy(),
                    )
                    fig_elev.update_layout(
                        template="plotly_white",
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        height=430,
                        margin=dict(l=10, r=10, t=42, b=10),
                    )
                    st.plotly_chart(fig_elev, use_container_width=True)

                bins = [0, 3, 8, 20, 45, np.inf]
                labels = ["0-3%", "3-8%", "8-20%", "20-45%", ">45%"]
                class_df = analysis_df.copy()
                class_df["classe_declividade"] = pd.cut(
                    class_df["declividade_pct"].clip(lower=0), bins=bins, labels=labels, right=False
                )
                summary = (
                    class_df.groupby("classe_declividade", observed=False)[selected_metric]
                    .agg(["count", "mean", "median", "std"])
                    .reset_index()
                )
                summary.columns = [
                    "Classe de declividade",
                    "Amostras",
                    "Media da metrica",
                    "Mediana da metrica",
                    "Desvio padrao",
                ]
                st.subheader("Comportamento da metrica por classe de declividade")
                st.dataframe(summary, use_container_width=True)

                st.subheader("Leitura executiva")
                low_row = summary.loc[summary["Classe de declividade"] == "0-3%"]
                high_row = summary.loc[summary["Classe de declividade"].isin(["8-20%", "20-45%", ">45%"])]
                high_mean = high_row["Media da metrica"].mean() if not high_row.empty else np.nan
                low_mean = low_row["Media da metrica"].iloc[0] if not low_row.empty else np.nan
                impact_pct = pct_change(low_mean, high_mean)
                corr_text = classify_correlation(pearson_decl)
                if pd.notna(impact_pct):
                    trend_word = "aumenta" if impact_pct >= 0 else "reduz"
                    st.markdown(
                        f"- Em areas de maior declividade (>=8%), a media de `{selected_metric}` "
                        f"**{trend_word} {abs(impact_pct):.1f}%** em relacao a faixa de 0-3%."
                    )
                else:
                    st.markdown(
                        f"- Nao foi possivel calcular diferenca percentual robusta entre a faixa 0-3% e faixas >=8% para `{selected_metric}`."
                    )
                st.markdown(
                    f"- A correlacao entre `{selected_metric}` e declividade e **{corr_text}** "
                    f"(r = {pearson_decl:.3f}) dentro do filtro atual."
                )
                st.markdown(
                    "- Essa leitura indica tendencia estatistica do historico analisado; para calibracao mecanica final, "
                    "considere segmentar por implemento, operador e condicao de solo."
                )

                line = px.line(
                    summary,
                    x="Classe de declividade",
                    y="Media da metrica",
                    markers=True,
                    title="Tendencia da metrica por classe de declividade",
                )
                line.update_layout(
                    template="plotly_white",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    height=320,
                    margin=dict(l=10, r=10, t=40, b=10),
                )
                st.plotly_chart(line, use_container_width=True)

with tab5:
    st.subheader("Classificacao de terreno por talhao")
    if farm_gdf is None or farm_gdf.empty:
        st.info("Mapa de talhoes nao disponivel. Adicione o arquivo fields.mbtiles para habilitar esta aba.")
    else:
        talhoes_summary = talhoes_summary_global

        if talhoes_summary.empty:
            st.warning("Nao houve interseccao valida entre talhoes e rasters para gerar classificacao.")
        else:
            c1, c2 = st.columns([1.6, 1])
            with c1:
                st.dataframe(talhoes_summary, use_container_width=True)
            with c2:
                class_count = (
                    talhoes_summary["Classe predominante"]
                    .value_counts()
                    .rename_axis("Classe")
                    .reset_index(name="Talhoes")
                )
                pie_cls = px.pie(
                    class_count,
                    names="Classe",
                    values="Talhoes",
                    title="Classe predominante por talhao",
                    color_discrete_sequence=["#176ab8", "#4a9dd8", "#f18f01", "#db3a34", "#4e5d6c"],
                )
                pie_cls.update_layout(
                    template="plotly_white",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    height=360,
                    margin=dict(l=10, r=10, t=40, b=10),
                )
                st.plotly_chart(pie_cls, use_container_width=True)

            top_steep = talhoes_summary.nlargest(12, "Declividade media (%)")
            bar = px.bar(
                top_steep,
                x="Talhao",
                y="Declividade media (%)",
                color="Classe predominante",
                title="Talhoes com maior declividade media",
            )
            bar.update_layout(
                template="plotly_white",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=360,
                margin=dict(l=10, r=10, t=40, b=10),
                xaxis_title="Talhao",
                yaxis_title="Declividade media (%)",
            )
            st.plotly_chart(bar, use_container_width=True)

with tab6:
    st.subheader("Escoamento superficial, NDVI e composicao visual")
    st.caption(
        "Nesta aba voce visualiza o potencial de escoamento da agua e a classificacao de declividade sobre uma "
        "imagem de base recortada pela fazenda selecionada."
    )

    h1, h2 = st.columns(2)
    with h1:
        fig_acc = build_raster_figure(
            np.log1p(rasters["Acumulacao de fluxo (D8)"]["arr"]),
            rasters["Acumulacao de fluxo (D8)"]["bounds"],
            title="Acumulacao de fluxo (log1p D8)",
            colorscale="Blues",
        )
        fig_acc.update_layout(height=420)
        st.plotly_chart(fig_acc, use_container_width=True)

    with h2:
        fig_runoff = build_raster_figure(
            rasters["Indice de escoamento"]["arr"],
            rasters["Indice de escoamento"]["bounds"],
            title="Indice de escoamento superficial (0-1)",
            colorscale="YlOrRd",
            zmin=0,
            zmax=1,
        )
        fig_runoff.update_layout(height=420)
        st.plotly_chart(fig_runoff, use_container_width=True)

    st.subheader("Direcao de escoamento (setas D8)")
    flow_step = st.slider(
        "Densidade das setas (quanto menor, mais setas)",
        min_value=8,
        max_value=28,
        value=14,
        step=2,
    )
    flow_dir_fig = build_flow_direction_figure(
        hillshade(
            rasters["MDT (Elevacao)"]["arr"],
            rasters["MDT (Elevacao)"]["transform"],
            rasters["MDT (Elevacao)"]["bounds"],
        ),
        flow_receiver_arr,
        rasters["MDT (Elevacao)"]["bounds"],
        title="Setas de direcao preferencial de escoamento (D8)",
        step=flow_step,
    )
    st.plotly_chart(flow_dir_fig, use_container_width=True)
    st.caption(
        "As setas mostram para qual vizinho cada celula drena no MDT. Use este mapa para entender caminho "
        "preferencial da agua e pontos de concentracao."
    )

    if ndvi_layer is not None:
        ndvi_arr = ndvi_layer["arr"]
        ndvi_valid = ndvi_arr[np.isfinite(ndvi_arr)]
        if ndvi_valid.size > 0:
            if np.nanmin(ndvi_valid) < -1.2 or np.nanmax(ndvi_valid) > 1.2:
                st.warning("`ndvi_recente.tif` parece nao estar na faixa [-1, 1]. Verifique a escala do arquivo.")
            fig_ndvi = build_raster_figure(
                np.clip(ndvi_arr, -1, 1),
                ndvi_layer["bounds"],
                title="NDVI recortado",
                colorscale="RdYlGn",
                zmin=-1,
                zmax=1,
            )
            fig_ndvi.update_layout(height=430)
            st.plotly_chart(fig_ndvi, use_container_width=True)
    else:
        st.info(
            "Para habilitar NDVI, adicione um raster `ndvi_recente.tif` na pasta do projeto. "
            "A analise sera recortada automaticamente pela fazenda selecionada."
        )

    st.subheader("Imagem base + classificacao de declividade")
    decliv_class = classify_declividade_array(rasters["Declividade"]["arr"])
    if rgb_layer is not None and rgb_layer["arr"].shape[:2] == decliv_class.shape:
        base_gray = normalize_rgb_to_gray(rgb_layer["arr"])
        overlay_bounds = rgb_layer["bounds"]
        overlay_note = (
            "Base: `imagem_recente.tif` (recortada). "
            "Sobreposicao: classes de declividade do raster principal."
        )
    elif rgb_layer is not None:
        base_gray = hillshade(
            rasters["MDT (Elevacao)"]["arr"],
            rasters["MDT (Elevacao)"]["transform"],
            rasters["MDT (Elevacao)"]["bounds"],
        )
        overlay_bounds = rasters["Declividade"]["bounds"]
        overlay_note = (
            "A imagem recente foi encontrada, mas possui grade diferente do raster de declividade. "
            "Foi usado hillshade como base para preservar o alinhamento."
        )
    else:
        base_gray = hillshade(
            rasters["MDT (Elevacao)"]["arr"],
            rasters["MDT (Elevacao)"]["transform"],
            rasters["MDT (Elevacao)"]["bounds"],
        )
        overlay_bounds = rasters["Declividade"]["bounds"]
        overlay_note = (
            "Base de fallback: hillshade do MDT (nao e imagem recente). "
            "Para usar imagem recente, adicione `imagem_recente.tif` na pasta do projeto."
        )

    overlay_fig = build_decliv_overlay_figure(
        base_gray,
        decliv_class,
        overlay_bounds,
        title="Declividade sobre imagem de apoio recortada",
    )
    st.plotly_chart(overlay_fig, use_container_width=True)
    st.caption(overlay_note)

with tab7:
    st.subheader("Integracao de chuva, clima e colheita")
    st.caption(
        "Envie seus arquivos para cruzar condicoes climaticas e desempenho de colheita com o contexto de terreno."
    )

    st.markdown("#### Ingestao automatica GEE (`DECISION_*`)")
    gee_sources = gee_exports_global.get("sources", {})
    gee_status_rows = []
    for key, _ in GEE_DECISION_PREFIXES.items():
        label_map = {
            "talhoes_stats": "Talhoes stats",
            "talhoes_indices_ts": "Serie indices por talhao",
            "fazenda_rain_daily": "Chuva diaria fazenda",
            "fazenda_climate_daily": "Clima diario fazenda",
        }
        df = gee_exports_global.get(key)
        gee_status_rows.append(
            {
                "Produto": label_map.get(key, key),
                "Status": "Carregado" if isinstance(df, pd.DataFrame) and not df.empty else "Nao encontrado",
                "Arquivo": gee_sources.get(key, "-"),
                "Linhas": int(len(df)) if isinstance(df, pd.DataFrame) else 0,
            }
        )
    gee_status_df = pd.DataFrame(gee_status_rows)
    st.dataframe(gee_status_df, use_container_width=True, hide_index=True)

    gee_idx_df = gee_exports_global.get("talhoes_indices_ts")
    if isinstance(gee_idx_df, pd.DataFrame) and not gee_idx_df.empty:
        idx_date_col = infer_column(gee_idx_df, [r"^date$|data|dt"])
        idx_talhao_col = infer_column(gee_idx_df, [r"^TALHAO$|cd_talhao|talhao"])
        idx_ndvi_col = infer_column(gee_idx_df, [r"^NDVI$|ndvi"])
        if idx_date_col and idx_talhao_col and idx_ndvi_col:
            gee_idx_view = gee_idx_df.copy()
            gee_idx_view[idx_date_col] = pd.to_datetime(gee_idx_view[idx_date_col], errors="coerce")
            gee_idx_view[idx_ndvi_col] = pd.to_numeric(gee_idx_view[idx_ndvi_col], errors="coerce")
            gee_idx_view = gee_idx_view.dropna(subset=[idx_date_col, idx_talhao_col, idx_ndvi_col])
            if not gee_idx_view.empty:
                st.markdown("#### Serie NDVI por talhao (GEE)")
                talhao_options = sorted(gee_idx_view[idx_talhao_col].astype(str).unique().tolist())
                selected_talhao_gee = st.selectbox(
                    "Talhao para serie temporal NDVI (GEE)",
                    talhao_options,
                    key="gee_talhao_ndvi",
                )
                ts_plot_df = gee_idx_view[gee_idx_view[idx_talhao_col].astype(str) == selected_talhao_gee].copy()
                ts_plot_df = ts_plot_df.sort_values(idx_date_col)
                fig_ts_ndvi = px.line(
                    ts_plot_df,
                    x=idx_date_col,
                    y=idx_ndvi_col,
                    markers=True,
                    title=f"NDVI temporal - Talhao {selected_talhao_gee}",
                )
                fig_ts_ndvi.update_layout(
                    template="plotly_white",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    height=320,
                    margin=dict(l=10, r=10, t=40, b=10),
                    xaxis_title="Data",
                    yaxis_title="NDVI",
                )
                st.plotly_chart(fig_ts_ndvi, use_container_width=True)

    gee_rain_df = gee_exports_global.get("fazenda_rain_daily")
    if isinstance(gee_rain_df, pd.DataFrame) and not gee_rain_df.empty:
        rain_date_col = infer_column(gee_rain_df, [r"^date$|data|dt"])
        rain_mm_col = infer_column(gee_rain_df, [r"rain_mm|rain|chuva|precip"])
        if rain_date_col and rain_mm_col:
            plot_rain = gee_rain_df.copy()
            plot_rain[rain_date_col] = pd.to_datetime(plot_rain[rain_date_col], errors="coerce")
            plot_rain[rain_mm_col] = pd.to_numeric(plot_rain[rain_mm_col], errors="coerce")
            plot_rain = plot_rain.dropna(subset=[rain_date_col, rain_mm_col]).sort_values(rain_date_col)
            if not plot_rain.empty:
                fig_rain_gee = px.bar(
                    plot_rain,
                    x=rain_date_col,
                    y=rain_mm_col,
                    title="Chuva diaria da fazenda (GEE)",
                )
                fig_rain_gee.update_layout(
                    template="plotly_white",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    height=300,
                    margin=dict(l=10, r=10, t=40, b=10),
                    xaxis_title="Data",
                    yaxis_title="Chuva (mm)",
                )
                st.plotly_chart(fig_rain_gee, use_container_width=True)

    gee_climate_df = gee_exports_global.get("fazenda_climate_daily")
    if isinstance(gee_climate_df, pd.DataFrame) and not gee_climate_df.empty:
        climate_date_col = infer_column(gee_climate_df, [r"^date$|data|dt"])
        climate_temp_col = infer_column(gee_climate_df, [r"temp_max_c|temp_mean_c|temp|temperatura"])
        if climate_date_col and climate_temp_col:
            plot_climate = gee_climate_df.copy()
            plot_climate[climate_date_col] = pd.to_datetime(plot_climate[climate_date_col], errors="coerce")
            plot_climate[climate_temp_col] = pd.to_numeric(plot_climate[climate_temp_col], errors="coerce")
            plot_climate = plot_climate.dropna(subset=[climate_date_col, climate_temp_col]).sort_values(climate_date_col)
            if not plot_climate.empty:
                fig_temp_gee = px.line(
                    plot_climate,
                    x=climate_date_col,
                    y=climate_temp_col,
                    markers=True,
                    title="Temperatura diaria da fazenda (GEE)",
                )
                fig_temp_gee.update_layout(
                    template="plotly_white",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    height=300,
                    margin=dict(l=10, r=10, t=40, b=10),
                    xaxis_title="Data",
                    yaxis_title="Temperatura (C)",
                )
                st.plotly_chart(fig_temp_gee, use_container_width=True)

    up1, up2 = st.columns(2)
    with up1:
        rain_file = st.file_uploader(
            "Arquivo de chuva/clima (CSV ou Parquet)",
            type=["csv", "parquet"],
            key="rain_climate_upload",
        )
    with up2:
        harvest_file = st.file_uploader(
            "Arquivo de colheita de soja (CSV ou Parquet)",
            type=["csv", "parquet"],
            key="harvest_upload",
        )

    rain_df = read_uploaded_table(rain_file)
    rain_info, rain_status = summarize_rain_climate(rain_df)
    if rain_status == "ok":
        rdf = rain_info["df"]
        rain_col = rain_info["rain_col"]
        temp_col = rain_info["temp_col"]
        hum_col = rain_info["hum_col"]
        wind_col = rain_info["wind_col"]
        date_col = rain_info["date_col"]

        kc1, kc2, kc3, kc4 = st.columns(4)
        with kc1:
            if rain_col:
                kpi_card("Chuva acumulada", f"{rdf[rain_col].sum(skipna=True):.1f} mm", "periodo carregado")
            else:
                kpi_card("Chuva acumulada", "n/d", "coluna de chuva nao detectada")
        with kc2:
            if rain_col:
                kpi_card("P95 chuva", f"{rdf[rain_col].quantile(0.95):.1f} mm", "eventos intensos")
            else:
                kpi_card("P95 chuva", "n/d", "")
        with kc3:
            if temp_col:
                kpi_card("Temp media", f"{rdf[temp_col].mean(skipna=True):.1f} C", "periodo carregado")
            else:
                kpi_card("Temp media", "n/d", "")
        with kc4:
            if hum_col:
                kpi_card("Umidade media", f"{rdf[hum_col].mean(skipna=True):.1f} %", "periodo carregado")
            else:
                kpi_card("Umidade media", "n/d", "")

        if date_col and rain_col:
            by_day = (
                rdf.dropna(subset=[date_col])
                .assign(data=rdf[date_col].dt.date)
                .groupby("data", as_index=False)[rain_col]
                .sum()
            )
            rain_line = px.line(by_day, x="data", y=rain_col, markers=True, title="Chuva diaria")
            rain_line.update_layout(
                template="plotly_white",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=320,
                margin=dict(l=10, r=10, t=40, b=10),
                xaxis_title="Data",
                yaxis_title="Chuva (mm)",
            )
            st.plotly_chart(rain_line, use_container_width=True)
        st.dataframe(rdf.head(200), use_container_width=True)
    else:
        st.info("Suba um arquivo de chuva/clima para habilitar esta analise.")

    harvest_df = read_uploaded_table(harvest_file)
    if harvest_df is not None and not harvest_df.empty:
        st.subheader("Resumo de colheita de soja")
        yield_col = infer_column(harvest_df, [r"produt|yield|sc_ha|saca|ton_ha"])
        talhao_col = infer_column(harvest_df, [r"talhao|desc_talha|field"])
        date_col_h = infer_column(harvest_df, [r"data|date|dt"])
        if yield_col:
            harvest_df[yield_col] = pd.to_numeric(harvest_df[yield_col], errors="coerce")
            if talhao_col:
                summary_h = (
                    harvest_df.groupby(talhao_col, as_index=False)[yield_col]
                    .agg(["count", "mean", "std"])
                    .reset_index()
                )
                summary_h.columns = ["Talhao", "Amostras", "Produtividade media", "Desvio padrao"]
                st.dataframe(summary_h.sort_values("Produtividade media", ascending=False), use_container_width=True)
                if not priority_df_global.empty:
                    merge_df = priority_df_global.copy()
                    merge_df["Talhao"] = merge_df["Talhao"].astype(str)
                    summary_h["Talhao"] = summary_h["Talhao"].astype(str)
                    joined = merge_df.merge(summary_h[["Talhao", "Produtividade media"]], on="Talhao", how="inner")
                    if not joined.empty:
                        corr = joined["Score de prioridade (0-100)"].corr(joined["Produtividade media"])
                        st.markdown(
                            f"- Correlacao entre score de prioridade e produtividade media: **{corr:.3f}** "
                            "(negativo indica queda de produtividade em talhoes de maior risco)."
                        )
                        scat = px.scatter(
                            joined,
                            x="Score de prioridade (0-100)",
                            y="Produtividade media",
                            hover_name="Talhao",
                            color="Prioridade",
                            title="Risco operacional-terreno vs produtividade",
                        )
                        scat = add_linear_trendline(
                            scat,
                            joined["Score de prioridade (0-100)"].to_numpy(),
                            joined["Produtividade media"].to_numpy(),
                        )
                        scat.update_layout(
                            template="plotly_white",
                            paper_bgcolor="rgba(0,0,0,0)",
                            plot_bgcolor="rgba(0,0,0,0)",
                            height=380,
                            margin=dict(l=10, r=10, t=40, b=10),
                        )
                        st.plotly_chart(scat, use_container_width=True)
            else:
                st.markdown(f"- Produtividade media no arquivo: **{harvest_df[yield_col].mean(skipna=True):.2f}**")
        else:
            st.warning(
                "Nao consegui detectar automaticamente a coluna de produtividade. "
                "Use um nome contendo: produtividade, yield, sc_ha, saca ou ton_ha."
            )
        if date_col_h:
            harvest_df[date_col_h] = pd.to_datetime(harvest_df[date_col_h], errors="coerce")
    else:
        st.info("Suba um arquivo de colheita para cruzar com o ranking de risco.")

with tab8:
    st.subheader("Analise de processo da telemetria de colheita")
    st.caption(
        "Mapa de estados adotado: E=Efetivo, P=Parada, M=Manobra, D=Deslocamento. "
        "Leitura focada em sincronismo de turno e consistencia dos apontamentos."
    )

    if process_telemetry_source is not None:
        st.caption(f"Fonte atual: `{process_telemetry_source}`")

    if process_telemetry_global.empty:
        st.warning(
            "Nao foi encontrada base de telemetria consolidada para analise de processo. "
            "Coloque `telemetria_colheita_extraida/consolidado_telemetria_colheita.csv` na pasta do projeto."
        )
    else:
        proc_df = process_telemetry_global.copy()
        proc_df = proc_df.sort_values("dt_hr_local_inicial")

        f1, f2, f3 = st.columns([1.2, 1, 1])
        with f1:
            dmin = proc_df["dt_hr_local_inicial"].min().date()
            dmax = proc_df["dt_hr_local_inicial"].max().date()
            selected_period = st.date_input("Periodo", value=(dmin, dmax), min_value=dmin, max_value=dmax)
        with f2:
            state_options = sorted(proc_df["estado_processo"].dropna().astype(str).unique().tolist())
            default_states = [s for s in ["Efetivo", "Parada", "Manobra", "Deslocamento"] if s in state_options]
            selected_states = st.multiselect(
                "Estados",
                state_options,
                default=default_states if default_states else state_options,
            )
        with f3:
            equip_options = sorted(proc_df["cd_equipamento"].dropna().astype(str).unique().tolist())
            equip_default = (
                proc_df.groupby("cd_equipamento", as_index=False)["vl_tempo_segundos"]
                .sum()
                .sort_values("vl_tempo_segundos", ascending=False)["cd_equipamento"]
                .astype(str)
                .head(6)
                .tolist()
            )
            selected_equip = st.multiselect("Equipamentos", equip_options, default=equip_default)

        if isinstance(selected_period, tuple) and len(selected_period) == 2:
            start_date, end_date = selected_period
        else:
            start_date, end_date = dmin, dmax
        start_ts = pd.Timestamp(start_date)
        end_ts = pd.Timestamp(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)

        proc_df = proc_df[
            (proc_df["dt_hr_local_inicial"] >= start_ts)
            & (proc_df["dt_hr_local_inicial"] <= end_ts)
        ].copy()
        if selected_states:
            proc_df = proc_df[proc_df["estado_processo"].astype(str).isin(selected_states)].copy()
        if selected_equip:
            proc_df = proc_df[proc_df["cd_equipamento"].astype(str).isin(selected_equip)].copy()

        if proc_df.empty:
            st.info("Sem dados para os filtros selecionados.")
        else:
            total_h = proc_df["vl_tempo_segundos"].sum() / 3600.0
            parada_h = proc_df.loc[proc_df["is_parada"], "vl_tempo_segundos"].sum() / 3600.0
            efetivo_h = proc_df.loc[proc_df["estado_processo"] == "Efetivo", "vl_tempo_segundos"].sum() / 3600.0
            manobra_h = proc_df.loc[proc_df["estado_processo"] == "Manobra", "vl_tempo_segundos"].sum() / 3600.0
            desloc_h = proc_df.loc[proc_df["estado_processo"] == "Deslocamento", "vl_tempo_segundos"].sum() / 3600.0

            k1, k2, k3, k4, k5 = st.columns(5)
            with k1:
                kpi_card("Tempo total", f"{total_h:.1f} h", "base filtrada")
            with k2:
                kpi_card("Efetivo", f"{efetivo_h:.1f} h", "estado E")
            with k3:
                kpi_card("Parada", f"{parada_h:.1f} h", "estado P/F")
            with k4:
                kpi_card("Manobra", f"{manobra_h:.1f} h", "estado M")
            with k5:
                kpi_card("Deslocamento", f"{desloc_h:.1f} h", "estado D")

            st.markdown("#### Horas por maquina em todos os dias (small multiples)")
            daily_state = proc_df[proc_df["estado_processo"].isin(["Efetivo", "Parada"])].copy()
            if daily_state.empty:
                st.info("Sem eventos Efetivo/Parada no periodo selecionado.")
            else:
                daily_compact = compress_process_intervals(daily_state, gap_seconds=45)
                if daily_compact.empty:
                    st.info("Nao foi possivel montar os intervalos diarios para visualizacao.")
                else:
                    equip_sorted = sorted(daily_compact["cd_equipamento"].astype(str).unique().tolist())
                    day_sorted = sorted(daily_compact["data_str"].unique().tolist())

                    ctrl_a, ctrl_b, ctrl_c = st.columns([1.1, 1.2, 1.2])
                    with ctrl_a:
                        show_days_mode = st.selectbox(
                            "Dias exibidos",
                            ["Todos", "Ultimos 14", "Ultimos 21", "Ultimos 28"],
                            index=1,
                            key="proc_small_days_mode",
                        )
                    with ctrl_b:
                        facet_wrap = st.slider("Colunas de mini-graficos", 3, 8, 5, key="proc_small_wrap")
                    with ctrl_c:
                        merge_gap = st.slider("Unir blocos consecutivos (segundos)", 0, 180, 45, step=15, key="proc_merge_gap")

                    if merge_gap != 45:
                        daily_compact = compress_process_intervals(daily_state, gap_seconds=int(merge_gap))
                        day_sorted = sorted(daily_compact["data_str"].unique().tolist())

                    if show_days_mode != "Todos":
                        keep_n = int(show_days_mode.split()[-1])
                        keep_days = sorted(day_sorted)[-keep_n:]
                        daily_compact = daily_compact[daily_compact["data_str"].isin(keep_days)].copy()
                        day_sorted = sorted(daily_compact["data_str"].unique().tolist())

                    facet_rows = int(np.ceil(len(day_sorted) / facet_wrap)) if day_sorted else 1
                    tick_vals_day = [0, 360, 720, 1080, 1439]
                    tick_txt_day = ["00:00", "06:00", "12:00", "18:00", "23:59"]

                    fig_days = px.bar(
                        daily_compact,
                    x="dur_min",
                    y="cd_equipamento",
                    color="estado_processo",
                    orientation="h",
                    base="start_min",
                    facet_col="data_str",
                    facet_col_wrap=facet_wrap,
                    category_orders={
                        "estado_processo": ["Efetivo", "Parada"],
                        "cd_equipamento": equip_sorted,
                        "data_str": day_sorted,
                    },
                    color_discrete_map={"Efetivo": "#2a9d8f", "Parada": "#c1121f"},
                    title="Linha do tempo diaria por maquina: Efetivo (verde) e Parada (vermelho)",
                    hover_data={
                        "inicio_hhmm": True,
                        "fim_hhmm": True,
                        "dur_min": ":.1f",
                        "start_min": False,
                        "data_str": False,
                    },
                    )
                    fig_days.for_each_annotation(
                        lambda a: a.update(text=a.text.replace("data_str=", "Dia "), font=dict(size=11, color="#14354f"))
                    )
                    fig_days.update_traces(marker_line_width=0, opacity=0.92)
                    fig_days.update_xaxes(
                        tickmode="array",
                        tickvals=tick_vals_day,
                        ticktext=tick_txt_day,
                        range=[0, 24 * 60],
                        showgrid=True,
                        gridcolor="rgba(20,53,79,0.12)",
                        zeroline=False,
                    )
                    fig_days.update_yaxes(
                        title="Equipamento",
                        showgrid=True,
                        gridcolor="rgba(20,53,79,0.08)",
                        categoryorder="array",
                        categoryarray=equip_sorted,
                    )
                    fig_days.update_layout(
                        height=max(620, 360 * facet_rows),
                        barmode="overlay",
                        template="plotly_white",
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(247,250,252,0.7)",
                        margin=dict(l=10, r=10, t=60, b=10),
                        xaxis_title="Horario (00:00 a 23:59)",
                        yaxis_title="Equipamento",
                        legend_title="Estado",
                        legend=dict(
                            orientation="h",
                            yanchor="bottom",
                            y=1.02,
                            xanchor="left",
                            x=0,
                            bgcolor="rgba(255,255,255,0.7)",
                        ),
                        bargap=0.16,
                    )
                    st.plotly_chart(fig_days, use_container_width=True)

                st.markdown("#### Horario de inicio do efetivo por maquina (small multiples)")
                start_eff = (
                    proc_df[proc_df["estado_processo"] == "Efetivo"]
                    .groupby(["data", "cd_equipamento"], as_index=False)["dt_hr_local_inicial"]
                    .min()
                    .rename(columns={"dt_hr_local_inicial": "inicio_efetivo"})
                )
                if start_eff.empty:
                    st.info("Sem registros em estado Efetivo para calcular horario de inicio.")
                else:
                    start_eff["data_str"] = pd.to_datetime(start_eff["data"]).dt.strftime("%Y-%m-%d")
                    start_eff["inicio_min"] = (
                        start_eff["inicio_efetivo"].dt.hour * 60
                        + start_eff["inicio_efetivo"].dt.minute
                        + start_eff["inicio_efetivo"].dt.second / 60.0
                    )
                    start_eff["inicio_hhmm"] = start_eff["inicio_efetivo"].dt.strftime("%H:%M")

                    start_fig = px.scatter(
                        start_eff,
                        x="inicio_min",
                        y="cd_equipamento",
                        facet_col="data_str",
                        facet_col_wrap=facet_wrap,
                        category_orders={"cd_equipamento": equip_sorted, "data_str": day_sorted},
                        color_discrete_sequence=["#2a9d8f"],
                        hover_data=["inicio_hhmm"],
                        title="Comparacao do primeiro horario efetivo por maquina em cada dia",
                    )
                    tick_vals = list(range(0, 24 * 60 + 1, 120))
                    tick_txt = [f"{m // 60:02d}:{m % 60:02d}" for m in tick_vals]
                    start_fig.for_each_annotation(lambda a: a.update(text=a.text.replace("data_str=", "Dia ")))
                    start_fig.update_xaxes(
                        tickmode="array",
                        tickvals=tick_vals,
                        ticktext=tick_txt,
                        range=[0, 24 * 60],
                    )
                    start_fig.update_layout(
                        height=max(440, 320 * facet_rows),
                        template="plotly_white",
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        margin=dict(l=10, r=10, t=55, b=10),
                        xaxis_title="Horario de inicio do efetivo",
                        yaxis_title="Equipamento",
                        showlegend=False,
                    )
                    st.plotly_chart(start_fig, use_container_width=True)

            st.markdown("#### Linha do tempo operacional por equipamento")
            timeline_df = proc_df[
                ["cd_equipamento", "dt_hr_local_inicial", "dt_hr_fim", "estado_processo", "desc_parada", "vl_tempo_segundos"]
            ].copy()
            timeline_df = timeline_df.sort_values("vl_tempo_segundos", ascending=False).head(5000)
            color_map = {
                "Efetivo": "#2a9d8f",
                "Parada": "#c1121f",
                "Manobra": "#f4a261",
                "Deslocamento": "#1d4e89",
                "Outros": "#7b8ea3",
            }
            tl = px.timeline(
                timeline_df,
                x_start="dt_hr_local_inicial",
                x_end="dt_hr_fim",
                y="cd_equipamento",
                color="estado_processo",
                color_discrete_map=color_map,
                hover_data=["desc_parada", "vl_tempo_segundos"],
                title="Eventos operacionais (Top 5000 por duracao na janela filtrada)",
            )
            tl.update_yaxes(title="Equipamento", autorange="reversed")
            tl.update_layout(
                height=520,
                template="plotly_white",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=10, r=10, t=45, b=10),
                xaxis_title="Data/hora",
            )
            st.plotly_chart(tl, use_container_width=True)

            st.markdown("#### Sincronismo de fim de turno")
            fim_df = proc_df[
                proc_df["desc_parada"].astype(str).str.upper().str.contains("FIM DE EXPEDIENTE", na=False)
            ].copy()
            if fim_df.empty:
                st.info("Nao ha eventos com `FIM DE EXPEDIENTE` na selecao atual.")
            else:
                fim_turno = (
                    fim_df.groupby(["data", "cd_equipamento"], as_index=False)["dt_hr_fim"]
                    .max()
                    .rename(columns={"dt_hr_fim": "fim_turno"})
                )
                fim_turno["fim_minutos"] = (
                    fim_turno["fim_turno"].dt.hour * 60
                    + fim_turno["fim_turno"].dt.minute
                    + fim_turno["fim_turno"].dt.second / 60.0
                )
                spread = (
                    fim_turno.groupby("data", as_index=False)
                    .agg(
                        equipamentos=("cd_equipamento", "nunique"),
                        fim_min=("fim_minutos", "min"),
                        fim_max=("fim_minutos", "max"),
                        fim_mediana=("fim_minutos", "median"),
                    )
                )
                spread["dispersao_min"] = spread["fim_max"] - spread["fim_min"]
                spread_multi = spread[spread["equipamentos"] >= 2].copy()

                s1, s2, s3 = st.columns(3)
                with s1:
                    med_disp = spread_multi["dispersao_min"].median() if not spread_multi.empty else np.nan
                    kpi_card("Dispersao mediana", f"{med_disp:.1f} min" if pd.notna(med_disp) else "n/d", "fim de turno")
                with s2:
                    p90_disp = spread_multi["dispersao_min"].quantile(0.9) if not spread_multi.empty else np.nan
                    kpi_card("Dispersao P90", f"{p90_disp:.1f} min" if pd.notna(p90_disp) else "n/d", "dias criticos")
                with s3:
                    mean_end = spread["fim_mediana"].mean() if not spread.empty else np.nan
                    kpi_card("Horario medio", minutes_to_hhmm(mean_end), "mediana diaria")

                sync_fig = px.line(
                    spread.sort_values("data"),
                    x="data",
                    y="dispersao_min",
                    markers=True,
                    title="Dispersao diaria do horario de fim de turno",
                )
                sync_fig.update_layout(
                    height=320,
                    template="plotly_white",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    margin=dict(l=10, r=10, t=40, b=10),
                    xaxis_title="Data",
                    yaxis_title="Dispersao (min)",
                )
                st.plotly_chart(sync_fig, use_container_width=True)

                show_cols = ["data", "equipamentos", "dispersao_min", "fim_min", "fim_max", "fim_mediana"]
                spread_show = spread[show_cols].copy()
                for c in ["fim_min", "fim_max", "fim_mediana"]:
                    spread_show[c] = spread_show[c].apply(minutes_to_hhmm)
                st.dataframe(spread_show.sort_values("data", ascending=False), use_container_width=True, height=220)

            st.markdown("#### Paradas iguais em horarios iguais terminam juntas?")
            pleft, pright = st.columns([1.4, 1])
            with pleft:
                parada_options = sorted(
                    proc_df.loc[proc_df["is_parada"], "desc_parada"].dropna().astype(str).unique().tolist()
                )
                selected_parada = st.selectbox("Tipo de parada", parada_options, index=0 if parada_options else None)
            with pright:
                bucket_min = st.slider("Janela de agrupamento de inicio (min)", 5, 60, 10, step=5)

            if not parada_options:
                st.info("Nao ha eventos de parada para os filtros atuais.")
            else:
                same_stop = proc_df[
                    (proc_df["is_parada"]) & (proc_df["desc_parada"].astype(str) == str(selected_parada))
                ].copy()
                same_stop["janela_inicio"] = same_stop["dt_hr_local_inicial"].dt.floor(f"{bucket_min}min")
                grouped = (
                    same_stop.groupby(["data", "janela_inicio"], as_index=False)
                    .agg(
                        equipamentos=("cd_equipamento", "nunique"),
                        eventos=("cd_equipamento", "size"),
                        inicio=("dt_hr_local_inicial", "min"),
                        fim_min=("dt_hr_fim", "min"),
                        fim_max=("dt_hr_fim", "max"),
                        tempo_total_s=("vl_tempo_segundos", "sum"),
                    )
                )
                grouped = grouped[grouped["equipamentos"] >= 2].copy()
                if grouped.empty:
                    st.info("Nao houve grupos com 2+ equipamentos para essa parada e janela.")
                else:
                    grouped["dispersao_fim_min"] = (grouped["fim_max"] - grouped["fim_min"]).dt.total_seconds() / 60.0
                    grouped["tempo_total_h"] = grouped["tempo_total_s"] / 3600.0

                    g1, g2 = st.columns(2)
                    with g1:
                        kpi_card(
                            "Grupos simultaneos",
                            f"{len(grouped):,}".replace(",", "."),
                            "2+ equipamentos no mesmo inicio",
                        )
                    with g2:
                        med = grouped["dispersao_fim_min"].median()
                        kpi_card("Dispersao mediana de termino", f"{med:.1f} min", selected_parada)

                    hist = px.histogram(
                        grouped,
                        x="dispersao_fim_min",
                        nbins=30,
                        title="Distribuicao da dispersao de termino por grupo simultaneo",
                    )
                    hist.update_layout(
                        height=300,
                        template="plotly_white",
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        margin=dict(l=10, r=10, t=40, b=10),
                        xaxis_title="Dispersao de termino (min)",
                        yaxis_title="Quantidade de grupos",
                    )
                    st.plotly_chart(hist, use_container_width=True)

                    grouped_show = grouped[
                        ["data", "janela_inicio", "equipamentos", "eventos", "dispersao_fim_min", "tempo_total_h"]
                    ].sort_values(["data", "janela_inicio"], ascending=[False, False])
                    st.dataframe(grouped_show.head(200), use_container_width=True, height=240)

            st.markdown("#### Heatmap de tempo de parada (hora x dia)")
            heat_df = proc_df[proc_df["is_parada"]].copy()
            if heat_df.empty:
                st.info("Sem paradas para montar o heatmap na janela atual.")
            else:
                heat = (
                    heat_df.groupby(["hora", "data"], as_index=False)["vl_tempo_segundos"]
                    .sum()
                    .assign(tempo_h=lambda d: d["vl_tempo_segundos"] / 3600.0)
                )
                heat_pivot = heat.pivot(index="hora", columns="data", values="tempo_h").fillna(0.0)
                hm = go.Figure(
                    data=go.Heatmap(
                        z=heat_pivot.to_numpy(),
                        x=[str(c) for c in heat_pivot.columns.tolist()],
                        y=heat_pivot.index.tolist(),
                        colorscale="YlOrRd",
                        colorbar=dict(title="Horas"),
                    )
                )
                hm.update_layout(
                    height=360,
                    template="plotly_white",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    margin=dict(l=10, r=10, t=35, b=10),
                    xaxis_title="Data",
                    yaxis_title="Hora do dia",
                    title="Carga horaria de parada por hora",
                )
                st.plotly_chart(hm, use_container_width=True)

            st.markdown("#### Pareto de perdas por parada")
            pareto = (
                proc_df[proc_df["is_parada"]]
                .groupby("desc_parada", as_index=False)
                .agg(
                    tempo_s=("vl_tempo_segundos", "sum"),
                    ocorrencias=("desc_parada", "size"),
                    equipamentos=("cd_equipamento", "nunique"),
                )
            )
            if pareto.empty:
                st.info("Sem eventos de parada no recorte atual.")
            else:
                pareto["tempo_h"] = pareto["tempo_s"] / 3600.0
                pareto = pareto.sort_values("tempo_h", ascending=False).head(15)
                pfig = px.bar(
                    pareto,
                    x="tempo_h",
                    y="desc_parada",
                    orientation="h",
                    color="ocorrencias",
                    title="Top 15 paradas por tempo acumulado",
                    color_continuous_scale="Tealgrn",
                )
                pfig.update_layout(
                    height=430,
                    template="plotly_white",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    margin=dict(l=10, r=10, t=40, b=10),
                    xaxis_title="Tempo acumulado (h)",
                    yaxis_title="Parada",
                )
                st.plotly_chart(pfig, use_container_width=True)
                st.dataframe(
                    pareto[["desc_parada", "tempo_h", "ocorrencias", "equipamentos"]],
                    use_container_width=True,
                    height=240,
                )

with tab9:
    st.markdown(
        """
<div class="hero-panel">
  <h2>Dashboard Operacional Profissional</h2>
  <p>Visao integrada de consumo, declividade, direcao operacional, sem apontamento e picos de parada para decisao de viabilidade e retorno.</p>
</div>
        """,
        unsafe_allow_html=True,
    )

    if professional_source is not None:
        st.caption(f"Fonte da analise: `{professional_source}`")

    if professional_ops_global.empty:
        st.warning(
            "Nao foi possivel montar o dataset operacional profissional. "
            "Verifique se o consolidado de telemetria esta disponivel."
        )
    else:
        prof = professional_ops_global.copy()

        st.markdown("#### Filtros executivos")
        c1, c2, c3, c4 = st.columns([1.15, 1.2, 1.1, 1.1])
        with c1:
            dmin = pd.to_datetime(prof["dt_hr_local_inicial"]).min().date()
            dmax = pd.to_datetime(prof["dt_hr_local_inicial"]).max().date()
            period = st.date_input("Periodo", value=(dmin, dmax), min_value=dmin, max_value=dmax, key="pro_period")
        with c2:
            equips = sorted(prof["cd_equipamento"].dropna().astype(str).unique().tolist())
            eq_default = equips[: min(8, len(equips))]
            selected_eq = st.multiselect("Maquinas", equips, default=eq_default, key="pro_eq")
        with c3:
            states = sorted(prof["estado_processo"].dropna().astype(str).unique().tolist())
            states_default = [s for s in ["Efetivo", "Parada", "Manobra", "Deslocamento"] if s in states]
            selected_states = st.multiselect("Estados", states, default=states_default, key="pro_states")
        with c4:
            fuel_price = st.number_input("Diesel (R$/L)", min_value=0.0, value=6.5, step=0.1, key="pro_fuel_price")

        if isinstance(period, tuple) and len(period) == 2:
            dt_start, dt_end = period
        else:
            dt_start, dt_end = dmin, dmax
        start_ts = pd.Timestamp(dt_start)
        end_ts = pd.Timestamp(dt_end) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)

        prof = prof[
            (prof["dt_hr_local_inicial"] >= start_ts)
            & (prof["dt_hr_local_inicial"] <= end_ts)
        ].copy()
        if selected_eq:
            prof = prof[prof["cd_equipamento"].astype(str).isin(selected_eq)].copy()
        if selected_states:
            prof = prof[prof["estado_processo"].astype(str).isin(selected_states)].copy()

        if prof.empty:
            st.info("Sem dados no recorte selecionado.")
        else:
            # KPIs
            total_h = prof["horas_evento"].sum()
            total_l = prof["consumo_l_estimado"].sum()
            l_h = total_l / total_h if total_h > 0 else np.nan
            total_ha = prof["hectares_evento"].sum() if "hectares_evento" in prof.columns else 0.0
            l_ha = total_l / total_ha if total_ha > 0 else np.nan
            sem_ap_h = prof.loc[prof["sem_apontamento"], "horas_evento"].sum()

            k1, k2, k3, k4, k5 = st.columns(5)
            with k1:
                kpi_card("Horas analisadas", f"{total_h:,.1f}".replace(",", "."), "base georreferenciada")
            with k2:
                kpi_card("Consumo estimado", f"{total_l:,.0f} L".replace(",", "."), "soma dos eventos")
            with k3:
                kpi_card("Intensidade media", f"{l_h:.2f} L/h" if pd.notna(l_h) else "n/d", "consumo por hora")
            with k4:
                kpi_card("Consumo por ha", f"{l_ha:.2f} L/ha" if pd.notna(l_ha) else "n/d", "quando hectares disponivel")
            with k5:
                kpi_card("Sem apontamento", f"{sem_ap_h:.1f} h", "regra operacional aplicada")

            st.markdown("#### Consumo x declividade")
            slope_df = prof[prof["estado_processo"].isin(["Efetivo", "Deslocamento", "Manobra"])].copy()
            slope_df = slope_df[slope_df["classe_decliv"].notna() & slope_df["classe_decliv"].ne("nan")].copy()
            slope_sum = (
                slope_df.groupby("classe_decliv", as_index=False)
                .agg(horas=("horas_evento", "sum"), litros=("consumo_l_estimado", "sum"))
            )
            order_decliv = ["0-3%", "3-8%", "8-20%", "20-45%", ">45%"]
            slope_sum["classe_decliv"] = pd.Categorical(slope_sum["classe_decliv"], categories=order_decliv, ordered=True)
            slope_sum = slope_sum.sort_values("classe_decliv")
            slope_sum["l_h"] = slope_sum["litros"] / slope_sum["horas"]
            base_lh = slope_sum.loc[slope_sum["classe_decliv"] == "0-3%", "l_h"]
            base_lh = base_lh.iloc[0] if len(base_lh) else np.nan
            slope_sum["delta_pct_vs_0_3"] = (
                (slope_sum["l_h"] / base_lh - 1.0) * 100.0 if pd.notna(base_lh) and base_lh > 0 else np.nan
            )

            sleft, sright = st.columns([1.35, 1])
            with sleft:
                fig_slope = px.bar(
                    slope_sum,
                    x="classe_decliv",
                    y="l_h",
                    text="l_h",
                    title="Consumo medio por faixa de declividade",
                    labels={"classe_decliv": "Declividade", "l_h": "L/h"},
                )
                fig_slope.update_traces(texttemplate="%{text:.2f}", textposition="outside", marker_color="#1d4e89")
                fig_slope.update_layout(
                    template="plotly_white",
                    height=350,
                    margin=dict(l=10, r=10, t=40, b=10),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(fig_slope, use_container_width=True)
            with sright:
                view_cols = ["classe_decliv", "horas", "litros", "l_h", "delta_pct_vs_0_3"]
                st.dataframe(slope_sum[view_cols], use_container_width=True, height=320)

            st.markdown("#### Mapa georreferenciado dentro dos talhoes")
            map_df = prof[
                [
                    "latitude_interpolacao",
                    "longitude_interpolacao",
                    "cd_equipamento",
                    "talhao_label",
                    "estado_processo",
                    "vl_consumo_instantaneo",
                    "declividade_pct",
                ]
            ].dropna(subset=["latitude_interpolacao", "longitude_interpolacao"])
            map_color = st.selectbox(
                "Colorir mapa por",
                ["vl_consumo_instantaneo", "declividade_pct", "estado_processo", "talhao_label"],
                key="pro_map_color",
            )
            if len(map_df) > 50000:
                map_df = map_df.sample(50000, random_state=42)
            if map_color in ["estado_processo", "talhao_label"]:
                fig_map = px.scatter_mapbox(
                    map_df,
                    lat="latitude_interpolacao",
                    lon="longitude_interpolacao",
                    color=map_color,
                    hover_data=["cd_equipamento", "talhao_label", "vl_consumo_instantaneo", "declividade_pct"],
                    zoom=10,
                    height=620,
                    title="Distribuicao operacional georreferenciada",
                )
            else:
                fig_map = px.scatter_mapbox(
                    map_df,
                    lat="latitude_interpolacao",
                    lon="longitude_interpolacao",
                    color=map_color,
                    color_continuous_scale="Turbo",
                    hover_data=["cd_equipamento", "talhao_label", "estado_processo"],
                    zoom=10,
                    height=620,
                    title="Distribuicao operacional georreferenciada",
                )
            fig_map.update_layout(
                mapbox_style="carto-positron",
                template="plotly_white",
                margin=dict(l=10, r=10, t=40, b=10),
                paper_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(
                fig_map,
                use_container_width=True,
                config={"scrollZoom": True, "displayModeBar": True},
            )

            st.markdown("#### Faixas de declividade com rastros de consumo")
            t1, t2 = st.columns([1.2, 1])
            with t1:
                st.caption("Regra fixa aplicada: rastros apenas em `Efetivo` e dentro dos talhões.")
            with t2:
                track_metric = st.selectbox(
                    "Colorir consumo por",
                    ["vl_consumo_instantaneo", "consumo_l_estimado"],
                    key="pro_tracks_metric",
                )
            with st.container():
                max_points = st.slider("Max pontos no mapa", 5000, 60000, 25000, step=5000, key="pro_tracks_max_points")

            tracks_df = prof.copy()
            tracks_df = tracks_df[
                tracks_df["estado_processo"].eq("Efetivo")
                & tracks_df["talhao_label"].notna()
                & tracks_df["talhao_label"].ne("SEM_TALHAO")
            ].copy()
            tracks_df = tracks_df.dropna(subset=["latitude_interpolacao", "longitude_interpolacao", track_metric])
            tracks_df = tracks_df[
                tracks_df["latitude_interpolacao"].between(-90, 90)
                & tracks_df["longitude_interpolacao"].between(-180, 180)
            ].copy()

            if tracks_df.empty:
                st.info("Sem pontos de rastro para os filtros atuais.")
            else:
                if len(tracks_df) > max_points:
                    tracks_df = tracks_df.sample(max_points, random_state=42)
                tracks_df = tracks_df.sort_values(["cd_equipamento", "dt_hr_local_inicial"])

                slope_class = classify_declividade_array(rasters["Declividade"]["arr"])
                base_gray = hillshade(
                    rasters["MDT (Elevacao)"]["arr"],
                    rasters["MDT (Elevacao)"]["transform"],
                    rasters["MDT (Elevacao)"]["bounds"],
                )
                fig_tracks = build_decliv_overlay_figure(
                    base_gray,
                    slope_class,
                    rasters["Declividade"]["bounds"],
                    title="Declividade (faixas) + rastros com consumo",
                )

                # Linhas de rastro por equipamento (baixa opacidade para manter legibilidade).
                for eq, grp_eq in tracks_df.groupby("cd_equipamento", sort=False):
                    if len(grp_eq) > 1200:
                        stride = int(np.ceil(len(grp_eq) / 1200))
                        grp_eq = grp_eq.iloc[::stride, :]
                    fig_tracks.add_trace(
                        go.Scattergl(
                            x=grp_eq["longitude_interpolacao"],
                            y=grp_eq["latitude_interpolacao"],
                            mode="lines",
                            line=dict(color="rgba(18,38,58,0.20)", width=1),
                            showlegend=False,
                            hoverinfo="skip",
                            name=f"Rastro {eq}",
                        )
                    )

                c_low = float(tracks_df[track_metric].quantile(0.05))
                c_high = float(tracks_df[track_metric].quantile(0.95))
                fig_tracks.add_trace(
                    go.Scattergl(
                        x=tracks_df["longitude_interpolacao"],
                        y=tracks_df["latitude_interpolacao"],
                        mode="markers",
                        marker=dict(
                            size=5,
                            opacity=0.82,
                            color=tracks_df[track_metric],
                            colorscale="Turbo",
                            cmin=c_low,
                            cmax=c_high,
                            colorbar=dict(title="Consumo"),
                        ),
                        customdata=np.stack(
                            [
                                tracks_df["cd_equipamento"].astype(str).to_numpy(),
                                tracks_df["estado_processo"].astype(str).to_numpy(),
                                tracks_df["talhao_label"].astype(str).to_numpy(),
                                tracks_df["declividade_pct"].to_numpy(),
                                tracks_df[track_metric].to_numpy(),
                            ],
                            axis=-1,
                        ),
                        hovertemplate=(
                            "<b>Equip:</b> %{customdata[0]}<br>"
                            "<b>Estado:</b> %{customdata[1]}<br>"
                            "<b>Talhao:</b> %{customdata[2]}<br>"
                            "<b>Declividade:</b> %{customdata[3]:.2f}%<br>"
                            "<b>Consumo:</b> %{customdata[4]:.2f}<extra></extra>"
                        ),
                        name="Pontos de consumo",
                        showlegend=False,
                    )
                )
                fig_tracks.update_layout(
                    height=700,
                    margin=dict(l=10, r=10, t=45, b=10),
                )
                st.plotly_chart(fig_tracks, use_container_width=True)
                st.caption(
                    "Leitura recomendada: use zoom nos talhoes com maiores tons quentes na camada de consumo e compare com as classes de declividade ao fundo."
                )

            st.markdown("#### Direcao operacional e eficiencia")
            dir_df = prof[
                prof["dir_valida"]
                & prof["estado_processo"].isin(["Efetivo", "Deslocamento", "Manobra"])
            ].copy()
            if dir_df.empty:
                st.info("Sem dados suficientes de direcao valida no recorte atual.")
            else:
                dir_sum = (
                    dir_df.groupby("direcao_setor", as_index=False)
                    .agg(
                        horas=("horas_evento", "sum"),
                        litros=("consumo_l_estimado", "sum"),
                        dist_m=("dist_m", "sum"),
                        hectares=("hectares_evento", "sum"),
                    )
                )
                dir_order = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
                dir_sum["direcao_setor"] = pd.Categorical(dir_sum["direcao_setor"], categories=dir_order, ordered=True)
                dir_sum = dir_sum.sort_values("direcao_setor")
                dir_sum["dist_km"] = dir_sum["dist_m"] / 1000.0
                dir_sum["l_h"] = dir_sum["litros"] / dir_sum["horas"]
                dir_sum["l_km"] = dir_sum["litros"] / dir_sum["dist_km"]
                dir_sum["l_ha"] = np.where(dir_sum["hectares"] > 0, dir_sum["litros"] / dir_sum["hectares"], np.nan)

                dleft, dright = st.columns([1.15, 1.15])
                with dleft:
                    fig_dir = px.bar(
                        dir_sum,
                        x="direcao_setor",
                        y="l_h",
                        text="l_h",
                        title="Consumo medio por direcao (L/h)",
                        labels={"direcao_setor": "Direcao", "l_h": "L/h"},
                    )
                    fig_dir.update_traces(texttemplate="%{text:.2f}", textposition="outside", marker_color="#1d4e89")
                    fig_dir.update_layout(
                        template="plotly_white",
                        height=330,
                        margin=dict(l=10, r=10, t=40, b=10),
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                    )
                    st.plotly_chart(fig_dir, use_container_width=True)
                with dright:
                    fig_dir_km = px.bar(
                        dir_sum,
                        x="direcao_setor",
                        y="l_km",
                        text="l_km",
                        title="Eficiencia por direcao (L/km)",
                        labels={"direcao_setor": "Direcao", "l_km": "L/km"},
                    )
                    fig_dir_km.update_traces(texttemplate="%{text:.2f}", textposition="outside", marker_color="#2a9d8f")
                    fig_dir_km.update_layout(
                        template="plotly_white",
                        height=330,
                        margin=dict(l=10, r=10, t=40, b=10),
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                    )
                    st.plotly_chart(fig_dir_km, use_container_width=True)

                dir_base = dir_sum[dir_sum["horas"] >= 10].copy()
                bench_lh = dir_base["l_h"].quantile(0.25) if not dir_base.empty else np.nan
                dir_gain = dir_base.copy()
                dir_gain["delta_l_h_vs_bench"] = (dir_gain["l_h"] - bench_lh).clip(lower=0)
                dir_gain["litros_potenciais"] = dir_gain["delta_l_h_vs_bench"] * dir_gain["horas"]
                dir_gain["retorno_r$"] = dir_gain["litros_potenciais"] * fuel_price
                st.dataframe(dir_gain.sort_values("retorno_r$", ascending=False), use_container_width=True, height=220)

            st.markdown("#### Sobreposicao operacional (largura x rastro) e efeito de meia plataforma")
            o1, o2, o3 = st.columns([0.9, 1.2, 1.1])
            valid_days = sorted(prof["data"].dropna().unique().tolist())
            with o1:
                overlap_day = st.selectbox(
                    "Dia",
                    valid_days,
                    index=max(len(valid_days) - 1, 0),
                    key="pro_overlap_day",
                )
            ov_base = prof[
                (prof["data"] == overlap_day)
                & (prof["estado_processo"].eq("Efetivo"))
                & (prof["talhao_label"].notna())
                & (prof["talhao_label"].ne("SEM_TALHAO"))
            ].copy()
            talhao_opts = sorted(ov_base["talhao_label"].astype(str).unique().tolist()) if not ov_base.empty else []
            with o2:
                overlap_talhao = st.selectbox(
                    "Talhão (somente efetivo)",
                    talhao_opts if talhao_opts else ["Sem dados"],
                    key="pro_overlap_talhao",
                )
            with o3:
                overlap_points = st.slider(
                    "Densidade geométrica (pts/máquina)",
                    600,
                    4000,
                    1800,
                    step=200,
                    key="pro_overlap_pts",
                )

            ov_df = ov_base.copy()
            if talhao_opts:
                ov_df = ov_df[ov_df["talhao_label"].astype(str) == str(overlap_talhao)].copy()
            ov_df = ov_df[ov_df["vl_largura_implemento"].notna()].copy()

            if ov_df.empty:
                st.info("Sem dados efetivos dentro do talhão selecionado para esse dia.")
            else:
                overlap_res = estimate_overlap_by_machine_day(ov_df, max_points_per_group=int(overlap_points))
                coverage_ll, coverage_utm = build_machine_coverage_polygons(
                    ov_df, max_points_per_machine=int(overlap_points)
                )
                swath_ll, swath_utm = build_swath_segment_polygons(
                    ov_df, max_segments_per_machine=int(max(500, overlap_points))
                )

                overlap_geom_ll = None
                overlap_global_ha = np.nan
                overlap_global_pct = np.nan
                theoretical_global_ha = np.nan
                unique_global_ha = np.nan
                if coverage_utm is not None and not coverage_utm.empty:
                    union_geom = unary_union(list(coverage_utm.geometry))
                    theoretical_global_ha = float(coverage_utm["theoretical_ha"].sum())
                    unique_global_ha = (
                        float(union_geom.area / 10000.0) if union_geom is not None and not union_geom.is_empty else 0.0
                    )
                    overlap_global_ha = max(theoretical_global_ha - unique_global_ha, 0.0)
                    overlap_global_pct = (
                        (overlap_global_ha / theoretical_global_ha) * 100.0 if theoretical_global_ha > 0 else np.nan
                    )
                    ov_geom = build_overlap_polygon(coverage_utm)
                    if ov_geom is not None and not ov_geom.is_empty:
                        overlap_geom_ll = (
                            gpd.GeoSeries([ov_geom], crs=coverage_utm.crs).to_crs("EPSG:4326").iloc[0]
                        )

                meta_overlap_pct = st.slider(
                    "Meta de sobreposição (%) para cenário",
                    0.0,
                    20.0,
                    2.0,
                    0.5,
                    key="pro_overlap_meta_pct",
                )
                gain_ha_meta = np.nan
                if pd.notna(theoretical_global_ha) and pd.notna(overlap_global_ha):
                    target_overlap_ha = theoretical_global_ha * (meta_overlap_pct / 100.0)
                    gain_ha_meta = max(overlap_global_ha - target_overlap_ha, 0.0)

                k_ov1, k_ov2, k_ov3, k_ov4 = st.columns(4)
                with k_ov1:
                    kpi_card("Taxa de sobreposição", f"{overlap_global_pct:.2f} %" if pd.notna(overlap_global_pct) else "n/d", f"{overlap_day} | {overlap_talhao}")
                with k_ov2:
                    kpi_card("Área sobreposta", f"{overlap_global_ha:.2f} ha" if pd.notna(overlap_global_ha) else "n/d", "interseção entre coberturas")
                with k_ov3:
                    kpi_card("Área única coberta", f"{unique_global_ha:.2f} ha" if pd.notna(unique_global_ha) else "n/d", "sem sobreposição")
                with k_ov4:
                    kpi_card("Ganho com meta", f"{gain_ha_meta:.2f} ha" if pd.notna(gain_ha_meta) else "n/d", f"se cair para {meta_overlap_pct:.1f}%")

                left_map, right_chart = st.columns([1.45, 1.0])
                with left_map:
                    fig_cov = go.Figure()
                    # Limite do talhão selecionado.
                    talhao_geom = None
                    try:
                        all_fields = load_fields_map(FIELDS_FILE)
                        if str(all_fields.crs) != "EPSG:4326":
                            all_fields = all_fields.to_crs("EPSG:4326")
                        talhao_match = all_fields[all_fields["DESC_TALHA"].astype(str) == str(overlap_talhao)].copy() if "DESC_TALHA" in all_fields.columns else pd.DataFrame()
                        if not talhao_match.empty:
                            talhao_geom = unary_union(list(talhao_match.geometry))
                    except Exception:
                        talhao_geom = None
                    if talhao_geom is not None and not talhao_geom.is_empty:
                        add_polygon_to_mapbox(
                            fig_cov,
                            talhao_geom,
                            name=f"Talhão {overlap_talhao}",
                            line_color="rgba(40,60,80,0.9)",
                            fill_color="rgba(0,0,0,0)",
                            line_width=2.0,
                            showlegend=True,
                        )

                    # Faixas/passadas como polígonos da plataforma.
                    if swath_ll is not None and not swath_ll.empty:
                        machine_palette = px.colors.qualitative.Bold + px.colors.qualitative.Safe
                        machine_colors = {
                            eq: machine_palette[i % len(machine_palette)]
                            for i, eq in enumerate(sorted(swath_ll["cd_equipamento"].astype(str).unique().tolist()))
                        }
                        for eq, grp_eq in swath_ll.groupby("cd_equipamento", sort=False):
                            color = machine_colors.get(str(eq), "#2a9d8f")
                            # limita desenhados para performance.
                            grp_eq = grp_eq.iloc[: min(len(grp_eq), 900), :]
                            first = True
                            for geom in grp_eq.geometry:
                                add_polygon_to_mapbox(
                                    fig_cov,
                                    geom,
                                    name=f"Faixa {eq}",
                                    line_color=color,
                                    fill_color="rgba(70,130,180,0.20)",
                                    line_width=0.8,
                                    showlegend=first,
                                )
                                first = False

                    # Polígono de sobreposição em destaque.
                    if overlap_geom_ll is not None:
                        add_polygon_to_mapbox(
                            fig_cov,
                            overlap_geom_ll,
                            name="Sobreposição",
                            line_color="rgba(180,20,20,0.95)",
                            fill_color="rgba(220,20,20,0.40)",
                            line_width=2.0,
                            showlegend=True,
                        )

                    # Pontos centrais de GPS por cima (opcional visual).
                    pts = ov_df.dropna(subset=["latitude_interpolacao", "longitude_interpolacao", "vl_consumo_instantaneo"]).copy()
                    if len(pts) > 8000:
                        pts = pts.sample(8000, random_state=42)
                    fig_cov.add_trace(
                        go.Scattermapbox(
                            lon=pts["longitude_interpolacao"],
                            lat=pts["latitude_interpolacao"],
                            mode="markers",
                            marker=dict(
                                size=3,
                                opacity=0.45,
                                color=pts["vl_consumo_instantaneo"],
                                colorscale="Turbo",
                                cmin=float(pts["vl_consumo_instantaneo"].quantile(0.05)),
                                cmax=float(pts["vl_consumo_instantaneo"].quantile(0.95)),
                                colorbar=dict(title="Consumo L/h"),
                            ),
                            name="GPS centro",
                            showlegend=False,
                            hovertemplate="Consumo: %{marker.color:.2f}<extra></extra>",
                        )
                    )
                    fig_cov.update_layout(
                        mapbox=dict(
                            style="carto-positron",
                            center=dict(
                                lat=float(ov_df["latitude_interpolacao"].median()),
                                lon=float(ov_df["longitude_interpolacao"].median()),
                            ),
                            zoom=15,
                        ),
                        template="plotly_white",
                        height=680,
                        margin=dict(l=10, r=10, t=45, b=10),
                        paper_bgcolor="rgba(0,0,0,0)",
                        legend=dict(orientation="h", y=1.02, x=0),
                        title=f"Talhão {overlap_talhao}: faixas da plataforma + sobreposição",
                    )
                    st.plotly_chart(
                        fig_cov,
                        use_container_width=True,
                        config={"scrollZoom": True, "displayModeBar": True},
                    )
                with right_chart:
                    if overlap_res is not None and not overlap_res.empty:
                        fig_ov = px.bar(
                            overlap_res.sort_values("sobreposicao_pct", ascending=False),
                            x="cd_equipamento",
                            y="sobreposicao_pct",
                            color="area_sobreposicao_ha",
                            color_continuous_scale="OrRd",
                            title="Índice de sobreposição por máquina",
                            labels={
                                "cd_equipamento": "Máquina",
                                "sobreposicao_pct": "Sobreposição (%)",
                                "area_sobreposicao_ha": "Área sobreposta (ha)",
                            },
                        )
                        fig_ov.update_layout(
                            template="plotly_white",
                            height=320,
                            margin=dict(l=10, r=10, t=40, b=10),
                            paper_bgcolor="rgba(0,0,0,0)",
                            plot_bgcolor="rgba(0,0,0,0)",
                        )
                        st.plotly_chart(fig_ov, use_container_width=True)
                        st.dataframe(
                            overlap_res.sort_values("sobreposicao_pct", ascending=False),
                            use_container_width=True,
                            height=320,
                        )
                    else:
                        st.info("Sem ranking por máquina para este recorte.")
                st.caption(
                    "Modelo geométrico: GPS como eixo central da máquina; plataforma simulada por polígonos de cada passada com `largura_implemento/2` para cada lado."
                )

            # Analise de "faixinhas / meia plataforma" (proxy por eficiência de largura).
            eff_df = prof[
                prof["estado_processo"].isin(["Efetivo", "Deslocamento"])
                & prof["vl_largura_implemento"].between(0.5, 30)
                & prof.get("vl_velocidade", pd.Series(index=prof.index)).fillna(0).between(0.5, 25)
                & prof.get("vl_hectares_hora", pd.Series(index=prof.index)).fillna(0).between(0.01, 80)
            ].copy()
            if not eff_df.empty and "vl_velocidade" in eff_df.columns and "vl_hectares_hora" in eff_df.columns:
                eff_df["ha_h_teorico"] = (eff_df["vl_velocidade"] * eff_df["vl_largura_implemento"]) / 10.0
                eff_df["indice_largura_efetiva"] = (eff_df["vl_hectares_hora"] / eff_df["ha_h_teorico"]).replace([np.inf, -np.inf], np.nan)
                eff_df = eff_df[eff_df["indice_largura_efetiva"].between(0.05, 1.3)].copy()

                if not eff_df.empty:
                    threshold = float(eff_df["indice_largura_efetiva"].quantile(0.25))
                    eff_df["modo_faixinha_proxy"] = eff_df["indice_largura_efetiva"] <= threshold

                    rpm_col = "vl_rpm" if "vl_rpm" in eff_df.columns else None
                    st.markdown(
                        f"- Critério proxy aplicado: `indice_largura_efetiva <= P25 ({threshold:.2f})` para representar operação parcial/faixinhas."
                    )
                    if rpm_col is not None:
                        comp = (
                            eff_df.groupby("modo_faixinha_proxy", as_index=False)
                            .agg(
                                horas=("horas_evento", "sum"),
                                rpm_mediana=(rpm_col, "median"),
                                consumo_l_h=("vl_consumo_instantaneo", "median"),
                                vel_mediana=("vl_velocidade", "median"),
                                largura_efetiva_med=("indice_largura_efetiva", "median"),
                            )
                        )
                        comp["modo"] = comp["modo_faixinha_proxy"].map({True: "Faixinha (proxy)", False: "Faixa cheia (proxy)"})
                        st.dataframe(
                            comp[
                                ["modo", "horas", "rpm_mediana", "consumo_l_h", "vel_mediana", "largura_efetiva_med"]
                            ],
                            use_container_width=True,
                            height=180,
                        )

                        fig_fx = px.scatter(
                            eff_df.sample(min(12000, len(eff_df)), random_state=42),
                            x="indice_largura_efetiva",
                            y=rpm_col,
                            color="vl_consumo_instantaneo",
                            color_continuous_scale="Turbo",
                            opacity=0.45,
                            title="RPM x indice de largura efetiva (proxy de meia plataforma)",
                            labels={"indice_largura_efetiva": "Indice largura efetiva", rpm_col: "RPM"},
                        )
                        fig_fx.update_layout(
                            template="plotly_white",
                            height=330,
                            margin=dict(l=10, r=10, t=40, b=10),
                            paper_bgcolor="rgba(0,0,0,0)",
                            plot_bgcolor="rgba(0,0,0,0)",
                        )
                        st.plotly_chart(fig_fx, use_container_width=True)
                        st.caption(
                            "Interpretação técnica: em operação parcial, a tendência esperada é redução de carga e possibilidade de RPM menor. "
                            "Se RPM não reduzir junto com largura efetiva, há espaço para ajuste operacional e economia."
                        )

            st.markdown("#### Sem apontamento e picos de parada")
            pleft, pright = st.columns([1, 1.25])
            with pleft:
                sem_talhao = (
                    prof[prof["sem_apontamento"]]
                    .groupby("talhao_label", as_index=False)
                    .agg(horas_sem=("horas_evento", "sum"), eventos=("talhao_label", "size"))
                    .sort_values("horas_sem", ascending=False)
                )
                fig_sem = px.bar(
                    sem_talhao.head(12),
                    x="horas_sem",
                    y="talhao_label",
                    orientation="h",
                    title="Top talhoes com sem apontamento",
                    labels={"horas_sem": "Horas", "talhao_label": "Talhao"},
                    color="eventos",
                    color_continuous_scale="Oranges",
                )
                fig_sem.update_layout(
                    template="plotly_white",
                    height=390,
                    margin=dict(l=10, r=10, t=40, b=10),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(fig_sem, use_container_width=True)
            with pright:
                stop_target = st.text_input("Parada alvo para pico horario", value="FALTA CAMINHAO", key="pro_stop_target")
                stop_df = prof[prof["estado_processo"] == "Parada"].copy()
                stop_df = stop_df[
                    stop_df["desc_parada"].str.upper().str.contains(stop_target.upper().strip(), na=False)
                ].copy()
                if stop_df.empty:
                    st.info("Sem registros para a parada alvo no recorte.")
                else:
                    hourly = (
                        stop_df.groupby("hora", as_index=False)
                        .agg(horas=("horas_evento", "sum"), eventos=("hora", "size"))
                        .sort_values("hora")
                    )
                    fig_peak = go.Figure()
                    fig_peak.add_bar(
                        x=hourly["hora"],
                        y=hourly["horas"],
                        name="Horas",
                        marker_color="#c1121f",
                    )
                    fig_peak.add_trace(
                        go.Scatter(
                            x=hourly["hora"],
                            y=hourly["eventos"],
                            mode="lines+markers",
                            name="Eventos",
                            yaxis="y2",
                            line=dict(color="#1d4e89"),
                        )
                    )
                    fig_peak.update_layout(
                        template="plotly_white",
                        height=390,
                        margin=dict(l=10, r=10, t=40, b=10),
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        title=f"Picos horarios - {stop_target}",
                        xaxis_title="Hora do dia",
                        yaxis=dict(title="Horas de parada"),
                        yaxis2=dict(title="Eventos", overlaying="y", side="right"),
                    )
                    st.plotly_chart(fig_peak, use_container_width=True)

            st.markdown("#### Viabilidade e retorno (cenarios)")
            v1, v2, v3 = st.columns(3)
            stop_sum = (
                prof[prof["estado_processo"] == "Parada"]
                .groupby("desc_parada", as_index=False)
                .agg(horas=("horas_evento", "sum"), litros=("consumo_l_estimado", "sum"))
            )
            stop_mean = (
                prof[prof["estado_processo"] == "Parada"]
                .groupby("desc_parada", as_index=False)["vl_consumo_instantaneo"]
                .mean()
                .rename(columns={"vl_consumo_instantaneo": "l_h_medio"})
            )
            stop_sum = stop_sum.merge(stop_mean, on="desc_parada", how="left")
            pot10 = np.where(stop_sum["l_h_medio"] > 0, stop_sum["litros"] * 0.10, 0).sum()
            pot20 = np.where(stop_sum["l_h_medio"] > 0, stop_sum["litros"] * 0.20, 0).sum()
            dir_pot = 0.0
            if "dir_gain" in locals() and isinstance(dir_gain, pd.DataFrame) and not dir_gain.empty:
                dir_pot = dir_gain["litros_potenciais"].sum()

            with v1:
                kpi_card("Potencial parada 10%", f"{pot10:.1f} L", f"R$ {(pot10 * fuel_price):,.0f}".replace(",", "."))
            with v2:
                kpi_card("Potencial parada 20%", f"{pot20:.1f} L", f"R$ {(pot20 * fuel_price):,.0f}".replace(",", "."))
            with v3:
                kpi_card("Potencial direcao", f"{dir_pot:.1f} L", f"R$ {(dir_pot * fuel_price):,.0f}".replace(",", "."))

            with st.expander("Metodologia e formulas de calculo", expanded=False):
                st.markdown(
                    """
- `horas_evento = vl_tempo_segundos / 3600`
- `consumo_l_estimado = vl_consumo_instantaneo * horas_evento` (premissa de `vl_consumo_instantaneo` em L/h)
- `l_h = litros / horas`
- `l_km = litros / distancia_km`
- `l_ha = litros / hectares`
- Declividade por ponto: amostragem do raster `declividade_area_talhoes.tif` nas coordenadas da telemetria.
- Talhao por ponto: `spatial join` do ponto georreferenciado com `fields.mbtiles`.
- Bearing (direcao): calculo angular com coordenadas inicial/final do evento.
- Qualidade para direcao: coordenadas validas, distancia >= 5 m, velocidade implícita <= 20 m/s, duracao <= 2 h.
- Sem apontamento: `desc_parada=*NAO_DEFINIDO*` ou `desc_operador=*NAO_DEFINIDO*` ou `cd_operador=-1`.
- Cenario de viabilidade em parada: aplicacao de reducao de 10% e 20% sobre litros em eventos de parada com consumo positivo.
- Cenario direcional: benchmark = quartil inferior de `L/h` por setor direcional com base mínima de horas.
                    """
                )

            st.markdown("#### Diagnostico por Machine Learning (rodado offline)")
            if not ML_RESULTS_DIR.exists():
                st.info("Resultados de ML ainda não encontrados em `analises_resultados/ml`.")
            else:
                ml_metrics_path = ML_RESULTS_DIR / "ml_metrics.csv"
                ml_hot_eq_path = ML_RESULTS_DIR / "hotspots_falha_maquina.csv"
                ml_hot_hour_path = ML_RESULTS_DIR / "hotspots_falha_hora.csv"

                if ml_metrics_path.exists():
                    ml_metrics = pd.read_csv(ml_metrics_path, sep=";")
                    st.dataframe(ml_metrics, use_container_width=True, height=220)
                else:
                    st.info("Arquivo `ml_metrics.csv` não encontrado.")

                fi_files = sorted(ML_RESULTS_DIR.glob("feature_importance_*.csv"))
                if fi_files:
                    fi_map = {p.stem.replace("feature_importance_", ""): p for p in fi_files}
                    fi_sel = st.selectbox("Drivers do modelo (feature importance)", list(fi_map.keys()), key="ml_fi_select")
                    fi_df = pd.read_csv(fi_map[fi_sel], sep=";")
                    fig_fi = px.bar(
                        fi_df.head(20).sort_values("importance", ascending=True),
                        x="importance",
                        y="feature",
                        orientation="h",
                        title=f"Top fatores - modelo {fi_sel}",
                        labels={"importance": "Importância", "feature": "Variável"},
                        color="importance",
                        color_continuous_scale="Tealgrn",
                    )
                    fig_fi.update_layout(
                        template="plotly_white",
                        height=420,
                        margin=dict(l=10, r=10, t=40, b=10),
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                    )
                    st.plotly_chart(fig_fi, use_container_width=True)

                hleft, hright = st.columns(2)
                with hleft:
                    if ml_hot_eq_path.exists():
                        hot_eq = pd.read_csv(ml_hot_eq_path, sep=";")
                        fig_hot_eq = px.bar(
                            hot_eq.head(12).sort_values("taxa_falha", ascending=True),
                            x="taxa_falha",
                            y="cd_equipamento",
                            orientation="h",
                            title="Hotspots de falha por máquina",
                            labels={"taxa_falha": "Taxa de falha", "cd_equipamento": "Máquina"},
                            color="taxa_falha",
                            color_continuous_scale="OrRd",
                        )
                        fig_hot_eq.update_layout(
                            template="plotly_white",
                            height=340,
                            margin=dict(l=10, r=10, t=40, b=10),
                            paper_bgcolor="rgba(0,0,0,0)",
                            plot_bgcolor="rgba(0,0,0,0)",
                        )
                        st.plotly_chart(fig_hot_eq, use_container_width=True)
                with hright:
                    if ml_hot_hour_path.exists():
                        hot_hour = pd.read_csv(ml_hot_hour_path, sep=";")
                        fig_hot_hr = px.bar(
                            hot_hour.sort_values("hora"),
                            x="hora",
                            y="taxa_falha",
                            title="Taxa de falha por hora",
                            labels={"hora": "Hora", "taxa_falha": "Taxa de falha"},
                            color="taxa_falha",
                            color_continuous_scale="YlOrRd",
                        )
                        fig_hot_hr.update_layout(
                            template="plotly_white",
                            height=340,
                            margin=dict(l=10, r=10, t=40, b=10),
                            paper_bgcolor="rgba(0,0,0,0)",
                            plot_bgcolor="rgba(0,0,0,0)",
                        )
                        st.plotly_chart(fig_hot_hr, use_container_width=True)

                st.caption(
                    "Nota técnica: modelos com alvo muito desbalanceado podem inflar métricas. "
                    "Priorize leitura conjunta de métricas, importância de variáveis e hotspots operacionais."
                )
