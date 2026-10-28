#!/usr/bin/env python3
"""O que versões antigas do bloco `imovel` já publicaram (no git, no Pages e na release
v2026.10.26) e que, subtraído do que se publica hoje, revelaria um grupo cortado.

1. As células da grade de 0,05°, levadas ao beelink para a etapa `grade` de
   baixa_imovel.py cortar a célula de 0,25° cuja diferença contra elas revelaria uma
   célula de 0,05° cortada.
2. O crédito com embargo vigente (ce_valor, ce_area) de antes da SEMA-MT (versões
   963e077d838e, 2eaaf6544651 e dd4d1e88d891, até 2026-10-25 19:57; tiradas do histórico
   do git em 2026-10-26, com as chaves guardadas no beelink). Onde ele saiu e o grupo que a SEMA-MT acrescentou
   tem 1 a 4 operações ou imóveis, hoje − antes revelaria esse grupo: o município × safra
   vai para pipeline/dados/imovel_ce_corta.parquet, e monta_pagina.py anula o ce dele
   (37 em 2026-10-26). Rode de novo depois de refazer a etapa `agrega` ou `embargo`.
3. O grupo que os embargos eletrônicos do ICMBio acrescentaram (2026-10-27: a chave
   numero_emb || serie os perdia), cortado do mesmo jeito.
4. O grupo que muda contra a versão publicada em 299362d (2026-10-28, a área desembargada
   da SEMA-MT saiu do polígono embargado), nos dois sentidos: a marcação de então ficou em
   ~/bragro_tmp/imovel/marca_299362d.parquet. Na medida de 2026-10-28, nenhum par mudou.

    python3 celulas_publicadas.py   # ~/bragro_tmp/imovel/grade_005_publicada.parquet e imovel_ce_corta

Lê o formato binário antigo do bloco (u32 tamanho | cabeçalho JSON | arrays com os bytes em
planos), o de antes dos .json.gz. Saída: k (ccar, desm), i, j (célula de 0,05°), ano.
"""
import glob
import gzip
import json
import subprocess
import tempfile

import numpy as np
import polars as pl

from beelink import REMOTO, roda

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

# 2. ce de antes da SEMA-MT: as chaves publicadas, e o grupo que ela acrescentou
IM = f"{REMOTO}/imovel"
ANTES = "dd4d1e88d891"
# as versões de antes da SEMA-MT saíram do histórico do git em 2026-10-26 (git filter-repo):
# as chaves em que o ce delas saiu ficaram só no beelink, em ce_publicado_sem_sema.parquet
corta = roda("imovel_ce_corta", f"""
COPY (
  WITH mm AS (SELECT * FROM '{IM}/marca.parquet' WHERE emb),
  velho AS (   -- embargo vigente sem as áreas da SEMA-MT, como na versão {ANTES}
    SELECT DISTINCT mm.id_referencia_bacen, mm.numero_ordem, mm.id_imovel
    FROM mm JOIN br_bcb_sicor.operacao o USING (id_referencia_bacen, numero_ordem)
    JOIN '{IM}/embargo.parquet' e ON e.id_imovel = mm.id_imovel
     AND e.dia <= o.data_emissao AND (e.desembargo IS NULL OR e.desembargo > o.data_emissao)
    WHERE NOT starts_with(e.seq_tad, 'sema_mt:')),
  g AS (SELECT id_municipio::VARCHAR id_municipio, ano FROM mm ANTI JOIN velho USING (id_referencia_bacen, numero_ordem, id_imovel)
        GROUP BY ALL
        HAVING count(DISTINCT (id_referencia_bacen, numero_ordem)) BETWEEN 1 AND 4 OR count(DISTINCT id_imovel) BETWEEN 1 AND 4),
  -- 3. os embargos eletrônicos do ICMBio (serie NULL, chave 'icmbio:<numero>:'), que a versão
  -- publicada até 2026-10-27 perdia: o grupo que eles acrescentam, com 1 a 4 operações ou
  -- imóveis, sai também. Sem conferir contra o publicado (as chaves dele não estão no beelink):
  -- corta a mais, nunca a menos.
  sem_eletr AS (
    SELECT DISTINCT mm.id_referencia_bacen, mm.numero_ordem, mm.id_imovel
    FROM mm JOIN br_bcb_sicor.operacao o USING (id_referencia_bacen, numero_ordem)
    JOIN '{IM}/embargo.parquet' e ON e.id_imovel = mm.id_imovel
     AND e.dia <= o.data_emissao AND (e.desembargo IS NULL OR e.desembargo > o.data_emissao)
    WHERE NOT (starts_with(e.seq_tad, 'icmbio:') AND ends_with(e.seq_tad, ':'))),
  g2 AS (SELECT id_municipio::VARCHAR id_municipio, ano FROM mm ANTI JOIN sem_eletr USING (id_referencia_bacen, numero_ordem, id_imovel)
         GROUP BY ALL
         HAVING count(DISTINCT (id_referencia_bacen, numero_ordem)) BETWEEN 1 AND 4 OR count(DISTINCT id_imovel) BETWEEN 1 AND 4),
  -- 4. contra a versão 299362d: os pares cuja marca de embargo mudou, para mais ou para menos
  g3 AS (SELECT a.id_municipio::VARCHAR id_municipio, a.ano
         FROM '{IM}/marca_299362d.parquet' a JOIN '{IM}/marca.parquet' n USING (id_referencia_bacen, numero_ordem, id_imovel)
         WHERE a.emb <> n.emb GROUP BY ALL
         HAVING count(DISTINCT (id_referencia_bacen, numero_ordem)) BETWEEN 1 AND 4 OR count(DISTINCT id_imovel) BETWEEN 1 AND 4)
  SELECT * FROM g SEMI JOIN '{IM}/ce_publicado_sem_sema.parquet' USING (id_municipio, ano)
  UNION SELECT * FROM g2 UNION SELECT * FROM g3 ORDER BY ALL
) TO '{{saida}}' (FORMAT parquet);
""")
