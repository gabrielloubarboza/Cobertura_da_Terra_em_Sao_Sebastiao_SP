# -*- coding: utf-8 -*-
"""
04_verificar_etapa1.py — Testes de verificação da Etapa 1.

Reabre o projeto QGIS, confere camadas, caminhos, grades, máscaras e o NDVI,
e exporta imagens PNG das camadas (documentacao/figuras/) para inspeção visual.
O resultado é gravado em documentacao/verificacao_etapa1.txt.

Execução:
  "C:\\Program Files\\QGIS 3.40.8\\bin\\python-qgis-ltr.bat" scripts\\04_verificar_etapa1.py
"""
import glob
import json
import os
import re
import zipfile

import numpy as np
from osgeo import gdal, ogr
from qgis.PyQt.QtCore import QSize
from qgis.PyQt.QtGui import QColor
from qgis.core import (
    QgsApplication, QgsMapRendererParallelJob, QgsMapSettings, QgsProject, QgsRectangle,
)

gdal.UseExceptions()
PROJETO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARQ_PROJETO = os.path.join(PROJETO, "qgis", "sao_sebastiao_cobertura.qgz")
FIG = os.path.join(PROJETO, "documentacao", "figuras")
NODATA = -9999
linhas = []
falhas = []


def c(*p):
    return os.path.join(PROJETO, *p)


def registro(ok, texto):
    linhas.append(("[OK]    " if ok else "[FALHA] ") + texto)
    if not ok:
        falhas.append(texto)


def ler(caminho, banda=1):
    ds = gdal.Open(caminho)
    b = ds.GetRasterBand(banda)
    return b.ReadAsArray().astype("float64"), b.GetNoDataValue(), ds.GetGeoTransform(), ds


app = QgsApplication([], False)
app.initQgis()

# 1–2. Origem e identificação da cena ---------------------------------------
item = json.load(open(c("dados", "sentinel2_original", "metadados",
                        "S2A_T23KMP_20260417T131303_L2A_stac_item.json"), encoding="utf-8"))
mtd = open(c("dados", "sentinel2_original", "metadados", "MTD_MSIL2A_product_metadata.xml"),
           encoding="utf-8").read()
uri = re.search(r"<PRODUCT_URI>(.*?)</PRODUCT_URI>", mtd).group(1)
registro(uri == item["properties"]["s2:product_uri"],
         "Produto identificado nos metadados oficiais: " + uri)
originais = sorted(glob.glob(c("dados", "sentinel2_original", "*_original.tif")))
registro(len(originais) == 6, "6 recortes originais presentes (B02, B03, B04, B08, B11, SCL)")

# 5. Coerência de datas: todos os arquivos vêm do mesmo produto/data
manifesto = json.load(open(c("dados", "fontes_manifesto.json"), encoding="utf-8"))
origens = [a["origem"] for a in manifesto["arquivos"] if "sentinel" in a["origem"]]
registro(all("S2A_T23KMP_20260417T131303_L2A" in o for o in origens),
         "Todas as bandas pertencem à mesma cena/data (17/04/2026)")

# 4. Integridade das bandas (abrem, têm estatística e não estão vazias)
for f in originais:
    a, nd, gt, ds = ler(f)
    registro(ds.RasterXSize > 0 and np.count_nonzero(a != nd) > 0,
             "Integridade %s: %dx%d px, %.0f m" % (os.path.basename(f), ds.RasterXSize,
                                                  ds.RasterYSize, gt[1]))

# 6–8. Grade, extensão e SRC dos produtos ------------------------------------
ref = None
for f in sorted(glob.glob(c("processamento", "**", "*.tif"), recursive=True)):
    ds = gdal.Open(f)
    assinatura = (ds.RasterXSize, ds.RasterYSize, ds.GetGeoTransform(),
                  ds.GetSpatialRef().GetAuthorityCode(None))
    ref = ref or assinatura
    registro(assinatura == ref and assinatura[3] == "31983",
             "Grade/SRC %s: %s" % (os.path.relpath(f, PROJETO), assinatura))
o = gdal.Open(c("dados", "sentinel2_original", "S2A_20260417_T23KMP_B04_original.tif")).ReadAsArray()
w = gdal.Open(c("processamento", "01_recorte_10m", "B04_20260417_31983_10m.tif")).ReadAsArray()
registro(np.array_equal(o[100:400, 100:400], w),
         "Reprojeção 32723->31983 sem reamostragem efetiva: B04 recortada idêntica ao original")

def primeira_geometria(caminho):
    ds = ogr.Open(caminho)  # manter a fonte aberta enquanto a camada é lida
    feicao = ds.GetLayer().GetNextFeature()
    return feicao.GetGeometryRef().Clone()


geom_area = primeira_geometria(c("dados", "area_estudo", "area_estudo_maresias.gpkg"))
geom_mun = primeira_geometria(c("dados", "contexto", "municipio_sao_sebastiao_ibge2024.gpkg"))
terra = geom_area.Intersection(geom_mun).GetArea() / 1e6
registro(abs(geom_area.GetArea() / 1e6 - 9.0) < 1e-6, "Área de estudo = 9,000 km² (3 × 3 km), EPSG:31983")
registro(terra > 6, "Parte terrestre da área de estudo dentro de São Sebastião (IBGE): %.2f km²" % terra)
ds_bio = ogr.Open(c("dados", "contexto", "bioma_ibge2025_sao_sebastiao.gpkg"))
nomes = set()
for f in ds_bio.GetLayer():
    if f.GetGeometryRef().Intersects(geom_area):
        nomes.add(f.GetField("NM_BIOMA"))
registro(nomes == {"Mata Atlântica"}, "Bioma IBGE 2025 na área de estudo: %s" % ", ".join(sorted(nomes)))

# 13. Máscara e SCL -----------------------------------------------------------
scl, _, _, _ = ler(c("processamento", "01_recorte_10m", "SCL_20260417_31983_10m.tif"))
msk, _, _, _ = ler(c("processamento", "02_mascara", "mascara_validos_20260417.tif"))
invalidas = [0, 1, 3, 8, 9, 10, 11]
registro(np.array_equal(msk == 0, np.isin(scl, invalidas)), "Máscara = classes SCL %s" % invalidas)
v, n = np.unique(scl, return_counts=True)
dist = {int(a): round(100 * b / scl.size, 2) for a, b in zip(v, n)}
linhas.append("        Distribuição SCL na área (%%): %s" % dist)
linhas.append("        Pixels inválidos: %d de %d (%.3f %%)" % ((msk == 0).sum(), msk.size,
                                                          100 * (msk == 0).mean()))
linhas.append("        Água (SCL 6): %.2f km²; área não-água válida: %.2f km²" % (
    (scl == 6).sum() * 1e-4, ((scl != 6) & (msk == 1)).sum() * 1e-4))

# 11–12. NDVI -----------------------------------------------------------------
pilha = c("processamento", "S2A_20260417_refletancia_B02_B03_B04_B08_B11.tif")
b04, nd, _, _ = ler(pilha, 3)
b08, _, _, _ = ler(pilha, 4)
ndvi, nd_ndvi, _, _ = ler(c("processamento", "NDVI_20260417.tif"))
validos = (b04 != NODATA) & (b08 != NODATA) & (b04 > 0) & (b08 > 0)
esperado = np.where(validos, (b08 - b04) / (b08 + b04), NODATA)
registro(np.allclose(ndvi, esperado, atol=1e-6), "NDVI recalculado a partir da pilha confere com o arquivo")
nv = ndvi[ndvi != nd_ndvi]
registro(nv.min() >= -1 and nv.max() <= 1 and np.isfinite(nv).all(),
         "NDVI no intervalo [-1, 1], sem infinitos/NaN: min %.4f, max %.4f, média %.4f" % (
             nv.min(), nv.max(), nv.mean()))
registro(np.all(ndvi[msk == 0] == nd_ndvi), "NDVI é NoData em todos os pixels mascarados")
linhas.append("        NDVI válido: %d px; percentis 2/25/50/75/98: %s" % (
    nv.size, np.round(np.percentile(nv, [2, 25, 50, 75, 98]), 3).tolist()))
linhas.append("        NDVI mediano por classe SCL: " + str({
    k: round(float(np.median(ndvi[(scl == k) & (ndvi != nd_ndvi)])), 3)
    for k in (4, 5, 6) if ((scl == k) & (ndvi != nd_ndvi)).any()}))
for i, nome in enumerate(["B02", "B03", "B04", "B08", "B11"], start=1):
    a, nd, _, _ = ler(pilha, i)
    a = a[a != nd]
    registro(-0.01 < a.min() and a.max() < 1.2,
             "Reflectância %s: %.4f a %.4f (média %.4f)" % (nome, a.min(), a.max(), a.mean()))

# 14–15. Projeto QGIS ---------------------------------------------------------
projeto = QgsProject.instance()
registro(projeto.read(ARQ_PROJETO), "Projeto QGIS abre: " + os.path.relpath(ARQ_PROJETO, PROJETO))
registro(projeto.crs().authid() == "EPSG:31983", "SRC do projeto: " + projeto.crs().authid())
for camada in projeto.mapLayers().values():
    registro(camada.isValid(), "Camada válida: " + camada.name())
with zipfile.ZipFile(ARQ_PROJETO) as z:
    qgs = z.read([n for n in z.namelist() if n.endswith(".qgs")][0]).decode("utf-8")
# fontes vazias = camada interna de anotações do QGIS (não aponta para arquivo)
fontes = [f for f in re.findall(r"<datasource>(.*?)</datasource>", qgs) if f]
registro(all(f.startswith("../") or f.startswith("./") for f in fontes) and "C:/" not in qgs and "Users" not in qgs,
         "Caminhos relativos no projeto: " + "; ".join(sorted(set(fontes))))

# Figuras para inspeção visual ------------------------------------------------
os.makedirs(FIG, exist_ok=True)
por_nome = {lyr.name(): lyr for lyr in projeto.mapLayers().values()}


def camada(prefixo):
    return next(lyr for n, lyr in por_nome.items() if n.startswith(prefixo))


def exportar(arquivo, prefixos, extensao, largura=900):
    ms = QgsMapSettings()
    ms.setLayers([camada(p) for p in prefixos])
    ms.setDestinationCrs(projeto.crs())
    ms.setExtent(extensao)
    altura = round(largura * extensao.height() / extensao.width())
    ms.setOutputSize(QSize(largura, altura))
    ms.setBackgroundColor(QColor("white"))
    job = QgsMapRendererParallelJob(ms)
    job.start()
    job.waitForFinished()
    job.renderedImage().save(os.path.join(FIG, arquivo))


aoi = QgsRectangle(440940, 7368140, 443940, 7371140)
exportar("01_cor_verdadeira.png", ["Limite", "Cor verdadeira"], aoi)
exportar("02_falsa_cor_nir.png", ["Limite", "Falsa-cor"], aoi)
exportar("03_ndvi.png", ["Limite", "NDVI"], aoi)
exportar("04_scl_mascara.png", ["Limite", "Máscara", "SCL"], aoi)
exportar("05_contexto_bioma_municipio.png", ["Limite", "Município", "Bioma"],
         QgsRectangle(410000, 7355000, 464000, 7388000), largura=1200)
linhas.append("        Figuras exportadas em documentacao/figuras/ (renderizadas a partir do projeto)")

with open(c("documentacao", "verificacao_etapa1.txt"), "w", encoding="utf-8") as f:
    f.write("Verificação automática — Etapa 1\n\n" + "\n".join(linhas) + "\n\n")
    f.write("Resultado: %s\n" % ("todos os testes passaram" if not falhas else
                                 "%d falha(s)" % len(falhas)))
print("\n".join(linhas))
print("FALHAS:", falhas)
# Libera os objetos do QGIS e do GDAL ainda referenciados ANTES de encerrar o QGIS;
# caso contrário, eles são destruídos depois dele e o processo termina com erro.
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
