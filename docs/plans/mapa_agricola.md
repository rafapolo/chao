# Mapa agrícola: o que se planta onde, ano a ano

> **Virou o repositório `~/Projetos/chao` em 2026-10-21** (privado, git local, sem remoto),
> com spec própria em `docs/superpowers/specs/2026-10-21-bragro-design.md`. Lá o plano
> abaixo foi executado com estas mudanças: grade regular de 0,05° no lugar de H3; a área
> rural vira máscara desenhada por cima, e não polígono recortado; e entraram PPM, Proagro,
> Garantia-Safra e SICAR. As armadilhas medidas foram para `docs/context/gotchas/`
> (`br_ibge_pam`, `br_mapbiomas_estatisticas`, `br_cgu_garantia_safra`). Este arquivo fica
> como registro do plano original.

Aberto em 2026-10-21, a pedido. Só plano: nada construído. Revisto no mesmo
dia com três pedidos:

1. **timeline**: o mapa anda no tempo;
2. **o mais específico possível**: descer abaixo do município, cruzando com o
   satélite;
3. **deduzir a área rural** de cada município e só pôr lavoura lá.

## A ideia em uma frase

O IBGE diz **quanto** de cada cultura há em cada município. O MapBiomas diz
**onde dentro do município** há soja, cana, arroz, algodão, café, citros e
"outras lavouras". As glebas do SICOR dizem **onde exatamente** uma
cultura foi plantada numa safra (polígono por operação de crédito). A malha
do geobr diz **onde não pode haver lavoura** (mancha urbana, setor urbano, terra
indígena, UC de proteção integral, água). Juntas, as quatro dão um mapa
**dasimétrico**: o total do IBGE redistribuído só sobre as áreas onde o satélite
e as glebas dizem que há lavoura, dentro da área rural deduzida.

## Níveis de especificidade (do mais grosso ao mais fino)

| Nível | Grão | Fonte | Período | Cobre |
|---|---|---|---|---|
| N0 | município | PAM (`br_ibge_pam`) | 1974–2024 | 71 produtos, todos os municípios |
| N1 | município × classe | MapBiomas estatísticas (`cobertura_municipio_classe`, `area_ha`) | 1985–2025 | 9 classes agrícolas + pasto e silvicultura |
| N2 | área rural do município | geobr (`br_geobr_mapas`): município − `pegada_urbana` − setores `situacao_setor` urbanos − `terra_indigena` − `unidade_conservacao` (proteção integral) | estático (setores 2010/2022) | todos |
| N3 | polígono de gleba | SICOR `recurso_publico_gleba` (+ `proagro_rcp_gleba`, 1,76 M) → `operacao` → `empreendimento.produto`, `ano_safra_emissao` | safras com gleba georreferenciada (a medir: desde ~2016?) | só área financiada |
| N4 | pixel 30 m | raster do MapBiomas (Coleção 10, GeoTIFF anual) | 1985–2025 | **não está no espelho**: baixar à parte |

O mapa mostra o nível mais fino que existir em cada lugar e em cada ano, e diz
qual é.

## Timeline

- Eixo de **1974 a 2025**, um quadro por ano.
  - 1974–1984: só N0 (PAM), coroplético municipal.
  - 1985 em diante: N1/N4 (satélite), com a PAM redistribuída.
  - Safras com gleba: N3 por cima, polígono a polígono.
- **Malha que muda**: são 3.950 municípios em 1974 e 5.570 hoje. Usar
  `br_geobr_mapas.area_minima_comparavel_2010` (AMC) para que a série seja
  comparável, ou pintar cada ano na malha do próprio ano. **Decidir.**
- Animação + slider; clicar num município abre a série das culturas.
- Narrativas prontas: a soja subindo o Cerrado (MT, MATOPIBA), a cana em SP,
  o café migrando, o arroz no RS.

## Dedução da área rural (N2)

Para cada município:

```
área rural = polígono do município
           − pegada_urbana (mancha urbana)
           − setores censitários com situacao_setor urbana (2010; 2022 quando houver geometria)
           − terra_indigena, unidade_conservacao (proteção integral)
           − água, urbano e mineração do MapBiomas (no nível N4, se baixado)
```

Conferências:

- A área rural deduzida tem que ser ≥ à área agropecuária do MapBiomas
  (classe 14) no mesmo município. Se for menor, a dedução está tirando demais.
- Comparar com `arranjo_populacional.populacao_rural_2010` só como sanidade, não
  como área.

## Cruzamentos que dão especificidade

1. **PAM × MapBiomas por município e ano** para as culturas que existem nas
   duas: soja↔39, cana↔20, arroz↔40, algodão↔62, café↔46, laranja/limão/
   tangerina↔47. A razão satélite/declarado identifica onde confiar em cada um.
2. **PAM → pixels**: a área PAM de uma cultura sem classe própria (milho, feijão,
   trigo, mandioca…) é distribuída sobre a classe "41 outras temporárias", ou
   "21 mosaico" se faltar. Isso é uma **estimativa**, e o mapa precisa dizer.
   - Ponto em aberto: milho safrinha é plantado na mesma terra da soja e
     soma área sem ocupar terra nova. Tratar como camada sobreposta, não como
     concorrente.
3. **Glebas SICOR → rótulo de cultura**: cada polígono tem produto e safra.
   - Serve de **verdade de campo** para os pixels: que fração das glebas de
     "soja" cai em pixel MapBiomas 39?
   - Permite separar milho de feijão e de trigo onde o satélite só diz "outras".
4. **Transição MapBiomas** (`transicao_municipio_de_para_decenal`): de onde veio
   cada lavoura (floresta, savana, pasto), por década.

## Medido no beelink (2026-10-21)

- PAM: temporária 1974–2024, 33 produtos, 5.563 municípios, 183.579
  linhas/ano. Permanente 1974–2024, 38 produtos, com a coluna
  `area_destinada_colheita` em vez de `area_plantada`. Em 2024: soja
  46,2 M ha, milho 21,4 M, cana 10,1 M (bate com a CONAB).
- MapBiomas: `cobertura_municipio_classe` 1985–2025, colunas `ano,
  id_municipio, bioma, id_classe, classe_nivel_0..4, area_ha, colecao`.
  Legenda em `.classe`.
- Gotchas já escritas: `docs/context/gotchas/br_bcb_sicor.yml`
  - geometria da gleba: 2% nula, com `geometria_original` preenchida;
  - Proagro sem ano na fonte.

  E `br_sfb_sicar.yml`: `area_imovel` é série mensal, e a `app` tem área
  absurda.

## A conferir (o beelink caiu por SSH no meio da sondagem)

1. `recurso_publico_gleba`: quantas linhas, quais safras e quanto da área PAM
   ela cobre por cultura e ano. É o que decide se o N3 é camada de fundo ou
   amostra.
2. A chave `gleba → operacao → empreendimento`: o par
   `id_referencia_bacen, numero_ordem` duplica? A gotcha diz que duplica no
   COP. E o `produto` vem como texto ou como código?
3. A geometria dos setores censitários: o `setor_censitario_2010` do geobr tem
   polígono? Existe o de 2022?
4. O tamanho do raster MapBiomas Coleção 10 por ano (Brasil inteiro, 30 m),
   para saber se cabe no beelink. Alternativa: recortar só as classes agrícolas
   ou reamostrar para 250 m.
5. A PAM tem armadilhas próprias, ainda sem `gotchas/br_ibge_pam.yml`:
   - unidade das frutas muda em 2001 (mil frutos → t);
   - valor em moeda da época antes de 1994;
   - nulo × zero.

   O MapBiomas também não tem `.yml`: conferir se a coluna `colecao` mistura
   coleções.
6. Municípios que mudam de malha: AMC de 2010 × malha do ano.

## Passos

1. Fechar "A conferir" (consultas `-readonly`; extensão `spatial` do DuckDB para
   as geometrias).
2. **N2 primeiro**: área rural por município, uma vez, com as conferências
   acima → parquet com o polígono rural.
3. **N0+N1 por ano**: PAM e MapBiomas por município × cultura × ano, com a
   tabela de correspondência em YAML versionado.
4. **N3**: glebas com produto e safra, simplificadas para web e agregadas em
   grade (por exemplo hexágonos H3 res 7–8) para não mandar milhões de polígonos
   ao navegador.
5. **N4 (opcional)**: baixar o raster, recortar pelo rural, distribuir a PAM e
   gerar os tiles por ano.
6. Validação:
   - soma nacional por cultura e ano contra a PAM;
   - glebas × pixel (acurácia por cultura);
   - três municípios conhecidos: Sorriso-MT soja, Ribeirão Preto-SP cana,
     sul de MG café.
7. Página com a timeline. Vector tiles (PMTiles) por ano; a camada de grade
   N3/N4 em H3. Dark mode (fundo `#121211`), cor = cultura com rótulo, regra
   de CVD do atlas. A legenda diz qual nível N está sendo mostrado.
8. As gotchas novas vão para `docs/context/gotchas/br_ibge_pam.yml` e
   `br_mapbiomas_estatisticas.yml`.

Código novo de extração em Polars (ou Bun+TS no front); scripts em
`scripts/mapa_agricola/`.

## Decisões em aberto (suas)

- **Onde publicar**: `pages/` do rodado.xyz ou o DataViz Hub (`xyz`)?
- **Malha da timeline**: AMC (comparável, mais grossa) ou a malha de cada ano?
- **Raster MapBiomas (N4)**: baixar (disco) ou parar no N3 + grade H3?
- **Glebas (N3) no mapa público**: mostrar o polígono, ou só agregado em
  hexágono? A gleba liga a uma operação de crédito, e `recurso_publico_mutuario`
  tem CPF. Mesmo sem nome no mapa, o polígono identifica uma propriedade. O
  padrão sugerido é agregar.
