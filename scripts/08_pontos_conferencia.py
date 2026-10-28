# -*- coding: utf-8 -*-
"""
08_pontos_conferencia.py — Amostra de pontos para a conferência visual (Etapa 2).

Rodadas:
  - Rodada 1 (semente 2026, diagnóstica): revelou o efeito de borda do NDBI
    (bordas de floresta mapeadas como vegetação aberta). A regra R2 foi corrigida
    e, por isso, esses pontos deixaram de ser conferência independente. Arquivos
    em processamento/06_conferencia/rodada1_diagnostico/ e
    documentacao/conferencia/rodada1_diagnostico/.
  - Rodada 2 (semente 2027, final): novo sorteio sobre a classificação corrigida,
    excluindo também um raio de 15 m em torno dos pontos da rodada 1. Os estratos
    são ordenados por classe antes do sorteio, o que torna o resultado repetível.
    Uma prévia da rodada 2, sorteada antes dessa ordenação, não pôde ser repetida
    e ficou só como registro (rodada2_previa/).
Desenho amostral: aleatório ESTRATIFICADO pela classe mapeada, semente fixa.
  Classe 1 arbórea: 20 | 2 aberta: 10 | 3 não vegetada: 18 | 4 água: 8 |
  5 areia: 8 | 6 transição: 16  -> total 80 pontos.
  As classes pequenas recebem mais pontos que sua área (para poderem ser avaliadas);
  a classe de transição recebe 16 pontos porque concentra a incerteza.
Regras:
  - pontos dentro dos polígonos da própria classe (dissolvidos), fora das
    amostras de calibração (não reutilizar a calibração como conferência);
  - distância mínima de 20 m entre pontos da mesma classe;
  - pixels inválidos (9) não são amostrados;
  - a numeração final é embaralhada (semente fixa) para que a interpretação
    seja feita sem saber a classe mapeada ("às cegas").
Saídas:
  processamento/06_conferencia/pontos_conferencia_rodada2.gpkg
  documentacao/conferencia/rodada2/fichas_pontos_NN.png  (cor verdadeira | falsa-cor,
  janela de 150 × 150 m, pixel central destacado, sem a classe mapeada)

Equivalente na interface:
  Poligonizar > Dissolver (campo classe) > Diferença (com as amostras de calibração) >
  Vetor > Ferramentas de pesquisa > "Pontos aleatórios dentro de polígonos"
  (número de pontos definido por expressão; distância mínima 20 m; semente 2026) >
  "Amostrar valores raster" > Calculadora de campo ($x, $y).

Execução:
  "C:\\Program Files\\QGIS 3.40.8\\bin\\python-qgis-ltr.bat" scripts\\08_pontos_conferencia.py
"""
import os
import random
import sys

import numpy as np
from osgeo import gdal
from qgis.core import (
    QgsApplication, QgsFeature, QgsField, QgsProperty, QgsVectorFileWriter, QgsVectorLayer,
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

SEMENTE = 2027
RODADA1 = c("processamento", "06_conferencia", "rodada1_diagnostico", "pontos_conferencia_sorteados.gpkg")
ALOCACAO = {1: 20, 2: 10, 3: 18, 4: 8, 5: 8, 6: 16}
FINAL = c("resultados", "cobertura_classificada_20260417.tif")
AMOSTRAS = c("processamento", "amostras_calibracao.gpkg")
D = c("processamento", "06_conferencia")
FICHAS = c("documentacao", "conferencia", "rodada2")
SAIDA = os.path.join(D, "pontos_conferencia_rodada2.gpkg")
os.makedirs(D, exist_ok=True)
os.makedirs(FICHAS, exist_ok=True)

# 1. Polígonos por classe, sem as áreas de calibração ---------------------------
poligonos = processing.run("gdal:polygonize", {
    "INPUT": FINAL, "BAND": 1, "FIELD": "classe", "EIGHT_CONNECTEDNESS": False,
    "OUTPUT": "TEMPORARY_OUTPUT"})["OUTPUT"]
validos = processing.run("native:extractbyexpression", {
    "INPUT": poligonos, "EXPRESSION": '"classe" IN (1, 2, 3, 4, 5, 6)',
    "OUTPUT": "memory:"})["OUTPUT"]
por_classe = processing.run("native:dissolve", {
    "INPUT": validos, "FIELD": ["classe"], "OUTPUT": "memory:"})["OUTPUT"]
estratos = processing.run("native:difference", {
    "INPUT": por_classe, "OVERLAY": AMOSTRAS, "OUTPUT": "memory:"})["OUTPUT"]
# Interface: Buffer de 15 m nos pontos da rodada 1 e nova Diferença.
entorno_rodada1 = processing.run("native:buffer", {
    "INPUT": RODADA1, "DISTANCE": 15, "SEGMENTS": 8, "END_CAP_STYLE": 0, "JOIN_STYLE": 0,
    "MITER_LIMIT": 2, "DISSOLVE": True, "OUTPUT": "memory:"})["OUTPUT"]
estratos = processing.run("native:difference", {
    "INPUT": estratos, "OVERLAY": entorno_rodada1, "OUTPUT": "memory:"})["OUTPUT"]

# Ordena os estratos por classe. Sem isso, a ordem das feições após "Dissolver" pode
# variar entre execuções e, com ela, os pontos sorteados (mesmo com semente fixa).
# Interface: Processamento > "Ordenar por expressão" ("classe", crescente).
estratos = processing.run("native:orderbyexpression", {
    "INPUT": estratos, "EXPRESSION": '"classe"', "ASCENDING": True, "NULLS_FIRST": False,
    "OUTPUT": "memory:"})["OUTPUT"]

# 2. Sorteio estratificado -------------------------------------------------------
expressao = "CASE " + " ".join("WHEN \"classe\" = %d THEN %d" % (k, n) for k, n in ALOCACAO.items()) + " END"
pontos = processing.run("native:randompointsinpolygons", {
    "INPUT": estratos,
    "POINTS_NUMBER": QgsProperty.fromExpression(expressao),
    "MIN_DISTANCE": 20, "MIN_DISTANCE_GLOBAL": 0, "MAX_TRIES_PER_POINT": 50,
    "SEED": SEMENTE, "INCLUDE_POLYGON_ATTRIBUTES": True, "OUTPUT": "memory:"})["OUTPUT"]

# 3. Classe do raster no ponto (confirmação independente do estrato) -------------
pontos = processing.run("native:rastersampling", {
    "INPUT": pontos, "RASTERCOPY": FINAL, "COLUMN_PREFIX": "raster_", "OUTPUT": "memory:"})["OUTPUT"]

# 4. Numeração embaralhada e coordenadas -----------------------------------------
feicoes = list(pontos.getFeatures())
feicoes.sort(key=lambda f: (f["classe"], f.geometry().asPoint().x(), f.geometry().asPoint().y()))
random.Random(SEMENTE).shuffle(feicoes)

campos = [QgsField("id", QVariant.Int), QgsField("x_31983", QVariant.Double),
          QgsField("y_31983", QVariant.Double), QgsField("estrato", QVariant.Int),
          QgsField("classe_mapeada", QVariant.Int)]
camada = QgsVectorLayer("Point?crs=EPSG:31983", "pontos_conferencia", "memory")
camada.dataProvider().addAttributes(campos)
camada.updateFields()
registros = []
for i, f in enumerate(feicoes, start=1):
    p = f.geometry().asPoint()
    nova = QgsFeature(camada.fields())
    nova.setGeometry(f.geometry())
    nova.setAttributes([i, round(p.x(), 2), round(p.y(), 2), int(f["classe"]), int(f["raster_1"])])
    camada.dataProvider().addFeature(nova)
    registros.append((i, p.x(), p.y()))
opcoes = QgsVectorFileWriter.SaveVectorOptions()
opcoes.driverName = "GPKG"
QgsVectorFileWriter.writeAsVectorFormatV3(camada, SAIDA, QgsCoordinateTransformContext(), opcoes)
print("Pontos sorteados:", len(registros), {k: sum(1 for f in feicoes if f["classe"] == k) for k in ALOCACAO})

# 5. Fichas para interpretação visual (sem a classe mapeada) ---------------------
import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

ds = gdal.Open(c("processamento", "S2A_20260417_refletancia_B02_B03_B04_B08_B11.tif"))
gt = ds.GetGeoTransform()
pilha = ds.ReadAsArray().astype(float)
pilha[pilha == -9999] = np.nan


def realce(rgb):
    lo = np.nanpercentile(rgb, 2, axis=(0, 1))
    hi = np.nanpercentile(rgb, 98, axis=(0, 1))
    return np.nan_to_num(np.clip((rgb - lo) / (hi - lo), 0, 1), nan=1.0)


cor_verdadeira = realce(np.dstack([pilha[2], pilha[1], pilha[0]]))
falsa_cor = realce(np.dstack([pilha[3], pilha[2], pilha[1]]))
MEIA = 7  # janela de 15 × 15 pixels (150 m)
POR_FICHA = 10
for n_ficha in range(0, len(registros), POR_FICHA):
    grupo = registros[n_ficha:n_ficha + POR_FICHA]
    fig, eixos = plt.subplots(5, 4, figsize=(12, 15.6))
    for eixo in eixos.flat:
        eixo.axis("off")
    for k, (pid, x, y) in enumerate(grupo):
        col, lin = int((x - gt[0]) / gt[1]), int((y - gt[3]) / gt[5])
        for j, img in enumerate((cor_verdadeira, falsa_cor)):
            eixo = eixos[k // 2, (k % 2) * 2 + j]
            janela = np.ones((2 * MEIA + 1, 2 * MEIA + 1, 3))
            r0, c0 = lin - MEIA, col - MEIA
            rr0, cc0 = max(r0, 0), max(c0, 0)
            rr1, cc1 = min(lin + MEIA + 1, img.shape[0]), min(col + MEIA + 1, img.shape[1])
            janela[rr0 - r0:rr1 - r0, cc0 - c0:cc1 - c0] = img[rr0:rr1, cc0:cc1]
            eixo.imshow(janela, interpolation="nearest")
            eixo.add_patch(Rectangle((MEIA - 0.5, MEIA - 0.5), 1, 1, fill=False, ec="yellow", lw=1.6))
            eixo.add_patch(Rectangle((MEIA - 1.5, MEIA - 1.5), 3, 3, fill=False, ec="yellow", lw=0.6, ls=":"))
            eixo.set_title("P%02d %s" % (pid, "cor verdadeira" if j == 0 else "falsa-cor"), fontsize=10)
    fig.suptitle("Conferência visual — Sentinel-2 17/04/2026 — janela 150 m; quadrado = pixel de 10 m do ponto",
                 fontsize=10)
    fig.tight_layout()
    fig.savefig(os.path.join(FICHAS, "fichas_pontos_%02d.png" % (n_ficha // POR_FICHA + 1)), dpi=90)
    plt.close(fig)
print("Fichas gravadas em", FICHAS)
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
