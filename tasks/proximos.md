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

- [ ] Testar 0,25° (~28 km) com a mesma checagem de diferença contra o município (etapa
  `grade` de `baixa_imovel.py`, constante `PASSO`), e mostrar o antes e depois do total
  publicado por UF.
- [ ] Se valer, decidir entre trocar a grade ou oferecer as duas.

## 3. Teste intermitente do service worker

`testes/site.test.ts`, "segunda visita sem rede", só no Chromium: falha em cerca de 1 de cada
3 rodadas. Na falha, a página offline mostra "Não foi possível abrir os dados do mapa (Failed
t…)".

- [ ] Achar a causa (provavelmente uma corrida entre o cache do SW e o reload) em vez de
  rodar de novo até passar.

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

- [ ] Gerar em `monta_pagina.py` um `<bloco>.<hash>.json.gz` por bloco, com
  `{"meta": ..., "arrays": {nome: [...]}}`, no lugar do `.bin` (ou ao lado, durante a troca).
  - Manter o que o binário já faz e não depende do formato: escala log em u16, colunas em
    diferença, saída determinística (hash estável).
- [ ] No template, trocar a leitura dos blocos (cabeçalho + planos de bytes) por
  `DecompressionStream('gzip')` → `JSON.parse` → `TypedArray.from`, com o mesmo
  `{A, meta}` de saída, para o resto da página não mudar.
- [ ] Tirar os blocos embutidos do `index.html`: a página passa a ser o HTML de `site/` com
  `dados/` ao lado. O `fetch` da 1ª etapa no `<head>` (`window.__pre`) e o service worker
  seguem iguais, só com a extensão nova.
- [ ] Release: em vez do `index.html` único, um zip da pasta, com instrução de abrir por
  `python3 -m http.server`. Ou só a web, e a release deixa de levar a página.
- [ ] Testes: a suíte principal abre o `index.html` por `file://` (`testes/comum.ts`,
  `URL_INDEX`); passa a subir um servidor local. Ajustar os testes de `site/` que conferem o
  `.bin`.
- [ ] Atualizar o CLAUDE.md: o requisito de `file://`, a seção "Duas saídas", o formato de
  cada bloco e o orçamento.
- [ ] Medir de novo, com rede 4G simulada, o primeiro mapa e o tudo pronto (hoje 3,0 s e 4,2 s).
- [ ] Se o +25% pesar, a alternativa medida é ficar com o `.bin` e só tirá-lo do HTML: o
  ganho de tamanho é o mesmo, sem o custo do JSON.

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

- [ ] Medir o crédito dado a imóvel com área da lista desmatada antes da emissão, pelo
  `ano_desmat`. É uma aproximação: a lista não tem a data do embargo (gotcha
  `sem_data_de_embargo` em `br_semas_pa_ldi`).
