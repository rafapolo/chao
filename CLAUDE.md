# CLAUDE.md

Orientação para agentes que trabalham neste repositório.

## O que é

"Chão" (repositório `rafapolo/chao`, antes "bragro" e "Safra a Safra") é uma página HTML,
`site/index.html` (~230 kB) com os dados em `site/dados/` (28 MB), com o mapa do campo brasileiro em cada município: o que se
planta e se cria de 1974 a 2025, a terra, o crédito, o clima e quem vive do campo. Ela tem linha do tempo, filtros por cultura,
medida, fonte e recorte, e uma ficha por município. A spec está em
`docs/superpowers/specs/2026-10-21-bragro-design.md`.

**Não há dependência em runtime.** O único build é o da versão web (`scripts/build.js`).
- Os dados vão em gzip, um `.bin` por bloco, buscados por `fetch` e abertos com
  `DecompressionStream`.
- A página precisa de servidor (a web, ou `python3 -m http.server` na pasta): por
  `file://` ela avisa. O arquivo único que abria por `file://` saiu em 2026-10-26: o
  `index.html` tinha 38 MB, contra o orçamento de 25 MB.
- O `package.json` e o `node_modules/` servem à suíte de testes e ao build da web (minificação).

Arquitetura herdada de `../rios-do-brasil`.

## Os dados moram em `../rodado`, no beelink

Este repositório não guarda dado: `pipeline/dados/` fica fora do git.
- `pipeline/beelink.py` roda cada extração no DuckDB do beelink em modo `-readonly`, com a
  extensão `spatial`.
- Cada extração grava um parquet em `beelink:~/bragro_tmp/` com `COPY ... TO`, e o arquivo
  volta por `scp`.
- Nunca use S3 nem BigQuery: vale a regra do `../rodado/AGENTS.md`.

| Script | Fonte no espelho | Saída |
|---|---|---|
| `baixa_malha.py` | `br_geobr_mapas` (município, setor 2010, pegada urbana, TI, UC) + `br_bd_diretorios_brasil.municipio` | `malha`, `mascara` |
| `baixa_producao.py` | `br_ibge_pam.lavoura_*`, `br_ibge_ppm.*` | `producao` |
| `baixa_mapbiomas.py` | `br_mapbiomas_estatisticas.*` | `mapbiomas`, `transicao`, `bioma` |
| `baixa_credito.py` | `br_bcb_sicor` (glebas, operação, empreendimento, Proagro) | `glebas_*`, `proagro_*` |
| `baixa_cadastros.py` | `br_cgu_garantia_safra`, `br_sfb_sicar` | `gsafra`, `sicar` |
| `baixa_regioes.py` | `br_geobr_mapas` (UF, região, país, bioma, semiárido, Amazônia Legal, sedes) + diretório | `regioes`, `divisao`, `sedes` |
| `baixa_dinheiro.py` | SICOR completo, `br_bcb_estban`, `br_bndes_desembolsos`, `br_bcb_scrdata`, `br_ibge_pib` | `credito_*`, `estban`, `bndes`, `scr`, `pib` |
| `baixa_terra.py` | PRODES, DETER, queimadas, IBAMA (embargos, autos), INCRA | `prodes_*`, `deter_mun`, `fogo_*`, `ibama_mun`, `fundiario` |
| `baixa_clima.py` | `br_inpe_sisam`, `br_inmet_bdmep`, `br_sedec_desastres` | `clima_ano`, `clima_normal`, `estacoes`, `desastres` |
| `baixa_mercado_gente.py` | Trase, Comex, SEEG, RAIS, CAGED, CadÚnico, Seguro-Defeso, população, CAFIR, CNEFE | `trase*`, `logistica`, `comex`, `seeg`, `trabalho`, `social`, `imoveis` |
| `baixa_calendario.py` | SICOR (datas de plantio e colheita) | `calendario` |
| `baixa_censo_agro.py` | `br_ibge_censo_agropecuario.sidra_municipio` (recortes do Censo 2017 por município) | `censo_agro` |
| `baixa_listasuja.py` | `br_mte_listasuja.empregadores_municipio` (município derivado do texto, no rodado) | `listasuja`, `listasuja_ativ` |
| `baixa_lspa.py` | `br_ibge_lspa.sidra` (tabela 1618, último levantamento) | `lspa_uf` |
| `baixa_imovel.py` | CAR (SICAR) × SICOR e Proagro, embargos (IBAMA, ICMBio), polígonos do PRODES/DETER, TI/UC, florestas públicas (CNFP), polígonos do INCRA (SIGEF, assentamentos); cruzamento no beelink, só agregados voltam | `imovel_mun`, `imovel_ano` |

`baixa_producao.py` também traz a PEVS (itens `E|` extração e `S|` silvicultura) e vacas
ordenhadas e ovinos tosquiados da PPM. As armadilhas medidas estão no docstring de cada script
e em `../rodado/docs/context/gotchas/`.

## Comandos

```bash
cd pipeline
for s in malha producao mapbiomas credito cadastros regioes dinheiro terra clima mercado_gente calendario imovel \
         censo_agro listasuja lspa; do
  python3 baixa_$s.py || break; done                          # ~3 min no total
python3 monta_pagina.py      # parquet -> blocos -> ../site/ (index.html e dados/*.bin)
cd .. && bun run build       # site/ -> dist/: HTML, CSS e JS minificados + service worker (é o que o Pages publica)

cd .. && bun install && bun run preparar   # uma vez: chromium, firefox, webkit
bun test                                   # 133 testes nos 3 motores (3 pulados: offline no WebKit, file:// fora do Chromium), ~3 min; CHAO_MOTORES=chromium para um só
bun testes/_perf.ts                        # primeiro mapa e tudo pronto com rede 4G simulada
```

Dependências Python: `polars`, `numpy`, `shapely`. Cada `baixa_*.py` imprime a própria
conferência contra uma ordem de grandeza conhecida (soja 2024 = 46,2 M ha; Brasil = 8,5 M km²;
bovinos = 238 M; SICAR = 716 M ha). Se uma delas sair do esperado, investigue antes de montar.

## Como a página é montada

- Edite `pipeline/template.html`, nunca o `site/index.html`: ele é gerado e a próxima
  montagem o sobrescreve.
- Os marcadores `/*__MALHA__*/`, `PROD`, `MAPB`, `CRED`, `CAD`… viram `data-src` com o
  arquivo do bloco, e `FONTE` vira a fonte embutida, em `monta_pagina.py`.

Formato de cada bloco: `u32 tamanho | cabeçalho JSON | arrays`, em gzip.
- **Bytes em planos:** inteiros de mais de um byte vão com todos os bytes 0, depois todos os
  bytes 1, e assim por diante.
- **Escala log:** magnitudes vão em u16, com código = round(ln(1+v)·200) + 1, passo de 0,5%.
- **Diferenças:** município e ano da produção e do MapBiomas vão em diferença com a linha
  anterior (`meta.delta`); o JS faz a soma acumulada.
- Os valores ficam absolutos, porque em diferença o gzip piora (medido).

## A saída: `site/`

- Sem release a partir de 2026-10-26: a página é só a web (e `site/` servido localmente). O
  `index.html` único das releases até `v2026.10.26` não é mais gerado.
- `site/`: a fonte da versão web, e o que a suíte principal testa (`testes/comum.ts` a serve
  por HTTP). O workflow `.github/workflows/pages.yml` roda `bun run
  build`, que minifica o HTML (−27%) em `dist/` e escreve o `sw.js`, como no `../swissviz`, e
  publica `dist/` em https://rafapolo.github.io/chao/. `dist/` fica fora do git.
- Service worker: a página guarda no cache `chao-dados` cada bloco que baixa (o nome tem o
  hash; o SW não pré-carrega bloco, senão a 1ª visita baixaria tudo duas vezes). O SW serve
  o bloco do cache e a página da rede, com o cache como reserva: a 2ª visita abre sem rede.
- A primeira etapa é pedida por um `fetch` no `<head>` (`window.__pre`), não por `<link
  rel=preload>`: o WebKit não casava o preload e baixava a malha duas vezes.
- Download parado (nenhum pedaço em 20 s, `PARADO`) desiste com aviso. Sem JavaScript, um
  `<noscript>` explica.
- Testes no estilo do swissviz (`testes/site.test.ts`, sobre `dist/`): sem
  DecompressionStream, sem JavaScript, download parado, 2ª visita offline (não no WebKit, que
  não recarrega offline no Playwright). Fora do teste do SW, o contexto usa
  `serviceWorkers: "block"`: com o SW no controle o Playwright não vê os pedidos. HTML de ~160 kB e um `.bin` (gzip cru) por bloco,
  com o hash do conteúdo no nome. Dado que não muda mantém o nome, e o navegador não baixa
  de novo quando só o HTML muda. A montagem apaga de `site/dados/` os blocos de hashes
  antigos. O Pages serve o `.bin` cru; se um servidor mandar `Content-Encoding: gzip`, a
  página vê que os bytes não começam com `1f 8b` e lê o bloco direto.
- A página carrega em três etapas. A primeira traz malha e área da produção (6,2 MB) e
  desenha. A segunda traz MapBiomas, crédito e cadastros (3,5 MB). Quantidade e valor
  (`prodqv`, 10 MB) ficaram na terceira: a abertura (lavoura principal) só usa área. Medido
  com rede 4G (`testes/_perf.ts`): primeiro mapa em 3,0 s, tudo pronto em 4,2 s com 9,9 MB
  (antes das etapas: 8,5 s com 20,6 MB). Até ela chegar, as outras fontes e medidas ficam desligadas; um
  estado de URL que precise delas espera tudo antes de desenhar.
- A terceira etapa (`data-etapa="sob-demanda"`: prodqv, contornos, credrs, econ, terra, fogo, clima,
  calend, mercado, emis, gente, imovel; 19 MB) só é pedida quando um modo a usa (`blocos:` em
  `MODOS`), por `carrega(id)` com cache de promessa e `garante([ids])`. A ficha não baixa
  bloco: mostra o que já veio e oferece o botão "Mostrar também".
- Modo novo de série município × ano: uma entrada em `SERIES` (bloco, medidas, unidade) e,
  no pipeline, `series(bloco, df, {chave: coluna})`. Não precisa de código de cálculo.
- JSON foi testado em 2026-10-26 e voltou atrás: +25% transferidos (35,4 contra 28,4 MB) e
  tudo pronto em 5,2 s, contra 4,2 s com o binário. O Brotli ganharia só 7% e pediria um decodificador em wasm, porque o `DecompressionStream`
  não abre Brotli em todo navegador.
- A saída é determinística (toda ordenação desempata até o fim). Sem isso o hash muda a
  cada montagem e o cache se perde.

O orçamento da spec é ≤ 25 MB. Ele valia para o arquivo único; no `site/`, o que se baixa
para o primeiro mapa são 6,6 MB (HTML e 1ª etapa), e o resto vem por etapa.

## Armadilhas dos dados (medidas em 2026-10-21)

- **PAM, área plantada:** só existe a partir de 1988. De 1974 a 1987 entra a área
  **colhida**, e a página avisa.
- **PAM, valor:** está em R$ mil e entra só a partir de 1994; antes disso está em moeda da
  época.
- **PAM, quantidade das permanentes:** entra só a partir de 2001, porque as frutas trocaram
  de unidade (laranja: 106.651 mil frutos em 2000 → 16.983 mil t em 2001).
- **PAM, café:** só o Total, sem Arábica e Canephora, para não somar duas vezes.
- **MapBiomas, cobertura:** repete município × ano × classe quando o município atravessa dois
  biomas; sempre some.
- **MapBiomas, transição decenal:** o `ano` é o fim da década (2000 = 1990→2000) e a área
  está em km², não em ha.
- **Garantia-Safra:** o código SIAFI tem zero à esquerda. A junção com `id_municipio_rf` tem
  de ser feita como inteiro: como texto casam 1.106 de 1.327 municípios.
- **Glebas do SICOR:** são **amostra**, não total. Só cobrem crédito com recurso público (soja
  2023/24: ~4 M ha em polígonos, contra 46 M ha na PAM). A área do polígono passa da área
  financiada.
- **Privacidade:** célula da grade com menos de 5 glebas ou perdas não é embutida (cai ~35% da
  área de glebas). O mesmo corte vale para o agregado por município × produto × safra (glebas)
  e município × evento × safra (perdas). Também vale para o crédito em R$ (combinação com
  menos de 5 operações; indicadores do município × safra só com 5 ou mais operações, para
  que a diferença com as combinações não revele o que foi cortado; tomadores só com 5 ou
  mais; instituição por município), o calendário (município × cultura) e o Seguro-Defeso
  (5 pescadores). O teste de privacidade confere todos esses cortes.
- **Imóvel do CAR** (`baixa_imovel.py`): o cruzamento por imóvel fica no beelink
  (`~/bragro_tmp/imovel/`) e só voltam somas por município. Cada soma de crédito precisa de 5
  ou mais operações e 5 ou mais imóveis, e o resto do crédito em CAR, de 0 ou 5 ou mais
  operações. Quem confere esse corte é um assert no `monta_pagina.py`, com as contagens que
  não entram na página. A grade do imóvel é de 0,25°; a de 0,05° já foi publicada, então a
  etapa `grade` também corta a célula de 0,25° cujo resíduo contra as de 0,05° publicadas
  (`celulas_publicadas.py`, no beelink) tem 1 a 4 operações ou imóveis.
  O mesmo vale entre versões: com a entrada da SEMA-MT (2026-10-25), o `ce` de hoje menos o
  de antes revelaria o grupo acrescentado em 37 município × safra do MT, e eles ficam sem
  `ce` (`imovel_ce_corta.parquet`). As versões de antes saíram do histórico do git
  (`git filter-repo`, 2026-10-26). Ao mudar a definição de uma medida já publicada, meça o
  grupo que muda antes de publicar.
  Da SEMA-MT sai a área que `areas_desembargadas` devolve com o mesmo termo e que toca o
  polígono (`ST_Difference`; só o termo não basta, porque ele se repete). Sem data, o
  desembargo vale para todas as safras. Em 2026-10-28 nenhuma operação mudou de marca. O teste só confere que o bloco não traz nada além das séries.
- **PRODES:** começa em 2002. O incremento de 2001 sai da diferença contra a linha de base de
  2000 e infla (101 mil km², contra 73–79 mil em 2002–2004).
- **SICOR em R$:** só o crédito de recurso controlado ou equalizado tem município (R$ 136 de
  422 bi em 2023/24). O mapa mostra essa parte, e a UF mostra o total.
- **Censo Agropecuário 2017** (`baixa_censo_agro.py`): por município o SIDRA só cabe em
  recortes (uma classificação aberta, as outras no Total; `ibge_sidra.py recorte` no rodado).
  O IBGE põe `X` (sigilo) onde há 1 ou 2 informantes: o valor vem nulo, e a porcentagem com
  numerador ou denominador em `X` fica sem valor, não 0. Estabelecimento não é imóvel, e
  "familiar" é a tipologia do Censo (Lei 11.326), não a DAP. Um ano só: a linha do tempo fica
  em 2017.
- **Lista Suja** (`baixa_listasuja.py`): o MTE não publica município; o rodado o tira do texto
  do estabelecimento (344 de 345 casos do campo casam). O `empregadores_historico` soma os
  retratos de cada coleta: conte caso distinto, senão os trabalhadores dobram. Ações fiscais
  de 2020 a 2026. **Sem o corte de 5**, por decisão (`tasks/done/decisoes_pendentes.md`, item 9).
  No mapa, círculo na sede (`emSedes`), não cor.
- **LSPA** (`baixa_lspa.py`): só por UF, e muda a cada levantamento mensal. A PAM do espelho
  vai até 2024, então o LSPA acrescenta 2025 e 2026 ao modo Declarado, só na soma de lavouras
  em % da área rural (`lspaVale`): a UF inteira pinta com a mesma cor. Vai no bloco `cad`.
- **Desmembramentos:** 1.624 municípios foram instalados depois de 1974. Antes de existir, o
  filho não tem dado, e o pai traz o território inteiro da época, desenhado menor na malha
  atual.
  - Nos anos em que um grupo da AMC (`br_geobr_mapas.area_minima_comparavel_2010`, coluna
    `id_municipio` = lista de membros) está incompleto, a página reparte o total do grupo
    entre os membros pela área rural (`porAMC`).
  - Os 5 municípios de 2013 vão para a AMC do município de origem (`ORIGEM_2013` em
    `monta_pagina.py`).
  - Vale para os modos Declarado e Satélite × declarado. O MapBiomas e o crédito já vêm na
    malha atual.
- **Transição do MapBiomas:** a área fica 2–11% acima da cobertura do mesmo ano (Sorriso), o
  que sugere outra coleção. O modo Expansão herda esse viés; use-o para proporção de origens.
- **Abaixo do município**, a página tem só a máscara do que não é rural e a grade de glebas,
  que é amostra. O número do IBGE não é redistribuído sobre os pixels do satélite, porque isso
  exige o raster de 30 m do MapBiomas, que ficou fora da v1.
- **Área urbana:** a máscara usa o setor censitário urbano de 2010, que segue o perímetro
  legal da cidade. Por isso dá 105 mil km², mais que a mancha urbanizada.

## Lavoura principal

- Cada uma das 69 lavouras pertence a uma de 10 famílias (`FAMILIAS` em `monta_pagina.py`:
  cereais, oleaginosas, cana, feijões, raízes, café/cacau/estimulantes, fibras, frutas,
  hortaliças, borracha e forragem). Lavoura nova na PAM sem família quebra a montagem de
  propósito (`KeyError`).
- O município sai na cor da família que soma mais área entre as lavouras ligadas. A legenda
  à direita é uma árvore em três níveis: grupo do IBGE (lavoura temporária, lavoura
  permanente; abertos de início), família e lavoura. Família que tem lavoura dos dois grupos
  aparece nos dois, cada vez só com as suas (`data-g` + `data-fam` no botão). Grupo, família
  e lavoura ligam e desligam; na soma, o grupo inteiro conta como uma unidade
  (`c=f:lavoura-temporaria`).
- A árvore é o único lugar onde se escolhe a cultura, nos dois modos (alternador `Soma |
  Principal` no topo da legenda, busca logo abaixo). Na soma ela ganha um galho por grupo do
  IBGE que não é lavoura (rebanho, origem animal, aquicultura, extração, silvicultura;
  `ARVORE` no template), mostra o total do ano no recorte e marca em vez de ligar. Família
  com itens de unidades diferentes só abre e fecha.
- Seleção da soma: lavouras somam entre si (em ha); o resto só com a mesma unidade, e um
  item de outra unidade troca a seleção (fica apagado na árvore). Família inteira conta como
  uma no limite de 8, no título e na URL (`c=soja,f:cereais`).
- Cores `--f1`…`--f10`: sóbrias (L 0,49–0,72, C ≤ 0,13), de um recozimento em OKLCH que
  maximiza o menor ΔE. Todos os pares passam o piso de visão normal (15,3); o de daltonismo
  não, e com 10 cores nenhuma paleta passa. O tooltip nomeia a família e a maior lavoura.
- Estado na URL: `d=1` liga o modo e `dx=soja,milho` lista as lavouras desligadas.
- Cada lavoura é um tom da cor da família (OKLCH, mesmo matiz, mais clara ou escura; a
  maior fica com a cor da família), no mapa e na árvore.
- Só tema escuro, a pedido. Sem botões de zoom: roda, pinça e duplo clique.
- Como no swissviz: chips embaixo à direita (`sobre`, que abre um diálogo, e a linha do
  tempo com o ano); a linha do tempo é compacta, no centro de baixo, e abre e fecha; o
  painel esquerdo tem a altura do conteúdo e recolhe só no título. No celular, filtros e
  legenda são folhas de baixo, uma por vez.
- Ficha: cabeçalho fixo com um atalho por tema (os de `SECOES`, achados pelo começo do
  título em `TEMA_FICHA`); as seções vêm agrupadas na ordem das abas, e ao abrir o
  município ou trocar de modo a ficha rola até o tema do modo. Em tela de até 1700 px ela
  recolhe a legenda ao abrir e a reabre ao fechar (só se foi ela quem recolheu), e a linha
  do tempo sai de baixo dela. `/` leva à busca de município; os atalhos estão no `sobre`.

## Testes

`testes/mapa.test.ts` roda nos três motores. Os internos da página ficam fechados na IIFE;
`testes/comum.ts` define `window.__testes` com `addInitScript`, e a página chama esse gancho
no fim do carregamento. Sem o gancho, não há porta de depuração.
- **Playwright:** use o Chromium que vem com ele, nunca o Chrome instalado.
- **`expect`:** o do Bun não tem `toHaveText` e similares; leia o `textContent`.
