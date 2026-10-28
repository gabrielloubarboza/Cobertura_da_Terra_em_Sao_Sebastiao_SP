# -*- coding: utf-8 -*-
"""
06_classificar.py — Classificação exploratória por regras (Etapa 2).

Classes finais (raster Byte, NoData = 0):
  1 Vegetação arbórea
  2 Vegetação baixa ou aberta
  3 Superfícies construídas e outras não vegetadas (inclui solo exposto)
  4 Água
  5 Areia de praia
  6 Transição / mistura (classificação incerta)
  9 Pixel inválido (máscara SCL da Etapa 1, sem classe temática)

Limiares (definidos em documentacao/estatisticas_amostras.csv e nos histogramas):
  T_NDWI_AGUA  = 0,20   água: NDWI > 0,20
  T_NDVI_ARB   = 0,75   arbórea: NDVI >= 0,80, ou NDVI >= 0,75 E NDBI <= -0,20
  T_NDVI_ARB2  = 0,80   (acima de 0,80 o NDBI não é exigido — ver nota abaixo)
  T_NDBI_ARB   = -0,20
  T_NDVI_VEG   = 0,55   vegetação intermediária: NDVI >= 0,55 (e não arbórea)
  T_B02_CLARO  = 0,15   superfície clara: B02 >= 0,15 E NDVI < 0,20

Ordem das regras:
  R0 máscara = 0                                   -> 9
  R1 NDWI > 0,20                                   -> 4
  R2 NDVI >= 0,80, ou NDVI >= 0,75 e NDBI <= -0,20 -> 1
     Nota (revisão após a rodada diagnóstica de conferência): o NDBI usa a B11
     de 20 m reamostrada; nas bordas da floresta ele é "contaminado" pelas
     superfícies vizinhas (NDBI > -0,20 em 12 % dos pixels de borda contra 1 %
     no interior). Exigir NDBI quando o NDVI já é >= 0,80 jogava bordas de
     floresta na classe 2. Nas amostras de calibração a mudança elevou ARB3 de
     95 % para 100 % e ARB4 de 86 % para 98 % sem alterar os lotes abertos.
  R3 NDVI >= 0,55                                  -> candidato a 2
  R4 B02 >= 0,15 e NDVI < 0,20                     -> candidato a 5
  R5 demais pixels                                 -> 3
Regras de contexto (fotointerpretação traduzida em regra explícita):
  C1 candidato a 5 só vira "Areia de praia" se a mancha clara toca a água;
     manchas claras isoladas (telhados claros) -> 3.
  C2 candidato a 2 só vira "Vegetação baixa ou aberta" se, após remover as
     partes com até 2 pixels (20 m) de largura, restar mancha >= 10 pixels
     (0,1 ha). Franjas de borda e fragmentos de quintal -> 6 (transição).
  C3 fragmento de transição (6) com até 4 pixels (400 m²) cercado somente por
     vegetação arbórea -> 1 (variação de iluminação/textura do dossel contínuo,
     não uma transição de cobertura). Definida após a revisão visual.

Execução:
  "C:\\Program Files\\QGIS 3.40.8\\bin\\python-qgis-ltr.bat" scripts\\06_classificar.py
"""
import os
import sys

from osgeo import gdal
from qgis.core import QgsApplication

PROJETO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def c(*p):
    return os.path.join(PROJETO, *p)


app = QgsApplication([], False)
app.initQgis()
sys.path.append(os.path.join(QgsApplication.prefixPath(), "python", "plugins"))
import processing  # noqa: E402
from processing.core.Processing import Processing  # noqa: E402

Processing.initialize()

EXTENSAO = "440940,443940,7368140,7371140 [EPSG:31983]"
T_NDWI_AGUA, T_NDVI_ARB, T_NDVI_ARB2, T_NDBI_ARB, T_NDVI_VEG, T_B02_CLARO = 0.20, 0.75, 0.80, -0.20, 0.55, 0.15
LARGURA_MIN_M = 10      # buffer de erosão/dilatação (remove partes com largura <= 20 m)
AREA_MIN_M2 = 1000      # 10 pixels de 10 m

D = os.path.join(PROJETO, "processamento", "04_classificacao")
os.makedirs(D, exist_ok=True)
# Apaga resultados anteriores, inclusive os .aux.xml (metadados auxiliares do GDAL),
# para que nomes de classe ou descrições antigas não sobrevivam a uma nova execução.
for pasta_saida in (D, os.path.join(PROJETO, "resultados")):
    for nome in os.listdir(pasta_saida):
        if nome.endswith((".tif", ".tif.aux.xml", ".gpkg")) and (
                pasta_saida == D or nome.startswith("cobertura_classificada")):
            os.remove(os.path.join(pasta_saida, nome))
os.makedirs(c("resultados"), exist_ok=True)
MASCARA = c("processamento", "02_mascara", "mascara_validos_20260417.tif")
NDVI = c("processamento", "NDVI_20260417.tif")
NDWI = c("processamento", "NDWI_20260417.tif")
NDBI = c("processamento", "NDBI_20260417.tif")
B02 = c("processamento", "03_refletancia", "B02_20260417_refletancia.tif")
ESPECTRAL = os.path.join(D, "classes_espectrais_regras.tif")
POLIGONOS = os.path.join(D, "poligonos_classes_espectrais.gpkg")
AREIA = os.path.join(D, "areia_conectada_agua.tif")
ABERTA = os.path.join(D, "vegetacao_aberta_nucleo.tif")
COMBINADA = os.path.join(D, "classes_combinadas_antes_C3.tif")
POLIGONOS_C3 = os.path.join(D, "poligonos_classes_combinadas.gpkg")
DOSSEL = os.path.join(D, "fragmentos_dossel_C3.tif")
AREA_MAX_C3_M2 = 400    # 4 pixels
FINAL = c("resultados", "cobertura_classificada_20260417.tif")

# =============================================================================
# 1. Regras espectrais R0–R5
#    Interface: Processamento > GDAL > Diversos raster > Calculadora raster,
#    camadas A = máscara, B = NDWI, C = NDVI, D = NDBI, E = B02 (reflectância).
#    "--hideNoData": os pixels mascarados são tratados pela regra R0 (código 9),
#    em vez de virarem NoData.
# =============================================================================
print("1. Regras espectrais")
formula = (
    "where(A == 0, 9,"
    " where(B > {w}, 4,"
    " where((C >= {a2}) | ((C >= {a}) & (D <= {nb})), 1,"
    " where(C >= {v}, 2,"
    " where((E >= {cl}) & (C < 0.20) & (C > -1), 5, 3)))))"
).format(w=T_NDWI_AGUA, a=T_NDVI_ARB, a2=T_NDVI_ARB2, nb=T_NDBI_ARB, v=T_NDVI_VEG, cl=T_B02_CLARO)
processing.run("gdal:rastercalculator", {
    "INPUT_A": MASCARA, "BAND_A": 1, "INPUT_B": NDWI, "BAND_B": 1,
    "INPUT_C": NDVI, "BAND_C": 1, "INPUT_D": NDBI, "BAND_D": 1,
    "INPUT_E": B02, "BAND_E": 1,
    "FORMULA": formula, "NO_DATA": 0, "RTYPE": 0, "EXTRA": "--hideNoData",
    "OUTPUT": ESPECTRAL})

# =============================================================================
# 2. Vetorização das classes espectrais (uma feição por mancha, 4-vizinhança)
#    Interface: Raster > Conversão > Poligonizar (raster para vetor), campo "classe".
# =============================================================================
print("2. Poligonização")
processing.run("gdal:polygonize", {
    "INPUT": ESPECTRAL, "BAND": 1, "FIELD": "classe", "EIGHT_CONNECTEDNESS": False,
    "OUTPUT": POLIGONOS})
poligonos = POLIGONOS + "|layername=poligonos_classes_espectrais"


def extrair(classe):
    """Interface: Vetor > Ferramentas de pesquisa > Extrair por atributo."""
    return processing.run("native:extractbyattribute", {
        "INPUT": poligonos, "FIELD": "classe", "OPERATOR": 0, "VALUE": str(classe),
        "OUTPUT": "memory:"})["OUTPUT"]


def rasterizar(camada, saida):
    """Interface: Raster > Conversão > Rasterizar (vetor para raster), valor 1,
    resolução 10 m, extensão da área de estudo (o pixel recebe 1 se o centro
    estiver dentro do polígono)."""
    # O campo "fid" herdado do GeoPackage fica repetido após "Multipartes para
    # partes simples" e quebraria a exportação temporária usada pelo GDAL.
    if camada.fields().indexOf("fid") >= 0:
        camada = processing.run("native:deletecolumn", {
            "INPUT": camada, "COLUMN": ["fid"], "OUTPUT": "memory:"})["OUTPUT"]
    processing.run("gdal:rasterize", {
        "INPUT": camada, "BURN": 1, "UNITS": 1, "WIDTH": 10, "HEIGHT": 10,
        "EXTENT": EXTENSAO, "NODATA": None, "INIT": 0, "DATA_TYPE": 0,
        "OPTIONS": "COMPRESS=DEFLATE", "OUTPUT": saida})


# =============================================================================
# 3. Regra C1 — areia de praia = mancha clara que toca a água
#    Interface: Vetor > Ferramentas de pesquisa > Extrair por localização
#    (feições de "classe 5" que intersectam feições de "classe 4"); depois Rasterizar.
# =============================================================================
print("3. Areia conectada à água")
claras = extrair(5)
agua = extrair(4)
areia = processing.run("native:extractbylocation", {
    "INPUT": claras, "PREDICATE": [0], "INTERSECT": agua, "OUTPUT": "memory:"})["OUTPUT"]
rasterizar(areia, AREIA)

# =============================================================================
# 4. Regra C2 — vegetação baixa ou aberta = núcleo com largura > 20 m e >= 0,1 ha
#    Abertura morfológica feita com dois buffers:
#      Vetor > Geoprocessamento > Buffer, distância -10 m (erosão: some o que tem <= 20 m)
#      Vetor > Geoprocessamento > Buffer, distância +10 m (dilatação: recompõe o contorno)
#      Vetor > Geoprocessamento > Recortar pelo polígono original (não ultrapassa a mancha)
#      Vetor > Geometria > Multipartes para partes simples; Calculadora de campo $area
#      Extrair por expressão: $area >= 1000; Rasterizar.
# =============================================================================
print("4. Núcleos de vegetação aberta")
candidatos = extrair(2)
erodido = processing.run("native:buffer", {
    "INPUT": candidatos, "DISTANCE": -LARGURA_MIN_M, "SEGMENTS": 8, "END_CAP_STYLE": 0,
    "JOIN_STYLE": 0, "MITER_LIMIT": 2, "DISSOLVE": False, "OUTPUT": "memory:"})["OUTPUT"]
dilatado = processing.run("native:buffer", {
    "INPUT": erodido, "DISTANCE": LARGURA_MIN_M, "SEGMENTS": 8, "END_CAP_STYLE": 0,
    "JOIN_STYLE": 0, "MITER_LIMIT": 2, "DISSOLVE": True, "OUTPUT": "memory:"})["OUTPUT"]
recorte = processing.run("native:clip", {
    "INPUT": dilatado, "OVERLAY": candidatos, "OUTPUT": "memory:"})["OUTPUT"]
partes = processing.run("native:multiparttosingleparts", {
    "INPUT": recorte, "OUTPUT": "memory:"})["OUTPUT"]
nucleos = processing.run("native:extractbyexpression", {
    "INPUT": partes, "EXPRESSION": "$area >= %d" % AREA_MIN_M2, "OUTPUT": "memory:"})["OUTPUT"]
rasterizar(nucleos, ABERTA)

# =============================================================================
# 5. Combinação final
#    Interface: Calculadora raster (GDAL), A = classes espectrais, B = areia, C = núcleos.
# =============================================================================
print("5. Combinação das regras")
processing.run("gdal:rastercalculator", {
    "INPUT_A": ESPECTRAL, "BAND_A": 1, "INPUT_B": AREIA, "BAND_B": 1,
    "INPUT_C": ABERTA, "BAND_C": 1,
    "FORMULA": "where(A == 5, where(B == 1, 5, 3), where(A == 2, where(C == 1, 2, 6), A))",
    "NO_DATA": 0, "RTYPE": 0, "EXTRA": "--hideNoData",
    "OUTPUT": COMBINADA})

# =============================================================================
# 6. Regra C3 — fragmentos de transição dentro do dossel contínuo
#    Interface: Poligonizar a classificação combinada; Extrair por expressão
#    "classe" = 6 AND $area <= 400; Extrair por expressão "classe" NOT IN (1, 6)
#    (vizinhos não florestais); Extrair por localização com predicado "disjunto"
#    (fragmentos que não tocam nenhum vizinho não florestal); Rasterizar;
#    Calculadora raster: where(B == 1, 1, A).
# =============================================================================
print("6. Fragmentos de dossel (C3)")
processing.run("gdal:polygonize", {
    "INPUT": COMBINADA, "BAND": 1, "FIELD": "classe", "EIGHT_CONNECTEDNESS": False,
    "OUTPUT": POLIGONOS_C3})
poligonos_c3 = POLIGONOS_C3 + "|layername=poligonos_classes_combinadas"
pequenos = processing.run("native:extractbyexpression", {
    "INPUT": poligonos_c3, "EXPRESSION": '"classe" = 6 AND $area <= %d' % AREA_MAX_C3_M2,
    "OUTPUT": "memory:"})["OUTPUT"]
nao_florestais = processing.run("native:extractbyexpression", {
    "INPUT": poligonos_c3, "EXPRESSION": '"classe" NOT IN (1, 6)', "OUTPUT": "memory:"})["OUTPUT"]
cercados = processing.run("native:extractbylocation", {
    "INPUT": pequenos, "PREDICATE": [2], "INTERSECT": nao_florestais,
    "OUTPUT": "memory:"})["OUTPUT"]
rasterizar(cercados, DOSSEL)
processing.run("gdal:rastercalculator", {
    "INPUT_A": COMBINADA, "BAND_A": 1, "INPUT_B": DOSSEL, "BAND_B": 1,
    "FORMULA": "where(B == 1, 1, A)",
    "NO_DATA": 0, "RTYPE": 0, "EXTRA": "--hideNoData",
    "OPTIONS": "COMPRESS=DEFLATE", "OUTPUT": FINAL})

# Tabela de cores e nomes de categoria gravados no próprio GeoTIFF
# (Interface: Propriedades > Simbologia > Valores paletados; Estilo > Salvar como padrão.)
CLASSES = {
    1: ("Vegetação arbórea", (30, 90, 44)),
    2: ("Vegetação baixa ou aberta", (156, 204, 101)),
    3: ("Superfícies construídas e outras não vegetadas", (126, 122, 133)),
    4: ("Água", (74, 144, 217)),
    5: ("Areia de praia", (246, 232, 177)),
    6: ("Transição / mistura (incerta)", (232, 111, 58)),
    9: ("Pixel inválido (máscara SCL)", (0, 0, 0)),
}
ds = gdal.Open(FINAL, gdal.GA_Update)
banda = ds.GetRasterBand(1)
tabela = gdal.ColorTable()
nomes = [""] * 10
nomes[0] = "Sem dado"
for codigo, (nome, cor) in CLASSES.items():
    tabela.SetColorEntry(codigo, cor + (255,))
    nomes[codigo] = nome
banda.SetColorTable(tabela)
banda.SetCategoryNames(nomes)
ds.SetMetadataItem("DESCRICAO", "Cobertura da terra — classificação exploratória por regras (S2A 17/04/2026)")
ds = None

print("Classificação gravada em", FINAL)
app.exitQgis()
