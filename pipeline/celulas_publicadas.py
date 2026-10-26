#!/usr/bin/env python3
"""As células da grade de 0,05° do crédito por imóvel que já foram publicadas (no git, no
Pages e na release v2026.10.26), tiradas de cada versão do bloco `imovel` no histórico e
levadas ao beelink, para a etapa `grade` de baixa_imovel.py cortar a célula de 0,25° cuja
diferença contra elas revelaria uma célula de 0,05° cortada.

    python3 celulas_publicadas.py   # grava ~/bragro_tmp/imovel/grade_005_publicada.parquet

Lê o formato binário antigo do bloco (u32 tamanho | cabeçalho JSON | arrays com os bytes em
planos), o de antes dos .json.gz. Saída: k (ccar, desm), i, j (célula de 0,05°), ano.
"""
import gzip
import json
import subprocess
import tempfile

import numpy as np
import polars as pl

from beelink import REMOTO

TIPOS = {"u8": np.uint8, "i8": np.int8, "u16": np.uint16, "i16": np.int16, "u32": np.uint32, "i32": np.int32}


def arrays(gz):
    b = gzip.decompress(gz)
    n = int.from_bytes(b[:4], "little")
    cab = json.loads(b[4:4 + n])
    A = {}
    for nome, d in cab["arrays"].items():
        dt = np.dtype(TIPOS[d["t"]])
        cru = np.frombuffer(b, np.uint8, d["n"] * dt.itemsize, 4 + n + d["o"])
        A[nome] = cru.reshape(dt.itemsize, d["n"]).T.copy().view(dt).ravel()
    for nome in cab["meta"].get("delta", []):
        A[nome] = np.cumsum(A[nome].astype(np.int64)).astype(A[nome].dtype)
    return A, cab["meta"]


git = lambda *a: subprocess.run(["git", *a], capture_output=True, check=True).stdout
caminhos = {p for p in git("log", "--all", "--format=", "--name-only", "--", "../site/dados/imovel.*.bin").decode().split()}
partes = []
for p in sorted(caminhos):
    rev = git("rev-list", "--all", "-1", "--", "../" + p).decode().strip()
    # o arquivo some no commit que o troca: o blob está no pai do primeiro commit sem ele
    blob = subprocess.run(["git", "cat-file", "blob", f"{rev}:{p}"], capture_output=True)
    if blob.returncode:
        blob = subprocess.run(["git", "cat-file", "blob", f"{rev}^:{p}"], capture_output=True, check=True)
    A, meta = arrays(blob.stdout)
    if meta.get("passo") != 0.05:   # antes da grade, ou a de 0,25° (que não foi publicada)
        continue
    for g, k in (("g_ccar", "ccar"), ("g_cd", "desm")):
        if g + "_i" in A:
            partes.append(pl.DataFrame({"k": k, "i": A[g + "_i"].view(np.int16).astype(np.int32),
                                        "j": A[g + "_j"].view(np.int16).astype(np.int32),
                                        "ano": A[g + "_a"].astype(np.int32) + 2000}))
    print(p, {g: len(A[g + "_i"]) for g in ("g_ccar", "g_cd") if g + "_i" in A})
df = pl.concat(partes).unique().sort(["k", "ano", "j", "i"])
print(df.group_by("k").len().sort("k"))
with tempfile.NamedTemporaryFile(suffix=".parquet") as t:
    df.write_parquet(t.name)
    subprocess.run(["scp", "-q", t.name, f"beelink:{REMOTO}/imovel/grade_005_publicada.parquet"], check=True)
