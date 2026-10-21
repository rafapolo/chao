#!/usr/bin/env python3
"""Crédito rural (SICOR): glebas de custeio agrícola e perdas do Proagro.

Saídas em pipeline/dados/:
  glebas_celula.parquet  — i, j (grade de 0,05°), produto, safra, glebas, area_ha
  glebas_mun.parquet     — id_municipio, produto, safra, glebas, area_ha
  proagro_celula.parquet — i, j, evento, safra, perdas, area_ha
  proagro_mun.parquet    — id_municipio, produto, evento, safra, perdas, area_ha

As glebas são AMOSTRA de localização, não total: `recurso_publico_gleba` só traz
crédito com recurso público (custeio de soja 2023/24 com gleba = 3,3 M ha contra
46 M ha da PAM). Só entra `atividade = 'Agrícola' AND finalidade = 'Custeio'`.
A área da gleba é a do polígono; a do Proagro é a área da comprovação de perda,
repartida igualmente entre as glebas da operação quando vai para a grade.
A grade é guardada sem filtro aqui — o corte de privacidade (célula com menos de
5 glebas ou perdas) é aplicado em monta_pagina.py, antes de embutir.
"""
import polars as pl

from beelink import roda

PASSO = 0.05
EVENTO = """CASE r.id_evento
  WHEN '48' THEN 'Seca' WHEN '17' THEN 'Chuva excessiva' WHEN '135' THEN 'Chuva excessiva'
  WHEN '127' THEN 'Chuva excessiva' WHEN '55' THEN 'Chuva excessiva'
  WHEN '24' THEN 'Geada' WHEN '31' THEN 'Granizo'
  WHEN '86' THEN 'Temperatura' WHEN '62' THEN 'Temperatura'
  WHEN '79' THEN 'Vento' WHEN '61' THEN 'Vento'
  WHEN '110' THEN 'Doença ou praga' ELSE 'Outros' END"""

BASE_GLEBA = f"""
  WITH g AS (
    SELECT g.id_referencia_bacen, g.numero_ordem,
           ST_X(ST_Centroid(g.geometria)) lon, ST_Y(ST_Centroid(g.geometria)) lat,
           least(ST_Area_Spheroid(g.geometria) / 1e4, 20000) area_ha
    FROM br_bcb_sicor.recurso_publico_gleba g WHERE g.geometria IS NOT NULL),
  op AS (
    SELECT o.id_referencia_bacen, o.numero_ordem, e.produto,
           left(o.ano_safra_emissao, 4)::INTEGER safra
    FROM br_bcb_sicor.operacao o
    JOIN br_bcb_sicor.empreendimento e ON e.id_empreendimento = o.id_empreendimento
    WHERE e.atividade = 'Agrícola' AND e.finalidade = 'Custeio')
"""

gc = roda("glebas_celula", "COPY (" + BASE_GLEBA + f"""
  SELECT floor(lon / {PASSO})::INTEGER i, floor(lat / {PASSO})::INTEGER j,
         produto, safra, count(*) glebas, sum(area_ha) area_ha
  FROM g JOIN op USING (id_referencia_bacen, numero_ordem)
  GROUP BY ALL
) TO '{{saida}}' (FORMAT parquet);
""")

gm = roda("glebas_mun", "COPY (" + BASE_GLEBA + """
  SELECT c.id_municipio, produto, safra, count(*) glebas, sum(area_ha) area_ha
  FROM g JOIN op USING (id_referencia_bacen, numero_ordem)
  JOIN br_bcb_sicor.recurso_publico_complemento_operacao c USING (id_referencia_bacen, numero_ordem)
  GROUP BY ALL
) TO '{saida}' (FORMAT parquet);
""")

BASE_PROAGRO = f"""
  WITH r AS (
    SELECT r.id_referencia_bacen, r.numero_ordem, {EVENTO} evento, r.area,
           left(o.ano_safra_emissao, 4)::INTEGER safra, e.produto
    FROM br_bcb_sicor.proagro_rcp r
    JOIN br_bcb_sicor.operacao o USING (id_referencia_bacen, numero_ordem)
    JOIN br_bcb_sicor.empreendimento e ON e.id_empreendimento = o.id_empreendimento
    WHERE r.area > 0 AND r.area < 50000)
"""

pc = roda("proagro_celula", "COPY (" + BASE_PROAGRO + f"""
  , gl AS (
    SELECT id_referencia_bacen, numero_ordem,
           ST_X(ST_Centroid(geometria)) lon, ST_Y(ST_Centroid(geometria)) lat,
           count(*) OVER (PARTITION BY id_referencia_bacen, numero_ordem) n
    FROM br_bcb_sicor.proagro_rcp_gleba WHERE geometria IS NOT NULL)
  SELECT floor(lon / {PASSO})::INTEGER i, floor(lat / {PASSO})::INTEGER j, evento, safra,
         count(DISTINCT (id_referencia_bacen, numero_ordem)) perdas, sum(area / n) area_ha
  FROM r JOIN gl USING (id_referencia_bacen, numero_ordem)
  GROUP BY ALL
) TO '{{saida}}' (FORMAT parquet);
""")

pm = roda("proagro_mun", "COPY (" + BASE_PROAGRO + """
  SELECT c.id_municipio, produto, evento, safra, count(*) perdas, sum(area) area_ha
  FROM r JOIN br_bcb_sicor.recurso_publico_complemento_operacao c USING (id_referencia_bacen, numero_ordem)
  GROUP BY ALL
) TO '{saida}' (FORMAT parquet);
""")

# ---------- conferências ----------
s = gm.filter((pl.col("produto") == "SOJA") & (pl.col("safra") == 2023))
print(f"glebas de soja 2023/24: {s['glebas'].sum():,} glebas, {s['area_ha'].sum() / 1e6:.2f} M ha "
      "(área de operação financiada medida: 3,27 M ha)".replace(",", "."))
print(f"glebas na grade: {gc['glebas'].sum():,}; com município: {gm['glebas'].sum():,}".replace(",", "."))
print(f"proagro: {pm['perdas'].sum():,} perdas, {pm['area_ha'].sum() / 1e6:.1f} M ha".replace(",", "."))
print(pm.group_by("evento").agg(pl.col("area_ha").sum() / 1e6).sort("area_ha", descending=True))
print(f"safras: {gm['safra'].min()}–{gm['safra'].max()}")
