# Documento Técnico Operacional
## Telemetria de Colheita, Declividade, Direção, Sobreposição e ROI

Data de consolidação: 15/04/2026  
Projeto: painel analítico em `app.py` + notebooks e artefatos em `results/analises_resultados`

## 1) Objetivo Executivo
Construir uma solução analítica operacional para:
- consolidar telemetria de colheita;
- cruzar consumo, RPM, estado operacional, georreferenciamento e declividade;
- identificar falhas (sem apontamento, paradas críticas, ineficiência);
- medir sobreposição operacional com base na largura da plataforma;
- estimar ganho técnico e financeiro (ROI) com ajustes de direção, sobreposição e operação.

## 2) Escopo Implementado
Foi implementado no `app.py` um conjunto de dashboards e blocos analíticos com:
- ingestão de dados zipados de telemetria (extração + consolidação);
- análises de processo por dia/máquina/estado;
- mapas georreferenciados com talhões;
- cruzamento consumo x declividade;
- análise de direção operacional (bearing/setores);
- estimativa de sobreposição por máquina/talhão/dia;
- cenários de redução de perdas e retorno financeiro;
- bloco de ML com métricas, drivers e hotspots.

Também foram criados notebooks para exploração e validação detalhada.

## 3) Fontes de Dados Utilizadas
- Telemetria consolidada:
  - `data/telemetry/processed/consolidado_telemetria_colheita.csv`
- Rasters:
  - `data/geospatial/declividade_area_talhoes.tif`
  - `data/geospatial/mdt_nasadem_area_talhoes.tif`
- Limites de talhão:
  - `data/geospatial/fields.mbtiles`
- Exportações auxiliares já existentes no projeto:
  - `DECISION_*` (quando aplicável ao painel)

## 4) Preparação de Dados (ETL)
### 4.1 Extração dos ZIPs
Arquivos `15-04-2026_*.zip` foram extraídos e consolidados em uma base única.

### 4.2 Normalização
- Conversão de tipos numéricos (`vl_*`, coordenadas, etc.).
- Conversão temporal de `dt_hr_local_inicial`.
- Padronização de estado operacional:
  - `E -> Efetivo`
  - `P -> Parada`
  - `F -> Parada` (compatibilidade)
  - `M -> Manobra`
  - `D -> Deslocamento`
  - demais -> `Outros`

### 4.3 Regras de Qualidade
Filtros aplicados em diferentes análises:
- coordenadas válidas;
- duração de evento > 0 e limite superior plausível;
- consumo instantâneo em faixa plausível;
- para direção: distância mínima por segmento e velocidade implícita máxima.

## 5) Dashboards e Blocos no App
## 5.1 Aba `Telemetria Colheita`
- Timeline operacional por máquina.
- Sincronismo de fim de turno (`FIM DE EXPEDIENTE`).
- Paradas iguais em janelas de tempo iguais.
- Heatmap hora x dia para paradas.
- Pareto de perdas.
- Small multiples com leitura diária.

## 5.2 Aba `Dashboard Operacional PRO`
Bloco executivo implementado com:
- filtros globais (período, máquinas, estados, preço do diesel);
- KPIs: horas, litros estimados, L/h, L/ha, sem apontamento;
- consumo por faixa de declividade;
- mapas georreferenciados;
- direção operacional com eficiência;
- sobreposição operacional com polígonos;
- cenários de viabilidade e ROI;
- explicação metodológica e fórmulas;
- integração de resultados de ML offline.

## 6) Análises Geoespaciais Implementadas
## 6.1 Consumo x Declividade
Declividade amostrada por ponto no raster `declividade_area_talhoes.tif`.

Faixas:
- `0-3%`
- `3-8%`
- `8-20%`
- `20-45%`
- `>45%`

Métricas:
- horas por faixa;
- litros por faixa;
- `L/h`;
- delta percentual versus faixa base `0-3%`.

## 6.2 Join com Talhões
Spatial join dos pontos com `fields.mbtiles` para obter:
- talhão (`DESC_TALHA`/label),
- fazenda/zona (quando disponível).

## 6.3 Mapa de Faixas + Rastros
Configuração final conforme solicitação:
- rastros e polígonos apenas em `Efetivo`;
- apenas dentro de talhões (sem `SEM_TALHAO`);
- zoom habilitado diretamente no mapa.

## 7) Direção Operacional
## 7.1 Cálculo de Rumo
Bearing calculado com coordenadas inicial/final dos eventos:
- transformação trigonométrica para azimute `[0, 360)`.
- setores de 45°: `N`, `NE`, `E`, `SE`, `S`, `SW`, `W`, `NW`.

## 7.2 Métricas por Direção
- `L/h`
- `L/km`
- `L/ha` (quando `vl_hectares_hora` disponível)

## 7.3 Cenário de ROI por Direção
Benchmark direcional com quartil de melhor desempenho:
- diferença de consumo por setor versus benchmark;
- litros potenciais;
- retorno em R$ via `preço_diesel`.

## 8) Sobreposição Operacional (núcleo solicitado)
## 8.1 Modelo Geométrico
GPS tratado como linha central da máquina.  
Plataforma simulada por buffer de meia largura:
- `buffer = largura_implemento / 2`.

Dois níveis foram implementados:
1. Cobertura agregada por máquina (polígono total por dia/talhão).
2. Faixas/passadas segmentadas (swaths) para visual próximo do sistema de referência.

## 8.2 Índices
- Área teórica (distância x largura).
- Área única coberta (união geométrica).
- Área sobreposta (diferença).
- Taxa de sobreposição (%).

## 8.3 Mapa Final de Sobreposição (como solicitado)
Recorte por:
- dia,
- talhão,
- estado `Efetivo`,
- somente pontos dentro do talhão.

Camadas:
- limite do talhão,
- polígonos das passadas,
- polígono de sobreposição destacado,
- pontos GPS centrais (opcional visual).

## 8.4 Cenário de Ganho em Hectares
Para máquinas que trabalharam no dia/talhão:
- define-se meta de sobreposição (slider).
- ganho potencial:
  - `ganho_ha = sobreposição_atual_ha - sobreposição_meta_ha` (clipped em 0).

## 9) “Faixinhas / Meia Plataforma” e RPM
Foi implementado um proxy operacional para avaliar operação parcial:
- `ha_h_teorico = velocidade * largura / 10`
- `indice_largura_efetiva = vl_hectares_hora / ha_h_teorico`
- faixa inferior (P25) tratada como proxy de operação parcial.

Análises:
- comparação de RPM mediano entre “faixinha (proxy)” vs “faixa cheia (proxy)”;
- consumo, velocidade e largura efetiva;
- scatter para inspeção técnica.

Observação técnica:
- Em teoria, operação parcial tende a reduzir carga e pode reduzir RPM.
- Na prática, isso depende de estratégia de controle da máquina (automatismos, setpoints, perdas).
- Portanto foi tratado como hipótese mensurável, não premissa fixa.

## 10) Machine Learning Implementado
## 10.1 Modelos
Biblioteca: `scikit-learn` (Random Forests).

Modelos treinados:
- Classificação: `target_consumo_alto`
- Classificação: `target_sem_apontamento`
- Classificação: `target_parada_critica`
- Regressão: `vl_consumo_instantaneo`
- Classificação adicional balanceada: `target_ineficiencia_balanceada`

## 10.2 Métricas e Interpretação
Artefatos gerados em `results/analises_resultados/ml`:
- métricas de modelos;
- importância de variáveis;
- hotspots de falha por máquina/hora/talhão.

Nota importante:
- alvos muito desbalanceados podem inflar métricas;
- leitura correta deve combinar métricas + feature importance + hotspots.

## 11) Fórmulas-Chave
- `horas_evento = vl_tempo_segundos / 3600`
- `consumo_l_estimado = vl_consumo_instantaneo * horas_evento`
- `L/h = litros / horas`
- `L/km = litros / distância_km`
- `L/ha = litros / hectares`
- `sobreposição = área_teórica - área_única`
- `sobreposição_% = sobreposição / área_teórica`

## 12) Arquivos Gerados (principais)
## 12.1 Notebooks
- `notebooks/analise_telemetria_colheita.ipynb`
- `notebooks/estudo_geoespacial_consumo_declividade.ipynb`

## 12.2 Resultados
- `results/analises_resultados/consumo_declividade_resumo.csv`
- `results/analises_resultados/consumo_talhao_ranking.csv`
- `results/analises_resultados/consumo_maquina_classe_declividade.csv`
- `results/analises_resultados/potencial_economia_alta_declividade.csv`
- `results/analises_resultados/picos_horarios_falta_caminhao.csv`
- `results/analises_resultados/sem_apontamento_talhao.csv`
- `results/analises_resultados/eventos_operacionais_georef.gpkg`
- `results/analises_resultados/consumo_por_direcao_setor.csv`
- `results/analises_resultados/cenario_ganho_por_direcao.csv`
- `results/analises_resultados/eventos_com_direcao.gpkg`

## 12.3 ML
- `results/analises_resultados/ml/ml_metrics.csv`
- `results/analises_resultados/ml/ml_metric_ineficiencia_balanceada.csv`
- `results/analises_resultados/ml/feature_importance_*.csv`
- `results/analises_resultados/ml/hotspots_falha_*.csv`
- `results/analises_resultados/ml/hotspots_ineficiencia_*.csv`
- `results/analises_resultados/ml/ml_summary.json`

## 13) Limitações e Cuidados
- `vl_consumo_instantaneo` foi tratado como L/h (validar com telemetria de origem).
- Sobreposição é estimada por geometria de rastro + largura (não substitui piloto automático RTK + telemetria de seção).
- Diferenças entre máquinas/modelos precisam de controle por configuração e contexto operacional.
- Resultados de direção e declividade exigem base suficiente por classe para decisões fortes.

## 14) Próximos Passos Recomendados
1. Fixar cadastro oficial de pátio e modelos de máquinas.
2. Adicionar meta operacional por talhão (sobreposição, L/ha, janela de RPM).
3. Criar ranking automático de ações com impacto em ha, litros e R$.
4. Consolidar “pacote executivo” diário (PDF/PowerPoint) com:
- top desvios,
- top oportunidades,
- plano de ação para o próximo turno.

---
Documento gerado com base nas implementações realizadas no projeto até esta data.
