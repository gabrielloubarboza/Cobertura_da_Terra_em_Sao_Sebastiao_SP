# -*- coding: utf-8 -*-
"""
00_triagem_cenas.py — Triagem das cenas Sentinel-2 L2A candidatas.

Por que existe: a porcentagem de nuvens informada para a cena inteira
(110 × 110 km) não descreve as condições locais. Este script lê apenas a
banda SCL numa janela de 8 × 8 km em torno de Maresias e calcula a fração
de nuvem, sombra de nuvem e cirro (classes 3, 8, 9, 10) e de área escura /
sombra topográfica (classe 2) em cada cena candidata.

Busca: catálogo STAC Earth Search (espelho público dos produtos L2A na AWS),
coleção sentinel-2-c1-l2a, abril/2025 a outubro/2026, nuvem da cena < 15 %.

Execução:
  "C:\\Program Files\\QGIS 3.40.8\\bin\\python-qgis-ltr.bat" scripts\\00_triagem_cenas.py

Equivalente na interface: abrir o Copernicus Browser, filtrar Sentinel-2 L2A
por nuvens e inspecionar visualmente a camada "Scene classification" sobre a área.
"""
import json
import urllib.request

import numpy as np
from osgeo import gdal

gdal.UseExceptions()
gdal.SetConfigOption("AWS_NO_SIGN_REQUEST", "YES")
gdal.SetConfigOption("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")

STAC = "https://earth-search.aws.element84.com/v1/search"
# Centro aproximado de Maresias em EPSG:32723 (lon −45,563; lat −23,787)
CX, CY = 442642, 7369242
JANELA = [CX - 4000, CY + 4000, CX + 4000, CY - 4000]

consulta = {
    "collections": ["sentinel-2-c1-l2a"],
    "intersects": {"type": "Point", "coordinates": [-45.565, -23.785]},
    "datetime": "2025-04-01T00:00:00Z/2026-10-26T23:59:59Z",
    "query": {"eo:cloud_cover": {"lt": 15}},
    "limit": 100,
}
req = urllib.request.Request(STAC, data=json.dumps(consulta).encode(),
                             headers={"Content-Type": "application/json"})
cenas = json.load(urllib.request.urlopen(req))["features"]

print("data        nuvem_cena%  nuvem_local%  sombra_topo%  elev_solar  produto")
for cena in sorted(cenas, key=lambda f: f["properties"]["datetime"]):
    p = cena["properties"]
    ds = gdal.Translate("/vsimem/scl.tif", "/vsicurl/" + cena["assets"]["scl"]["href"], projWin=JANELA)
    scl = ds.ReadAsArray()
    ds = None
    local = 100 * np.isin(scl, [3, 8, 9, 10]).mean()
    topo = 100 * (scl == 2).mean()
    print("%s  %10.2f  %12.2f  %12.2f  %10.1f  %s" % (
        p["datetime"][:10], p["eo:cloud_cover"], local, topo,
        p.get("view:sun_elevation", float("nan")), p.get("s2:product_uri")))
