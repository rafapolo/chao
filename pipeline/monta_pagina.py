#!/usr/bin/env python3
"""Lê os parquets de pipeline/dados/, codifica em blocos binários e escreve index.html.

Formato de cada bloco (um <script type="text/plain"> por bloco, gzip + base64):
  u32 tamanho do cabeçalho | cabeçalho JSON | bytes dos arrays
O cabeçalho diz, para cada array, tipo, tamanho e posição. Inteiros de mais de um
byte vão com os bytes em planos separados (todos os bytes baixos, depois os
altos): o gzip comprime muito melhor assim, porque os bytes altos de séries
parecidas se repetem. Valores de magnitude (área, produção, valor) vão em u16 na
escala log: código = round(ln(1 + v) · K) + 1, com K = 200 — passo de 0,5%, folga
de sobra para cor e para os números da ficha (que mostram 3 algarismos). Com
K = 2800 (0,04%) o bloco de produção passava de 21 MB em base64.

Privacidade: célula da grade com menos de MIN_CELULA glebas (ou perdas) por
produto × safra não entra, e o mesmo corte vale para o agregado por município —
o teste de privacidade em testes/mapa.test.ts confere os quatro.
"""
import base64
import gzip
import hashlib
import json
import re
import unicodedata
from pathlib import Path

import numpy as np
import polars as pl
import shapely

S = Path(__file__).parent
D = S / "dados"
RAIZ = S.parent

K_LOG = 200.0
Q = 2 ** 22          # quantização da coordenada de mundo (Mercator em [0,1]): ~9,5 m no equador
PASSO = 0.05         # grade das glebas, em graus (o mesmo de baixa_credito.py)
MIN_CELULA = 5
ANO0_PROD, ANO0_MB = 1974, 1985


# Toda ordenação desempata até o fim: a saída tem que ser a mesma byte a byte para
# os mesmos dados, ou o hash no nome dos blocos de site/ muda e o cache se perde.

# ---------- codificação ----------
class Bloco:
    def __init__(self):
        self.arrays, self.meta = [], {}

    def add(self, nome, arr, tipo):
        dt = {"u8": np.uint8, "i8": np.int8, "u16": np.uint16, "i16": np.int16,
              "u32": np.uint32, "i32": np.int32}[tipo]
        a = np.ascontiguousarray(np.asarray(arr).astype(dt))
        self.arrays.append((nome, tipo, a))

    def bytes(self):
        cab, corpo, off = {"arrays": {}, "meta": self.meta}, [], 0
        for nome, tipo, a in self.arrays:
            larg = a.dtype.itemsize
            planos = a.view(np.uint8).reshape(-1, larg).T.tobytes() if larg > 1 else a.tobytes()
            cab["arrays"][nome] = {"t": tipo, "n": int(a.size), "o": off}
            corpo.append(planos)
            off += len(planos)
        j = json.dumps(cab, ensure_ascii=False, separators=(",", ":")).encode()
        return len(j).to_bytes(4, "little") + j + b"".join(corpo)


def log16(v):
    v = np.nan_to_num(np.asarray(v, dtype=np.float64), nan=-1)
    out = np.where(v < 0, 0, np.round(np.log1p(np.maximum(v, 0)) * K_LOG) + 1)
    assert out.max() < 65535, "valor estoura a escala log"
    return out  # 0 = sem dado; código c > 0 decodifica como exp((c − 1)/K) − 1


def comprime(nome, bloco):
    cru = bloco.bytes()
    # mtime=0: o mesmo dado dá os mesmos bytes, e o nome com hash não muda à toa
    gz = gzip.compress(cru, 9, mtime=0)
    print(f"  {nome:9s} {len(cru) / 1e6:6.1f} MB -> gz {len(gz) / 1e6:5.1f}")
    return gz


def norm(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().upper()
    return re.sub(r"[^A-Z ]", " ", s).split()


# ---------- municípios ----------
malha = pl.read_parquet(D / "malha.parquet").sort("id_municipio")
masc = pl.read_parquet(D / "mascara.parquet")
bioma = pl.read_parquet(D / "bioma.parquet")
mun = (malha.join(masc.drop("wkb"), on="id_municipio", how="left")
       .join(bioma, on="id_municipio", how="left").fill_null(0))
IDS = mun["id_municipio"].to_list()
IDX = {m: i for i, m in enumerate(IDS)}
NMUN = len(IDS)


def idx_mun(df):
    """Troca id_municipio por índice; descarta (e conta) o que não está na malha."""
    fora = df.filter(~pl.col("id_municipio").is_in(IDS))
    if fora.height:
        print(f"    {fora.height} linhas de {fora['id_municipio'].n_unique()} códigos fora da malha descartadas")
    return (df.filter(pl.col("id_municipio").is_in(IDS))
              .with_columns(pl.col("id_municipio").replace_strict(IDX, return_dtype=pl.Int32).alias("m")))


# ---------- geometria ----------
def merc(lon, lat):
    s = np.sin(np.radians(lat))
    return (lon + 180) / 360, 0.5 - np.log((1 + s) / (1 - s)) / (4 * np.pi)


def aneis(geom):
    polys = getattr(geom, "geoms", [geom])
    for p in polys:
        if p.geom_type != "Polygon" or p.is_empty:
            continue
        yield np.asarray(p.exterior.coords)
        for r in p.interiors:
            yield np.asarray(r.coords)


def codifica_geo(bloco, prefixo, wkbs, min_pts=4):
    """Anéis por feição: contagem de anéis por feição, pontos por anel, primeiro
    ponto absoluto (i32) e deltas (i16). Aresta cujo delta não cabe em i16 é
    subdividida — acontece nas divisas retas da Amazônia."""
    n_aneis, n_pts, ini, deltas = [], [], [], []
    for w in wkbs:
        g = shapely.from_wkb(w) if w is not None else None
        cont = 0
        for anel in (aneis(g) if g is not None else []):
            if len(anel) < min_pts:
                continue
            x, y = merc(anel[:, 0], anel[:, 1])
            q = np.stack([np.round(x * Q), np.round(y * Q)], axis=1).astype(np.int64)
            seg = np.diff(q, axis=0)
            passos = np.abs(seg).max(axis=1) // 32000 + 1
            if passos.max() > 1:   # subdivide só as arestas longas
                novos = [q[:1]]
                for k, n in enumerate(passos):
                    s = np.arange(1, n + 1)[:, None]
                    novos.append(q[k] + seg[k] * s // n)
                q = np.concatenate(novos)
            arr = q
            ini.append(arr[0])
            d = np.diff(arr, axis=0)
            assert np.abs(d).max(initial=0) < 32768
            deltas.append(d)
            n_pts.append(len(d))
            cont += 1
        n_aneis.append(cont)
    bloco.add(prefixo + "aneis", n_aneis, "u16")
    bloco.add(prefixo + "pts", n_pts, "u32")
    bloco.add(prefixo + "ini", np.array(ini).ravel(), "i32")
    bloco.add(prefixo + "d", np.concatenate(deltas).ravel(), "i16")
    return sum(n_pts)


print("malha")
bm = Bloco()
p = codifica_geo(bm, "m_", malha["wkb"].to_list())
print(f"    municípios: {p:,} vértices".replace(",", "."))
masc_idx = masc.filter(pl.col("id_municipio").is_in(IDS)).with_columns(
    pl.col("id_municipio").replace_strict(IDX, return_dtype=pl.Int32).alias("m")).sort("m")
# grupo comparável (AMC) de cada município. Os cinco instalados em 2013, depois
# da AMC de 2010, vão para o grupo do município de origem.
ORIGEM_2013 = {"1504752": "1506807",   # Mojuí dos Campos <- Santarém
               "4212650": "4209409",   # Pescaria Brava <- Laguna
               "4220000": "4207007",   # Balneário Rincão <- Içara
               "4314548": "4302105",   # Pinto Bandeira <- Bento Gonçalves
               "5006275": "5003256"}   # Paraíso das Águas <- Costa Rica
amc = pl.read_parquet(D / "amc.parquet")
amc_de = dict(zip(amc["id_municipio"].to_list(), amc["id_amc"].to_list()))
for filho, pai in ORIGEM_2013.items():
    amc_de.setdefault(filho, amc_de[pai])
grupos = {g: i for i, g in enumerate(sorted(set(amc_de.values())))}
sem = [m for m in IDS if m not in amc_de]
assert not sem, f"municípios sem AMC: {sem}"
bm.add("amc", [grupos[amc_de[m]] for m in IDS], "u16")
bm.add("k_mun", masc_idx["m"], "u16")
p = codifica_geo(bm, "k_", masc_idx["wkb"].to_list(), min_pts=4)
print(f"    máscara: {p:,} vértices".replace(",", "."))
# divisas das UFs: sempre à vista, em traço fino, por isso na primeira etapa
regioes = pl.read_parquet(D / "regioes.parquet").sort(["tipo", "nome"])
ufs_geo = regioes.filter(pl.col("tipo") == "uf")
p = codifica_geo(bm, "u_", ufs_geo["wkb"].to_list())
print(f"    UFs: {p:,} vértices".replace(",", "."))

# divisão regional: pertença do município (semiárido, Amazônia Legal) e os
# agrupamentos do IBGE, como índice numa lista de nomes
div = pl.DataFrame({"id_municipio": IDS}).join(pl.read_parquet(D / "divisao.parquet"), on="id_municipio", how="left")
assert div["regiao"].null_count() == 0, "município da malha fora do diretório"
bm.add("semiarido", div["semiarido"].fill_null(False), "u8")
bm.add("amazonia", div["amazonia_legal"].fill_null(False), "u8")
DIVISOES = {}
for chave, col_id, col_nome in [("regiao", "regiao", "regiao"), ("meso", "id_mesorregiao", "nome_mesorregiao"),
                                ("micro", "id_microrregiao", "nome_microrregiao"),
                                ("intermediaria", "id_regiao_intermediaria", "nome_regiao_intermediaria"),
                                ("imediata", "id_regiao_imediata", "nome_regiao_imediata")]:
    pares = sorted(set(zip(div[col_id].to_list(), div[col_nome].to_list())))
    pos = {cod: i for i, (cod, _) in enumerate(pares)}
    bm.add("dv_" + chave, [pos[c] for c in div[col_id].to_list()], "u16")
    DIVISOES[chave] = [n for _, n in pares]

# contornos de região (3ª etapa, sob demanda): semiárido no modo Garantia-Safra,
# divisas de bioma com bioma no recorte, Amazônia Legal, regiões e país
print("contornos")
bt = Bloco()
outros = regioes.filter(pl.col("tipo") != "uf")


def sem_furos(w, min_km2=50):
    """Tira os furos pequenos (frestas da união de municípios); o contorno é só traço."""
    g = shapely.from_wkb(w)
    lim = min_km2 / 12300   # km² -> grau² aproximado na latitude do semiárido
    polys = [shapely.Polygon(p.exterior, [r for r in p.interiors if shapely.Polygon(r).area > lim])
             for p in getattr(g, "geoms", [g]) if p.geom_type == "Polygon" and p.area > lim]
    return shapely.to_wkb(shapely.MultiPolygon(polys))


outros = outros.with_columns(pl.col("wkb").map_elements(sem_furos, return_dtype=pl.Binary))
p = codifica_geo(bt, "r_", outros["wkb"].to_list())
bt.meta = {"regioes": [{"tipo": t, "nome": n} for t, n in zip(outros["tipo"].to_list(), outros["nome"].to_list())]}
print(f"    {outros.height} contornos, {p:,} vértices".replace(",", "."))

# ---------- catálogo de itens ----------
prod = idx_mun(pl.read_parquet(D / "producao.parquet"))
GRUPOS = {"T": "Lavoura temporária", "P": "Lavoura permanente", "R": "Rebanho",
          "A": "Origem animal", "Q": "Aquicultura", "E": "Extração vegetal", "S": "Silvicultura"}
UNID_A = {"Leite": "mil litros", "Ovos de codorna": "mil dúzias", "Ovos de galinha": "mil dúzias"}


def rotulo(cru):
    g, nome = cru.split("|", 1)
    if g in "ES":
        # PEVS: o nome leva a fonte, porque açaí, palmito, erva-mate, lenha e carvão
        # existem também na PAM ou nas duas tabelas da PEVS (e o slug da URL é o nome)
        un = "m³" if any(w in nome for w in ("Lenha", "Madeira", "madeira")) else "t"
        sufixo = " · extração" if g == "E" else " · silvicultura"
        return {"cru": cru, "nome": nome + sufixo, "grupo": GRUPOS[g], "g": g, "un": un, "area": False}
    curto = re.sub(r"\s*\(.*?\)\s*", " ", nome).replace("*", "").strip()
    curto = {"Café Total": "Café", "Cana-de-açúcar": "Cana-de-açúcar", "Suíno - total": "Suínos",
             "Galináceos - total": "Galináceos", "Bovino": "Bovinos", "Bubalino": "Bubalinos",
             "Equino": "Equinos", "Caprino": "Caprinos", "Ovino": "Ovinos"}.get(curto, curto)
    # as duas borrachas viram o mesmo nome sem o parêntese (e o mesmo slug na URL)
    curto = {"Borracha (látex coagulado)": "Borracha coagulada",
             "Borracha (látex líquido)": "Borracha líquida"}.get(nome, curto)
    if g in "TP":
        un = "mil frutos" if "*" in nome else "t"
    elif g == "R":
        un = "cabeças"
    elif g == "A":
        un = UNID_A.get(nome, "kg")
    else:
        un = "kg"
    return {"cru": cru, "nome": curto, "grupo": GRUPOS[g], "g": g, "un": un, "area": g in "TP"}


tot = (prod.group_by("item").agg(pl.col("area").sum(), pl.col("quantidade").sum())
       .sort(["area", "quantidade"], descending=True))
ordem_g = {"T": 0, "P": 1, "R": 2, "A": 3, "Q": 4, "E": 5, "S": 6}
itens_cru = sorted(tot["item"].to_list(),
                   key=lambda c: (ordem_g[c[0]], -(tot.filter(pl.col("item") == c)["area"][0] or 0),
                                  -(tot.filter(pl.col("item") == c)["quantidade"][0] or 0), c))
ITENS = [rotulo(c) for c in itens_cru]
IIDX = {it["cru"]: i for i, it in enumerate(ITENS)}
assert len(ITENS) < 256, "o índice do item vai em u8"
# rendimento por cabeça: o produto de origem animal e o rebanho que o produz
POR_CABECA = {"A|Leite": ("R|Vacas ordenhadas", "litros por vaca ordenhada", 1000),
              "A|Lã": ("R|Ovinos tosquiados", "kg por ovino tosquiado", 1)}
for cru, (reb, txt, fator) in POR_CABECA.items():
    ITENS[IIDX[cru]]["porcab"] = {"reb": IIDX[reb], "txt": txt, "fator": fator}

# correspondência com o MapBiomas (classe de satélite que vê a cultura)
MB_CLASSES = ["Soja", "Cana", "Arroz", "Algodão", "Outras temporárias", "Café", "Citros", "Dendê",
              "Outras perenes", "Silvicultura", "Pastagem", "Mosaico de usos", "Vegetação natural",
              "Água", "Área urbana", "Outros"]
MB_DE = {"Soja (em grão)": "Soja", "Cana-de-açúcar": "Cana", "Arroz (em casca)": "Arroz",
         "Algodão herbáceo (em caroço)": "Algodão", "Café (em grão) Total": "Café",
         "Laranja": "Citros", "Limão": "Citros", "Tangerina": "Citros", "Dendê (cacho de coco)": "Dendê"}
for it in ITENS:
    nome = it["cru"][2:]
    if it["g"] == "T":
        it["mb"] = MB_CLASSES.index(MB_DE.get(nome, "Outras temporárias"))
    elif it["g"] == "P":
        it["mb"] = MB_CLASSES.index(MB_DE.get(nome, "Outras perenes"))
    elif it["cru"] == "R|Bovino":
        it["mb"] = MB_CLASSES.index("Pastagem")

# famílias de lavoura: a legenda em árvore da "lavoura principal" e a cor do mapa.
# Toda lavoura (T|, P|) cai em exatamente uma; a ordem é a das cores --f1…--f10.
FAMILIAS = [
    ("Cereais", ["Milho (em grão)", "Arroz (em casca)", "Trigo (em grão)", "Sorgo (em grão)", "Aveia (em grão)",
                 "Cevada (em grão)", "Triticale (em grão)", "Centeio (em grão)"]),
    ("Oleaginosas", ["Soja (em grão)", "Mamona (baga)", "Amendoim (em casca)", "Dendê (cacho de coco)",
                     "Girassol (em grão)", "Linho (semente)", "Tungue (fruto seco)", "Azeitona"]),
    ("Cana-de-açúcar", ["Cana-de-açúcar"]),
    ("Feijões", ["Feijão (em grão)", "Fava (em grão)", "Ervilha (em grão)"]),
    ("Raízes e tubérculos", ["Mandioca", "Batata-inglesa", "Batata-doce"]),
    ("Café, cacau e estimulantes", ["Café (em grão) Total", "Cacau (em amêndoa)", "Fumo (em folha)",
                                    "Erva-mate (folha verde)", "Guaraná (semente)", "Chá-da-índia (folha verde)"]),
    ("Fibras", ["Algodão herbáceo (em caroço)", "Algodão arbóreo (em caroço)", "Sisal ou agave (fibra)",
                "Malva (fibra)", "Juta (fibra)", "Rami (fibra)"]),
    ("Frutas e castanhas", ["Laranja", "Banana (cacho)", "Castanha de caju", "Coco-da-baía*", "Melancia", "Uva",
                            "Caju", "Manga", "Abacaxi*", "Tangerina", "Limão", "Açaí", "Maracujá", "Maçã", "Mamão",
                            "Pêssego", "Abacate", "Melão", "Goiaba", "Caqui", "Noz (fruto seco)", "Figo", "Pera",
                            "Marmelo"]),
    ("Hortaliças e temperos", ["Cebola", "Tomate", "Alho", "Pimenta-do-reino", "Urucum (semente)", "Palmito"]),
    ("Borracha e forragem", ["Borracha (látex coagulado)", "Borracha (látex líquido)", "Cana para forragem",
                             "Alfafa fenada"]),
]
FAM_DE = {n: f for f, (_, ns) in enumerate(FAMILIAS) for n in ns}
for it in ITENS:
    if it["g"] in "TP":
        it["fam"] = FAM_DE[it["cru"][2:]]   # KeyError = lavoura nova sem família: inclua acima
FAM_META = [{"nome": nome, "itens": sorted((i for i, it in enumerate(ITENS) if it.get("fam") == f),
                                           key=lambda i: -(tot.filter(pl.col("item") == ITENS[i]["cru"])["area"][0] or 0))}
            for f, (nome, _) in enumerate(FAMILIAS)]
assert sum(len(f["itens"]) for f in FAM_META) == sum(it["g"] in "TP" for it in ITENS)

print("produção")
prod = prod.with_columns(pl.col("item").replace_strict(IIDX, return_dtype=pl.Int32).alias("i")) \
           .sort(["i", "m", "ano"])
bp = Bloco()
# Município e ano em diferença com a linha anterior (módulo 2^16): o município
# quase sempre repete e o ano quase sempre anda 1, e os planos de bytes viram
# corridas que o gzip esmaga. O JS desfaz com soma acumulada. Os VALORES ficam
# absolutos: em diferença o byte baixo vira ruído e o gzip piora (medido em
# 2026-10-21 com K=200: 10,7 MB absolutos contra 11,3 em diferença).
def dif(a):
    a = np.asarray(a, dtype=np.int64)
    return np.diff(a, prepend=0) % 65536
bp.add("i", prod["i"], "u8")
bp.add("m", dif(prod["m"]), "u16")
bp.add("a", dif(prod["ano"] - ANO0_PROD), "u16")
bp.add("area", log16(prod["area"].to_numpy()), "u16")
bp.meta = {"delta": ["m", "a"]}
# quantidade e valor num bloco à parte, nas mesmas linhas: o primeiro mapa só
# precisa da área, e na versão web esses ~9 MB chegam depois dele
bq = Bloco()
for col, nome in [("quantidade", "q"), ("valor", "v")]:
    bq.add(nome, log16(prod[col].to_numpy()), "u16")
# primeiro ano com dado = ano de instalação aproximado (antes dele: "não existia")
inst = prod.filter(pl.col("item").str.starts_with("R|")).group_by("m").agg(pl.col("ano").min())
inst_arr = np.full(NMUN, ANO0_PROD, dtype=np.int32)
inst_arr[inst["m"].to_numpy()] = inst["ano"].to_numpy()
anos_prod = (int(prod["ano"].min()), int(prod["ano"].max()))

print("mapbiomas")
mb = idx_mun(pl.read_parquet(D / "mapbiomas.parquet")).with_columns(
    pl.col("classe").replace_strict({c: i for i, c in enumerate(MB_CLASSES)}, return_dtype=pl.Int32).alias("c")
).sort(["c", "m", "ano"])
bb = Bloco()
bb.add("c", mb["c"], "u8")
bb.add("m", dif(mb["m"]), "u16")
bb.add("a", dif(mb["ano"] - ANO0_MB), "u16")
bb.add("area", log16(mb["area_ha"].to_numpy()), "u16")
bb.meta = {"delta": ["m", "a"]}
ORIGENS = ["Floresta", "Savana", "Campo e outras naturais", "Pastagem", "Outra lavoura ou mosaico", "Outros"]
tr = idx_mun(pl.read_parquet(D / "transicao.parquet")).with_columns(
    pl.col("de").replace_strict({c: i for i, c in enumerate(ORIGENS)}, return_dtype=pl.Int32).alias("d"),
    pl.col("para").replace_strict({c: i for i, c in enumerate(MB_CLASSES)}, return_dtype=pl.Int32).alias("p"),
).sort(["p", "decada_fim", "m"])
bb.add("t_dec", (tr["decada_fim"] - 2000) // 10, "u8")
bb.add("t_m", tr["m"], "u16")
bb.add("t_de", tr["d"], "u8")
bb.add("t_para", tr["p"], "u8")
bb.add("t_area", log16(tr["area_ha"].to_numpy()), "u16")
anos_mb = (int(mb["ano"].min()), int(mb["ano"].max()))

# ---------- crédito ----------
print("crédito")
gc = pl.read_parquet(D / "glebas_celula.parquet").filter(pl.col("glebas") >= MIN_CELULA)
# o corte de privacidade vale também para o agregado por município: um morango
# financiado sozinho num município identificaria a propriedade do mesmo jeito
gm = idx_mun(pl.read_parquet(D / "glebas_mun.parquet")).filter(pl.col("glebas") >= MIN_CELULA)
SICOR = (pl.concat([gc.select("produto", "glebas"), gm.select("produto", "glebas")])
         .group_by("produto").agg(pl.col("glebas").sum())
         .sort(["glebas", "produto"], descending=[True, False])["produto"].to_list())
SIDX = {p: i for i, p in enumerate(SICOR)}
# ligação item da PAM -> produto do SICOR, pela primeira palavra normalizada
for it in ITENS:
    if it["g"] not in "TP":
        continue
    w = norm(it["nome"])[0]
    cand = [p for p in SICOR if norm(p) and norm(p)[0] == w and "SILAGEM" not in p and "SEMENTE" not in p]
    if cand:
        it["sicor"] = SIDX[cand[0]]
liga = {it["nome"]: SICOR[it["sicor"]] for it in ITENS if "sicor" in it}
print(f"    {len(liga)} culturas ligadas a produto do SICOR, ex.: "
      + ", ".join(f"{k}→{v}" for k, v in list(liga.items())[:8]))

EVENTOS = ["Seca", "Chuva excessiva", "Geada", "Granizo", "Temperatura", "Vento", "Doença ou praga", "Outros"]
EIDX = {e: i for i, e in enumerate(EVENTOS)}
pc = pl.read_parquet(D / "proagro_celula.parquet").filter(pl.col("perdas") >= MIN_CELULA)
pm = idx_mun(pl.read_parquet(D / "proagro_mun.parquet"))
pm_ag = (pm.group_by(["m", "evento", "safra"]).agg(pl.col("perdas").sum(), pl.col("area_ha").sum())
         .filter(pl.col("perdas") >= MIN_CELULA))

bc = Bloco()
gc = gc.with_columns(pl.col("produto").replace_strict(SIDX, return_dtype=pl.Int32).alias("p")).sort(["p", "safra", "i", "j"])
bc.add("g_i", gc["i"], "i16"); bc.add("g_j", gc["j"], "i16")
bc.add("g_p", gc["p"], "u16"); bc.add("g_s", gc["safra"] - 2000, "u8")
bc.add("g_n", gc["glebas"].clip(upper_bound=65535), "u16"); bc.add("g_area", log16(gc["area_ha"].to_numpy()), "u16")
gm = gm.with_columns(pl.col("produto").replace_strict(SIDX, return_dtype=pl.Int32).alias("p")).sort(["m", "p", "safra"])
bc.add("gm_m", gm["m"], "u16"); bc.add("gm_p", gm["p"], "u16"); bc.add("gm_s", gm["safra"] - 2000, "u8")
bc.add("gm_n", gm["glebas"].clip(upper_bound=65535), "u16"); bc.add("gm_area", log16(gm["area_ha"].to_numpy()), "u16")
pc = pc.with_columns(pl.col("evento").replace_strict(EIDX, return_dtype=pl.Int32).alias("e")).sort(["e", "safra", "i", "j"])
bc.add("p_i", pc["i"], "i16"); bc.add("p_j", pc["j"], "i16")
bc.add("p_e", pc["e"], "u8"); bc.add("p_s", pc["safra"] - 2000, "u8")
bc.add("p_n", pc["perdas"].clip(upper_bound=65535), "u16"); bc.add("p_area", log16(pc["area_ha"].to_numpy()), "u16")
pm_ag = pm_ag.with_columns(pl.col("evento").replace_strict(EIDX, return_dtype=pl.Int32).alias("e")).sort(["m", "e", "safra"])
bc.add("pm_m", pm_ag["m"], "u16"); bc.add("pm_e", pm_ag["e"], "u8"); bc.add("pm_s", pm_ag["safra"] - 2000, "u8")
bc.add("pm_n", pm_ag["perdas"].clip(upper_bound=65535), "u16"); bc.add("pm_area", log16(pm_ag["area_ha"].to_numpy()), "u16")
safras = (int(min(gc["safra"].min(), pc["safra"].min())), int(max(gc["safra"].max(), pc["safra"].max())))

# ---------- cadastros ----------
print("cadastros")
gs = idx_mun(pl.read_parquet(D / "gsafra.parquet")).sort(["m", "ano"])
sc = idx_mun(pl.read_parquet(D / "sicar.parquet"))
bk = Bloco()
bk.add("gs_m", gs["m"], "u16"); bk.add("gs_a", gs["ano"] - 2000, "u8")
bk.add("gs_n", gs["agricultores"], "u32"); bk.add("gs_v", log16(gs["valor"].to_numpy()), "u16")
SICAR_COLS = ["imoveis", "imoveis_pequenos", "imoveis_medios", "imoveis_grandes", "area_cadastrada",
              "area_pequenos", "area_medios", "area_grandes", "area_assentamentos", "area_tradicionais",
              "reserva_legal", "app", "pousio", "vegetacao_nativa", "consolidada"]
for c in SICAR_COLS:
    arr = np.zeros(NMUN)
    arr[sc["m"].to_numpy()] = sc[c].fill_null(0).to_numpy()
    bk.add("car_" + c, np.round(arr), "u32")
anos_gs = (int(gs["ano"].min()), int(gs["ano"].max()))

# ---------- dinheiro (3ª etapa): crédito do SICOR, ESTBAN, BNDES, SCR e PIB ----------
print("crédito em R$")
FINALIDADES = ["Custeio", "Investimento", "Comercialização", "Industrialização"]
ATIVIDADES = ["Agrícola", "Pecuária"]
PROGRAMAS = ["Pronaf", "Pronamp", "Demais"]
cm = idx_mun(pl.read_parquet(D / "credito_mun.parquet"))
v0 = cm["valor"].sum()
# privacidade: combinação município × safra × finalidade × atividade × programa com
# menos de MIN_CELULA operações identificaria o valor emprestado a uma pessoa
cm = cm.filter(pl.col("operacoes") >= MIN_CELULA)
print(f"    corte de {MIN_CELULA} operações: fica {cm['valor'].sum() / v0 * 100:.1f}% do valor")
cm = cm.with_columns(pl.col("finalidade").replace_strict({f: i for i, f in enumerate(FINALIDADES)}, return_dtype=pl.Int32).alias("f"),
                     pl.col("atividade").replace_strict({f: i for i, f in enumerate(ATIVIDADES)}, return_dtype=pl.Int32).alias("t"),
                     pl.col("programa").replace_strict({f: i for i, f in enumerate(PROGRAMAS)}, return_dtype=pl.Int32).alias("p"),
                     ).sort(["m", "safra", "f", "t", "p"])
br = Bloco()
br.add("cr_m", dif(cm["m"]), "u16"); br.add("cr_s", cm["safra"] - 2000, "u8")
br.add("cr_f", cm["f"], "u8"); br.add("cr_t", cm["t"], "u8"); br.add("cr_p", cm["p"], "u8")
br.add("cr_n", cm["operacoes"], "u32"); br.add("cr_v", log16(cm["valor"].to_numpy()), "u16")
br.add("cr_a", log16(cm["area"].to_numpy()), "u16")

ci = idx_mun(pl.read_parquet(D / "credito_ind.parquet")).filter(pl.col("safra").is_between(2012, 2026)).sort(["m", "safra"])
# o que vem de tomador (contagem, PJ, concentração) só onde há ao menos MIN_CELULA tomadores
poucos = pl.col("tomadores").fill_null(0) < MIN_CELULA
ci = ci.with_columns([pl.when(poucos).then(None).otherwise(pl.col(c)).alias(c) for c in ("tomadores", "tomadores_pj", "top10")])
br.add("ci_m", ci["m"], "u16"); br.add("ci_s", ci["safra"] - 2000, "u8")
br.add("ci_ops", ci["ops"].fill_null(0), "u32")
for c in ("valor", "liberado", "desclass_valor", "via_coop_credito", "cooperado", "saldo"):
    br.add("ci_" + c, log16(ci[c].to_numpy()), "u16")
br.add("ci_desclass", ci["desclass_ops"].fill_null(0), "u32")
br.add("ci_tom", ci["tomadores"].fill_null(0), "u32"); br.add("ci_tompj", ci["tomadores_pj"].fill_null(0), "u32")
br.add("ci_top10", (ci["top10"].fill_null(-1) * 200 + 1).clip(lower_bound=0).round(), "u8")   # 0 = sem dado; passo de 0,5%
br.add("ci_car", ci["ops_car"].fill_null(0), "u32")

# quem empresta: as 5 maiores instituições por município, com MIN_CELULA operações
cf = (idx_mun(pl.read_parquet(D / "credito_if.parquet")).filter(pl.col("operacoes") >= MIN_CELULA)
      .group_by(["m", "instituicao", "segmento"]).agg(pl.col("operacoes").sum(), pl.col("valor").sum())
      .sort(["m", "valor", "instituicao"], descending=[False, True, False])
      .group_by("m", maintain_order=True).head(5))
INST = sorted(set(zip(cf["instituicao"].to_list(), cf["segmento"].to_list())))
IIDX_INST = {k: i for i, k in enumerate(INST)}
br.add("if_m", cf["m"], "u16")
br.add("if_k", [IIDX_INST[k] for k in zip(cf["instituicao"].to_list(), cf["segmento"].to_list())], "u16")
br.add("if_n", cf["operacoes"], "u32"); br.add("if_v", log16(cf["valor"].to_numpy()), "u16")

eb = idx_mun(pl.read_parquet(D / "estban.parquet")).sort(["m", "ano"])
br.add("eb_m", eb["m"], "u16"); br.add("eb_a", eb["ano"] - 1990, "u8"); br.add("eb_v", log16(eb["saldo"].to_numpy()), "u16")
bn = idx_mun(pl.read_parquet(D / "bndes.parquet")).sort(["m", "ano"])
br.add("bn_m", bn["m"], "u16"); br.add("bn_a", bn["ano"] - 1990, "u8"); br.add("bn_v", log16(bn["valor"].to_numpy()), "u16")

cu = pl.read_parquet(D / "credito_uf.parquet").filter(pl.col("safra").is_between(2012, 2025)).sort(["sigla_uf", "safra"])
scr = pl.read_parquet(D / "scr.parquet").sort(["sigla_uf", "ano"])
br.meta = {
    "delta": ["cr_m"],
    "finalidades": FINALIDADES, "atividades": ATIVIDADES, "programas": PROGRAMAS,
    "inst": [{"nome": n, "seg": sg} for n, sg in INST],
    "safras": [int(cm["safra"].min()), int(cm["safra"].max())],
    "estban": sorted(eb["ano"].unique().to_list()), "bndes": [int(bn["ano"].min()), int(bn["ano"].max())],
    # por UF: todo o crédito (com e sem município) e a carteira do SCR
    "uf": {u: {"safra": g["safra"].to_list(), "valor": g["valor"].round(0).to_list(), "valor_mun": g["valor_mun"].fill_null(0).round(0).to_list()}
           for (u,), g in cu.group_by(["sigla_uf"], maintain_order=True)},
    "scr": {u: {"ano": g["ano"].to_list(), "carteira": g["carteira"].round(0).to_list(), "inad": g["inadimplencia"].round(0).to_list()}
            for (u,), g in scr.group_by(["sigla_uf"], maintain_order=True)},
}

print("economia")
# 2022 e 2023 vêm só com o PIB total, sem o valor adicionado por setor (medido em 2026-10-22)
pb = idx_mun(pl.read_parquet(D / "pib.parquet")).filter(pl.col("va_agro").is_not_null()).sort(["m", "ano"])
be = Bloco()
be.add("m", pb["m"], "u16"); be.add("a", pb["ano"] - 1990, "u8")
for c in ("pib", "va", "va_agro"):
    be.add(c, log16(pb[c].to_numpy()), "u16")
be.meta = {"anos": [int(pb["ano"].min()), int(pb["ano"].max())]}

# ---------- metadados ----------
meta = {
    "mun": {
        "id": IDS, "nome": mun["nome"].to_list(), "uf": mun["sigla_uf"].to_list(),
        "bioma": mun["bioma"].cast(pl.Utf8).to_list(),
        "km2": mun["area_km2"].round(1).to_list(),
        "masc_km2": mun["area_mascara_km2"].round(1).to_list(),
        "urb_km2": mun["area_urbana_km2"].round(1).to_list(),
        "ti_km2": mun["area_ti_km2"].round(1).to_list(),
        "uc_km2": mun["area_uc_km2"].round(1).to_list(),
        "lon": mun["lon"].round(3).to_list(), "lat": mun["lat"].round(3).to_list(),
        "inst": inst_arr.tolist(),
    },
    "ufs": ufs_geo["nome"].to_list(), "divisoes": DIVISOES,
    "itens": ITENS, "familias": FAM_META, "mb": MB_CLASSES, "origens": ORIGENS, "sicor": SICOR, "eventos": EVENTOS,
    "sicar": SICAR_COLS,
    "anos": {"prod": anos_prod, "mb": anos_mb, "safra": safras, "gsafra": anos_gs,
             "trans": [2000, 2010, 2020]},
    "k": K_LOG, "q": Q, "passo": PASSO, "ano0": {"prod": ANO0_PROD, "mb": ANO0_MB},
    "min_celula": MIN_CELULA,
}
bm.meta = meta

# fixture para os testes: números da PAM conferidos contra o parquet
fix = {}
for mid, cru in [("5107925", "T|Soja (em grão)"), ("3543402", "T|Cana-de-açúcar")]:
    r = prod.filter((pl.col("id_municipio") == mid) & (pl.col("item") == cru) & (pl.col("ano") == 2024))
    fix[mid] = {"item": IIDX[cru], "ano": 2024, "area": float(r["area"][0])}
# leite por vaca em Castro (PR), a bacia leiteira; açaí extraído no maior
# município; Garantia-Safra pago em 2020 no país
def q_de(mid, cru, ano):
    r = prod.filter((pl.col("id_municipio") == mid) & (pl.col("item") == cru) & (pl.col("ano") == ano))
    return float(r["quantidade"][0])
fix["leite_castro"] = {"mun": "4104907", "ano": 2024,
                       "porcab": q_de("4104907", "A|Leite", 2024) * 1000 / q_de("4104907", "R|Vacas ordenhadas", 2024)}
acai = (prod.filter((pl.col("item") == "E|Açaí (fruto)") & (pl.col("ano") == 2024))
        .sort(["quantidade", "id_municipio"], descending=[True, False]).row(0, named=True))
fix["acai_ext"] = {"mun": acai["id_municipio"], "ano": 2024, "q": acai["quantidade"], "slug": "acai-fruto-extracao"}
fix["gs_2020"] = {"valor": float(gs.filter(pl.col("ano") == 2020)["valor"].sum()),
                  "agricultores": int(gs.filter(pl.col("ano") == 2020)["agricultores"].sum())}
fix["semiarido"] = int(div["semiarido"].sum())
cr = pl.read_parquet(D / "credito_mun.parquet")
fix["credito"] = {"mun": "5107925", "safra": 2023,
                  "valor": float(cr.filter((pl.col("id_municipio") == "5107925") & (pl.col("safra") == 2023)
                                           & (pl.col("operacoes") >= MIN_CELULA))["valor"].sum())}
fix["pib"] = {"mun": "5107925", "ano": 2021,
              "va_agro": float(pb.filter((pl.col("id_municipio") == "5107925") & (pl.col("ano") == 2021))["va_agro"][0])}
(RAIZ / "testes" / "fixture.json").write_text(json.dumps(fix, ensure_ascii=False, indent=1))

# ---------- página ----------
print("blocos")
tpl = (S / "template.html").read_text().replace("/*__FONTE__*/", (S / "fonte_mono.txt").read_text().strip())
BLOCOS = [("MALHA", "malha", bm), ("PROD", "prod", bp), ("PRODQV", "prodqv", bq), ("MAPB", "mapb", bb),
          ("CRED", "cred", bc), ("CAD", "cad", bk), ("CONTORNOS", "contornos", bt), ("CREDRS", "credrs", br),
          ("ECON", "econ", be)]
GZ = {nome: comprime(nome, bloco) for _, nome, bloco in BLOCOS}

# 1. index.html: arquivo único, abre por file:// (os blocos em base64 dentro dele)
pagina = tpl
for marca, nome, _ in BLOCOS:
    pagina = pagina.replace(f"/*__{marca}__*/", base64.b64encode(GZ[nome]).decode())
out = RAIZ / "index.html"
out.write_text(pagina)
print(f"{out} — {out.stat().st_size / 1e6:.1f} MB")

# 2. site/: a versão do GitHub Pages (publicada por .github/workflows/pages.yml). HTML leve e um arquivo gzip por bloco, com o
# hash do conteúdo no nome: dado que não mudou mantém o nome (e o cache do
# navegador), e só a primeira etapa (malha + área) é baixada antes do mapa.
# O GitHub Pages não comprime .bin de novo nem serve Content-Encoding pré-pronto,
# então o navegador baixa o gzip cru e o abre com DecompressionStream.
WEB = RAIZ / "site"
(WEB / "dados").mkdir(parents=True, exist_ok=True)
web, nomes = tpl, set()
for marca, nome, _ in BLOCOS:
    arq = f"{nome}.{hashlib.sha256(GZ[nome]).hexdigest()[:12]}.bin"
    nomes.add(arq)
    if not (WEB / "dados" / arq).exists():
        (WEB / "dados" / arq).write_bytes(GZ[nome])
    # o marcador fica entre a tag de abertura (que pode ter data-etapa) e o fechamento
    web = re.sub(rf'(<script id="b-{nome}" type="text/plain"[^>]*)>/\*__{marca}__\*/</script>',
                 rf'\1 data-src="dados/{arq}"></script>', web)
assert "/*__" not in web, "marcador sem bloco na versão web"
(WEB / "index.html").write_text(web)
(WEB / ".nojekyll").write_text("")
(WEB / "favicon.svg").write_text((RAIZ / "favicon.svg").read_text())
# blocos de montagens anteriores: gerados por este script, saem quando o hash muda
for velho in (WEB / "dados").glob("*.bin"):
    if velho.name not in nomes:
        velho.unlink()
tam = {a: (WEB / "dados" / a).stat().st_size for a in nomes}
etapa = {a: (1 if a.split(".")[0] in ("malha", "prod") else 3 if f'id="b-{a.split(".")[0]}" type="text/plain" data-etapa' in tpl else 2)
         for a in nomes}
por = [sum(v for a, v in tam.items() if etapa[a] == e) / 1e6 for e in (1, 2, 3)]
print(f"{WEB}/ — html {(WEB / 'index.html').stat().st_size / 1e3:.0f} kB, dados {sum(tam.values()) / 1e6:.1f} MB "
      f"(etapas: 1ª {por[0]:.1f} MB, 2ª {por[1]:.1f} MB, 3ª sob demanda {por[2]:.1f} MB)")
