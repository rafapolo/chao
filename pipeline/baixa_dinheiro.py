#!/usr/bin/env python3
"""Dinheiro no campo: crédito rural (SICOR completo), ESTBAN, BNDES, SCR e PIB.

Saídas em pipeline/dados/:
  credito_mun.parquet — id_municipio, safra, finalidade, atividade, programa
                        (Pronaf, Pronamp, Demais), operacoes, valor, area (ha)
  credito_ind.parquet — id_municipio, safra e os indicadores da safra: liberado,
                        desclassificado (operações e R$), tomadores (distintos), tomadores_pj,
                        top10 (parte do valor dos 10% maiores tomadores), via_coop_credito
                        (R$ por cooperativa ou banco cooperativo), cooperado (R$ por
                        cooperados), ops_car (operações com CAR informado), saldo (R$ em
                        aberto no fim do ano)
  credito_if.parquet  — id_municipio, instituicao, segmento, operacoes, valor (2012–2025)
  credito_uf.parquet  — sigla_uf, safra, valor (todo o crédito), valor_mun (o que tem município)
  estban.parquet      — id_municipio, ano, saldo de financiamentos rurais (R$)
  bndes.parquet       — id_municipio, ano, desembolso do BNDES à agropecuária (R$)
  scr.parquet         — sigla_uf, ano, carteira ativa e inadimplência dos financiamentos rurais (R$)
  pib.parquet         — id_municipio, ano, pib, va, va_agro (R$)

Medido em 2026-10-22:
  - **SICOR: a `operacao` não tem município.** Só `recurso_publico_complemento_operacao`
    o traz, e cobre apenas o crédito de recurso controlado ou equalizado (poupança
    rural equalizada, BNDES/Finame, fundos constitucionais, LCA equalizada, Funcafé…):
    em 2023/24, R$ 136 bi de R$ 422 bi. A LCA livre (R$ 166 bi), os recursos livres e
    o BNDES livre não têm município. O mapa mostra a parte com município, e o total
    por UF (`operacao.sigla_uf`) vai para a faixa e para a nota.
  - o total nacional bate com o anuário do crédito rural do BCB (2023/24: ~R$ 420 bi).
  - `recurso_publico_mutuario` é chaveado só por `id_referencia_bacen`: o tomador de
    uma operação é o mutuário com `primeiro_mutuario = 'S'` (CPF ou CNPJ básico).
  - ESTBAN `municipio`: os anos ímpares faltam desde 2003 (2003, 2005, …, 2021), 2020 cai
    para R$ 275 bi depois de R$ 513 bi em 2018, e de 2022 em diante os verbetes 164–166
    somem (só o 163). Antes de 1994, moeda da época. Entra de 1995 a 2023 com aviso.
  - PIB municipal: `municipio` de 2002 a 2023 e `municipio_antigo` de 1999 a 2012
    (a série velha só cobre 1999–2001 aqui); valores em R$ (o PIB de 2021 soma R$ 9,0 tri).
    2022 e 2023 trazem só o PIB total: va e va_agropecuaria vêm nulos nos 5.570 municípios.
"""
import polars as pl

from beelink import roda

if __name__ != "__main__":   # importar rodaria as extrações no beelink
    raise ImportError("baixa_dinheiro.py é um script: rode python3 baixa_dinheiro.py")

OPS = """
  c AS (SELECT DISTINCT ON (id_referencia_bacen, numero_ordem) id_referencia_bacen, numero_ordem, id_municipio
        FROM br_bcb_sicor.recurso_publico_complemento_operacao WHERE id_municipio IS NOT NULL ORDER BY id_referencia_bacen, numero_ordem, id_municipio),   -- determinístico se houver dois municípios
  o AS (
    SELECT o.id_referencia_bacen, o.numero_ordem, left(o.ano_safra_emissao, 4)::INTEGER safra,
           o.valor_parcela_credito v, o.area_financiada a, o.cnpj_basico_instituicao_financeira inst,
           e.finalidade, CASE WHEN e.atividade = 'Agrícola' THEN 'Agrícola' ELSE 'Pecuária' END atividade,
           CASE o.id_programa WHEN '1' THEN 'Pronaf' WHEN '50' THEN 'Pronamp' ELSE 'Demais' END programa
    FROM br_bcb_sicor.operacao o
    JOIN br_bcb_sicor.empreendimento e USING (id_empreendimento)
    WHERE e.finalidade IS NOT NULL),
  oc AS (SELECT * FROM o JOIN c USING (id_referencia_bacen, numero_ordem))
"""

cm = roda("credito_mun", "COPY (WITH" + OPS + """
  SELECT id_municipio, safra, finalidade, atividade, programa,
         count(*) operacoes, sum(v) valor, sum(a) area
  FROM oc GROUP BY ALL ORDER BY ALL
) TO '{saida}' (FORMAT parquet);
""")

ci = roda("credito_ind", "COPY (WITH" + OPS + """,
  base AS (SELECT id_municipio, safra, count(*) ops, sum(v) valor FROM oc GROUP BY ALL),
  lib AS (SELECT id_municipio, safra, sum(l.valor_liberado) liberado
          FROM oc JOIN br_bcb_sicor.liberacao l USING (id_referencia_bacen, numero_ordem) GROUP BY ALL),
  des AS (SELECT id_municipio, safra, count(DISTINCT (d.id_referencia_bacen, d.numero_ordem)) desclass_ops,
                 sum(d.valor_desclassificado) desclass_valor
          FROM oc JOIN br_bcb_sicor.operacoes_desclassificadas d USING (id_referencia_bacen, numero_ordem) GROUP BY ALL),
  mut AS (SELECT DISTINCT ON (id_referencia_bacen) id_referencia_bacen, coalesce(cpf, 'J' || cnpj_basico) tomador,
                 cpf IS NULL pj
          FROM br_bcb_sicor.recurso_publico_mutuario WHERE primeiro_mutuario = 'S'
          ORDER BY id_referencia_bacen, tomador),
  por_tom AS (SELECT id_municipio, safra, tomador, any_value(pj) pj, sum(v) v
              FROM oc JOIN mut USING (id_referencia_bacen) GROUP BY ALL),
  tom AS (SELECT id_municipio, safra, count(*) tomadores, count(*) FILTER (WHERE pj) tomadores_pj,
                 sum(v) FILTER (WHERE r <= greatest(1, ceil(n * 0.1))) / sum(v) top10
          FROM (SELECT *, row_number() OVER w r, count(*) OVER (PARTITION BY id_municipio, safra) n
                FROM por_tom WINDOW w AS (PARTITION BY id_municipio, safra ORDER BY v DESC, tomador))
          GROUP BY ALL),
  coopcred AS (SELECT id_municipio, safra, sum(v) via_coop_credito
               FROM oc JOIN br_bcb_sicor.instituicao_financeira i ON i.cnpj_basico = oc.inst
               WHERE i.segmento IN ('COOPERATIVA DE CRÉDITO', 'BANCO COOPERATIVO') GROUP BY ALL),
  coop AS (SELECT id_municipio, safra, sum(k.valor_parcela) cooperado
           FROM oc JOIN br_bcb_sicor.recurso_publico_cooperado k USING (id_referencia_bacen, numero_ordem) GROUP BY ALL),
  car AS (SELECT id_municipio, safra, count(*) ops_car FROM oc
          WHERE (id_referencia_bacen, numero_ordem) IN
                (SELECT (id_referencia_bacen, numero_ordem) FROM br_bcb_sicor.recurso_publico_propriedade WHERE id_car IS NOT NULL)
          GROUP BY ALL),
  sal AS (SELECT id_municipio, s.ano safra, sum(s.valor_ultimo_dia) saldo
          FROM br_bcb_sicor.saldo s JOIN c USING (id_referencia_bacen, numero_ordem)
          WHERE s.mes = 12 GROUP BY ALL)
  SELECT * FROM base
  LEFT JOIN lib USING (id_municipio, safra) LEFT JOIN des USING (id_municipio, safra)
  LEFT JOIN tom USING (id_municipio, safra) LEFT JOIN coopcred USING (id_municipio, safra)
  LEFT JOIN coop USING (id_municipio, safra) LEFT JOIN car USING (id_municipio, safra)
  FULL JOIN sal USING (id_municipio, safra)
  ORDER BY id_municipio, safra
) TO '{saida}' (FORMAT parquet);
""")

cf = roda("credito_if", "COPY (WITH" + OPS + """
  SELECT id_municipio, coalesce(i.nome, 'CNPJ ' || inst) instituicao, coalesce(i.segmento, 'outro') segmento,
         count(*) operacoes, sum(v) valor
  FROM oc LEFT JOIN br_bcb_sicor.instituicao_financeira i ON i.cnpj_basico = oc.inst
  GROUP BY ALL ORDER BY ALL
) TO '{saida}' (FORMAT parquet);
""")

cu = roda("credito_uf", """
COPY (
  WITH c AS (SELECT DISTINCT id_referencia_bacen, numero_ordem
             FROM br_bcb_sicor.recurso_publico_complemento_operacao WHERE id_municipio IS NOT NULL)
  SELECT o.sigla_uf, left(o.ano_safra_emissao, 4)::INTEGER safra, sum(o.valor_parcela_credito) valor,
         sum(o.valor_parcela_credito) FILTER (WHERE c.numero_ordem IS NOT NULL) valor_mun
  FROM br_bcb_sicor.operacao o LEFT JOIN c USING (id_referencia_bacen, numero_ordem)
  WHERE o.sigla_uf IS NOT NULL GROUP BY ALL ORDER BY ALL
) TO '{saida}' (FORMAT parquet);
""")

eb = roda("estban", """
COPY (
  SELECT id_municipio, ano, sum(valor) saldo
  FROM br_bcb_estban.municipio
  WHERE mes = 12 AND ano >= 1995 AND id_verbete IN ('163', '164', '165', '166')
  GROUP BY ALL HAVING sum(valor) > 0 ORDER BY ALL
) TO '{saida}' (FORMAT parquet);
""")

bn = roda("bndes", """
COPY (
  SELECT id_municipio, ano, sum(valor_desembolsado) valor
  FROM br_bndes_desembolsos.mensal
  WHERE setor_bndes = 'AGROPECUÁRIA' AND id_municipio IS NOT NULL AND ano <= 2025
  GROUP BY ALL HAVING sum(valor_desembolsado) > 0 ORDER BY ALL
) TO '{saida}' (FORMAT parquet);
""")

sc = roda("scr", """
COPY (
  SELECT uf sigla_uf, year(data_base) ano, sum(carteira_ativa) carteira, sum(carteira_inadimplencia) inadimplencia
  FROM br_bcb_scrdata.dados
  WHERE modalidade LIKE 'Financiamentos rurais%' AND month(data_base) = 12 AND length(uf) = 2
  GROUP BY ALL ORDER BY ALL
) TO '{saida}' (FORMAT parquet);
""")

pb = roda("pib", """
COPY (
  SELECT id_municipio, ano, pib, va, va_agropecuaria va_agro FROM br_ibge_pib.municipio
  UNION ALL
  SELECT id_municipio, ano, pib, va, va_agropecuaria FROM br_ibge_pib.municipio_antigo WHERE ano < 2002
  ORDER BY ALL
) TO '{saida}' (FORMAT parquet);
""")

# ---------- conferências ----------
def bi(df, col, **f):
    for k, v in f.items():
        df = df.filter(pl.col(k) == v)
    return df[col].sum() / 1e9

print(f"SICOR com município, 2023/24: R$ {bi(cm, 'valor', safra=2023):.1f} bi (medido: 135,7)")
print(f"SICOR total por UF, 2023/24: R$ {bi(cu, 'valor', safra=2023):.1f} bi (anuário BCB: ~420)")
assert 120 < bi(cm, "valor", safra=2023) < 150
assert 380 < bi(cu, "valor", safra=2023) < 460
p = cm.filter(pl.col("safra") == 2023).group_by("programa").agg(pl.col("valor").sum() / 1e9)
print(p.sort("programa"))
print(f"indicadores: {ci.height:,} município×safra; top10 mediano {ci['top10'].median():.2f}; "
      f"saldo 2023 R$ {bi(ci, 'saldo', safra=2023):.0f} bi".replace(",", "."))
print(f"ESTBAN 2023: R$ {bi(eb, 'saldo', ano=2023):.0f} bi (medido: 543); anos: {sorted(eb['ano'].unique().to_list())}")
print(f"BNDES agro 2024: R$ {bi(bn, 'valor', ano=2024):.1f} bi")
print(f"SCR rural 2024: carteira R$ {bi(sc, 'carteira', ano=2024):.0f} bi, inadimplência R$ {bi(sc, 'inadimplencia', ano=2024):.1f} bi")
va = pb.filter(pl.col("ano") == 2021)["va_agro"].sum() / 1e9
print(f"VA agropecuário 2021: R$ {va:.0f} bi (IBGE: ~591)")
assert 550 < va < 630
