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
      expect(await x.p.locator("#legenda .fam").count()).toBe(10);   // famílias de lavoura
      expect(x.erros).toEqual([]);
      await fecha(x);
    }, LENTO);

    test("lavoura principal: árvore de famílias liga e desliga, conta municípios e vai para a URL", async () => {
      const x = await abre(nav, "?c=soja&a=2020&d=1");
      await quadro(x.p);
      expect(await x.p.locator("#legenda .fam").count()).toBe(10);
      const conta = async (sel: string) => Number((await x.p.locator(`#legenda ${sel} .n`).textContent())!.replace(/\D/g, "") || 0);
      // a soja é oleaginosa (família 1); os cereais (0) herdam municípios quando ela sai
      const oleo = await conta('[data-fam="1"]'), cereais = await conta('[data-fam="0"]');
      expect(oleo).toBeGreaterThan(500);
      await x.p.click('#legenda [data-abre="1"]');
      expect(await x.p.locator('#legenda .filhos [data-item]').count()).toBeGreaterThan(3);
      const soja = await x.p.locator('#legenda .filhos [data-item]').first();
      expect(await soja.locator(".rot").textContent()).toBe("Soja");
      const antes = await digital(x.p);
      await soja.click();
      await quadro(x.p);
      expect(x.p.url()).toContain("dx=soja");
      expect(await x.p.locator('#legenda [data-fam="1"]').getAttribute("class")).toContain("parcial");
      expect(await conta('[data-fam="0"]')).toBeGreaterThan(cereais);
      expect(await digital(x.p)).not.toBe(antes);
      await x.p.click('#legenda [data-todas="0"]');
      await quadro(x.p);
      expect(await x.p.locator('#legenda [data-fam].desligada').count()).toBe(10);
      await x.p.click('#legenda [data-todas="1"]');
      await quadro(x.p);
      expect(await x.p.locator("#legenda .desligada, #legenda .parcial").count()).toBe(0);
      expect(await conta('[data-fam="1"]')).toBe(oleo);
      expect(x.erros).toEqual([]);
      await fecha(x);
    }, LENTO);

    test("sobre os dados abre num diálogo, e cada fonte tem ícone", async () => {
      const x = await abre(nav, "?c=soja&a=2020");
      expect(await x.p.locator("#modos button svg").count()).toBe(7);
      expect(await x.p.locator("#sobre").isVisible()).toBe(false);
      await x.p.click("#abre-sobre");
      expect(await x.p.locator("#sobre").isVisible()).toBe(true);
      expect((await x.p.locator("#sobre #nota").textContent())!.length).toBeGreaterThan(100);
      await x.p.click("#sobre .fechar");
      expect(await x.p.locator("#sobre").isVisible()).toBe(false);
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
      await fecha(x);
    }, LENTO);
  });
}
