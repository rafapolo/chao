#!/usr/bin/env bun
// Build da versão web: site/ (escrito por pipeline/monta_pagina.py) -> dist/, o que o
// GitHub Pages publica. Minifica o HTML com o CSS e o JS embutidos, copia os blocos e
// escreve o service worker, como o build do swissviz.
//
// O index.html autocontido (file://) não passa por aqui: ele é quase todo base64, e a
// minificação não ganharia nada que se note.

import { minify } from "html-minifier-terser";
import { minify as terser } from "terser";
import { cpSync, mkdirSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from "fs";
import { join } from "path";

const RAIZ = new URL("..", import.meta.url).pathname;
const SITE = join(RAIZ, "site");
const DIST = join(RAIZ, "dist");

// do zero, para nada que saiu de site/ sobrar em dist/
rmSync(DIST, { recursive: true, force: true });
mkdirSync(DIST, { recursive: true });

// ── 1. HTML, com CSS e JS embutidos ─────────────────────────────────────────
const fonte = readFileSync(join(SITE, "index.html"), "utf-8");
let html = await minify(fonte, {
    collapseWhitespace: true,
    removeComments: true,
    removeRedundantAttributes: true,
    removeScriptTypeAttributes: true,
    useShortDoctype: true,
    minifyCSS: true,
    minifyJS: { compress: { passes: 2 }, mangle: true, format: { comments: false } },
    sortClassName: false,
});

// ── 2. Service worker ───────────────────────────────────────────────────────
// Os blocos têm o hash do conteúdo no nome: nunca mudam, ficam num cache próprio entre
// deploys, e só os que mudaram são baixados de novo. Quem guarda o bloco é a própria
// página, ao baixá-lo (o service worker não pré-carrega bloco: na primeira visita, isso
// baixaria tudo duas vezes). A página e o ícone vão num cache
// com o nome do commit, buscados primeiro na rede (o max-age=600 do Pages faria uma
// visita logo depois do deploy ver a página velha) e, sem rede, no cache.
const sha = (process.env.GITHUB_SHA || Bun.spawnSync(["git", "rev-parse", "HEAD"], { cwd: RAIZ }).stdout.toString().trim() || "dev").slice(0, 8);
const blocos = readdirSync(join(SITE, "dados")).filter(f => f.endsWith(".json.gz")).sort();
const sw = `
const PAGINA = 'chao-${sha}', DADOS = 'chao-dados';
const BLOCOS = ${JSON.stringify(blocos)};
const INICIAIS = ['./', './favicon.svg'];
self.addEventListener('install', e => {
  self.skipWaiting();
  // cache: 'reload' passa por cima do cache HTTP do navegador
  e.waitUntil(caches.open(PAGINA).then(c => c.addAll(INICIAIS.map(u => new Request(u, { cache: 'reload' })))).catch(() => {}));
});
self.addEventListener('activate', e => {
  e.waitUntil((async () => {
    for (const k of await caches.keys()) if (k !== PAGINA && k !== DADOS) await caches.delete(k);
    // blocos de deploys anteriores, que nenhuma página pede mais
    const d = await caches.open(DADOS);
    for (const r of await d.keys()) if (!BLOCOS.includes(new URL(r.url).pathname.split('/').pop())) await d.delete(r);
    await self.clients.claim();
  })());
});
const guarda = (e, nome, req, res) => e.waitUntil(caches.open(nome).then(c => c.put(req, res)).catch(() => {}));
self.addEventListener('fetch', e => {
  const req = e.request, url = new URL(req.url);
  if (req.method !== 'GET' || url.origin !== location.origin) return;
  if (url.pathname.includes('/dados/')) {
    e.respondWith(caches.match(req, { cacheName: DADOS }).then(r => r || fetch(req).then(res => {
      if (res.ok) guarda(e, DADOS, req, res.clone());
      return res;
    })));
    return;
  }
  // a página: o mesmo HTML para qualquer ?estado da URL
  const chave = req.mode === 'navigate' ? new Request('./') : req;
  e.respondWith(fetch(req).then(res => {
    if (res.ok) guarda(e, PAGINA, chave, res.clone());
    return res;
  }).catch(() => caches.match(chave, { cacheName: PAGINA }).then(r => r || Response.error())));
});
`;
const swMin = await terser(sw, { toplevel: true, compress: { passes: 2 }, mangle: true, format: { comments: false } });
writeFileSync(join(DIST, "sw.js"), swMin.code);
// o registro vai só em dist/: site/ cru, servido para teste, não tem sw.js
html = html.replace("</body>", `<script>"serviceWorker"in navigator&&navigator.serviceWorker.register("sw.js").catch(()=>{})</script></body>`);
if (!html.includes("serviceWorker")) html += `<script>"serviceWorker"in navigator&&navigator.serviceWorker.register("sw.js").catch(()=>{})</script>`;
writeFileSync(join(DIST, "index.html"), html);

// ── 3. Blocos e arquivos estáticos ──────────────────────────────────────────
cpSync(join(SITE, "dados"), join(DIST, "dados"), { recursive: true });
for (const f of ["favicon.svg", ".nojekyll"]) cpSync(join(SITE, f), join(DIST, f));

// ── 4. Tamanhos ─────────────────────────────────────────────────────────────
const kb = n => (n / 1024).toFixed(1) + " KB";
const de = statSync(join(SITE, "index.html")).size, para = statSync(join(DIST, "index.html")).size;
console.log(`index.html: ${kb(de)} -> ${kb(para)} (−${((1 - para / de) * 100).toFixed(0)}%), ${kb(Bun.gzipSync(readFileSync(join(DIST, "index.html"))).length)} com gzip`);
console.log(`sw.js:      ${kb(swMin.code.length)} (cache chao-${sha}; ${blocos.length} blocos conhecidos)`);
const du = d => readdirSync(d, { withFileTypes: true }).reduce((n, e) => n + (e.isDirectory() ? du(join(d, e.name)) : statSync(join(d, e.name)).size), 0);
console.log(`dist/:      ${(du(DIST) / 1048576).toFixed(1)} MB`);
