# Land Cover Classification in Maresias — São Sebastião, Brazil

**[Versão em português](README.pt.md)** · **Portfolio page:** https://gabrielloubarboza.github.io/en/projects/maresias/

Exploratory classification of a single Sentinel-2 scene with QGIS, spectral indices and explicit
rules, over a 9 km² window of Maresias on São Paulo's North Coast (Atlantic Forest biome).

Author: **Gabriel Barboza Lourenço** · QGIS 3.40 LTR / PyQGIS · GDAL · Sentinel-2 L2A · 2026

<p align="center"><img src="resultados/figuras/mapa_classificacao.png" width="860"
alt="Exploratory land cover map of Maresias (map text in Portuguese)"></p>

> **Exploratory classification.** The map shows land cover observable on a single date
> (17 April 2026), derived from spectral and contextual rules. It is not an official land use map,
> it was not validated in the field, it has no independent accuracy assessment and it does not
> identify native vegetation.

**Final report (PDF, 5 A4 landscape pages, in Portuguese):**
[`resultados/relatorio_classificacao_cobertura_maresias.pdf`](resultados/relatorio_classificacao_cobertura_maresias.pdf)

## 1. Question and objective

> To what extent can a Sentinel-2 satellite image identify and distinguish different types of land
> cover in Maresias, and which areas show the greatest classification uncertainty?

The objective is to test which basic patterns — forest, settlement, beach and water — a single
scene can separate reliably, using spectral bands, indices and explicit rules in QGIS, and to
document where the separation stops being reliable. This is not a biome classification: the
Atlantic Forest is the environmental context of the study area.

## 2. Study area

- **Location:** Maresias, São Sebastião, São Paulo state. The window covers the forested slopes of
  the Serra do Mar, the settled coastal plain, the beach and the sea.
- **Window:** a 3 × 3 km square (9.00 km²) in SIRGAS 2000 / UTM 23S (EPSG:31983), centred at
  45.5650° W / 23.7834° S. Polygon in `dados/area_estudo/area_estudo_maresias.gpkg`.
- **Context:** Atlantic Forest biome (IBGE, 2025).

## 3. Sentinel-2 imagery

| Item | Value |
|---|---|
| Product | Copernicus Sentinel-2A MSI, Level-2A (surface reflectance) |
| Scene | `S2A_MSIL2A_20260417T131301_N0512_R138_T23KMP_20260417T224715` |
| Date | 17 April 2026, 13:13 UTC |
| Bands | B02, B03, B04, B08 (10 m), B11 (20 m, resampled to 10 m) and SCL |
| Selection | lowest cloud fraction measured with the SCL over the window itself, among 32 scenes |
| Access | product checked in the Copernicus Data Space; a 5 × 5 km window read from the public COG mirror (Earth Search / AWS) |

## 4. Method in brief

The pipeline runs in **PyQGIS** (`scripts/00`–`12`) and uses only QGIS/GDAL Processing tools. Each
step has a documented equivalent in the QGIS interface (code comments are in Portuguese).

1. **Preparation:** 10 m grid, cloud and shadow mask from the SCL, and reflectance computed as
   (DN − 1000) / 10000.
2. **Composites:** true colour (B04/B03/B02) and near-infrared false colour (B08/B04/B03) for visual
   reading.
3. **Spectral indices:** NDVI, NDWI and NDBI (section 5).
4. **Rule-based classification:** thresholds set from 17 exploratory samples and the area's
   histograms, applied in order. No classifier was trained; this is not a supervised classification.
5. **Contextual rules:** sand only where the patch touches water; open vegetation only in compact
   patches; small canopy gaps returned to tree cover. Ambiguous pixels are kept as transition/mixed.
6. **Visual review:** comparison with true colour, false colour and the indices. Systematic errors
   were fixed by rules, not by hand.
7. **Internal check:** 80 random points stratified by class (seed 2027), interpreted by AI (Claude)
   on the same Sentinel-2 scene without seeing the mapped class. It is an internal consistency check:
   there is no independent reference and no field validation, and the result (56 of 80 points
   agreeing) is **not thematic accuracy**. Records in `documentacao/conferencia/rodada2/`.
8. **Quantification:** area per class from the count of 100 m² pixels; the land–sea boundary is
   compared with the OpenStreetMap coastline.

| Rule | Condition | Result |
|---|---|---|
| R0 | invalid SCL mask | 9 invalid pixel |
| R1 | NDWI > 0.20 | 4 water |
| R2 | NDVI ≥ 0.80, or NDVI ≥ 0.75 and NDBI ≤ −0.20 | 1 tree cover |
| R3 | NDVI ≥ 0.55 | candidate for 2 |
| R4 | B02 ≥ 0.15 and NDVI < 0.20 | candidate for 5 |
| R5 | all other pixels | 3 built-up and other non-vegetated surfaces |
| C1 | candidate 5 whose patch touches water | 5 beach sand (otherwise 3) |
| C2 | candidate 2 with a core wider than 20 m and ≥ 0.1 ha | 2 low or open vegetation (otherwise 6 transition/mixed) |
| C3 | class-6 fragment of up to 4 pixels surrounded only by tree cover | 1 tree cover |

Details (in Portuguese) in [`documentacao/METODO_CLASSIFICACAO.md`](documentacao/METODO_CLASSIFICACAO.md)
and [`documentacao/FONTES_E_DECISOES.md`](documentacao/FONTES_E_DECISOES.md).

## 5. Spectral indices

| Index | Formula | Use in the study |
|---|---|---|
| NDVI | (B08 − B04) / (B08 + B04) | vegetation vigour; separates tree cover, open vegetation and non-vegetated surfaces |
| NDWI (McFeeters) | (B03 − B08) / (B03 + B08) | presence of water; defines the sea and the land–sea boundary |
| NDBI | (B11 − B08) / (B11 + B08) | support to confirm tree cover; overlaps built-up areas, soil, sand and water |

## 6. Mapped classes

| Code | Class | What it includes |
|---|---|---|
| 1 | Tree cover | continuous canopy on the slopes and trees on the plain, including backyards; not the same as native forest |
| 2 | Low or open vegetation | lawns, fields and low vegetation in compact patches |
| 3 | Built-up and other non-vegetated surfaces | roofs, roads, bare soil and wet sand; not the same as urban land |
| 4 | Water | sea and water bodies (excluded from the land-area denominator) |
| 5 | Beach sand | dry sand in contact with water |
| 6 | Transition/mixed | mixed pixels at edges and in backyards, kept as uncertain |
| 9 | Invalid pixel | cloud, shadow or no data in the SCL |

## 7. Main results

| Class | km² | % of valid land area |
|---|---:|---:|
| 1 Tree cover | 5.27 | 68.8 |
| 3 Built-up and other non-vegetated surfaces | 1.62 | 21.1 |
| 6 Transition/mixed | 0.56 | 7.3 |
| 5 Beach sand | 0.12 | 1.5 |
| 2 Low or open vegetation | 0.10 | 1.3 |
| **Valid land area (denominator)** | **7.66** | **100.0** |
| 4 Water (excluded from the denominator) | 1.34 | — |
| 9 Invalid pixel (excluded) | < 0.01 | — |

- Tree cover takes up about two thirds of the land area, mostly on the slopes. The class includes
  backyard trees and does not prove native forest.
- Built-up and other non-vegetated surfaces are concentrated on the coastal plain.
- The land–sea boundary is consistent: the edge of the classified water lies 4.9 m (median) from
  the OpenStreetMap coastline, less than one pixel.
- The small classes — low or open vegetation and transition/mixed — are the least reliable.

Full table: `resultados/areas_por_classe.csv`.

## 8. Limitations

- **A single date** and **10 m pixels** (native 20 m for B11): tree crown, roof and soil mix within
  one pixel.
- **Low or open vegetation** is the least reliable class. At 10 m, a lawn and a pixel mixing tree
  crown and roof respond in a similar way.
- **Built-up and other non-vegetated surfaces** form a heterogeneous class.
- **Transition/mixed** is an uncertainty category, not a land use class.
- **Beach sand** depends on contact with water (rule C1); wet sand stayed in class 3.
- **NDBI** overlapped built-up areas, soil, sand and water, so it only separates forest from lawn.
- **No field validation** and **no independent accuracy assessment**: the internal check used the
  image itself as reference.

## 9. Repository structure

```
qgis/          sao_sebastiao_cobertura.qgz (relative paths; 5 layouts)
scripts/       00–12 (PyQGIS)
dados/         study area, clipped IBGE and OSM context, fontes_manifesto.json (URLs + MD5)
processamento/ reflectance stack, NDVI/NDWI/NDBI, SCL and mask (used by the project) and points from
               earlier check rounds
resultados/    cobertura_classificada_20260417.tif (analytical result), sao_sebastiao_cobertura.gpkg,
               areas_por_classe.csv, PDF report and figuras/
documentacao/  method, sources and decisions, sources and licences, sample statistics, check records
               (sheets, interpretations, matrices)
```

The **GeoPackage** [`resultados/sao_sebastiao_cobertura.gpkg`](resultados/sao_sebastiao_cobertura.gpkg)
(EPSG:31983) contains:

- the study area;
- land cover dissolved by class (7 multipolygons with the raster's exact area);
- the 80 check points;
- the diagnostic-round points;
- the calibration samples;
- class, area and metadata tables.

## 10. Reproduction

The repository does **not** include the original Sentinel-2 bands or the IBGE ZIP files.
`scripts/01_obter_dados.py` downloads both from the public sources and checks them against the
manifest. Run the scripts in order from the repository folder with QGIS's `python-qgis-ltr.bat`:
`01` → `02` → `03` → `04` → `05` → `06` → `07` → `08` → `09` → `10` → `12` → `11`. The full
command list is in [`README.pt.md`](README.pt.md#10-reprodução).

- `scripts/00_triagem_cenas.py` optionally repeats the scene selection.
- The interpretation of the points is an input file
  (`documentacao/conferencia/rodada2/interpretacao_visual.csv`); script `08` only creates the sheets.
- The automated tests check technical integrity (grids, masks, rules, areas, geometries, paths and
  repeatability), not accuracy.
- **Final maps:** the figures in `resultados/figuras/` received final layout adjustments in
  `qgis/sao_sebastiao_cobertura.qgz`. Scripts `03`, `10` and `12` rebuild the base project and maps
  and overwrite those files; run them on a copy to keep the published version.
- **External layers in the QGIS project:** the location map uses IBGE's 2020 municipal boundaries
  (neighbouring municipalities), which are not distributed. To display them, extract
  [`SP_Municipios_2020.zip`](https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_municipais/municipio_2020/UFs/SP/SP_Municipios_2020.zip)
  into `dados/externo/SP_Municipios_2020/`. The location maps' background is the Google Satellite
  XYZ layer, loaded over the internet.
- The report was laid out in PowerPoint from the figures and tables in `resultados/`; only the final
  PDF is distributed.
- Some QGIS layout labels use IBM Plex Sans; if it is not installed, QGIS substitutes it.

## 11. Dependencies

- QGIS 3.40 LTR, whose Python provides PyQGIS, GDAL, NumPy, SciPy and Matplotlib;
- internet access for script `01` (Earth Search / AWS and IBGE) and for the Google Satellite layer;
- Windows for the commands in the Portuguese README (the scripts themselves are OS-independent).

## 12. Sources and credits

- **Imagery:** Copernicus Sentinel-2 (ESA / European Commission). Contains modified Copernicus
  Sentinel data [2026].
- **IBGE:** Biomes and Coastal-Marine System of Brazil (2025, 1:250,000); 2024 and 2020 municipal
  boundaries.
- **OpenStreetMap:** coastline used only to check the land–sea boundary, © OpenStreetMap
  contributors (ODbL 1.0).
- **Location maps:** Google Satellite background imagery (© Google).

Terms of use for each source: [`documentacao/fontes_e_licencas.md`](documentacao/fontes_e_licencas.md).

## 13. Licence

- **Original code** (`scripts/*.py`): [MIT](LICENSE), © 2026 Gabriel Barboza Lourenço.
- **Report, maps, figures and texts** (READMEs, documentation, check records): **no general reuse
  licence**, © 2026 Gabriel Barboza Lourenço. Their public availability in this repository does not
  by itself grant permission to reuse them.
- **Third-party data and derivatives** (Copernicus Sentinel, IBGE, OpenStreetMap, Google background
  imagery) keep their own terms and are not covered by the MIT licence; see
  [`documentacao/fontes_e_licencas.md`](documentacao/fontes_e_licencas.md).

## 14. Portfolio

Project page in Gabriel Barboza Lourenço's portfolio:
https://gabrielloubarboza.github.io/en/projects/maresias/
