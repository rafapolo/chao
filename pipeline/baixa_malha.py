#!/usr/bin/env python3
"""Malha municipal e máscara do que não é rural.

Saídas em pipeline/dados/:
  malha.parquet    — id_municipio, nome, sigla_uf, area_km2 (do polígono original),
                     wkb (simplificado por cobertura: as divisas continuam encaixadas)
  mascara.parquet  — id_municipio, wkb da máscara unida e as áreas de cada parte:
                     setor urbano de 2010 + pegada urbana, terra indígena, UC de
                     proteção integral; area_mascara_km2 é a da UNIÃO (as partes se
                     sobrepõem, a soma delas passaria da área real)

A área rural do município é area_km2 − area_mascara_km2. A página desenha o
município inteiro e a máscara por cima, em cinza: dá o mesmo efeito que recortar o
polígono rural, sem a diferença geométrica.
"""
import polars as pl

from beelink import consulta, roda

TOL_MUN = 0.005    # ~550 m: some no zoom de estado, aparece só perto do teto
TOL_MASC = 0.003

PROTECAO_INTEGRAL = ("Estação Ecológica", "Reserva Biológica", "Parque",
                     "Monumento Natural", "Refúgio de Vida Silvestre")

malha = roda("malha", f"""
COPY (
  WITH c AS (
    SELECT ST_CoverageSimplify_Agg(geometria, {TOL_MUN} ORDER BY id_municipio) g
    FROM br_geobr_mapas.municipio),
  partes AS (SELECT unnest(ST_Dump(g)) u FROM c),
  simpl AS (
    SELECT u.path[1] AS ordem, ST_Union_Agg(u.geom) geom FROM partes GROUP BY 1),
  orig AS (
    SELECT row_number() OVER (ORDER BY id_municipio) AS ordem, id_municipio,
           ST_Area_Spheroid(geometria) / 1e6 AS area_km2,
           ST_X(ST_PointOnSurface(geometria)) AS lon, ST_Y(ST_PointOnSurface(geometria)) AS lat
    FROM br_geobr_mapas.municipio)
  SELECT o.id_municipio, d.nome, d.sigla_uf, o.area_km2, o.lon, o.lat,
         ST_AsWKB(s.geom) AS wkb
  FROM orig o JOIN simpl s USING (ordem)
  LEFT JOIN br_bd_diretorios_brasil.municipio d USING (id_municipio)
  ORDER BY o.id_municipio
) TO '{{saida}}' (FORMAT parquet);
""")

pi = ", ".join(f"'{c}'" for c in PROTECAO_INTEGRAL)
mascara = roda("mascara", f"""
COPY (
  WITH mun AS (SELECT id_municipio, ST_MakeValid(geometria) g FROM br_geobr_mapas.municipio),
  urb AS (
    SELECT id_municipio, ST_MakeValid(geometria) g FROM br_geobr_mapas.setor_censitario_2010
    WHERE zona = 'URBANO'
    UNION ALL
    SELECT id_municipio, ST_MakeValid(geometria) FROM br_geobr_mapas.pegada_urbana),
  urb_m AS (
    SELECT u.id_municipio, ST_Intersection(ST_Union_Agg(u.g), any_value(m.g)) g
    FROM urb u JOIN mun m USING (id_municipio) GROUP BY 1),
  ti_m AS (
    SELECT m.id_municipio, ST_Union_Agg(ST_Intersection(m.g, ST_MakeValid(t.geometria))) g
    FROM mun m JOIN br_geobr_mapas.terra_indigena t ON ST_Intersects(m.g, t.geometria)
    GROUP BY 1),
  uc_m AS (
    SELECT m.id_municipio, ST_Union_Agg(ST_Intersection(m.g, ST_MakeValid(u.geometria))) g
    FROM mun m JOIN br_geobr_mapas.unidade_conservacao u ON ST_Intersects(m.g, u.geometria)
    WHERE u.categoria IN ({pi})
    GROUP BY 1),
  todas AS (
    SELECT id_municipio, g FROM urb_m UNION ALL
    SELECT id_municipio, g FROM ti_m UNION ALL
    SELECT id_municipio, g FROM uc_m),
  uniao AS (
    SELECT id_municipio, ST_Union_Agg(ST_MakeValid(g)) g FROM todas
    WHERE g IS NOT NULL AND NOT ST_IsEmpty(g) GROUP BY 1)
  SELECT x.id_municipio,
         ST_Area_Spheroid(x.g) / 1e6 AS area_mascara_km2,
         coalesce(ST_Area_Spheroid(u.g) / 1e6, 0) AS area_urbana_km2,
         coalesce(ST_Area_Spheroid(t.g) / 1e6, 0) AS area_ti_km2,
         coalesce(ST_Area_Spheroid(c.g) / 1e6, 0) AS area_uc_km2,
         ST_AsWKB(ST_SimplifyPreserveTopology(x.g, {TOL_MASC})) AS wkb
  FROM uniao x
  LEFT JOIN urb_m u USING (id_municipio)
  LEFT JOIN ti_m t USING (id_municipio)
  LEFT JOIN uc_m c USING (id_municipio)
  ORDER BY 1
) TO '{{saida}}' (FORMAT parquet);
""")

# ---------- conferências ----------
area_br = malha["area_km2"].sum()
print(f"área do Brasil: {area_br:,.0f} km² (IBGE: 8.510.418)".replace(",", "."))
assert 8.3e6 < area_br < 8.7e6, "área total fora do esperado"
assert malha["nome"].null_count() == 0, "município sem nome no diretório"
s = malha.filter(pl.col("id_municipio") == "5107925").row(0, named=True)
print(f"Sorriso: {s['area_km2']:,.0f} km² (IBGE: 9.329)".replace(",", "."))

j = malha.join(mascara, on="id_municipio", how="left").with_columns(
    pl.col("area_mascara_km2").fill_null(0))
fr = (j["area_mascara_km2"].sum() / area_br)
print(f"máscara: {j['area_mascara_km2'].sum():,.0f} km² ({fr:.1%} do país)".replace(",", "."))
print("  urbana  :", f"{mascara['area_urbana_km2'].sum():,.0f} km²".replace(",", "."))
print("  TI      :", f"{mascara['area_ti_km2'].sum():,.0f} km² (FUNAI ~1,17 M km²)".replace(",", "."))
print("  UC (PI) :", f"{mascara['area_uc_km2'].sum():,.0f} km²".replace(",", "."))
excesso = j.filter(pl.col("area_mascara_km2") > pl.col("area_km2") * 1.01)
print(f"municípios com máscara > área: {excesso.height}")
cap = j.filter(pl.col("id_municipio") == "3550308").row(0, named=True)
print(f"São Paulo capital: {cap['area_mascara_km2'] / cap['area_km2']:.0%} mascarado")

# ---------- áreas mínimas comparáveis ----------
# Um município desmembrado depois de 1974 não tem dado antes de existir, e o pai,
# nesses anos, traz na PAM e na PPM a área do território inteiro da época — que a
# malha atual desenha menor. As 3.800 AMC do geobr agrupam os municípios de hoje
# em territórios estáveis; a página usa o grupo nos anos em que ele está
# incompleto. `id_municipio` da tabela é a lista de membros, separada por vírgula.
amc = roda("amc", """
COPY (
  SELECT id_amc, unnest(string_split(id_municipio, ',')) AS id_municipio
  FROM br_geobr_mapas.area_minima_comparavel_2010
) TO '{saida}' (FORMAT parquet);
""")
cobre = amc["id_municipio"].is_in(malha["id_municipio"].to_list()).sum()
print(f"AMC: {amc['id_amc'].n_unique()} grupos, {cobre} de {malha.height} municípios da malha cobertos")
