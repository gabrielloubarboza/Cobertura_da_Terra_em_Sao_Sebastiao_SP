# -*- coding: utf-8 -*-
"""
10_atualizar_projeto_qgis.py — Atualiza o projeto QGIS com as camadas da Etapa 2.

Abre qgis/sao_sebastiao_cobertura.qgz (o mesmo projeto criado pelo script 03, sem
versões paralelas), preserva os grupos da Etapa 1 e:
  - acrescenta NDWI e NDBI ao grupo de índices;
  - cria o grupo "0. Classificação exploratória (Etapa 2)" no topo;
  - acrescenta a linha de costa OSM ao grupo de contexto.
Os layouts e os mapas finais são feitos pelo script 12.
Pode ser executado de novo: remove antes o que ele mesmo criou.

Equivalente na interface: arrastar as camadas para o painel Camadas e ajustar a
Simbologia (Valores paletados / Categorizado / Banda simples falsa-cor).

Execução:
  "C:\\Program Files\\QGIS 3.40.8\\bin\\python-qgis-ltr.bat" scripts\\10_atualizar_projeto_qgis.py
"""
import os

from qgis.PyQt.QtGui import QColor
from qgis.core import (
    QgsApplication, QgsCategorizedSymbolRenderer, QgsColorRampShader, QgsFillSymbol,
    QgsLineSymbol, QgsMarkerSymbol, QgsPalLayerSettings, QgsPalettedRasterRenderer, QgsProject,
    QgsRasterLayer, QgsRasterShader, QgsRendererCategory, QgsSingleBandPseudoColorRenderer,
    QgsSingleSymbolRenderer, QgsTextFormat, QgsVectorLayer, QgsVectorLayerSimpleLabeling,
)

PROJETO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARQ = os.path.join(PROJETO, "qgis", "sao_sebastiao_cobertura.qgz")
GRUPO = "0. Classificação exploratória (Etapa 2)"
TITULO = ("Classificação Exploratória da Cobertura da Terra em Maresias — São Sebastião/SP "
          "(Sentinel-2, 17/04/2026)")

# Paleta conferida por simulação de daltonismo (protan, deutan, tritan): menor
# distância entre classes = 10,4 (OKLab × 100). Ver documentacao/METODO_CLASSIFICACAO.md.
CLASSES = [(1, "#1e5a2c", "1 Vegetação arbórea"), (2, "#9ccc65", "2 Vegetação baixa ou aberta"),
           (3, "#7e7a85", "3 Superfícies construídas e outras não vegetadas"),
           (4, "#4a90d9", "4 Água"), (5, "#f6e8b1", "5 Areia de praia"),
           (6, "#e86f3a", "6 Transição / mistura (incerta)"),
           (9, "#000000", "9 Pixel inválido (máscara SCL)")]


def c(*p):
    return os.path.join(PROJETO, *p)


app = QgsApplication([], False)
app.initQgis()
projeto = QgsProject.instance()
assert projeto.read(ARQ), "não foi possível abrir o projeto"
projeto.setTitle(TITULO)
raiz = projeto.layerTreeRoot()

# --- Remove o que este script criou numa execução anterior ------------------
for nome in ("NDWI (B03 − B08) / (B03 + B08)", "NDBI (B11 − B08) / (B11 + B08)",
             "Linha de costa OSM (conferência)"):
    for lyr in projeto.mapLayersByName(nome):
        projeto.removeMapLayer(lyr.id())
antigo = raiz.findGroup(GRUPO)
if antigo:
    for no in antigo.findLayers():
        projeto.removeMapLayer(no.layerId())
    raiz.removeChildNode(antigo)

# --- Índices NDWI e NDBI (grupo 3) ------------------------------------------
g_ind = raiz.findGroup("3. Índice espectral") or raiz.findGroup("3. Índices espectrais")
g_ind.setName("3. Índices espectrais")


def pseudocor(caminho, nome, paradas):
    camada = QgsRasterLayer(caminho, nome)
    rampa = QgsColorRampShader(paradas[0][0], paradas[-1][0], None, QgsColorRampShader.Interpolated)
    rampa.setColorRampItemList([QgsColorRampShader.ColorRampItem(v, QColor(cor), rot)
                                for v, cor, rot in paradas])
    shader = QgsRasterShader()
    shader.setRasterShaderFunction(rampa)
    camada.setRenderer(QgsSingleBandPseudoColorRenderer(camada.dataProvider(), 1, shader))
    return camada


ndwi = pseudocor(c("processamento", "NDWI_20260417.tif"), "NDWI (B03 − B08) / (B03 + B08)",
                 [(-1, "#7f5a2b", "−1"), (0, "#f2f2f2", "0"), (0.2, "#9ecae1", "0,2 (limiar água)"),
                  (1, "#08306b", "1")])
ndbi = pseudocor(c("processamento", "NDBI_20260417.tif"), "NDBI (B11 − B08) / (B11 + B08)",
                 [(-0.6, "#2166ac", "−0,6"), (-0.2, "#d1e5f0", "−0,2 (limiar arbórea)"),
                  (0, "#f7f7f7", "0"), (0.4, "#b2182b", "0,4")])
for camada in (ndwi, ndbi):
    projeto.addMapLayer(camada, False)
    no = g_ind.addLayer(camada)
    no.setItemVisibilityChecked(False)

# --- Linha de costa OSM (grupo 5) -------------------------------------------
osm = QgsVectorLayer(c("dados", "contexto", "linha_costa_osm.gpkg"), "Linha de costa OSM (conferência)", "ogr")
osm.setRenderer(QgsSingleSymbolRenderer(QgsLineSymbol.createSimple(
    {"line_color": "0,190,255,255", "line_width": "0.5", "line_style": "dash"})))
projeto.addMapLayer(osm, False)
g_ctx = raiz.findGroup("5. Contexto oficial (IBGE)") or raiz.findGroup("5. Contexto (IBGE e OSM)")
g_ctx.setName("5. Contexto (IBGE e OSM)")
g_ctx.insertLayer(0, osm).setItemVisibilityChecked(False)

# --- Grupo da Etapa 2 --------------------------------------------------------
cobertura = QgsRasterLayer(c("resultados", "cobertura_classificada_20260417.tif"),
                           "Cobertura da terra — classificação exploratória (17/04/2026)")
cobertura.setRenderer(QgsPalettedRasterRenderer(cobertura.dataProvider(), 1, [
    QgsPalettedRasterRenderer.Class(v, QColor(cor), rot) for v, cor, rot in CLASSES]))

gpkg = c("resultados", "sao_sebastiao_cobertura.gpkg")
pontos = QgsVectorLayer(gpkg + "|layername=pontos_conferencia", "Pontos de conferência (rodada 2)", "ogr")
categorias = []
for valor, cor, forma, rotulo in (("sim", "255,255,255,255", "circle", "Concordante"),
                                   ("não", "0,0,0,255", "triangle", "Discordante")):
    simbolo = QgsMarkerSymbol.createSimple({"name": forma, "color": cor, "outline_color": "0,0,0,255",
                                            "size": "2.6", "outline_width": "0.4"})
    categorias.append(QgsRendererCategory(valor, simbolo, rotulo))
pontos.setRenderer(QgsCategorizedSymbolRenderer("concordancia", categorias))
rotulo = QgsPalLayerSettings()
rotulo.fieldName = "id"
formato = QgsTextFormat()
formato.setSize(7)
rotulo.setFormat(formato)
pontos.setLabeling(QgsVectorLayerSimpleLabeling(rotulo))
pontos.setLabelsEnabled(True)

amostras = QgsVectorLayer(gpkg + "|layername=amostras_calibracao", "Amostras de calibração (limiares)", "ogr")
amostras.setRenderer(QgsSingleSymbolRenderer(QgsFillSymbol.createSimple(
    {"color": "0,0,0,0", "outline_color": "0,255,255,255", "outline_width": "0.5"})))
rot_am = QgsPalLayerSettings()
rot_am.fieldName = "codigo"
rot_am.setFormat(formato)
amostras.setLabeling(QgsVectorLayerSimpleLabeling(rot_am))
amostras.setLabelsEnabled(True)

poligonos = QgsVectorLayer(gpkg + "|layername=cobertura_poligonos", "Cobertura — polígonos por classe", "ogr")
poligonos.setRenderer(QgsCategorizedSymbolRenderer("classe", [
    QgsRendererCategory(v, QgsFillSymbol.createSimple({"color": cor, "outline_style": "no"}), rot)
    for v, cor, rot in CLASSES]))

for camada in (cobertura, pontos, amostras, poligonos):
    assert camada.isValid(), camada.name()
    projeto.addMapLayer(camada, False)
grupo = raiz.insertGroup(0, GRUPO)
for camada, visivel in ((pontos, False), (amostras, False), (cobertura, True), (poligonos, False)):
    grupo.addLayer(camada).setItemVisibilityChecked(visivel)

# Ao abrir: classificação visível, composições da Etapa 1 desligadas
for nome in ("Cor verdadeira (R=B04, G=B03, B=B02)",):
    for lyr in projeto.mapLayersByName(nome):
        raiz.findLayer(lyr.id()).setItemVisibilityChecked(False)

projeto.writeEntryBool("Paths", "/Absolute", False)
assert projeto.write(ARQ), "falha ao salvar"
print("Projeto atualizado:", ARQ)
app.exitQgis()
