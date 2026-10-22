<p align="center"><img src="favicon.svg" width="72" alt=""></p>

# Chão

O campo brasileiro, município a município: o que se planta e se cria de 1974 a 2025, a
terra, o dinheiro, o clima e quem vive dele. É uma página só,
`index.html`, que abre sem internet: basta dar dois cliques no arquivo.

## O que dá para ver

- **Lavoura principal:** cada município na cor da família de lavouras que ocupa mais área:
  cereais, oleaginosas, cana, feijões, raízes, frutas… A legenda, à direita, é uma árvore.
  Abra uma família para ver as lavouras dela, cada uma num tom da cor da família, e ligue
  ou desligue cada uma, ou todas de uma vez. Tire a soja e veja o que vem por baixo.
- **Declarado:** área plantada, produção, valor e rendimento de 69 lavouras, além de
  rebanhos, leite, ovos e aquicultura, como o IBGE registra (PAM e PPM, 1974–2025). A
  porcentagem é sobre a **área rural** do município: o que sobra depois de tirar a área
  urbana, as terras indígenas e as unidades de conservação de proteção integral.
- **Satélite:** a mesma pergunta respondida pelo MapBiomas (coleção 11, 1985–2025). Ele separa
  soja, cana, arroz, algodão, café, citros e dendê.
- **Satélite × declarado:** onde o que se vê do alto diverge do que foi declarado.
- **Expansão:** que área virou lavoura em cada década, e se ela veio de floresta, de cerrado,
  de campo ou de pasto.
- **Glebas:** onde está o custeio agrícola financiado com recurso público, pelos polígonos do
  SICOR (Banco Central, 2012–2025), numa grade de ~30 km². É uma amostra, não o total.
- **Perdas:** onde e por quê a safra quebrou (seca, chuva, geada, granizo…), pelas perdas
  comprovadas no Proagro.
- **Garantia-Safra:** agricultores familiares do semiárido pagos a cada ano, e quanto receberam.
- **Calendário:** em que mês se planta cada cultura, quanto dura o ciclo e quanto é 2ª safra,
  pelas datas do custeio no SICOR.
- **Desmatamento:** PRODES por ano e em grade, alertas do DETER, embargos e multas do IBAMA.
- **Emissões:** gases da agropecuária e da mudança de uso da terra (SEEG).
- **Crédito rural:** todo o crédito com município no SICOR, por finalidade e programa, quem
  empresta, concentração, cooperativas, CAR; saldo nos bancos (ESTBAN) e BNDES.
- **Economia:** o valor adicionado da agropecuária no PIB de cada município.
- **Exportação:** a soja e a carne exportadas pelo município que produz (Trase) e o agro pela
  sede da empresa (Comex), com fertilizantes e defensivos importados.
- **Clima:** chuva, anomalia e temperatura (SISAM), as estações do INMET e as emergências
  reconhecidas pela Defesa Civil.
- **Fogo:** focos de calor do INPE e cicatriz de queimada.
- **Trabalho e estrutura:** emprego formal (RAIS, CAGED), estabelecimentos agropecuários
  (Censo 2022) e imóveis rurais (Receita).
- **Famílias do campo:** agricultores familiares, pescadores, extrativistas e assentados no
  CadÚnico, e o Seguro-Defeso.

O recorte vai por estado, bioma, região, semiárido ou Amazônia Legal, e qualquer medida pode
ser somada por região imediata, microrregião, mesorregião, estado ou grande região.

A ficha de cada município junta:
- a série histórica de qualquer lavoura do município (escolhida num select), declarada e
  vista do satélite;
- o que o satélite vê no município;
- de onde veio a lavoura nova;
- os rebanhos;
- o crédito e as perdas;
- o Garantia-Safra;
- o Cadastro Ambiental Rural: imóveis por tamanho, reserva legal, APP e vegetação nativa;
- e, sob demanda, crédito, economia, desmatamento, fogo, clima, calendário, exportação,
  emissões, trabalho e famílias.

## Como usar

- **Linha do tempo:** embaixo, com play e três velocidades. O chip com o ano, no canto de
  baixo, mostra e esconde a linha. As setas ← → também andam no tempo.
- **Mapa:** arraste para mover; roda do mouse, pinça ou duplo clique para aproximar. Clique
  num município para abrir a ficha; Esc fecha.
- **Painéis:** o de filtros, à esquerda, recolhe no botão do título; a legenda, à direita,
  recolhe no título dela. No celular, os dois são folhas que sobem de baixo.
- **Sobre:** o chip `sobre` explica a fonte que está na tela e o que ela não mostra.
- **Link:** o estado da tela fica na URL. Por exemplo,
  `index.html?c=soja&a=2010&mun=5107925` abre a soja de 2010 com a ficha de Sorriso (MT), e
  `index.html?a=1985&d=1` abre a lavoura principal de 1985.

A versão para a web fica em `site/` e é publicada em https://rafapolo.github.io/chao/: uma
página leve que baixa os dados aos poucos. O mapa aparece com a primeira etapa, a segunda
chega por trás, e o resto só quando um modo pede. Para vê-la localmente:
`bunx serve site`.

## Fontes

- **IBGE:** PAM, PPM, PEVS, PIB municipal, população, malha, setores de 2010, CNEFE.
- **MapBiomas.**
- **Banco Central:** SICOR, Proagro, ESTBAN, SCR. **BNDES.**
- **INPE:** PRODES, DETER, queimadas, SISAM. **INMET.** **Defesa Civil (S2ID).**
- **IBAMA:** embargos e autos. **INCRA:** assentamentos, SIGEF, SNCI.
- **CGU:** Garantia-Safra, Seguro-Defeso. **MDS:** CadÚnico. **MTE:** RAIS, CAGED.
- **Receita Federal:** CAFIR. **MDIC:** Comex Stat. **Trase.** **SEEG.**
- **Serviço Florestal Brasileiro:** SICAR. **FUNAI** e **MMA (CNUC).**

Todas vêm do espelho do projeto [rodado](https://rodado.xyz).

## Limites

- Abaixo do município, a página tem só a área não rural coberta em cinza e a grade das
  glebas. O número do IBGE não é espalhado sobre os pixels do satélite.
- De 1974 a 1987 a área é a **colhida**: a PAM só pergunta a plantada desde 1988.
- Municípios criados depois de 1974 recebem, antes de existir, a parte que lhes cabe do
  território de origem (área mínima comparável do IBGE).
- Células e municípios com menos de 5 glebas, perdas, operações de crédito ou pescadores
  ficam de fora, para não identificar pessoa ou propriedade.
- O crédito com município é só o de recurso controlado ou equalizado (cerca de um terço do
  total); a chuva por município do SISAM é estimativa de modelo e vai até 2019.

Como a página é gerada e testada: ver `CLAUDE.md`.
