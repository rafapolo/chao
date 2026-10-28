# Próximos passos

Aberto em 2026-10-26, depois de fechar o [`imovel_pendente.md`](imovel_pendente.md) e as
[`decisoes_pendentes.md`](decisoes_pendentes.md). A ordem é a recomendada; nada foi começado.

## 1. Publicar (pede o seu ok: deixa o trabalho público)

- [x] Push do Chão (2026-10-26, depois de juntar com a mineração do DETER do remoto).
- [x] Release `v2026.10.26` com o `index.html` (a última com o arquivo único).
- [x] Push do rodado: os três commits já estavam no remoto.

## 2. Grade mais grossa no modo Imóvel

Na Amazônia, a grade de 0,05° mostra só R$ 0,4 bi dos R$ 12 bi de crédito com desmatamento
em 2021: cada célula precisa de 5 operações e 5 imóveis, e lá os imóveis são grandes e poucos
por célula.

- [x] Testado em 2026-10-26 (`baixa_imovel.py grade:N`). Crédito com desmatamento publicado:
  R$ 0,4 → 5,2 bi de 13,1 bi em 2021 (PA 0,0 → 0,39 de 1,68; MT 0,0 → 0,11 de 0,87; GO 0,0 →
  0,49 de 1,43); ligado a CAR: 55,9 → 96,9 de 108,2 bi.
- [x] Trocada a grade (constante `GRADE = 5`), sem oferecer as duas: a célula grande menos as
  pequenas publicadas revelaria a pequena cortada. Como a de 0,05° já saiu (Pages, release
  v2026.10.26, git), `celulas_publicadas.py` leva ao beelink as células dela, e a etapa
  `grade` corta a de 0,25° cujo resíduo contra elas tem 1 a 4 operações ou imóveis. Depois
  do corte: R$ 5,3 de 13,1 bi com desmatamento em 2021, 93,3 de 108,2 bi ligados a CAR.

## 3. Teste intermitente do service worker

`testes/site.test.ts`, "segunda visita sem rede", só no Chromium: falha em cerca de 1 de cada
3 rodadas. Na falha, a página offline mostra "Não foi possível abrir os dados do mapa (Failed
t…)".

- [x] Causa (2026-10-26): o `waitForFunction` com predicado `async` passava na hora (a Promise
  é "truthy"), e o reload offline pegava `malha` e `prod` ainda sendo gravadas no cache. O
  teste agora confere cada bloco das duas etapas com `caches.match`, em laço; 6 de 6 passaram.

## 4. Dados fora do `index.html` (feito em 2026-10-26)

O `index.html` único (38,4 MB, contra o orçamento de 25 MB da spec) saiu: a página é
`site/` com `dados/` ao lado, buscados por `fetch`, e por `file://` ela explica como abrir
com `python3 -m http.server`. Os testes servem `site/` por HTTP. Release: só a web.

O formato foi JSON em `.json.gz` por um commit e voltou ao `.bin` com bytes em planos.
Medido com 4G (`testes/_perf.ts`): o JSON levava o primeiro mapa de 3,05 a 3,34 s, o tudo
pronto de 4,24 a 5,17 s e os dados de 28,4 a 35,4 MB. Com o `.bin` de volta, os hashes são
os de antes e o cache de quem já visitou continua valendo.

## 5. Arquivos gerados do rodado

`docs/context/datasets.md`, `docs/mapa/catalog.md`, `pages/atlas/schema_graph.json`,
`pages/mcp*.html` e `docs/context/join_keys.md` ficaram sem commit: outra sessão mexia nos
mesmos arquivos (`br_mma_cnuc`, `br_prf_infracoes`, `br_ans_operadoras`, `br_tse_eleicoes`).

- [x] (2026-10-26) Regenerado e commitado no rodado; os 7 datasets aparecem em datasets.md, catalog.md, schema_graph.json e mcp.html. O `gera_dicionario_coverage.py` e os passos seguintes não rodaram (trava de escrita de outro processo no beelink) e só precisam rodar quando um dicionário mudar. Antes: quando ela terminar, rodar a sequência de regeneração do `../rodado/AGENTS.md` e commitar
  tudo junto. Os datasets novos desta rodada que precisam aparecer: `br_icmbio_embargos`,
  `br_sfb_cnfp`, `br_semas_pa_ldi`, `br_sema_mt_embargos` e os polígonos de
  `br_inpe_prodes_acumulado`, `br_inpe_deter` e `br_incra_acervo`.

## 6. A LDI do Pará ligada ao crédito

Hoje a LDI entra só como retrato atual (área do CAR na lista).

- [x] Uma frase no texto do modo Imóvel com o total do Pará (2026-10-26).
- [x] Medido em 2026-10-26 (consulta avulsa sobre `marca.parquet`; imóvel do PA com ≥ 1% na
  LDI e `ano_desmat` menor que o ano da safra de emissão; 4.985 imóveis tocam a lista). É
  uma aproximação: a lista não tem a data do embargo (gotcha `sem_data_de_embargo`).

  | safra | crédito em CAR no PA | em imóvel da LDI desmatado antes | operações | imóveis | municípios |
  |---|---|---|---|---|---|
  | 2019 | R$ 2.149 mi | R$ 6,8 mi | 54 | 32 | 18 |
  | 2020 | R$ 2.844 mi | R$ 8,9 mi | 59 | 26 | 14 |
  | 2021 | R$ 4.630 mi | R$ 32,9 mi (0,7%) | 137 | 95 | 24 |
  | 2022 | R$ 3.629 mi | R$ 12,7 mi | 68 | 50 | 21 |
  | 2023 | R$ 4.425 mi | R$ 7,9 mi | 52 | 36 | 14 |
  | 2024 | R$ 5.729 mi | R$ 19,3 mi | 100 | 61 | 24 |

  Soma ~R$ 98 mi de 2016 a 2025. Com ~2–4 imóveis por município, o corte de 5 operações e
  5 imóveis apagaria quase tudo por município: não vale uma medida na página. Cabe como
  número no texto do modo (por UF), se quiser.

## SEMA-MT: termos embargados que já têm desembargo (aberto e fechado em 2026-10-28)

- [x] **Medido:** 353 áreas desembargadas têm termo que ainda consta em `areas_embargadas`, mas
  o termo se repete em áreas que não se tocam. Pelo termo saem 560 pares e só 247 se tocam.
  Outros 2.661 desembargos tocam a área de outro termo, que continua embargada, e não entram.
  A fonte não tem data de desembargo: `DATA_ENVIO`, no SIGA, é o envio do auto, e
  `situacao` é a fase do processo.
- [x] **Feito (`baixa_imovel.py`, etapa `embargo`):** cada área embargada perde, por
  `ST_Difference`, a união das áreas desembargadas de mesmo termo que a tocam. Se sobra menos
  de 1%, ela sai inteira (desembargo total), e a `area_ha` encolhe na proporção. Sem data,
  vale para todas as safras. Das 204 áreas atingidas, 18 saem inteiras e somam 1.828 ha.
  Imóveis com embargo da SEMA-MT: 15.923 → 15.911.
- [x] **Antes e depois por município:** nenhuma operação de crédito mudou de marca de embargo.
  O desembargo cai em imóvel sem crédito, ou em crédito emitido antes da lavratura. Por isso
  `imovel_ano` sai igual coluna a coluna (54.921 linhas; `ce_valor`, `ce_area`, `pp_area`
  com 0 diferenças) e os blocos `.bin` não mudam de hash. Só o texto do modo Imóvel mudou.
- [x] **Corte entre versões:** `celulas_publicadas.py` ganhou o 4º corte, contra a marcação
  publicada em `299362d` (`~/bragro_tmp/imovel/marca_299362d.parquet`, nos dois sentidos).
  Ele dá 0 hoje, e `imovel_ce_corta` segue com as 152 linhas.
- [x] Gotcha `desembargo_parcial_de_termo_vigente` no rodado (`e5a2f01`).
