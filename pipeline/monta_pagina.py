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
produto × safra não entra — o teste testes/privacidade.test.ts confere.
"""
import base64
import gzip
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


def embute(nome, bloco):
    cru = bloco.bytes()
    gz = gzip.compress(cru, 9)
    b64 = base64.b64encode(gz).decode()
    print(f"  {nome:8s} {len(cru) / 1e6:6.1f} MB -> gz {len(gz) / 1e6:5.1f} -> b64 {len(b64) / 1e6:5.1f}")
    return b64


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
bm.add("k_mun", masc_idx["m"], "u16")
p = codifica_geo(bm, "k_", masc_idx["wkb"].to_list(), min_pts=4)
print(f"    máscara: {p:,} vértices".replace(",", "."))

# ---------- catálogo de itens ----------
prod = idx_mun(pl.read_parquet(D / "producao.parquet"))
GRUPOS = {"T": "Lavoura temporária", "P": "Lavoura permanente", "R": "Rebanho",
          "A": "Origem animal", "Q": "Aquicultura"}
UNID_A = {"Leite": "mil litros", "Ovos de codorna": "mil dúzias", "Ovos de galinha": "mil dúzias"}


def rotulo(cru):
    g, nome = cru.split("|", 1)
    curto = re.sub(r"\s*\(.*?\)\s*", " ", nome).replace("*", "").strip()
    curto = {"Café Total": "Café", "Cana-de-açúcar": "Cana-de-açúcar", "Suíno - total": "Suínos",
             "Galináceos - total": "Galináceos", "Bovino": "Bovinos", "Bubalino": "Bubalinos",
             "Equino": "Equinos", "Caprino": "Caprinos", "Ovino": "Ovinos"}.get(curto, curto)
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
ordem_g = {"T": 0, "P": 1, "R": 2, "A": 3, "Q": 4}
itens_cru = sorted(tot["item"].to_list(),
                   key=lambda c: (ordem_g[c[0]], -(tot.filter(pl.col("item") == c)["area"][0] or 0),
                                  -(tot.filter(pl.col("item") == c)["quantidade"][0] or 0)))
ITENS = [rotulo(c) for c in itens_cru]
IIDX = {it["cru"]: i for i, it in enumerate(ITENS)}

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
for col, nome in [("area", "area"), ("quantidade", "q"), ("valor", "v")]:
    bp.add(nome, log16(prod[col].to_numpy()), "u16")
bp.meta = {"delta": ["m", "a"]}
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
gm = idx_mun(pl.read_parquet(D / "glebas_mun.parquet"))
SICOR = (pl.concat([gc.select("produto", "glebas"), gm.select("produto", "glebas")])
         .group_by("produto").agg(pl.col("glebas").sum()).sort("glebas", descending=True)["produto"].to_list())
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
pm_ag = pm.group_by(["m", "evento", "safra"]).agg(pl.col("perdas").sum(), pl.col("area_ha").sum())

bc = Bloco()
gc = gc.with_columns(pl.col("produto").replace_strict(SIDX, return_dtype=pl.Int32).alias("p")).sort(["p", "safra"])
bc.add("g_i", gc["i"], "i16"); bc.add("g_j", gc["j"], "i16")
bc.add("g_p", gc["p"], "u16"); bc.add("g_s", gc["safra"] - 2000, "u8")
bc.add("g_n", gc["glebas"].clip(upper_bound=65535), "u16"); bc.add("g_area", log16(gc["area_ha"].to_numpy()), "u16")
gm = gm.with_columns(pl.col("produto").replace_strict(SIDX, return_dtype=pl.Int32).alias("p")).sort(["m", "p", "safra"])
bc.add("gm_m", gm["m"], "u16"); bc.add("gm_p", gm["p"], "u16"); bc.add("gm_s", gm["safra"] - 2000, "u8")
bc.add("gm_n", gm["glebas"].clip(upper_bound=65535), "u16"); bc.add("gm_area", log16(gm["area_ha"].to_numpy()), "u16")
pc = pc.with_columns(pl.col("evento").replace_strict(EIDX, return_dtype=pl.Int32).alias("e")).sort(["e", "safra"])
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
    "itens": ITENS, "mb": MB_CLASSES, "origens": ORIGENS, "sicor": SICOR, "eventos": EVENTOS,
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
(RAIZ / "testes" / "fixture.json").write_text(json.dumps(fix, ensure_ascii=False, indent=1))

# ---------- página ----------
print("embutindo")
tpl = (S / "template.html").read_text()
pagina = tpl.replace("/*__FONTE__*/", (S / "fonte_mono.txt").read_text().strip())
for marca, nome, bloco in [("MALHA", "malha", bm), ("PROD", "produção", bp), ("MAPB", "mapbiomas", bb),
                           ("CRED", "crédito", bc), ("CAD", "cadastros", bk)]:
    pagina = pagina.replace(f"/*__{marca}__*/", embute(nome, bloco))
out = RAIZ / "index.html"
out.write_text(pagina)
print(f"{out} — {out.stat().st_size / 1e6:.1f} MB")
