# -*- coding: utf-8 -*-
"""
09_conferencia_e_produtos.py — Resultado da conferência e produtos finais (Etapa 2).

1. Junta a interpretação visual da rodada 2 (documentacao/diagnostico_2/
   interpretacao_visual.csv) aos pontos sorteados e calcula a concordância.
   A rodada 1 (diagnóstica) entra no GeoPackage só como registro.
   ATENÇÃO: conferência INTERNA exploratória. A referência é a mesma imagem
   Sentinel-2 usada na classificação, interpretada visualmente. Não é validação
   independente nem estimativa de acurácia temática.
2. Monta resultados/sao_sebastiao_cobertura.gpkg com: area_estudo,
   cobertura_poligonos (dissolvida por classe), pontos_conferencia,
   amostras_calibracao, classes, areas_por_classe, metadados.
3. Gráfico de área por classe -> resultados/figuras/grafico_area_por_classe.png

Equivalente na interface:
  - Junção: Propriedades da camada > Uniões (campo "id") com o CSV aberto como
    texto delimitado; Calculadora de campo para "concordancia".
  - Tabela cruzada: Processamento > "Estatísticas por categorias" (classe_mapeada
    × classe_interpretada) ou Tabela de atributos + filtros.
  - GeoPackage: Processamento > "Empacotar camadas" (native:package).
  - Polígonos por classe: Poligonizar > Dissolver (campo classe).

Execução:
  "C:\\Program Files\\QGIS 3.40.8\\bin\\python-qgis-ltr.bat" scripts\\09_conferencia_e_produtos.py
"""
import csv
import os
import sys

from qgis.core import (
    QgsApplication, QgsFeature, QgsVectorLayer, edit,
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

FINAL = c("resultados", "cobertura_classificada_20260417.tif")
GPKG = c("resultados", "sao_sebastiao_cobertura.gpkg")
FIG = c("resultados", "figuras")
os.makedirs(FIG, exist_ok=True)

CLASSES = [
    (1, "Vegetação arbórea", "#1e5a2c",
     "Cobertura predominantemente arbórea (não equivale a floresta nativa)",
     "NDWI <= 0,20 e (NDVI >= 0,80 ou NDVI >= 0,75 com NDBI <= -0,20) (+ regra C3)"),
    (2, "Vegetação baixa ou aberta", "#9ccc65",
     "Gramíneas, herbáceas e arbustos em manchas compactas",
     "NDVI >= 0,55 sem ser arbórea; núcleo com largura > 20 m e >= 0,1 ha (C2)"),
    (3, "Superfícies construídas e outras não vegetadas", "#7e7a85",
     "Telhados, vias, pavimentos, solo exposto e areia úmida; inclui superfícies naturais não vegetadas",
     "Demais pixels terrestres (NDVI < 0,55) e superfícies claras que não tocam a água"),
    (4, "Água", "#4a90d9", "Oceano, arrebentação e água artificial (piscina)", "NDWI > 0,20"),
    (5, "Areia de praia", "#f6e8b1", "Superfície clara não vegetada contínua à água",
     "B02 >= 0,15 e NDVI < 0,20, em mancha que toca a água (C1)"),
    (6, "Transição / mistura (incerta)", "#e86f3a",
     "Pixels mistos: bordas floresta/construção, quintais arborizados, falhas pequenas do dossel",
     "Vegetação intermediária que não forma núcleo de vegetação aberta (C2)"),
    (9, "Pixel inválido (máscara SCL)", "#000000",
     "Excluído da análise (provável falso positivo de nuvem sobre areia)", "SCL classes 0,1,3,8,9,10,11"),
]
NOME = {k: n for k, n, *_ in CLASSES}

# =============================================================================
# 1. Conferência interna
# =============================================================================
DIR_CONF = c("documentacao", "diagnostico_2")
pontos = QgsVectorLayer(c("processamento", "pontos_conferencia_rodada2.gpkg"),
                        "pontos", "ogr")
with open(os.path.join(DIR_CONF, "interpretacao_visual.csv"), encoding="utf-8") as fh:
    interp = {int(r["id"]): r for r in csv.DictReader(fh)}
campos = ("id:integer&field=x_31983:double&field=y_31983:double&field=classe_mapeada:integer"
          "&field=nome_mapeada:string&field=classe_interpretada:integer&field=nome_interpretada:string"
          "&field=concordancia:string&field=confianca:string&field=observacao:string"
          "&field=fonte:string&field=interprete:string")
camada_pontos = QgsVectorLayer("Point?crs=EPSG:31983&field=" + campos, "pontos_conferencia", "memory")
matriz = {}
with edit(camada_pontos):
    for f in sorted(pontos.getFeatures(), key=lambda f: f["id"]):
        r = interp[f["id"]]
        m, i = int(f["classe_mapeada"]), int(r["classe_interpretada"])
        matriz[(m, i)] = matriz.get((m, i), 0) + 1
        nova = QgsFeature(camada_pontos.fields())
        nova.setGeometry(f.geometry())
        nova.setAttributes([f["id"], f["x_31983"], f["y_31983"], m, NOME[m], i, NOME[i],
                            "sim" if m == i else "não", r["confianca"], r["observacao"],
                            r["fonte"], r["interprete"]])
        camada_pontos.addFeature(nova)

codigos = [1, 2, 3, 4, 5, 6]
total = sum(matriz.values())
concordantes = sum(matriz.get((k, k), 0) for k in codigos)
with open(os.path.join(DIR_CONF, "matriz_conferencia_interna.csv"), "w", newline="",
          encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["mapeada \\ interpretada"] + [str(k) for k in codigos] + ["total", "concordantes", "pct"])
    for m in codigos:
        linha = [matriz.get((m, i), 0) for i in codigos]
        w.writerow([m] + linha + [sum(linha), matriz.get((m, m), 0),
                                  round(100 * matriz.get((m, m), 0) / max(sum(linha), 1), 1)])
    w.writerow(["total"] + [sum(matriz.get((m, i), 0) for m in codigos) for i in codigos] +
               [total, concordantes, round(100 * concordantes / total, 1)])
resumo = ["Conferência interna exploratória (rodada 2, semente 2027) — %d pontos estratificados por classe mapeada" % total,
          "Concordância bruta (não ponderada por área): %d/%d = %.1f %%" % (
              concordantes, total, 100 * concordantes / total),
          "Concordância bruta sem a classe 6 (transição): %d/%d" % (
              sum(matriz.get((k, k), 0) for k in codigos if k != 6),
              sum(v for (m, _), v in matriz.items() if m != 6))]
for m in codigos:
    n = sum(matriz.get((m, i), 0) for i in codigos)
    resumo.append("  classe %d %-48s %2d/%2d concordantes; interpretados como: %s" % (
        m, NOME[m], matriz.get((m, m), 0), n,
        {i: matriz[(m, i)] for i in codigos if matriz.get((m, i)) and i != m}))
with open(os.path.join(DIR_CONF, "resumo_conferencia.txt"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(resumo) + "\n")
print("\n".join(resumo))

# =============================================================================
# 2. GeoPackage final
# =============================================================================
poligonos = processing.run("gdal:polygonize", {
    "INPUT": FINAL, "BAND": 1, "FIELD": "classe", "EIGHT_CONNECTEDNESS": False,
    "OUTPUT": "TEMPORARY_OUTPUT"})["OUTPUT"]
dissolvido = processing.run("native:dissolve", {
    "INPUT": poligonos, "FIELD": ["classe"], "OUTPUT": "memory:"})["OUTPUT"]
cobertura = QgsVectorLayer("MultiPolygon?crs=EPSG:31983&field=classe:integer&field=nome_classe:string"
                           "&field=area_km2:double&field=n_partes:integer", "cobertura_poligonos", "memory")
with edit(cobertura):
    for f in dissolvido.getFeatures():
        g = f.geometry()
        nova = QgsFeature(cobertura.fields())
        nova.setGeometry(g)
        nova.setAttributes([int(f["classe"]), NOME[int(f["classe"])], round(g.area() / 1e6, 4),
                            g.constGet().numGeometries()])
        cobertura.addFeature(nova)

classes = QgsVectorLayer("None?field=codigo:integer&field=classe:string&field=cor:string"
                         "&field=descricao:string&field=regra:string", "classes", "memory")
with edit(classes):
    for k, n, cor, desc, regra in CLASSES:
        f = QgsFeature(classes.fields())
        f.setAttributes([k, n, cor, desc, regra])
        classes.addFeature(f)

# Rodada 1 (diagnóstica) como registro: classes mapeadas da versão ANTERIOR à correção da regra R2
rodada1 = QgsVectorLayer("Point?crs=EPSG:31983&field=id:integer&field=classe_mapeada_versao_anterior:integer"
                         "&field=classe_interpretada:integer&field=observacao:string",
                         "pontos_diagnostico_rodada1", "memory")
with open(c("documentacao", "diagnostico_1", "interpretacao_visual.csv"),
          encoding="utf-8") as fh:
    interp1 = {int(r["id"]): r for r in csv.DictReader(fh)}
with edit(rodada1):
    for f in QgsVectorLayer(c("processamento", "pontos_conferencia_rodada1.gpkg"), "r1", "ogr").getFeatures():
        nova = QgsFeature(rodada1.fields())
        nova.setGeometry(f.geometry())
        nova.setAttributes([f["id"], f["classe_mapeada"], int(interp1[f["id"]]["classe_interpretada"]),
                            interp1[f["id"]]["observacao"]])
        rodada1.addFeature(nova)

areas = QgsVectorLayer("None?field=codigo:string&field=classe:string&field=pixels:string&field=area_km2:double"
                       "&field=pct_area_total:double&field=pct_area_terrestre_valida:string",
                       "areas_por_classe", "memory")
with edit(areas):
    with open(c("resultados", "areas_por_classe.csv"), encoding="utf-8") as fh:
        linhas_areas = list(csv.DictReader(fh))
    for r in linhas_areas:
        f = QgsFeature(areas.fields())
        f.setAttributes([r["codigo"], r["classe"], r["pixels"], float(r["area_km2"]),
                         float(r["pct_area_total"]), r["pct_area_terrestre_valida"]])
        areas.addFeature(f)

META = [
    ("titulo", "Classificação Exploratória da Cobertura da Terra por Imagem Sentinel-2 em São Sebastião/SP"),
    ("local", "Maresias, São Sebastião/SP — recorte 3 × 3 km (9,00 km²)"),
    ("imagem", "S2A_MSIL2A_20260417T131301_N0512_R138_T23KMP_20260417T224715.SAFE"),
    ("data_imagem", "2026-04-17 13:13 UTC"),
    ("src", "EPSG:31983 — SIRGAS 2000 / UTM 23S"),
    ("resolucao", "10 m (B11 e NDBI com detalhe efetivo de 20 m, reamostrados por bilinear)"),
    ("metodo", "Classificação exploratória por regras espectrais (NDWI, NDVI, NDBI, B02) e regras de contexto C1–C3; não supervisionada; sem aprendizado de máquina"),
    ("escala_uso", "Interpretação compatível com ~1:25 000 ou menor; não usar para limites de lote"),
    ("conferencia", "Interna exploratória: rodada 2 com 80 pontos estratificados (semente 2027), interpretados visualmente na mesma imagem; não é validação independente. A rodada 1 (semente 2026) foi diagnóstica"),
    ("raster_analitico", "resultados/cobertura_classificada_20260417.tif (o vetor é derivado dele)"),
    ("creditos", "Contém dados Copernicus Sentinel modificados [2026]; IBGE; © colaboradores OpenStreetMap (ODbL), usado só na conferência da linha de costa"),
]
metadados = QgsVectorLayer("None?field=chave:string&field=valor:string", "metadados", "memory")
with edit(metadados):
    for k, v in META:
        f = QgsFeature(metadados.fields())
        f.setAttributes([k, v])
        metadados.addFeature(f)

area_estudo = QgsVectorLayer(c("dados", "area_estudo_maresias.gpkg"), "area_estudo", "ogr")
amostras = QgsVectorLayer(c("processamento", "amostras_calibracao.gpkg"), "amostras_calibracao", "ogr")
if os.path.exists(GPKG):
    os.remove(GPKG)
processing.run("native:package", {
    "LAYERS": [area_estudo, cobertura, camada_pontos, rodada1, amostras, classes, areas, metadados],
    "OUTPUT": GPKG, "OVERWRITE": True, "SAVE_STYLES": False, "SAVE_METADATA": False,
    "SELECTED_FEATURES_ONLY": False})
print("GeoPackage:", GPKG)

# =============================================================================
# 3. Gráfico de área por classe (área terrestre válida)
# =============================================================================
import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

linhas = [r for r in linhas_areas if r["codigo"] and r["pct_area_terrestre_valida"]]
linhas.sort(key=lambda r: float(r["area_km2"]))
cores = {str(k): cor for k, _, cor, *_ in CLASSES}
fig, eixo = plt.subplots(figsize=(8.5, 3.8))
y = range(len(linhas))
eixo.barh(y, [float(r["area_km2"]) for r in linhas], height=0.62,
          color=[cores[r["codigo"]] for r in linhas], edgecolor="#555555", linewidth=0.5)
for i, r in zip(y, linhas):
    eixo.text(float(r["area_km2"]) + 0.06, i, "%s km²  (%s %%)" % (
        ("%.2f" % float(r["area_km2"])).replace(".", ","), r["pct_area_terrestre_valida"].replace(".", ",")),
        va="center", fontsize=9, color="#333333")
eixo.set_yticks(list(y))
eixo.set_yticklabels([r["classe"] for r in linhas], fontsize=9, color="#333333")
eixo.set_xlim(0, 7.4)
eixo.set_xlabel("Área (km²) — percentual sobre a área terrestre válida (7,66 km²)", fontsize=9, color="#555555")
for lado in ("top", "right"):
    eixo.spines[lado].set_visible(False)
for lado in ("left", "bottom"):
    eixo.spines[lado].set_color("#999999")
eixo.tick_params(axis="x", colors="#777777", labelsize=8)
fig.suptitle("Área por classe — Maresias, Sentinel-2 de 17/04/2026 (classificação exploratória)",
             fontsize=10, x=0.01, ha="left", color="#222222")
fig.text(0.01, 0.01, "Excluídos do denominador: água (1,34 km²) e pixels inválidos (0,005 km²).",
         fontsize=7.5, color="#666666")
fig.tight_layout(rect=(0, 0.04, 1, 0.95))
fig.savefig(os.path.join(FIG, "grafico_area_por_classe.png"), dpi=130)
print("Gráfico gravado.")
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
