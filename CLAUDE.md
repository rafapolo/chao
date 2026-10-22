# CLAUDE.md

Orientação para agentes que trabalham neste repositório.

## O que é

"Safra a Safra" é uma página HTML autocontida, `index.html` (~26 MB), com o mapa do que se planta e se cria
em cada município do Brasil, de 1974 a 2025. Ela tem linha do tempo, filtros por cultura,
medida, fonte e recorte, e uma ficha por município. A spec está em
`docs/superpowers/specs/2026-10-21-bragro-design.md`.

**Não há build nem dependência em runtime.**
- Os dados vão embutidos em gzip+base64 e são abertos no navegador com `DecompressionStream`.
- A página tem de abrir por `file://`: é requisito.
- O `package.json` e o `node_modules/` servem só à suíte de testes.

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

## Comandos

```bash
cd pipeline
python3 baixa_malha.py && python3 baixa_producao.py && python3 baixa_mapbiomas.py \
  && python3 baixa_credito.py && python3 baixa_cadastros.py    # ~2 min no total
python3 monta_pagina.py      # parquet -> blocos binários -> ../index.html (+ testes/fixture.json)

cd .. && bun install && bun run preparar   # uma vez: chromium, firefox, webkit
bun test                                   # 33 testes (11 × 3 motores), ~45 s; BRAGRO_MOTORES=chromium para um só
```

Dependências Python: `polars`, `numpy`, `shapely`. Cada `baixa_*.py` imprime a própria
conferência contra uma ordem de grandeza conhecida (soja 2024 = 46,2 M ha; Brasil = 8,5 M km²;
bovinos = 238 M; SICAR = 716 M ha). Se uma delas sair do esperado, investigue antes de montar.

## Como a página é montada

- Edite `pipeline/template.html`, nunca o `index.html`: ele é gerado e a próxima montagem o
  sobrescreve.
- Os marcadores `/*__MALHA__*/`, `PROD`, `MAPB`, `CRED`, `CAD` e `FONTE` são substituídos
  por `monta_pagina.py`.

Formato de cada bloco: `u32 tamanho | cabeçalho JSON | arrays`.
- **Bytes em planos:** inteiros de mais de um byte vão com todos os bytes 0, depois todos os
  bytes 1, e assim por diante.
- **Escala log:** magnitudes vão em u16, com código = round(ln(1+v)·200) + 1, passo de 0,5%.
- **Diferenças:** município e ano da produção e do MapBiomas vão em diferença com a linha
  anterior; o JS faz a soma acumulada.
- Os valores ficam absolutos, porque em diferença o gzip piora (medido).

O orçamento da spec é ≤ 25 MB, e **a página passa um pouco: 25,7 MB** (2026-10-21). A produção sozinha leva 16 MB. Se precisar cortar, os candidatos são os itens menores de origem animal (casulos, lã, ovos de codorna).

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
  e município × evento × safra (perdas). Há teste que confere os quatro.
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
  à direita é uma árvore: a família abre, e família e lavoura ligam e desligam.
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

## Testes

`testes/mapa.test.ts` roda nos três motores. Os internos da página ficam fechados na IIFE;
`testes/comum.ts` define `window.__testes` com `addInitScript`, e a página chama esse gancho
no fim do carregamento. Sem o gancho, não há porta de depuração.
- **Playwright:** use o Chromium que vem com ele, nunca o Chrome instalado.
- **`expect`:** o do Bun não tem `toHaveText` e similares; leia o `textContent`.
