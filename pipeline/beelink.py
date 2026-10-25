"""Acesso ao espelho do rodado no beelink.

Toda extração é um SQL que termina num `COPY (...) TO '<saida>.parquet'`, roda no
DuckDB do beelink em modo somente leitura, e o parquet volta por scp para
`pipeline/dados/`. O pesado (junções espaciais, agregação de 7 milhões de glebas)
fica lá, onde o dado está; aqui chegam só os resultados.
"""
import subprocess
import sys
import time
from pathlib import Path

import polars as pl

S = Path(__file__).parent
DADOS = S / "dados"
REMOTO = "/home/polo/bragro_tmp"
DUCKDB = "~/bin/duckdb -readonly ~/rodado/basedosdados.duckdb"


def _executa(nome: str, corpo: str) -> str:
    r = subprocess.run(
        ["ssh", "beelink", f"mkdir -p {REMOTO} && {DUCKDB} -csv"],
        input="SET enable_progress_bar=false;\nLOAD spatial;\nSET geometry_always_xy = true;\n" + corpo,
        capture_output=True, text=True,
    )
    erro = "\n".join(l for l in r.stderr.splitlines() if "Loading resources" not in l).strip()
    if r.returncode != 0 or "Error" in r.stdout or "Error" in erro:
        sys.exit(f"[{nome}] falhou:\n{r.stdout[-3000:]}\n{erro[-3000:]}")
    return r.stdout.strip()


def prepara(nome: str, sql: str) -> str:
    """Roda `sql` no beelink e deixa o resultado lá (parquet intermediário, que não
    volta): para cruzamentos cujas linhas não podem sair do beelink."""
    t = time.time()
    saida = _executa(nome, sql)
    print(f"[{nome}] {time.time() - t:.0f} s")
    return saida


def roda(nome: str, sql: str) -> pl.DataFrame:
    """Roda `sql` (com {saida} no lugar do caminho remoto) e devolve o parquet."""
    DADOS.mkdir(exist_ok=True)
    saida = f"{REMOTO}/{nome}.parquet"
    t = time.time()
    _executa(nome, sql.format(saida=saida))
    local = DADOS / f"{nome}.parquet"
    subprocess.run(["scp", "-q", f"beelink:{saida}", str(local)], check=True)
    df = pl.read_parquet(local)
    print(f"[{nome}] {df.height:,} linhas em {time.time() - t:.0f} s".replace(",", "."))
    return df


def consulta(sql: str) -> str:
    """Consulta curta, saída CSV em texto — para conferências."""
    r = subprocess.run(
        ["ssh", "beelink", f"{DUCKDB} -csv"],
        input="SET enable_progress_bar=false;\nLOAD spatial;\nSET geometry_always_xy = true;\n" + sql,
        capture_output=True, text=True,
    )
    return r.stdout.strip()
