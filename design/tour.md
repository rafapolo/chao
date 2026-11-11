# Tour: o roteiro

O tour é um passeio de cerca de 3 minutos pelo Chão, com quadro de cinema. Um ponteiro desenhado
clica nos controles de verdade (fonte, legenda, busca, linha do tempo), então o tour também
ensina a usar a página.

## Abrir e parar

- **Abrir.** Há três jeitos:
  - o chip **▶ tour**, embaixo à direita, ao lado de `sobre`;
  - `?tour=1`, que mostra um convite (**Começar o tour**) sobre o mapa. O clique começa o tour e
    libera o som, que o navegador não toca sem um gesto. Clicar fora ou Esc deixa só o mapa;
  - `&t=<segundos>` (por exemplo `?tour=1&t=90`), que começa perto desse ponto. As cenas
    anteriores rodam instantâneas e em silêncio, para deixar o estado certo.

  Depois de aberto, `tour` e `t` saem do endereço: recarregar abre o mapa, não o filme.
- **Parar.** **Esc**, **✕ esc** ou o voltar do navegador param o tour. O mapa fica onde a câmera
  estava, e voltam como eram antes: fonte, medida, culturas, ano, recorte, Soma ou Principal,
  ficha, painéis e linha do tempo.
- **Carga.** O tour usa blocos da 3ª etapa: `prodqv` (quantidade), `terra` (PRODES) e `fogo`.
  Eles só são pedidos no clique de começar, nunca numa visita comum, e o convite mostra a carga.

O código fica em `pipeline/template.html`, na seção `tour` (as cenas ficam em `cenas()`).
Para mudar algo, edite este arquivo e peça a mudança no código.

## Regras gerais

- **Quadro.**
  - Faixas pretas de cinema 2.39:1 (até 16% da tela cada).
  - Uma linha fina de progresso na borda da faixa de baixo, com o tempo que falta acima dela,
    à direita.
  - Painel, legenda, linha do tempo e ficha somem. Só reaparece o controle que a cena ensina.
- **Texto.**
  - Em português.
  - Uma legenda tem duas partes: um rótulo pequeno em cima (o *kicker*: lugar · anos · fonte) e
    a frase.
  - Cada legenda fica no mínimo 6 s na tela.
- **Números.**
  - São contados no navegador a partir dos blocos carregados, com os cortes de privacidade e a
    escala log, e arredondados.
  - A conferência de cada um está em [achados.md](achados.md). Nenhum está escrito à mão na
    legenda.
- **Câmera.**
  - O mapa é plano (canvas 2D): a câmera é centro e escala.
  - Cada voo afasta e aproxima, como um `flyTo` (interpolação de van Wijk e Nuij).
  - Durante a frase, o mapa desliza devagar (*deriva*).
  - Com `prefers-reduced-motion`, a câmera corta de plano em plano.
- **Ponteiro.**
  - Só em tela larga (acima de 760 px).
  - No celular o tour aplica a mesma escolha sem mostrar o clique e espera o mesmo tempo, então
    a duração não muda.
- **Linha do tempo.**
  - O tour toca os anos com o próprio relógio, não com o ▶ da página. O ponteiro clica no ▶,
    que vira ❚❚ enquanto os anos correm.
  - O relógio para no último ano da PAM (2024). Assim, a previsão do LSPA (2025–2026), que
    pinta a UF inteira de uma cor, nunca entra.

## Cenas

| # | tempo | câmera | o que acontece | kicker · frase |
|---|---|---|---|---|
| 0 | 0–14 s | Brasil inteiro, aproximando devagar | Lavoura principal em 2024; a legenda aparece | **Chão · 1974–2024** · *O que se planta e se cria em cada um dos {5.570} municípios do Brasil, ano a ano.* Aos 7 s: **lavoura principal · 2024** · *Cada município na cor da família de lavouras que ocupa mais área.* |
| 1 | 14–28 s | voa para o Sul (RS, PR, SC) | o ponteiro clica **Soma**, digita "soja" na busca da legenda e clica **Soja**; o ano vai a 1974 | **soja · 1974 (área colhida)** · *{54}% da soja do país estava no Rio Grande do Sul, e {26}% no Paraná.* |
| 2 | 28–45 s | desliza do Sul até o Centro-Oeste | a linha do tempo aparece, o ponteiro clica ▶, de 1974 a 2024 em 13 s | **linha do tempo** · *▶ toca os anos. Olhe a soja subir para o Cerrado.* Aos 10,5 s: **soja · 1974–2024** · *De {5,1} para {46,2} milhões de hectares. O centro da área andou {920} km para o norte.* |
| 3 | 45–58 s | voa até Sorriso | o ponteiro clica a busca de município e digita "Sorriso"; a ficha abre | **Sorriso (MT) · 2024** · *{600} mil hectares de soja: a maior área do país.* |
| 4 | 58–72 s | Sorriso e vizinhos | a ficha fecha; o ponteiro clica a fonte **Satélite**; de 1985 a 2024 em 7 s | **satélite · MapBiomas · 1985–2024** · *Do alto, a vegetação nativa de Sorriso foi de {692} para {238} mil hectares.* |
| 5 | 72–86 s | voa ao Matopiba (oeste da BA ao sul do MA) | volta a **Declarado**; de 1990 a 2024 em 6 s | **Matopiba · 1990–2024** · *Maranhão, Tocantins, Piauí e Bahia: de {0,4} para {5,8} milhões de hectares de soja.* |
| 6 | 86–102 s | Brasil inteiro, depois desliza para o Norte | busca "bovino" na legenda e clica **Bovino**; de 1974 a 2024 em 8 s | **rebanho bovino · 1974–2024** · *De {92} para {238} milhões de cabeças. O Norte tinha {4,6}% do gado; hoje tem {27}%.* |
| 7 | 102–118 s | voa a São Félix do Xingu (PA) | aos 7 s o ponteiro clica a aba **Terra** e a fonte **Desmatamento** (km² no ano, 2002) | **São Félix do Xingu (PA) · 2024** · *O maior rebanho do país: {2,5} milhões de cabeças.* Aos 7 s: **desmatamento · PRODES · 2002–2025** · *E o município que mais desmatou desde 2002: {12,9} mil km².* |
| 8 | 118–132 s | recua para a Amazônia e o Cerrado | de 2002 a 2025 em 8 s | **PRODES · todos os biomas** · *{73} mil km² desmatados em 2002, {20} mil em 2012, nova alta em 2022 e {15,6} mil em 2025, o menor da série.* |
| 9 | 132–146 s | o arco do desmatamento | aba **Clima**, fonte **Fogo**, ano 2024 | **fogo · INPE · 2024** · *{278} mil focos de calor, o maior número desde 2010. São Félix do Xingu de novo em primeiro: {7.356}.* |
| 10 | 146–160 s | voa ao Rio Grande do Sul | **Declarado**, soja, medida **Produção**; 2021, depois 2022 | **Rio Grande do Sul · 2021 → 2022** · *A seca levou {54}% da colheita de soja: de {20,4} para {9,4} milhões de toneladas.* |
| 11 | 160–172 s | Brasil inteiro | busca "arroz" na legenda e clica **Arroz**, medida Área; de 1980 a 2024 em 6 s | **arroz · 1980–2024** · *A área de arroz caiu de {6,2} para {1,6} milhões de hectares, e a colheita não caiu: cada hectare rende {4,2} vezes mais.* |
| 12 | 172–182 s | Brasil inteiro, afastando devagar | volta à **Principal** em 2024 | **Chão** · *Cinquenta anos de campo, município a município. Agora é com você: escolha uma cultura, um ano, um lugar.* |

## Som

A música é feita no navegador, com Web Audio e sem arquivo de som:
- um bordão grave, de duas serras desafinadas sob um filtro;
- cada cena desliza o bordão para a sua nota, e um acorde de seno sopra por cima;
- o filtro abre quando a câmera se aproxima e fecha quando se afasta;
- cada ano que a linha do tempo passa toca um pulso curto e grave.

Quem toca o tour até o fim ouve o som se apagar em 3 s; quem para no meio, em 0,6 s.

O botão **♪**, ao lado de **✕ esc**, liga e desliga o som. A escolha fica em `localStorage`
(`chao-som`), e o som começa ligado.

| cena | nota |
|---|---|
| 0, 12 | ré |
| 1, 2 | fá |
| 3, 4, 5 | lá |
| 6, 7 | sol |
| 8, 9 | dó (abaixo) |
| 10, 11 | mi |

## Fora do tour

- Crédito e imóvel do CAR: os cortes de privacidade pedem nota.
- Cana: cresce, mas no mesmo lugar.
- Lista Suja e Censo: fortes, mas de um ano só.
