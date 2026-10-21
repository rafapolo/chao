#!/usr/bin/env python3
"""Produção municipal: PAM (lavouras) e PPM (pecuária) num formato só.

Saída: pipeline/dados/producao.parquet com uma linha por item × município × ano:
  item, ano, id_municipio, area (ha), quantidade, valor (R$ mil)

As três armadilhas da PAM medidas em 2026-10-21 são tratadas aqui:
  - valor_producao está em R$ mil e, antes de 1994, em moeda da época: o valor
    só entra a partir de 1994;
  - a quantidade das lavouras permanentes troca de unidade em 2001 (frutas em mil
    frutos -> t; a laranja vai de 106.651 mil para 16.983 mil): a quantidade
    delas só entra a partir de 2001;
  - café vem em Total, Arábica e Canephora: só o Total, para não somar duas vezes.
Na PPM, "Galináceos - galinhas" e "Suíno - matrizes" são subconjuntos dos totais
e ficam de fora pelo mesmo motivo.
"""
import polars as pl

from beelink import roda

AQUI_PRINCIPAIS = ("Tilápia", "Tambaqui", "Tambacu, tambatinga", "Pacu e patinga",
                   "Carpa", "Camarão", "Ostras, vieiras e mexilhões")
AQUI_FORA = ("Alevinos", "Larvas e pós-larvas de camarão", "Sementes de moluscos")
REBANHOS_FORA = ("Galináceos - galinhas", "Suíno - matrizes de suínos")

aqui_princ = ", ".join(f"'{p}'" for p in AQUI_PRINCIPAIS)
aqui_fora = ", ".join(f"'{p}'" for p in AQUI_FORA)
reb_fora = ", ".join(f"'{p}'" for p in REBANHOS_FORA)

df = roda("producao", f"""
COPY (
  SELECT 'T|' || produto AS item, ano, id_municipio,
         area_plantada::DOUBLE AS area, quantidade_produzida AS quantidade,
         CASE WHEN ano >= 1994 THEN valor_producao END AS valor
  FROM br_ibge_pam.lavoura_temporaria
  WHERE coalesce(area_plantada, 0) > 0 OR coalesce(quantidade_produzida, 0) > 0
  UNION ALL
  SELECT 'P|' || produto, ano, id_municipio,
         area_destinada_colheita::DOUBLE,
         CASE WHEN ano >= 2001 THEN quantidade_produzida END,
         CASE WHEN ano >= 1994 THEN valor_producao END
  FROM br_ibge_pam.lavoura_permanente
  WHERE produto NOT IN ('Café (em grão) Arábica', 'Café (em grão) Canephora')
    AND (coalesce(area_destinada_colheita, 0) > 0 OR coalesce(quantidade_produzida, 0) > 0)
  UNION ALL
  SELECT 'R|' || tipo_rebanho, ano, id_municipio, NULL, quantidade::DOUBLE, NULL
  FROM br_ibge_ppm.efetivo_rebanhos
  WHERE quantidade > 0 AND tipo_rebanho NOT IN ({reb_fora})
  UNION ALL
  SELECT 'A|' || produto, ano, id_municipio, NULL, quantidade::DOUBLE, valor::DOUBLE
  FROM br_ibge_ppm.producao_origem_animal WHERE quantidade > 0
  UNION ALL
  SELECT 'Q|' || CASE WHEN produto IN ({aqui_princ}) THEN produto ELSE 'Outros peixes' END,
         ano, id_municipio, NULL, sum(quantidade)::DOUBLE, sum(valor)::DOUBLE
  FROM br_ibge_ppm.producao_aquicultura
  WHERE quantidade > 0 AND produto NOT IN ({aqui_fora})
  GROUP BY ALL
) TO '{{saida}}' (FORMAT parquet);
""")

# ---------- conferências (ordens de grandeza conhecidas) ----------
def total(item, ano, col):
    return df.filter((pl.col("item") == item) & (pl.col("ano") == ano))[col].sum()

checks = [
    ("T|Soja (em grão)", 2024, "area", 46.2e6, "ha"),
    ("T|Cana-de-açúcar", 2024, "area", 10.1e6, "ha"),
    ("P|Café (em grão) Total", 2024, "area", 1.9e6, "ha"),
    ("R|Bovino", 2024, "quantidade", 238e6, "cabeças"),
    ("A|Leite", 2024, "quantidade", 35.7e6, "mil litros"),
]
for item, ano, col, ref, un in checks:
    v = total(item, ano, col)
    print(f"{item} {ano}: {v / 1e6:.1f} M {un} (ref ~{ref / 1e6:.1f} M)")
    assert 0.8 * ref < v < 1.2 * ref, f"{item} fora da ordem de grandeza"
print(f"itens: {df['item'].n_unique()}, anos {df['ano'].min()}–{df['ano'].max()}")
