import io
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import rasterio
import streamlit as st

st.set_page_config(page_title="Análise MDT - Agricultura de Precisão", layout="wide")

DATA_FILES = {
    "MDT (Elevação)": Path("mdt_nasadem_area_talhoes.tif"),
    "Declividade": Path("declividade_area_talhoes.tif"),
    "Diferença de Elevação Média": Path("diferenca_elevacao_media_area_talhoes.tif"),
}


def read_raster(path: Path):
    with rasterio.open(path) as src:
        arr = src.read(1).astype("float64")
        nodata = src.nodata
        if nodata is not None:
            arr = np.where(arr == nodata, np.nan, arr)
        bounds = src.bounds
        transform = src.transform
        crs = src.crs
        res = src.res
    return arr, bounds, transform, crs, res


def raster_stats(arr: np.ndarray):
    valid = arr[np.isfinite(arr)]
    if valid.size == 0:
        return {
            "Mínimo": np.nan,
            "Máximo": np.nan,
            "Média": np.nan,
            "Mediana": np.nan,
            "Desvio padrão": np.nan,
            "P05": np.nan,
            "P95": np.nan,
            "Pixels válidos": 0,
        }
    return {
        "Mínimo": float(np.nanmin(valid)),
        "Máximo": float(np.nanmax(valid)),
        "Média": float(np.nanmean(valid)),
        "Mediana": float(np.nanmedian(valid)),
        "Desvio padrão": float(np.nanstd(valid)),
        "P05": float(np.nanpercentile(valid, 5)),
        "P95": float(np.nanpercentile(valid, 95)),
        "Pixels válidos": int(valid.size),
    }


def normalize(arr: np.ndarray):
    vmin = np.nanpercentile(arr, 2)
    vmax = np.nanpercentile(arr, 98)
    return np.clip((arr - vmin) / (vmax - vmin + 1e-12), 0, 1)


def hillshade(elevation: np.ndarray, transform, azimuth=315, altitude=45):
    xres = transform.a
    yres = abs(transform.e)
    dy, dx = np.gradient(elevation, yres, xres)
    slope = np.pi / 2.0 - np.arctan(np.sqrt(dx * dx + dy * dy))
    aspect = np.arctan2(-dx, dy)

    az_rad = np.deg2rad(azimuth)
    alt_rad = np.deg2rad(altitude)

    shaded = (
        np.sin(alt_rad) * np.sin(slope)
        + np.cos(alt_rad) * np.cos(slope) * np.cos(az_rad - aspect)
    )
    shaded = np.where(np.isfinite(elevation), shaded, np.nan)
    return normalize(shaded)


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
        return pd.DataFrame(columns=["Classe", "Área relativa (%)", "Pixels"])

    clipped = np.clip(valid, 0, np.inf)
    classes = pd.cut(clipped, bins=bins, labels=labels, right=False)
    counts = pd.value_counts(classes, sort=False)
    df = pd.DataFrame({
        "Classe": counts.index.astype(str),
        "Pixels": counts.values,
    })
    df["Área relativa (%)"] = (df["Pixels"] / df["Pixels"].sum() * 100).round(2)
    return df


st.title("MDT e Declividade - Unidade de Avaliação")
st.markdown(
    "Ferramenta inicial para análise de altimetria, declividade e integração futura com telemetria (VRPM, velocidade, consumo, etc.)."
)

missing = [name for name, file in DATA_FILES.items() if not file.exists()]
if missing:
    st.error(f"Arquivos ausentes: {', '.join(missing)}")
    st.stop()

rasters = {}
meta_rows = []
for name, path in DATA_FILES.items():
    arr, bounds, transform, crs, res = read_raster(path)
    rasters[name] = {
        "arr": arr,
        "bounds": bounds,
        "transform": transform,
        "crs": crs,
        "res": res,
    }
    stats = raster_stats(arr)
    meta_rows.append({
        "Camada": name,
        "Arquivo": str(path),
        "CRS": str(crs),
        "Resolução X (m)": round(res[0], 3),
        "Resolução Y (m)": round(res[1], 3),
        **{k: round(v, 3) if isinstance(v, float) else v for k, v in stats.items()},
    })

st.subheader("Resumo das camadas")
st.dataframe(pd.DataFrame(meta_rows), use_container_width=True)

col1, col2 = st.columns([2, 1])
with col2:
    selected_layer = st.selectbox("Camada para mapa", list(rasters.keys()))
    percentile_cut = st.slider("Recorte para contraste (%)", 0, 20, 2)

arr = rasters[selected_layer]["arr"]
valid = arr[np.isfinite(arr)]
vmin = np.nanpercentile(valid, percentile_cut)
vmax = np.nanpercentile(valid, 100 - percentile_cut)

with col1:
    fig = px.imshow(
        arr,
        color_continuous_scale="Viridis",
        zmin=vmin,
        zmax=vmax,
        origin="upper",
        aspect="auto",
        title=f"Mapa raster: {selected_layer}",
    )
    fig.update_layout(height=550, margin=dict(l=10, r=10, t=40, b=10))
    st.plotly_chart(fig, use_container_width=True)

st.subheader("Distribuição dos valores")
fig_hist = go.Figure()
fig_hist.add_trace(
    go.Histogram(x=valid, nbinsx=60, marker_color="#2a9d8f", opacity=0.85)
)
fig_hist.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10))
st.plotly_chart(fig_hist, use_container_width=True)

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
            title="Participação por classe de declividade",
        )
        pie.update_layout(height=360, margin=dict(l=10, r=10, t=45, b=10))
        st.plotly_chart(pie, use_container_width=True)

st.subheader("Visualização de relevo (hillshade)")
mdt_arr = rasters["MDT (Elevação)"]["arr"]
hs = hillshade(mdt_arr, rasters["MDT (Elevação)"]["transform"])
fig_hs = px.imshow(hs, color_continuous_scale="gray", origin="upper", aspect="auto")
fig_hs.update_layout(height=500, margin=dict(l=10, r=10, t=10, b=10))
st.plotly_chart(fig_hs, use_container_width=True)

st.subheader("Exportar estatísticas (CSV)")
out_stats = pd.DataFrame(meta_rows)
csv_bytes = out_stats.to_csv(index=False).encode("utf-8")
st.download_button(
    "Baixar resumo das camadas",
    data=csv_bytes,
    file_name="resumo_rasters_mdt_declividade.csv",
    mime="text/csv",
)

st.info(
    "Próximo passo sugerido: anexar telemetria georreferenciada (CSV/Parquet com latitude/longitude e VRPM), "
    "realizar amostragem espacial no MDT/declividade e gerar análises por talhão/rota."
)
