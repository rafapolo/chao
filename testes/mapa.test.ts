import { afterAll, beforeAll, describe, expect, test } from "bun:test";
import { type Browser } from "playwright";
import { ESCOLHIDOS, FIXTURE, LENTO, MOTORES, abre, digital, fecha, quadro, roda } from "./comum";

for (const motor of ESCOLHIDOS) {
  describe(motor, () => {
    let nav: Browser;
    beforeAll(async () => { nav = await MOTORES[motor].launch(); }, LENTO);
    afterAll(async () => { await nav?.close(); });

    test("abre por file:// sem pedir nada à rede e sem erro", async () => {
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

    test("cultura, ano, medida e fonte mudam o desenho e a URL", async () => {
      const x = await abre(nav, "?c=soja&a=2024");
      const p = x.p;
      await quadro(p);
      let antes = await digital(p);
      const passos: [string, () => Promise<unknown>, RegExp][] = [
        ["ano", () => roda(p, "T.defineAno(1990)"), /a=1990/],
        ["cultura", () => p.locator("#lista-itens label", { hasText: /^\s*Milho$/ }).locator("input").check(), /c=soja%2Cmilho|c=soja,milho/],
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
      for (const [mid, f] of Object.entries<any>(FIXTURE)) {
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
      for (const modo of ["pam", "sat", "cmp", "exp", "gleba", "perda", "gs"]) {
        await x.p.click(`[data-modo="${modo}"]`);
        await quadro(x.p);
        expect(await x.p.locator("#nota").textContent(), modo).not.toBe("");
        expect(await x.p.locator("#legenda .extra").count(), modo).toBe(1);
      }
      await x.p.click('[data-modo="pam"]');
      await x.p.check("#disputa");
      expect(await x.p.locator("#legenda .cat div").count()).toBe(4);   // 3 culturas + outras
      expect(x.erros).toEqual([]);
      await fecha(x);
    }, LENTO);

    test("privacidade: nenhuma célula embutida tem menos de 5 glebas ou perdas", async () => {
      const x = await abre(nav, "");
      const minimos = await roda<number[]>(x.p, `
        const C = T.CRED.A;
        let g = Infinity, p = Infinity;
        for (const v of C.g_n) if (v < g) g = v;
        for (const v of C.p_n) if (v < p) p = v;
        return [g, p, T.M.min_celula];`);
      expect(minimos[0]).toBeGreaterThanOrEqual(5);
      expect(minimos[1]).toBeGreaterThanOrEqual(5);
      expect(minimos[2]).toBe(5);
      await fecha(x);
    }, LENTO);

    test("celular: painel vira gaveta e não há rolagem horizontal", async () => {
      const x = await abre(nav, "?c=soja&a=2024", { viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: motor !== "firefox" });
      const p = x.p;
      expect(await p.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      const fora = () => p.evaluate(() => document.getElementById("painel")!.getBoundingClientRect().top >= innerHeight - 2);
      expect(await fora()).toBe(true);
      await p.click("#abre-painel");
      await p.waitForTimeout(400);
      expect(await fora()).toBe(false);
      expect(await p.locator("#rotulo-celular").textContent()).toContain("Soja");
      await fecha(x);
    }, LENTO);
  });
}
