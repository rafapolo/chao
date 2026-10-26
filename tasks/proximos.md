# Próximos passos

Aberto em 2026-10-26, depois de fechar o [`imovel_pendente.md`](imovel_pendente.md) e as
[`decisoes_pendentes.md`](decisoes_pendentes.md). A ordem é a recomendada; nada foi começado.

## 1. Publicar (pede o seu ok: deixa o trabalho público)

- [ ] Push do Chão: os commits de `a32a3ed` a `6f419b8` estão só na máquina local. O push
  atualiza a versão web pelo GitHub Pages (`.github/workflows/pages.yml`).
- [ ] Release nova com o `index.html` (`gh release create vAAAA.MM.DD index.html`, como diz o
  CLAUDE.md).
- [ ] Push do rodado: `13e55a6`, `cc93df2` e `a494dc1` (gotchas e o teste do MCP).

## 2. Grade mais grossa no modo Imóvel

Na Amazônia, a grade de 0,05° mostra só R$ 0,4 bi dos R$ 12 bi de crédito com desmatamento
em 2021: cada célula precisa de 5 operações e 5 imóveis, e lá os imóveis são grandes e poucos
por célula.

- [x] Testado em 2026-10-26 (`baixa_imovel.py grade:N`). Crédito com desmatamento publicado:
  R$ 0,4 → 5,2 bi de 13,1 bi em 2021 (PA 0,0 → 0,39 de 1,68; MT 0,0 → 0,11 de 0,87; GO 0,0 →
  0,49 de 1,43); ligado a CAR: 55,9 → 96,9 de 108,2 bi.
- [x] Trocada a grade (constante `GRADE = 5`), sem oferecer as duas: a célula grande menos as
  pequenas publicadas revelaria a pequena cortada. O bloco `imovel` caiu de 1,0 para 0,5 MB.

## 3. Teste intermitente do service worker

`testes/site.test.ts`, "segunda visita sem rede", só no Chromium: falha em cerca de 1 de cada
3 rodadas. Na falha, a página offline mostra "Não foi possível abrir os dados do mapa (Failed
t…)".

- [x] Causa (2026-10-26): o `waitForFunction` com predicado `async` passava na hora (a Promise
  é "truthy"), e o reload offline pegava `malha` e `prod` ainda sendo gravadas no cache. O
  teste agora confere cada bloco das duas etapas com `caches.match`, em laço; 6 de 6 passaram.

## 4. Dados fora do `index.html`, em `.json.gz` (decidido em 2026-10-26)

O `index.html` tem 38,4 MB, contra o orçamento de 25 MB da spec, porque embute os blocos em
base64 para abrir por `file://`. **Decisão: tirar os dados do HTML e servi-los como
`.json.gz`**, buscados por `fetch`, na web e com servidor local. Isso derruba o requisito
de abrir por `file://` (dois cliques) que está no CLAUDE.md.

Medido em 2026-10-26, decodificando os blocos de `site/dados/` e regravando em JSON (gzip -9):

| | binário gz (hoje) | json | json.gz |
|---|---|---|---|
| total | 28,8 MB | 220 MB | 36,0 MB (1,25×) |
| prod (1ª etapa) | 3,29 MB | 64,1 MB | 3,59 MB (1,09×) |
| malha (1ª etapa) | 2,87 MB | 10,7 MB | 3,37 MB (1,17×) |
| prodqv (sob demanda) | 10,12 MB | 48,6 MB | 12,82 MB (1,27×) |
| emis | 1,46 MB | 16,0 MB | 2,07 MB (1,42×) |

O JSON custa +7,2 MB (+25%) transferidos, e a 1ª etapa vai de 6,2 para ~7,0 MB. Em memória o
navegador ainda tem de converter as listas em arrays tipados (o `prod` cru tem 64 MB de texto).

- [x] Feito em 2026-10-26: `monta_pagina.py` grava `site/dados/<bloco>.<hash>.json.gz`
  (`{"meta", "arrays": {nome: {"t", "v"}}}`, diferenças com sinal), o template lê com
  `JSON.parse` → `TypedArray.from` e o `index.html` único saiu. Por `file://` a página
  explica como abrir com `python3 -m http.server`; se o servidor mandar
  `Content-Encoding: gzip`, ela lê o JSON direto.
- [x] Testes servem `site/` por HTTP (`testes/comum.ts`); 118 passam nos 3 motores, 3
  pulados. CLAUDE.md e README atualizados.
- [x] Medido com 4G (`testes/_perf.ts`, 3 rodadas): primeiro mapa 3,05 → 3,34 s, tudo
  pronto 4,24 → 5,17 s, 9,9 → 11,9 MB. Total em `site/dados/`: 28,4 → 35,4 MB.
- [ ] Release: zip de `site/` com instrução de `python3 -m http.server`, ou só a web?
- [ ] Depois do push, conferir que o Pages serve o `.json.gz` (o `.bin` ia como
  `application/octet-stream`, sem Content-Encoding).
- [ ] Se o +22% no "tudo pronto" pesar, a alternativa medida é voltar ao `.bin`, só fora do
  HTML.

## 5. Arquivos gerados do rodado

`docs/context/datasets.md`, `docs/mapa/catalog.md`, `pages/atlas/schema_graph.json`,
`pages/mcp*.html` e `docs/context/join_keys.md` ficaram sem commit: outra sessão mexia nos
mesmos arquivos (`br_mma_cnuc`, `br_prf_infracoes`, `br_ans_operadoras`, `br_tse_eleicoes`).

- [ ] Quando ela terminar, rodar a sequência de regeneração do `../rodado/AGENTS.md` e commitar
  tudo junto. Os datasets novos desta rodada que precisam aparecer: `br_icmbio_embargos`,
  `br_sfb_cnfp`, `br_semas_pa_ldi`, `br_sema_mt_embargos` e os polígonos de
  `br_inpe_prodes_acumulado`, `br_inpe_deter` e `br_incra_acervo`.

## 6. A LDI do Pará ligada ao crédito

Hoje a LDI entra só como retrato atual (área do CAR na lista).

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
