# Censo Agropecuário, Lista Suja e LSPA

Aberto em 2026-10-26. São três fontes do `../rodado` que o Chão ainda não lê. Feito em 2026-10-26, menos o Censo 2006 e o crédito a empregador da lista (abertos abaixo). A ordem era a
recomendada: o Censo é o que mais acrescenta ("quem produz"), a Lista Suja é a mais barata,
e o LSPA é um extra para o ano corrente. Nada foi começado.

Vale a regra de sempre: a fonte entra no espelho com as suas armadilhas medidas, e só depois
o Chão lê (`pipeline/baixa_*.py`, extração no beelink em `-readonly`, parquet por `scp`).

## 1. Censo Agropecuário 2017 (`br_ibge_censo_agropecuario`)

### O que há no espelho (medido em 2026-10-26)

- O dataset é o SIDRA em formato longo: `sidra` (valores) e `sidra_tabelas` (índice).
  Raspado por `../rodado/scripts/scrap/ibge_sidra.py --pesquisa CA --periodo 2017`.
- 736 tabelas, e 498 delas existem no IBGE por município. **Só 5 estão no espelho por
  município** (6869, 8552, 8580, 9098, 9220: tratores e efetivo da pecuária). As outras estão
  em Brasil e UF. O motivo é o teto `TETO_MUN = 10 mi` de células: o raspador baixa todos os
  cruzamentos das classificações, e por município quase nenhuma tabela cabe.
- O parquet está com data de 2026-10-26: confira se outra sessão ainda mexe nele antes de
  rodar a raspagem.

### Dado: o que buscar (no rodado)

- [x] Um modo `recorte` no `ibge_sidra.py`, como o `ibge_sidra_censo2022_recortes.py`. Ele
  pede uma tabela em N6 com algumas categorias fixas (o Total na maior parte das
  classificações) em vez do produto cartesiano. Exemplo: a 6753 com tipologia em Total,
  familiar e não familiar e o resto em Total dá 5.570 × 2 variáveis × 3 ≈ 33 mil células.
  A saída vai numa tabela nova, `br_ibge_censo_agropecuario.sidra_municipio`, com a mesma
  forma longa e uma coluna `recorte`.
- [x] As tabelas e os recortes. Todas têm `tem_municipio = true` no índice:

  | Tabela | Recorte por município | Medida no Chão |
  |---|---|---|
  | 6753 ou 6770 | tipologia (familiar, não familiar); condição do produtor (proprietário, arrendatário, parceiro, comodatário, ocupante, sem área) | estabelecimentos, área, % familiar, % proprietário, área média |
  | 6770 | sexo do produtor | % dirigido por mulher |
  | 6885 ou 6887 | tipologia; laço de parentesco | pessoal ocupado, pessoal por estabelecimento |
  | 6851 | uso de agrotóxicos (usou, não usou) | % que usou agrotóxico |
  | 6857 | tipologia; Total do método | estabelecimentos com irrigação, área irrigada |
  | 6846 ou 6852 | origem da orientação técnica | % com orientação técnica (e de qual origem: governo, própria, cooperativa, empresa) |
  | 6848 ou 6846 | associação à cooperativa ou entidade de classe | % associado |
  | 6895 | obteve financiamento; agente financeiro | % com financiamento |
  | 6962 | possui DAP | % com DAP (Pronaf) |

  Escolha uma tabela por linha, e confira em `sidra_tabelas.variaveis` e
  `classificacoes` se o Total de cada classificação existe e qual é o id dele.
- [x] As armadilhas a medir e escrever em `../rodado/docs/context/gotchas/`:
  - o símbolo `X` (sigilo do IBGE, município com 1 ou 2 informantes) vem com `valor` NULL;
    conte quantos municípios caem assim em cada medida;
  - a "tipologia" do Censo é a agricultura familiar da Lei 11.326, e não a DAP nem o CAF;
  - o estabelecimento não é o imóvel: um imóvel pode ter vários estabelecimentos, e um
    estabelecimento pode juntar vários imóveis;
  - a malha é a de 2017 (5.570 municípios); confira os que faltam contra o diretório.
- [x] A conferência: a soma dos municípios tem de bater com a linha Brasil da 6753, que já
  está no espelho (conferida em 2026-10-26): 5.073.324 estabelecimentos, 351,3 M ha,
  3.897.408 familiares (76,8%, com 80,9 M ha). A tipologia tem 8 categorias: além de
  familiar sim e não, traz Pronaf B, Pronaf V, não pronafiano e Pronamp, que valem como
  medidas também.
- [x] Opcional: o Censo 2006 (tem outra numeração de tabelas no SIDRA) para dar a variação
  2006→2017. Antes disso, meça quantas medidas existem nos dois com a mesma definição: a
  agricultura familiar de 2006 seguia outro recorte.
- [x] **Medido em 2026-10-28; não entra por ora.** O 2006 não está no espelho: o catálogo
  `sidra_tabelas` só traz 2017. O SIDRA tem 547 tabelas do CA com 2006 por município, e os
  metadados saem só pelo proxy BR. Entre as medidas do modo Quem produz:
  - **Mesma definição (cerca de 15):** estabelecimentos, área, área média, condição do
    produtor (proprietário, assentado, arrendatário, parceiro, ocupante, sem área; tabela
    1109), sexo do dirigente, agrotóxico, irrigação e área irrigada, orientação técnica e a
    origem dela, associação, financiamento por agente (tabela 3302: bancos, cooperativas).
  - **Não comparáveis:** agricultura familiar (em 2006 era a Lei 11.326 com os critérios de
    então; em 2017, o Decreto 9.064, e o IBGE não compara), pessoal ocupado (31/12 em 2006,
    30/09 em 2017), DAP (em 2006 o recorte era "pronafiano", A a E) e comodatário (só existe
    em 2017).
  - **Próximo passo, se quiser:** buscar no rodado umas 8 tabelas de 2006
    (`ibge_sidra.py recorte --periodo 2006`), com as suas gotchas, e dar ao modo a variação
    2006→2017 só das medidas comparáveis.

> Feito em 2026-10-26. `ibge_sidra.py recorte` (10 recortes, 590.526 linhas) em `sidra_municipio`; a soma bate exata com a 6753 (5.073.324 estabelecimentos, 3.897.408 familiares). A 6848 ficou de fora: a associação vem da 6846. As tabelas por linha: 6753, 6770, 6885, 6851, 6857, 6846, 6895, 6962.

### Dado: o que entra no Chão

- [x] `pipeline/baixa_censo_agro.py`: lê a `sidra_municipio`, pivota para uma linha por
  município, e grava `censo_agro.parquet`. Imprime a conferência acima.
- [x] Em `monta_pagina.py`, um bloco novo `censo` na etapa `sob-demanda`, pelo caminho de
  sempre: `series('censo', df, {...})` com `ano = 2017` (e 2006, se entrar). Cabe no formato
  de série município × ano sem código novo de cálculo. Tamanho esperado: 5.570 × ~12
  medidas, bem menos de 1 MB.
- [x] As porcentagens saem no pipeline, não no navegador, e o município com o
  denominador em `X` fica sem valor (não 0).

### UX

- [x] Modo novo **"Quem produz"**, na seção Gente: `{ id: 'censo', nome: 'Quem produz',
  sub: 'Censo Agropecuário · 2017', sec: 'Gente', blocos: ['censo'] }` e uma entrada em
  `SERIES` com as medidas da tabela acima.
- [x] **Linha do tempo**: o Censo tem um ano só (ou dois). No modo, ela trava em 2017 e
  mostra o motivo ("o Censo é de 2017"), em vez de deixar o usuário mover para um ano sem
  dado. Com 2006, a linha mostra só os dois pontos e ganha a medida "variação 2006→2017".
- [x] **Ficha do município**: uma seção "Quem produz (Censo 2017)" com estabelecimentos,
  % familiar, área média, condição do produtor (uma barra empilhada), pessoal ocupado e os
  "% que usou" (agrotóxico, irrigação, orientação técnica, financiamento). Ela segue a regra
  da ficha: se o bloco não veio, entra no botão "Mostrar também".
- [x] Comparações de leitura direta, numa linha de texto do modo ou na ficha:
  - estabelecimentos do Censo 2017 × do CNEFE 2022 (`cnefe`, já no modo Trabalho);
  - agricultores familiares do Censo × famílias de agricultores no CadÚnico (`cad_agri`);
  - % com financiamento (Censo) × crédito do SICOR no município em 2017.
- [x] O texto do modo avisa que estabelecimento não é imóvel, e que o `X` é sigilo do IBGE.

## 2. Lista Suja do trabalho escravo

> Feito em 2026-10-26, sem o corte de 5 (decisão em `decisoes_pendentes.md`, item 9). Diferenças do plano: o histórico soma retratos (660 casos distintos, 5.248 trabalhadores, não 8.692); as ações fiscais vão de 2020 a 2026, não de 2018; a tabela derivada é `br_mte_listasuja.empregadores_municipio` (`../rodado/scripts/sync/listasuja_municipio.py`). (`br_mte_listasuja`)

### O que há no espelho (medido em 2026-10-26)

- `empregadores` (a lista atual, 508 linhas) e `empregadores_historico` (1.086 linhas, com
  todos que passaram pela lista desde a ação fiscal de 2018 até 2026). `ceac` e
  `ceac_historico` são os que firmaram termo de ajuste.
- Sem código de município: só `sigla_uf` e o texto `estabelecimento`, que quase sempre
  termina em `MUNICÍPIO/UF` ("FAZENDA JATOBÁ, ZONA RURAL, BARROLÂNDIA/TO").
- 729 linhas com CPF e 357 com CNPJ; 8.692 trabalhadores ao todo.
- Pela divisão da CNAE, o campo é a maior parte: 01 (agricultura e pecuária) tem 422 casos e
  4.072 trabalhadores; 02 (produção florestal, carvão) tem 139 e 995. Depois vêm 97 (trabalho
  doméstico), 08 (extração mineral) e 41 (construção).

### Dado

- [x] No rodado, uma coluna `id_municipio` derivada (ou uma tabela `empregadores_municipio`):
  - tire o último `.../UF` do texto, normalize (maiúsculas, sem acento, `trim`) e case com
    `br_bd_diretorios_brasil.municipio` por nome + UF;
  - para CNPJ, confira contra `br_me_cnpj.estabelecimentos.id_municipio` pelo `cnpj` inteiro.
    Se o cadastro e o texto divergirem, vale o texto (é o local da fiscalização, e o CNPJ é
    a sede);
  - meça e anote como gotcha quantos casam, quantos ficam sem município e quantos o CNPJ
    contradiz.
- [x] `pipeline/baixa_listasuja.py`: soma por município × ano da ação fiscal, com
  `casos` (empregadores distintos) e `trab` (trabalhadores resgatados), separando o campo
  (CNAE 01, 02, 03) do resto. Nome, CPF e CNPJ não saem do beelink.
- [x] **Decisão pendente: o corte de 5.** A lista é pública e nominal por lei, mas a página
  só publica agregado. Com 1 ou 2 casos por município, o corte de 5 apagaria quase tudo.
  Proposta: publicar sem o corte, porque o agregado não revela nada além da lista oficial. A
  decisão é sua; registre em `decisoes_pendentes.md` e no teste de privacidade.
- [x] Bloco: vai no `gente` (já sob demanda), como séries `le_casos` e `le_trab`, em vez de
  um bloco próprio (são poucas centenas de linhas).

### UX

- [x] Duas medidas no modo **"Trabalho e estrutura"**: "Trabalhadores resgatados em
  ação fiscal (Lista Suja, MTE)" e "Empregadores incluídos na Lista Suja".
- [x] O mapa fica quase vazio em coroplético (uns 350 municípios, de 1 a 3 casos cada).
  Melhor um círculo na sede do município (`sedes` já existe), com área proporcional aos
  trabalhadores. O seletor de ano mostra o ano da ação fiscal, com a opção "acumulado
  2018–ano".
- [x] Tooltip e ficha: número de casos e de trabalhadores e a atividade (CNAE em palavras:
  "criação de bovinos", "carvão vegetal"). Sem o nome do empregador, para manter a regra de
  só publicar agregado, mesmo com a fonte sendo nominal.
- [x] O texto do modo explica que a lista só tem quem já foi julgado em processo
  administrativo, e que ela começa na ação fiscal de 2018 (antes disso, sem dado, não zero).
- [x] Mais tarde, no modo Imóvel: crédito rural a empregador da lista (CNPJ e CPF contra o
  SICOR, no beelink, só a soma volta). É sensível; meça o tamanho do grupo antes de
  propor uma medida.
  - **Medido em 2026-10-28 (no beelink, só somas): não vira medida.** O CPF e o CNPJ do
    tomador estão em `br_bcb_sicor.recurso_publico_mutuario`, completos, e só cobrem o
    crédito de recurso público. Dos 647 empregadores do `empregadores_historico`, 126 tomaram
    crédito: R$ 315 mi em 1.244 operações de 2012 a 2025, de 10 a 54 tomadores por safra.
    Depois da decisão de procedência foram cerca de 15 tomadores e R$ 15 mi (2023–2025; MG 5
    tomadores, R$ 13 mi). Depois da inclusão na lista, nenhum. Por município, quase tudo
    cairia no corte de 5, e o grupo é pequeno e nominal, então fica fora da página.

## 3. LSPA (`br_ibge_lspa`)

> Feito em 2026-10-26. A PAM do espelho vai até 2024, então o LSPA acrescenta 2025 **e** 2026, e a conferência foi contra a PAM 2024. Só na medida % da área rural (em ha a UF não cabe na escala dos municípios). O bloco `lspa` foi para dentro do `cad` (2ª etapa).

### O que há no espelho (medido em 2026-10-26)

- Só Brasil, grande região e UF (`N1`, `N2`, `N3`); não existe por município.
- Tabela 1618: área plantada, área colhida e produção, por "ano da safra" (Safra 2025 e
  Safra 2026) e 37 produtos (`"1.17 Soja"`), no levantamento de setembro de 2026 (`202609`).
  A 188 tem o rendimento. A 7832 e a 7878 têm o fechamento de dezembro de 2025.
- A série histórica mês a mês (6588) está no índice mas não no espelho.

### Dado

- [x] `pipeline/baixa_lspa.py`: lê a 1618 no último `periodo`, casa o produto com o item da
  PAM (tabela de para à mão no script, como as famílias: produto sem casamento quebra a
  montagem de propósito) e grava `lspa_uf.parquet` (UF × safra × item × área, produção).
- [x] Conferência: o LSPA da Safra 2025 contra a PAM 2025 somada por UF (soja do MT: LSPA
  12,79 M ha). Diferença acima de ~5% é para investigar.
- [x] Bloco pequeno `lspa` (27 UF × ~37 itens), que pode ir na 2ª etapa.
- [x] O mês do levantamento vai no cabeçalho do bloco (`meta.lspa_mes`), porque o número
  muda a cada mês. Para atualizar, basta rodar o script de novo e remontar.

### UX

- [x] No modo **Declarado**, a linha do tempo ganha um ponto a mais, **2026 (previsão)**,
  tracejado.
- [x] Nesse ano o mapa pinta a UF, não o município, com a cor e a escala da lavoura
  selecionada, e diz no topo: "Estimativa do LSPA, levantamento de setembro de 2026, por
  estado".
- [x] Item sem LSPA (rebanho, PEVS, a maior parte das frutas) fica apagado na árvore nesse
  ano, com o motivo no tooltip.
- [x] O modo Lavoura principal não ganha 2026: por UF ele perde o sentido.
- [x] Ficha da UF (e, no município, a linha da UF): "2025 → 2026 previsto: +2,1% de área de
  soja".

## 4. `docs/ERD.md`

- [x] **Gente, trabalho e clima:** trocar a linha de `fato_trabalho_escravo`. Hoje ela diz
  "`sigla_uf` (sem município) ◻". Passa a ser "município pelo texto `estabelecimento`
  (nome/UF) contra o diretório, conferido pelo CNPJ em `br_me_cnpj`". Entra no diagrama:

  ```
  dim_municipio ||--o{ fato_trabalho_escravo : "nome/UF do estabelecimento"
  fato_trabalho_escravo {
      varchar id_municipio PK,FK
      smallint ano_acao_fiscal PK
      char cnae_divisao PK "01, 02, 03 = campo"
      int casos "empregadores distintos"
      int trabalhadores "resgatados"
  }
  ```
- [x] **Uma seção nova, "Estrutura dos estabelecimentos (Censo Agropecuário)"**: os
  diagramas de hoje não têm o estabelecimento, que não é imóvel nem município.

  ```
  dim_municipio ||--o{ fato_censo_agro : "id_municipio"
  fato_censo_agro {
      varchar id_municipio PK,FK
      smallint ano_censo PK "2006, 2017"
      varchar tipologia PK "familiar, não familiar, total"
      varchar condicao_produtor PK "proprietário, arrendatário, ocupante..."
      int estabelecimentos
      float area_ha
      int pessoal_ocupado
      int com_agrotoxico
      int com_irrigacao
      float area_irrigada_ha
      int com_orientacao_tecnica
      int com_financiamento
      int com_dap
      varchar simbolo "X = sigilo"
  }
  ```

  Na tabela de origem: `br_ibge_censo_agropecuario.sidra_municipio` (o recorte novo);
  `id_localidade` é o `id_municipio` direto. As ligações a declarar:
  - `fato_censo_agro` × `fato_trabalho` (CNEFE 2022): estabelecimentos;
  - × `fato_familias`: familiares;
  - × `sicor_*` de 2017: financiamento.
- [x] **Produção e uso da terra:** `fato_lspa_uf` (`sigla_uf`, `ano_safra`, `mes_levantamento`,
  `id_item`, `area_plantada_ha`, `area_colhida_ha`, `producao`), com FK para `dim_uf` e
  `dim_item`, e a nota de que `dim_item` ganha `id_produto_lspa`.
- [x] **"O que a integração destravaria":** um item 6, "Quem produz × o que se financia":
  `fato_censo_agro` (familiar, % com financiamento) contra o crédito do Pronaf no SICOR, no
  mesmo município, em 2017.
- [x] Regenerar o `ERD.png` depois.

## 5. Fechamento

- [x] `CLAUDE.md`: os scripts novos na tabela de scripts, e as armadilhas medidas na seção
  de armadilhas (o sigilo `X`, estabelecimento ≠ imóvel, a Lista Suja sem município, o LSPA
  só por UF e mensal).
- [x] Testes: o modo novo nos três motores (`testes/mapa.test.ts`), a trava da linha do tempo
  em 2017, o ponto 2026 do LSPA, e o teste de privacidade com a regra que for decidida para
  a Lista Suja.
- [x] `bun testes/_perf.ts`: o primeiro mapa não pode piorar (os blocos novos são sob
  demanda, menos o `lspa`).
