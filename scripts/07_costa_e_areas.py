# -*- coding: utf-8 -*-
"""
07_costa_e_areas.py — Conferência do limite terra-mar e cálculo das áreas (Etapa 2).

1. Linha de costa independente: OpenStreetMap (natural=coastline), obtida pela
   API Overpass e guardada sem alteração em dados/contexto/osm_original/.
2. Compara a linha de costa espectral (borda da classe Água) com:
     - OSM (traçada sobre imagens Bing, edições de 2019–2020);
     - IBGE Malha Municipal 2024 (escala 1:250 000).
   Métricas: distância de pontos a cada 10 m da linha espectral até a linha de
   referência, e área "não aquática" segundo cada fonte.
3. Áreas por classe a partir da contagem de pixels de 10 m × 10 m (100 m²).
   -> resultados/areas_por_classe.csv e documentacao/conferencia_linha_costa.txt

Execução:
  "C:\\Program Files\\QGIS 3.40.8\\bin\\python-qgis-ltr.bat" scripts\\07_costa_e_areas.py
"""
import csv
import json
import os
import statistics
import sys
import urllib.parse
import urllib.request

from qgis.core import (
    QgsApplication, QgsCoordinateReferenceSystem, QgsFeature, QgsGeometry, QgsPointXY,
    QgsVectorLayer,
)

PROJETO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def c(*p):
    return os.path.join(PROJETO, *p)


app = QgsApplication([], False)
app.initQgis()
sys.path.append(os.path.join(QgsApplication.prefixPath(), "python", "plugins"))
import processing  # noqa: E402
from processing.core.Processing import Processing  # noqa: E402

Processing.initialize()

SRC = "EPSG:31983"
FINAL = c("resultados", "cobertura_classificada_20260417.tif")
AREA = c("dados", "area_estudo", "area_estudo_maresias.gpkg")
MUNICIPIO = c("dados", "contexto", "municipio_sao_sebastiao_ibge2024.gpkg")
OSM_JSON = c("dados", "contexto", "osm_original", "osm_coastline_overpass.json")
OSM_GPKG = c("dados", "contexto", "linha_costa_osm.gpkg")
D = c("processamento", "05_costa")
os.makedirs(D, exist_ok=True)
os.makedirs(os.path.dirname(OSM_JSON), exist_ok=True)

CLASSES = {
    1: "Vegetação arbórea",
    2: "Vegetação baixa ou aberta",
    3: "Superfícies construídas e outras não vegetadas",
    4: "Água",
    5: "Areia de praia",
    6: "Transição / mistura (incerta)",
    9: "Pixel inválido (máscara SCL)",
}

# =============================================================================
# 1. Linha de costa OSM (download único; o arquivo bruto é preservado)
#    Interface: complemento QuickOSM, chave natural = coastline, extensão da área.
# =============================================================================
if not os.path.exists(OSM_JSON):
    consulta = ('[out:json][timeout:60];way["natural"="coastline"]'
                '(-23.805,-45.590,-23.760,-45.540);out geom meta;')
    for servidor in ("https://overpass-api.de/api/interpreter",
                     "https://overpass.kumi.systems/api/interpreter"):
        try:
            req = urllib.request.Request(servidor, urllib.parse.urlencode({"data": consulta}).encode(),
                                         headers={"User-Agent": "estudo-qgis-sao-sebastiao"})
            dados = json.load(urllib.request.urlopen(req, timeout=120))
            break
        except Exception as erro:  # servidor público pode estar sobrecarregado
            print("  Overpass indisponível em", servidor, erro)
    with open(OSM_JSON, "w", encoding="utf-8") as fh:
        json.dump(dados, fh, ensure_ascii=False, indent=1)

with open(OSM_JSON, encoding="utf-8") as fh:
    dados = json.load(fh)
linhas = QgsVectorLayer("LineString?crs=EPSG:4326&field=osm_id:string&field=editado:string"
                        "&field=fonte:string", "costa_osm", "memory")
for el in dados["elements"]:
    f = QgsFeature(linhas.fields())
    f.setGeometry(QgsGeometry.fromPolylineXY([QgsPointXY(p["lon"], p["lat"]) for p in el["geometry"]]))
    f.setAttributes([str(el["id"]), el.get("timestamp", ""), el.get("tags", {}).get("source", "")])
    linhas.dataProvider().addFeature(f)
processing.run("native:reprojectlayer", {"INPUT": linhas, "TARGET_CRS": SRC, "OUTPUT": OSM_GPKG})

# =============================================================================
# 2. Linha de costa espectral e comparação
#    Interface: Poligonizar a classificação; Extrair "classe" = 4; Dissolver;
#    Vetor > Geometria > Limite (borda); Recortar pela área de estudo reduzida
#    em 5 m (para descartar a moldura do recorte); Pontos ao longo da linha (10 m);
#    Juntar atributos pelo mais próximo (campo "distance").
# =============================================================================
poligonos = processing.run("gdal:polygonize", {
    "INPUT": FINAL, "BAND": 1, "FIELD": "classe", "EIGHT_CONNECTEDNESS": False,
    "OUTPUT": os.path.join(D, "poligonos_classificacao.gpkg")})["OUTPUT"]
agua = processing.run("native:extractbyattribute", {
    "INPUT": poligonos, "FIELD": "classe", "OPERATOR": 0, "VALUE": "4",
    "OUTPUT": "memory:"})["OUTPUT"]
agua = processing.run("native:dissolve", {"INPUT": agua, "OUTPUT": "memory:"})["OUTPUT"]
borda = processing.run("native:boundary", {"INPUT": agua, "OUTPUT": "memory:"})["OUTPUT"]
interior = processing.run("native:buffer", {
    "INPUT": AREA, "DISTANCE": -5, "SEGMENTS": 1, "END_CAP_STYLE": 2, "JOIN_STYLE": 1,
    "MITER_LIMIT": 2, "DISSOLVE": False, "OUTPUT": "memory:"})["OUTPUT"]
costa_espectral = processing.run("native:clip", {
    "INPUT": borda, "OVERLAY": interior,
    "OUTPUT": os.path.join(D, "linha_costa_espectral.gpkg")})["OUTPUT"]
pontos = processing.run("native:pointsalonglines", {
    "INPUT": costa_espectral, "DISTANCE": 10, "START_OFFSET": 0, "END_OFFSET": 0,
    "OUTPUT": "memory:"})["OUTPUT"]
# "Pontos ao longo da linha" cria o campo "distance" (posição ao longo da linha).
# Ele é removido para não ser confundido com a distância calculada na junção.
pontos = processing.run("native:deletecolumn", {
    "INPUT": pontos, "COLUMN": [f.name() for f in pontos.fields()], "OUTPUT": "memory:"})["OUTPUT"]

costa_ibge = processing.run("native:boundary", {"INPUT": MUNICIPIO, "OUTPUT": "memory:"})["OUTPUT"]
costa_ibge = processing.run("native:clip", {
    "INPUT": costa_ibge, "OVERLAY": processing.run("native:buffer", {
        "INPUT": AREA, "DISTANCE": 300, "SEGMENTS": 1, "END_CAP_STYLE": 2, "JOIN_STYLE": 1,
        "MITER_LIMIT": 2, "DISSOLVE": False, "OUTPUT": "memory:"})["OUTPUT"],
    "OUTPUT": "memory:"})["OUTPUT"]

relatorio = ["Conferência do limite terra-mar — classificação de 17/04/2026", ""]
for nome, referencia in (("OSM (natural=coastline)", OSM_GPKG), ("IBGE Malha Municipal 2024", costa_ibge)):
    unido = processing.run("native:joinbynearest", {
        "INPUT": pontos, "INPUT_2": referencia, "FIELDS_TO_COPY": [], "DISCARD_NONMATCHING": False,
        "PREFIX": "ref_", "NEIGHBORS": 1, "MAX_DISTANCE": None, "OUTPUT": "memory:"})["OUTPUT"]
    dist = sorted(f["distance"] for f in unido.getFeatures())
    p90 = dist[int(0.9 * (len(dist) - 1))]
    relatorio.append("%s: %d pontos a cada 10 m; distância mediana %.1f m; P90 %.1f m; máx. %.1f m" % (
        nome, len(dist), statistics.median(dist), p90, dist[-1]))

# Área não aquática segundo cada fonte
#   OSM: Vetor > Geoprocessamento > Dividir com linhas (área de estudo × costa OSM);
#        a parte que contém um ponto no oceano é o mar.
#   IBGE: Vetor > Geoprocessamento > Interseção (área de estudo × município).
geom_area = next(QgsVectorLayer(AREA, "a", "ogr").getFeatures()).geometry()
# Os trechos (ways) da costa OSM precisam ser unidos numa linha contínua para
# cortar o polígono: Vetor > Geoprocessamento > Dissolver; Vetor > Geometria > Mesclar linhas.
costa_unida = processing.run("native:dissolve", {"INPUT": OSM_GPKG, "OUTPUT": "memory:"})["OUTPUT"]
costa_unida = processing.run("native:mergelines", {"INPUT": costa_unida, "OUTPUT": "memory:"})["OUTPUT"]
partes = processing.run("native:splitwithlines", {
    "INPUT": AREA, "LINES": costa_unida, "OUTPUT": "memory:"})["OUTPUT"]
assert partes.featureCount() >= 2, "a costa OSM não dividiu a área de estudo"
ponto_oceano = QgsGeometry.fromPointXY(QgsPointXY(442095, 7368315))
mar_osm = sum(f.geometry().area() for f in partes.getFeatures() if f.geometry().contains(ponto_oceano))
terra_ibge = sum(f.geometry().intersection(geom_area).area()
                 for f in QgsVectorLayer(MUNICIPIO, "m", "ogr").getFeatures())

# =============================================================================
# 3. Áreas por classe
#    Interface: Processamento > "Relatório de valores únicos da camada raster"
#    (native:rasterlayeruniquevaluesreport) — informa contagem de pixels e área m².
# =============================================================================
rel = processing.run("native:rasterlayeruniquevaluesreport", {
    "INPUT": FINAL, "BAND": 1, "OUTPUT_TABLE": "memory:"})
contagem = {int(f["value"]): (int(f["count"]), float(f["m2"])) for f in rel["OUTPUT_TABLE"].getFeatures()}
total = sum(m2 for _, m2 in contagem.values())
agua_m2 = contagem.get(4, (0, 0))[1]
invalido_m2 = contagem.get(9, (0, 0))[1]
terra_valida = total - agua_m2 - invalido_m2

with open(c("resultados", "areas_por_classe.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["codigo", "classe", "pixels", "area_m2", "area_km2", "pct_area_total",
                "pct_area_terrestre_valida"])
    for cod in sorted(CLASSES):
        n, m2 = contagem.get(cod, (0, 0.0))
        pct_terra = "" if cod in (4, 9) else round(100 * m2 / terra_valida, 2)
        w.writerow([cod, CLASSES[cod], n, round(m2), round(m2 / 1e6, 4), round(100 * m2 / total, 2), pct_terra])
    w.writerow(["", "Área total do recorte", rel["TOTAL_PIXEL_COUNT"], round(total), round(total / 1e6, 4), 100.0, ""])
    w.writerow(["", "Área terrestre válida (total - água - inválidos)", "", round(terra_valida),
                round(terra_valida / 1e6, 4), round(100 * terra_valida / total, 2), 100.0])

area_aoi = geom_area.area()
relatorio += [
    "",
    "Área não aquática (km²):",
    "  espectral (classes 1, 2, 3, 5, 6; exclui água e 9) : %.3f" % (terra_valida / 1e6),
    "  espectral incluindo os 48 pixels inválidos (areia)   : %.3f" % ((terra_valida + invalido_m2) / 1e6),
    "  OSM (área de estudo menos o lado do mar)             : %.3f" % ((area_aoi - mar_osm) / 1e6),
    "  IBGE 1:250 000 (interseção com o município)          : %.3f" % (terra_ibge / 1e6),
    "",
    "Interpretação: as proporções de cobertura usam a área não aquática identificada",
    "espectralmente na própria data da imagem. OSM e IBGE servem só como conferência.",
]
with open(c("documentacao", "conferencia_linha_costa.txt"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(relatorio) + "\n")
print("\n".join(relatorio))
app.exitQgis()
