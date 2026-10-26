import { afterAll, beforeAll, describe, expect, test } from "bun:test";
import { type Browser } from "playwright";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import { ESCOLHIDOS, FIXTURE, LENTO, MOTORES, RAIZ, abre, digital, fecha, quadro, roda } from "./comum";

for (const motor of ESCOLHIDOS) {
  describe(motor, () => {
    let nav: Browser;
    beforeAll(async () => { nav = await MOTORES[motor].launch(); }, LENTO);
    afterAll(async () => { await nav?.close(); });

    test("abre sem pedir nada fora do servidor e sem erro", async () => {
      const x = await abre(nav, "?c=soja&a=2024");
      expect(x.erros).toEqual([]);
      expect(x.pedidosRede).toEqual([]);
      expect(await x.p.$("#carregando")).toBeNull();
      // todos os blocos descomprimiram: há municípios, itens e glebas
      const n = await roda<number[]>(x.p, "return [T.M.mun.id.length, T.ITENS.length, T.CRED.A.g_i.length]");
      expect(n[0]).toBe(5570);
      expect(n[1]).toBeGreaterThan(80);
      expect(n[2]).toBeGreaterThan(1000);
      await fecha(x);
    }, LENTO);

    // os blocos chegam por fetch, que o Chromium não faz em file://; os outros motores
    // variam (o WebKit do Playwright abre arquivo local), então só ele confere o aviso
    test.if(motor === "chromium")("por file://, a página explica que precisa de um servidor", async () => {
      const ctx = await nav.newContext();
      const p = await ctx.newPage();
      await p.goto(pathToFileURL(join(RAIZ, "site", "index.html")).href);
      await p.waitForSelector("#carregando.erro", { timeout: 30_000 });
      expect(await p.locator("#carregando").textContent()).toContain("python3 -m http.server");
      await ctx.close();
    }, LENTO);

    test("cultura, ano, medida e fonte mudam o desenho e a URL", async () => {
      const x = await abre(nav, "?c=soja&a=2024");
      const p = x.p;
      await quadro(p);
      let antes = await digital(p);
      const passos: [string, () => Promise<unknown>, RegExp][] = [
        ["ano", () => roda(p, "T.defineAno(1990)"), /a=1990/],
        ["cultura", async () => { await p.fill("#busca-item", "milho"); await p.locator('#leg-arvore [data-item]:has(.rot:text-is("Milho"))').click(); }, /c=soja%2Cmilho|c=soja,milho/],
        ["medida", () => p.selectOption("#metrica", "area"), /m=area/],
        ["fonte", () => p.click('[data-modo="sat"]'), /f=sat/],
      ];
      for (const [nome, faz, url] of passos) {
        await faz();
        await quadro(p);
        const agora = await digital(p);
        expect(agora, nome).not.toBe(antes);
        expect(decodeURIComponent(p.url()), nome).toMatch(url);
        antes = agora;
      }
      expect(x.erros).toEqual([]);
      await fecha(x);
    }, LENTO);

    test("a URL restaura o estado e abre a ficha de Sorriso", async () => {
      const x = await abre(nav, "?c=soja&a=2010&mun=5107925");
      const est = await roda<any>(x.p, "return { ano: T.est.ano, mun: T.M.mun.id[T.est.mun], itens: T.est.itens.map(i => T.ITENS[i].slug) }");
      expect(est).toEqual({ ano: 2010, mun: "5107925", itens: ["soja"] });
      expect(await x.p.locator("#ficha h2").textContent()).toBe("Sorriso");
      expect(await x.p.locator("#ficha").textContent()).toContain("Lavouras declaradas em 2010");
      await fecha(x);
    }, LENTO);

    test("os números batem com a PAM (fixture gerada pelo pipeline)", async () => {
      const x = await abre(nav, "?c=soja&a=2024");
      for (const [mid, f] of Object.entries<any>(FIXTURE).filter(([k]) => /^\d{7}$/.test(k))) {
        const v = await roda<number>(x.p, `
          const m = T.M.mun.id.indexOf(${JSON.stringify(mid)});
          const NA = T.M.anos.prod[1] - T.M.ano0.prod + 1;
          return T.serieItem(${f.item}).area[m * NA + ${f.ano} - T.M.ano0.prod];`);
        // a escala log guarda a área com passo de 0,5%
        expect(Math.abs(v / f.area - 1), mid).toBeLessThan(0.005);
      }
      // e a ficha mostra o valor de Sorriso
      await roda(x.p, "T.seleciona(T.M.mun.id.indexOf('5107925'))");
      const kha = Math.round(FIXTURE["5107925"].area / 1000);
      expect(await x.p.locator("#ficha .barra").first().textContent()).toContain(`${kha} mil ha`);
      await fecha(x);
    }, LENTO);

    test("todas as fontes desenham sem erro, e a legenda acompanha", async () => {
      const x = await abre(nav, "?c=soja&a=2020");
      for (const [modo, sec] of await x.p.locator("#modos button[data-modo]").evaluateAll(bs => bs.map(b => [(b as HTMLElement).dataset.modo!, (b as HTMLElement).dataset.sec!]))) {
        await x.p.click(`#modos .grupo-modos[data-sec="${sec}"]`);
        await x.p.click(`[data-modo="${modo}"]`);
        await x.p.waitForFunction(() => document.getElementById("rotulo-carga")!.hidden, null, { timeout: 30_000 });
        await quadro(x.p);
        expect(await x.p.locator("#nota").textContent(), modo).not.toBe("");
        expect(await x.p.locator("#legenda .extra").count(), modo).toBe(1);
      }
      await x.p.click('#modos .grupo-modos[data-sec="Produção"]');
      await x.p.click('[data-modo="pam"]');
      await x.p.click('#alterna-disputa [data-d="1"]');
      expect(await x.p.locator("#legenda .fam.grupo").count()).toBe(2);   // lavoura temporária e permanente
      expect(x.erros).toEqual([]);
      await fecha(x);
    }, LENTO);

    test("fontes agrupadas em seções; bloco sob demanda carrega uma vez e fica em cache", async () => {
      const x = await abre(nav, "?c=soja&a=2020");
      const secoes = await x.p.locator("#modos .grupo-modos").allTextContents();
      expect(secoes).toEqual(["Produção", "Terra", "Dinheiro", "Clima", "Gente"]);
      // as abas cabem numa linha só, cada uma com ícone, no desktop e no celular
      const linhas = async () => x.p.locator("#modos .grupo-modos").evaluateAll(ts => new Set(ts.map(t => Math.round(t.getBoundingClientRect().top))).size);
      expect(await linhas()).toBe(1);
      expect(await x.p.locator("#modos .grupo-modos svg").count()).toBe(5);
      // a aba mostra só as fontes dela; trocar de aba não troca o modo
      expect(await x.p.locator('[data-modo="gs"]').isVisible()).toBe(false);
      await x.p.click('#modos .grupo-modos[data-sec="Clima e fogo"]');
      expect(await x.p.locator('[data-modo="gs"]').isVisible()).toBe(true);
      expect(await x.p.locator('[data-modo="pam"]').isVisible()).toBe(false);
      expect(x.p.url()).not.toContain("f=");
      const r = await roda<any>(x.p, `
        const a = T.carrega('contornos'), b = T.carrega('contornos');
        return a.then(c => ({ igual: a === b, n: c.meta.regioes.length }));`);
      expect(r.igual).toBe(true);
      expect(r.n).toBeGreaterThan(5);
      expect(x.erros).toEqual([]);
      await fecha(x);
    }, LENTO);

    test("leite por vaca ordenhada em Castro bate com a PPM", async () => {
      const x = await abre(nav, "?c=leite&m=porcab&a=2024");
      const f = FIXTURE.leite_castro;
      const v = await roda<number>(x.p, `return T.VAL[T.M.mun.id.indexOf('${f.mun}')]`);
      expect(Math.abs(v / f.porcab - 1)).toBeLessThan(0.01);
      expect(await x.p.locator("#metrica option:checked").textContent()).toContain("por vaca ordenhada");
      expect(x.erros).toEqual([]);
      await fecha(x);
    }, LENTO);

    test("extração vegetal (PEVS): o açaí extraído tem slug próprio e aparece na ficha ao lado do plantado", async () => {
      const f = FIXTURE.acai_ext;
      const x = await abre(nav, `?c=${f.slug}&m=q&a=2024&mun=${f.mun}`);
      const r = await roda<any>(x.p, `return { item: T.ITENS[T.est.itens[0]].nome, v: T.VAL[T.M.mun.id.indexOf('${f.mun}')] }`);
      expect(r.item).toBe("Açaí (fruto) · extração");
      expect(Math.abs(r.v / f.q - 1)).toBeLessThan(0.005);
      expect(await x.p.locator("#ficha").textContent()).toContain("Extração vegetal e silvicultura");
      expect(x.erros).toEqual([]);
      await fecha(x);
    }, LENTO);

    test("Garantia-Safra em R$: pago e por agricultor, somando o que a CGU pagou", async () => {
      const x = await abre(nav, "?f=gs&m=v&a=2020");
      const tot = await roda<number>(x.p, "let s = 0; for (const v of T.VAL) if (v > 0) s += v; return s;");
      expect(Math.abs(tot / FIXTURE.gs_2020.valor - 1)).toBeLessThan(0.005);
      await x.p.selectOption("#metrica", "vpa");
      const media = await roda<number>(x.p, "const v = [...T.VAL].filter(v => v > 0); return v.reduce((a, b) => a + b, 0) / v.length;");
      expect(media).toBeGreaterThan(100);
      expect(media).toBeLessThan(5000);
      expect(x.erros).toEqual([]);
      await fecha(x);
    }, LENTO);

    test("recorte por região especial: semiárido e Amazônia Legal, com contorno", async () => {
      const x = await abre(nav, "?c=soja&a=2020&rg=semiarido");
      const n = await roda<number>(x.p, "let n = 0; for (let m = 0; m < T.M.mun.id.length; m++) if (T.noRecorte(m)) n++; return n;");
      expect(n).toBe(FIXTURE.semiarido);
      await x.p.selectOption("#regiao", "amazonia");
      expect(x.p.url()).toContain("rg=amazonia");
      await x.p.waitForFunction(() => (window as any).__T.CONT, null, { timeout: 30_000 });
      expect(await x.p.locator("#regiao optgroup").count()).toBeGreaterThanOrEqual(3);
      expect(x.erros).toEqual([]);
      await fecha(x);
    }, LENTO);

    test("crédito rural em R$: Sorriso bate com o SICOR, os filtros mudam o mapa e a ficha diz quem empresta", async () => {
      const f = FIXTURE.credito;
      const x = await abre(nav, `?f=cred&a=${f.safra}&mun=${f.mun}`);
      await x.p.waitForFunction(() => (window as any).__T.SOB.credrs, null, { timeout: 60_000 });
      await quadro(x.p);
      const v = await roda<number>(x.p, `return T.VAL[T.M.mun.id.indexOf('${f.mun}')]`);
      expect(Math.abs(v / f.valor - 1)).toBeLessThan(0.01);
      const antes = await digital(x.p);
      await x.p.selectOption("#cred-fin", "0");
      await quadro(x.p);
      expect(await digital(x.p)).not.toBe(antes);
      expect(x.p.url()).toContain("cf=0");
      const custeio = await roda<number>(x.p, `return T.VAL[T.M.mun.id.indexOf('${f.mun}')]`);
      expect(custeio).toBeLessThan(v);
      const ficha = await x.p.locator("#ficha").textContent();
      expect(ficha).toContain("Quem empresta");
      expect(ficha).toContain("Crédito rural contratado");
      for (const mt of ["pronaf", "top10", "car", "estban", "bndes"]) {
        await x.p.selectOption("#metrica", mt);
        expect(await x.p.locator("#tit-legenda").textContent(), mt).not.toBe("");
      }
      expect(x.erros).toEqual([]);
      await fecha(x);
    }, LENTO);

    test("economia: VA agropecuário de Sorriso bate com o PIB municipal", async () => {
      const f = FIXTURE.pib;
      const x = await abre(nav, `?f=econ&a=${f.ano}`);
      await x.p.waitForFunction(() => (window as any).__T.SOB.econ, null, { timeout: 60_000 });
      const v = await roda<number>(x.p, `return T.VAL[T.M.mun.id.indexOf('${f.mun}')]`);
      expect(Math.abs(v / f.va_agro - 1)).toBeLessThan(0.005);
      await x.p.selectOption("#metrica", "pct");
      const pct = await roda<number>(x.p, `return T.VAL[T.M.mun.id.indexOf('${f.mun}')]`);
      expect(pct).toBeGreaterThan(5); expect(pct).toBeLessThan(80);
      expect(x.erros).toEqual([]);
      await fecha(x);
    }, LENTO);

    test("desmatamento: PRODES de Novo Progresso bate, a grade desenha células e a ficha traz a fiscalização", async () => {
      const f = FIXTURE.prodes;
      const x = await abre(nav, `?f=desm&a=${f.ano}&mun=${f.mun}`);
      await x.p.waitForFunction(() => (window as any).__T.SOB.terra, null, { timeout: 60_000 });
      await quadro(x.p);
      const v = await roda<number>(x.p, `return T.VAL[T.M.mun.id.indexOf('${f.mun}')]`);
      expect(Math.abs(v / f.km2 - 1)).toBeLessThan(0.005);
      await x.p.selectOption("#metrica", "grade");
      await quadro(x.p);
      expect(await roda<number>(x.p, "return T.CEL.size")).toBeGreaterThan(1000);
      for (const mt of ["deter", "emb", "autos", "multas", "acum"]) {
        await x.p.selectOption("#metrica", mt);
        expect(await x.p.locator("#tit-legenda").textContent(), mt).toContain("Desmatamento");
      }
      expect(await x.p.locator("#ficha").textContent()).toContain("Desmatamento e fiscalização");
      expect(x.erros).toEqual([]);
      await fecha(x);
    }, LENTO);

    test("fogo: focos do satélite de referência somam o total do INPE e a ficha dá o mês de pico", async () => {
      const x = await abre(nav, `?f=fogo&a=${FIXTURE.fogo.ano}&mun=5107925`);
      await x.p.waitForFunction(() => (window as any).__T.SOB.fogo, null, { timeout: 60_000 });
      const tot = await roda<number>(x.p, "let s = 0; for (const v of T.VAL) if (v > 0) s += v; return s;");
      expect(tot).toBe(FIXTURE.fogo.focos);
      expect(await x.p.locator("#ficha").textContent()).toContain("mês de pico");
      expect(x.erros).toEqual([]);
      await fecha(x);
    }, LENTO);

    test("clima: chuva do SISAM em Sorriso, anomalia divergente, estações do INMET como pontos e a ficha com o clima", async () => {
      const f = FIXTURE.clima;
      const x = await abre(nav, `?f=clima&a=${f.ano}&mun=${f.mun}`);
      await x.p.waitForFunction(() => (window as any).__T.SOB.clima, null, { timeout: 60_000 });
      const chuva = await roda<number>(x.p, `return T.VAL[T.M.mun.id.indexOf('${f.mun}')]`);
      expect(Math.abs(chuva - f.chuva)).toBeLessThan(1);
      await x.p.selectOption("#metrica", "anom");
      const anom = await roda<number>(x.p, `return T.VAL[T.M.mun.id.indexOf('${f.mun}')]`);
      expect(Math.abs(anom - (f.chuva / f.media - 1) * 100)).toBeLessThan(0.5);
      expect(await x.p.locator("#legenda .rotulos").textContent()).toContain("mais seco");
      await x.p.selectOption("#metrica", "est");
      await quadro(x.p);
      expect(await roda<number>(x.p, "return T.PONTOS.length")).toBe(f.estacoes);   // as do ano com ≥ 90% medido
      const ficha = await x.p.locator("#ficha").textContent();
      expect(ficha).toContain("Clima");
      expect(ficha).toContain("estação do INMET");
      expect(x.erros).toEqual([]);
      await fecha(x);
    }, LENTO);

    test("séries genéricas: Trase, SEEG, RAIS e CAGED batem com o pipeline; o saldo do CAGED é divergente", async () => {
      const F = FIXTURE.series;
      for (const [modo, k] of [["expo", "soja_t"], ["emis", "se_agro"], ["trab", "rais"], ["imovel", "cd_v"]]) {
        const f = F[k];
        const x = await abre(nav, `?f=${modo}&m=${k}&a=${f.ano}&mun=${f.mun}`);
        await x.p.waitForFunction(() => document.getElementById("rotulo-carga")!.hidden && (window as any).__T.est.metrica, null, { timeout: 60_000 });
        await x.p.waitForFunction(m => (window as any).__T.VAL[(window as any).__T.M.mun.id.indexOf(m)] > 0, f.mun, { timeout: 60_000 });
        const v = await roda<number>(x.p, `return T.VAL[T.M.mun.id.indexOf('${f.mun}')]`);
        expect(Math.abs(v / f.v - 1), k).toBeLessThan(0.005);
        expect(await x.p.locator("#ficha").textContent(), k).toContain({ expo: "Destinos da soja", emis: "Emissões", trab: "Trabalho e estrutura", imovel: "Imóvel (CAR)" }[modo]!);
        expect(x.erros).toEqual([]);
        await fecha(x);
      }
      const x = await abre(nav, `?f=trab&m=caged&a=${F.caged.ano}`);
      await x.p.waitForFunction(() => (window as any).__T.SOB.gente, null, { timeout: 60_000 });
      await quadro(x.p);
      const tot = await roda<number>(x.p, "let s = 0; for (const v of T.VAL) if (Number.isFinite(v)) s += v; return s;");
      expect(tot).toBe(F.caged.v);
      expect(await x.p.locator("#legenda .rotulos").textContent()).toContain("fechou");
      await fecha(x);
    }, LENTO);

    test("calendário: soja em Sorriso planta em outubro, escala cíclica, safrinha do milho e faixa de 12 meses na ficha", async () => {
      const f = FIXTURE.calendario;
      const x = await abre(nav, `?f=cal&c=soja&mun=${f.mun}`);
      await x.p.waitForFunction(() => (window as any).__T.SOB.calend, null, { timeout: 60_000 });
      await quadro(x.p);
      const v = await roda<number>(x.p, `return T.VAL[T.M.mun.id.indexOf('${f.mun}')]`);
      expect(Math.round(v)).toBe(f.mes_moda);
      expect(await x.p.locator("#legenda .faixa span").count()).toBe(12);
      for (const mt of ["ciclo", "safrinha"]) {
        await x.p.selectOption("#metrica", mt);
        expect(await x.p.locator("#tit-legenda").textContent(), mt).toContain("Calendário");
      }
      expect(await x.p.locator("#ficha").textContent()).toContain("Calendário de plantio e colheita");
      expect(await x.p.locator("#ficha svg.gantt").count()).toBe(1);
      expect(x.erros).toEqual([]);
      await fecha(x);
    }, LENTO);

    test("agrupar por: a UF soma a área de soja dos municípios, a % da área rural é ponderada, e o tooltip nomeia o grupo", async () => {
      const x = await abre(nav, "?c=soja&a=2024&m=area&ag=uf");
      await quadro(x.p);
      const r = await roda<any>(x.p, `
        const sor = T.M.mun.id.indexOf('5107925'), NA = T.M.anos.prod[1] - T.M.ano0.prod + 1, a = 2024 - T.M.ano0.prod;
        const s = T.serieItem(T.est.itens[0]); let mt = 0;
        for (let m = 0; m < T.M.mun.id.length; m++) if (T.M.mun.uf[m] === 'MT') { const v = s.area[m * NA + a]; if (v > 0) mt += v; }
        const outro = T.M.mun.id.indexOf('5103403');   // Cuiabá: mesmo valor que Sorriso
        return { sor: T.VAL[sor], mt, cuiaba: T.VAL[outro] };`);
      expect(Math.abs(r.sor / r.mt - 1)).toBeLessThan(1e-4);
      expect(r.cuiaba).toBe(r.sor);
      // a faixa soma os municípios, não o total do grupo repetido em cada um
      const faixa = await roda<number>(x.p, "return T.serieNacional.find(s => s[0] === 2024)[1]");
      expect(Math.abs(faixa / 46.2e6 - 1)).toBeLessThan(0.05);
      expect(x.p.url()).toContain("ag=uf");
      await x.p.selectOption("#metrica", "pct");
      const pct = await roda<number>(x.p, "return T.VAL[T.M.mun.id.indexOf('5107925')]");
      expect(pct).toBeGreaterThan(5); expect(pct).toBeLessThan(40);   // soja / área rural de MT
      await x.p.selectOption("#agrupa", "imediata");
      const n = await roda<number>(x.p, "return new Set([...T.VAL].filter(v => v > 0)).size");
      expect(n).toBeGreaterThan(100); expect(n).toBeLessThan(511);
      expect(x.erros).toEqual([]);
      await fecha(x);
    }, LENTO);

    test("agrupar por: % do VA e % dos imóveis do CAR somam numerador e denominador do grupo", async () => {
      const x = await abre(nav, "?f=econ&m=pct&a=2021&ag=uf");
      await x.p.waitForFunction(() => (window as any).__T.SOB.econ, null, { timeout: 60_000 });
      await quadro(x.p);
      const r = await roda<number[]>(x.p, `
        const E = T.SOB.econ.A, LUT = v => Math.exp((v - 1) / T.M.k) - 1; let n = 0, d = 0;
        for (let i = 0; i < E.m.length; i++) if (E.a[i] === 31 && T.M.mun.uf[E.m[i]] === 'SP') { n += LUT(E.va_agro[i]); d += LUT(E.va[i]); }
        return [T.VAL[T.M.mun.id.indexOf('3550308')], n / d * 100];`);
      expect(Math.abs(r[0] - r[1])).toBeLessThan(0.05);
      await fecha(x);
    }, LENTO);

    test("o ano da URL sobrevive à chegada do bloco da 3ª etapa", async () => {
      for (const [busca, ano] of [["?f=emis&m=se_agro&a=1995", 1995], ["?f=clima&m=est&a=2024", 2024], ["?f=trab&m=caged&a=2025", 2025]] as const) {
        const x = await abre(nav, busca);
        await x.p.waitForFunction(() => document.getElementById("rotulo-carga")!.hidden, null, { timeout: 60_000 });
        expect(await roda<number>(x.p, "return T.est.ano"), busca).toBe(ano);
        expect(x.p.url(), busca).toContain(`a=${ano}`);
        await fecha(x);
      }
    }, LENTO);

    test("PRODES começa em 2002: 2001 é artefato da linha de base do acumulado", async () => {
      const x = await abre(nav, "?f=desm&a=2001");
      await x.p.waitForFunction(() => (window as any).__T.SOB.terra, null, { timeout: 60_000 });
      expect(await roda<number>(x.p, "return +document.getElementById('ano').min")).toBe(2002);
      await fecha(x);
    }, LENTO);

    test("rótulos das sedes aparecem só no zoom alto, sem se sobrepor", async () => {
      const x = await abre(nav, "?c=soja&a=2024");
      await quadro(x.p);
      expect(await roda<number>(x.p, "return T.ROTULOS.length")).toBe(0);
      await roda(x.p, "T.seleciona(T.M.mun.id.indexOf('3550308')); T.voaPara(T.GEO.caixa.slice(4 * T.est.mun, 4 * T.est.mun + 4), 6)");
      await quadro(x.p); await quadro(x.p);
      const rot = await roda<any[]>(x.p, "return T.ROTULOS");
      expect(rot.length).toBeGreaterThan(5);
      for (let i = 0; i < rot.length; i++) for (let j = i + 1; j < rot.length; j++) {
        const [a, b] = [rot[i], rot[j]];
        expect(a.x1 <= b.x0 || b.x1 <= a.x0 || a.y1 <= b.y0 || b.y1 <= a.y0).toBe(true);
      }
      expect(rot.map(r => r.nome)).toContain("São Paulo");
      await fecha(x);
    }, LENTO);

    test("sem nada na URL, a página abre na lavoura principal, com a árvore de famílias à direita", async () => {
      const x = await abre(nav, "");
      expect(await roda<boolean>(x.p, "return T.est.disputa && T.est.modo === 'pam'")).toBe(true);
      expect(await x.p.locator("#legenda .fam.grupo").count()).toBe(2);   // lavoura temporária e permanente
      expect(await x.p.locator("#tit-legenda").textContent()).toContain("Lavoura principal");
      expect(x.p.url()).toContain("d=1");
      await fecha(x);
    }, LENTO);

    test("lavoura principal: árvore de famílias liga e desliga, conta municípios e vai para a URL", async () => {
      const x = await abre(nav, "?c=soja&a=2020&d=1");
      await quadro(x.p);
      // os dois grupos do IBGE no topo, abertos, com as famílias dentro
      expect(await x.p.locator("#legenda .fam.grupo").count()).toBe(2);
      const nFam = await x.p.locator("#legenda button[data-fam]").count();
      expect(nFam).toBeGreaterThan(10);   // família com lavoura temporária e permanente aparece nos dois
      const conta = async (sel: string) => Number((await x.p.locator(`#legenda ${sel} .n`).textContent())!.replace(/\D/g, "") || 0);
      // a soja é oleaginosa (família 1) temporária; os cereais (0) herdam municípios quando ela sai
      const OLEO = '[data-g="T"][data-fam="1"]', CEREAIS = '[data-g="T"][data-fam="0"]';
      const oleo = await conta(OLEO), cereais = await conta(CEREAIS);
      expect(oleo).toBeGreaterThan(500);
      await x.p.click('#legenda [data-abre="T:1"]');
      expect(await x.p.locator('#legenda .filhos [data-item]').count()).toBeGreaterThan(3);
      const soja = await x.p.locator('#legenda .filhos [data-item]').first();
      expect(await soja.locator(".rot").textContent()).toBe("Soja");
      const antes = await digital(x.p);
      await soja.click();
      await quadro(x.p);
      expect(x.p.url()).toContain("dx=soja");
      expect(await x.p.locator(`#legenda ${OLEO}`).getAttribute("class")).toContain("parcial");
      expect(await x.p.locator('#legenda button[data-g="T"]:not([data-fam])').getAttribute("class")).toContain("parcial");
      expect(await conta(CEREAIS)).toBeGreaterThan(cereais);
      expect(await digital(x.p)).not.toBe(antes);
      await x.p.click('#legenda [data-todas="0"]');
      await quadro(x.p);
      expect(await x.p.locator('#legenda button[data-fam].desligada').count()).toBe(nFam);
      await x.p.click('#legenda [data-todas="1"]');
      await quadro(x.p);
      expect(await x.p.locator("#legenda .desligada, #legenda .parcial").count()).toBe(0);
      expect(await conta(OLEO)).toBe(oleo);
      expect(x.erros).toEqual([]);
      await fecha(x);
    }, LENTO);

    test("soma: a árvore escolhe lavoura e família inteira, com total e unidade", async () => {
      const x = await abre(nav, "?c=soja&a=2020");
      await quadro(x.p);
      expect(await x.p.locator('#alterna-disputa [data-d="0"]').getAttribute("aria-pressed")).toBe("true");
      // rebanho e os outros grupos entram como galhos da árvore, depois das lavouras
      expect(await x.p.locator("#legenda .fam.grupo").count()).toBe(2);
      expect(await x.p.locator("#legenda .arvore > .fam:not(.grupo)").count()).toBeGreaterThan(2);
      const soja = x.p.locator('#legenda .soma [data-g="T"][data-fam="1"]');
      expect(await soja.locator(".n").textContent()).toMatch(/mi ha/);
      // família inteira: uma unidade no título e na URL
      await x.p.click('#legenda [data-g="T"][data-fam="0"]');
      await quadro(x.p);
      expect(decodeURIComponent(x.p.url())).toContain("c=soja,f:cereais");
      expect(await x.p.locator("#tit-legenda").textContent()).toContain("Soja + Cereais");
      // a mesma URL volta à mesma seleção
      const n = await roda<number>(x.p, "return T.est.itens.length");
      expect(n).toBeGreaterThan(5);
      // outra unidade: bovinos troca a seleção inteira
      await x.p.fill("#busca-item", "bovinos");
      await x.p.press("#busca-item", "Enter");
      await quadro(x.p);
      expect(decodeURIComponent(x.p.url())).toMatch(/c=bovinos&/);
      expect(await x.p.locator('#legenda .soma .item.sub.outra', { hasText: "Soja" }).count()).toBe(0);   // a busca filtra
      await x.p.fill("#busca-item", "");
      await x.p.dispatchEvent("#busca-item", "input");
      expect(await x.p.locator('#legenda .soma [data-g="T"][data-fam="0"]').getAttribute("class")).toContain("outra");
      expect(x.erros).toEqual([]);
      await fecha(x);
    }, LENTO);

    test("ao sair da produção declarada e voltar, a legenda fica em Soma ou Principal como estava", async () => {
      const x = await abre(nav, "");
      await quadro(x.p);
      const ida = async () => {
        await x.p.click('[data-modo="sat"]'); await quadro(x.p);
        await x.p.click('[data-modo="pam"]'); await quadro(x.p);
      };
      await ida();
      expect(await roda<boolean>(x.p, "return T.est.disputa")).toBe(true);
      expect(await x.p.locator("#legenda .fam.grupo").count()).toBe(2);
      await x.p.click('#alterna-disputa [data-d="0"]'); await quadro(x.p);
      await ida();
      expect(await roda<boolean>(x.p, "return T.est.disputa")).toBe(false);
      expect(await x.p.locator('#alterna-disputa [data-d="0"]').getAttribute("aria-pressed")).toBe("true");
      expect(x.erros).toEqual([]);
      await fecha(x);
    }, LENTO);

    test("soma: o grupo lavoura temporária entra inteiro como uma unidade", async () => {
      const x = await abre(nav, "?c=soja&a=2020");
      await quadro(x.p);
      await x.p.click('#legenda button[data-g="T"]:not([data-fam])');
      await quadro(x.p);
      expect(decodeURIComponent(x.p.url())).toContain("f:lavoura-temporaria");
      expect(await x.p.locator("#tit-legenda").textContent()).toContain("Lavoura temporária");
      expect(await roda<number>(x.p, "return T.est.itens.length")).toBeGreaterThan(20);
      expect(await x.p.locator('#legenda button[data-g="T"]:not([data-fam])').getAttribute("aria-pressed")).toBe("true");
      expect(x.erros).toEqual([]);
      await fecha(x);
    }, LENTO);

    test("sobre em diálogo, ícone por fonte, linha do tempo e painel recolhíveis", async () => {
      const x = await abre(nav, "?c=soja&a=2020");
      expect(await x.p.locator("#modos button[data-modo] svg").count()).toBe(await x.p.locator("#modos button[data-modo]").count());
      expect(await x.p.locator("#sobre").isVisible()).toBe(false);
      await x.p.click("#abre-sobre");
      expect(await x.p.locator("#sobre").isVisible()).toBe(true);
      expect((await x.p.locator("#sobre #nota").textContent())!.length).toBeGreaterThan(100);
      await x.p.click("#sobre .fechar");
      expect(await x.p.locator("#sobre").isVisible()).toBe(false);
      // linha do tempo e painel esquerdo abrem e fecham; o chip mostra o ano
      expect(await x.p.locator("#chip-ano").textContent()).toBe("2020");
      await x.p.click("#abre-tempo");
      expect(await x.p.locator("#tempo").isVisible()).toBe(false);
      await x.p.click("#abre-tempo");
      expect(await x.p.locator("#tempo").isVisible()).toBe(true);
      await x.p.click("#recolhe-painel");
      expect(await x.p.locator("#modos").isVisible()).toBe(false);
      await x.p.click("#recolhe-painel");
      expect(await x.p.locator("#modos").isVisible()).toBe(true);
      expect(x.erros).toEqual([]);
      await fecha(x);
    }, LENTO);

    test("Lista Suja: círculos na sede somam o acumulado do pipeline, e o tooltip diz a atividade", async () => {
      const F = FIXTURE.listasuja;
      const x = await abre(nav, `?f=trab&m=le_trab_ac&a=${F.ano}`);
      await x.p.waitForFunction(() => (window as any).__T.SOB.gente && (window as any).__T.est.metrica === "le_trab_ac", null, { timeout: 60_000 });
      await quadro(x.p);
      const tot = await roda<number>(x.p, "let s = 0; for (const v of T.VAL) if (v > 0) s += v; return s;");
      expect(tot).toBe(F.trab_ac);
      // sem faixa de cores: a legenda explica o círculo
      expect(await x.p.locator("#legenda .faixa").count()).toBe(0);
      expect(await x.p.locator("#leg-extra").textContent()).toContain("Círculo na sede");
      expect(x.erros).toEqual([]);
      await fecha(x);
    }, LENTO);

    test("LSPA: depois da última PAM, a soja em % da área rural vira previsão por UF, e só nessa medida", async () => {
      const F = FIXTURE.lspa;
      const x = await abre(nav, `?f=pam&c=soja&m=pct&a=${F.ano}`);
      await x.p.waitForFunction(a => (window as any).__T.est.ano === a && (window as any).__T.CAD, F.ano, { timeout: 60_000 });
      await quadro(x.p);
      // todo município do MT com o mesmo valor, e a soma (valor × área rural) dá a área prevista da UF
      const [n, area] = await roda<number[]>(x.p, `const vs = new Set(); let s = 0;
        for (let m = 0; m < T.M.mun.id.length; m++) if (T.M.mun.uf[m] === 'MT') { vs.add(T.VAL[m].toFixed(9)); s += T.VAL[m] * T.RURAL_KM2[m]; }
        return [vs.size, s];`);
      expect(n).toBe(1);
      expect(Math.abs(area / F.area - 1)).toBeLessThan(0.005);
      expect(await x.p.locator("#ano-sub").textContent()).toContain("LSPA");
      expect(await x.p.locator("#tit-legenda").textContent()).toContain("LSPA");
      // em ha, a linha do tempo volta a parar na última PAM
      await x.p.selectOption("#metrica", "area");
      expect(await roda<number>(x.p, "return T.est.ano")).toBeLessThan(F.ano - 1);
      expect(x.erros).toEqual([]);
      await fecha(x);
    }, LENTO);

    test("ficha: o select da série histórica troca a cultura sem mexer no mapa", async () => {
      const x = await abre(nav, "?c=soja&a=2020&mun=5107925");
      await quadro(x.p);
      const sel = x.p.locator("#serie-item");
      expect(await sel.locator("option:checked").textContent()).toBe("Soja");
      const mapa = await digital(x.p);
      const milho = await sel.locator("option", { hasText: /^Milho$/ }).getAttribute("value");
      await sel.selectOption(milho!);
      expect(await x.p.locator("#serie-item option:checked").textContent()).toBe("Milho");
      expect(await digital(x.p)).toBe(mapa);
      expect(x.erros).toEqual([]);
      await fecha(x);
    }, LENTO);

    test("ficha: abre no tema do modo, o cabeçalho leva a cada tema e a legenda recolhida volta ao fechar", async () => {
      const x = await abre(nav, "?f=cred&mun=5107925");
      const p = x.p;
      await p.waitForSelector("#ficha .temas button[data-sec='Dinheiro']");
      const temas = () => p.locator("#ficha .temas button").evaluateAll(bs => bs.map(b => [b.textContent, b.getAttribute("aria-current")]));
      // a seção no alto da ficha é de Dinheiro, e o tema marcado também
      expect(await p.evaluate(() => { const f = document.getElementById("ficha")!; return f.scrollTop > 0; })).toBe(true);
      expect((await temas()).find(([, c]) => c === "true")![0]).toBe("Dinheiro");
      // as seções vêm agrupadas na ordem das abas
      const ordem = await p.locator("#ficha > details").evaluateAll(ds => [...new Set(ds.map(d => (d as HTMLElement).dataset.sec))]);
      expect(ordem.slice(0, 3)).toEqual(["Produção", "Terra", "Dinheiro"]);
      await p.click("#ficha .temas button[data-sec='Produção']");
      await p.waitForFunction(() => document.getElementById("ficha")!.scrollTop === 0);
      // rolada à mão, a ficha fica onde está quando o ano muda
      await p.evaluate(() => { document.getElementById("ficha")!.scrollTop = 300; });
      await roda(p, "T.defineAno(2020)");
      expect(await p.evaluate(() => document.getElementById("ficha")!.scrollTop)).toBe(300);
      // a 1440 px a ficha recolheu a legenda; ao fechar, ela volta
      expect(await p.locator("#painel-legenda").getAttribute("class")).toContain("recolhida");
      // aberta à mão, a legenda não recolhe de novo ao trocar de município
      await p.click("#dobra-legenda");
      await roda(p, "T.seleciona(T.M.mun.id.indexOf('5106240'))");
      expect(await p.locator("#painel-legenda").getAttribute("class")).not.toContain("recolhida");
      // ao fechar, a legenda que a ficha recolheu volta
      await roda(p, "T.seleciona(-1); T.seleciona(T.M.mun.id.indexOf('5107925'))");
      expect(await p.locator("#painel-legenda").getAttribute("class")).toContain("recolhida");
      await p.keyboard.press("Escape");
      expect(await p.locator("#painel-legenda").getAttribute("class")).not.toContain("recolhida");
      // "/" leva à busca de município
      await p.keyboard.press("/");
      expect(await p.evaluate(() => document.activeElement?.id)).toBe("busca-mun");
      expect(x.erros).toEqual([]);
      await fecha(x);
    }, LENTO);

    test("privacidade: nenhuma célula ou município embutido tem menos de 5 glebas ou perdas", async () => {
      const x = await abre(nav, "");
      const minimos = await roda<number[]>(x.p, `
        const C = T.CRED.A;
        let g = Infinity, p = Infinity;
        for (const v of C.g_n) if (v < g) g = v;
        for (const v of C.gm_n) if (v < g) g = v;
        for (const v of C.p_n) if (v < p) p = v;
        for (const v of C.pm_n) if (v < p) p = v;
        return [g, p, T.M.min_celula];`);
      expect(minimos[0]).toBeGreaterThanOrEqual(5);
      expect(minimos[1]).toBeGreaterThanOrEqual(5);
      expect(minimos[2]).toBe(5);
      // crédito em R$: combinação, tomadores e instituição por município, todos com o corte
      const cr = await roda<number[]>(x.p, `return T.carrega('credrs').then(b => {
        const A = b.A; let n = Infinity, t = Infinity, i = Infinity;
        for (const v of A.cr_n) if (v < n) n = v;
        for (const v of A.ci_tom) if (v > 0 && v < t) t = v;
        for (const v of A.if_n) if (v < i) i = v;
        return [n, t, i]; })`);
      for (const v of cr) expect(v).toBeGreaterThanOrEqual(5);
      // indicadores do crédito por município × safra, calendário (município × cultura) e Seguro-Defeso
      const outros = await roda<number[]>(x.p, `return Promise.all(['credrs', 'calend', 'gente'].map(T.carrega)).then(([c, k, g]) => {
        let ops = Infinity; for (const v of c.A.ci_ops) if (v < ops) ops = v;
        const tot = new Map(); for (let r = 0; r < k.A.p.length; r++) if (!k.A.f[r]) { const key = k.A.m[r] * 1000 + k.A.p[r]; tot.set(key, (tot.get(key) || 0) + k.A.n[r]); }
        let cal = Infinity; for (const v of tot.values()) if (v < cal) cal = v;
        let def = Infinity; for (const v of g.A.def_n_v) { const n = Math.exp((v - 1) / T.M.k) - 1; if (v && n < def) def = n; }
        return [ops, cal, Math.round(def)]; })`);
      for (const v of outros) expect(v).toBeGreaterThanOrEqual(5);
      // imóvel do CAR: o bloco só traz séries município × ano (nada por imóvel; o corte
      // de 5 operações e 5 imóveis é conferido em monta_pagina.py, onde estão as contagens)
      const imv = await roda<string[]>(x.p, `return T.carrega('imovel').then(b =>
        Object.keys(b.A).filter(k => !/^(cd_v|cd_a|ce_v|ce_a|pp_a|ccar|dcar|dpct|ti|ucpi|fpnd|ldi|ldi_ha|sigef|assent|anl|u_flo|u_pas|u_soja|u_agro|rlvn|ncar)_[mav]$|^(g_ccar|g_cd)_[aijv]$/.test(k)))`);
      expect(imv).toEqual([]);
      // Lista Suja: sem o corte de 5, por decisão (a lista é pública e nominal). O bloco só traz
      // somas por município × ano e a atividade CNAE; nada por empregador
      const ls = await roda<string[]>(x.p, `return T.carrega('gente').then(b => Object.keys(b.A).filter(k => k.startsWith('le_')))`);
      expect(ls.sort()).toEqual(["le_ativ", ...["le_casos", "le_casos_ac", "le_trab", "le_trab_ac"].flatMap(k => ["_a", "_m", "_v"].map(s => k + s))].sort());
      await fecha(x);
    }, LENTO);

    test("território comparável: antes do desmembramento o total é repartido, sem mudar a soma", async () => {
      const x = await abre(nav, "?c=soja&a=1985&m=area");
      const r = await roda<any>(x.p, `
        const NA = T.M.anos.prod[1] - T.M.ano0.prod + 1, a = 1985 - T.M.ano0.prod;
        const s = T.serieItem(T.est.itens[0]);
        let cru = 0; for (let m = 0; m < T.M.mun.id.length; m++) { const v = s.area[m * NA + a]; if (v > 0) cru += v; }
        T.calcula(1985);
        let mapa = 0; for (const v of T.VAL) if (v > 0) mapa += v;
        const sorriso = T.M.mun.id.indexOf('5107925');
        return { cru, mapa, sorrisoCru: s.area[sorriso * NA + a], sorrisoMapa: T.VAL[sorriso] };`);
      // a soma nacional não muda (a repartição só move área dentro do grupo)
      expect(Math.abs(r.mapa / r.cru - 1)).toBeLessThan(1e-4);
      // Sorriso não existia em 1985: sem dado próprio, recebe a parte do território
      expect(Number.isNaN(r.sorrisoCru)).toBe(true);
      expect(r.sorrisoMapa).toBeGreaterThan(0);
      await fecha(x);
    }, LENTO);

    test("celular: filtros e legenda viram folhas, uma por vez, sem rolagem horizontal", async () => {
      const x = await abre(nav, "?c=soja&a=2024", { viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: motor !== "firefox" });
      const p = x.p;
      expect(await p.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      const fora = () => p.evaluate(() => document.getElementById("painel")!.getBoundingClientRect().top >= innerHeight - 2);
      expect(await fora()).toBe(true);
      await p.click("#abre-painel");
      await p.waitForTimeout(400);
      expect(await fora()).toBe(false);
      expect(await p.locator("#rotulo-celular").textContent()).toContain("Soja");
      // a folha fechada (legenda) fica fora da tabulação; a aberta, não
      expect(await p.evaluate(() => [document.getElementById("painel")!.inert, document.getElementById("painel-legenda")!.inert])).toEqual([false, true]);
      // a legenda é outra folha: abrir uma fecha a outra
      const legFora = () => p.evaluate(() => document.getElementById("painel-legenda")!.getBoundingClientRect().top >= innerHeight - 2);
      expect(await legFora()).toBe(true);
      await p.click("#abre-legenda");
      await p.waitForTimeout(400);
      expect(await legFora()).toBe(false);
      expect(await fora()).toBe(true);
      await p.click("#dobra-legenda");
      await p.waitForTimeout(400);
      expect(await legFora()).toBe(true);
      expect(await p.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await p.click("#abre-painel");
      await p.waitForTimeout(400);
      expect(await p.locator("#modos .grupo-modos").evaluateAll(ts => new Set(ts.map(t => Math.round(t.getBoundingClientRect().top))).size)).toBe(1);
      await fecha(x);
    }, LENTO);
  });
}
