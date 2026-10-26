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

## 4. Peso do `index.html`

São 38,4 MB, contra o orçamento de 25 MB da spec; o modo Imóvel cresceu nesta rodada (bloco
`imovel` 4,4 MB cru, 1,0 MB gz).

- [ ] Aplicar o caminho que o CLAUDE.md já aponta: a 3ª etapa (sob demanda) só no `site/`, fora
  do arquivo único, e medir o resultado.

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
