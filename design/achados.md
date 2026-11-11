# Achados para o tour

Pesquisa de 2026-11-11 sobre os parquets de `pipeline/dados/`, os mesmos que montam a página. O
roteiro (`tour.md`) sai daqui. Cada número tem três colunas:
- **fonte**: o arquivo do projeto;
- **esperado**: a ordem de grandeza que se esperava;
- **conferência**: uma segunda conta independente. É a magnitude do `CLAUDE.md` ou a cifra que o
  IBGE ou o INPE publicam. Nenhuma relê o mesmo parquet do mesmo jeito.

Os números das legendas são **contados no navegador**, a partir dos blocos que a página carrega.
- Os blocos têm o corte de privacidade e a escala log de 0,5%, então a legenda arredonda: um
  algarismo decimal em milhões, ou mil.
- A coluna "parquet" é a referência: o teste de fumaça confere que o navegador chega perto dela.

Ranqueados por força da história e confiança no número.

| # | achado | parquet | fonte | conferência |
|---|---|---|---|---|
| 1 | **A soja foi do Sul para o Centro-Oeste.** Em 1974, 54% da área estava no RS e 26% no PR. Em 2024 o MT tem 27% e o RS, 14%. O centro de gravidade da área subiu de 26,4° S para 18,1° S, uns 920 km para o norte. | RS 53,9%, PR 26,1% (1974); MT 26,8%, RS 14,5% (2024); centroide −26,41 → −18,13 | `producao` (PAM), área ponderada pela posição da sede | Soja 2024 = 46,2 M ha, a magnitude do `CLAUDE.md`. Que a fronteira andou para o MT é fato conhecido (Conab: o MT é o 1º produtor desde os anos 2000). |
| 2 | **Nove vezes mais soja.** De 5,1 M ha (1974, área colhida) para 46,2 M ha (2024, área plantada). Os municípios com soja passaram de 984 para 2.645. | 5,14 → 46,21 M ha; 984 → 2.645 | `producao` | 46,2 M ha bate com o `CLAUDE.md`. Até 1987 a PAM só tem área colhida, e a página avisa: o tour diz "colhida" na cena de 1974. |
| 3 | **Sorriso (MT), a maior área de soja do país.** São 600 mil ha em 2024. No satélite, a vegetação nativa caiu de 692 mil ha (1985) para 238 mil ha (2024), e a soja tomou 551 mil ha. | 600.000 ha (PAM); 692 → 238 mil ha de vegetação natural (MapBiomas) | `producao`, `mapbiomas` | As duas fontes são independentes e batem: 600 mil ha declarados contra 551 mil vistos do satélite. O `CLAUDE.md` já registra que a transição de Sorriso fica 2–11% acima da cobertura. |
| 4 | **O Matopiba.** MA, TO, PI e BA juntos foram de quase nada (0,4 M ha em 1990) para 5,8 M ha de soja em 2024. São Desidério e Formosa do Rio Preto, no oeste baiano, são o 2º e o 3º municípios do país em área de soja. | 0,41 → 5,78 M ha; 513 e 508 mil ha | `producao` | No MapBiomas, Formosa do Rio Preto tem 589 mil ha de soja em 2024 e São Desidério 521 mil: outra fonte, mesma ordem. |
| 5 | **O gado foi para o Norte.** O rebanho bovino passou de 92 M (1974) para 238 M (2024). A parte do Norte foi de 4,6% para 27,1%; a do Sudeste caiu de 32,9% para 15,8%. | 92,5 → 238,2 M; Norte 4,6 → 27,1% | `producao` (PPM) | 238 M bate com a magnitude do `CLAUDE.md`. |
| 6 | **São Félix do Xingu (PA), três primeiros lugares.** É o maior rebanho do país (2,5 M cabeças em 2024), o município que mais desmatou desde 2002 (12,9 mil km², PRODES) e o que mais queimou em 2024 (7.356 focos). No satélite, o pasto foi de 9 mil ha (1985) para 1,84 M ha (2024). | 2.519.911 cabeças; 12.878 km²; 7.356 focos; pasto 9 → 1.838 mil ha | `producao`, `prodes_mun`, `fogo_mun`, `mapbiomas` | Quatro fontes independentes (IBGE, INPE/PRODES, INPE/queimadas, MapBiomas) apontam o mesmo município. O maior rebanho é cifra conhecida da PPM. |
| 7 | **O desmatamento caiu e voltou.** PRODES, todos os biomas: 73 mil km² em 2002 e 76 mil em 2004, 20 mil em 2012, outra alta em 2022 (28 mil) e 15,6 mil em 2025, o menor da série. 2001 fica de fora, porque é inflado (ver `CLAUDE.md`). | 73,1 / 76,5 / 20,0 / 28,3 / 15,6 mil km² | `prodes_mun` | A faixa de 73–79 mil km² em 2002–2004 é a do `CLAUDE.md`. O INPE publicou 2025 como o menor da Amazônia e do Cerrado juntos. |
| 8 | **2024, o ano do fogo.** Foram 278 mil focos, o maior número desde 2010 (319 mil). Setembro sozinho teve 83 mil. | 278.341; 83.157 em setembro | `fogo_mun` | O INPE (BDQueimadas, satélite de referência) publicou cerca de 278 mil focos em 2024. 2026 é ano parcial e não entra. |
| 9 | **A seca de 2022 no RS.** A colheita de soja do estado caiu de 20,4 Mt (2021) para 9,4 Mt (2022): menos 54%. No Proagro do RS, a seca é o evento que mais aparece. | 20,42 → 9,37 Mt | `producao` (PAM, ano da colheita = safra 2021/22) | A Emater-RS e o IBGE publicaram uma quebra de cerca de 55% na soja gaúcha de 2022. O Proagro conta pela safra de emissão (2021 = 2021/22), então não é somado com a PAM. |
| 10 | **Menos arroz e feijão.** O arroz foi de 6,2 M ha (1980) para 1,6 M ha (2024). A colheita até subiu (de 9,8 para 10,7 Mt), porque o rendimento por hectare foi de 1,6 para 6,5 t: 4,2 vezes. O feijão foi de 4,6 M ha para 2,7 M ha. | 6,24 → 1,63 M ha; 9,78 → 10,67 Mt; 1,57 → 6,53 t/ha | `producao` | IBGE e Conab dão cerca de 1,6 M ha de arroz em 2023/24. |

## Fora do tour

- **Cana.** Foi de 2,1 para 10,1 M ha, mas fica no mesmo SP de sempre: a história é menos
  geográfica.
- **Café.** Sem quantidade antes de 2001.
- **Proagro.** Quase vazio antes de 2016, e as safras de crédito pedem explicação demais para
  3 minutos.
- **Crédito e imóvel do CAR.** São fortes, mas os cortes de privacidade e a amostra das glebas
  pedem nota de rodapé.
