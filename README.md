# O que se planta onde

Um mapa que mostra, município a município, o que o Brasil planta e cria, de 1974 a 2025, e
como isso mudou. É uma página só, `index.html`, que abre sem internet: basta dar dois cliques
no arquivo.

## O que dá para ver

- **Declarado:** área plantada, produção, valor e rendimento de 69 lavouras, além de
  rebanhos, leite, ovos e aquicultura, como o IBGE registra (PAM e PPM, 1974–2025). A
  porcentagem é sobre a **área rural** do município: o que sobra depois de tirar a área
  urbana, as terras indígenas e as unidades de conservação de proteção integral.
- **Lavoura principal:** cada município na cor da cultura que ocupa mais área. As 11
  culturas que mais vencem têm cor própria. Na legenda, à direita, cada cultura liga e
  desliga (ou todas de uma vez): tire a soja e veja o que vem por baixo.
- **Satélite:** a mesma pergunta respondida pelo MapBiomas (coleção 11, 1985–2025). Ele separa
  soja, cana, arroz, algodão, café, citros e dendê.
- **Satélite × declarado:** onde o que se vê do alto diverge do que foi declarado.
- **Expansão:** que área virou lavoura em cada década, e se ela veio de floresta, de cerrado,
  de campo ou de pasto.
- **Glebas:** onde está o custeio agrícola financiado com recurso público, pelos polígonos do
  SICOR (Banco Central, 2012–2025), numa grade de ~30 km². É uma amostra, não o total.
- **Perdas:** onde e por quê a safra quebrou: seca, chuva, geada, granizo… pelas perdas
  comprovadas no Proagro.
- **Garantia-Safra:** agricultores familiares do semiárido pagos a cada ano.

A ficha de cada município junta:
- a série histórica de qualquer lavoura do município (escolhida num select), declarada e vista do satélite;
- o que o satélite vê no município;
- de onde veio a lavoura nova;
- os rebanhos;
- o crédito e as perdas;
- o Garantia-Safra;
- o Cadastro Ambiental Rural: imóveis por tamanho, reserva legal, APP e vegetação nativa.

O estado da tela fica na URL. Por exemplo, `index.html?c=soja&a=2010&mun=5107925` abre a soja
de 2010 com a ficha de Sorriso (MT).

## Fontes

- **IBGE:** PAM, PPM, malha municipal e setores censitários de 2010.
- **MapBiomas.**
- **Banco Central:** SICOR e Proagro.
- **CGU:** Garantia-Safra.
- **Serviço Florestal Brasileiro:** SICAR.
- **FUNAI** e **MMA (CNUC).**

Todas vêm do espelho do projeto [rodado](https://rodado.xyz).

Como a página é gerada e testada: ver `CLAUDE.md`.
