# bragro: o que se planta onde no Brasil, ano a ano

Spec aprovada em conversa em 2026-10-21. Origem: `../rodado/tasks/plans/mapa_agricola.md`.
Base de arquitetura: `../rios-do-brasil`.

## Objetivo

Um mapa público e exploratório do que se planta onde, de 1974 a 2025. Tem uma
timeline, filtros por cultura, região, métrica e fonte, e desce o mais fino que
o espelho permite: do município para a área rural deduzida, e daí para as
glebas financiadas. O tom é o do rios-do-brasil: uma ficha lateral, conferências
impressas e números medidos, nunca arredondados para enfeite.

**Sucesso** é cumprir as quatro condições abaixo:

- Abrir `index.html` por `file://` e, sem rede:
  - escolher "soja";
  - apertar play;
  - ver a soja subir o Cerrado de 1974 a 2024.
- Clicar em Sorriso (MT) e ler, na ficha, a série da soja e de onde veio a
  lavoura.
- Alternar para "satélite × declarado" e ver onde o IBGE e o MapBiomas
  divergem.
- Ver hexágonos de glebas com cultura e safra sem que nenhum deles identifique
  uma propriedade.

## Restrições

- **HTML único e autocontido.**
  - Os dados vão embutidos em gzip+base64 e são abertos com
    `DecompressionStream`.
  - Nenhuma dependência roda na página publicada.
  - Abrir por `file://` é requisito.
  - Meta de tamanho: ≤ 25 MB.
- **Os dados moram em `../rodado`, no beelink.**
  - Acesso sempre por `ssh beelink '~/bin/duckdb -readonly -json ~/rodado/basedosdados.duckdb'`.
  - Nunca S3 e nunca BigQuery.
  - O repo não guarda dado bruto, só o que é gerado e pequeno.
- O **repositório é privado** por enquanto: git local, sem remoto.
- Tudo o que o usuário vê fica em pt-BR.
- Commits seguem o formato convencional.
- O pipeline é em Python + Polars. Os testes usam Bun + Playwright, só como
  ferramenta de desenvolvimento.

## Fontes (medidas em 2026-10-21)

| Fonte | Tabela | Grão | Período |
|---|---|---|---|
| IBGE PAM | `br_ibge_pam.lavoura_temporaria` (`area_plantada`) e `.lavoura_permanente` (`area_destinada_colheita`); ambas com `area_colhida`, `quantidade_produzida`, `rendimento_medio_producao`, `valor_producao` | município × produto × ano | 1974–2024; 33 + 38 produtos |
| MapBiomas | `br_mapbiomas_estatisticas.cobertura_municipio_classe` (`area_ha`, `id_classe`, `bioma`, `colecao`) + `.classe` + `.transicao_municipio_de_para_decenal` | município × classe × ano | 1985–2025 |
| geobr | `br_geobr_mapas`: `municipio`, `pegada_urbana`, `setor_censitario_2010` (`situacao_setor`), `terra_indigena`, `unidade_conservacao`, `bioma`, `uf` | polígono | estático |
| SICOR | `br_bcb_sicor.recurso_publico_gleba` (+ `proagro_rcp_gleba`) → `operacao` (`id_referencia_bacen`, `numero_ordem`, `ano_safra_emissao`, `id_empreendimento`) → `empreendimento` (`produto`) | polígono de gleba | a medir |

Escala conferida: soma nacional da PAM em 2024 dá soja 46,2 M ha, milho 21,4 M e
cana 10,1 M.

Armadilhas já registradas no rodado:

- `gotchas/br_bcb_sicor.yml`:
  - 2% das geometrias de gleba são nulas;
  - o par (`id_referencia_bacen`, `numero_ordem`) se repete no COP.
- A PAM não tem `.yml`. Armadilhas esperadas:
  - unidade das frutas muda em 2001;
  - moeda da época antes de 1994;
  - nulo × zero.

## Arquitetura

```
beelink (DuckDB) ──ssh──> pipeline/*.py (Polars) ──> pipeline/*.bin|json (gerados, gitignored)
                                                         │
                         pipeline/template.html ──monta_pagina.py──> index.html (único arquivo publicado)
```

### Pipeline (`pipeline/`)

| Script | Faz | Conferência impressa |
|---|---|---|
| `beelink.py` | `consulta(sql) -> pl.DataFrame` | sempre com `-readonly`; descarta o lixo do `.duckdbrc` antes do JSON |
| `baixa_malha.py` | busca município, pegada urbana, setores urbanos, TI, UC, UF e bioma; calcula **rural = município − urbano − setores urbanos − TI − UC de proteção integral**; simplifica (Douglas-Peucker, tolerância para o zoom máximo) e quantiza as coordenadas | área rural ≥ área agropecuária do MapBiomas (classe 14) no último ano, por município; lista as exceções |
| `baixa_pam.py` | busca as duas lavouras por município × produto × ano; mantém só as células não nulas; normaliza o nome do produto | soma nacional por produto e ano; soja em 2024 ≈ 46,2 M ha |
| `baixa_mapbiomas.py` | busca cobertura e transição só das classes agrícolas, pasto, silvicultura e mosaico | uma só `colecao`; soma por classe e ano |
| `baixa_glebas.py` | liga gleba → operação → empreendimento sem duplicar a chave; extrai o centroide; agrega em **H3 res 6** × produto × safra | células com < 5 glebas são descartadas, e o script imprime quantas caíram; área total das glebas por cultura e safra ÷ área da PAM |
| `correspondencia.yaml` | liga produto da PAM ↔ classe do MapBiomas (soja↔39, cana↔20, arroz↔40, algodão↔62, café↔46, laranja/limão/tangerina↔47; demais temporárias↔41, demais perenes↔48) e produto do SICOR ↔ produto da PAM | — |
| `monta_pagina.py` | serializa em arrays tipados (Float32/Uint16), comprime e preenche os marcadores do template | tamanho por bloco e tamanho total ≤ 25 MB |

### Formato embutido

Cada bloco ocupa um marcador `/*__NOME__*/` no template:

| Marcador | Conteúdo |
|---|---|
| `MALHA` | polígonos rurais quantizados; inclui `id_municipio`, nome, UF, bioma, ano de instalação e a área urbana e protegida recortada, desenhada em cinza |
| `PAM` | colunar: índice de município, índice de produto, ano − 1974, área, produção, valor, rendimento |
| `MAPB` | colunar: índice de município, classe, ano − 1985, `area_ha`; transição decenal à parte |
| `GLEBAS` | índice H3 (como 2 × Uint32), produto, safra, área, número de glebas |
| `FONTE` | fonte mono subconjunto, como no rios |

Orçamento de tamanho:

| Bloco | Estimativa |
|---|---|
| malha | 3–5 MB |
| PAM | 6–10 MB |
| MapBiomas | ~3 MB |
| glebas | 2–5 MB |
| índices | < 1 MB |

Se o total estourar 25 MB, o primeiro corte é a produção e o valor antes de
1994.

### Página (`pipeline/template.html`)

- Canvas 2D com projeção fixa, zoom e arrasto, como no rios-do-brasil.
- A camada de coroplético pinta o polígono **rural**. O recorte (urbano, TI, UC)
  vai em cinza neutro com rótulo na legenda.
- A camada de glebas desenha os hexágonos por cima, com cor da cultura e
  opacidade pela área. Só aparece a partir de um zoom mínimo.
- Município que não existia no ano escolhido fica hachurado como "não
  existia". A malha é a atual, sem estimativa.

## UX

- **Timeline** (rodapé):
  - slider de 1974 a 2025, play/pausa e velocidade;
  - abaixo do slider, uma faixa com a área nacional da seleção, que serve de
    minigráfico e de navegação (clicar leva ao ano).
  - Anos fora da fonte do modo escolhido ficam apagados: o MapBiomas começa em
    1985, a PAM vai até 2024 e as glebas cobrem só as safras que existem.
- **Painel lateral** (gaveta de baixo no celular):
  - **Cultura**: seleção múltipla com busca, mais a opção "cultura dominante",
    que pinta cada município pela cultura de maior área.
  - **Métrica**: área, produção, valor, rendimento, % da área rural e
    expansão (ganho de área de lavoura na década, vinda de floresta, savana ou
    pasto).
  - **Fonte / modo**:
    - Declarado (IBGE);
    - Satélite (MapBiomas): só as culturas com classe própria, as demais
      apagadas;
    - Satélite × declarado: razão divergente centrada em 1;
    - Glebas.
  - **Recorte**: UF, bioma, e busca de município por nome com voo até ele.
- **Ficha do município** (clique):
  - série por cultura, em pequenos múltiplos;
  - composição da área rural no ano;
  - transição decenal (de onde veio a lavoura);
  - IBGE × MapBiomas lado a lado;
  - as fontes nomeadas.
- **Estado na URL** (`?c=soja,milho&a=2010&m=area&f=pam&uf=MT&mun=5107925`),
  sincronizado com `replaceState`.
- **Visual**:
  - tema escuro por padrão (fundo `#121211`), com o claro também conferido;
  - cor por cultura em paleta categórica curta e sempre com rótulo; mais de 8
    culturas viram "outras";
  - rampa sequencial para magnitude e divergente para a razão.

## Erros e casos limite

- Bloco que não descomprime: a página mostra um aviso e não desenha pela metade.
- Cultura sem classe no MapBiomas no modo satélite: aparece em cinza, com a
  nota "o satélite não separa esta cultura".
- Valor monetário antes de 1994: a ficha avisa que está em moeda da época, e a
  métrica "valor" aparece apagada antes de 1994.

## Testes (`testes/`, Bun + Playwright, nos três motores)

- **Estrutura:** a página abre por `file://` sem nenhum pedido à rede, e todos os
  blocos descomprimem.
- **Filtros:** mudar cultura, ano, métrica e modo altera o desenho (hash do
  canvas) e a URL.
- **URL:** abrir com `?c=soja&a=2010&mun=5107925` restaura o estado e abre a
  ficha de Sorriso.
- **Dados:** a ficha de Sorriso mostra a soja de 2024 igual à PAM, com o valor
  gravado na fixture gerada pelo pipeline.
- **Celular:** o painel vira a gaveta, sem rolagem horizontal.
- **Privacidade:** nenhuma célula de gleba embutida tem menos de 5 glebas.

## Fora de escopo (v1)

- Raster do MapBiomas a 30 m e tiles.
- Polígono de gleba individual.
- SICAR, PPM e Garantia-Safra.
- Remoto no GitHub e deploy.

## Pendências medidas antes da implementação (passo 1 do plano)

1. Cobertura de `recurso_publico_gleba`: linhas, safras e fração da área da PAM
   por cultura. Isso decide se as glebas entram em todo o Brasil ou só como
   camada parcial com aviso.
2. Chave gleba → empreendimento: duplica? O produto vem como texto ou código?
3. `setor_censitario_2010` tem geometria? Existe o de 2022?
4. Tamanho real dos blocos depois da compressão, comparado ao orçamento.
5. Escrever as armadilhas novas em `../rodado/docs/context/gotchas/br_ibge_pam.yml` e
   `br_mapbiomas_estatisticas.yml`.
