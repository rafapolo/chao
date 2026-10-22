#!/usr/bin/env python3
"""Mercado e gente: exportação (Trase, Comex), logística, emissões (SEEG), trabalho
(RAIS, CAGED), cadastros sociais (CadÚnico, Seguro-Defeso), população, imóveis rurais
(CAFIR) e estabelecimentos agropecuários (CNEFE).

Saídas em pipeline/dados/:
  trase.parquet       — id_municipio, ano, produto (soja, carne), t, usd, desm_ha (exposição
                        a desmatamento, só soja), co2_t (emissão líquida do desmatamento, só soja)
  trase_pais.parquet  — id_municipio, pais, t (soja, 2016–2020 somados)
  logistica.parquet   — id_municipio, armazens, cap_armazem (t), esmagadoras, cap_esmagadora (t/dia),
                        frigorificos (ativos, com SIF)
  comex.parquet       — id_municipio, ano, agro_usd (exportação SH 01–24, 41, 47, 52), fert_usd
                        (importação do capítulo 31), defensivo_usd (importação SH 3808)
  seeg.parquet        — id_municipio, ano, agro, enterica, solos, dejetos, arroz, mut, remocao (tCO2e)
  trabalho.parquet    — id_municipio, ano, vinculos (RAIS, agropecuária), saldo (CAGED, seção A)
  social.parquet      — id_municipio, ano, agricultores, pescadores, extrativistas, assentados,
                        familias_rurais (CadÚnico, dezembro ou o último mês), defeso (pescadores
                        pagos), defeso_valor (R$), populacao
  imoveis.parquet     — id_municipio, imoveis_cafir (ativos), estabelecimentos_agro (CNEFE 2022)

Medido em 2026-10-22:
  - Trase: a exportação vai ao MUNICÍPIO DE PRODUÇÃO (o Comex usa o domicílio fiscal da
    exportadora). Soja de 2004 a 2020 (em equivalente de grão: 2020 = 121,8 Mt), carne de
    2015 a 2017.
  - SEEG `municipio`: `gas` só tem '1' e '2', e o dicionário dá dois nomes para cada; o
    '2' com `emissao_ar5` (GWP-AR5) bate com o SEEG publicado (agropecuária 2022: 617 Mt).
    `setor` 1 = Agropecuária, 3 = Mudança de uso da terra; `tipo` 2 = emissão, 4 = remoção.
    As categorias da agropecuária são 9 fermentação entérica (399 Mt), 28 solos manejados
    (178), 14 manejo de dejetos (29), 5 cultivo de arroz (10); o dicionário de `categoria`
    traz duas numerações misturadas.
  - RAIS: agropecuária = `subsetor_ibge = '25'` (agricultura, silvicultura, criação, extração
    vegetal e pesca), em vínculos ativos em 31/12. CAGED: `cnae_2_secao = 'A'`, 2020 em diante.
  - Seguro-Defeso: CPF mistura completo e mascarado (gotcha): conta-se `nis_favorecido`.
  - CAFIR: a `area` não fecha em nenhuma unidade (os imóveis ativos somam 9,0 bi): só a
    contagem de imóveis ativos (`situacao_imovel = '02'`) na data mais recente.
  - CNEFE 2022: `COD_ESPECIE = 3` é estabelecimento agropecuário (4,06 M endereços).
Nome de pessoa, CPF e NIS nunca saem do beelink: só contagens e somas.
"""
import polars as pl

from beelink import roda

tr = roda("trase", """
COPY (
  SELECT municipality_id_production id_municipio, year ano, 'soja' produto, sum(try_cast(soy_total_export AS DOUBLE)) t, sum(try_cast(fob_usd AS DOUBLE)) usd,
         sum(try_cast(soy_deforestation_exposure AS DOUBLE)) desm_ha, sum(try_cast(co2_net_emissions_deforestation_5 AS DOUBLE)) co2_t
  FROM br_trase_supply_chain.soy_beans WHERE municipality_id_production IS NOT NULL GROUP BY ALL
  UNION ALL
  SELECT municipality_id_production, year, 'carne', sum(try_cast(beef_equivalent_tonnes AS DOUBLE)), sum(try_cast(fob_usd AS DOUBLE)), NULL, NULL
  FROM br_trase_supply_chain.beef WHERE municipality_id_production IS NOT NULL GROUP BY ALL
  ORDER BY ALL
) TO '{saida}' (FORMAT parquet);
""")

tp = roda("trase_pais", """
COPY (
  SELECT municipality_id_production id_municipio, coalesce(country_first_import_name, 'desconhecido') pais, sum(try_cast(soy_total_export AS DOUBLE)) t
  FROM br_trase_supply_chain.soy_beans WHERE year >= 2016 AND municipality_id_production IS NOT NULL
  GROUP BY ALL HAVING sum(try_cast(soy_total_export AS DOUBLE)) > 0 ORDER BY ALL
) TO '{saida}' (FORMAT parquet);
""")

lg = roda("logistica", """
COPY (
  WITH a AS (SELECT municipality_id id_municipio, count(*) armazens, sum(try_cast(capacity AS DOUBLE)) cap_armazem
             FROM br_trase_supply_chain.soy_beans_storage_facilities GROUP BY 1),
  e AS (SELECT municipality_id id_municipio, count(*) esmagadoras, sum(try_cast(capacity AS DOUBLE)) cap_esmagadora
        FROM br_trase_supply_chain.soy_beans_crushing_facilities
        WHERE year = (SELECT max(year) FROM br_trase_supply_chain.soy_beans_crushing_facilities) GROUP BY 1),
  f AS (SELECT municipality_id id_municipio, count(*) frigorificos
        FROM br_trase_supply_chain.beef_slaughterhouses WHERE status = 'ATIVO' GROUP BY 1)
  SELECT * FROM a FULL JOIN e USING (id_municipio) FULL JOIN f USING (id_municipio)
  WHERE id_municipio IS NOT NULL ORDER BY ALL
) TO '{saida}' (FORMAT parquet);
""")

cx = roda("comex", """
COPY (
  WITH ex AS (
    SELECT id_municipio, ano, sum(valor_fob_dolar) agro_usd FROM br_me_comex_stat.municipio_exportacao
    WHERE left(id_sh4, 2) <= '24' OR left(id_sh4, 2) IN ('41', '47', '52') GROUP BY ALL),
  im AS (
    SELECT id_municipio, ano, sum(valor_fob_dolar) FILTER (WHERE left(id_sh4, 2) = '31') fert_usd,
           sum(valor_fob_dolar) FILTER (WHERE id_sh4 = '3808') defensivo_usd
    FROM br_me_comex_stat.municipio_importacao GROUP BY ALL)
  SELECT * FROM ex FULL JOIN im USING (id_municipio, ano)
  WHERE id_municipio IS NOT NULL ORDER BY ALL
) TO '{saida}' (FORMAT parquet);
""")

sg = roda("seeg", """
COPY (
  SELECT id_municipio, ano,
         sum(emissao_ar5) FILTER (WHERE setor = '1' AND tipo = '2') agro,
         sum(emissao_ar5) FILTER (WHERE setor = '1' AND tipo = '2' AND categoria = '9') enterica,
         sum(emissao_ar5) FILTER (WHERE setor = '1' AND tipo = '2' AND categoria = '28') solos,
         sum(emissao_ar5) FILTER (WHERE setor = '1' AND tipo = '2' AND categoria = '14') dejetos,
         sum(emissao_ar5) FILTER (WHERE setor = '1' AND tipo = '2' AND categoria = '5') arroz,
         sum(emissao_ar5) FILTER (WHERE setor = '3' AND tipo = '2') mut,
         -sum(emissao_ar5) FILTER (WHERE setor = '3' AND tipo IN ('4', '5')) remocao
  FROM br_seeg_emissoes.municipio
  WHERE gas = '2' AND id_municipio IS NOT NULL AND ano >= 1990
  GROUP BY ALL ORDER BY ALL
) TO '{saida}' (FORMAT parquet);
""")

tb = roda("trabalho", """
COPY (
  WITH r AS (SELECT id_municipio, ano, sum(quantidade_vinculos_ativos) vinculos
             FROM br_me_rais.microdados_estabelecimentos WHERE subsetor_ibge = '25' GROUP BY ALL),
  c AS (SELECT id_municipio, ano, sum(saldo_movimentacao) saldo
        FROM br_me_caged.microdados_movimentacao WHERE cnae_2_secao = 'A' GROUP BY ALL)
  SELECT * FROM r FULL JOIN c USING (id_municipio, ano)
  WHERE id_municipio IS NOT NULL ORDER BY ALL
) TO '{saida}' (FORMAT parquet);
""")

so = roda("social", """
COPY (
  WITH ult AS (SELECT year(referencia) ano, max(referencia) ultima FROM br_mds_cadunico.indicadores_municipio GROUP BY 1),
  cad AS (
    SELECT i.id_municipio, u.ano,
           max(valor) FILTER (WHERE id_indicador = '75df80a5b899') agricultores,
           max(valor) FILTER (WHERE id_indicador = '0328e90fc9b3') pescadores,
           max(valor) FILTER (WHERE id_indicador = '3bdabbdb2979') extrativistas,
           max(valor) FILTER (WHERE id_indicador = '17444e3ccfdf') assentados,
           max(valor) FILTER (WHERE id_indicador = '4e9c79c1b29b'
                              AND variavel ILIKE '%rurais%' AND variavel NOT ILIKE '%pobreza%') familias_rurais
    FROM br_mds_cadunico.indicadores_municipio i JOIN ult u ON i.referencia = u.ultima
    WHERE id_indicador IN ('75df80a5b899', '0328e90fc9b3', '3bdabbdb2979', '17444e3ccfdf', '4e9c79c1b29b')
    GROUP BY ALL),
  def AS (
    SELECT d.id_municipio, left(s.mes_referencia, 4)::INTEGER ano,
           count(DISTINCT s.nis_favorecido) defeso, sum(s.valor_parcela) defeso_valor
    FROM br_cgu_seguro_defeso.seguro_defeso s
    JOIN br_bd_diretorios_brasil.municipio d
      ON try_cast(d.id_municipio_rf AS INTEGER) = try_cast(s.codigo_municipio_siafi AS INTEGER)
    GROUP BY ALL),
  pop AS (SELECT id_municipio, ano, populacao FROM br_ibge_populacao.municipio)
  SELECT * FROM pop FULL JOIN cad USING (id_municipio, ano) FULL JOIN def USING (id_municipio, ano)
  WHERE id_municipio IS NOT NULL ORDER BY ALL
) TO '{saida}' (FORMAT parquet);
""")

im = roda("imoveis", """
COPY (
  WITH caf AS (
    SELECT id_municipio, count(*) imoveis_cafir FROM br_rf_cafir.imoveis_rurais
    WHERE situacao_imovel = '02' AND data_referencia = (SELECT max(data_referencia) FROM br_rf_cafir.imoveis_rurais)
    GROUP BY 1),
  cn AS (SELECT COD_MUNICIPIO::VARCHAR id_municipio, count(*) estabelecimentos_agro
         FROM br_ibge_cnefe.enderecos WHERE COD_ESPECIE = 3 GROUP BY 1)
  SELECT * FROM caf FULL JOIN cn USING (id_municipio) WHERE id_municipio IS NOT NULL ORDER BY ALL
) TO '{saida}' (FORMAT parquet);
""")

# ---------- conferências ----------
def soma(df, col, ano=None, **f):
    if ano is not None:
        df = df.filter(pl.col("ano") == ano)
    for k, v in f.items():
        df = df.filter(pl.col(k) == v)
    return df[col].sum()

print(f"Trase soja 2020: {soma(tr, 't', 2020, produto='soja') / 1e6:.1f} Mt (medido: 121,8); carne 2017: {soma(tr, 't', 2017, produto='carne') / 1e6:.2f} Mt")
print(f"logística: {lg['armazens'].sum():,.0f} armazéns, {lg['esmagadoras'].sum():,.0f} esmagadoras, {lg['frigorificos'].sum():,.0f} frigoríficos".replace(",", "."))
print(f"Comex agro 2024: US$ {soma(cx, 'agro_usd', 2024) / 1e9:.0f} bi (agronegócio, MAPA: ~165); fertilizantes US$ {soma(cx, 'fert_usd', 2024) / 1e9:.1f} bi")
ag = soma(sg, "agro", 2022) / 1e6
print(f"SEEG 2022: agro {ag:.0f} Mt (SEEG: 617), entérica {soma(sg, 'enterica', 2022) / 1e6:.0f}, MUT {soma(sg, 'mut', 2022) / 1e6:.0f}")
assert 580 < ag < 660
print(f"RAIS agro 2020: {soma(tb, 'vinculos', 2020) / 1e6:.2f} M vínculos (RAIS: ~1,5 M); CAGED agro 2023: saldo {soma(tb, 'saldo', 2023):,.0f}".replace(",", "."))
print(f"CadÚnico 2024: {soma(so, 'agricultores', 2024) / 1e6:.2f} M famílias de agricultores familiares; "
      f"defeso 2024: {soma(so, 'defeso', 2024):,.0f} pescadores, R$ {soma(so, 'defeso_valor', 2024) / 1e9:.1f} bi; "
      f"população 2022: {soma(so, 'populacao', 2022) / 1e6:.0f} M".replace(",", "."))
print(f"CAFIR: {im['imoveis_cafir'].sum() / 1e6:.1f} M imóveis ativos; CNEFE: {im['estabelecimentos_agro'].sum() / 1e6:.2f} M estabelecimentos agropecuários")
