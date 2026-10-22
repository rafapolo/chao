#!/usr/bin/env python3
"""Calendário agrícola: quando se planta e se colhe cada cultura, por município,
pelas datas que o produtor declara no custeio agrícola do SICOR.

Saída em pipeline/dados/:
  calendario.parquet — id_municipio, produto, fase (plantio, colheita), mes, operacoes,
                       ciclo_dias (soma, para a média de dias entre o início do plantio e o
                       fim da colheita; só na fase plantio)

Medido em 2026-10-22:
  - `operacao.data_inicio_plantio` e `data_fim_colheita` vêm em ~70% do custeio agrícola
    com município (soja: 1,17 M de 1,62 M operações), com poucas datas fora de
    2010–2027 (soja: 83). O `proagro_cop` (1 M linhas, com chave repetida) cobre só o
    que tem Proagro: a `operacao` cobre mais e é a base.
  - Moda do mês de plantio: soja outubro, milho setembro (o milho de 2ª safra planta de
    janeiro a março), trigo junho, feijão fevereiro. Ciclo mediano: soja 170 dias.
  - Todas as safras de 2012 a 2025 entram juntas: é o calendário típico, não o de um ano.
Só entram datas entre 2010 e 2027 e ciclos de 30 a 900 dias.
"""
import polars as pl

from beelink import roda

cal = roda("calendario", """
COPY (
  WITH c AS (SELECT DISTINCT ON (id_referencia_bacen, numero_ordem) id_referencia_bacen, numero_ordem, id_municipio
             FROM br_bcb_sicor.recurso_publico_complemento_operacao WHERE id_municipio IS NOT NULL ORDER BY id_referencia_bacen, numero_ordem, id_municipio),   -- determinístico se houver dois municípios
  o AS (
    SELECT c.id_municipio, e.produto, o.data_inicio_plantio p, o.data_fim_colheita f
    FROM br_bcb_sicor.operacao o
    JOIN br_bcb_sicor.empreendimento e USING (id_empreendimento)
    JOIN c USING (id_referencia_bacen, numero_ordem)
    WHERE e.finalidade = 'Custeio' AND e.atividade = 'Agrícola'
      AND o.data_inicio_plantio BETWEEN DATE '2010-01-01' AND DATE '2027-12-31'
      AND date_diff('day', o.data_inicio_plantio, o.data_fim_colheita) BETWEEN 30 AND 900)
  SELECT id_municipio, produto, 'plantio' fase, month(p) mes, count(*) operacoes,
         sum(date_diff('day', p, f)) ciclo_dias
  FROM o GROUP BY ALL
  UNION ALL
  SELECT id_municipio, produto, 'colheita', month(f), count(*), NULL FROM o GROUP BY ALL
  ORDER BY ALL
) TO '{saida}' (FORMAT parquet);
""")

# ---------- conferências ----------
def moda(produto, fase):
    d = cal.filter((pl.col("produto") == produto) & (pl.col("fase") == fase)).group_by("mes").agg(pl.col("operacoes").sum())
    return int(d.sort("operacoes", descending=True)["mes"][0])

for prod, esperado in [("SOJA", 10), ("TRIGO", 6), ("FEIJÃO", 2)]:
    m = moda(prod, "plantio")
    print(f"{prod}: plantio mais comum no mês {m} (medido: {esperado}); colheita no mês {moda(prod, 'colheita')}")
    assert m == esperado
s = cal.filter((pl.col("produto") == "SOJA") & (pl.col("fase") == "plantio"))
print(f"soja: ciclo médio {s['ciclo_dias'].sum() / s['operacoes'].sum():.0f} dias; {s['operacoes'].sum():,} operações com data".replace(",", "."))
