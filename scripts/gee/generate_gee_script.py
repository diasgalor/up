from __future__ import annotations

import argparse
import json
from pathlib import Path

import geopandas as gpd
from shapely.geometry import mapping


def round_coords(obj, nd=6):
    if isinstance(obj, (list, tuple)):
        return [round_coords(v, nd) for v in obj]
    if isinstance(obj, float):
        return round(obj, nd)
    if isinstance(obj, dict):
        return {k: round_coords(v, nd) for k, v in obj.items()}
    return obj


def build_gee_script(fields_path: Path, farm_id: int, out_path: Path):
    gdf = gpd.read_file(fields_path)
    gdf = gdf[gdf["FAZENDA"] == farm_id].copy()
    if gdf.empty:
        raise ValueError(f"Nenhum talhao encontrado para FAZENDA={farm_id}")
    farm_name = str(gdf["NOME_FAZ"].iloc[0]).upper().replace(" ", "_")
    gdf = gdf.to_crs(4326)
    gdf["geometry"] = gdf.geometry.simplify(0.00001, preserve_topology=True)

    features = []
    for _, row in gdf.iterrows():
        geom = round_coords(mapping(row.geometry), 6)
        talhao_label = str(row.get("DESC_TALHA") if row.get("DESC_TALHA") not in [None, ""] else row.get("TALHAO"))
        props = {
            "FAZENDA": int(row.get("FAZENDA")) if row.get("FAZENDA") is not None else None,
            "NOME_FAZ": str(row.get("NOME_FAZ")),
            "TALHAO": int(row.get("TALHAO")) if str(row.get("TALHAO")).replace(".", "", 1).isdigit() else str(row.get("TALHAO")),
            "DESC_TALHA": talhao_label,
            "AREA_TOTAL": float(row.get("AREA_TOTAL")) if row.get("AREA_TOTAL") is not None else None,
        }
        features.append({"type": "Feature", "geometry": geom, "properties": props})

    geojson_fc = {"type": "FeatureCollection", "features": features}
    geojson_text = json.dumps(geojson_fc, ensure_ascii=False)

    js = f"""// Gerado automaticamente por generate_gee_script.py
// Fazenda: {farm_name} (ID {farm_id})
var talhoesGeoJson = {geojson_text};
var talhoes = ee.FeatureCollection(talhoesGeoJson.features.map(function(f) {{
  return ee.Feature(ee.Geometry(f.geometry), f.properties);
}}));

var fazenda = talhoes.geometry().dissolve();
var pontosRecorte = talhoes.map(function(f) {{
  return ee.Feature(f.geometry().centroid(1), {{
    TALHAO: f.get('TALHAO'),
    DESC_TALHA: f.get('DESC_TALHA')
  }});
}});

Map.centerObject(fazenda, 13);
Map.addLayer(fazenda, {{color: 'yellow'}}, 'Limite fazenda');
Map.addLayer(talhoes.style({{color: '#00FFFF', fillColor: '00000000', width: 1}}), {{}}, 'Talhoes');
Map.addLayer(pontosRecorte, {{color: 'red'}}, 'Pontos de recorte');

function maskS2Clouds(img) {{
  var qa = img.select('QA60');
  var cloudBitMask = 1 << 10;
  var cirrusBitMask = 1 << 11;
  var mask = qa.bitwiseAnd(cloudBitMask).eq(0)
    .and(qa.bitwiseAnd(cirrusBitMask).eq(0));
  var scl = img.select('SCL');
  var sclMask = scl.neq(3).and(scl.neq(8)).and(scl.neq(9)).and(scl.neq(10)).and(scl.neq(11));
  return img.updateMask(mask).updateMask(sclMask).divide(10000).copyProperties(img, ['system:time_start']);
}}

function addNdvi(img) {{
  return img.addBands(img.normalizedDifference(['B8', 'B4']).rename('NDVI'));
}}

var endDate = ee.Date(Date.now());
var startRecent = endDate.advance(-120, 'day');
var analysisYear = endDate.get('year');

var s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
  .filterBounds(fazenda)
  .filterDate(startRecent, endDate)
  .filter(ee.Filter.lte('CLOUDY_PIXEL_PERCENTAGE', 50))
  .map(maskS2Clouds)
  .map(addNdvi);

var latestGood = ee.Image(s2.sort('system:time_start', false).first());

function monthComposite(year, month) {{
  var start = ee.Date.fromYMD(year, month, 1);
  var end = start.advance(1, 'month');
  var coll = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
    .filterBounds(fazenda)
    .filterDate(start, end)
    .filter(ee.Filter.lte('CLOUDY_PIXEL_PERCENTAGE', 60))
    .map(maskS2Clouds)
    .map(addNdvi);
  return coll.median().set({{'year': year, 'month': month, 'count_images': coll.size()}});
}}

var jan = monthComposite(analysisYear, 1);
var feb = monthComposite(analysisYear, 2);
var mar = monthComposite(analysisYear, 3);
var ndviJan = jan.select('NDVI').rename('NDVI_JAN');
var ndviFeb = feb.select('NDVI').rename('NDVI_FEV');
var ndviMar = mar.select('NDVI').rename('NDVI_MAR');
var ndviDiffJanMar = ndviMar.subtract(ndviJan).rename('NDVI_DIFF_JAN_MAR');

Map.addLayer(latestGood.clip(fazenda), {{bands: ['B4','B3','B2'], min: 0.03, max: 0.35}}, 'Ultima boa RGB');
Map.addLayer(latestGood.select('NDVI').clip(fazenda), {{min: 0, max: 0.9, palette: ['#d73027','#fee08b','#1a9850']}}, 'NDVI recente');
Map.addLayer(ndviDiffJanMar.clip(fazenda), {{min: -0.4, max: 0.4, palette: ['#762a83','#f7f7f7','#1b7837']}}, 'NDVI diff Jan-Mar');

var statsByTalhao = ee.Image.cat([latestGood.select('NDVI').rename('NDVI_LATEST'), ndviJan, ndviFeb, ndviMar, ndviDiffJanMar])
  .reduceRegions({{
    collection: talhoes,
    reducer: ee.Reducer.mean().combine({{reducer2: ee.Reducer.stdDev(), sharedInputs: true}}),
    scale: 10,
    tileScale: 4
  }});

Export.image.toDrive({{
  image: latestGood.select(['B4','B3','B2']).clip(fazenda),
  description: 'S2_latest_RGB_{farm_name}',
  folder: 'GEE_EXPORT',
  fileNamePrefix: 'S2_latest_RGB_{farm_name}',
  region: fazenda, scale: 10, maxPixels: 1e13
}});
Export.image.toDrive({{
  image: latestGood.select('NDVI').clip(fazenda),
  description: 'S2_latest_NDVI_{farm_name}',
  folder: 'GEE_EXPORT',
  fileNamePrefix: 'S2_latest_NDVI_{farm_name}',
  region: fazenda, scale: 10, maxPixels: 1e13
}});
Export.image.toDrive({{
  image: ee.Image.cat([ndviJan, ndviFeb, ndviMar, ndviDiffJanMar]).clip(fazenda),
  description: 'S2_NDVI_JAN_FEV_MAR_{farm_name}',
  folder: 'GEE_EXPORT',
  fileNamePrefix: 'S2_NDVI_JAN_FEV_MAR_{farm_name}',
  region: fazenda, scale: 10, maxPixels: 1e13
}});
Export.table.toDrive({{
  collection: statsByTalhao,
  description: 'Talhoes_NDVI_stats_{farm_name}',
  folder: 'GEE_EXPORT',
  fileNamePrefix: 'Talhoes_NDVI_stats_{farm_name}',
  fileFormat: 'CSV'
}});
Export.table.toDrive({{
  collection: pontosRecorte,
  description: 'Talhoes_centroides_{farm_name}',
  folder: 'GEE_EXPORT',
  fileNamePrefix: 'Talhoes_centroides_{farm_name}',
  fileFormat: 'CSV'
}});

print('Talhoes:', talhoes.size());
print('Imagens recentes:', s2.size());
print('Preview stats:', statsByTalhao.limit(5));
"""
    out_path.write_text(js, encoding="utf-8")
    return farm_name, len(features), out_path


def main():
    parser = argparse.ArgumentParser(description="Gera script GEE com talhoes embutidos do fields.mbtiles")
    parser.add_argument("--fields", default="fields.mbtiles", help="Caminho do fields.mbtiles")
    parser.add_argument("--farm-id", type=int, default=3, help="Valor de FAZENDA")
    parser.add_argument("--out", default=None, help="Arquivo JS de saida")
    args = parser.parse_args()

    fields_path = Path(args.fields)
    out_path = Path(args.out) if args.out else Path(f"gee_export_fazenda_{args.farm_id}.js")
    farm_name, n, out_file = build_gee_script(fields_path, args.farm_id, out_path)
    print(f"OK: {out_file} | fazenda={farm_name} | talhoes={n}")


if __name__ == "__main__":
    main()
