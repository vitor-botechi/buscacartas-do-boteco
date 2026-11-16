"use strict";
/* Tela do Buscador de Cartas MTG. O Python (buscador/web/ponte.py) faz as buscas; aqui só se
   desenha a tela e se guarda o estado dela (o que está aberto, histórico Voltar/Avançar).
   Acontecimentos da busca chegam por app.evento(tipo, sid, dados); os de uma busca antiga
   (sid diferente) são ignorados. */

const $ = (id) => document.getElementById(id);
const api = () => window.pywebview.api;
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const dinheiro = (v) => (v == null ? "—" : new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v));
const plural = (n, um, varios) => `${n} ${n === 1 ? um : varios}`;
const norm = (s) => String(s || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/\s+/g, " ").trim();
const clonar = (o) => JSON.parse(JSON.stringify(o));
function idade(seg) {
  let m = Math.floor(seg / 60);
  if (m < 60) return `há ${m} min`;
  const h = Math.floor(m / 60); m %= 60;
  return `há ${h} h` + (m ? ` ${m} min` : "");
}

let cfg = { itens_por_loja: 8, historico_max: 10, velho_depois: 1800, auto_max: 10 };
let lojas = [];
let historico = [];
let avancar = [];
let tela = novaTela();

function novaTela() {
  return {
    sid: 0, carta: "", exato: false, nomes: null, nomesOk: true, tempo: Date.now(),
    ordem: [], res: {}, pendentes: 0, lojasTotal: 0, lojasFeitas: 0,
    autoAtivo: 0, autoTotal: 0, autoFeito: 0, carregando: {}, aviso: "",
    abertos: {}, fechadas: {}, expandidas: {}, recolhido: false, detalhes: {},
  };
}

/* ---------------- lojas (coluna da esquerda) ---------------- */
function desenharLojas() {
  $("lojas").innerHTML = lojas.map((l, i) => `
    <div class="loja${l.marcada ? "" : " off"}" data-i="${i}" title="${esc(l.url)}">
      <span class="chave"></span><span class="nome">${esc(l.nome)}</span>
      ${l.padrao ? "" : `<button class="remover" data-remover="${i}" title="Remover esta loja">✕</button>`}
    </div>`).join("");
}
$("lojas").addEventListener("click", async (e) => {
  const rem = e.target.closest("[data-remover]");
  if (rem) {
    const l = lojas[+rem.dataset.remover];
    const sim = await perguntar(`Remover a loja ${l.nome}?`,
      "Ela sai da lista e deixa de ser pesquisada. Para voltar a usá-la, é só adicioná-la de novo em “+ Adicionar loja”.",
      "Remover", true);
    if (sim) { lojas = await api().remover_loja(l.url); desenharLojas(); }
    return;
  }
  const el = e.target.closest(".loja");
  if (!el) return;
  const l = lojas[+el.dataset.i];
  l.marcada = !l.marcada;
  desenharLojas();
  lojas = await api().marcar_lojas({ [l.url]: l.marcada });
});
async function marcarTodas(valor) {
  const m = {};
  lojas.forEach((l) => { l.marcada = valor; m[l.url] = valor; });
  desenharLojas();
  lojas = await api().marcar_lojas(m);
}
$("todas").onclick = () => marcarTodas(true);
$("nenhuma").onclick = () => marcarTodas(false);

/* janela de pergunta (no lugar do confirm() do navegador, que mostra "127.0.0.1 diz") */
let respostaPergunta = null;
function perguntar(titulo, texto, sim, perigo = false) {
  $("pergunta-titulo").textContent = titulo;
  $("pergunta-texto").textContent = texto;
  $("pergunta-sim").textContent = sim;
  $("pergunta-sim").classList.toggle("perigo", perigo);
  $("pergunta").hidden = false;
  $("pergunta-nao").focus();  // o padrão é não fazer nada
  return new Promise((resolve) => { respostaPergunta = resolve; });
}
function responder(valor) {
  if ($("pergunta").hidden) return;
  $("pergunta").hidden = true;
  const r = respostaPergunta; respostaPergunta = null;
  if (r) r(valor);
}
$("pergunta-sim").onclick = () => responder(true);
$("pergunta-nao").onclick = () => responder(false);
$("pergunta").addEventListener("mousedown", (e) => { if (e.target === $("pergunta")) responder(false); });

function abrirModal() {
  $("loja-link").value = ""; $("loja-nome").value = ""; $("loja-erro").textContent = "";
  $("modal").hidden = false;
  $("loja-link").focus();
}
function fecharModal() { $("modal").hidden = true; }
$("adicionar").onclick = abrirModal;
$("cancelar-loja").onclick = fecharModal;
$("modal").addEventListener("mousedown", (e) => { if (e.target === $("modal")) fecharModal(); });
$("form-loja").addEventListener("submit", async (e) => {
  e.preventDefault();
  const r = await api().adicionar_loja($("loja-link").value, $("loja-nome").value);
  if (r.erro) { $("loja-erro").textContent = r.erro; return; }
  lojas = r.lojas; desenharLojas(); fecharModal();
});

/* ---------------- campo e botões ---------------- */
function avisar(msg, alerta = true) {
  $("resumo").textContent = msg;
  $("resumo").classList.toggle("alerta", alerta);
}
async function colar() {
  let nome = await api().colar();
  if (nome === null) {  // fora do Windows: tenta pela área de transferência do navegador
    try { nome = await api().limpar_nome(await navigator.clipboard.readText()); } catch { nome = ""; }
  }
  $("carta").focus();
  if (!nome) { avisar("Não há texto copiado. Copie o nome da carta e clique em “📋 Colar nome”."); return; }
  $("carta").value = nome;
  avisar(`Colado: “${nome}”. Aperte Enter ou clique em Buscar.`, false);
}
$("colar").onclick = colar;
$("colar").addEventListener("keydown", (e) => {
  // com o foco no botão: Ctrl+V cola; digitar uma letra leva o texto para o campo
  if (e.ctrlKey && e.key.toLowerCase() === "v") { e.preventDefault(); colar(); return; }
  if (e.ctrlKey || e.altKey || e.metaKey) return;
  if (e.key.length === 1 && e.key !== " ") {
    e.preventDefault();
    $("carta").value = e.key;
    $("carta").focus();
  }
});
// ao voltar para o programa (Alt+Tab), o foco vai para "Colar nome": Enter cola, Enter de novo busca
// (a dica que explica isso só aparece ao passar o mouse no botão)
window.addEventListener("focus", () => {
  if (!$("modal").hidden || !$("pergunta").hidden) return;
  setTimeout(() => $("colar").focus(), 30);
});

$("buscar").onclick = () => buscar();
$("carta").addEventListener("keydown", (e) => { if (e.key === "Enter") buscar(); });
$("navegador").onclick = () => {
  const carta = $("carta").value.trim();
  if (!carta) { avisar("Digite o nome da carta."); return; }
  if (!lojas.some((l) => l.marcada)) { avisar("Marque ao menos uma loja."); return; }
  api().abrir_lojas(carta);
};
$("auto").addEventListener("change", async () => { $("auto").value = await api().salvar_auto_limite($("auto").value); });
$("exato").addEventListener("change", aoMarcarExato);
$("recolher").onclick = alternarRecolher;
$("voltar").onclick = () => navegar(historico, avancar);
$("avancar").onclick = () => navegar(avancar, historico);
document.addEventListener("keydown", (e) => {
  if (e.altKey && e.key === "ArrowLeft") { e.preventDefault(); navegar(historico, avancar); }
  if (e.altKey && e.key === "ArrowRight") { e.preventDefault(); navegar(avancar, historico); }
  if (e.key === "Escape" && !$("pergunta").hidden) responder(false);
  else if (e.key === "Escape" && !$("modal").hidden) fecharModal();
});
$("abrir-achadas").onclick = () => {
  const urls = tela.ordem.map((u) => tela.res[u]).filter((r) => r && (temCarta(r) || ["blocked", "unknown", "error"].includes(r.status)))
    .map((r) => r.url_busca);
  if (urls.length) api().abrir(urls);
};

/* ---------------- busca ---------------- */
function telaCompleta() { return Boolean(tela.carta && tela.ordem.length && tela.pendentes === 0); }

function guardarNoHistorico(novaCarta) {
  if (!telaCompleta() || norm(novaCarta) === norm(tela.carta)) return;  // repetir a mesma busca só atualiza
  historico.push(clonar(tela));
  historico.splice(0, Math.max(0, historico.length - cfg.historico_max));
  avancar = [];
}

async function buscar(semHistorico = false) {
  const carta = $("carta").value;
  if (!semHistorico) guardarNoHistorico(carta.trim());
  const r = await api().buscar(carta, $("exato").checked, $("auto").value);
  if (r.erro === "sem_bibliotecas") {
    if (await perguntar("Faltam bibliotecas",
      "Para ler os resultados aqui dentro é preciso instalar: pip install requests beautifulsoup4. Quer abrir as buscas no navegador por enquanto?",
      "Abrir no navegador")) {
      api().abrir_lojas(carta);
    }
    return;
  }
  if (r.erro) { avisar(r.erro); return; }
  tela = novaTela();
  tela.sid = r.sid;
  tela.carta = r.carta;
  tela.exato = $("exato").checked;
  tela.lojasTotal = tela.pendentes = r.lojas.length;
  for (const l of r.lojas) {
    tela.ordem.push(l.url);
    tela.res[l.url] = { loja: { nome: l.nome, url: l.url, cor: l.cor, cor2: l.cor2, logo: l.logo }, url_busca: l.url_busca, status: "buscando", msg: "", itens: [] };
  }
  $("carta").value = r.carta;
  textoRecolher(false);
  atualizarNavegacao();
  desenhar();
  avisar(`Buscando “${r.carta}” em ${plural(r.lojas.length, "loja", "lojas")}…`, false);
}

function itemDe(lojaUrl, itemUrl) {
  const r = tela.res[lojaUrl];
  return r ? r.itens.find((i) => i.url === itemUrl) : null;
}

const app = {
  evento(tipo, sid, dados) {
    if (sid !== tela.sid) return;
    if (tipo === "result") {
      tela.res[dados.loja.url] = dados;
      tela.pendentes = Math.max(0, tela.pendentes - 1);
      tela.lojasFeitas += 1;
    } else if (tipo === "names") {
      aplicarNomes(tela, dados);
    } else if (tipo === "offers") {
      const [lojaUrl, itemUrl, ofertas] = dados;
      const it = itemDe(lojaUrl, itemUrl);
      if (it) it.ofertas = ofertas;
    } else if (tipo === "autostart") {
      const [, urls] = dados;
      tela.autoAtivo += 1; tela.autoTotal += urls.length;
      urls.forEach((u) => { tela.carregando[u] = true; });
    } else if (tipo === "autostep") {
      tela.autoFeito += 1;
      delete tela.carregando[dados[1]];
    } else if (tipo === "autoend") {
      const [, resto] = dados;
      tela.autoAtivo = Math.max(0, tela.autoAtivo - 1);
      tela.autoFeito += resto.length;
      resto.forEach((u) => delete tela.carregando[u]);
    } else if (tipo === "autostop") {
      tela.aviso = `⚠ Detalhes automáticos pausados (${dados} limitou as requisições): use “Ver edições e preços” nos itens.`;
    }
    desenhar();
  },
};
window.app = app;

function aplicarNomes(t, dados) {
  t.nomes = dados.nomes;
  t.nomesOk = dados.ok;
  for (const [url, marcas] of Object.entries(dados.marcas || {})) {
    const r = t.res[url];
    if (r) r.itens.forEach((it, i) => { it.exato = marcas[i]; });
  }
}

async function aoMarcarExato() {
  tela.exato = $("exato").checked;
  if (tela.exato && tela.nomes === null && tela.ordem.length) {
    desenhar();
    avisar("Consultando o Scryfall para reconhecer o nome exato…", false);
    const t = tela;
    const itens = {};
    t.ordem.forEach((u) => { if (t.res[u]) itens[u] = t.res[u].itens.map((i) => i.nome); });
    const dados = await api().nomes_exatos(t.carta, itens);
    aplicarNomes(t, dados);
    if (t !== tela) return;
  }
  desenhar();
}

/* ---------------- o que aparece de cada loja ---------------- */
function visiveis(r) {
  if (tela.exato && tela.nomes) return r.itens.filter((i) => i.exato === true);
  return r.itens;
}
function temCarta(r) { return r.status === "found" && visiveis(r).length > 0; }
const chave = (lojaUrl, itemUrl) => `${lojaUrl}|${itemUrl}`;

function textoStatus(r) {
  const itens = visiveis(r);
  switch (r.status) {
    case "buscando": return ["buscando", '<span class="girando"></span>Buscando…'];
    case "found":
      if (itens.length) return ["found", `✓ Encontrada · ${plural(itens.length, "resultado", "resultados")}`];
      return ["exato", `Nenhum com o nome exato (${r.itens.length} parecidos escondidos)`];
    case "soldout": return ["soldout", "Cadastrada, mas indisponível"];
    case "none": return ["none", "Não encontrada"];
    case "blocked": return ["blocked", "⚠ A loja bloqueou a leitura: abra no navegador"];
    case "unknown": return ["unknown", "⚠ Não consegui ler: abra no navegador"];
    default: return ["error", "⚠ Falha de conexão: abra no navegador" + (r.msg ? ` (${esc(r.msg.slice(0, 70))})` : "")];
  }
}

function qualidade(q) {
  const cls = ["M", "NM", "SP", "MP", "HP", "D"].includes(q) ? q : "outro";
  return q ? `<span class="etq q-${cls}">${esc(q)}</span>` : "";
}

const COLUNAS = '<colgroup><col class="c-edicao"><col class="c-idioma"><col class="c-qual"><col class="c-estoque"><col class="c-extras"><col class="c-preco"></colgroup>';

// bandeira que a própria loja usa para o idioma (só imagens da web, nunca outro tipo de endereço)
function bandeira(url, idioma) {
  if (!/^https:\/\/[^\s"'<>]+\.(svg|png|gif|jpg)$/i.test(url || "")) return "";
  return `<img class="bandeira" src="${esc(url)}" alt="" title="${esc(idioma)}" onerror="this.remove()">`;
}

function linhaOferta(o, itemUrl) {
  const extras = [];
  if (o.pre) {
    const dica = o.pre_data ? `Pré-venda: envio previsto para ${esc(o.pre_data)}` : "Pré-venda";
    extras.push(`<span class="etq pre" title="${dica}">Pré-venda${o.pre_data ? " · " + esc(o.pre_data) : ""}</span>`);
  }
  if (o.extras) {
    const foil = /foil/i.test(o.extras);
    extras.push(`<span class="etq ${foil ? "foil" : "q-outro"}">${esc(o.extras.replace(/\s*,\s*/g, ", "))}</span>`);
  }
  if (o.promo) extras.push(`<span class="etq promo">-${o.promo}%</span>`);
  if (o.obs) extras.push(`<span class="etq obs" title="Observação da loja:
${esc(o.obs)}">Contém obs.</span>`);
  const riscado = o.preco_original ? `<span class="riscado">${dinheiro(o.preco_original)}</span>` : "";
  const lang = o.idioma === "Português" ? "pt" : "en";
  return `<tr class="oferta" data-abrir="${esc(itemUrl)}" title="Clique para abrir a página na loja">
    <td class="edicao">${esc(o.edicao)}</td>
    <td class="${lang}">${bandeira(o.bandeira, o.idioma)}${esc(o.idioma || "—")}</td>
    <td>${qualidade(o.qualidade)}</td>
    <td class="un">${o.estoque ?? "?"} un.</td>
    <td class="extras">${extras.join(" ")}</td>
    <td class="preco">${riscado}${dinheiro(o.preco)}</td></tr>`;
}

function blocoItem(r, it) {
  const k = chave(r.loja.url, it.url);
  const abrir = `<button class="abrir" data-abrir="${esc(it.url)}" title="Abrir a página do produto na loja">Abrir ↗</button>`;
  if (it.ofertas) {
    const aberto = tela.abertos[k] ?? !tela.recolhido;
    if (!it.ofertas.length) {
      return `<div class="item"><div class="item-cab"><span class="seta"></span><span class="item-nome">${esc(it.nome)}</span>
        <span class="info">sem ofertas em estoque no momento</span>${abrir}</div></div>`;
    }
    const precos = it.ofertas.map((o) => o.preco).filter((p) => p != null);
    const menor = precos.length ? `a partir de <b>${dinheiro(Math.min(...precos))}</b>` : "";
    return `<div class="item${aberto ? "" : " fechado"}"><div class="item-cab" data-alternar="${esc(k)}">
        <span class="seta">▾</span><span class="item-nome">${esc(it.nome)}</span>
        <span class="info">${plural(it.ofertas.length, "oferta", "ofertas")} · ${menor}</span>${abrir}</div>
      <div class="corpo"><table>${COLUNAS}${it.ofertas.map((o) => linhaOferta(o, it.url)).join("")}</table></div></div>`;
  }
  const d = tela.detalhes[k];
  let direita;
  if (tela.carregando[it.url] || (d && d.estado === "carregando")) {
    direita = '<span class="info"><span class="girando"></span>carregando edições e preços…</span>';
  } else {
    direita = `<span class="info"></span><button class="pedir" data-detalhes="${esc(k)}">Ver edições e preços</button>`;
  }
  const msg = d && d.estado === "erro" ? `<div class="msg aviso">${esc(d.msg)}</div>` : "";
  return `<div class="item"><div class="item-cab" data-detalhes="${esc(k)}"><span class="seta">▸</span>
    <span class="item-nome">${esc(it.nome)}</span>${direita}${abrir}</div>${msg}</div>`;
}

function blocoLoja(url) {
  const r = tela.res[url];
  const [cls, texto] = textoStatus(r);
  const itens = visiveis(r);
  const n = cfg.itens_por_loja;
  const grande = itens.length > n;
  const tudo = grande && tela.expandidas[url];
  const mostrar = tudo || !grande ? itens : itens.slice(0, n);
  const fechada = tela.fechadas[url] ?? false;
  let corpo = mostrar.map((it) => blocoItem(r, it)).join("");
  if (grande) {
    corpo += tudo ? `<button class="mais" data-mais="${esc(url)}">▲ Mostrar menos</button>`
      : `<button class="mais" data-mais="${esc(url)}">▼ Mostrar mais ${itens.length - n}</button>`;
  }
  const temItens = mostrar.length > 0;
  const apagada = ["none", "soldout", "exato"].includes(cls);  // sem a carta: fica mais clara que as outras
  const corOk = (c) => /^#[0-9a-f]{6}$/i.test(c || "");
  const cor = corOk(r.loja.cor) ? r.loja.cor : "#6b7280";  // cor da loja: faixa, fundo e botões
  const cor2 = corOk(r.loja.cor2) ? r.loja.cor2 : cor;      // segunda cor da logo (Deckmaster: amarelo)
  const logo = /^https:\/\/[^\s"'<>]+\.(jpg|jpeg|png|gif|webp|svg)$/i.test(r.loja.logo || "")
    ? `<img class="logo" src="${esc(r.loja.logo)}" alt="" onerror="this.remove()">` : "";
  return `<div class="cartao${fechada || !temItens ? " fechado" : ""}${apagada ? " apagada" : ""}" style="--cor-loja:${cor};--cor-loja2:${cor2}">
    <div class="cab" data-loja="${esc(url)}"><span class="seta">${temItens ? "▾" : ""}</span>
      ${logo}<span class="nome">${esc(r.loja.nome)}</span><span class="status st-${cls}">${texto}</span>
      <button class="abrir" data-abrir="${esc(r.url_busca)}" title="Abrir esta busca no navegador">Abrir no navegador ↗</button></div>
    <div class="corpo">${corpo}</div></div>`;
}

function desenhar() {
  const area = $("resultados");
  const rolagem = area.scrollTop;
  if (!tela.ordem.length) {
    area.innerHTML = `<div class="vazio"><div class="grande">🃏</div><p>Digite o nome de uma carta e clique em <b>Buscar</b>.<br>
      Você vê em quais lojas marcadas há estoque, com edição, idioma, qualidade e preço.</p></div>`;
  } else {
    area.innerHTML = tela.ordem.map(blocoLoja).join("");
  }
  area.scrollTop = rolagem;
  desenharProgresso();
  if (tela.ordem.length && tela.pendentes === 0) resumir();
}

function desenharProgresso() {
  const total = Math.max(1, tela.lojasTotal + tela.autoTotal);
  const feito = Math.min(total, tela.lojasFeitas + tela.autoFeito);
  const ativo = tela.pendentes > 0 || tela.autoAtivo > 0;
  $("progresso").classList.toggle("ativo", ativo);
  $("barra").style.width = ativo ? `${(feito / total) * 100}%` : "0";
}

function resumir() {
  const rs = tela.ordem.map((u) => tela.res[u]).filter(Boolean);
  const ok = rs.filter(temCarta).length;
  const conferir = rs.filter((r) => ["blocked", "unknown", "error"].includes(r.status)).length;
  let msg = `“${tela.carta}”: encontrada em ${ok} de ${plural(rs.length, "loja", "lojas")}`;
  msg += tela.exato && tela.nomes ? " (nome exato)." : ".";
  if (tela.autoAtivo > 0) {
    msg += ` Carregando edições e preços (${tela.autoFeito}/${tela.autoTotal})…`;
  } else if (rs.some((r) => temCarta(r) && visiveis(r).some((i) => !i.ofertas))) {
    msg += " Onde há muitos resultados, edições e preços não carregam sozinhos: clique em “Ver edições e preços”.";
  }
  if (tela.aviso) msg += " " + tela.aviso;
  if (tela.exato && tela.nomes && !tela.nomesOk) msg += " Scryfall indisponível: filtrando só pelo texto digitado.";
  if (conferir) msg += ` ${plural(conferir, "loja não pôde ser lida", "lojas não puderam ser lidas")}: confira no navegador.`;
  const seg = (Date.now() - tela.tempo) / 1000;
  if (seg >= 120) msg += ` 🕒 Resultados ${idade(seg)}.`;
  if (ok) msg += " Clique numa edição para abrir a página na loja. Do menor para o maior preço.";
  avisar(msg, Boolean(tela.aviso || conferir));
  $("abrir-achadas").disabled = !(ok || conferir);
}

/* ---------------- cliques nos resultados ---------------- */
// abre a página uma vez só, mesmo com clique duplo (ou cliques seguidos) no mesmo link
let ultimaAberta = { url: "", quando: 0 };
function abrirUmaVez(url) {
  const agora = Date.now();
  if (url === ultimaAberta.url && agora - ultimaAberta.quando < 1500) return;
  ultimaAberta = { url, quando: agora };
  api().abrir(url);
}
$("resultados").addEventListener("click", (e) => {
  const abrir = e.target.closest(".abrir, tr.oferta");
  if (abrir) { abrirUmaVez(abrir.dataset.abrir); return; }
  const mais = e.target.closest("[data-mais]");
  if (mais) {
    const url = mais.dataset.mais;
    tela.expandidas[url] = !tela.expandidas[url];
    desenhar();
    return;
  }
  const det = e.target.closest("[data-detalhes]");
  if (det) { carregarDetalhes(det.dataset.detalhes); return; }
  const alt = e.target.closest("[data-alternar]");
  if (alt) {
    const k = alt.dataset.alternar;
    tela.abertos[k] = !(tela.abertos[k] ?? !tela.recolhido);
    desenhar();
    return;
  }
  const loja = e.target.closest("[data-loja]");
  if (loja) {
    const url = loja.dataset.loja;
    tela.fechadas[url] = !tela.fechadas[url];
    desenhar();
  }
});

async function carregarDetalhes(k) {
  const t = tela;
  const sep = k.indexOf("|");  // a url da loja não tem "|"
  const lojaUrl = k.slice(0, sep), itemUrl = k.slice(sep + 1);
  if (t.carregando[itemUrl] || (t.detalhes[k] && t.detalhes[k].estado === "carregando")) return;
  t.detalhes[k] = { estado: "carregando" };
  desenhar();
  const r = await api().detalhes(lojaUrl, itemUrl);
  const it = t.res[lojaUrl] && t.res[lojaUrl].itens.find((i) => i.url === itemUrl);
  if (r.status === "ok" || r.status === "empty") {
    delete t.detalhes[k];
    if (it) it.ofertas = r.ofertas;
    t.abertos[k] = true;
  } else {
    const msgs = {
      unreadable: "⚠ A loja não entregou estoque e preço como texto nesta página. Use “Abrir ↗”.",
      blocked: "⚠ A loja bloqueou a leitura. Use “Abrir ↗”.",
    };
    t.detalhes[k] = { estado: "erro", msg: msgs[r.status] || `⚠ Falha de conexão: ${r.msg || ""}` };
  }
  if (t === tela) desenhar();
}

function textoRecolher(recolhido) {
  $("recolher").textContent = recolhido ? "▼ Expandir tudo" : "▲ Recolher tudo";
}

function alternarRecolher() {
  tela.recolhido = !tela.recolhido;
  tela.abertos = {};
  if (tela.recolhido) tela.expandidas = {};
  textoRecolher(tela.recolhido);
  desenhar();
}

/* ---------------- histórico (Voltar / Avançar) ---------------- */
function atualizarNavegacao() {
  for (const [pilha, botao, vazio, rotulo, tecla] of [
    [historico, $("voltar"), "Não há busca anterior", "Voltar para", "Alt+←"],
    [avancar, $("avancar"), "Não há busca para avançar", "Avançar para", "Alt+→"]]) {
    botao.disabled = !pilha.length;
    if (!pilha.length) { botao.title = vazio; continue; }
    const s = pilha[pilha.length - 1];
    const seg = (Date.now() - s.tempo) / 1000;
    botao.title = `${rotulo} “${s.carta}” (${tecla})` +
      (seg > cfg.velho_depois ? `\nResultados ${idade(seg)}: a busca será refeita` : "");
  }
}

async function navegar(origem, destino) {
  if (!origem.length) return;
  const snap = origem.pop();
  if (telaCompleta()) {
    destino.push(clonar(tela));
    destino.splice(0, Math.max(0, destino.length - cfg.historico_max));
  }
  $("carta").value = snap.carta;
  $("exato").checked = snap.exato;
  if ((Date.now() - snap.tempo) / 1000 > cfg.velho_depois) {
    // resultados antigos (preço e estoque podem ter mudado): refaz a busca em vez de mostrá-los
    atualizarNavegacao();
    await buscar(true);
    return;
  }
  await api().cancelar();
  tela = snap;
  tela.sid = -1;  // nenhum acontecimento novo pertence a esta tela
  tela.carregando = {}; tela.autoAtivo = 0;
  for (const k of Object.keys(tela.detalhes)) if (tela.detalhes[k].estado === "carregando") delete tela.detalhes[k];
  textoRecolher(tela.recolhido);
  atualizarNavegacao();
  desenhar();
  $("carta").focus();
}
setInterval(atualizarNavegacao, 60000);  // as dicas dizem quando uma busca guardada ficou velha

/* ---------------- início ---------------- */
window.addEventListener("pywebviewready", async () => {
  cfg = await api().iniciar();
  lojas = cfg.lojas;
  $("auto").max = cfg.auto_max;
  $("auto").value = cfg.auto_limite;
  desenharLojas();
  desenhar();
  if (!cfg.tem_bibliotecas) {
    avisar("Para ver os resultados aqui dentro, instale: pip install requests beautifulsoup4 (enquanto isso, o botão 🌐 abre as lojas no navegador).");
  }
  $("colar").focus();
});
