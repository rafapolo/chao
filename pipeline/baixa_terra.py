#!/usr/bin/env python3
"""Terra: desmatamento (PRODES, DETER), fogo (queimadas), embargos e autos do IBAMA,
assentamentos e certificação fundiária (INCRA).

Saídas em pipeline/dados/:
  prodes_mun.parquet   — id_municipio, ano, incremento (km² desmatados no ano), acumulado (km²)
  prodes_celula.parquet — i, j (grade de 0,05°), ano, area_km2
  deter_mun.parquet    — id_municipio, ano (PRODES, ago–jul; queimada: civil), classe (desmatamento, degradação, queimada,
                         mineração), avisos, area_km2, ultimo (dia do aviso mais recente)
  fogo_mun.parquet     — id_municipio, ano, mes, focos
  fogo_celula.parquet  — i, j, ano, focos
  ibama_mun.parquet    — id_municipio, ano, embargos, area_embargada, autos, autos_flora,
                         multas (R$), multas_flora (R$)
  fundiario.parquet    — id_municipio e o retrato: assentamentos, famílias assentadas,
                         área de assentamento, parcelas SIGEF e SNCI e área certificada

Medido em 2026-10-22 (e nos gotchas do rodado):
  - PRODES por município: `br_inpe_prodes.municipio_bioma` traz o desmatado ACUMULADO
    (Sorriso: 5.692 km² em 2000, 6.918 em 2023), uma linha por bioma; o incremento é a
    diferença ano a ano. De 2017 em diante usa-se `incremento_municipio` (que vai até
    2025); os dois batem a <0,3% (gotcha prodes_acumulado). 2001–2016 vêm da diferença.
  - polígonos do PRODES: `bioma_arquivo = 'amazonia_legal'` sobrepõe a Amazônia e parte
    do Cerrado e fica de fora; RESERVATORIO e QUEIMADA também.
  - DETER: `class_name` só existe em Pantanal e não-floresta; nos outros a classe está
    em `CLASSNAME`. Município pelo `GEOCODIBGE`, área pela parte no município
    (`AREAMUNKM`). Cicatriz de queimada não é desmatamento: classe à parte. Desmatamento,
    degradação e mineração vão no ano do PRODES (agosto a julho), para as duas fontes
    falarem da mesma janela, e o ano mais recente fica incompleto até julho; queimada fica
    no ano civil, o dos focos de calor. Dentro de um ano e de uma classe os
    polígonos não se sobrepõem (união/soma = 1,000 em 2024); somando 2016–2026 o mesmo
    trecho volta a ser alertado em ~5% da área (PA: 0,947) — somar anos superestima pouco.
  - queimadas: 23 M focos, todos com município; a célula usa lat/lon do foco. De 2003 a
    2022 o espelho só tem a série do satélite de referência (satelite NULL; 2020: 222.797,
    igual ao INPE); de 2023 em diante vêm todos os satélites (2024: 8,1 M focos) e a
    série de referência é a do AQUA_M-T (2024: 278.341). Somar tudo multiplica por 30.
  - embargos: `dat_embargo` é texto com anos impossíveis (2925): try_strptime e corte
    no ano corrente; cancelados (sit_cancelado = 'S') saem; `qtd_area_embargada` sem
    unidade declarada (tratada como ha).
  - autos: `tipo_infracao = 'Flora'` são os de vegetação (219 mil, R$ 65,5 bi em multas);
    cancelados saem.
  - SIGEF: `municipio_` é o código IBGE (inteiro). SNCI e assentamentos só têm lat/lon
    e nome: o município vem do ponto dentro da malha.
O nome do embargado ou autuado nunca sai do beelink: só contagens e somas.
"""
import polars as pl

from beelink import roda

PASSO = 0.1   # ~120 km²: com 0,05° as duas grades passavam de 1,4 M células cada
REFERENCIA = "(satelite IS NULL OR satelite = 'AQUA_M-T')"

pm = roda("prodes_mun", """
COPY (
  WITH acum AS (
    SELECT id_municipio, ano, sum(desmatado) acumulado FROM br_inpe_prodes.municipio_bioma GROUP BY ALL),
  dif AS (
    SELECT id_municipio, ano, acumulado,
           acumulado - lag(acumulado) OVER (PARTITION BY id_municipio ORDER BY ano) incremento
    FROM acum),
  novo AS (
    SELECT id_municipio, ano, sum(area_km2) incremento FROM br_inpe_prodes_acumulado.incremento_municipio GROUP BY ALL)
  SELECT coalesce(n.id_municipio, d.id_municipio) id_municipio, coalesce(n.ano, d.ano) ano,
         CASE WHEN coalesce(n.ano, d.ano) >= 2017 THEN n.incremento ELSE greatest(d.incremento, 0) END incremento,
         d.acumulado
  FROM dif d FULL JOIN novo n USING (id_municipio, ano)
  WHERE coalesce(n.ano, d.ano) > 2000
  ORDER BY ALL
) TO '{saida}' (FORMAT parquet);
""")

pc = roda("prodes_celula", f"""
COPY (
  SELECT floor(centroid_lon / {PASSO})::INTEGER i, floor(centroid_lat / {PASSO})::INTEGER j, year ano,
         sum(area_km) area_km2
  FROM br_inpe_prodes_acumulado.desmatamento
  WHERE main_class = 'DESMATAMENTO' AND bioma_arquivo <> 'amazonia_legal' AND year > 2000
  GROUP BY ALL HAVING sum(area_km) > 0 ORDER BY ALL
) TO '{{saida}}' (FORMAT parquet);
""")

dm = roda("deter_mun", """
COPY (
  WITH a AS (
    SELECT GEOCODIBGE id_municipio, VIEW_DATE dia, coalesce(AREAMUNKM, area_km) area,
           CASE WHEN coalesce(CLASSNAME, class_name) IN ('DESMATAMENTO_CR', 'DESMATAMENTO_VEG')
                  OR coalesce(CLASSNAME, class_name) LIKE 'supressão%' THEN 'desmatamento'
                WHEN coalesce(CLASSNAME, class_name) IN ('DEGRADACAO', 'CS_DESORDENADO', 'CS_GEOMETRICO', 'CORTE_SELETIVO') THEN 'degradação'
                WHEN coalesce(CLASSNAME, class_name) IN ('CICATRIZ_DE_QUEIMADA', 'cicatriz de queimada') THEN 'queimada'
                WHEN coalesce(CLASSNAME, class_name) IN ('MINERACAO', 'mineração') THEN 'mineração' END classe
    FROM br_inpe_deter.avisos WHERE GEOCODIBGE IS NOT NULL)
  -- desmatamento, degradação e mineração no ano PRODES (agosto a julho), o do incremento ao
  -- lado: aviso de ago–dez conta no ano seguinte. Queimada fica no ano civil, o dos focos de
  -- calor com que ela aparece no modo Fogo.
  SELECT id_municipio,
         year(dia) + CASE WHEN classe <> 'queimada' AND month(dia) >= 8 THEN 1 ELSE 0 END ano,
         classe, count(*) avisos, sum(area) area_km2,
         max(max(dia)) OVER () ultimo  -- dia do aviso mais recente: até onde vai o último ano
  FROM a WHERE classe IS NOT NULL
  GROUP BY ALL ORDER BY ALL
) TO '{saida}' (FORMAT parquet);
""")


fm = roda("fogo_mun", """
COPY (
  SELECT id_municipio, ano, mes, count(*) focos FROM br_inpe_queimadas.microdados
  WHERE id_municipio IS NOT NULL AND """ + REFERENCIA + """ GROUP BY ALL ORDER BY ALL
) TO '{saida}' (FORMAT parquet);
""")

fc = roda("fogo_celula", f"""
COPY (
  SELECT floor(longitude / {PASSO})::INTEGER i, floor(latitude / {PASSO})::INTEGER j, ano, count(*) focos
  FROM br_inpe_queimadas.microdados WHERE longitude IS NOT NULL AND {REFERENCIA}
  GROUP BY ALL ORDER BY ALL
) TO '{{saida}}' (FORMAT parquet);
""")

ib = roda("ibama_mun", """
COPY (
  WITH emb AS (
    SELECT cod_municipio id_municipio, year(try_strptime(dat_embargo, '%Y-%m-%d %H:%M:%S')) ano,
           count(*) embargos, sum(qtd_area_embargada) area_embargada
    FROM br_ibama_embargos_novo.termo_embargo
    WHERE coalesce(sit_cancelado, 'N') <> 'S' GROUP BY ALL),
  aut AS (
    SELECT cod_municipio id_municipio, year(dat_hora_auto_infracao) ano,
           count(*) autos, count(*) FILTER (WHERE tipo_infracao = 'Flora') autos_flora,
           sum(val_auto_infracao) multas, sum(val_auto_infracao) FILTER (WHERE tipo_infracao = 'Flora') multas_flora
    FROM br_ibama_autos.auto_infracao
    WHERE coalesce(sit_cancelado, 'N') <> 'S' GROUP BY ALL)
  SELECT * FROM emb FULL JOIN aut USING (id_municipio, ano)
  WHERE ano BETWEEN 1990 AND year(current_date) AND id_municipio IS NOT NULL
  ORDER BY ALL
) TO '{saida}' (FORMAT parquet);
""")

fu = roda("fundiario", """
COPY (
  WITH mun AS (SELECT id_municipio, geometria g FROM br_geobr_mapas.municipio),
  ast AS (
    SELECT m.id_municipio, count(*) assentamentos, sum(a.num_famili) familias, sum(a.area_ha) area_assentamentos
    FROM br_incra_acervo.assentamentos a JOIN mun m ON ST_Contains(m.g, ST_Point(a.lon, a.lat))
    GROUP BY ALL),
  sig AS (
    SELECT municipio_::VARCHAR id_municipio, count(*) parcelas_sigef, sum(area_ha) area_sigef
    FROM br_incra_acervo.sigef_parcelas WHERE municipio_ IS NOT NULL GROUP BY ALL),
  snc AS (
    SELECT m.id_municipio, count(*) parcelas_snci, sum(s.area_ha) area_snci
    FROM br_incra_acervo.snci_parcelas s JOIN mun m ON ST_Contains(m.g, ST_Point(s.lon, s.lat))
    GROUP BY ALL)
  SELECT * FROM ast FULL JOIN sig USING (id_municipio) FULL JOIN snc USING (id_municipio)
  ORDER BY ALL
) TO '{saida}' (FORMAT parquet);
""")

# ---------- conferências ----------
def tot(df, col, ano):
    return df.filter(pl.col("ano") == ano)[col].sum()

print(f"PRODES 2023 (municípios): {tot(pm, 'incremento', 2023):,.0f} km² (incremento_municipio 2023: 24.108)".replace(",", "."))
print(f"PRODES 2010 (diferença do acumulado): {tot(pm, 'incremento', 2010):,.0f} km²".replace(",", "."))
print(f"PRODES polígonos 2023 na grade: {tot(pc, 'area_km2', 2023):,.0f} km²".replace(",", "."))
assert 20000 < tot(pm, "incremento", 2023) < 28000
print(dm.filter(pl.col("ano") == 2024).group_by("classe").agg(pl.col("area_km2").sum()).sort("classe"))
f24 = tot(fm, "focos", 2024)
print(f"focos 2024: {f24:,} (satélite de referência AQUA_M-T: 278.341)".replace(",", "."))
assert 270000 < f24 < 290000 and 215000 < tot(fm, "focos", 2020) < 230000
print(f"embargos ativos: {ib['embargos'].sum():,.0f} (gotcha: 110.439 não cancelados)".replace(",", "."))
print(f"autos de flora: {ib['autos_flora'].sum():,.0f}, multas de flora R$ {ib['multas_flora'].sum() / 1e9:.1f} bi".replace(",", "."))
print(f"fundiário: {fu['assentamentos'].sum():,.0f} assentamentos (acervo: 8.216), {fu['familias'].sum():,.0f} famílias; "
      f"SIGEF {fu['area_sigef'].sum() / 1e6:.0f} M ha".replace(",", "."))
