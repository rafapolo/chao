#!/usr/bin/env python3
"""Clima: chuva e temperatura por município (SISAM), estações do INMET e desastres
reconhecidos (S2ID).

Saídas em pipeline/dados/:
  clima_ano.parquet    — id_municipio, ano, chuva_mm, temp_media, temp_max (média das
                         leituras das 18 h), dias_sem_chuva (< 1 mm)
  clima_normal.parquet — id_municipio, mes, chuva_mm (média de 2000–2019)
  estacoes.parquet     — id_estacao, nome, lat, lon, ano, chuva_mm, temp_media, cobertura
                         (fração das horas com chuva medida); só anos com cobertura ≥ 0,9
  desastres.parquet    — id_municipio, ano (da ocorrência), grupo (seca, chuva, frio e
                         granizo, outros), reconhecimentos

Medido em 2026-10-22:
  - SISAM (`br_inpe_sisam.microdados`): 2000–2019, os 5.572 municípios, 4 leituras por
    dia (0, 6, 12, 18 h). `precipitacao_dia` só vem na leitura das 0 h (as outras são
    NULL): a chuva do ano é a soma dela. É saída de modelo, não pluviômetro: Sorriso
    tem 623 mm em 2015, quando a estação do INMET da cidade marca ~1.000–2.000 mm nos
    anos completos. Vale como anomalia relativa, com aviso.
  - INMET (`br_inmet_bdmep`): 633 estações, 2000–2025, leitura horária; 30% das horas de
    2020 com chuva NULL, e anos com quase tudo NULL (Sorriso 2005 e 2015: 1 mm). Só
    entra o ano com ≥ 90% das horas medidas. `estacao.geolocalizacao` é POINT(lat lon),
    com os eixos trocados (Manaus: POINT(-3,10 -60,02)).
  - S2ID (`br_sedec_desastres.reconhecimentos_vigentes`): só o retrato dos
    reconhecimentos VIGENTES na data da extração, sem a série histórica.
  - `br_ana_reservatorios.sin` só tem os reservatórios do SIN (hidrelétricas), não os
    açudes do semiárido: fica de fora.
"""
import polars as pl

from beelink import roda

if __name__ != "__main__":   # importar rodaria as extrações no beelink
    raise ImportError("baixa_clima.py é um script: rode python3 baixa_clima.py")

ca = roda("clima_ano", """
COPY (
  SELECT id_municipio, ano, sum(precipitacao_dia) chuva_mm, avg(temperatura) temp_media,
         avg(temperatura) FILTER (WHERE hour(data_hora) = 18) temp_max,
         count(*) FILTER (WHERE hour(data_hora) = 0 AND precipitacao_dia < 1) dias_sem_chuva
  FROM br_inpe_sisam.microdados WHERE id_municipio IS NOT NULL
  GROUP BY ALL ORDER BY ALL
) TO '{saida}' (FORMAT parquet);
""")

cn = roda("clima_normal", """
COPY (
  SELECT id_municipio, month(data_hora) mes, sum(precipitacao_dia) / count(DISTINCT ano) chuva_mm
  FROM br_inpe_sisam.microdados WHERE id_municipio IS NOT NULL AND hour(data_hora) = 0
  GROUP BY ALL ORDER BY ALL
) TO '{saida}' (FORMAT parquet);
""")

es = roda("estacoes", """
COPY (
  WITH e AS (
    SELECT id_estacao, estacao nome,
           ST_X(geolocalizacao::GEOMETRY) lat, ST_Y(geolocalizacao::GEOMETRY) lon   -- eixos trocados na fonte
    FROM br_inmet_bdmep.estacao),
  a AS (
    SELECT id_estacao, ano, sum(precipitacao_total) chuva_mm, avg(temperatura_bulbo_hora) temp_media,
           count(precipitacao_total) horas
    FROM br_inmet_bdmep.microdados GROUP BY id_estacao, ano)
  SELECT e.*, a.ano, a.chuva_mm, a.temp_media,
         a.horas / (CASE WHEN a.ano % 4 = 0 THEN 8784 ELSE 8760 END)::DOUBLE cobertura
  FROM e JOIN a USING (id_estacao)
  WHERE a.horas / (CASE WHEN a.ano % 4 = 0 THEN 8784 ELSE 8760 END)::DOUBLE >= 0.9 AND a.ano <= 2025
  ORDER BY ALL
) TO '{saida}' (FORMAT parquet);
""")

ds = roda("desastres", """
COPY (
  SELECT id_municipio, year(data_ocorrencia::DATE) ano,
         CASE WHEN nome_cobrade ILIKE '%seca%' OR nome_cobrade ILIKE '%estiagem%' THEN 'seca'
              WHEN nome_cobrade ILIKE '%chuva%' OR nome_cobrade ILIKE '%inunda%' OR nome_cobrade ILIKE '%enxurrada%'
                OR nome_cobrade ILIKE '%alagamento%' OR nome_cobrade ILIKE '%deslizamento%' THEN 'chuva'
              WHEN nome_cobrade ILIKE '%granizo%' OR nome_cobrade ILIKE '%geada%' OR nome_cobrade ILIKE '%frio%'
                OR nome_cobrade ILIKE '%vendaval%' THEN 'frio, granizo e vento'
              ELSE 'outros' END grupo,
         count(*) reconhecimentos
  FROM br_sedec_desastres.reconhecimentos_vigentes WHERE id_municipio IS NOT NULL
  GROUP BY ALL ORDER BY ALL
) TO '{saida}' (FORMAT parquet);
""")

# ---------- conferências ----------
s = ca.filter(pl.col("id_municipio") == "5107925").sort("ano")
print("SISAM Sorriso, chuva por ano:", s["chuva_mm"].round(0).to_list())
br = ca.group_by("ano").agg(pl.col("chuva_mm").median()).sort("ano")
print(f"SISAM, mediana nacional da chuva: {br['chuva_mm'].min():.0f}–{br['chuva_mm'].max():.0f} mm")
assert 800 < br["chuva_mm"].median() < 1800
print(f"INMET: {es['id_estacao'].n_unique()} estações com algum ano ≥ 90% medido; {es.height:,} estação×ano".replace(",", "."))
print(f"lat {es['lat'].min():.1f}…{es['lat'].max():.1f}, lon {es['lon'].min():.1f}…{es['lon'].max():.1f}")
assert -35 < es["lat"].min() and es["lat"].max() < 6 and -75 < es["lon"].min() and es["lon"].max() < -28
print(ds.group_by("grupo").agg(pl.col("reconhecimentos").sum()).sort("grupo"))
print("anos de ocorrência:", sorted(ds["ano"].unique().to_list()))
