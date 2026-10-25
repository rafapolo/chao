#!/usr/bin/env python3
"""Terra e imóvel: crédito, embargo, desmatamento e terra pública cruzados pelo imóvel
do CAR, no beelink, e devolvidos só como somas por município (plano em tasks/done/imovel.md).

    python3 baixa_imovel.py              # todas as etapas (~3 min)
    python3 baixa_imovel.py gleba agrega # só algumas ("terra-" pula a parte do INCRA)

Etapas no beelink, cada uma um parquet em ~/bragro_tmp/imovel/ que NÃO volta:
  car       — um imóvel por id_imovel da foto 2025-10-15, polígono válido, por UF
  camadas   — APP (só APP_TOTAL, < 1e7 ha), reserva legal, vegetação nativa e área
              consolidada declaradas, somadas por imóvel
  gleba     — cada gleba do SICOR, e cada gleba de perda do Proagro, no imóvel (não
              cancelado) que contém o centroide; se cai em mais de um, o de maior sobreposição
  operacao  — a ponte operação → imóvel: pelo id_car (de 2019 em diante), senão pela gleba
              do SICOR, senão pela gleba do Proagro; `fracao` reparte a operação e soma 1
  embargo   — termos do IBAMA (sem cancelados) e do ICMBio por polígono (fração da área
              embargada em cada imóvel, desprezada abaixo de 1%) ou, no IBAMA, pelo ponto
  auto      — autos de flora, pelo polígono da área autuada ou pelo ponto
  desmat    — polígonos do PRODES (2016–) e do DETER (desmatamento e supressão) cruzados
              com o imóvel: a área do alerta se reparte pela interseção
  terra     — área do imóvel em TI, em UC de proteção integral e em floresta pública não
              destinada (CNFP tipo B) e na Lista de Desmatamento Ilegal do Pará; cobertura
              por parcelas do SIGEF; ponto do imóvel dentro de assentamento (polígonos do INCRA)

Saídas em pipeline/dados/ (só agregados; nenhum id_imovel, CPF, CNPJ ou nome):
  imovel_mun.parquet — id_municipio (o do imóvel) e o retrato do CAR: imoveis, area_car,
                       area_ti, area_ucpi, area_fpnd, area_ldi (só com 5+ imóveis atingidos), area_analisada, imoveis_sigef,
                       imoveis_assent, app, rl, veg_nativa, consolidada (ha); nulo onde há
                       menos de 5 imóveis
  imovel_ano.parquet — id_municipio, ano (safra de emissão, ou ano do PRODES): crédito em
                       imóvel com desmatamento durante a operação (cd_valor, cd_area),
                       com embargo vigente na emissão (ce_valor, ce_area), crédito ligado
                       a um CAR (ccar_valor), perda comprovada no Proagro em imóvel com
                       desmatamento ou embargo (pp_area, ha); PRODES no município e dentro
                       de CAR (desm_km2, desm_car_km2). Cada medida de crédito só com 5 ou
                       mais operações e 5 ou mais imóveis; ops_* e imo_* são as contagens
                       por marca (desm, emb, perda, car), para a conferência do corte.

Medido em 2026-10-25 (gotchas no rodado: br_bcb_sicor, br_sfb_sicar, br_ibama_embargos_novo,
br_rf_cafir):
  - `recurso_publico_propriedade.id_car` é o código do CAR sem hífens; casa ~100% com a
    foto 2025-10-15 de 2019 a 2024. Antes de 2018 vem vazio: 2016–2018 dependem da gleba.
  - uma operação tem em média 1,65 CARs: sem `fracao` o R$ conta duas vezes.
  - os CARs se sobrepõem (12% inteiros dentro de outro): áreas de alerta e embargo somam
    pela origem (o alerta, o termo), nunca por imóvel.
  - a foto do CAR é uma só para todas as safras: um imóvel inscrito em 2024 aparece como
    se existisse em 2016. A página avisa.
  - "área financiada maior que o imóvel" saiu: caía de 2,2% das operações (2019) para
    0,17% (2023) também com a foto do CAR de 2024-10, então não era efeito da foto única.
    A divergência código × gleba cai no mesmo ano (≈20% → 6%): mudança de registro no
    SICOR, não do campo.
"""
import sys

import polars as pl

from beelink import REMOTO, prepara, roda

IM = f"{REMOTO}/imovel"
CAR = f"read_parquet('{IM}/car/*/*.parquet', hive_partitioning = true)"
ATIVO = f"(SELECT id_imovel, id_municipio, area_ha, geometria FROM {CAR} WHERE status <> 'CA')"
BRASIL = "BETWEEN -74 AND -28"   # longitude; latitude vai em BETWEEN -34 AND 6
MIN = 5   # o mesmo corte de privacidade das glebas e do crédito (MIN_CELULA)


def xy(lon, lat):
    """Ponto a partir de duas colunas de texto com vírgula decimal, só dentro do Brasil."""
    x = f"try_cast(replace({lon}, ',', '.') AS DOUBLE)"
    y = f"try_cast(replace({lat}, ',', '.') AS DOUBLE)"
    return f"CASE WHEN {x} {BRASIL} AND {y} BETWEEN -34 AND 6 THEN ST_Point({x}, {y}) END"


def cortes():
    """As somas de crédito por município × safra, cada uma só com MIN ou mais operações e
    MIN ou mais imóveis marcados; e o resto (operações em CAR sem a marca) com 0 ou MIN
    ou mais, senão ccar_valor menos a soma revelaria um grupo cortado."""
    ops = "count(DISTINCT (id_referencia_bacen, numero_ordem))"
    imo = "count(DISTINCT id_imovel)"
    sai = []
    for nome, col, marca in [("cd_valor", "v", "desm"), ("cd_area", "a", "desm"), ("ce_valor", "v", "emb"),
                             ("ce_area", "a", "emb"), ("pp_area", "p", "perda"), ("ccar_valor", "v", None)]:
        f = f" FILTER (WHERE {marca})" if marca else ""
        resto = f" AND ({ops} - {ops}{f} = 0 OR {ops} - {ops}{f} >= {MIN})" if marca else ""
        sai.append(f"CASE WHEN {ops}{f} >= {MIN} AND {imo}{f} >= {MIN}{resto} THEN sum({col}){f} END {nome}")
    # as contagens vão junto (não entram na página): monta_pagina.py confere o corte
    for marca in ("desm", "emb", "perda", None):
        f = f" FILTER (WHERE {marca})" if marca else ""
        sai += [f"{ops}{f} ops_{marca or 'car'}", f"{imo}{f} imo_{marca or 'car'}"]
    return ",\n         ".join(sai)


ETAPAS = {}


def etapa(f):
    ETAPAS[f.__name__] = f
    return f


@etapa
def car():
    prepara("car", f"""
COPY (
  SELECT id_imovel, any_value(sigla_uf) sigla_uf, any_value(id_municipio) id_municipio,
         any_value(area) area_ha, any_value(try_cast(modulos_fiscais AS DOUBLE)) modulos_fiscais,
         any_value(status) status, any_value(condicao) condicao,
         any_value(data_atualizacao_car) data_atualizacao_car, ST_MakeValid(any_value(geometria)) geometria
  FROM br_sfb_sicar.area_imovel WHERE data_extracao = '2025-10-15'
  GROUP BY id_imovel ORDER BY id_imovel
) TO '{IM}/car' (FORMAT parquet, COMPRESSION zstd, PARTITION_BY (sigla_uf), OVERWRITE_OR_IGNORE);
""")


@etapa
def camadas():
    prepara("camadas", f"""
COPY (
  SELECT id_imovel, sum(area) FILTER (WHERE t = 'app') app, sum(area) FILTER (WHERE t = 'rl') rl,
         sum(area) FILTER (WHERE t = 'vn') veg_nativa, sum(area) FILTER (WHERE t = 'ac') consolidada
  FROM (SELECT id_imovel, 'app' t, area FROM br_sfb_sicar.app WHERE tipo = 'APP_TOTAL' AND area < 1e7
        UNION ALL SELECT id_imovel, 'rl', area FROM br_sfb_sicar.reserva_legal
        UNION ALL SELECT id_imovel, 'vn', area FROM br_sfb_sicar.vegetacao_nativa
        UNION ALL SELECT id_imovel, 'ac', area FROM br_sfb_sicar.area_consolidada)
  GROUP BY id_imovel ORDER BY id_imovel
) TO '{IM}/camadas.parquet' (FORMAT parquet, COMPRESSION zstd);
""")


def _gleba(tabela, saida):
    # Primeiro só as chaves (gleba × imóvel que contém o centroide); a interseção, que é
    # cara, só para as glebas que caem em mais de um imóvel.
    return prepara(saida, f"""
SET threads = 14;
CREATE TEMP TABLE g AS
  SELECT id_referencia_bacen, numero_ordem, indice_gleba, ST_Area(geometria) a, geometria
  FROM br_bcb_sicor.{tabela} WHERE geometria IS NOT NULL;
CREATE TEMP TABLE h AS
  SELECT g.id_referencia_bacen, g.numero_ordem, g.indice_gleba, c.id_imovel
  FROM g JOIN {ATIVO} c ON ST_Intersects(c.geometria, ST_Centroid(g.geometria));
CREATE TEMP TABLE n AS
  SELECT id_referencia_bacen, numero_ordem, indice_gleba, count(*) n FROM h GROUP BY ALL;
COPY (
  WITH um AS (SELECT h.*, 1.0 sobre FROM h JOIN n USING (id_referencia_bacen, numero_ordem, indice_gleba) WHERE n = 1),
  varios AS (
    SELECT h.*, ST_Area(ST_Intersection(g.geometria, c.geometria)) / nullif(g.a, 0) sobre
    FROM h JOIN n USING (id_referencia_bacen, numero_ordem, indice_gleba)
    JOIN g USING (id_referencia_bacen, numero_ordem, indice_gleba)
    JOIN {ATIVO} c USING (id_imovel)
    WHERE n > 1
    QUALIFY row_number() OVER (PARTITION BY id_referencia_bacen, numero_ordem, indice_gleba
                               ORDER BY sobre DESC NULLS LAST, id_imovel) = 1)
  SELECT x.id_referencia_bacen, x.numero_ordem, x.indice_gleba, x.id_imovel, x.sobre, g.a area_grau
  FROM (SELECT * FROM um UNION ALL SELECT * FROM varios) x
  JOIN g USING (id_referencia_bacen, numero_ordem, indice_gleba)
  ORDER BY ALL
) TO '{IM}/{saida}.parquet' (FORMAT parquet, COMPRESSION zstd);
SELECT (SELECT count(*) FROM g) glebas, (SELECT count(*) FROM n) com_car, (SELECT count(*) FROM n WHERE n > 1) varios;
""")


@etapa
def gleba():
    print(_gleba("recurso_publico_gleba", "gleba"))
    # o Proagro tem glebas próprias (a perda comunicada); 2% sem geometria convertida
    # (gotcha proagro_gleba_wkt_invalido) ficam de fora
    print(_gleba("proagro_rcp_gleba", "gleba_proagro"))


@etapa
def operacao():
    # fracao: pelo código, a área de cada CAR dentro da soma dos CARs da operação; pela
    # gleba, a área das glebas da operação em cada imóvel.
    print(prepara("operacao", f"""
CREATE TEMP TABLE cod AS
  WITH p AS (SELECT DISTINCT id_referencia_bacen, numero_ordem, id_car FROM br_bcb_sicor.recurso_publico_propriedade
             WHERE id_car IS NOT NULL),
  c AS (SELECT replace(id_imovel, '-', '') k, id_imovel, area_ha FROM {CAR})
  SELECT p.id_referencia_bacen, p.numero_ordem, c.id_imovel,
         coalesce(c.area_ha / nullif(sum(c.area_ha) OVER w, 0), 1.0 / count(*) OVER w) fracao
  FROM p JOIN c ON c.k = p.id_car
  WINDOW w AS (PARTITION BY p.id_referencia_bacen, p.numero_ordem);
CREATE TEMP TABLE gl AS
  SELECT id_referencia_bacen, numero_ordem, id_imovel,
         CASE WHEN st > 0 THEN a / st ELSE 1.0 / n END fracao   -- glebas de área 0: partes iguais
  FROM (SELECT *, sum(a) OVER (PARTITION BY id_referencia_bacen, numero_ordem) st,
               count(*) OVER (PARTITION BY id_referencia_bacen, numero_ordem) n
        FROM (SELECT id_referencia_bacen, numero_ordem, id_imovel, sum(area_grau) a
              FROM '{IM}/gleba.parquet' GROUP BY id_referencia_bacen, numero_ordem, id_imovel));
CREATE TEMP TABLE pg AS
  SELECT id_referencia_bacen, numero_ordem, id_imovel,
         CASE WHEN st > 0 THEN a / st ELSE 1.0 / n END fracao
  FROM (SELECT *, sum(a) OVER (PARTITION BY id_referencia_bacen, numero_ordem) st,
               count(*) OVER (PARTITION BY id_referencia_bacen, numero_ordem) n
        FROM (SELECT id_referencia_bacen, numero_ordem, id_imovel, sum(area_grau) a
              FROM '{IM}/gleba_proagro.parquet' GROUP BY id_referencia_bacen, numero_ordem, id_imovel));
COPY (
  SELECT *, 'codigo' metodo FROM cod
  UNION ALL
  SELECT *, 'gleba' FROM gl WHERE NOT EXISTS (
    SELECT 1 FROM cod WHERE cod.id_referencia_bacen = gl.id_referencia_bacen AND cod.numero_ordem = gl.numero_ordem)
  UNION ALL   -- sem código nem gleba do SICOR: a gleba da perda comunicada ao Proagro (2016–2018)
  SELECT *, 'gleba_proagro' FROM pg WHERE NOT EXISTS (
    SELECT 1 FROM cod WHERE cod.id_referencia_bacen = pg.id_referencia_bacen AND cod.numero_ordem = pg.numero_ordem)
    AND NOT EXISTS (SELECT 1 FROM gl WHERE gl.id_referencia_bacen = pg.id_referencia_bacen AND gl.numero_ordem = pg.numero_ordem)
  ORDER BY ALL
) TO '{IM}/operacao.parquet' (FORMAT parquet, COMPRESSION zstd);
-- divergência: operação com código e gleba em que nenhuma gleba cai num CAR declarado
WITH ambos AS (SELECT DISTINCT id_referencia_bacen, numero_ordem FROM gl
               WHERE EXISTS (SELECT 1 FROM cod WHERE cod.id_referencia_bacen = gl.id_referencia_bacen AND cod.numero_ordem = gl.numero_ordem))
SELECT (SELECT count(*) FROM ambos) ops_com_os_dois,
       (SELECT count(*) FROM ambos a WHERE NOT EXISTS (
          SELECT 1 FROM gl JOIN cod USING (id_referencia_bacen, numero_ordem, id_imovel)
          WHERE gl.id_referencia_bacen = a.id_referencia_bacen AND gl.numero_ordem = a.numero_ordem)) divergem,
       (SELECT round(max(abs(s - 1)), 6) FROM (SELECT sum(fracao) s FROM '{IM}/operacao.parquet' GROUP BY id_referencia_bacen, numero_ordem)) erro_fracao,
       (SELECT count(DISTINCT (id_referencia_bacen, numero_ordem)) FROM '{IM}/operacao.parquet' WHERE metodo = 'gleba_proagro') ops_proagro;
"""))


@etapa
def embargo():
    print(prepara("embargo", f"""
CREATE TEMP TABLE e0 AS
  SELECT 'ibama:' || seq_tad seq_tad,
         least(try_strptime(any_value(dat_embargo), '%Y-%m-%d %H:%M:%S')::DATE, current_date) dia,
         try_strptime(any_value(dat_desembargo), '%Y-%m-%d %H:%M:%S')::DATE desembargo,
         any_value(qtd_area_embargada) area_ha,
         min(geom_area_embargada) wkt, any_value({xy('num_longitude_tad', 'num_latitude_tad')}) ponto
  FROM br_ibama_embargos_novo.termo_embargo WHERE sit_cancelado = 'N'
  GROUP BY seq_tad;
CREATE TEMP TABLE e AS SELECT * EXCLUDE (wkt), try(ST_MakeValid(ST_GeomFromText(wkt))) poligono FROM e0;
-- ICMBio: um embargo em várias feições (numero_emb + serie); sem data de desembargo,
-- vale da lavratura em diante. O julgamento é do auto, e o embargo quase sempre fica.
INSERT INTO e
  SELECT 'icmbio:' || numero_emb || serie, least(min(data), current_date), NULL, sum(area_calc_ha), NULL,
         ST_MakeValid(ST_Union_Agg(geometria))
  FROM br_icmbio_embargos.termo_embargo WHERE geometria IS NOT NULL AND data IS NOT NULL
  GROUP BY numero_emb, serie;
COPY (
  WITH p AS (
    SELECT e.seq_tad, c.id_imovel, 'poligono' metodo,
           ST_Area(ST_Intersection(e.poligono, c.geometria)) / nullif(ST_Area(e.poligono), 0) fracao
    FROM e JOIN {ATIVO} c ON ST_Intersects(c.geometria, e.poligono)
    WHERE e.poligono IS NOT NULL),
  q AS (
    SELECT e.seq_tad, c.id_imovel, 'ponto' metodo, 1.0 / count(*) OVER (PARTITION BY e.seq_tad) fracao
    FROM e JOIN {ATIVO} c ON ST_Intersects(c.geometria, e.ponto)
    WHERE e.poligono IS NULL AND e.ponto IS NOT NULL)
  SELECT x.*, e.dia, e.desembargo, e.area_ha
  FROM (SELECT * FROM p WHERE fracao >= 0.01 UNION ALL SELECT * FROM q) x JOIN e USING (seq_tad)
  ORDER BY ALL
) TO '{IM}/embargo.parquet' (FORMAT parquet, COMPRESSION zstd);
SELECT split_part(seq_tad, ':', 1) orgao, count(DISTINCT seq_tad) com_imovel, count(*) pares
FROM '{IM}/embargo.parquet' GROUP BY 1 ORDER BY 1;
"""))


@etapa
def auto():
    print(prepara("auto", f"""
CREATE TEMP TABLE a0 AS
  SELECT seq_auto_infracao, any_value(dat_hora_auto_infracao)::DATE dia, any_value(val_auto_infracao) multa,
         min(wkt_ge_area_autuada) wkt, any_value({xy('num_longitude_auto', 'num_latitude_auto')}) ponto
  FROM br_ibama_autos.auto_infracao
  WHERE coalesce(sit_cancelado, 'N') <> 'S' AND tipo_infracao = 'Flora'
  GROUP BY seq_auto_infracao;
CREATE TEMP TABLE a AS SELECT * EXCLUDE (wkt), try(ST_MakeValid(ST_GeomFromText(wkt))) poligono FROM a0;
COPY (
  WITH p AS (
    SELECT a.seq_auto_infracao, c.id_imovel, 'poligono' metodo,
           ST_Area(ST_Intersection(a.poligono, c.geometria)) / nullif(ST_Area(a.poligono), 0) fracao
    FROM a JOIN {ATIVO} c ON ST_Intersects(c.geometria, a.poligono) WHERE a.poligono IS NOT NULL),
  q AS (
    SELECT a.seq_auto_infracao, c.id_imovel, 'ponto' metodo, 1.0 / count(*) OVER (PARTITION BY a.seq_auto_infracao) fracao
    FROM a JOIN {ATIVO} c ON ST_Intersects(c.geometria, a.ponto)
    WHERE a.poligono IS NULL AND a.ponto IS NOT NULL)
  SELECT x.*, a.dia, a.multa
  FROM (SELECT * FROM p WHERE fracao >= 0.01 UNION ALL SELECT * FROM q) x JOIN a USING (seq_auto_infracao)
  ORDER BY ALL
) TO '{IM}/auto.parquet' (FORMAT parquet, COMPRESSION zstd);
SELECT (SELECT count(*) FROM a) autos, count(DISTINCT seq_auto_infracao) com_imovel FROM '{IM}/auto.parquet';
"""))


@etapa
def desmat():
    # Pelo polígono (metodo = poligono): a área do alerta se reparte entre os imóveis pela
    # interseção; pedaço abaixo de 1% do alerta é desprezado, como no embargo. Os CARs se
    # sobrepõem, então a área "dentro de CAR" de cada alerta é a soma das frações limitada a 1.
    # PRODES de 2016 em diante (o crédito por imóvel começa em 2016); DETER inteiro (2016–).
    print(prepara("desmat", f"""
SET threads = 14;
CREATE TEMP TABLE d AS
  SELECT 'prodes' fonte, bioma_arquivo || ':' || uuid alerta, coalesce(image_date, make_date(year, 8, 1)) dia,
         year ano, area_km, geometria g, ST_Area(geometria) ga
  FROM br_inpe_prodes_acumulado.desmatamento_poligono
  WHERE main_class = 'DESMATAMENTO' AND year >= 2016
  UNION ALL
  SELECT 'deter', bioma_arquivo || ':' || OGC_FID, view_date, year(view_date), area_km, geometria, ST_Area(geometria)
  FROM br_inpe_deter.avisos_poligono
  WHERE classe IN ('DESMATAMENTO_CR', 'DESMATAMENTO_VEG') OR classe LIKE 'SUPRESSÃO%';
CREATE TEMP TABLE mun AS
  SELECT d.fonte, d.alerta, any_value(m.id_municipio) id_municipio
  FROM d JOIN br_geobr_mapas.municipio m ON ST_Intersects(m.geometria, ST_PointOnSurface(d.g)) GROUP BY ALL;
CREATE TEMP TABLE x AS
  SELECT d.fonte, d.alerta, c.id_imovel, d.dia, d.ano, d.area_km,
         CASE WHEN ST_Within(d.g, c.geometria) THEN 1.0
              ELSE ST_Area(ST_Intersection(d.g, c.geometria)) / nullif(d.ga, 0) END fracao
  FROM d JOIN {ATIVO} c ON ST_Intersects(c.geometria, d.g);
COPY (
  SELECT fonte, alerta, id_imovel, dia, ano, area_km * fracao area_km, fracao
  FROM x WHERE fracao >= 0.01 ORDER BY ALL
) TO '{IM}/desmat.parquet' (FORMAT parquet, COMPRESSION zstd);
COPY (
  SELECT d.fonte, d.alerta, m.id_municipio, d.dia, d.ano, d.area_km,
         d.area_km * least(coalesce(f.f, 0), 1) area_car_km
  FROM d JOIN mun m USING (fonte, alerta)
  LEFT JOIN (SELECT fonte, alerta, sum(fracao) f FROM x GROUP BY ALL) f USING (fonte, alerta)
  ORDER BY ALL
) TO '{IM}/desmat_alerta.parquet' (FORMAT parquet, COMPRESSION zstd);
SELECT fonte, count(*) alertas, round(sum(area_km)) km2, round(sum(area_car_km)) km2_em_car
FROM '{IM}/desmat_alerta.parquet' GROUP BY 1 ORDER BY 1;
"""))


@etapa
def terra(incra=True):
    # Área em TI, UC, floresta pública não destinada (CNFP tipo B) ou parcela do SIGEF: a
    # proporção da interseção no polígono do imóvel, vezes a área declarada; somada sobre
    # as feições e limitada a 1. "Com parcela certificada" = metade ou mais do imóvel
    # coberta por parcelas do SIGEF. Assentamento: o ponto interno do imóvel no projeto.
    # LDI (Pará): área embargada por desmatamento ilegal, sem data (retrato atual).
    # `terra-` pula o INCRA.
    def fr(nome, tabela, onde="TRUE"):
        # uma tabela temporária por camada: num WITH só, as quatro interseções juntas
        # passam dos 15 GB de memória
        return f"""CREATE TEMP TABLE {nome} AS
    SELECT c.id_imovel, sum(CASE WHEN ST_Within(c.geometria, t.geometria) THEN 1.0
                            ELSE ST_Area(ST_Intersection(c.geometria, t.geometria)) / nullif(ST_Area(c.geometria), 0) END) f
    FROM {ATIVO} c JOIN {tabela} t ON ST_Intersects(c.geometria, t.geometria) WHERE {onde} GROUP BY 1;"""
    prepara("terra", f"""
SET threads = 8; SET memory_limit = '22GB'; SET preserve_insertion_order = false;
{fr("ti", "br_geobr_mapas.terra_indigena")}
{fr("uc", "br_geobr_mapas.unidade_conservacao", "t.sigla_grupo = 'PI'")}
{fr("fp", "br_sfb_cnfp.florestas_publicas", "t.tipo = 'TIPO B'")}
{fr("ld", "br_semas_pa_ldi.areas_embargadas", "t.ano_desmat <= year(current_date)")}
COPY (
  WITH k AS (SELECT id_imovel FROM ti UNION SELECT id_imovel FROM uc UNION SELECT id_imovel FROM fp
             UNION SELECT id_imovel FROM ld)
  SELECT k.id_imovel, least(coalesce(ti.f, 0), 1) f_ti, least(coalesce(uc.f, 0), 1) f_ucpi,
         least(coalesce(fp.f, 0), 1) f_fpnd, least(coalesce(ld.f, 0), 1) f_ldi
  FROM k LEFT JOIN ti USING (id_imovel) LEFT JOIN uc USING (id_imovel) LEFT JOIN fp USING (id_imovel)
  LEFT JOIN ld USING (id_imovel)
  ORDER BY ALL
) TO '{IM}/terra.parquet' (FORMAT parquet, COMPRESSION zstd);
""")
    # INCRA à parte: os polígonos vêm por proxy BR (rodado, incra_poligonos.py) e
    # demoram mais que o resto para chegar ao espelho
    prepara("incra", f"""
SET threads = 8; SET memory_limit = '22GB'; SET preserve_insertion_order = false;
{fr("sg", "br_incra_acervo.sigef_poligono")}
CREATE TEMP TABLE pa AS
  SELECT DISTINCT c.id_imovel FROM {ATIVO} c JOIN br_incra_acervo.assentamentos_poligono a
  ON ST_Intersects(a.geometria, ST_PointOnSurface(c.geometria));
COPY (
  WITH k AS (SELECT id_imovel FROM sg UNION SELECT id_imovel FROM pa)
  SELECT k.id_imovel, coalesce(sg.f, 0) >= 0.5 sigef, pa.id_imovel IS NOT NULL assentamento
  FROM k LEFT JOIN sg USING (id_imovel) LEFT JOIN pa USING (id_imovel)
  ORDER BY ALL
) TO '{IM}/incra.parquet' (FORMAT parquet, COMPRESSION zstd);
""") if incra else None


@etapa
def agrega():
    global mun, ano
    mun = roda("imovel_mun", f"""
COPY (
  WITH c AS (SELECT * FROM {CAR} WHERE status <> 'CA'),
  x AS (
    SELECT c.id_municipio, count(*) imoveis, sum(c.area_ha) area_car,
           sum(c.area_ha * coalesce(t.f_ti, 0)) area_ti, sum(c.area_ha * coalesce(t.f_ucpi, 0)) area_ucpi,
           sum(c.area_ha * coalesce(t.f_fpnd, 0)) area_fpnd,
           -- Lista de Desmatamento Ilegal do Pará: só com 5 ou mais imóveis atingidos
           CASE WHEN count(*) FILTER (WHERE t.f_ldi >= 0.01) >= {MIN}
                THEN sum(c.area_ha * coalesce(t.f_ldi, 0)) END area_ldi,
           count(*) FILTER (WHERE i.sigef) imoveis_sigef, count(*) FILTER (WHERE i.assentamento) imoveis_assent,
           sum(c.area_ha) FILTER (WHERE c.condicao LIKE 'Analisado%') area_analisada,
           sum(k.app) app, sum(k.rl) rl, sum(k.veg_nativa) veg_nativa, sum(k.consolidada) consolidada
    FROM c LEFT JOIN '{IM}/terra.parquet' t USING (id_imovel) LEFT JOIN '{IM}/incra.parquet' i USING (id_imovel)
    LEFT JOIN '{IM}/camadas.parquet' k USING (id_imovel)
    WHERE c.id_municipio IS NOT NULL GROUP BY 1)
  SELECT * FROM x WHERE imoveis >= {MIN} ORDER BY ALL
) TO '{{saida}}' (FORMAT parquet);
""")
    # Crédito: o valor e a área da operação repartidos pela fracao; o município é o do
    # imóvel. Desmatamento "durante a operação": alerta entre a emissão e o vencimento.
    # Embargo vigente: embargado antes da emissão e não desembargado até ela.
    ano = roda("imovel_ano", f"""
COPY (
  WITH op AS (
    SELECT b.id_referencia_bacen, b.numero_ordem, b.id_imovel, b.fracao, c.id_municipio,
           left(o.ano_safra_emissao, 4)::INTEGER ano, o.data_emissao, o.data_vencimento,
           o.valor_parcela_credito * b.fracao v, o.area_financiada * b.fracao a
    FROM '{IM}/operacao.parquet' b
    JOIN br_bcb_sicor.operacao o USING (id_referencia_bacen, numero_ordem)
    JOIN {CAR} c USING (id_imovel)
    WHERE c.id_municipio IS NOT NULL),
  dm AS (SELECT DISTINCT o.id_referencia_bacen, o.numero_ordem, o.id_imovel FROM op o
         JOIN '{IM}/desmat.parquet' d ON d.id_imovel = o.id_imovel
          AND d.dia > o.data_emissao AND d.dia <= coalesce(o.data_vencimento, o.data_emissao + INTERVAL 1 YEAR)),
  em AS (SELECT DISTINCT o.id_referencia_bacen, o.numero_ordem, o.id_imovel FROM op o
         JOIN '{IM}/embargo.parquet' e ON e.id_imovel = o.id_imovel
          AND e.dia <= o.data_emissao AND (e.desembargo IS NULL OR e.desembargo > o.data_emissao)),
  rcp AS (   -- perda comprovada no Proagro (ha), como em baixa_credito.py
    SELECT id_referencia_bacen, numero_ordem, sum(area) ha FROM br_bcb_sicor.proagro_rcp
    WHERE area > 0 AND area < 50000 GROUP BY ALL),
  marca AS (
    SELECT op.*, dm.id_imovel IS NOT NULL desm, em.id_imovel IS NOT NULL emb,
           rcp.ha * op.fracao p, rcp.ha IS NOT NULL AND (dm.id_imovel IS NOT NULL OR em.id_imovel IS NOT NULL) perda
    FROM op LEFT JOIN dm USING (id_referencia_bacen, numero_ordem, id_imovel)
    LEFT JOIN em USING (id_referencia_bacen, numero_ordem, id_imovel)
    LEFT JOIN rcp USING (id_referencia_bacen, numero_ordem)),
  -- cada medida com o seu próprio corte (ver cortes())
  cr AS (SELECT id_municipio, ano, {cortes()}
    FROM marca GROUP BY ALL),
  ds AS (
    SELECT id_municipio, ano, sum(area_km) desm_km2, sum(area_car_km) desm_car_km2
    FROM '{IM}/desmat_alerta.parquet' WHERE fonte = 'prodes' AND ano >= 2017   -- antes, bienal fora da Amazônia
      -- só os anos que todos os biomas têm: o Cerrado da versão 2026 já traz 2026
      AND ano <= (SELECT min(m) FROM (SELECT max(year) m FROM br_inpe_prodes_acumulado.desmatamento_poligono GROUP BY bioma_arquivo))
    GROUP BY ALL)
  SELECT * FROM cr FULL JOIN ds USING (id_municipio, ano)
  WHERE ano BETWEEN 2001 AND year(current_date)
  ORDER BY ALL
) TO '{{saida}}' (FORMAT parquet);
""")


pedidas = sys.argv[1:] or list(ETAPAS)
for nome in pedidas:
    ETAPAS[nome]() if nome != "terra-" else terra(incra=False)

if "agrega" in pedidas:
    # ---------- conferências ----------
    f = lambda v: f"{v:,.0f}".replace(",", ".")
    print(f"CAR ativo nos municípios: {f(mun['area_car'].sum() / 1e6)} mi ha em {f(mun['imoveis'].sum())} imóveis (SICAR ≈ 713 mi ha)")
    print(f"  em TI: {f(mun['area_ti'].sum() / 1e6)} mi ha · em UC de proteção integral: {f(mun['area_ucpi'].sum() / 1e6)} mi ha"
          f" · em floresta pública não destinada: {f(mun['area_fpnd'].sum() / 1e6)} mi ha"
          f" · na LDI do Pará: {f(mun['area_ldi'].sum())} ha")
    print(f"  com parcela SIGEF: {f(mun['imoveis_sigef'].sum())} imóveis · em assentamento: {f(mun['imoveis_assent'].sum())}"
          f" · área analisada: {f(mun['area_analisada'].sum() / 1e6)} mi ha")
    print(f"perda no Proagro em imóvel com desmatamento ou embargo: {f(ano['pp_area'].sum())} ha")
    s = ano.group_by("ano").agg(pl.col("ccar_valor", "cd_valor", "ce_valor", "desm_km2", "desm_car_km2").sum()).sort("ano")
    print(s.with_columns((pl.col(c) / 1e9).round(1) for c in ("ccar_valor", "cd_valor", "ce_valor")))
    assert 600e6 < mun["area_car"].sum() < 760e6
    c23 = s.filter(pl.col("ano") == 2023)
    assert 100e9 < c23["ccar_valor"][0] < 400e9, "crédito 2023/24 ligado a CAR fora da ordem de grandeza"
