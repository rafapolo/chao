#!/usr/bin/env python3
"""Censo Agropecuário 2017: quem produz, por município.

Saída em pipeline/dados/:
  censo_agro.parquet — id_municipio, ano (2017) e uma coluna por medida (MEDIDAS, abaixo)

Lê br_ibge_censo_agropecuario.sidra_municipio, os recortes por município que o rodado raspa do
SIDRA (`ibge_sidra.py recorte --pesquisa CA --periodo 2017`): cada tabela com uma classificação
aberta e as outras no Total. Medido em 2026-10-26:
  - Sigilo: o IBGE põe `X` onde o município tem 1 ou 2 informantes; `valor` vem NULL. A
    porcentagem cujo numerador ou denominador está em `X` fica sem valor (não 0).
  - "Agricultura familiar" é a tipologia do Censo (Lei 11.326), não a DAP nem o CAF.
  - Estabelecimento não é imóvel: um imóvel pode ter vários estabelecimentos, e um
    estabelecimento pode juntar vários imóveis.
  - A malha do Censo é a de 2017 (5.570 municípios), a mesma da página.
Conferência: a soma dos municípios contra a linha Brasil da 6753 (5.073.324 estabelecimentos,
351,3 M ha, 3.897.408 familiares com 80,9 M ha).
"""
import polars as pl

from beelink import roda

if __name__ != "__main__":   # importar rodaria as extrações no beelink
    raise ImportError("baixa_censo_agro.py é um script: rode python3 baixa_censo_agro.py")

lg = roda("censo_agro_longo", """
COPY (
  SELECT id_localidade id_municipio, id_tabela, recorte, id_variavel, valor, simbolo,
         list_filter([id_categoria_1, id_categoria_2, id_categoria_3, id_categoria_4, id_categoria_5, id_categoria_6, id_categoria_7],
                     x -> x IS NOT NULL) cats
  FROM br_ibge_censo_agropecuario.sidra_municipio
) TO '{saida}' (FORMAT parquet);
""")


def pega(tab, rec, var, *cats):
    """Valor por município da tabela × recorte × variável, com as categorias `cats` (as outras no Total)."""
    d = lg.filter((pl.col("id_tabela") == tab) & (pl.col("recorte") == rec) & (pl.col("id_variavel") == var))
    for c in cats:
        d = d.filter(pl.col("cats").list.contains(c))
    # as classificações fora de `cats` ficam no Total (as categorias de nível 0, em TOTAIS)
    if not cats:
        d = d.filter(pl.col("cats").list.eval(pl.element().is_in(TOTAIS)).list.all())
    else:
        outras = pl.col("cats").list.set_difference(pl.lit(list(cats)))
        d = d.filter(outras.list.eval(pl.element().is_in(TOTAIS)).list.all())
    assert d["id_municipio"].n_unique() == d.height, (tab, rec, var, cats)
    return d.select("id_municipio", "valor")


# o Total de cada classificação usada (categoria de nível 0 nos metadados do SIDRA)
TOTAIS = [46302, 111195, 46502, 41145, 41148, 6794, 46571, 110085, 46556, 41147, 41141, 118477, 45951, 10969,
          113197, 41151, 115947, 113601, 115949, 46531, 46553, 47179]
FAM_SIM, PROP = 46304, 46503
COND = {"c_prop": 46503, "c_asse": 46504, "c_arre": 46505, "c_parc": 46506, "c_como": 46507, "c_ocup": 4783, "c_sem": 111518}
ORIENT = {"o_gov": 112647, "o_propria": 112648, "o_coop": 112649, "o_integ": 112650}

col = {}
col["estab"] = pega(6753, "tipologia", 183)
col["area"] = pega(6753, "tipologia", 184)
col["estab_fam"] = pega(6753, "tipologia", 183, FAM_SIM)
col["area_fam"] = pega(6753, "tipologia", 184, FAM_SIM)
for k, c in COND.items():
    col[k] = pega(6753, "condicao_produtor", 183, c)
col["mulher"] = pega(6770, "sexo_produtor", 183, 112635)
col["sexo_tot"] = pega(6770, "sexo_produtor", 183)
col["pessoal"] = pega(6885, "tipologia", 185)
col["estab_pessoal"] = pega(6885, "tipologia", 10099)
col["agrotox"] = pega(6851, "agrotoxico", 183, 111611)
col["agrotox_tot"] = pega(6851, "agrotoxico", 183)
col["irrig"] = pega(6857, "irrigacao", 2372)
col["area_irrig"] = pega(6857, "irrigacao", 2373)
col["orient"] = pega(6846, "orientacao_tecnica", 183, 113111)
col["orient_tot"] = pega(6846, "orientacao_tecnica", 183)
for k, c in ORIENT.items():
    col[k] = pega(6846, "orientacao_tecnica", 183, c)
col["assoc"] = pega(6846, "associacao", 183, 114543)
col["financ"] = pega(6895, "agente_financeiro", 1990)
col["financ_banco"] = pega(6895, "agente_financeiro", 1990, 111915)
col["financ_coop"] = pega(6895, "agente_financeiro", 1990, 111916)
col["dap"] = pega(6962, "dap", 183, 46532)
col["dap_tot"] = pega(6962, "dap", 183)

df = None
for k, d in col.items():
    d = d.rename({"valor": k})
    df = d if df is None else df.join(d, on="id_municipio", how="full", coalesce=True)

pct = lambda num, den: (100 * pl.col(num) / pl.col(den)).alias("p_" + num)
df = df.with_columns(
    pct("estab_fam", "estab"), pct("mulher", "sexo_tot"), pct("agrotox", "agrotox_tot"), pct("irrig", "estab"),
    pct("orient", "orient_tot"), pct("assoc", "orient_tot"), pct("financ", "estab"), pct("dap", "dap_tot"),
    (pl.col("area") / pl.col("estab")).alias("area_media"),
    (pl.col("pessoal") / pl.col("estab_pessoal")).alias("pessoal_estab"),
    *[(100 * pl.col(k) / pl.col("estab")).alias("p_" + k) for k in COND],
    *[(100 * pl.col(k) / pl.col("orient")).alias("p_" + k) for k in ORIENT],
    pl.lit(2017).alias("ano"),
).sort("id_municipio")
df.write_parquet("dados/censo_agro.parquet")

# conferência contra a linha Brasil da 6753
tot = df.select(pl.col("estab", "area", "estab_fam", "area_fam").sum())
x = {c: int(lg.filter(pl.col("simbolo") == "X").filter(pl.col("recorte") == r).height) for c, r in
     [("tipologia", "tipologia"), ("condição", "condicao_produtor"), ("agrotóxico", "agrotoxico"), ("financiamento", "agente_financeiro")]}
print(f"{df.height} municípios; estabelecimentos {int(tot['estab'][0]):,} (Brasil: 5.073.324), área {tot['area'][0] / 1e6:.1f} M ha (351,3), "
      f"familiares {int(tot['estab_fam'][0]):,} (3.897.408) com {tot['area_fam'][0] / 1e6:.1f} M ha (80,9)".replace(",", "."))
print(f"valores em sigilo (X) por recorte: {x}")
for c in ["estab", "estab_fam", "p_estab_fam", "p_agrotox", "p_financ", "p_dap", "area_media"]:
    print(f"  {c}: {df[c].null_count()} municípios sem valor")
