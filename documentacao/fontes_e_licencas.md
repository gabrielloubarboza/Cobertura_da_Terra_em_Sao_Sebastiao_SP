# Fontes e licenças / Sources and licences

| Material | Direito aplicável |
|---|---|
| Código original: `scripts/*.py` | [MIT](../LICENSE), © 2026 Gabriel Barboza Lourenço |
| Relatório (PDF), mapas, figuras, gráfico, READMEs, documentação e registros da conferência | **Sem licença geral de reutilização**, © 2026 Gabriel Barboza Lourenço. A publicação não concede automaticamente permissão para reutilizar. Os dados de terceiros contidos neles mantêm as próprias condições (abaixo) |
| Dados de terceiros e derivados | Condições de cada fonte (tabela abaixo); nunca MIT |
| Fontes tipográficas | Não distribuídas |

## Fontes de dados

| Fonte | Condições identificadas | No repositório |
|---|---|---|
| **Copernicus Sentinel-2 L2A** (ESA / Comissão Europeia), cena `S2A_MSIL2A_20260417T131301_N0512_R138_T23KMP_20260417T224715`. Obtida pelo Copernicus Data Space e pelo espelho Earth Search / AWS (Element 84), cuja licença declarada remete ao *Sentinel Data Legal Notice* | Acesso livre, completo e aberto ([Regulamento Delegado (UE) nº 1159/2013](https://eur-lex.europa.eu/eli/reg_del/2013/1159/oj); [Sentinel Data Legal Notice](https://sentinel.esa.int/documents/247904/690755/Sentinel_Data_Legal_Notice)). Uso e redistribuição permitidos, com a menção **"Contém dados Copernicus Sentinel modificados [2026]"** | **Não:** bandas originais (o script `01` baixa a janela usada). **Sim:** derivados no recorte de 3 × 3 km, com a menção acima: pilha de reflectância, NDVI/NDWI/NDBI, SCL recortada, máscara, classificação, GeoPackage e figuras |
| **IBGE** — Biomas e Sistema Costeiro-Marinho do Brasil, 1:250 000 (2025); Malha Municipal 2024 (SP); Malha Municipal 2020 (SP), usada só no mapa de localização e referenciada pelo projeto QGIS em `dados/externo/` | Dados públicos; reutilização com citação da fonte | **Sim:** recortes derivados (`dados/contexto/municipio_*.gpkg`, `bioma_*.gpkg`, `sp_estado_*.gpkg`). **Não:** ZIPs originais (o script `01` baixa os de 2024 e 2025) e a Malha Municipal 2020 (download indicado no README) |
| **OpenStreetMap** — `natural=coastline` (extração Overpass com base de 31/05/2026) | [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/); atribuição "© colaboradores do OpenStreetMap"; bases derivadas distribuídas sob ODbL | **Sim, sob ODbL 1.0 (não MIT):** `dados/contexto/osm_original/osm_coastline_overpass.json` e `dados/contexto/linha_costa_osm.gpkg`, usados só para conferir o limite terra-mar |
| **Google Satellite** (camada XYZ do Google no QGIS), imagem de fundo dos mapas de localização | Termos de serviço do Google Maps/Google Earth; atribuição "© Google". O uso em publicação deve seguir as diretrizes de permissão do Google | **Sim, como fundo de figuras:** `resultados/figuras/fig_localizacao.png`, encarte de `mapa_classificacao.png` e relatório PDF. O projeto QGIS só referencia o endereço da camada XYZ; nenhum bloco de imagem do Google é distribuído separadamente |

## Atribuição sugerida

> Contém dados Copernicus Sentinel modificados [2026]. IBGE — Biomas e Sistema Costeiro-Marinho do
> Brasil (2025); malhas municipais 2024 e 2020. © colaboradores do OpenStreetMap (ODbL). Imagem de fundo dos
> mapas de localização: Google Satellite (© Google). Processamento e
> análise: Gabriel Barboza Lourenço (2026).

## Conferência dos pontos

Conferência interna exploratória de 80 pontos, realizada por interpretação assistida por IA (Claude) sobre a própria cena Sentinel-2, sem referência independente ou validação de campo. Os registros estão em `documentacao/conferencia/rodada2/`. Não houve verificação humana independente.
