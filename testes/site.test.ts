import { afterAll, beforeAll, describe, expect, test } from "bun:test";
import { type Browser } from "playwright";
import { join } from "node:path";
import { ESCOLHIDOS, LENTO, MOTORES, RAIZ } from "./comum";

test("build: HTML, CSS e JS minificados, menores que os de site/", () => {
  const fonte = statSync(join(RAIZ, "site", "index.html")).size, saida = statSync(join(RAIZ, "dist", "index.html")).size;
  expect(saida).toBeLessThan(fonte * 0.8);   // medido: −27%; o resto é a fonte embutida em base64
  const html = readFileSync(join(RAIZ, "dist", "index.html"), "utf8");
  expect(html).not.toContain("/* ---------- ");
  expect(html).toContain("serviceWorker");
});

/* A versão do GitHub Pages: o build (scripts/build.js) minifica site/ em dist/, e é
   dist/ que se testa, servido por HTTP como o Pages faria. A segunda etapa fica presa
   até o teste soltar, para provar que o primeiro mapa sai só com a malha e a área.
   Os testes "sem …" e "trava" vêm do swissviz: cada um é um defeito já visto lá. */
import { readFileSync, statSync } from "node:fs";
const build = Bun.spawnSync(["bun", "scripts/build.js"], { cwd: RAIZ });
if (build.exitCode !== 0) throw new Error("build falhou:\n" + build.stderr.toString());
const SITE = join(RAIZ, "dist");
let trava = "";   // prefixo de bloco cuja resposta para no meio (40%) e nunca termina
const servidor = Bun.serve({
  port: 0,
  idleTimeout: 0,
  async fetch(req) {
    const caminho = decodeURIComponent(new URL(req.url).pathname);
    const arq = Bun.file(join(SITE, caminho === "/" ? "index.html" : caminho));
    if (!(await arq.exists())) return new Response("não achei", { status: 404 });
    if (trava && caminho.includes("/dados/" + trava)) {
      const dado = new Uint8Array(await arq.arrayBuffer());
      // como no swissviz: declara o tamanho inteiro e manda só 40%
      return new Response(new ReadableStream({ start(c) { c.enqueue(dado.subarray(0, Math.floor(dado.length * 0.4))); } }),
        { headers: { "Content-Length": String(dado.length) } });
    }
    return new Response(arq);
  },
});
const BASE = `http://localhost:${servidor.port}/`;

for (const motor of ESCOLHIDOS) {
  describe(`${motor} · site/`, () => {
    let nav: Browser;
    beforeAll(async () => { nav = await MOTORES[motor].launch(); }, LENTO);
    afterAll(async () => { await nav?.close(); });

    test("primeiro mapa com malha e área; o resto chega depois e liga as outras fontes", async () => {
      const ctx = await nav.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: "dark", serviceWorkers: "block" });
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
      // quantidade e valor (o maior bloco) não vêm só para a lavoura principal
      expect([...pedidos].sort()).toEqual(["cad", "cred", "malha", "mapb", "prod"]);
      // a primeira etapa é pedida no <head>, antes do script, e reusada (sem baixar duas vezes)
      expect(await p.evaluate(() => "__pre" in window)).toBe(true);
      expect(new Set(pedidos).size).toBe(pedidos.length);
      await p.click('#modos .grupo-modos[data-sec="Produção"]');
      await p.click('[data-modo="pam"]');
      await p.uncheck("#disputa");
      await p.selectOption("#metrica", "q");
      await p.waitForFunction(() => (window as any).__T.SOB.prodqv, null, { timeout: 60_000 });
      expect(pedidos).toContain("prodqv");
      // 3ª etapa: os contornos só vêm quando um modo pede (Garantia-Safra desenha o semiárido)
      await p.click('#modos .grupo-modos[data-sec="Clima e fogo"]');
      await p.click('[data-modo="gs"]');
      await p.waitForFunction(() => (window as any).__T.CONT, null, { timeout: 60_000 });
      expect(pedidos).toContain("contornos");
      expect(erros).toEqual([]);
      await ctx.close();
    }, LENTO);

    test("bloco da 3ª etapa que falha pode ser pedido de novo", async () => {
      const ctx = await nav.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: "dark", serviceWorkers: "block" });
      await ctx.addInitScript(() => { (window as any).__testes = (o: any) => { (window as any).__T = o; }; });
      let falhas = 0;
      await ctx.route("**/dados/econ.*.bin", async rota => { if (falhas++ === 0) await rota.abort(); else await rota.continue(); });
      const p = await ctx.newPage();
      await p.goto(BASE + "?c=soja&a=2020");
      await p.waitForFunction(() => !!(window as any).__T, null, { timeout: 60_000 });
      await p.click('#modos .grupo-modos[data-sec="Dinheiro"]');
      await p.click('[data-modo="econ"]');
      await p.waitForFunction(() => /falharam/.test(document.getElementById("rotulo-carga")!.textContent!), null, { timeout: 30_000 });
      await p.click('[data-modo="cred"]');
      await p.click('[data-modo="econ"]');
      await p.waitForFunction(() => (window as any).__T.SOB.econ, null, { timeout: 30_000 });
      expect(falhas).toBe(2);
      await ctx.close();
    }, LENTO);

    test("sem DecompressionStream, a página diz que o navegador não abre os dados", async () => {
      const ctx = await nav.newContext({ serviceWorkers: "block" });
      await ctx.addInitScript(() => { delete (window as any).DecompressionStream; });
      const p = await ctx.newPage();
      await p.goto(BASE);
      expect(await p.locator("#carregando").textContent()).toContain("não descomprime");
      await ctx.close();
    }, LENTO);

    test("sem JavaScript, a página diz que precisa dele", async () => {
      const ctx = await nav.newContext({ javaScriptEnabled: false });
      const p = await ctx.newPage();
      await p.goto(BASE);
      expect(await p.locator("#sem-js").isVisible()).toBe(true);
      await ctx.close();
    }, LENTO);

    test("bloco que para no meio do download desiste com aviso, em vez de girar para sempre", async () => {
      const ctx = await nav.newContext({ serviceWorkers: "block" });
      await ctx.addInitScript(() => { (window as any).__parado = 1500; });
      trava = "prod.";
      try {
        const p = await ctx.newPage();
        await p.goto(BASE);
        await p.waitForFunction(() => document.getElementById("carregando")?.classList.contains("erro"), null, { timeout: 30_000 });
        expect(await p.locator("#carregando").textContent()).toContain("parou");
      } finally { trava = ""; await ctx.close(); }
    }, LENTO);

    /* o WebKit do Playwright não recarrega offline ("internal error"); o teste roda no
       Chromium e no Firefox. Nos outros testes o service worker fica bloqueado: com ele no
       controle, o Playwright não vê nem intercepta os pedidos que ele faz. */
    test.skipIf(motor === "webkit")("segunda visita sem rede: o service worker serve a página e os blocos do cache", async () => {
      const ctx = await nav.newContext({ viewport: { width: 1440, height: 900 } });
      const p = await ctx.newPage();
      await p.goto(BASE + "?c=soja&a=2020");
      await p.waitForSelector("#carregando", { state: "detached", timeout: 60_000 });
      await p.evaluate(() => navigator.serviceWorker.ready);
      // a página guarda cada bloco ao baixá-lo; espera as duas primeiras etapas (5 blocos)
      await p.waitForFunction(async () => (await (await caches.open("chao-dados")).keys()).length >= 5, null, { timeout: 30_000, polling: 200 });
      await ctx.setOffline(true);
      await p.reload();
      await p.waitForSelector("#carregando", { state: "detached", timeout: 60_000 });
      expect(await p.locator("#legenda .faixa, #legenda .fam").count()).toBeGreaterThan(0);
      await ctx.close();
    }, LENTO);

    test("estado da URL que pede a segunda etapa espera por ela", async () => {
      const ctx = await nav.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: "dark", serviceWorkers: "block" });
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
