# -*- coding: utf-8 -*-
"""
05_indices_e_amostras.py — Índices espectrais e amostras exploratórias (Etapa 2).

O que faz:
  1. Calcula NDWI (McFeeters, verde/NIR) e NDBI (SWIR/NIR) sobre a reflectância
     já preparada na Etapa 1. O NDVI da Etapa 1 é reutilizado.
  2. Cria as amostras exploratórias de calibração (retângulos alinhados à grade,
     desenhados por interpretação visual da cor verdadeira e da falsa-cor).
  3. Extrai estatísticas zonais de NDVI, NDWI, NDBI, B02 e B04 em cada amostra
     -> documentacao/estatisticas_amostras.csv
  4. Desenha os histogramas dos índices na área, com as faixas das amostras
     -> documentacao/figuras/06_histogramas_indices.png

As amostras servem SOMENTE para definir os limiares. Elas não são usadas
na conferência (os pontos de conferência excluem essas áreas).

Equivalente na interface:
  - Índices: Processamento > GDAL > Diversos raster > Calculadora raster
    (ou Raster > Calculadora Raster), fórmulas abaixo.
  - Amostras: Camada > Criar camada > Nova camada GeoPackage (polígono),
    desenhando retângulos com a ferramenta "Adicionar retângulo".
  - Estatísticas: Processamento > "Estatísticas zonais" (native:zonalstatisticsfb).
  - Histograma: Propriedades da camada raster > Histograma.

Execução:
  "C:\\Program Files\\QGIS 3.40.8\\bin\\python-qgis-ltr.bat" scripts\\05_indices_e_amostras.py
"""
import csv
import os
import sys

import numpy as np
from osgeo import gdal
from qgis.core import (
    QgsApplication, QgsCoordinateReferenceSystem, QgsFeature, QgsField, QgsFields,
    QgsGeometry, QgsRectangle, QgsVectorFileWriter, QgsVectorLayer, QgsWkbTypes,
    QgsCoordinateTransformContext,
)
from qgis.PyQt.QtCore import QVariant

PROJETO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def c(*p):
    return os.path.join(PROJETO, *p)


app = QgsApplication([], False)
app.initQgis()
sys.path.append(os.path.join(QgsApplication.prefixPath(), "python", "plugins"))
import processing  # noqa: E402
from processing.core.Processing import Processing  # noqa: E402

Processing.initialize()

NODATA = -9999
X0, Y0 = 440940, 7371140  # canto superior esquerdo da grade (pixel de 10 m)
REFL = {b: c("processamento", "03_refletancia", "%s_20260417_refletancia.tif" % b)
        for b in ("B02", "B03", "B04", "B08", "B11")}
NDVI = c("processamento", "NDVI_20260417.tif")
NDWI = c("processamento", "NDWI_20260417.tif")
NDBI = c("processamento", "NDBI_20260417.tif")
AMOSTRAS = c("processamento", "amostras_calibracao.gpkg")

# =============================================================================
# 1. Índices (mesmas proteções do NDVI: NoData herdado, denominador > 0)
#    NDWI (McFeeters, 1996) = (B03 - B08) / (B03 + B08)  -> água superficial
#    NDBI (Zha et al., 2003) = (B11 - B08) / (B11 + B08) -> B11 tem 20 m nativos,
#    reamostrada para 10 m (bilinear) na Etapa 1: o detalhe efetivo é de 20 m.
#    Reflectâncias levemente negativas (B08 = -0,0005 em 3 pixels de água,
#    artefato da correção atmosférica) são tratadas como 0, para o índice
#    ficar em [-1, 1]: maximum(A, 0) e maximum(B, 0).
# =============================================================================
for saida, a, b in ((NDWI, "B03", "B08"), (NDBI, "B11", "B08")):
    processing.run("gdal:rastercalculator", {
        "INPUT_A": REFL[a], "BAND_A": 1, "INPUT_B": REFL[b], "BAND_B": 1,
        "FORMULA": ("where((maximum(A, 0) + maximum(B, 0)) > 0, "
                    "(maximum(A, 0) - maximum(B, 0)) / "
                    "(maximum(A, 0) + maximum(B, 0) + ((maximum(A, 0) + maximum(B, 0)) == 0)), %d)" % NODATA),
        "NO_DATA": NODATA, "RTYPE": 5, "OUTPUT": saida})

# =============================================================================
# 2. Amostras exploratórias: (código, classe de referência, descrição,
#    coluna inicial, coluna final, linha inicial, linha final) na grade 300 × 300.
#    Posicionadas por interpretação visual (cor verdadeira + falsa-cor).
# =============================================================================
AMOSTRAS_DEF = [
    ("ARB1", 1, "Floresta contínua na encosta norte", 50, 90, 40, 80),
    ("ARB2", 1, "Floresta contínua na encosta nordeste", 250, 290, 50, 90),
    ("ARB3", 1, "Floresta em encosta sombreada (menor NIR)", 70, 80, 75, 85),
    ("ARB4", 1, "Floresta de dossel mais claro (noroeste)", 10, 25, 25, 40),
    ("ARB5", 1, "Mancha arbórea na planície, entre loteamentos", 147, 160, 175, 198),
    ("ABE1", 2, "Lote aberto com gramíneas (oeste)", 72, 88, 190, 210),
    ("ABE2", 2, "Clareira com gramíneas junto à estrada (oeste)", 92, 101, 146, 153),
    ("ABE3", 2, "Lote gramado (centro-sul)", 120, 125, 212, 217),
    ("URB1", 3, "Ocupação densa junto à orla (centro)", 150, 175, 205, 225),
    ("URB2", 3, "Ocupação no eixo norte", 158, 172, 90, 140),
    ("URB3", 3, "Ocupação densa (leste)", 200, 233, 213, 233),
    ("URB4", 3, "Condomínios com jardins (oeste)", 47, 65, 170, 216),
    ("SOL1", 3, "Lote com solo exposto e gramíneas esparsas", 112, 135, 183, 197),
    ("ARE1", 5, "Areia de praia (trecho oeste)", 10, 85, 240, 242),
    ("ARE2", 5, "Areia de praia (trecho leste, mais larga)", 252, 258, 268, 272),
    ("AGU1", 4, "Oceano", 30, 200, 270, 295),
    ("AGU2", 4, "Zona de arrebentação (espuma)", 20, 60, 246, 252),
]

campos = QgsFields()
for nome, tipo in (("codigo", QVariant.String), ("classe_ref", QVariant.Int),
                   ("descricao", QVariant.String), ("n_pixels", QVariant.Int)):
    campos.append(QgsField(nome, tipo))
opcoes = QgsVectorFileWriter.SaveVectorOptions()
opcoes.driverName = "GPKG"
opcoes.layerName = "amostras_calibracao"
escritor = QgsVectorFileWriter.create(AMOSTRAS, campos, QgsWkbTypes.Polygon,
                                      QgsCoordinateReferenceSystem("EPSG:31983"),
                                      QgsCoordinateTransformContext(), opcoes)
for cod, cls, desc, c0, c1, r0, r1 in AMOSTRAS_DEF:
    f = QgsFeature(campos)
    f.setGeometry(QgsGeometry.fromRect(QgsRectangle(X0 + 10 * c0, Y0 - 10 * r1,
                                                    X0 + 10 * c1, Y0 - 10 * r0)))
    f.setAttributes([cod, cls, desc, (c1 - c0) * (r1 - r0)])
    escritor.addFeature(f)
del escritor

# =============================================================================
# 3. Estatísticas zonais (média, desvio, mínimo, máximo) por amostra
# =============================================================================
camada = QgsVectorLayer(AMOSTRAS, "amostras", "ogr")
rasters = [("ndvi_", NDVI), ("ndwi_", NDWI), ("ndbi_", NDBI),
           ("b02_", REFL["B02"]), ("b04_", REFL["B04"])]
for prefixo, raster in rasters:
    camada = processing.run("native:zonalstatisticsfb", {
        "INPUT": camada, "INPUT_RASTER": raster, "RASTER_BAND": 1,
        "COLUMN_PREFIX": prefixo, "STATISTICS": [2, 4, 5, 6], "OUTPUT": "memory:"})["OUTPUT"]

csv_saida = c("documentacao", "estatisticas_amostras.csv")
nomes = [f.name() for f in camada.fields()]
with open(csv_saida, "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(nomes)
    for f in camada.getFeatures():
        w.writerow([round(v, 4) if isinstance(v, float) else v for v in f.attributes()])

# =============================================================================
# 4. Histogramas dos índices na área de estudo, com a faixa (média ± 2 desvios)
#    de cada grupo de amostras sobreposta
# =============================================================================
import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

cores = {1: "#1e5a2c", 2: "#9ccc65", 3: "#7e7a85", 4: "#4a90d9", 5: "#d8b84a"}
rotulos = {1: "Vegetação arbórea", 2: "Vegetação aberta", 3: "Construído / solo exposto", 4: "Água", 5: "Areia de praia"}
fig, eixos = plt.subplots(3, 1, figsize=(9, 9))
for eixo, (nome, raster) in zip(eixos, (("NDVI", NDVI), ("NDWI", NDWI), ("NDBI", NDBI))):
    ds = gdal.Open(raster)
    a = ds.GetRasterBand(1).ReadAsArray()
    a = a[a != NODATA]
    eixo.hist(a, bins=200, range=(-1, 1), color="#888888")
    eixo.set_title(nome + " — área de estudo (pixels válidos)", fontsize=10)
    eixo.set_ylabel("pixels")
    pref = nome.lower() + "_"
    for f in camada.getFeatures():
        m, s = f[pref + "mean"], f[pref + "stdev"]
        eixo.axvspan(m - 2 * s, m + 2 * s, color=cores[f["classe_ref"]], alpha=0.12)
    for k, r in rotulos.items():
        eixo.plot([], [], color=cores[k], lw=6, alpha=0.4, label=r)
eixos[0].legend(fontsize=8, loc="upper left")
fig.tight_layout()
fig.savefig(c("documentacao", "figuras", "06_histogramas_indices.png"), dpi=110)

print("Índices, amostras e estatísticas gravados.")
# Libera as camadas do QGIS ainda referenciadas pelo Python ANTES de encerrar o QGIS;
# caso contrário, elas são destruídas depois dele e o processo termina com erro.
import gc  # noqa: E402


def _do_qgis(valor):
    if isinstance(valor, (list, tuple)):
        return any(_do_qgis(v) for v in valor)
    return (type(valor).__module__.startswith(("qgis", "osgeo"))  # QGIS e GDAL
            and not isinstance(valor, QgsApplication))


for _nome in [n for n, v in list(globals().items()) if _do_qgis(v)]:
    del globals()[_nome]
gc.collect()
app.exitQgis()
