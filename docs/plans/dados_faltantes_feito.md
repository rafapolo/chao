# Chão (antes bragro, Safra a Safra): o que já entrou do plano de dados faltantes

Separado de [`dados_faltantes.md`](dados_faltantes.md) em
2026-10-22. Feito na branch `dados-faltantes` do `~/Projetos/chao` (sem push: o push
publica `site/` no Pages). Cada item tem teste em `testes/mapa.test.ts` ou `site.test.ts`.

## Infraestrutura (fase 1)

- **3ª etapa sob demanda.** `<script id="b-…" data-etapa="sob-demanda">`, mais
  `carrega(id)` com cache de promessa e `garante([ids])`.
  - O modo, o recorte ou a ficha pedem o bloco; na chegada, a página redesenha.
  - No `index.html` (file://) os blocos seguem embutidos e o sob demanda só adia a
    decodificação. Em `site/` o `.bin` só é baixado quando pedido.
  - Teste: o bloco `contornos` não é pedido no carregamento e é pedido ao abrir o
    Garantia-Safra.
- **Fontes agrupadas em seções** no painel: Produção, Terra, Dinheiro, Clima e fogo,
  Gente.
- **Ficha em seções recolhíveis** (`<details>`): o que foi fechado continua fechado
  de um município a outro.

## Parte A: dos seis datasets iniciais e da malha

| Tabela | Como entrou |
|---|---|
| `br_ibge_ppm.producao_pecuaria` | Itens `R|Vacas ordenhadas` e `R|Ovinos tosquiados`. Medida "litros por vaca ordenhada" no Leite e "kg por ovino tosquiado" na Lã, com o AMC repartido. Na ficha, sob os rebanhos. Teste: Castro (PR). |
| `br_cgu_garantia_safra` (valor) | Medidas "R$ pagos" e "R$ por agricultor" no modo Garantia-Safra. Teste: soma de 2020 contra o parquet. |
| `br_geobr_mapas.semiarido` | Contorno tracejado no modo Garantia-Safra (união dos 1.262 municípios, com buffer de ida e volta de 0,003° para fechar as frestas) e recorte "Semiárido". |
| `br_geobr_mapas.amazonia_legal` | Recorte "Amazônia Legal", pela coluna do diretório de municípios (773), com contorno. |
| `br_geobr_mapas.bioma` | Contorno do bioma escolhido no recorte. Biomas de 2019, mais a Amazônia de 2004 (em 2019 ela está com geometria NULL). |
| `br_geobr_mapas.uf`, `regiao`, `pais` | As divisas de UF ficam sempre à vista, em traço fino, na 1ª etapa. As regiões viram recorte, com contorno. |
| `meso`/`micro`/`intermediaria`/`imediata` | A pertença do município já vai na malha (`dv_*`). Falta o seletor "agrupar por" (fase 8). |
| `br_geobr_mapas.limite_vizinhanca` | **Descartado:** não são divisas entre municípios, são os 14.832 limites de bairros do Censo. |

## Parte B

| Dataset | Como entrou |
|---|---|
| `br_ibge_pevs` | Itens `E|` (extração vegetal) e `S|` (silvicultura), só com quantidade e valor; a PEVS não tem área. O nome leva a fonte ("Açaí (fruto) · extração"), porque açaí, palmito, erva-mate, lenha e carvão se repetem. Na ficha, ao lado do que a PAM declara plantado. Não entram na lavoura principal, que disputa por área. |
| `br_ibge_amc` | **Descartado:** é a mesma base de 2010 (5.565 municípios), não cobre os 5 municípios de 2013 e tem `id_amc` nulo em vários pares de anos. Segue a AMC do geobr com `ORIGEM_2013`. |

## Fases 3 a 8 (2026-10-22, branch `dados-faltantes`, 81 testes nos três motores)

| Fase | Modo ou recurso | Fontes | Commit |
|---|---|---|---|
| 3 | **Crédito rural**: R$, R$/ha, operações, % Pronaf, liberado ÷ contratado, desclassificadas, tomadores, % PJ, concentração (10% maiores), cooperativa de crédito, cooperados, % com CAR, dívida em aberto, ESTBAN, BNDES. Filtros de finalidade, atividade e programa. Na ficha: quem empresta, total da UF e SCR. **Economia**: VA agropecuário, % do VA, por km² rural | SICOR (operacao, empreendimento, liberacao, saldo, mutuario, cooperado, propriedade, desclassificadas, instituicao_financeira, fonte_recurso, dicionario), ESTBAN, BNDES desembolsos, SCR, PIB municipal | `b05de15` |
| 4 | **Desmatamento**: PRODES por município e em grade de 0,1°, acumulado, DETER (desmatamento, degradação), embargos, área embargada, autos e multas de flora. **Fogo**: focos do satélite de referência, densidade, grade, cicatriz de queimada (DETER). Na ficha: assentamentos e área certificada (SIGEF + SNCI) ao lado do CAR | PRODES, PRODES acumulado, DETER, queimadas, IBAMA embargos e autos, INCRA acervo | `841f1d1` |
| 5 | **Clima**: chuva, anomalia (escala divergente), dias sem chuva, temperatura; estações do INMET em pontos; reconhecimentos do S2ID. Na ficha: série do município × estação mais próxima e chuva média por mês | SISAM, INMET BDMEP, S2ID | `6a9c7be` |
| 6 | **Exportação** (Trase pelo município de produção, Comex pela sede da empresa, fertilizantes e defensivos importados; destinos e logística na ficha), **Emissões** (SEEG), **Trabalho e estrutura** (RAIS, CAGED, CNEFE, CAFIR), **Famílias do campo** (CadÚnico por grupo, Seguro-Defeso, população) | Trase, Comex, SEEG, RAIS, CAGED, CNEFE, CAFIR, CadÚnico, Seguro-Defeso, população IBGE | `c2f34a4` |
| 7 | **Calendário**: mês típico de plantio (escala cíclica, média circular), ciclo, % de 2ª safra; faixa de 12 meses na ficha | SICOR (datas de plantio e colheita da operacao, não o proagro_cop) | `3ffc430` |
| 8 | **Agrupar por** região imediata, micro, intermediária, meso, UF ou grande região; **rótulos das sedes** no zoom alto | geobr `sede_municipal` (2010), diretório de municípios | `10fc9fc` |

Fase 9 (raster): **medida, não construída.** MapBiomas coleção 10, cobertura do Brasil: 799 MB (2023) e 802 MB (2024) por ano em `storage.googleapis.com/mapbiomas-public/initiatives/brasil/collection_10/lulc/coverage/brazil_coverage_<ano>.tif`; a coleção 11 não está nessa URL. Cinco anos ≈ 4 GB; o beelink tem 623 GB livres, 16 núcleos e 27 GB de RAM.

Gotchas novas em `docs/context/gotchas/` (2026-10-22): br_bcb_sicor (+4), br_bcb_estban, br_inpe_queimadas, br_inpe_deter, br_rf_cafir, br_cgu_seguro_defeso; novos br_ibge_pib, br_inpe_sisam, br_inmet_bdmep, br_sedec_desastres, br_seeg_emissoes, br_trase_supply_chain, br_geobr_mapas, br_inpe_prodes.

O `index.html` tem 37,6 MB; no `site/` a 1ª etapa segue com 6,7 MB, e a 3ª etapa (8,1 MB) só é baixada quando pedida.
