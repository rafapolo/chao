#!/usr/bin/env python3
"""Lista Suja do trabalho escravo (MTE): resgates em ação fiscal por município e ano.

Saídas em pipeline/dados/:
  listasuja.parquet       — id_municipio, ano (da ação fiscal), casos e trab (empregadores e
                            trabalhadores, no campo: CNAE 01, 02 e 03), casos_tot e trab_tot (todas
                            as atividades), e os acumulados do campo desde o primeiro ano (casos_ac,
                            trab_ac)
  listasuja_ativ.parquet  — id_municipio, atividade (a subclasse CNAE do campo com mais
                            trabalhadores no município, somando todos os anos)

Lê br_mte_listasuja.empregadores_municipio, que o rodado deriva do texto `estabelecimento`
(o MTE não publica código de município; regras em ../rodado/scripts/sync/listasuja_municipio.sql).
Medido em 2026-10-26:
  - 660 casos distintos (documento × estabelecimento × ano), 5.248 trabalhadores. O
    `empregadores_historico` soma os retratos de cada coleta: contado direto, ele dá 1.086 linhas
    e 8.692 trabalhadores, o mesmo caso duas vezes.
  - 625 casos com município; dos 345 do campo, só 1 fica sem (a Terra Indígena Yanomami, sem
    município no texto). As ações fiscais vão de 2020 a 2026.
  - O CNPJ dá outro município em 88 de 216 casos: é a sede da empresa, não o local resgatado.
Sem corte de 5 (decidido em 2026-10-26, `tasks/decisoes_pendentes.md`): a lista é pública e
nominal por lei, e o agregado não revela nada além dela. Nome, CPF e CNPJ não saem do beelink.
"""
import polars as pl

from beelink import roda

if __name__ != "__main__":   # importar rodaria as extrações no beelink
    raise ImportError("baixa_listasuja.py é um script: rode python3 baixa_listasuja.py")

CAMPO = "left(cnae, 2) IN ('01', '02', '03')"

ls = roda("listasuja", f"""
COPY (
  SELECT id_municipio, ano_acao_fiscal ano,
         count(*) FILTER ({CAMPO}) casos, coalesce(sum(trabalhadores_envolvidos) FILTER ({CAMPO}), 0) trab,
         count(*) casos_tot, sum(trabalhadores_envolvidos) trab_tot
  FROM br_mte_listasuja.empregadores_municipio
  WHERE id_municipio IS NOT NULL
  GROUP BY ALL ORDER BY ALL
) TO '{{saida}}' (FORMAT parquet);
""")

at = roda("listasuja_ativ", f"""
COPY (
  SELECT DISTINCT ON (id_municipio) id_municipio, lower(c.descricao_subclasse) atividade
  FROM (SELECT id_municipio, cnae_subclasse, sum(trabalhadores_envolvidos) t
        FROM br_mte_listasuja.empregadores_municipio WHERE id_municipio IS NOT NULL AND {CAMPO} GROUP BY ALL) e
  JOIN br_bd_diretorios_brasil.cnae_2 c ON c.subclasse = e.cnae_subclasse
  ORDER BY id_municipio, t DESC, cnae_subclasse
) TO '{{saida}}' (FORMAT parquet);
""")

# acumulado do campo, de ano em ano, em todo município que já teve caso (o ano sem caso repete)
anos = pl.DataFrame({"ano": range(ls["ano"].min(), ls["ano"].max() + 1)}, schema={"ano": pl.Int64})
ac = (ls.filter(pl.col("casos") > 0).select("id_municipio").unique().join(anos, how="cross")
      .join(ls.select("id_municipio", pl.col("ano").cast(pl.Int64), "casos", "trab"), on=["id_municipio", "ano"], how="left")
      .sort("id_municipio", "ano")
      .with_columns(pl.col("casos").fill_null(0).cum_sum().over("id_municipio").alias("casos_ac"),
                    pl.col("trab").fill_null(0).cum_sum().over("id_municipio").alias("trab_ac"))
      .filter(pl.col("casos_ac") > 0)
      .select("id_municipio", "ano", "casos_ac", "trab_ac"))
ls = (ls.with_columns(pl.col("ano").cast(pl.Int64)).join(ac, on=["id_municipio", "ano"], how="full", coalesce=True)
      .sort("id_municipio", "ano"))
ls.write_parquet("dados/listasuja.parquet")

campo = ls.filter(pl.col("casos") > 0)
print(f"conferência: {int(ls['casos_tot'].sum())} casos com município (esperado 625), "
      f"{int(campo['casos'].sum())} do campo (344), {int(campo['trab'].sum()):,} trabalhadores do campo, "
      f"{campo['id_municipio'].n_unique()} municípios; atividade em {at.height}".replace(",", "."))
