# Imóvel rural: o que ficou de fora

Aberto em 2026-10-25. Continua o [`tasks/done/imovel.md`](done/imovel.md), que já levou o
cruzamento para o imóvel do CAR. O que rodou: `pipeline/baixa_imovel.py`, que gera os
intermediários em `beelink:~/bragro_tmp/imovel/` (3,7 GB) e devolve só somas por município.
Na página, é o modo "Imóvel (CAR)". Nada daqui bloqueia o que já está no ar.

Executado em 2026-10-25, no mesmo dia: o que deu para buscar entrou no rodado
(`scripts/scrap/poligonos_ambientais.sh`, `scripts/scrap/incra_poligonos.py`, gotchas
medidas) e o Chão passou a ler. O que ficou aberto está marcado `[ ]`, com o motivo; o que
depende de uma resposta sua está em [`decisoes_pendentes.md`](decisoes_pendentes.md).

## 1. Dados novos para buscar (no rodado, não no Chão)

Vale a regra do `../rodado/AGENTS.md`: cada fonte entra no espelho com as suas gotchas
medidas, e só depois o Chão lê.

- [x] **Polígonos do PRODES (todos os biomas) e do DETER** (TerraBrasilis, shapefile e WFS).
  - Antes o alerta inteiro ia para o imóvel que contém o centroide (`metodo = centroide`).
  - Agora é interseção de verdade, com a área repartida entre os imóveis.
  - A etapa `desmat` do `baixa_imovel.py` foi trocada.
  - **Feito:** `br_inpe_prodes_acumulado.desmatamento_poligono`, com 6.816.093 polígonos
    de 6 biomas. É a versão do catálogo de 2026: Amazônia e Cerrado v20261016, e o Cerrado
    já traz 2026. Do DETER, `br_inpe_deter.avisos_poligono` (699.077), com a chave de
    `avisos`.
  - **Medido:** do PRODES 2016–2025 (226 mil km²), 191 mil km² caem dentro de CAR (85%).
  - A série da página para no último ano que todos os biomas têm (2025).
- [ ] **MapBiomas Alerta** (API GraphQL): o alerta validado vem com a lista de CARs atingidos.
  - Serve para conferir o cruzamento próprio. Espera-se casamento alto na Amazônia e no Cerrado.
  - **Bloqueado:** a introspecção abre sem login, mas `alerts`, `downloadShapefile` e
    `ruralProperty` respondem "Token de acesso inválido". Precisa de conta cadastrada na
    plataforma.
- [x] **Polígonos do SIGEF, do SNCI e dos assentamentos** (Acervo Fundiário do INCRA, por UF).
  - Antes a parcela do SIGEF entrava pelo centroide.
  - **Feito:** `br_incra_acervo.{sigef,snci,assentamentos}_poligono`, pelo proxy BR. A etapa
    `incra` do `baixa_imovel.py` mede a cobertura do imóvel por parcelas do SIGEF (metade ou
    mais = "com parcela certificada") e conta os imóveis cujo ponto interno cai num
    assentamento.
  - **Medido:** 392.146 imóveis do CAR dentro de assentamento.
- [x] **Cadastro Nacional de Florestas Públicas** (Serviço Florestal Brasileiro): CAR sobre
  floresta pública não destinada.
  - **Feito:** `br_sfb_cnfp.florestas_publicas`, CNFP 2025 do portal ArcGIS do SFB. São
    48,1 mi ha no tipo B (não destinada).
  - **Medido:** 42,8 mi ha de CAR somados imóvel a imóvel. Limitada a 1 por gleba, a
    interseção dá no máximo 36,1 mi ha de floresta tocada (AM 24,2). A página avisa da
    sobreposição.
- [x] **Embargos do ICMBio e das secretarias estaduais** (SEMA-MT, SEMAS-PA): completar o
  embargo federal.
  - **ICMBio feito:** `br_icmbio_embargos.termo_embargo`, 14.806 feições de 6.398
    embargos, sem data de desembargo. Entra na etapa `embargo`; 3.818 embargos tocam um
    CAR.
  - **SEMAS-PA no espelho, fora da página:** `br_semas_pa_ldi.areas_embargadas`, a Lista
    de Desmatamento Ilegal (5.387 áreas, 550.692 ha, do download do portal da LDI). A fonte
    não tem data de embargo (`difisc_dat` é o ano do desmatamento), então a área não entra
    em "embargo vigente na emissão".
    - Usar como "desmatamento ilegal reconhecido" pede outra medida; fica para depois.
  - **SEMA-MT feita:** `br_sema_mt_embargos`, pelo WFS da SEMA com a authkey publicada na
    página de transparência do SIMGEO. São 20.192 áreas embargadas, sem data de desembargo,
    e entram na etapa `embargo`.
- [x] **Situação de análise do CAR e adesão ao PRA** (SICAR): separar o CAR só declarado do
  CAR analisado.
  - Mediu-se antes de buscar fora: `area_imovel.condicao` resolve a análise.
    - 79% dos imóveis estão "Aguardando analise".
    - 181 mi ha estão em condição "Analisado...".
  - Virou a medida "Área do CAR já analisada (%)".
  - A adesão ao PRA não está no espelho e não foi buscada.
- [x] **Raster do MapBiomas, 30 m** (fase 9 do plano de dados, ~800 MB por ano): uso do solo
  dentro do imóvel, ano a ano.
  - **Feito para 2016–2024** (decisão em `decisoes_pendentes.md`): `zonal.py` em
    `beelink:~/scrap_tmp/mapbiomas_raster/` e a etapa `mapbiomas` do `baixa_imovel.py`. São 4
    medidas na página: floresta, pastagem, soja e agropecuária dentro do CAR.

## 2. Cruzamentos que dá para fazer com o que já está no espelho

- [x] **Glebas do Proagro** (`proagro_rcp_gleba`) → imóvel, como a etapa `gleba` faz com o
  SICOR.
  - Lembrar que 2% das glebas não têm geometria convertida (gotcha
    `proagro_gleba_wkt_invalido`).
  - Medida candidata: perda comprovada em imóvel com desmatamento ou embargo.
  - **Feito:** 1.701.765 de 1.727.475 glebas caem num CAR. O Proagro virou o 3º método da
    ponte (`gleba_proagro`) e ligou mais 47.026 operações.
    - Antes, as perdas ligadas a imóvel eram 28% em 2016, 55% em 2017 e 84% em 2018.
  - Medida nova: "perda comprovada no Proagro em imóvel com desmatamento ou embargo (ha)",
    257 mil ha no total, com o mesmo corte de 5.
- [x] **Agregado por célula da grade** (0,05°, como glebas e perdas), além do município, com
  o mesmo corte de 5 operações e 5 imóveis. **Feito com a checagem de diferença** (ver
  `decisoes_pendentes.md`, item 1).
  - **Não feito, por privacidade:** a célula e o município publicados juntos permitem
    diferença. Uma célula cortada sai do total do município menos as células publicadas
    quando os imóveis do município caem em poucas células.
  - O corte de 5 por célula não basta. Precisa de uma regra complementar (cortar o
    município, ou só publicar a grade sem o município), e essa decisão é sua.
- [x] **Divergência código × gleba** (15,8% das operações que têm os dois): virar medida na
  página, ou ao menos ser estudada por UF e por safra.
  - **Estudada; não vira medida.**
  - Por safra: ~20% de 2018 a 2022, 13,8% em 2023, 6,3% em 2024, 4,7% em 2025.
  - Por UF: PA 40%, AC 40%, MT 38%, MA 33%; RS 11%, PR 10%, MS 9%.
  - O degrau de 2023 é o mesmo da "área maior que o imóvel": mudança de registro no
    SICOR, e não do campo. Gotcha `registro_muda_em_2023` no rodado.
- [x] **"Área financiada maior que o imóvel"** cai de 2023 em diante. Provavelmente é efeito da
  foto única do CAR: o imóvel desmembrado depois fica menor que a área que financiou.
  - Testar usando a foto do CAR mais próxima da safra: `area_imovel` tem 10 fotos, de
    2024-10 a 2025-10.
  - Se não resolver, tirar a medida.
  - **Testado e tirado.** Com a foto 2024-10-04, a queda é a mesma: 2,18% em 2019, 1,09% em
    2022, 0,17% em 2023, 0,05% em 2024. Não é efeito da foto, e a medida saiu da página.

## 3. Decisões que ficaram como estão

- A foto única do CAR (2025-10-15) vale para todas as safras, com aviso na nota. Revisitar se
  o espelho passar a ter fotos antigas do SICAR.
- Na página, só somas; nenhuma contagem de embargos ligada a crédito.
- O crédito por imóvel começa em 2016, porque o `id_car` vem vazio antes de 2018 e há poucas
  glebas antes de 2016.
- O PRODES entra de 2017 em diante, porque antes é bienal fora da Amazônia.
- O embargo do ICMBio vale da lavratura em diante: a fonte não publica desembargo.
