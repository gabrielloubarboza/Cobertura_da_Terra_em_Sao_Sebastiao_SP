# -*- coding: utf-8 -*-
"""
01_obter_dados.py — Aquisição dos dados de origem (Etapa 1).

O que faz:
  1. Baixa SOMENTE a janela de interesse (área de estudo + 1 km de margem) das
     bandas B02, B03, B04, B08, B11 e SCL da cena Sentinel-2 L2A escolhida.
     Os valores dos pixels (DN) e a projeção original (EPSG:32723) não são
     alterados: é um recorte do arquivo oficial, nada mais.
  2. Baixa os metadados da cena (item STAC, MTD do produto e do grânulo).
  3. Baixa os vetores oficiais do IBGE (Biomas 2025 e municípios de SP 2024).
  4. Grava um manifesto (fontes_manifesto.json) com URL, tamanho e MD5 de cada arquivo.

Como executar (Windows, QGIS 3.40 LTR):
  "C:\\Program Files\\QGIS 3.40.8\\bin\\python-qgis-ltr.bat" scripts\\01_obter_dados.py

Equivalente na interface do QGIS:
  - Camada > Adicionar camada > Raster > Origem "Protocolo HTTP(S)", colar a URL
    do arquivo .tif (Cloud Optimized GeoTIFF) listada abaixo.
  - Raster > Extração > Recortar raster pela extensão (gdal_translate -projwin),
    informando a extensão em EPSG:32723 e salvando em dados/sentinel2_original/.
  - Os .zip do IBGE podem ser baixados pelo navegador e abertos por arrastar e soltar.
"""
import hashlib
import json
import os
import urllib.request

from osgeo import gdal

gdal.UseExceptions()
# Leitura anônima de arquivos COG públicos na AWS (sem credenciais)
gdal.SetConfigOption("AWS_NO_SIGN_REQUEST", "YES")
gdal.SetConfigOption("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")

PROJETO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR_S2 = os.path.join(PROJETO, "dados", "sentinel2_original")
DIR_META = os.path.join(DIR_S2, "metadados")
DIR_IBGE = os.path.join(PROJETO, "dados", "contexto", "ibge_original")

# --- Cena escolhida (ver documentacao/FONTES_E_DECISOES.md) -------------------
ITEM_ID = "S2A_T23KMP_20260417T131303_L2A"
STAC_ITEM = ("https://earth-search.aws.element84.com/v1/collections/"
             "sentinel-2-c1-l2a/items/" + ITEM_ID)
BASE = ("https://e84-earth-search-sentinel-data.s3.us-west-2.amazonaws.com/"
        "sentinel-2-c1-l2a/23/K/MP/2026/4/" + ITEM_ID + "/")
BANDAS = ["B02", "B03", "B04", "B08", "B11", "SCL"]

# Janela de download em EPSG:32723 (WGS 84 / UTM 23S, projeção nativa do tile):
# área de estudo (440940–443940 E; 7368140–7371140 N) + 1 km de margem.
# Coordenadas múltiplas de 20 m => coincidem com a grade de 10 m e de 20 m.
JANELA = [439940, 7372140, 444940, 7367140]  # [xmin, ymax, xmax, ymin]

IBGE = {
    "biomas_2025_250mil.zip":
        "https://geoftp.ibge.gov.br/informacoes_ambientais/estudos_ambientais/"
        "biomas/vetores/2025_Biomas-e-Sistema-Costeiro-Marinho-do-Brasil-1-250000_shp.zip",
    "SP_Municipios_2024.zip":
        "https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/"
        "malhas_municipais/municipio_2024/UFs/SP/SP_Municipios_2024.zip",
}


def md5(caminho):
    h = hashlib.md5()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def baixar(url, destino):
    if not os.path.exists(destino):
        print("  baixando", url)
        urllib.request.urlretrieve(url, destino)
    return destino


def main():
    for d in (DIR_S2, DIR_META, DIR_IBGE):
        os.makedirs(d, exist_ok=True)
    manifesto = {"cena": ITEM_ID, "janela_epsg32723": JANELA, "arquivos": []}

    # 1. Metadados da cena
    baixar(STAC_ITEM, os.path.join(DIR_META, ITEM_ID + "_stac_item.json"))
    baixar(BASE + "product_metadata.xml", os.path.join(DIR_META, "MTD_MSIL2A_product_metadata.xml"))
    baixar(BASE + "metadata.xml", os.path.join(DIR_META, "MTD_TL_granule_metadata.xml"))

    # 2. Recorte das bandas (DN originais, sem reprojeção nem reamostragem)
    for banda in BANDAS:
        url = BASE + banda + ".tif"
        saida = os.path.join(DIR_S2, "S2A_20260417_T23KMP_%s_original.tif" % banda)
        if not os.path.exists(saida):
            print("  recortando", banda)
            gdal.Translate(saida, "/vsicurl/" + url, projWin=JANELA,
                           creationOptions=["COMPRESS=DEFLATE", "TILED=YES"])
        manifesto["arquivos"].append({"arquivo": os.path.relpath(saida, PROJETO).replace(os.sep, "/"),
                                      "origem": url, "md5": md5(saida),
                                      "bytes": os.path.getsize(saida)})

    # 3. Vetores do IBGE (arquivos oficiais preservados como .zip)
    for nome, url in IBGE.items():
        saida = baixar(url, os.path.join(DIR_IBGE, nome))
        manifesto["arquivos"].append({"arquivo": os.path.relpath(saida, PROJETO).replace(os.sep, "/"),
                                      "origem": url, "md5": md5(saida),
                                      "bytes": os.path.getsize(saida)})

    with open(os.path.join(PROJETO, "dados", "fontes_manifesto.json"), "w", encoding="utf-8") as f:
        json.dump(manifesto, f, indent=2, ensure_ascii=False)
    print("Concluído.")


if __name__ == "__main__":
    main()
