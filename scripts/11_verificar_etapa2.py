# -*- coding: utf-8 -*-
"""
11_verificar_etapa2.py — Testes técnicos da Etapa 2.

Cada teste é realmente executado; o resultado vai para
documentacao/verificacao_etapa2.txt. Os testes de reprodutibilidade
executam de novo os scripts 06 e 08 e comparam as saídas.

Execução:
  "C:\\Program Files\\QGIS 3.40.8\\bin\\python-qgis-ltr.bat" scripts\\11_verificar_etapa2.py
"""
import csv
import glob
import os
import re
import subprocess
import sys
import zipfile

import numpy as np
from osgeo import gdal, ogr
from scipy import ndimage

gdal.UseExceptions()
PROJETO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(PROJETO)
linhas, falhas = [], []
ND = -9999


def teste(n, ok, texto):
    linhas.append("[%s] %2d. %s" % ("OK   " if ok else "FALHA", n, texto))
    if not ok:
        falhas.append("%d. %s" % (n, texto))


def info(texto):
    linhas.append("           " + texto)


def ler(p, banda=1):
    ds = gdal.Open(p)
    return ds.GetRasterBand(banda).ReadAsArray().astype("float64")


FINAL = "resultados/cobertura_classificada_20260417.tif"
GPKG = "resultados/sao_sebastiao_cobertura.gpkg"
cls = ler(FINAL).astype(int)

# 1. Alinhamento -----------------------------------------------------------
rasters = sorted(glob.glob("processamento/**/*.tif", recursive=True)) + [FINAL]
assin = {(gdal.Open(p).RasterXSize, gdal.Open(p).RasterYSize, gdal.Open(p).GetGeoTransform(),
          gdal.Open(p).GetSpatialRef().GetAuthorityCode(None)) for p in rasters}
teste(1, len(assin) == 1, "Alinhamento: %d rasters na mesma grade %s" % (len(rasters), next(iter(assin))))

# 2. Máscaras ----------------------------------------------------------------
mascara = ler("processamento/02_mascara/mascara_validos_20260417.tif")
teste(2, np.array_equal(cls == 9, mascara == 0) and (cls == 9).sum() == 48,
      "Máscara: classe 9 coincide exatamente com a máscara SCL da Etapa 1 (48 pixels); nenhum recebeu classe temática")

# 3. Índices -----------------------------------------------------------------
R = {b: ler("processamento/03_refletancia/%s_20260417_refletancia.tif" % b) for b in ("B02", "B03", "B04", "B08", "B11")}
ok3, txt = True, []
for nome, a, b in (("NDWI", "B03", "B08"), ("NDBI", "B11", "B08")):
    arq = ler("processamento/%s_20260417.tif" % nome)
    A, B = np.maximum(R[a], 0), np.maximum(R[b], 0)
    validos = (R[a] != ND) & (R[b] != ND) & ((A + B) > 0)
    esperado = np.where(validos, (A - B) / np.where(validos, A + B, 1), ND)
    v = arq[arq != ND]
    ok = np.allclose(arq, esperado, atol=1e-6) and v.min() >= -1 and v.max() <= 1 and np.isfinite(v).all()
    ok3 &= ok
    txt.append("%s recalculado confere; faixa %.3f a %.3f" % (nome, v.min(), v.max()))
ndvi = ler("processamento/NDVI_20260417.tif")
teste(3, ok3, "Índices: " + "; ".join(txt) + "; NDVI da Etapa 1 reutilizado")

# 4. Aplicação dos limiares (regras R0–R5 reproduzidas em numpy) -------------
ndwi, ndbi = ler("processamento/NDWI_20260417.tif"), ler("processamento/NDBI_20260417.tif")
esp = np.where(mascara == 0, 9,
      np.where(ndwi > 0.20, 4,
      np.where((ndvi >= 0.80) | ((ndvi >= 0.75) & (ndbi <= -0.20)), 1,
      np.where(ndvi >= 0.55, 2,
      np.where((R["B02"] >= 0.15) & (ndvi < 0.20) & (ndvi > -1), 5, 3)))))
esp_arq = ler("processamento/04_classificacao/classes_espectrais_regras.tif").astype(int)
teste(4, np.array_equal(esp, esp_arq), "Limiares: raster de regras espectrais idêntico à reprodução independente das regras R0–R5")
rotulo, _ = ndimage.label(cls == 5)
toca = set(np.unique(rotulo[ndimage.binary_dilation(cls == 4, np.ones((3, 3))) & (cls == 5)])) - {0}
coerente = (np.all(esp_arq[cls == 5] == 5) and np.all(np.isin(esp_arq[cls == 6], [2]))
            and np.all(esp_arq[cls == 2] == 2) and len(toca) == rotulo.max())
mudou_c3 = (cls == 1) & (esp_arq != 1)
teste(4, coerente and np.all(esp_arq[mudou_c3] == 2),
      "Regras de contexto: areia só onde a regra espectral deu 5 e toda mancha de areia toca a água; "
      "classes 2 e 6 só vêm de candidatos 2; %d pixels C3 (transição -> arbórea)" % mudou_c3.sum())

# 5–6. Códigos e valores inválidos ------------------------------------------
codigos = set(np.unique(cls).tolist())
teste(5, codigos <= {1, 2, 3, 4, 5, 6, 9} and 0 not in codigos, "Códigos de classe presentes: %s" % sorted(codigos))
teste(6, cls.size == 90000 and np.isfinite(ndwi[ndwi != ND]).all() and np.isfinite(ndbi[ndbi != ND]).all(),
      "Sem NoData dentro da área classificada (90 000 pixels) e sem NaN/infinito nos índices")

# 7–8. Áreas e percentuais ---------------------------------------------------
with open("resultados/areas_por_classe.csv", encoding="utf-8") as fh:
    areas = list(csv.DictReader(fh))
por_cod = {int(r["codigo"]): r for r in areas if r["codigo"]}
ok7 = all(int(por_cod[k]["pixels"]) == int((cls == k).sum()) and
          abs(float(por_cod[k]["area_m2"]) - 100 * (cls == k).sum()) < 1 for k in por_cod)
total_km2 = sum(float(por_cod[k]["area_km2"]) for k in por_cod)
teste(7, ok7 and abs(total_km2 - 9.0) < 1e-6,
      "Áreas: pixels × 100 m² conferem com a tabela; soma das classes e exclusões = %.4f km²" % total_km2)
pct_total = sum(float(por_cod[k]["pct_area_total"]) for k in por_cod)
pct_terra = sum(float(por_cod[k]["pct_area_terrestre_valida"]) for k in por_cod if por_cod[k]["pct_area_terrestre_valida"])
teste(8, abs(pct_total - 100) < 0.05 and abs(pct_terra - 100) < 0.05,
      "Percentuais: soma sobre a área total = %.2f %%; sobre a área terrestre válida = %.2f %%" % (pct_total, pct_terra))

# 9. Coerência espacial --------------------------------------------------------
costa = open("documentacao/conferencia_linha_costa.txt", encoding="utf-8").read()
mediana_osm = float(re.search(r"OSM.*?mediana ([\d.]+) m", costa).group(1))
agua_norte = (cls[:150] == 4).sum()
floresta_norte = (cls[:100] == 1).mean()
teste(9, mediana_osm <= 10 and agua_norte == 0 and floresta_norte > 0.8,
      "Coerência espacial: costa espectral a %.1f m (mediana) da costa OSM; %d pixel de água na metade norte; "
      "%.0f %% de arbórea no terço norte (encosta)" % (mediana_osm, agua_norte, 100 * floresta_norte))

# 10. Integridade do raster ----------------------------------------------------
ds = gdal.Open(FINAL)
b = ds.GetRasterBand(1)
teste(10, gdal.GetDataTypeName(b.DataType) == "Byte" and b.GetNoDataValue() == 0
      and b.GetColorTable() is not None and b.GetCategoryNames()[1] == "Vegetação arbórea"
      and b.Checksum() >= 0,
      "Raster final: Byte, NoData 0, tabela de cores e nomes de classe gravados, leitura completa sem erro")

# 11–13. GeoPackage, SRC e geometrias ------------------------------------------
g = ogr.Open(GPKG)
camadas = {g.GetLayer(i).GetName(): g.GetLayer(i) for i in range(g.GetLayerCount())}
esperadas = {"area_estudo", "cobertura_poligonos", "pontos_conferencia", "pontos_diagnostico_rodada1",
             "amostras_calibracao", "classes", "areas_por_classe", "metadados"}
teste(11, esperadas <= set(camadas), "GeoPackage com as camadas: %s" % ", ".join(sorted(camadas)))
src = {n: (l.GetSpatialRef().GetAuthorityCode(None) if l.GetSpatialRef() else "tabela") for n, l in camadas.items()}
teste(12, all(v in ("31983", "tabela") for v in src.values()) and ds.GetSpatialRef().GetAuthorityCode(None) == "31983",
      "SRC: todas as camadas espaciais e o raster em EPSG:31983")
validas, vazias, area_vet = True, 0, {}
for nome in ("area_estudo", "cobertura_poligonos", "amostras_calibracao"):
    for f in camadas[nome]:
        geom = f.GetGeometryRef()
        validas &= geom is not None and geom.IsValid()
        vazias += geom is None or geom.IsEmpty()
        if nome == "cobertura_poligonos":
            area_vet[f.GetField("classe")] = geom.GetArea()
dif = max(abs(area_vet[k] - 100 * (cls == k).sum()) for k in area_vet)
teste(13, validas and vazias == 0 and dif < 1,
      "Geometrias válidas e não vazias; área dos polígonos por classe = área do raster (diferença máx. %.3f m²)" % dif)

# 14. Pontos de conferência ----------------------------------------------------
pts = [(f.GetField("id"), f.GetGeometryRef().GetX(), f.GetGeometryRef().GetY(), f.GetField("classe_mapeada"),
        f.GetField("classe_interpretada")) for f in camadas["pontos_conferencia"]]
amostras = [f.GetGeometryRef().Clone() for f in camadas["amostras_calibracao"]]
dentro_amostra = sum(any(a.Contains(ogr.CreateGeometryFromWkt("POINT (%f %f)" % (x, y))) for a in amostras)
                     for _, x, y, _, _ in pts)
gt = ds.GetGeoTransform()
classe_no_ponto = all(cls[int((y - gt[3]) / gt[5]), int((x - gt[0]) / gt[1])] == m for _, x, y, m, _ in pts)
contagem = {k: sum(1 for p in pts if p[3] == k) for k in (1, 2, 3, 4, 5, 6)}
dist_min = min(np.hypot(a[1] - b[1], a[2] - b[2]) for i, a in enumerate(pts) for b in pts[i + 1:] if a[3] == b[3])
teste(14, len(pts) == 80 and sorted(p[0] for p in pts) == list(range(1, 81)) and dentro_amostra == 0
      and classe_no_ponto and contagem == {1: 20, 2: 10, 3: 18, 4: 8, 5: 8, 6: 16} and dist_min >= 20,
      "Pontos: 80, ids 1–80, %s por classe, nenhum dentro das amostras de calibração, classe mapeada = "
      "raster no ponto, distância mínima na mesma classe %.1f m" % (contagem, dist_min))

# 15. Conferência visual ---------------------------------------------------------
with open("documentacao/diagnostico_2/interpretacao_visual.csv", encoding="utf-8") as fh:
    interp = {int(r["id"]): int(r["classe_interpretada"]) for r in csv.DictReader(fh)}
concord = sum(1 for p in pts if p[3] == p[4])
with open("documentacao/diagnostico_2/matriz_conferencia_interna.csv", encoding="utf-8") as fh:
    matriz = list(csv.reader(fh))
teste(15, len(interp) == 80 and all(interp[p[0]] == p[4] for p in pts) and int(matriz[-1][-2]) == concord,
      "Conferência: 80 interpretações registradas, iguais às do GeoPackage; concordância recalculada %d/80 "
      "= matriz" % concord)

# 16–17. Projeto QGIS -------------------------------------------------------------
from qgis.core import QgsApplication, QgsProject  # noqa: E402
app = QgsApplication([], False)
app.initQgis()
projeto = QgsProject.instance()
ARQ = "processamento/sao_sebastiao_cobertura.qgz"
abriu = projeto.read(ARQ)
invalidas = [l.name() for l in projeto.mapLayers().values() if not l.isValid()]
grupos = [g.name() for g in projeto.layerTreeRoot().children()]
layouts = [l.name() for l in projeto.layoutManager().printLayouts()]
teste(16, abriu and not invalidas and len(grupos) == 6 and len(layouts) == 5,
      "Projeto abre com %d camadas válidas, grupos %s e %d layouts" % (len(projeto.mapLayers()), grupos, len(layouts)))
with zipfile.ZipFile(ARQ) as z:
    qgs = z.read([n for n in z.namelist() if n.endswith(".qgs")][0]).decode("utf-8")
fontes = [f for f in re.findall(r"<datasource>(.*?)</datasource>", qgs) if f]
teste(17, all(f.startswith(("../", "./")) for f in fontes) and "C:/" not in qgs and "Users" not in qgs,
      "Caminhos relativos: %d fontes de dados, todas iniciando por ../ ou ./" % len(fontes))

# 18. Reprodutibilidade ------------------------------------------------------------
# Libera os arquivos abertos neste processo: no Windows, um arquivo aberto não pode
# ser apagado pelo script 06, que recria as saídas.
projeto.clear()
b = ds = g = None
antes_cls = cls.copy()
antes_pts = sorted((p[0], round(p[1], 2), round(p[2], 2)) for p in pts)
amb = dict(os.environ)
r06 = subprocess.run([sys.executable, "scripts/06_classificar.py"], capture_output=True, env=amb)
depois_cls = ler(FINAL).astype(int)
r08 = subprocess.run([sys.executable, "scripts/08_pontos_conferencia.py"], capture_output=True, env=amb)
g2 = ogr.Open("processamento/pontos_conferencia_rodada2.gpkg")
depois_pts = sorted((f.GetField("id"), round(f.GetField("x_31983"), 2), round(f.GetField("y_31983"), 2))
                    for f in g2.GetLayer())
if r06.returncode or r08.returncode:
    info((r06.stderr + r08.stderr).decode("utf-8", "replace")[-600:])
teste(18, r06.returncode == 0 and r08.returncode == 0 and np.array_equal(antes_cls, depois_cls)
      and antes_pts == depois_pts,
      "Reprodutibilidade: 06 e 08 executados de novo; classificação idêntica pixel a pixel e os mesmos 80 pontos (semente 2027)")

# 19. Organização ------------------------------------------------------------------
obrigatorios = [FINAL, GPKG, "resultados/areas_por_classe.csv", "resultados/figuras/mapa_classificacao.png",
                "resultados/figuras/mapa_sentinel2_cor_verdadeira.png", "resultados/figuras/grafico_area_por_classe.png",
                "processamento/NDWI_20260417.tif", "processamento/NDBI_20260417.tif",
                "documentacao/estatisticas_amostras.csv", "documentacao/conferencia_linha_costa.txt",
                "documentacao/diagnostico_2/interpretacao_visual.csv",
                "documentacao/diagnostico_1/interpretacao_visual.csv",
                "dados/osm_coastline_overpass.json"]
faltando = [p for p in obrigatorios if not os.path.exists(p)]
pastas = sorted(d for d in os.listdir(".") if os.path.isdir(d))
teste(19, not faltando and pastas == ["dados", "documentacao", "processamento", "resultados", "scripts"],
      "Organização: arquivos esperados presentes; pastas de primeiro nível %s" % pastas)

# 20. Ausência de resultados fictícios ------------------------------------------------
readme = open("README.pt.md", encoding="utf-8").read()
valores = ["%.2f" % float(por_cod[k]["area_km2"]) for k in (1, 2, 3, 4, 5, 6)]
no_readme = all(v.replace(".", ",") in readme for v in valores)
teste(20, ok7 and len(interp) == 80 and no_readme and ("%d/80" % concord in readme or "%d de 80" % concord in readme),
      "Sem números fictícios: áreas do README (%s km²) e concordância %d/80 vêm do raster e da tabela de conferência"
      % (", ".join(v.replace(".", ",") for v in valores), concord))

with open("documentacao/verificacao_etapa2.txt", "w", encoding="utf-8") as fh:
    fh.write("Verificação automática — Etapa 2 (classificação exploratória)\n\n" + "\n".join(linhas) + "\n\n")
    fh.write("Resultado: %s\n" % ("todos os testes passaram" if not falhas else "%d falha(s)" % len(falhas)))
print("\n".join(linhas))
print("FALHAS:", falhas)
app.exitQgis()
