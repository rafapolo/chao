#!/usr/bin/env python3
"""Produção municipal: PAM (lavouras) e PPM (pecuária) num formato só.

Saída: pipeline/dados/producao.parquet com uma linha por item × município × ano:
  item, ano, id_municipio, area (ha), quantidade, valor (R$ mil)

As armadilhas da PAM medidas em 2026-10-21 são tratadas aqui:
  - valor_producao está em R$ mil e, antes de 1994, em moeda da época: o valor
    só entra a partir de 1994;
  - a quantidade das lavouras permanentes troca de unidade em 2001 (frutas em mil
    frutos -> t; a laranja vai de 106.651 mil para 16.983 mil): a quantidade
    delas só entra a partir de 2001;
  - café vem em Total, Arábica e Canephora: só o Total, para não somar duas vezes;
  - área plantada (e destinada à colheita, nas permanentes) só existe a partir de
    1988 — de 1974 a 1987 a PAM só tem área colhida, que entra no lugar (soja 1987:
    9,1 M ha colhidos; 1988: 10,5 M plantados). A página avisa.
Na PPM, "Galináceos - galinhas" e "Suíno - matrizes" são subconjuntos dos totais
e ficam de fora pelo mesmo motivo. Vacas ordenhadas e ovinos tosquiados
(`producao_pecuaria`) entram como rebanho à parte: são o denominador do leite por
vaca e da lã por ovino, não somam com bovinos e ovinos.

PEVS (medida em 2026-10-22): não tem área, só quantidade e valor (R$ mil, com o
mesmo corte de 1994: o açaí vale R$ 775 mil em 1993 e R$ 46 mi em 1994).
  - Extração vegetal (E|): os produtos com menos de MIN_LINHAS linhas na série
    viram "Outros" do mesmo tipo (t); "árvores abatidas" (mil árvores) e "nó de
    pinho" ficam de fora; as duas borrachas de hévea e os dois produtos da
    carnaúba (cera, pó) somam, porque têm a mesma unidade e o mesmo extrativista.
  - Silvicultura (S|): as espécies (eucalipto, pinus, outras) só existem de 2013
    em diante; somam no tipo (carvão, lenha, madeira para celulose, madeira para
    outros usos). Antes de 2013 a tabela só traz casca de acácia, folha de
    eucalipto e resina.
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
MIN_LINHAS = 1000
EXTRACAO_JUNTA = """CASE
    WHEN produto LIKE 'Hevea%' THEN 'Borracha de hévea'
    WHEN produto LIKE 'Carnaúba (%' THEN 'Carnaúba (cera e pó)'
    WHEN produto = 'Carnaúba' THEN 'Carnaúba (fibra)'
    ELSE produto END"""

df = roda("producao", f"""
COPY (
  SELECT 'T|' || produto AS item, ano, id_municipio,
         coalesce(area_plantada, CASE WHEN ano < 1988 THEN area_colhida END)::DOUBLE AS area,
         quantidade_produzida AS quantidade,
         CASE WHEN ano >= 1994 THEN valor_producao END AS valor
  FROM br_ibge_pam.lavoura_temporaria
  WHERE coalesce(area_plantada, area_colhida, 0) > 0 OR coalesce(quantidade_produzida, 0) > 0
  UNION ALL
  SELECT 'P|' || produto, ano, id_municipio,
         coalesce(area_destinada_colheita, CASE WHEN ano < 1988 THEN area_colhida END)::DOUBLE,
         CASE WHEN ano >= 2001 THEN quantidade_produzida END,
         CASE WHEN ano >= 1994 THEN valor_producao END
  FROM br_ibge_pam.lavoura_permanente
  WHERE produto NOT IN ('Café (em grão) Arábica', 'Café (em grão) Canephora')
    AND (coalesce(area_destinada_colheita, area_colhida, 0) > 0 OR coalesce(quantidade_produzida, 0) > 0)
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
  UNION ALL
  SELECT 'R|Vacas ordenhadas', ano, id_municipio, NULL, vacas_ordenhadas::DOUBLE, NULL
  FROM br_ibge_ppm.producao_pecuaria WHERE vacas_ordenhadas > 0
  UNION ALL
  SELECT 'R|Ovinos tosquiados', ano, id_municipio, NULL, ovinos_tosquiados::DOUBLE, NULL
  FROM br_ibge_ppm.producao_pecuaria WHERE ovinos_tosquiados > 0
  UNION ALL
  SELECT 'E|' || nome, ano, id_municipio, NULL, sum(quantidade)::DOUBLE,
         sum(CASE WHEN ano >= 1994 THEN valor END)
  FROM (
    SELECT e.*, CASE WHEN (n.linhas < {MIN_LINHAS} OR e.produto IN ('Outros', 'Outras')) AND e.unidade = 'Toneladas' THEN 'Outros (' || lower(coalesce(e.tipo_produto, 'diversos')) || ')'
                     ELSE {EXTRACAO_JUNTA} END nome
    FROM br_ibge_pevs.producao_extracao_vegetal e
    JOIN (SELECT {EXTRACAO_JUNTA} j, count(*) linhas FROM br_ibge_pevs.producao_extracao_vegetal GROUP BY 1) n
      ON n.j = {EXTRACAO_JUNTA.replace('produto', 'e.produto')}
    WHERE e.quantidade > 0 AND e.unidade <> 'Mil árvores' AND e.produto NOT LIKE '%nó de pinho%')
  GROUP BY ALL
  UNION ALL
  SELECT 'S|' || CASE
           WHEN subtipo_produto LIKE '%papel e celulose' THEN 'Madeira para celulose'
           WHEN subtipo_produto LIKE '%outras finalidades' THEN 'Madeira para outros usos'
           ELSE coalesce(tipo_produto, produto) END,
         ano, id_municipio, NULL, sum(quantidade)::DOUBLE, sum(CASE WHEN ano >= 1994 THEN valor END)
  FROM br_ibge_pevs.producao_silvicultura WHERE quantidade > 0
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
    ("R|Vacas ordenhadas", 2024, "quantidade", 15.1e6, "cabeças"),
    ("E|Açaí (fruto)", 2024, "quantidade", 0.247e6, "t"),
    ("S|Madeira para celulose", 2024, "quantidade", 122e6, "m³"),   # medido no espelho em 2026-10-22; madeira em tora toda: 188 M m³
]
for item, ano, col, ref, un in checks:
    v = total(item, ano, col)
    print(f"{item} {ano}: {v / 1e6:.1f} M {un} (ref ~{ref / 1e6:.1f} M)")
    assert 0.8 * ref < v < 1.2 * ref, f"{item} fora da ordem de grandeza"
print(f"itens: {df['item'].n_unique()}, anos {df['ano'].min()}–{df['ano'].max()}")
print("PEVS:", sorted(df.filter(pl.col("item").str.contains(r"^[ES]\|"))["item"].unique().to_list()))
