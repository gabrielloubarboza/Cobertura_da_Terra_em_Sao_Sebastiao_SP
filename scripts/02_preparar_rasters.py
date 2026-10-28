# -*- coding: utf-8 -*-
"""
02_preparar_rasters.py — Preparação dos dados no QGIS (Etapa 1).

Todas as operações abaixo usam algoritmos da Caixa de Ferramentas de
Processamento do QGIS. O script apenas encadeia as mesmas ferramentas que
podem ser executadas manualmente pela interface (ver documentacao/GUIA_DE_APRENDIZADO.md).

Etapas:
  A. Área de estudo (polígono 3 × 3 km, EPSG:31983)        -> dados/area_estudo/
  B. Contexto oficial IBGE (município e bioma)             -> dados/contexto/
  C. Reprojeção + recorte + grade de 10 m de cada banda     -> processamento/01_recorte_10m/
  D. Máscara de qualidade a partir da SCL                   -> processamento/02_mascara/
  E. Conversão DN -> reflectância, aplicando a máscara      -> processamento/03_refletancia/
  F. Empilhamento das bandas (B02, B03, B04, B08, B11)      -> processamento/
  G. NDVI                                                   -> processamento/

Como executar (Windows, QGIS 3.40 LTR), a partir da pasta do projeto:
  "C:\\Program Files\\QGIS 3.40.8\\bin\\python-qgis-ltr.bat" scripts\\02_preparar_rasters.py
"""
import os
import sys

from qgis.core import QgsApplication

PROJETO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def caminho(*partes):
    return os.path.join(PROJETO, *partes)


# --- Inicialização do QGIS fora da interface gráfica -------------------------
app = QgsApplication([], False)
app.initQgis()
sys.path.append(os.path.join(QgsApplication.prefixPath(), "python", "plugins"))
import processing  # noqa: E402
from processing.core.Processing import Processing  # noqa: E402

Processing.initialize()

# --- Parâmetros do estudo -----------------------------------------------------
SRC = "EPSG:31983"  # SIRGAS 2000 / UTM zona 23S
# Área de estudo: 3 × 3 km sobre Maresias (xmin, xmax, ymin, ymax).
# Os limites são múltiplos de 20 m e coincidem com as bordas dos pixels do tile 23KMP.
EXTENSAO = "440940,443940,7368140,7371140 [EPSG:31983]"
DATA = "20260417"
BANDAS_10M = ["B02", "B03", "B04", "B08"]
BANDA_20M = "B11"

# Classes da SCL consideradas INVÁLIDAS para análise:
# 0 sem dado, 1 saturado/defeituoso, 3 sombra de nuvem, 8 nuvem (prob. média),
# 9 nuvem (prob. alta), 10 cirro, 11 neve/gelo.
# A classe 2 (área escura/sombra topográfica) é mantida e documentada.
SCL_INVALIDAS = [0, 1, 3, 8, 9, 10, 11]

NODATA = -9999


def pasta(*partes):
    p = caminho(*partes)
    os.makedirs(p, exist_ok=True)
    return p


def original(banda):
    return caminho("dados", "sentinel2_original", "S2A_%s_T23KMP_%s_original.tif" % (DATA, banda))


# =============================================================================
# A. Área de estudo
#    Interface: Processamento > Ferramentas > "Criar camada a partir da extensão"
#    + Calculadora de campo (nome e área).
# =============================================================================
print("A. Área de estudo")
pasta("dados", "area_estudo")
ext = processing.run("native:extenttolayer", {"INPUT": EXTENSAO, "OUTPUT": "memory:"})["OUTPUT"]
ext = processing.run("native:fieldcalculator", {
    "INPUT": ext, "FIELD_NAME": "nome", "FIELD_TYPE": 2, "FIELD_LENGTH": 80,
    "FORMULA": "'Maresias - São Sebastião/SP (3 x 3 km)'", "OUTPUT": "memory:"})["OUTPUT"]
processing.run("native:fieldcalculator", {
    "INPUT": ext, "FIELD_NAME": "area_km2", "FIELD_TYPE": 0, "FIELD_PRECISION": 3,
    "FORMULA": "$area / 1000000",
    "OUTPUT": caminho("dados", "area_estudo", "area_estudo_maresias.gpkg")})
AREA = caminho("dados", "area_estudo", "area_estudo_maresias.gpkg")

# =============================================================================
# B. Contexto oficial (IBGE)
#    Interface: Vetor > "Extrair por atributo"; "Reprojetar camada"; Vetor > Geoprocessamento > Recortar.
# =============================================================================
print("B. Contexto IBGE")
pasta("dados", "contexto")
ZIP_MUN = caminho("dados", "contexto", "ibge_original", "SP_Municipios_2024.zip")
ZIP_BIO = caminho("dados", "contexto", "ibge_original", "biomas_2025_250mil.zip")
mun = processing.run("native:extractbyattribute", {
    "INPUT": "/vsizip/" + ZIP_MUN + "/SP_Municipios_2024.shp",
    "FIELD": "CD_MUN", "OPERATOR": 0, "VALUE": "3550704", "OUTPUT": "memory:"})["OUTPUT"]
MUNICIPIO = caminho("dados", "contexto", "municipio_sao_sebastiao_ibge2024.gpkg")
processing.run("native:reprojectlayer", {"INPUT": mun, "TARGET_CRS": SRC, "OUTPUT": MUNICIPIO})

bio = processing.run("native:reprojectlayer", {
    "INPUT": "/vsizip/" + ZIP_BIO + "/lml_bioma_e250k_v20250911_A.shp",
    "TARGET_CRS": SRC, "OUTPUT": "memory:"})["OUTPUT"]
processing.run("native:clip", {
    "INPUT": bio, "OVERLAY": MUNICIPIO,
    "OUTPUT": caminho("dados", "contexto", "bioma_ibge2025_sao_sebastiao.gpkg")})

# =============================================================================
# C. Reprojeção, recorte e grade comum de 10 m
#    Interface: Raster > Projeções > Reprojetar (Warp), informando
#    SRC de destino, resolução 10 m e "Extensão do georreferenciamento de saída".
#    - B02, B03, B04, B08 (10 m) e SCL (categórica): vizinho mais próximo.
#    - B11 (20 m -> 10 m): bilinear (dado contínuo).
#    Como a extensão coincide com a grade original, B02–B08 não sofrem reamostragem real.
# =============================================================================
print("C. Reprojeção e recorte")
d_rec = pasta("processamento", "01_recorte_10m")
recorte = {}
for banda in BANDAS_10M + [BANDA_20M, "SCL"]:
    saida = os.path.join(d_rec, "%s_%s_31983_10m.tif" % (banda, DATA))
    processing.run("gdal:warpreproject", {
        "INPUT": original(banda),
        "SOURCE_CRS": "EPSG:32723",
        "TARGET_CRS": SRC,
        "RESAMPLING": 1 if banda == BANDA_20M else 0,  # 0 = vizinho mais próximo, 1 = bilinear
        "NODATA": 0,                 # 0 é o valor "sem dado" do produto L2A
        "TARGET_RESOLUTION": 10,
        "TARGET_EXTENT": EXTENSAO,
        "TARGET_EXTENT_CRS": SRC,
        "OPTIONS": "COMPRESS=DEFLATE",
        "DATA_TYPE": 0,              # manter o tipo original (UInt16 / Byte)
        "OUTPUT": saida})
    recorte[banda] = saida

# =============================================================================
# D. Máscara de qualidade (1 = válido, 0 = inválido)
#    Interface: Processamento > GDAL > Diversos raster > "Calculadora raster"
#    Expressão: 1 - isin(A, [0,1,3,8,9,10,11])
# =============================================================================
print("D. Máscara")
d_mask = pasta("processamento", "02_mascara")
MASCARA = os.path.join(d_mask, "mascara_validos_%s.tif" % DATA)
processing.run("gdal:rastercalculator", {
    "INPUT_A": recorte["SCL"], "BAND_A": 1,
    "FORMULA": "1 - isin(A, %s)" % SCL_INVALIDAS,
    "NO_DATA": None, "RTYPE": 0,  # Byte
    "EXTRA": "--hideNoData",      # a classe 0 da SCL também deve virar 0 (inválido)
    "OUTPUT": MASCARA})

# =============================================================================
# E. Reflectância de superfície
#    Produto L2A com baseline >= 04.00:  reflectância = (DN + BOA_ADD_OFFSET) / 10000
#    com BOA_ADD_OFFSET = -1000 e QUANTIFICATION_VALUE = 10000 (ver MTD_MSIL2A).
#    Pixels com máscara = 0 recebem NoData (-9999).
# =============================================================================
print("E. Reflectância")
d_ref = pasta("processamento", "03_refletancia")
refl = {}
for banda in BANDAS_10M + [BANDA_20M]:
    saida = os.path.join(d_ref, "%s_%s_refletancia.tif" % (banda, DATA))
    processing.run("gdal:rastercalculator", {
        "INPUT_A": recorte[banda], "BAND_A": 1,
        "INPUT_B": MASCARA, "BAND_B": 1,
        # A é UInt16: converter para real ANTES de subtrair, senão 995 - 1000 "dá a volta" (65531)
        "FORMULA": "where(B == 1, (A.astype(float) - 1000) / 10000, %d)" % NODATA,
        "NO_DATA": NODATA, "RTYPE": 5,  # Float32
        "OUTPUT": saida})
    refl[banda] = saida

# =============================================================================
# F. Empilhamento em um único raster multibanda
#    Interface: Raster > Diversos > Mesclar, marcando
#    "Colocar cada arquivo de entrada em uma banda separada".
#    Ordem das bandas: 1=B02 azul, 2=B03 verde, 3=B04 vermelho, 4=B08 NIR, 5=B11 SWIR1
# =============================================================================
print("F. Empilhamento")
PILHA = caminho("processamento", "S2A_%s_refletancia_B02_B03_B04_B08_B11.tif" % DATA)
processing.run("gdal:merge", {
    "INPUT": [refl[b] for b in BANDAS_10M + [BANDA_20M]],
    "SEPARATE": True, "NODATA_INPUT": NODATA, "NODATA_OUTPUT": NODATA,
    "DATA_TYPE": 5, "OPTIONS": "COMPRESS=DEFLATE", "OUTPUT": PILHA})

# =============================================================================
# G. NDVI = (B08 - B04) / (B08 + B04)
#    Interface: Raster > Calculadora Raster (ou GDAL > Calculadora raster).
#    Proteções: (1) NoData herdado da máscara; (2) denominador > 0;
#    (3) NDVI só onde B04 > 0 e B08 > 0 (reflectâncias fisicamente válidas;
#        o offset de -0,1 pode gerar valores levemente negativos sobre a água).
# =============================================================================
print("G. NDVI")
NDVI = caminho("processamento", "NDVI_%s.tif" % DATA)
processing.run("gdal:rastercalculator", {
    "INPUT_A": refl["B08"], "BAND_A": 1,
    "INPUT_B": refl["B04"], "BAND_B": 1,
    "FORMULA": "where((A > 0) & (B > 0), (A - B) / (A + B + (A + B == 0)), %d)" % NODATA,
    "NO_DATA": NODATA, "RTYPE": 5,
    "OUTPUT": NDVI})

print("Preparação concluída.")
app.exitQgis()
