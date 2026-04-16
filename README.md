# Plataforma de Decisao Agro (Terreno + Operacao + Satelite + Clima)

Este projeto integra dados de terreno, operacao de maquinas, talhoes e imagens de satelite para apoiar decisao tecnica em:

- carga operacional por talhao,
- risco de escoamento,
- vigor vegetativo (NDVI e derivados),
- priorizacao de manejo e ROI operacional.

## Estrutura do repositorio

- `app.py` -> painel principal Streamlit
- `data/geospatial/` -> rasters e limites (`.tif`, `.mbtiles`)
- `data/telemetry/raw/` -> telemetria bruta
- `data/telemetry/processed/` -> telemetria consolidada
- `data/gee/` -> exportacoes `DECISION_*`
- `scripts/gee/` -> scripts GEE e gerador
- `notebooks/` -> notebooks de estudo
- `results/analises_resultados/` -> resultados de analises e ML
- `docs/` -> documentacao tecnica

## Entradas locais esperadas

Obrigatorias:
- `data/geospatial/mdt_nasadem_area_talhoes.tif`
- `data/geospatial/declividade_area_talhoes.tif`
- `data/geospatial/diferenca_elevacao_media_area_talhoes.tif`
- `data/geospatial/fields.mbtiles`
- `data/telemetry/raw/13-04-2026_17_26.csv` (fallback)
- `data/telemetry/processed/consolidado_telemetria_colheita.csv` (preferencial)

Opcionais:
- `data/geospatial/ndvi_recente.tif`
- `data/geospatial/imagem_recente.tif`

## Como executar

```bash
streamlit run app.py
```

## Pipeline GEE

Arquivos:
- `scripts/gee/gee_export_san_jorge.js`
- `scripts/gee/generate_gee_script.py`

O app detecta automaticamente os CSVs `DECISION_*` em `data/gee/`.

## Dashboards

Principais abas:
- `Painel Especialista`
- `Telemetria Colheita`
- `Dashboard Operacional PRO`

Destaques do painel PRO:
- consumo x declividade,
- direcao operacional e eficiencia,
- sobreposicao com poligonos da plataforma por talhao/dia,
- cenario de ganho em hectares e R$,
- diagnostico de ML (metricas, drivers e hotspots).

## Documentacao detalhada

- `docs/DOCUMENTO_TECNICO_OPERACIONAL.md`
