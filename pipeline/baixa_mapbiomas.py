#!/usr/bin/env python3
"""Cobertura e transição do MapBiomas (Coleção 11) por município.

Saídas em pipeline/dados/:
  mapbiomas.parquet  — classe (rótulo da página), ano, id_municipio, area_ha
  transicao.parquet  — decada_fim, id_municipio, de (grupo), para (classe agrícola), area_ha
  bioma.parquet      — id_municipio, bioma de maior área

Duas armadilhas medidas em 2026-10-21:
  - a cobertura repete município × ano × classe quando o município atravessa dois
    biomas (3,17 M linhas, 2,80 M combinações): soma-se, nunca se pega uma linha;
  - na transição decenal, `ano` é o FIM da década (2000 = 1990→2000) e a área está
    em km², não em ha (Sorriso: 4.158 "para soja" em 2000 contra 373.880 ha de
    cobertura) — multiplica-se por 100.
"""
import polars as pl

from beelink import roda

if __name__ != "__main__":   # importar rodaria as extrações no beelink
    raise ImportError("baixa_mapbiomas.py é um script: rode python3 baixa_mapbiomas.py")

# rótulo da página <- classes do MapBiomas
CLASSES = {
    "Soja": [39], "Cana": [20], "Arroz": [40], "Algodão": [62],
    "Outras temporárias": [41], "Café": [46], "Citros": [47], "Dendê": [35],
    "Outras perenes": [48], "Silvicultura": [9], "Pastagem": [15],
    "Mosaico de usos": [21],
    "Vegetação natural": [3, 4, 5, 6, 49, 11, 12, 13, 29, 32, 50],
    "Água": [33, 31], "Área urbana": [24],
}
AGRICOLAS = ["Soja", "Cana", "Arroz", "Algodão", "Outras temporárias", "Café",
             "Citros", "Dendê", "Outras perenes", "Silvicultura", "Pastagem"]
ORIGEM = {  # de onde veio: grupo da classe de partida
    "Floresta": [3, 5, 6, 49], "Savana": [4],
    "Campo e outras naturais": [11, 12, 13, 29, 32, 50],
    "Pastagem": [15], "Outra lavoura ou mosaico": [9, 20, 21, 35, 39, 40, 41, 46, 47, 48, 62],
}


def caso(mapa, col):
    linhas = [f"WHEN {col} IN ({', '.join(map(str, ids))}) THEN '{nome}'"
              for nome, ids in mapa.items()]
    return "CASE " + " ".join(linhas) + " ELSE 'Outros' END"


cob = roda("mapbiomas", f"""
COPY (
  SELECT {caso(CLASSES, 'id_classe')} AS classe, ano::INTEGER AS ano, id_municipio,
         sum(area_ha) AS area_ha
  FROM br_mapbiomas_estatisticas.cobertura_municipio_classe
  GROUP BY ALL HAVING sum(area_ha) > 0
) TO '{{saida}}' (FORMAT parquet);
""")

agr_ids = [i for n in AGRICOLAS for i in CLASSES[n]]
tr = roda("transicao", f"""
COPY (
  SELECT ano::INTEGER AS decada_fim, id_municipio,
         {caso(ORIGEM, 'id_classe_de')} AS de,
         {caso(CLASSES, 'id_classe_para')} AS para,
         sum(area) * 100 AS area_ha
  FROM br_mapbiomas_estatisticas.transicao_municipio_de_para_decenal
  WHERE id_classe_para IN ({', '.join(map(str, agr_ids))})
    AND id_classe_de <> id_classe_para
  GROUP BY ALL HAVING sum(area) > 0
) TO '{{saida}}' (FORMAT parquet);
""")

bio = roda("bioma", """
COPY (
  SELECT id_municipio, arg_max(bioma, a) AS bioma FROM (
    SELECT id_municipio, bioma, sum(area_ha) a
    FROM br_mapbiomas_estatisticas.cobertura_municipio_classe WHERE ano = 2024
    GROUP BY ALL) GROUP BY 1
) TO '{saida}' (FORMAT parquet);
""")

# ---------- conferências ----------
soja = cob.filter((pl.col("classe") == "Soja") & (pl.col("ano") == 2024))["area_ha"].sum()
print(f"soja 2024 no satélite: {soja / 1e6:.1f} M ha (PAM: 46,2 M)")
tot = cob.filter(pl.col("ano") == 2024)["area_ha"].sum()
print(f"área total coberta 2024: {tot / 1e6:.0f} M ha (Brasil: 851 M)")
assert 830e6 < tot < 870e6
sor = cob.filter((pl.col("id_municipio") == "5107925") & (pl.col("ano") == 2000)
                 & (pl.col("classe") == "Soja"))["area_ha"].sum()
sor_tr = tr.filter((pl.col("id_municipio") == "5107925") & (pl.col("decada_fim") == 2000)
                   & (pl.col("para") == "Soja"))["area_ha"].sum()
print(f"Sorriso: soja 2000 {sor:,.0f} ha; chegou à soja 1990→2000 (sem a que já era) {sor_tr:,.0f} ha")
print(bio["bioma"].value_counts().sort("count", descending=True))
