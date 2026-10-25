# Decisões pendentes (imóvel rural)

Aberto em 2026-10-25, ao executar o [`imovel_pendente.md`](imovel_pendente.md). Todos os itens
foram respondidos no mesmo dia; a decisão está marcada em cada um.

## 1. Agregado por célula da grade: qual regra de privacidade?

Publicar a célula (0,05°) junto com o município deixa recalcular por diferença o que o corte
de 5 escondeu. Isso acontece quando os imóveis do município caem em poucas células: a célula
cortada sai do total do município menos as células publicadas.

- [x] **Feito (2026-10-25), `baixa_imovel.py` etapa `grade`:** 332.665 células × ano, fechadas em 12 rodadas. As 21.929 violações que sobram são municípios sem nenhuma célula publicada, conferidos por asserção; ali o resto é o município inteiro, com menos de 5 operações, que já não é publicado. Na Amazônia a grade mostra pouco (2021: R$ 0,4 bi de R$ 12 bi). **Decidido: grade + município com checagem.** O resto do município (total menos as células publicadas) tem de dar 0 ou 5 ou mais operações e imóveis; se não der, corta-se a menor célula publicada até fechar. Uma asserção em `monta_pagina.py` confere.
- Opções que havia:
  - (a) publicar só a grade, sem o agregado por município;
  - (b) cortar também o município em que alguma célula foi cortada;
  - (c) não fazer a grade.

## 2. Raster do MapBiomas, 30 m: vale o custo?

O uso do solo dentro do imóvel, ano a ano, é a fase 9 do plano de dados. O custo:
- uns 800 MB por ano, cerca de 32 GB para 1985–2024;
- o recorte por 8 mi de polígonos do CAR no beelink.

- [x] **Decidido: 2016–2024.** São cerca de 7 GB no beelink; o zonal é feito por imóvel, e a página recebe só a área de pastagem, soja e floresta por município, com corte de 5.

## 3. MapBiomas Alerta: criar conta?

A API (`plataforma.alerta.mapbiomas.org/api/v2/graphql`) só entrega `alerts`,
`downloadShapefile` e `ruralProperty` com token de usuário cadastrado. Ela serviria para
conferir o cruzamento próprio de desmatamento × CAR.

- [x] **Decidido: desistir da fonte.** A conferência fica pelo PRODES e pelo DETER.

## 4. Embargos da SEMA-MT: pedir pela LAI?

Não há nada aberto:
- o GeoServer público (`geo.sema.mt.gov.br`) só tem mosaicos de imagem;
- uma busca não achou nenhum conjunto de embargos publicado.

- [x] **Decidido: raspar a consulta pública** do SIMCAR/SEMA-MT. Se ela não tiver polígono ou não abrir, volta para cá.

## 5. Lista de Desmatamento Ilegal do Pará: usar como?

A LDI já está no espelho (`br_semas_pa_ldi.areas_embargadas`), mas não entra na página.
Ela não tem data de embargo, então não serve para "embargo vigente na emissão".

- [x] **Feito (`ef4ac64`): 579 mil ha de CAR na LDI.** **Decidido: medida de retrato atual.** É a área do CAR atingida pela LDI (ha e %) por município, pela sobreposição dos polígonos, sem ligar a crédito.

## 6. Limpeza no beelink

Sobravam 13 GB de zips (a estimativa era 4 GB) das coletas de 2026-10-25, que já viraram parquet no espelho:
- `~/scrap_tmp/prodes_poligono/`
- `~/scrap_tmp/cnfp/`
- `~/scrap_tmp/ldi_pa/`

- [x] **Feito: apagados (13 GB).**

## 7. Commits

Nada foi commitado.
- No Chão: `baixa_imovel.py`, a montagem, o template, os testes e o CLAUDE.md.
- No rodado: as gotchas e os arquivos regenerados. Alguns arquivos gerados (`datasets.md`,
  `catalog.md`, páginas do MCP) já estavam modificados antes desta sessão e foram reescritos.

- [x] **Feito:** `a32a3ed` no Chão; `13e55a6` e `cc93df2` no rodado. No rodado foram só as gotchas e o teste: outra sessão estava mexendo nos mesmos arquivos gerados (`br_mma_cnuc`, `br_prf_infracoes`), que ficaram para ela.

## 8. Teste quebrado no rodado (não é deste trabalho)

`mcp/test_mcp_server.py::test_describe_table_gotchas_scoped_by_tabelas` espera o gotcha
`snapshot_mensal` de `br_me_cnpj`. Hoje o arquivo tem `so_o_ultimo_retrato`, e parece ter
mudado no commit `7f1c0a6` (2026-10-20); isso não foi conferido.

- [x] **Feito (`13e55a6`):** a renomeação foi de propósito (`59eb91e`, 2026-10-13).
