import { afterAll, beforeAll, describe, expect, test } from "bun:test";
import { type Browser } from "playwright";
import { join } from "node:path";
import { ESCOLHIDOS, LENTO, MOTORES, RAIZ } from "./comum";

/* A versão do GitHub Pages (site/): HTML leve e blocos gzip ao lado. Servida por
   HTTP como o Pages faria; a segunda etapa fica presa até o teste soltar, para
   provar que o primeiro mapa sai só com a malha e a área. */
const SITE = join(RAIZ, "site");
const servidor = Bun.serve({
  port: 0,
  async fetch(req) {
    const caminho = new URL(req.url).pathname;
    const arq = Bun.file(join(SITE, caminho === "/" ? "index.html" : decodeURIComponent(caminho)));
    return (await arq.exists()) ? new Response(arq) : new Response("não achei", { status: 404 });
  },
});
const BASE = `http://localhost:${servidor.port}/`;

for (const motor of ESCOLHIDOS) {
  describe(`${motor} · site/`, () => {
    let nav: Browser;
    beforeAll(async () => { nav = await MOTORES[motor].launch(); }, LENTO);
    afterAll(async () => { await nav?.close(); });

    test("primeiro mapa com malha e área; o resto chega depois e liga as outras fontes", async () => {
      const ctx = await nav.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: "dark" });
      await ctx.addInitScript(() => { (window as any).__testes = (o: any) => { (window as any).__T = o; }; });
      let solta!: () => void;
      const portao = new Promise<void>(r => { solta = r; });
      const pedidos: string[] = [];
      await ctx.route("**/dados/*.bin", async rota => {
        const nome = new URL(rota.request().url()).pathname.split("/").pop()!.split(".")[0];
        pedidos.push(nome);
        if (!["malha", "prod"].includes(nome)) await portao;
        await rota.continue();
      });
      const p = await ctx.newPage();
      const erros: string[] = [];
      p.on("pageerror", e => erros.push(e.message));
      await p.goto(BASE + "?c=soja&a=2020&d=1");
      await p.waitForSelector("#carregando", { state: "detached", timeout: 60_000 });
      // desenhado e com a árvore, mas sem a segunda etapa
      expect(await p.locator("#legenda .fam").count()).toBe(10);
      expect(await p.locator('[data-modo="sat"]').isDisabled()).toBe(true);
      expect(await p.evaluate(() => !!(window as any).__T)).toBe(false);
      solta();
      await p.waitForFunction(() => !!(window as any).__T, null, { timeout: 60_000 });
      expect(await p.locator('[data-modo="sat"]').isDisabled()).toBe(false);
      await p.click('[data-modo="sat"]');
      expect((await p.locator("#tit-legenda").textContent())!.length).toBeGreaterThan(3);
      expect(pedidos.slice(0, 2).sort()).toEqual(["malha", "prod"]);
      expect(pedidos.sort()).toEqual(["cad", "cred", "malha", "mapb", "prod", "prodqv"]);
      // 3ª etapa: os contornos só vêm quando um modo pede (Garantia-Safra desenha o semiárido)
      await p.click('[data-modo="gs"]');
      await p.waitForFunction(() => (window as any).__T.CONT, null, { timeout: 60_000 });
      expect(pedidos).toContain("contornos");
      expect(erros).toEqual([]);
      await ctx.close();
    }, LENTO);

    test("estado da URL que pede a segunda etapa espera por ela", async () => {
      const ctx = await nav.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: "dark" });
      await ctx.addInitScript(() => { (window as any).__testes = (o: any) => { (window as any).__T = o; }; });
      const p = await ctx.newPage();
      const erros: string[] = [];
      p.on("pageerror", e => erros.push(e.message));
      await p.goto(BASE + "?f=sat&c=soja&a=2020&mun=5107925");
      await p.waitForFunction(() => !!(window as any).__T, null, { timeout: 60_000 });
      expect(await p.locator('[data-modo="sat"]').getAttribute("aria-pressed")).toBe("true");
      expect(await p.locator("#ficha").textContent()).toContain("O que o satélite vê");
      expect(erros).toEqual([]);
      await ctx.close();
    }, LENTO);
  });
}

afterAll(() => servidor.stop(true));
