#!/usr/bin/env python3
"""Garantia-Safra (por município × ano) e SICAR (retrato por município).

Saídas em pipeline/dados/:
  gsafra.parquet — id_municipio, ano, agricultores (NIS distintos), valor (R$)
  sicar.parquet  — id_municipio e as áreas do CAR (ha): imóveis por tamanho,
                   reserva legal, APP, pousio, vegetação nativa, área consolidada

Garantia-Safra: `codigo_municipio_siafi` vem com zero à esquerda ("0512") e o
`id_municipio_rf` do diretório sem ele — por texto casam 1.106 de 1.327, como
inteiro casam os 1.327. O ano é o do mês de referência do pagamento.

SICAR: `area_imovel` guarda 10 fotos mensais; usa-se só a mais recente
(2025-10-15) e sem cancelados (status CA). A APP entra só como `APP_TOTAL`
(os outros tipos se sobrepõem a ele) e com o corte area < 1e7 ha (há 9 valores
absurdos na fonte, até 1,7e50). As demais tabelas são uma foto só, com data por UF.
Imóvel: IRU = rural, AST = assentamento, PCT = povos e comunidades tradicionais.
Tamanho em módulos fiscais: pequeno < 4, médio 4–15, grande > 15.
"""
import polars as pl

from beelink import roda

if __name__ != "__main__":   # importar rodaria as extrações no beelink
    raise ImportError("baixa_cadastros.py é um script: rode python3 baixa_cadastros.py")

gs = roda("gsafra", """
COPY (
  SELECT d.id_municipio, left(g.mes_referencia, 4)::INTEGER ano,
         count(DISTINCT g.nis_favorecido) agricultores, sum(g.valor_parcela) valor
  FROM br_cgu_garantia_safra.garantia_safra g
  JOIN br_bd_diretorios_brasil.municipio d
    ON try_cast(d.id_municipio_rf AS INTEGER) = try_cast(g.codigo_municipio_siafi AS INTEGER)
  GROUP BY ALL
) TO '{saida}' (FORMAT parquet);
""")

sc = roda("sicar", """
COPY (
  WITH im AS (
    SELECT id_municipio, tipo, try_cast(modulos_fiscais AS DOUBLE) mf, area
    FROM br_sfb_sicar.area_imovel
    WHERE data_extracao = (SELECT max(data_extracao) FROM br_sfb_sicar.area_imovel)
      AND status <> 'CA'),
  i AS (
    SELECT id_municipio,
      count(*) imoveis,
      count(*) FILTER (WHERE tipo = 'IRU' AND mf < 4) imoveis_pequenos,
      count(*) FILTER (WHERE tipo = 'IRU' AND mf >= 4 AND mf <= 15) imoveis_medios,
      count(*) FILTER (WHERE tipo = 'IRU' AND mf > 15) imoveis_grandes,
      sum(area) FILTER (WHERE tipo = 'IRU' AND mf < 4) area_pequenos,
      sum(area) FILTER (WHERE tipo = 'IRU' AND mf >= 4 AND mf <= 15) area_medios,
      sum(area) FILTER (WHERE tipo = 'IRU' AND mf > 15) area_grandes,
      sum(area) FILTER (WHERE tipo = 'AST') area_assentamentos,
      sum(area) FILTER (WHERE tipo = 'PCT') area_tradicionais,
      sum(area) area_cadastrada
    FROM im GROUP BY 1),
  soma AS (
    SELECT id_municipio, 'reserva_legal' k, sum(area) v FROM br_sfb_sicar.reserva_legal GROUP BY 1
    UNION ALL SELECT id_municipio, 'app', sum(area) FROM br_sfb_sicar.app
      WHERE tipo = 'APP_TOTAL' AND area < 1e7 GROUP BY 1
    UNION ALL SELECT id_municipio, 'pousio', sum(area) FROM br_sfb_sicar.area_pousio GROUP BY 1
    UNION ALL SELECT id_municipio, 'vegetacao_nativa', sum(area) FROM br_sfb_sicar.vegetacao_nativa GROUP BY 1
    UNION ALL SELECT id_municipio, 'consolidada', sum(area) FROM br_sfb_sicar.area_consolidada GROUP BY 1),
  p AS (PIVOT soma ON k USING sum(v) GROUP BY id_municipio)
  SELECT * FROM i FULL JOIN p USING (id_municipio)
) TO '{saida}' (FORMAT parquet);
""")

# ---------- conferências ----------
print(f"Garantia-Safra: {gs['id_municipio'].n_unique()} municípios, anos {gs['ano'].min()}–{gs['ano'].max()}")
print(gs.group_by("ano").agg(pl.col("agricultores").sum(), (pl.col("valor").sum() / 1e6).alias("R$ mi")).sort("ano"))
print(f"SICAR: {sc.height} municípios, {sc['imoveis'].sum():,} imóveis, "
      f"{sc['area_cadastrada'].sum() / 1e6:.0f} M ha (gotcha: 715,8 sem cancelados na foto de 2025-10)".replace(",", "."))
print(f"APP total: {sc['app'].sum() / 1e6:.1f} M ha (gotcha: 32,25)")
