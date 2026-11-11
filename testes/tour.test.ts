/* O tour (design/tour.md): o convite de ?tour=1, a carga só depois do clique, &t= no meio,
 * o fim sem erro e o Esc que devolve o estado de antes. */
import { afterAll, beforeAll, describe, expect, test } from "bun:test";
import { type Browser } from "playwright";
import { ESCOLHIDOS, LENTO, MOTORES, abre, fecha, roda } from "./comum";

const ESTADO = "return JSON.stringify({ ...T.est, desligadas: [...T.est.desligadas], abertas: [...T.est.abertas] })";

for (const motor of ESCOLHIDOS) {
  describe(motor, () => {
    let nav: Browser;
    beforeAll(async () => { nav = await MOTORES[motor].launch(); }, LENTO);
    afterAll(async () => { await nav?.close(); });

    test("?tour=1 abre o convite, sai do endereço e não baixa nada antes do clique", async () => {
      const x = await abre(nav, "?tour=1&t=170");
      const p = x.p;
      expect(await p.isVisible("#tour-convite")).toBe(true);
      expect(p.url()).not.toContain("tour");
      // sem parâmetros sobrando, a página abre na lavoura principal, como sempre
      expect(await roda<boolean>(p, "return T.est.disputa")).toBe(true);
      expect(await roda<boolean>(p, "return !!T.SOB.terra || !!T.SOB.fogo")).toBe(false);
      // &t=170: as cenas anteriores passam na hora, e o fim chega em poucos segundos
      await p.click("#tour-convite button");
      await p.waitForFunction(() => (window as any).tour.cena() === 12 && document.getElementById("tour-frase")!.textContent!.includes("Agora é com você"), null, { timeout: 60_000 });
      expect(await p.evaluate(() => getComputedStyle(document.querySelector(".painel")!).opacity)).toBe("0");
      await p.waitForFunction(() => !(window as any).tour.ativo(), null, { timeout: 60_000 });
      expect(await roda<string>(p, "return T.est.modo + T.est.disputa + T.est.ano")).toBe("pamtrue2024");
      expect(p.url()).not.toContain("tour");
      expect(x.erros).toEqual([]);
      await fecha(x);
    }, LENTO);

    test("os números das legendas saem dos blocos", async () => {
      const x = await abre(nav, "");
      const p = x.p;
      // começa em t segundos e espera a frase que casa com re (o texto vem dos blocos)
      const confere = async (t: number, re: RegExp) => {
        await p.evaluate(s => { (window as any).tour.iniciar(s); }, t);  // sem esperar o filme
        await p.waitForFunction(r => new RegExp(r).test(document.getElementById("tour-frase")!.textContent || ""), re.source, { timeout: 30_000 });
        await p.keyboard.press("Escape");
        await p.waitForFunction(() => !(window as any).tour.ativo());
      };
      // as referências estão em design/achados.md (parquets do pipeline)
      await confere(36, /De 5,1 para 46,2 milhões de hectares/);
      await confere(48, /^600 mil hectares de soja: a maior área do país/);
      await confere(118, /nova alta em 2022 \(28 mil\) e 15,6 mil em 2025, o menor da série/);
      await confere(146, /A seca levou 5\d% da colheita/);
      expect(x.erros).toEqual([]);
      await fecha(x);
    }, LENTO);

    test("Esc devolve fonte, culturas, ano e ficha; o mapa fica onde a câmera estava", async () => {
      const x = await abre(nav, "?f=sat&c=cana&a=2003&mun=3550308");
      const p = x.p;
      const antes = await roda<string>(p, ESTADO);
      await p.click("#abre-tour");
      await p.waitForFunction(() => (window as any).tour.cena() >= 1, null, { timeout: 60_000 });
      await p.keyboard.press("Escape");
      await p.waitForFunction(() => !(window as any).tour.ativo());
      expect(await roda<string>(p, ESTADO)).toBe(antes);
      expect(await p.isVisible("#ficha.aberta")).toBe(true);
      expect(await p.isHidden("#tour-convite")).toBe(true);
      await p.waitForTimeout(1000);
      expect(await p.isHidden("#tour")).toBe(true);
      expect(new URL(p.url()).searchParams.get("f")).toBe("sat");
      expect(x.erros).toEqual([]);
      await fecha(x);
    }, LENTO);
  });
}
