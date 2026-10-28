# -*- coding: utf-8 -*-
"""
03_criar_projeto_qgis.py — Monta o projeto QGIS da Etapa 1.

Cria qgis/sao_sebastiao_cobertura.qgz com caminhos RELATIVOS,
SRC EPSG:31983, grupos de camadas e simbologias:
  - cor verdadeira (R=B04, G=B03, B=B02) e falsa-cor (R=B08, G=B04, B=B03),
    ambas a partir do mesmo raster empilhado de reflectância;
  - NDVI em rampa de cores;
  - SCL (classificação da cena, cores padrão ESA) e máscara de pixels inválidos;
  - limite da área de estudo, município e bioma (IBGE).

O contraste das composições é apenas de VISUALIZAÇÃO (mínimo/máximo do
renderizador, a partir dos percentis 2 % e 98 % de cada banda). Os valores
de reflectância gravados no arquivo não são alterados.

Equivalente na interface: Propriedades da camada > Simbologia
  ("Multibanda colorida", "Banda simples falsa-cor", "Valores paletados/únicos").

Execução:
  "C:\\Program Files\\QGIS 3.40.8\\bin\\python-qgis-ltr.bat" scripts\\03_criar_projeto_qgis.py
"""
import os

import numpy as np
from osgeo import gdal
from qgis.PyQt.QtGui import QColor
from qgis.core import (
    QgsApplication, QgsColorRampShader, QgsContrastEnhancement, QgsCoordinateReferenceSystem,
    QgsFillSymbol, QgsMultiBandColorRenderer, QgsPalettedRasterRenderer, QgsProject,
    QgsRasterLayer, QgsRasterShader, QgsRectangle, QgsReferencedRectangle, QgsSingleBandPseudoColorRenderer,
    QgsSingleSymbolRenderer, QgsVectorLayer,
)

PROJETO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARQ_PROJETO = os.path.join(PROJETO, "qgis", "sao_sebastiao_cobertura.qgz")


def caminho(*partes):
    return os.path.join(PROJETO, *partes)


PILHA = caminho("processamento", "S2A_20260417_refletancia_B02_B03_B04_B08_B11.tif")
NDVI = caminho("processamento", "NDVI_20260417.tif")
SCL = caminho("processamento", "01_recorte_10m", "SCL_20260417_31983_10m.tif")
MASCARA = caminho("processamento", "02_mascara", "mascara_validos_20260417.tif")
AREA = caminho("dados", "area_estudo", "area_estudo_maresias.gpkg")
MUNICIPIO = caminho("dados", "contexto", "municipio_sao_sebastiao_ibge2024.gpkg")
BIOMA = caminho("dados", "contexto", "bioma_ibge2025_sao_sebastiao.gpkg")

app = QgsApplication([], False)
app.initQgis()


def percentis(banda, inferior=2, superior=98):
    """Percentis da banda (somente pixels válidos) para o realce de contraste."""
    ds = gdal.Open(PILHA)  # manter a referência ao arquivo aberto enquanto a banda é lida
    b = ds.GetRasterBand(banda)
    a = b.ReadAsArray()
    a = a[a != b.GetNoDataValue()]
    return [float(v) for v in np.percentile(a, [inferior, superior])]


def composicao(nome, r, g, b):
    camada = QgsRasterLayer(PILHA, nome)
    renderizador = QgsMultiBandColorRenderer(camada.dataProvider(), r, g, b)
    realces = []
    for banda in (r, g, b):
        mn, mx = percentis(banda)
        ce = QgsContrastEnhancement(camada.dataProvider().dataType(banda))
        ce.setContrastEnhancementAlgorithm(QgsContrastEnhancement.StretchToMinimumMaximum)
        ce.setMinimumValue(mn)
        ce.setMaximumValue(mx)
        realces.append(ce)
    renderizador.setRedContrastEnhancement(realces[0])
    renderizador.setGreenContrastEnhancement(realces[1])
    renderizador.setBlueContrastEnhancement(realces[2])
    camada.setRenderer(renderizador)
    return camada


def paletado(caminho_raster, nome, classes, opacidade=1.0):
    camada = QgsRasterLayer(caminho_raster, nome)
    itens = [QgsPalettedRasterRenderer.Class(v, QColor(cor), rotulo) for v, cor, rotulo in classes]
    camada.setRenderer(QgsPalettedRasterRenderer(camada.dataProvider(), 1, itens))
    camada.renderer().setOpacity(opacidade)
    return camada


def contorno(caminho_vetor, nome, cor, largura, preenchimento="0,0,0,0"):
    camada = QgsVectorLayer(caminho_vetor, nome, "ogr")
    simbolo = QgsFillSymbol.createSimple({
        "color": preenchimento, "outline_color": cor, "outline_width": str(largura)})
    camada.setRenderer(QgsSingleSymbolRenderer(simbolo))
    return camada


projeto = QgsProject.instance()
projeto.clear()
projeto.setTitle("Classificação Exploratória da Cobertura da Terra em Maresias — "
                 "São Sebastião/SP (Sentinel-2, 17/04/2026)")
projeto.setCrs(QgsCoordinateReferenceSystem("EPSG:31983"))
projeto.writeEntryBool("Paths", "/Absolute", False)  # caminhos relativos

# --- Camadas ------------------------------------------------------------------
area = contorno(AREA, "Limite da área de estudo (3 × 3 km)", "255,0,0,255", 0.8)
municipio = contorno(MUNICIPIO, "Município de São Sebastião (IBGE 2024)", "40,40,40,255", 0.5)
bioma = contorno(BIOMA, "Bioma Mata Atlântica (IBGE 2025, 1:250 000)", "0,90,40,255", 0.3,
                 preenchimento="60,140,70,90")

cor_verdadeira = composicao("Cor verdadeira (R=B04, G=B03, B=B02)", 3, 2, 1)
falsa_cor = composicao("Falsa-cor NIR (R=B08, G=B04, B=B03)", 4, 3, 2)

ndvi = QgsRasterLayer(NDVI, "NDVI (B08 − B04) / (B08 + B04)")
rampa = QgsColorRampShader(-1, 1, None, QgsColorRampShader.Interpolated)
rampa.setColorRampItemList([
    QgsColorRampShader.ColorRampItem(-1.0, QColor("#2b5c8a"), "−1,0"),
    QgsColorRampShader.ColorRampItem(0.0, QColor("#d9cbb0"), "0,0"),
    QgsColorRampShader.ColorRampItem(0.3, QColor("#f0e68c"), "0,3"),
    QgsColorRampShader.ColorRampItem(0.6, QColor("#8cc665"), "0,6"),
    QgsColorRampShader.ColorRampItem(0.9, QColor("#1a6b30"), "0,9"),
])
shader = QgsRasterShader()
shader.setRasterShaderFunction(rampa)
renderizador_ndvi = QgsSingleBandPseudoColorRenderer(ndvi.dataProvider(), 1, shader)
renderizador_ndvi.setClassificationMin(-1)
renderizador_ndvi.setClassificationMax(1)
ndvi.setRenderer(renderizador_ndvi)

scl = paletado(SCL, "SCL — classificação da cena (ESA)", [
    (0, "#000000", "0 Sem dado"), (1, "#ff0000", "1 Saturado/defeituoso"),
    (2, "#2f2f2f", "2 Área escura / sombra topográfica"), (3, "#643200", "3 Sombra de nuvem"),
    (4, "#00a000", "4 Vegetação"), (5, "#ffe65a", "5 Não vegetado"), (6, "#0000ff", "6 Água"),
    (7, "#808080", "7 Não classificado"), (8, "#c0c0c0", "8 Nuvem (prob. média)"),
    (9, "#ffffff", "9 Nuvem (prob. alta)"), (10, "#64c8ff", "10 Cirro"), (11, "#ff96ff", "11 Neve/gelo"),
])
mascara = paletado(MASCARA, "Máscara: pixels inválidos (nuvem/sombra/sem dado)", [
    (0, "#ff00ff", "0 Inválido — excluído dos cálculos"),
    (1, "#00000000", "1 Válido"),
])

for camada in (area, municipio, bioma, cor_verdadeira, falsa_cor, ndvi, scl, mascara):
    if not camada.isValid():
        raise RuntimeError("Camada inválida: " + camada.name())
    projeto.addMapLayer(camada, False)

# --- Grupos (ordem de cima para baixo) ---------------------------------------
raiz = projeto.layerTreeRoot()
g_area = raiz.addGroup("1. Área de estudo")
g_area.addLayer(area)
g_qual = raiz.addGroup("2. Qualidade da imagem (SCL)")
g_qual.addLayer(mascara)
g_qual.addLayer(scl)
g_ind = raiz.addGroup("3. Índice espectral")
g_ind.addLayer(ndvi)
g_img = raiz.addGroup("4. Sentinel-2 L2A — 17/04/2026")
g_img.addLayer(falsa_cor)
g_img.addLayer(cor_verdadeira)
g_ctx = raiz.addGroup("5. Contexto oficial (IBGE)")
g_ctx.addLayer(municipio)
g_ctx.addLayer(bioma)

# Visibilidade inicial: cor verdadeira + limites; demais camadas ligáveis pelo usuário
for camada in (falsa_cor, ndvi, scl):
    raiz.findLayer(camada.id()).setItemVisibilityChecked(False)
g_qual.setExpanded(False)
g_ctx.setExpanded(False)

# Extensão inicial: área de estudo com margem de 300 m
ext = QgsRectangle(440940 - 300, 7368140 - 300, 443940 + 300, 7371140 + 300)
projeto.viewSettings().setDefaultViewExtent(QgsReferencedRectangle(ext, projeto.crs()))

os.makedirs(os.path.dirname(ARQ_PROJETO), exist_ok=True)
if not projeto.write(ARQ_PROJETO):
    raise RuntimeError("Falha ao salvar o projeto")
print("Projeto salvo em", ARQ_PROJETO)
app.exitQgis()
