"""Fração de cada classe do MapBiomas (coleção 10, 30 m) dentro de cada imóvel do CAR.
Roda NO beelink, em ~/scrap_tmp/mapbiomas_raster/, que é para onde estes três arquivos
são copiados (como zonal.py, baixa.sh e roda.sh):

    ~/.local/bin/uv venv venv && ~/.local/bin/uv pip install --python venv/bin/python \
        exactextract rasterio geopandas pyogrio numpy pyarrow   # o beelink não tem python3-venv
    bash baixa.sh                    # os .tif de 2016–2024 (~780 MB cada)
    bash roda.sh                     # cada ano, 8 UFs em paralelo (2026-10-26: ~9 h ao todo)
    venv/bin/python zonal.py <ano> [UF ...]   # um ano ou uma UF à mão

Entrada: brazil_coverage_<ano>.tif e os polígonos de ~/bragro_tmp/imovel/car, exportados
por UF em FlatGeobuf. Saída: ~/bragro_tmp/imovel/mapbiomas/ano=<ano>/<UF>.parquet com
id_imovel e a fração do imóvel em floresta (3), pastagem (15), soja (39) e agropecuária
(nível 1 = 3). Fica no beelink: o Chão só recebe somas por município (baixa_imovel.py,
etapa mapbiomas).
"""
import os
import subprocess
import sys
import time

import geopandas as gpd
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from exactextract import exact_extract

D = os.path.expanduser("~/scrap_tmp/mapbiomas_raster")
CAR = "/home/polo/bragro_tmp/imovel/car"
OUT = "/home/polo/bragro_tmp/imovel/mapbiomas"
# agropecuária da coleção 10: pastagem, agricultura (temporária e perene) e silvicultura, e o mosaico
AGRO = [9, 15, 18, 19, 20, 21, 35, 36, 39, 40, 41, 46, 47, 48, 62]

ano = sys.argv[1]
ufs = sys.argv[2:] or sorted(p.split("=")[1] for p in os.listdir(CAR))
tif = f"{D}/brazil_coverage_{ano}.tif"

for uf in ufs:
    dst = f"{OUT}/ano={ano}/{uf}.parquet"
    if os.path.exists(dst):
        continue
    fgb = f"{D}/car_{uf}.fgb"   # só polígonos: o ST_MakeValid deixou coleções mistas
    if not os.path.exists(fgb):
        sql = (f"LOAD spatial; SET geometry_always_xy = true; COPY (SELECT id_imovel, ST_Multi(ST_CollectionExtract(geometria, 3)) geometria "
               f"FROM read_parquet('{CAR}/sigla_uf={uf}/*.parquet') WHERE status <> 'CA') TO '{fgb}' WITH (FORMAT GDAL, DRIVER 'FlatGeobuf', SRS 'EPSG:4326');")
        subprocess.run(["/home/polo/bin/duckdb", "-c", sql], check=True, capture_output=True)
    t = time.time()
    gdf = gpd.read_file(fgb, engine="pyogrio")   # o exactextract sem GDAL do Python não abre o caminho
    # nesta versão (0.3), unique e frac vêm como listas por imóvel: classe e fração dela
    df = exact_extract(tif, gdf, ["unique", "frac"], include_cols=["id_imovel"], output="pandas")
    n = len(df)
    lens = df["unique"].map(len).to_numpy()
    row = np.repeat(np.arange(n), lens)
    cls = np.concatenate(df["unique"].to_numpy()) if n else np.array([], int)
    fr = np.concatenate(df["frac"].to_numpy()) if n else np.array([])
    soma = lambda classes: np.bincount(row, weights=np.where(np.isin(cls, classes), fr, 0.0), minlength=n)
    tab = pa.table({"id_imovel": df["id_imovel"], "f_floresta": soma([3]), "f_pastagem": soma([15]),
                    "f_soja": soma([39]), "f_agro": soma(AGRO)})
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    pq.write_table(tab, dst + ".tmp", compression="zstd")
    os.replace(dst + ".tmp", dst)
    print(f"{ano} {uf}: {n:,} imóveis em {time.time() - t:.0f} s", flush=True)
