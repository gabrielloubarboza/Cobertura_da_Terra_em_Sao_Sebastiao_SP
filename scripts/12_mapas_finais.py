# -*- coding: utf-8 -*-
"""
12_mapas_finais.py — Mapas finais e figuras do relatório (Etapa 3).

O que faz, no projeto processamento/sao_sebastiao_cobertura.qgz:
  1. Cria o contorno do estado de São Paulo (dissolvendo os municípios do IBGE 2024)
     para o mapa de localização -> dados/sp_estado_ibge2024.gpkg
  2. Recria os layouts de impressão (remove os anteriores com o mesmo nome):
       "Mapa — Sentinel-2 cor verdadeira"        (A4 paisagem, portfólio)
       "Mapa — Classificação exploratória"       (A4 paisagem, portfólio)
       "Relatório — Sentinel-2"                  (figura do relatório, 118 × 118 mm)
       "Relatório — Classificação"               (figura do relatório, 116 × 116 mm)
       "Relatório — Localização"                 (figura do relatório, 178 × 48 mm)
  3. Exporta:
       resultados/figuras/mapa_sentinel2_cor_verdadeira.png
       resultados/figuras/mapa_classificacao.png
       resultados/figuras/relatorio/*.png (figuras em tamanho real, 300 dpi, e índices)

As figuras do relatório têm o tamanho em que são impressas: o texto da escala e
das legendas não é reduzido depois.

Equivalente na interface: Vetor > Geoprocessamento > Dissolver; Projeto > Novo
layout de impressão (Adicionar mapa, Legenda, Barra de escala, Imagem para a seta
de norte, Rótulo); Exibir > Temas de mapa; Layout > Exportar como imagem.

Execução:
  "C:\\Program Files\\QGIS 3.40.8\\bin\\python-qgis-ltr.bat" scripts\\12_mapas_finais.py
"""
import glob
import os
import sys

from qgis.PyQt.QtCore import QSize
from qgis.PyQt.QtGui import QColor, QFont, QFontDatabase
from qgis.core import (
    QgsApplication, QgsFillSymbol, QgsGeometryGeneratorSymbolLayer, QgsLayoutExporter,
    QgsLayoutItemLabel, QgsLayoutItemLegend, QgsLayoutItemMap, QgsLayoutItemPicture,
    QgsLayoutItemScaleBar, QgsLayoutPoint, QgsLayoutSize, QgsLegendRenderer, QgsLegendStyle,
    QgsMapLayerLegendUtils, QgsMapRendererParallelJob, QgsMapSettings, QgsMapThemeCollection,
    QgsMarkerSymbol, QgsPrintLayout, QgsProject, QgsRectangle, QgsSingleSymbolRenderer,
    QgsSymbol, QgsTextFormat, QgsUnitTypes, QgsVectorLayer,
)

PROJETO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def c(*p):
    return os.path.join(PROJETO, *p)


ARQ = c("processamento", "sao_sebastiao_cobertura.qgz")
FIG = c("resultados", "figuras")
FIG_REL = c("resultados", "figuras", "relatorio")
ESTADO = c("dados", "sp_estado_ibge2024.gpkg")
TITULO = "Classificação Exploratória da Cobertura da Terra em Maresias — São Sebastião/SP"
EXT_AREA = QgsRectangle(440940 - 60, 7368140 - 60, 443940 + 60, 7371140 + 60)
CREDITOS = ("SIRGAS 2000 / UTM 23S (EPSG:31983) · pixel de 10 m\n"
            "Imagem: Sentinel-2A MSI L2A, 17/04/2026 (S2A_MSIL2A_20260417T131301_N0512_R138_T23KMP).\n"
            "Contém dados Copernicus Sentinel modificados [2026].\n"
            "Localização: IBGE — Malha Municipal 2024. Elaboração: Gabriel Barboza Lourenço, 2026.")
NOTA = ("Classificação exploratória da cobertura observável numa única data, por regras espectrais e de "
        "contexto. Não é mapeamento oficial nem resultado validado em campo. A classe 6 reúne pixels mistos "
        "ou de interpretação incerta.")

app = QgsApplication([], False)
app.initQgis()
sys.path.append(os.path.join(QgsApplication.prefixPath(), "python", "plugins"))
import processing  # noqa: E402
from processing.core.Processing import Processing  # noqa: E402

Processing.initialize()

# Fonte IBM Plex Sans (SIL OFL) para os textos dos layouts: não é distribuída no repositório. Se não
# estiver instalada (nem em scripts/relatorio/fontes/), o QGIS usa uma fonte substituta.
for ttf in glob.glob(c("scripts", "relatorio", "fontes", "*.ttf")):
    QFontDatabase.addApplicationFont(ttf)
FONTE = "IBM Plex Sans"
if FONTE not in QFontDatabase().families():
    print("Aviso: fonte IBM Plex Sans não instalada; os layouts usarão uma fonte substituta.")

# =============================================================================
# 1. Contorno do estado de São Paulo (contexto de localização)
#    Interface: Vetor > Geoprocessamento > Dissolver; Reprojetar camada (EPSG:31983)
# =============================================================================
if not os.path.exists(ESTADO):
    zip_mun = c("dados", "ibge_original", "SP_Municipios_2024.zip")
    dissolvido = processing.run("native:dissolve", {
        "INPUT": "/vsizip/" + zip_mun + "/SP_Municipios_2024.shp", "FIELD": [],
        "OUTPUT": "memory:"})["OUTPUT"]
    processing.run("native:reprojectlayer", {
        "INPUT": dissolvido, "TARGET_CRS": "EPSG:31983", "OUTPUT": ESTADO})

projeto = QgsProject.instance()
assert projeto.read(ARQ), "não foi possível abrir o projeto"
raiz = projeto.layerTreeRoot()
g_ctx = raiz.findGroup("5. Contexto (IBGE e OSM)")

# Camadas de localização (recriadas a cada execução)
NOMES_LOC = ("Estado de São Paulo (IBGE 2024)", "Área de estudo (marcador de localização)",
             "São Sebastião (destaque de localização)")
for nome in NOMES_LOC:
    for lyr in projeto.mapLayersByName(nome):
        projeto.removeMapLayer(lyr.id())
estado = QgsVectorLayer(ESTADO, NOMES_LOC[0], "ogr")
estado.setRenderer(QgsSingleSymbolRenderer(QgsFillSymbol.createSimple(
    {"color": "#EEE9DF", "outline_color": "#BFB4A2", "outline_width": "0.25"})))
marcador = QgsVectorLayer(c("dados", "area_estudo_maresias.gpkg"), NOMES_LOC[1], "ogr")
gerador = QgsGeometryGeneratorSymbolLayer.create({"geometryModifier": "centroid($geometry)"})
gerador.setSymbolType(QgsSymbol.Marker)
gerador.setSubSymbol(QgsMarkerSymbol.createSimple(
    {"name": "square", "color": "#E86F3A", "outline_color": "#292A25", "outline_width": "0.35",
     "size": "2.6"}))
simbolo_marcador = QgsFillSymbol()
simbolo_marcador.changeSymbolLayer(0, gerador)
marcador.setRenderer(QgsSingleSymbolRenderer(simbolo_marcador))
destaque = QgsVectorLayer(c("dados", "municipio_sao_sebastiao_ibge2024.gpkg"), NOMES_LOC[2], "ogr")
destaque.setRenderer(QgsSingleSymbolRenderer(QgsFillSymbol.createSimple(
    {"color": "#AD725A", "outline_color": "#8A513B", "outline_width": "0.15"})))
for camada in (estado, marcador, destaque):
    assert camada.isValid(), camada.name()
    projeto.addMapLayer(camada, False)
    g_ctx.addLayer(camada).setItemVisibilityChecked(False)


def camada(nome):
    return projeto.mapLayersByName(nome)[0]


area = camada("Limite da área de estudo (3 × 3 km)")
cor_verdadeira = camada("Cor verdadeira (R=B04, G=B03, B=B02)")
cobertura = camada("Cobertura da terra — classificação exploratória (17/04/2026)")
municipio = camada("Município de São Sebastião (IBGE 2024)")

# Remove layouts e temas anteriores (de qualquer versão destes scripts)
for layout in list(projeto.layoutManager().printLayouts()):
    projeto.layoutManager().removeLayout(layout)
for tema in list(projeto.mapThemeCollection().mapThemes()):
    projeto.mapThemeCollection().removeMapTheme(tema)


# =============================================================================
# Funções de layout
# =============================================================================
def formato(tamanho, peso=QFont.Normal, cor="#292A25"):
    fmt = QgsTextFormat()
    fonte = QFont(FONTE)
    fonte.setWeight(peso)
    fmt.setFont(fonte)
    fmt.setSize(tamanho)
    fmt.setColor(QColor(cor))
    return fmt


def texto(layout, conteudo, x, y, w, h, tamanho, peso=QFont.Normal, cor="#292A25"):
    item = QgsLayoutItemLabel(layout)
    item.setText(conteudo)
    item.setTextFormat(formato(tamanho, peso, cor))
    item.attemptMove(QgsLayoutPoint(x, y, QgsUnitTypes.LayoutMillimeters))
    item.attemptResize(QgsLayoutSize(w, h, QgsUnitTypes.LayoutMillimeters))
    layout.addLayoutItem(item)
    return item


def novo_layout(nome, largura=None, altura=None):
    layout = QgsPrintLayout(projeto)
    layout.initializeDefaults()  # A4 paisagem
    layout.setName(nome)
    if largura:
        layout.pageCollection().page(0).setPageSize(
            QgsLayoutSize(largura, altura, QgsUnitTypes.LayoutMillimeters))
    projeto.layoutManager().addLayout(layout)
    return layout


def mapa(layout, tema, camadas, extensao, x, y, w, h, moldura=True, fundo="#FFFFFF"):
    """Mapa que segue um tema (Exibir > Temas de mapa): sem caminhos de arquivo no layout."""
    registro = QgsMapThemeCollection.MapThemeRecord()
    registro.setLayerRecords([QgsMapThemeCollection.MapThemeLayerRecord(lyr) for lyr in camadas])
    projeto.mapThemeCollection().insert(tema, registro)
    item = QgsLayoutItemMap(layout)
    item.attemptMove(QgsLayoutPoint(x, y, QgsUnitTypes.LayoutMillimeters))
    item.attemptResize(QgsLayoutSize(w, h, QgsUnitTypes.LayoutMillimeters))
    item.setFollowVisibilityPreset(True)
    item.setFollowVisibilityPresetName(tema)
    item.setCrs(projeto.crs())
    item.zoomToExtent(extensao)  # mantém o tamanho do quadro (setExtent o redimensionaria)
    item.setBackgroundColor(QColor(fundo))
    item.setFrameEnabled(moldura)
    item.setFrameStrokeColor(QColor("#575850"))
    layout.addLayoutItem(item)
    return item


def escala(layout, mapa_item, x, y, tamanho=7, fundo=False):
    barra = QgsLayoutItemScaleBar(layout)
    barra.setStyle("Single Box")
    barra.setLinkedMap(mapa_item)
    barra.setUnits(QgsUnitTypes.DistanceMeters)
    barra.setNumberOfSegments(2)
    barra.setNumberOfSegmentsLeft(0)
    barra.setUnitsPerSegment(500)
    barra.setUnitLabel("m")
    barra.setHeight(1.6)
    barra.setTextFormat(formato(tamanho))
    if fundo:
        barra.setBackgroundEnabled(True)
        barra.setBackgroundColor(QColor(255, 255, 255, 230))
        barra.setBoxContentSpace(1.2)
    barra.attemptMove(QgsLayoutPoint(x, y, QgsUnitTypes.LayoutMillimeters))
    layout.addLayoutItem(barra)
    return barra


def norte(layout, x, y, w=8, h=11, fundo=False):
    seta = QgsLayoutItemPicture(layout)
    seta.setPicturePath(os.path.join(QgsApplication.svgPaths()[0], "arrows", "NorthArrow_02.svg"))
    seta.setSvgFillColor(QColor("#292A25"))  # o SVG usa cor parametrizada; padrão era branco
    seta.setSvgStrokeColor(QColor("#292A25"))
    seta.attemptMove(QgsLayoutPoint(x, y, QgsUnitTypes.LayoutMillimeters))
    seta.attemptResize(QgsLayoutSize(w, h, QgsUnitTypes.LayoutMillimeters))
    if fundo:
        seta.setBackgroundEnabled(True)
        seta.setBackgroundColor(QColor(255, 255, 255, 230))
    layout.addLayoutItem(seta)


def legenda_classes(layout, mapa_item, x, y, tamanho=9, titulo="Classes de cobertura"):
    legenda = QgsLayoutItemLegend(layout)
    legenda.setTitle(titulo)
    legenda.setLinkedMap(mapa_item)
    legenda.setAutoUpdateModel(False)
    modelo = legenda.model().rootGroup()
    modelo.removeAllChildren()
    no = modelo.addLayer(cobertura)
    QgsLegendRenderer.setNodeLegendStyle(no, QgsLegendStyle.Hidden)
    # remove o cabeçalho automático "Band 1 (Palette)" e mantém só as classes
    n = len(legenda.model().layerLegendNodes(no))
    QgsMapLayerLegendUtils.setLegendNodeOrder(no, list(range(1, n)))
    legenda.model().refreshLayerLegend(no)
    legenda.rstyle(QgsLegendStyle.Title).setTextFormat(formato(tamanho + 1, QFont.DemiBold))
    legenda.rstyle(QgsLegendStyle.SymbolLabel).setTextFormat(formato(tamanho))
    legenda.setSymbolWidth(6)
    legenda.setSymbolHeight(4)
    legenda.setBackgroundEnabled(False)
    legenda.attemptMove(QgsLayoutPoint(x, y, QgsUnitTypes.LayoutMillimeters))
    layout.addLayoutItem(legenda)
    return legenda


def exportar(layout, arquivo, dpi):
    exportador = QgsLayoutExporter(layout)
    config = QgsLayoutExporter.ImageExportSettings()
    config.dpi = dpi
    config.exportMetadata = False  # evita que o GDAL tente regravar metadados no PNG
    resultado = exportador.exportToImage(arquivo, config)
    assert resultado == QgsLayoutExporter.Success, (arquivo, resultado)


ext_estado = estado.extent()
ext_estado.grow(15000)
ext_mun = QgsRectangle(410000, 7352000, 464000, 7389000)


# =============================================================================
# 2. Mapas do portfólio (A4 paisagem)
# =============================================================================
def mapa_portfolio(nome, camadas, subtitulo, arquivo, com_legenda):
    layout = novo_layout(nome)
    texto(layout, TITULO, 10, 7, 277, 8, 15, QFont.DemiBold)
    texto(layout, subtitulo, 10, 15.5, 277, 6, 9, cor="#575850")
    principal = mapa(layout, nome, camadas, EXT_AREA, 10, 24, 172, 172)
    y = 24
    if com_legenda:
        legenda_classes(layout, principal, 190, y, 9)
        y = 82
    texto(layout, "Localização", 190, y, 97, 5, 9, QFont.DemiBold)
    mapa(layout, nome + " (localização)", [marcador, destaque, estado], ext_estado, 190, y + 6, 97, 52)
    texto(layout, "São Sebastião (terracota) e área de estudo (quadrado) no estado de São Paulo",
          190, y + 59, 97, 4, 6.5, cor="#575850")
    norte(layout, 190, y + 66)
    escala(layout, principal, 202, y + 69, 8)
    texto(layout, NOTA, 190, 164, 97, 14, 7.5, cor="#575850")
    texto(layout, CREDITOS, 190, 180, 97, 18, 6.5, cor="#575850")
    exportar(layout, os.path.join(FIG, arquivo), 200)


os.makedirs(FIG_REL, exist_ok=True)
mapa_portfolio("Mapa — Sentinel-2 cor verdadeira", [area, cor_verdadeira],
               "Composição Sentinel-2 em cor verdadeira (R = B04, G = B03, B = B02), 17/04/2026 · "
               "contraste 2–98 % apenas para visualização",
               "mapa_sentinel2_cor_verdadeira.png", False)
mapa_portfolio("Mapa — Classificação exploratória", [area, cobertura],
               "Cobertura da terra em 17/04/2026 · regras espectrais (NDWI, NDVI, NDBI, B02) e de contexto · "
               "Sentinel-2, 10 m",
               "mapa_classificacao.png", True)

# =============================================================================
# 3. Figuras do relatório (tamanho real de impressão, 300 dpi)
# =============================================================================
for nome, camadas, lado, arquivo in (
        ("Relatório — Sentinel-2", [area, cor_verdadeira], 118, "fig_sentinel2_cor_verdadeira.png"),
        ("Relatório — Classificação", [area, cobertura], 116, "fig_classificacao.png")):
    layout = novo_layout(nome, lado, lado)
    principal = mapa(layout, nome, camadas, EXT_AREA, 0, 0, lado, lado)
    norte(layout, lado - 11, 2.5, 8, 11, fundo=True)
    escala(layout, principal, 2.5, lado - 17, 8, fundo=True)  # textos de 8 pt no tamanho impresso
    exportar(layout, os.path.join(FIG_REL, arquivo), 300)

layout = novo_layout("Relatório — Localização", 178, 48)
mapa(layout, "Relatório — Localização (estado)", [marcador, destaque, estado], ext_estado, 0, 0, 87, 48)
mapa(layout, "Relatório — Localização (município)", [area, municipio, estado], ext_mun, 91, 0, 87, 48)
texto(layout, "Estado de São Paulo", 2, 1.5, 55, 5, 8, QFont.DemiBold, "#575850")
texto(layout, "Município de São Sebastião", 93, 1.5, 70, 5, 8, QFont.DemiBold, "#575850")
exportar(layout, os.path.join(FIG_REL, "fig_localizacao.png"), 300)

# Índices (mesmas rampas do projeto), 54 × 54 mm a 300 dpi, sem layout salvo
for nome_camada, arquivo in (("NDVI (B08 − B04) / (B08 + B04)", "fig_ndvi.png"),
                             ("NDWI (B03 − B08) / (B03 + B08)", "fig_ndwi.png"),
                             ("NDBI (B11 − B08) / (B11 + B08)", "fig_ndbi.png")):
    ms = QgsMapSettings()
    ms.setLayers([area, camada(nome_camada)])
    ms.setDestinationCrs(projeto.crs())
    ms.setExtent(EXT_AREA)
    lado_px = round(54 / 25.4 * 300)
    ms.setOutputSize(QSize(lado_px, lado_px))
    ms.setOutputDpi(300)
    ms.setBackgroundColor(QColor("white"))
    job = QgsMapRendererParallelJob(ms)
    job.start()
    job.waitForFinished()
    job.renderedImage().save(os.path.join(FIG_REL, arquivo))

# Imagem de card para o portfólio: só o mapa de classificação, recorte 3:2 (3 × 2 km da área
# de estudo, com vila, praia e encosta), sem distorção (mesma escala em x e y)
ms = QgsMapSettings()
ms.setLayers([cobertura])
ms.setDestinationCrs(projeto.crs())
ms.setExtent(QgsRectangle(440940, 7368440, 443940, 7370440))
ms.setOutputSize(QSize(2400, 1600))
ms.setBackgroundColor(QColor("white"))
job = QgsMapRendererParallelJob(ms)
job.start()
job.waitForFinished()
job.renderedImage().save(os.path.join(FIG, "card_classificacao.png"))

projeto.writeEntryBool("Paths", "/Absolute", False)
assert projeto.write(ARQ), "falha ao salvar"
print("Layouts:", [l.name() for l in projeto.layoutManager().printLayouts()])

# Libera os objetos do QGIS e do GDAL antes de encerrar o QGIS (evita erro na saída)
import gc  # noqa: E402


def _do_qgis(valor):
    if isinstance(valor, (list, tuple)):
        return any(_do_qgis(v) for v in valor)
    return (type(valor).__module__.startswith(("qgis", "osgeo"))
            and not isinstance(valor, QgsApplication))


for _nome in [n for n, v in list(globals().items()) if _do_qgis(v)]:
    del globals()[_nome]
gc.collect()
app.exitQgis()
