#!/usr/bin/env python3
"""LSPA (IBGE): a previsão da safra do ano corrente, por UF.

Saída em pipeline/dados/:
  lspa_uf.parquet — sigla_uf, ano (da safra), item (o da PAM, "T|Soja (em grão)"), area_plantada,
                    area_colhida (ha), producao (t), mes (aaaamm do levantamento)

Lê br_ibge_lspa.sidra, tabela 1618, no último levantamento do espelho. Medido em 2026-10-26:
  - Só Brasil e UF: o LSPA não existe por município.
  - O levantamento de 2026-09 traz a Safra 2025 e a Safra 2026, 37 produtos. O número muda a cada
    mês: para atualizar, rode este script de novo (depois de o rodado raspar o mês) e remonte.
  - Produtos em safras (milho 1ª e 2ª, feijão 1ª a 3ª, amendoim, batata-inglesa) e o café em
    arábica e canephora somam no item da PAM, que não separa.
  - Gergelim e canola não têm item na PAM e ficam de fora (DE_PARA com None). Produto novo no
    LSPA sem linha no DE_PARA quebra a montagem de propósito.
Conferência: soja do MT na Safra 2025 = 12,79 M ha; e, item a item, a Safra 2025 contra a PAM 2024
(a PAM 2025 ainda não está no espelho).
"""
import polars as pl

from beelink import roda

if __name__ != "__main__":   # importar rodaria as extrações no beelink
    raise ImportError("baixa_lspa.py é um script: rode python3 baixa_lspa.py")

DE_PARA = {
    "Algodão herbáceo": "T|Algodão herbáceo (em caroço)", "Amendoim": "T|Amendoim (em casca)", "Arroz": "T|Arroz (em casca)",
    "Aveia": "T|Aveia (em grão)", "Canola": None, "Centeio": "T|Centeio (em grão)", "Cevada": "T|Cevada (em grão)",
    "Feijão": "T|Feijão (em grão)", "Gergelim": None, "Girassol": "T|Girassol (em grão)", "Mamona": "T|Mamona (baga)",
    "Milho": "T|Milho (em grão)", "Soja": "T|Soja (em grão)", "Sorgo": "T|Sorgo (em grão)", "Trigo": "T|Trigo (em grão)",
    "Triticale": "T|Triticale (em grão)", "Banana": "P|Banana (cacho)", "Batata - inglesa": "T|Batata-inglesa",
    "Cacau": "P|Cacau (em amêndoa)", "Café arábica": "P|Café (em grão) Total", "Café canephora": "P|Café (em grão) Total",
    "Cana-de-açúcar": "T|Cana-de-açúcar", "Castanha-de-caju": "P|Castanha de caju", "Fumo": "T|Fumo (em folha)",
    "Juta": "T|Juta (fibra)", "Laranja": "P|Laranja", "Mandioca": "T|Mandioca", "Tomate": "T|Tomate", "Uva": "P|Uva",
}

df = roda("lspa_bruto", """
COPY (
  SELECT id_localidade::INT id_uf, periodo mes, categoria_1 safra, categoria_2 produto, variavel, valor
  FROM br_ibge_lspa.sidra
  WHERE id_tabela = 1618 AND id_nivel = '3' AND id_categoria_2 NOT IN (0, 39428)
    AND periodo = (SELECT max(periodo) FROM br_ibge_lspa.sidra WHERE id_tabela = 1618)
) TO '{saida}' (FORMAT parquet);
""")
ufs = roda("lspa_ufs", "COPY (SELECT id_uf::INT id_uf, sigla FROM br_bd_diretorios_brasil.uf) TO '{saida}' (FORMAT parquet);")

# "1.15 Milho (1ª Safra)" -> "Milho"
df = df.with_columns(pl.col("produto").str.replace(r"^[\d.]+ ", "").str.replace(r" \(\d+ª Safra\)$", "").alias("produto"))
novos = set(df["produto"].unique()) - set(DE_PARA)
if novos:
    raise KeyError(f"produto do LSPA sem linha no DE_PARA: {sorted(novos)}")
df = df.with_columns(pl.col("produto").replace_strict(DE_PARA, return_dtype=pl.Utf8).alias("item"),
                     pl.col("safra").str.extract(r"(\d{4})").cast(pl.Int32).alias("ano"))
lspa = (df.filter(pl.col("item").is_not_null())
        .join(ufs, on="id_uf").rename({"sigla": "sigla_uf"})
        .group_by("sigla_uf", "ano", "item", "mes", "variavel").agg(pl.col("valor").sum())
        .pivot(on="variavel", index=["sigla_uf", "ano", "item", "mes"], values="valor")
        .rename({"Área plantada": "area_plantada", "Área colhida": "area_colhida", "Produção": "producao"})
        .sort("sigla_uf", "ano", "item"))
lspa.write_parquet("dados/lspa_uf.parquet")

# conferência: a PAM do espelho vai até 2024 (medido em 2026-10-26), então a Safra 2025 do LSPA
# é comparada com a PAM 2024, item a item no Brasil: ordem de grandeza, não igualdade
pam = (pl.read_parquet("dados/producao.parquet").filter(pl.col("ano") == 2024)
       .group_by("item").agg(pl.col("area").sum().alias("pam_2024")))
c = (lspa.filter(pl.col("ano") == 2025).group_by("item").agg(pl.col("area_plantada").sum().alias("lspa_2025"))
     .join(pam, on="item", how="left").with_columns((pl.col("lspa_2025") / pl.col("pam_2024") - 1).alias("dif")))
soja_mt = lspa.filter((pl.col("sigla_uf") == "MT") & (pl.col("item") == "T|Soja (em grão)") & (pl.col("ano") == 2025))
print(f"mês {lspa['mes'][0]}: {lspa.height} linhas, {lspa['item'].n_unique()} itens, safras {sorted(lspa['ano'].unique())}")
print(f"soja MT 2025: LSPA {soja_mt['area_plantada'][0] / 1e6:.2f} M ha (esperado 12,79)")
fora = c.filter((pl.col("pam_2024") > 100_000) & (pl.col("dif").abs() > 0.10)).sort("pam_2024", descending=True)
print(f"{fora.height} de {c.filter(pl.col('pam_2024') > 100_000).height} itens com mais de 100 mil ha mudam mais de 10% contra a PAM 2024:")
print(fora)
