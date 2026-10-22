# Safra a Safra (bragro): o que falta para integrar todos os dados do tema

Aberto em 2026-10-22. O feito (fases 1 a 8, mais a medição da 9) está em
[`dados_faltantes_feito.md`](dados_faltantes_feito.md),
no `~/Projetos/chao`, já na `main` e publicado em https://rafapolo.github.io/chao/ (repositório `rafapolo/chao`, nome público "Chão").

O mecanismo para dado novo está pronto. Um `baixa_*.py` gera a extração com a conferência
dela. O bloco vai em `monta_pagina.py`, com `data-etapa="sob-demanda"` no template. O modo
entra em `MODOS` (com `sec` e `blocos`) e, se a medida for uma série município × ano, numa
entrada de `SERIES`, sem código novo de cálculo.

## Tabelas que ainda não entram

| Dataset ou tabela | Integração proposta |
|---|---|
| MapBiomas `transicao_uf_de_para_anual`/`quinquenal`, `cobertura_uf_classe`, `classe` | Faixa ano a ano da conversão com UF no recorte; conferência município × UF no pipeline; rótulos e níveis das classes vindos de `classe`. |
| SICOR `proagro_parcela`, `proagro_sumula_julgamento`, `proagro_complemento_*`, `dicionario` (eventos) | R$ indenizados e % negados no modo Perdas; trocar o `CASE` de eventos pelo dicionário. |
| Garantia-Safra `pagamento`, `favorecido` | Conferência contra `garantia_safra`; recorrência do agricultor pago, agregada. |
| SICAR `uso_restrito`, `servidao_administrativa`, `hidrografia`, `dicionario` | Linhas na ficha do CAR. |
| geobr `regiao_metropolitana_2017`, `concentracao_urbana`, `arranjo_populacional`, `area_risco_desastre`, `escola`, `estabelecimentos_saude` | Conferência da máscara urbana; camada de risco; serviços fora da área urbana na ficha. |
| `br_ana_outorgas.captacoes` | Vazão para irrigação por município (m³/h ÷ 3600), "água por ha de lavoura". |
| `br_mme_consumo_energia_eletrica.uf` | Consumo rural na faixa com UF no recorte. |
| `br_ibge_munic.meio_ambiente` | Conselho e licenciamento ambiental na ficha. |
| `br_cgu_beneficios_cidadao` | Conferência do Garantia-Safra; renda de transferência na ficha. |
| `br_ibge_censo_2022` (agregados por setor) | População rural; trocar a máscara urbana de 2010 pela de 2022. |
| `br_mte_listasuja`, `br_anp_precos_combustiveis`, `br_aneel_dadosabertos` | Trabalho escravo por UF; diesel na faixa; geração solar rural (medir antes). |
| `br_bcb_scrdata` por modalidade | Já entra como carteira e inadimplência por UF na ficha; falta a faixa. |

## Raster de 30 m (fase 9)

Medido: ~800 MB por ano (coleção 10), e cabe no beelink. Passos do plano original:
contar pixels por classe em células de 0,05°, repartir a área declarada, criar o modo "Grade
fina" e validar contra as glebas do SICOR.

## Antes do push

- Revisão de UX no celular em todos os modos novos.
- O `index.html` passou do orçamento (37,6 MB contra 25 MB). Decidir se o `index.html`
  autocontido leva tudo ou só as duas primeiras etapas.
