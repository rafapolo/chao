#!/usr/bin/env python3
"""Contornos de regiões e a divisão regional de cada município.

Saídas em pipeline/dados/:
  regioes.parquet — tipo (uf, regiao, pais, bioma, semiarido, amazonia_legal),
                    nome, wkb simplificado (~1 km): só traço por cima do mapa
  sedes.parquet   — id_municipio, lon, lat da sede (2010; os 5 municípios de 2013 ficam
                    com o ponto interno do polígono, em monta_pagina.py)
  divisao.parquet — id_municipio, semiarido, amazonia_legal (booleanos) e o código
                    e o nome de região, mesorregião, microrregião, região
                    intermediária e imediata e região metropolitana

Medido em 2026-10-22:
  - `br_geobr_mapas.bioma` tem dois anos; em 2019 a Amazônia está com geometria
    NULL. Entram os biomas de 2019, mais a Amazônia de 2004; o "Sistema Costeiro"
    de 2019 e as massas d'água de 2004 ficam de fora.
  - `semiarido` é a lista dos 1.262 municípios, cada um com o polígono dele: o
    contorno é a união deles. A união crua deixa frestas entre vizinhos (centenas
    de furos); um buffer de ida e volta de 0,003° as fecha, e os furos que sobram
    com menos de 50 km² saem em monta_pagina.py.
  - `limite_vizinhanca` NÃO é a divisa entre municípios: são os limites dos
    bairros (vizinhanças) do Censo, 14.832 polígonos intraurbanos. Não serve para
    as divisas e fica de fora.
  - a pertença à Amazônia Legal e às regiões vem do diretório de municípios
    (`br_bd_diretorios_brasil.municipio`), não de interseção geométrica.
"""
import polars as pl

from beelink import roda

TOL = 0.01   # ~1 km: contorno de região, desenhado como traço

reg = roda("regioes", f"""
COPY (
  WITH r AS (
    SELECT 'uf' tipo, sigla_uf nome, geometria g FROM br_geobr_mapas.uf
    UNION ALL SELECT 'regiao', nome_regiao, geometria FROM br_geobr_mapas.regiao
    UNION ALL SELECT 'pais', 'Brasil', geometria FROM br_geobr_mapas.pais
    UNION ALL SELECT 'bioma', nome_bioma, geometria FROM br_geobr_mapas.bioma
      WHERE (ano = 2019 AND nome_bioma <> 'Sistema Costeiro' AND geometria IS NOT NULL)
         OR (ano = 2004 AND nome_bioma = 'Amazônia')
    UNION ALL SELECT 'semiarido', 'Semiárido',
      ST_Buffer(ST_Union_Agg(ST_Buffer(ST_MakeValid(geometria), 0.003)), -0.003) FROM br_geobr_mapas.semiarido
    UNION ALL SELECT 'amazonia_legal', 'Amazônia Legal', geometria FROM br_geobr_mapas.amazonia_legal)
  SELECT tipo, nome, ST_AsWKB(ST_SimplifyPreserveTopology(ST_MakeValid(g), {TOL})) wkb
  FROM r ORDER BY tipo, nome
) TO '{{saida}}' (FORMAT parquet);
""")

sd = roda("sedes", """
COPY (
  SELECT id_municipio, ST_X(geometria) lon, ST_Y(geometria) lat
  FROM br_geobr_mapas.sede_municipal WHERE ano = 2010 ORDER BY 1
) TO '{saida}' (FORMAT parquet);
""")

div = roda("divisao", """
COPY (
  SELECT d.id_municipio,
         s.id_municipio IS NOT NULL semiarido,
         coalesce(d.amazonia_legal::VARCHAR IN ('1', 'true'), false) amazonia_legal,
         d.nome_regiao regiao,
         d.id_mesorregiao, d.nome_mesorregiao, d.id_microrregiao, d.nome_microrregiao,
         d.id_regiao_intermediaria, d.nome_regiao_intermediaria,
         d.id_regiao_imediata, d.nome_regiao_imediata,
         d.id_regiao_metropolitana, d.nome_regiao_metropolitana
  FROM br_bd_diretorios_brasil.municipio d
  LEFT JOIN (SELECT DISTINCT id_municipio FROM br_geobr_mapas.semiarido) s USING (id_municipio)
  ORDER BY d.id_municipio
) TO '{saida}' (FORMAT parquet);
""")

# ---------- conferências ----------
print(reg.group_by("tipo").len().sort("tipo"))
print(f"sedes: {sd.height} (geobr 2010: 5.565)")
assert sd.height == 5565 and sd["lon"].is_between(-75, -28).all()
print(f"semiárido: {div['semiarido'].sum()} municípios (ref. 1.262 na delimitação de 2021)")
print(f"Amazônia Legal: {div['amazonia_legal'].sum()} municípios (ref. 772)")
for c in ["regiao", "id_mesorregiao", "id_microrregiao", "id_regiao_intermediaria", "id_regiao_imediata"]:
    print(f"  {c}: {div[c].n_unique()} distintos")
assert reg.filter(pl.col("tipo") == "uf").height == 27
assert 1200 < div["semiarido"].sum() < 1300
assert 700 < div["amazonia_legal"].sum() < 850
