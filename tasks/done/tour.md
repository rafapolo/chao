# Tour de 3 minutos

Aberto em 2026-11-05. O pedido é um tour guiado de cerca de 180 s pelo Chão, no mesmo formato
dos tours dos outros projetos, para o Chão entrar na seção WebDocs da home do rodado
(rodado.xyz, ao lado de Tocador, Rios do Brasil, Geoglifos, Cantography e Brasiliana). Nada
foi começado: uma primeira tentativa foi parada antes de mexer em qualquer arquivo.

## 1. Pesquisa: o que os dados têm de mais interessante

Isso vem antes do roteiro, a pedido. O roteiro sai dos achados, não de suposição.

- [ ] Rodar consultas sobre os dados do próprio Chão (`pipeline/` e o que a página carrega).
  Se faltar algo, usar o espelho no beelink com `ssh beelink '~/bin/duckdb -readonly -json
  ~/rodado/basedosdados.duckdb'`, sempre em `-readonly` e com filtro de partição.
- [ ] Procurar as histórias mais fortes de 1974 a 2025:
  - as maiores mudanças;
  - os municípios e as regiões nos extremos;
  - as viradas de cultura (café ou algodão dando lugar à soja, por exemplo);
  - os choques de clima e de preço;
  - a concentração de terra;
  - a fronteira agrícola andando do Sul e do Sudeste para o Centro-Oeste e o Matopiba;
  - os contrastes que surpreendem.
- [ ] Ranquear de 8 a 12 achados por interesse e por confiabilidade. Para cada número
  registrar a fonte (o arquivo do projeto), a ordem de grandeza esperada e uma segunda
  conferência independente. Salvar em `design/achados.md`.

## 2. Roteiro

- [ ] Escrever entre 10 e 14 cenas com começo, meio e fim, usando o tempo e o território a
  partir dos melhores achados. Escrever em `design/tour.md`, no estilo dos modelos: como
  abrir e parar o tour, o roteiro cena a cena com tempos e, para cada número citado, de onde
  saiu e como foi conferido.

Modelos para ler antes de começar:

- `../geoglifos-amazonia/design/tour.md`, com `docs/tour.js` (as cenas ficam em `cenas()`)
  e `docs/som.js`. É o melhor modelo para abrir, parar e ter som.
- `../cantography/design/tour.md` (as cenas ficam em `tourScenes()`, no `index.html`). É o
  modelo do ponteiro desenhado que clica nos controles de verdade e do `&t=<segundos>`.
- `../rios-do-brasil/design/tour.md` e `design/tour.json`. É o modelo de conferência de cada
  número.
- `../tocador/TOUR.md`.

## 3. Implementação

- [ ] Abrir com `?tour=1`: um convite "Começar o tour" sobre o mapa. O clique começa o tour e
  libera o som. Depois de começar, o parâmetro sai do endereço.
- [ ] Botão **Tour** no topo.
- [ ] **Esc** ou **✕ esc** param o tour e deixam o mapa onde a câmera estava, com as camadas,
  os filtros e o ano de antes. O voltar do navegador também para o tour.
- [ ] `&t=<segundos>` começa no meio; as cenas anteriores rodam instantâneas.
- [ ] Um ponteiro desenhado clica nos controles reais, para o tour também ensinar a usar a
  página.
- [ ] Música só se for simples e sem dependência pesada, seguindo o `som.js` do geoglifos.

## 4. Verificação

- [ ] Rodar o site localmente e testar com Playwright usando o Chromium embutido
  (`p.chromium.launch()`, nunca `channel="chrome"`) e fechando o navegador no `finally`.
- [ ] Conferir que o tour roda de ponta a ponta em cerca de 180 s sem erro no console.
- [ ] Conferir que `?tour=1&t=90` começa no meio.
- [ ] Conferir que Esc restaura o estado.
- [ ] Conferir que funciona em 390 px de largura.
- [ ] Rodar os testes do projeto e acrescentar um teste de fumaça do tour, se houver padrão
  para isso.

## 5. Depois

- [ ] Pôr o cartão do Chão na seção WebDocs de `../rodado/pages/index.html` e `en.html`, com
  uma miniatura 640×480 em `pages/assets/teaser/webdoc-chao.webp` e o link
  `https://rafapolo.github.io/chao/?tour=1`.
