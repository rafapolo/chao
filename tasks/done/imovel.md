# Terra e imóvel: juntar tudo pelo imóvel rural

Aberto e executado em 2026-10-25. Continua a seção 5 do [`docs/ERD.md`](../../docs/ERD.md) ("o hub que ainda
falta"). Hoje o Chão cruza crédito, desmatamento, embargo e cadastro de terra só no nível
do **município**. Este plano leva o cruzamento para o **imóvel** (o polígono do CAR) e
depois devolve à página só agregados.

## O que já temos no espelho (medido no `schemas.json` e nas gotchas, 2026-10-25)

| Tabela | Chave de imóvel | Geometria | Armadilha que pesa aqui |
|---|---|---|---|
| `br_sfb_sicar.area_imovel` | `id_imovel` (código do CAR) | **polígono** | 10 fotos mensais (79,3 mi linhas): use uma só (2025-10-15: 8,19 mi imóveis, 715,8 mi ha sem cancelados). É de outra safra que as camadas. |
| `br_sfb_sicar.app`, `reserva_legal`, `vegetacao_nativa`, `area_consolidada`, `area_pousio`, `uso_restrito`, `servidao_administrativa` | `id_imovel` | só `area_pousio`, `uso_restrito` e `servidao` têm polígono | `APP_TOTAL` já agrega os outros tipos; 9 áreas absurdas em `app` (corte < 1e7 ha). Data de extração por UF. |
| `br_bcb_sicor.recurso_publico_propriedade` | `id_car`, `id_sncr`, `id_cib`, mais CPF/CNPJ | — | **Taxa de preenchimento do `id_car` não medida.** |
| `br_bcb_sicor.recurso_publico_gleba`, `proagro_rcp_gleba` | pela operação | **polígono** | 2% das glebas do Proagro sem geometria convertida (`geometria_original` preenchida). |
| `br_ibama_embargos_novo.termo_embargo`, `itens`, `coordenadas` | `nome_imovel` (texto livre) | **polígono** em WKT (`geom_area_embargada`, `itens.wkt`) | datas impossíveis (ano 2925); 6.307 cancelados; área sem unidade declarada (≈ ha). |
| `br_ibama_autos.auto_infracao` | — | WKT (`wkt_ge_area_autuada`) e ponto | só os autos de flora interessam. |
| `br_inpe_deter.avisos` | — | **só centroide** | classe em duas colunas; no Pantanal e na não-floresta o município vem do centroide. |
| `br_inpe_prodes_acumulado.desmatamento` | — | **só centroide** | não somar `amazonia_legal` com os biomas. |
| `br_incra_acervo.sigef_parcelas`, `snci_parcelas` | `codigo_imo` / `cod_imovel` (SNCR?) | **só centroide** | o formato do código contra o CAFIR não foi conferido. |
| `br_incra_acervo.assentamentos` | `cd_sipra` | só ponto | município pelo nome. |
| `br_rf_cafir.imoveis_rurais` | `id_imovel_incra`, `id_imovel_receita_federal` | — | `id_imovel_receita_federal` nulo em 62%; a área não fecha em unidade nenhuma (use só contagem). |

Resumo prático: o **CAR é a única malha de imóveis** que temos. Crédito (gleba), embargo e
auto têm polígono e cruzam por geometria. Desmatamento e INCRA, por enquanto, só por ponto
dentro do polígono. O CAFIR não liga ao CAR, mas liga SIGEF, SNCI e SICOR pelo código INCRA
(com as colunas de nome trocado; ver o passo 0).

## O que não temos e onde buscar

Tudo isso entra no **rodado** (espelho), não no Chão: vale a regra do `../rodado/AGENTS.md`.
O Chão só lê do beelink.

| Dado | Para quê | Onde |
|---|---|---|
| Polígonos do PRODES (todos os biomas) e do DETER | interseção de verdade com o CAR, sem a aproximação pelo centroide | TerraBrasilis (INPE): shapefiles por bioma e WFS |
| **MapBiomas Alerta** | alerta de desmatamento já validado, **com os códigos do CAR atingidos** e laudo; atalho para o passo 5 | API GraphQL pública do MapBiomas Alerta |
| Polígonos do SIGEF e do SNCI (parcelas certificadas) e dos assentamentos | imóvel certificado × CAR declarado; assentamento como área, não ponto | Acervo Fundiário do INCRA (shapefile por UF) |
| **Cadastro Nacional de Florestas Públicas (CNFP)** | CAR sobreposto a floresta pública não destinada (a forma mais comum de grilagem declarada) | Serviço Florestal Brasileiro |
| Embargos do ICMBio e das secretarias estaduais (SEMA-MT, SEMAS-PA) | completar o embargo federal | dados abertos de cada órgão |
| Situação de análise do CAR e adesão ao PRA | separar o CAR só declarado do analisado | SICAR, consulta pública / demonstrativo |
| Raster do MapBiomas, 30 m (fase 9 do plano de dados) | uso do solo **dentro** do imóvel, ano a ano | GCS do MapBiomas, ~800 MB por ano (medido) |

## Passos

### 0. Medir antes de construir (uma tarde, só consultas)

Rodar no beelink por `pipeline/beelink.py`, que abre o banco em modo só leitura. Anotar cada
número como gotcha no rodado.

- [x] `id_car` em `recurso_publico_propriedade`, por safra:
  - fração preenchida;
  - fração que casa com um `id_imovel` da foto escolhida do CAR;
  - formato: com ou sem pontos, UF na frente.
  - **Medido (2026-10-25):** é o código do CAR sem hífens (41 caracteres). Vazio até 2017, 3%
    em 2018, 95–99% de 2019 em diante; casa 100,0% com a foto 2025-10-15 de 2019 a 2024
    (99,4% em 2025, 90% em 2018). Uma operação tem 1,65 CARs em média (31% com mais de um).
- [x] Fração das glebas do SICOR (safra 2023/24) cujo centroide cai num polígono do CAR. Na
  gleba que tem `id_car`, conferir se o polígono que a contém é o mesmo imóvel.
  **Medido:** amostra de 3.066 glebas: 98% caem num CAR, 16% em dois ou mais; 91% no CAR
  declarado. No total, 7.179.948 de 7.326.507 glebas ficam com imóvel.
- [x] Embargos com WKT válido (`ST_IsValid`) e quantos caem num CAR.
  **Medido:** 56.680 termos não cancelados com WKT, todos válidos depois de `ST_MakeValid`
  menos 1; 90% tocam um CAR (3,25 por termo, por isso a fração de área). Pelo ponto, 56%, e
  4.878 pontos caem fora do Brasil. `seq_tad` se repete.
- [x] `codigo_imo` do SIGEF contra o `id_imovel_incra` do CAFIR: formato e taxa de casamento.
  **Medido:** no CAFIR os nomes estão trocados. O código INCRA de 13 dígitos está em
  `id_imovel_receita_federal`; o SIGEF casa com ele em 71% (SNCI 76%, `id_sncr` do SICOR
  70%). O CAFIR liga SIGEF, SNCI e SICOR, mas não o CAR.
- [x] Sobreposição entre os próprios polígonos do CAR (imóveis que se sobrepõem a outros):
  define se a interseção precisa de "maior sobreposição vence".
  **Medido:** amostra de 2.034 imóveis ativos: 60% sobrepõem outro em mais de 1%, 23% em mais
  de 50%, 12% estão inteiros dentro de outro. Precisa, e as somas de área vão pela origem.

**Critério para seguir:** se o `id_car` do SICOR casar em menos de ~30% das operações com
gleba, a ponte principal passa a ser a geometria (passo 2b), não o código.
**Resultado:** o código casa ~100% de 2019 em diante e é a ponte principal; 2016–2018 vão pela
gleba. Gotchas e pontes gravadas no rodado (`472bcc5`).

### 1. Tabela de imóveis (no beelink, DuckDB `spatial`)

- [x] `imovel`: uma linha por `id_imovel` da foto 2025-10-15, sem cancelados, com:
  - polígono válido (`ST_MakeValid`);
  - centroide, área em ha, módulos fiscais, município, UF, status e condição.
- [x] Índice espacial (RTREE) e partição por UF: 8,2 mi polígonos cabem nos 27 GB de RAM do
  beelink se o trabalho for feito UF a UF. **Feito:** parquet particionado por UF (2,8 GB,
  13 s para o Brasil todo); sem RTREE persistente, o spatial join do DuckDB monta o seu.
  Glebas × CAR do Brasil inteiro em 33 s, sem precisar ir UF a UF.
- [x] Camadas por imóvel (APP, RL, vegetação nativa, consolidada): somar por `id_imovel`,
  respeitando as gotchas (APP_TOTAL, área absurda).

### 2. Crédito → imóvel

- [x] **2a. Pelo código:** juntar `recurso_publico_propriedade.id_car` com `imovel.id_imovel`.
- [x] **2b. Pela geometria:** a gleba (`recurso_publico_gleba`) cai no imóvel de maior
  sobreposição. Fazer o mesmo com a `proagro_rcp_gleba`. (Proagro ainda não: nenhuma medida
  do passo 6 usa.)
- [x] Ponte `operacao_imovel(id_referencia_bacen, numero_ordem, id_imovel, metodo, fracao)`,
  com `metodo` ∈ {código, gleba}. Quando os dois existem e discordam, registrar e contar a
  divergência, que já é um achado. **Medido:** 4.080.783 operações com os dois; em 644.484
  (15,8%) nenhuma gleba cai num CAR declarado. `fracao` soma 1 por operação.

### 3. Fiscalização → imóvel

- [x] Embargo: o polígono (`geom_area_embargada` ou `itens.wkt`) cruzado com o `imovel`.
  Sem polígono, o ponto (`num_latitude_tad`, `num_longitude_tad`).
  - Data limpa: `try_strptime`, cortada no presente.
  - Sem cancelados. Com desembargo (`sit_desembargo`, `dat_desembargo`).
- [x] Auto de flora: o mesmo cruzamento, pelo WKT da área autuada ou pelo ponto.

### 4. Desmatamento → imóvel

- [x] **Agora:** o centroide do PRODES e do DETER dentro do polígono do CAR. É uma
  aproximação, marcada `metodo = centroide`: um alerta grande que atravessa a divisa cai
  inteiro de um lado só.
- [x] **Depois:** com os polígonos do TerraBrasilis no rodado, a interseção de verdade, com a
  área desmatada repartida entre os imóveis. (Feito em 2026-10-25; ver `../imovel_pendente.md`.)
- [ ] **Atalho** (bloqueado: a API pede conta; ver `../imovel_pendente.md`)**:** o MapBiomas Alerta já entrega o alerta com a lista de CARs atingidos. Usar
  como conferência do cruzamento próprio (casamento esperado alto na Amazônia e no Cerrado).

### 5. Terra pública e certificação

- [x] CAR × TI e UC de proteção integral (já no espelho, geobr): área do imóvel declarada
  dentro de área protegida. **Medido:** 5,5 mi ha do CAR ativo em TI, 18,5 mi ha em UC de
  proteção integral.
- [x] CAR × florestas públicas não destinadas (CNFP 2025, feito em 2026-10-25).
- [x] CAR × SIGEF: o imóvel declarado tem parcela certificada? Agora pelo centroide da
  parcela; com o polígono do INCRA, pela sobreposição. **Medido:** 1.199.463 imóveis com
  parcela pelo centroide.
- [x] Assentamento: ponto agora, polígono depois (polígono do INCRA, 2026-10-25). Conta imóveis do CAR dentro do projeto.
  (Com o ponto só não dá para contar imóveis dentro do projeto: espera o polígono.)

### 6. O que volta para o Chão (só agregado)

O cruzamento por imóvel fica **no beelink**. A página recebe somas por município e por
célula da grade, sempre com o corte de 5 que já vale para glebas e crédito:
- nenhum imóvel, CPF, CNPJ ou nome vai para o `index.html`;
- nenhum `id_imovel` vai junto com um valor de crédito.

Medidas candidatas (um modo novo "Imóvel", seção Terra, ou linhas na ficha):

| Medida | Cruzamento |
|---|---|
| Crédito rural em imóvel com desmatamento **depois** da safra financiada (R$, ha) | 2 × 4, com a data do alerta posterior à emissão |
| Crédito em imóvel com embargo vigente na data da emissão | 2 × 3 |
| % da área do CAR sobreposta a TI, UC ou floresta pública | 5 |
| % do desmatamento do município que caiu dentro de CAR (e fora dele) | 4 |
| % dos imóveis do CAR com parcela certificada no SIGEF | 5 |
| Reserva legal declarada × vegetação nativa declarada, por município | camadas do 1 |
| Área financiada ÷ área do imóvel (gleba que passa do imóvel) | 2b |

**Feito (2026-10-25):** modo "Imóvel (CAR)" na seção Terra, série município × ano no bloco
sob demanda `imovel` (0,3 MB gz), com todas as medidas da tabela. "Depois do crédito" virou
"durante a operação": alerta entre a emissão e o vencimento. Crédito por imóvel só de 2016
em diante; PRODES de 2017 em diante (antes é bienal fora da Amazônia).

No pipeline: um `baixa_imovel.py` com as extrações e as conferências, um bloco `imovel`
sob demanda, e o modo em `MODOS` mais uma entrada em `SERIES`, quando a medida for município
× ano.

## Riscos e decisões em aberto

- **Privacidade.** Embargo e CAR são públicos, mas ligar crédito a imóvel identifica pessoa.
  Tudo o que sai do beelink é agregado com corte de 5. **Decidido (2026-10-25): só somas**
  (R$, ha), sem contagem de embargos; cada soma com 5+ operações e 5+ imóveis, e o resto do
  crédito em CAR com 0 ou 5+ operações, conferido em `monta_pagina.py`.
- **Foto do CAR.** O CAR muda todo mês. Usar uma foto só (2025-10-15) para todas as safras
  é anacrônico: um imóvel inscrito em 2024 não existia na safra de 2016. **Decidido
  (2026-10-25): foto única, com aviso na nota.** Efeito visível: a "área financiada maior que
  o imóvel" cai de 2023 em diante, provavelmente porque imóveis antigos foram desmembrados
  depois.
- **CAR declarado não é imóvel verificado.** É autodeclaração e tem sobreposição. A página
  tem de dizer isso sempre que mostrar um número por imóvel.
- **Custo.** Interseção de 8 mi de polígonos com milhões de glebas: fazer UF a UF, salvar
  em parquet no beelink e medir o tempo de MT (o maior) antes de rodar o resto.
