/* Peças que os testes compartilham.
 *
 * O index.html tem ~26 MB; cada motor abre a página uma vez por arquivo de teste
 * e quem mexe no estado volta ao ponto de partida pela URL. O package.json é só
 * de desenvolvimento: nada dele entra na página publicada. */
import { chromium, firefox, webkit, type Browser, type BrowserContext, type Page } from "playwright";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

export const RAIZ = join(import.meta.dir, "..");
export const INDEX = join(RAIZ, "index.html");
export const URL_INDEX = pathToFileURL(INDEX).href;
export const FIXTURE = JSON.parse(readFileSync(join(import.meta.dir, "fixture.json"), "utf8"));
export const LENTO = 120_000;

export const MOTORES = { chromium, firefox, webkit };
export type Motor = keyof typeof MOTORES;
/* BRAGRO_MOTORES=chromium roda só um; o padrão são os três */
export const ESCOLHIDOS = ((process.env.BRAGRO_MOTORES || "chromium,firefox,webkit").split(",") as Motor[]);

/** Abre a página com o gancho de teste: a página chama window.__testes(internos)
 *  no fim do carregamento, e o gancho guarda tudo em window.__T. O produto não
 *  ganha porta de depuração — sem o gancho definido, a chamada não acontece. */
export async function abre(nav: Browser, busca = "", opcoes: Parameters<Browser["newContext"]>[0] = {}) {
  const ctx = await nav.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: "dark", ...opcoes });
  await ctx.addInitScript(() => { (window as any).__testes = (o: any) => { (window as any).__T = o; }; });
  const pedidosRede: string[] = [];
  ctx.on("request", r => { if (!r.url().startsWith("file:") && !r.url().startsWith("data:") && !r.url().startsWith("blob:")) pedidosRede.push(r.url()); });
  const p = await ctx.newPage();
  const erros: string[] = [];
  p.on("pageerror", e => erros.push(e.message));
  await p.goto(URL_INDEX + busca);
  await p.waitForFunction(() => !!(window as any).__T, null, { timeout: 90_000 });
  return { ctx, p, erros, pedidosRede };
}

/** Avalia uma expressão sobre os internos (T) da página. */
export const roda = <R>(p: Page, corpo: string): Promise<R> =>
  p.evaluate(`(() => { const T = window.__T; ${corpo} })()`) as Promise<R>;

/** Impressão digital do canvas: muda quando o desenho muda. */
export const digital = (p: Page) => p.evaluate(() => {
  const c = document.getElementById("mapa") as HTMLCanvasElement;
  const d = c.getContext("2d")!.getImageData(0, 0, c.width, c.height).data;
  let h = 0;
  for (let i = 0; i < d.length; i += 97) h = (h * 31 + d[i]) | 0;
  return h;
});

export const quadro = (p: Page) => p.evaluate(() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))));

export async function fecha(x: { ctx: BrowserContext }) { await x.ctx.close(); }
