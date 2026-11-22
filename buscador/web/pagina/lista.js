"use strict";
/* Busca de uma lista inteira (deck): a pessoa cola a lista, confere o que o programa entendeu e busca.
   O Python (Ponte.buscar_lista, buscador/lista.py) busca carta por carta, em cada loja, num ritmo mais
   lento; os resultados chegam por app.evento ("lista", "listapausa", "listaretoma", "listadesiste",
   "listafim") e ficam em tela.lista. A tela mostra duas vistas: por carta (uma coluna por loja) e por
   loja (o que comprar em cada uma). Clicar numa carta abre as comandas normais dela, sem nova busca;
   ◀ Voltar volta para a lista. */

let textoDaLista = "";  // o que a pessoa colou da última vez (para "Editar a lista")
let listaLida = null;   // {cartas, ignoradas} da prévia

/* ---------------- janela de colar a lista ---------------- */
function abrirJanelaLista() {
  $("lista-texto").value = textoDaLista;
  $("lista-erro").textContent = "";
  $("janela-lista").hidden = false;
  $("lista-texto").focus();
  lerListaColada();
}
function fecharJanelaLista() { $("janela-lista").hidden = true; }

let esperaLeitura = null;
function lerListaColada() {
  clearTimeout(esperaLeitura);
  esperaLeitura = setTimeout(async () => {
    textoDaLista = $("lista-texto").value;
    listaLida = await api().ler_lista(textoDaLista);
    desenharPrevia();
  }, 200);
}

function cartasParaBuscar() {
  if (!listaLida) return [];
  const semBasicos = $("lista-basicos").checked;
  return listaLida.cartas.filter((c) => !(semBasicos && c.basico));
}

function tempoTexto(seg) {
  if (seg < 50) return "menos de 1 minuto";
  const min = Math.round(seg / 60);
  return min <= 1 ? "cerca de 1 minuto" : `cerca de ${min} minutos`;
}

function desenharPrevia() {
  const cartas = cartasParaBuscar();
  const todas = listaLida ? listaLida.cartas : [];
  const basicos = todas.filter((c) => c.basico);
  const ignoradas = listaLida ? listaLida.ignoradas : [];
  const nLojas = lojas.filter((l) => l.marcada).length;
  const linhas = todas.map((c) => {
    const fora = c.basico && $("lista-basicos").checked;
    return `<div class="${fora ? "fora" : ""}">${c.qtd} × ${esc(c.nome)}${fora ? " <i>(terreno básico)</i>" : ""}</div>`;
  });
  linhas.push(...ignoradas.map((l) => `<div class="nao-entendi" title="Esta linha não foi entendida como carta">? ${esc(l)}</div>`));
  $("lista-previa").innerHTML = linhas.length ? linhas.join("")
    : '<p class="vazia">Cole a lista ao lado: uma carta por linha, com ou sem a quantidade na frente.</p>';
  let info = "", erro = "";
  if (cartas.length) {
    const unidades = cartas.reduce((s, c) => s + c.qtd, 0);
    info = `${plural(cartas.length, "carta diferente", "cartas diferentes")} (${plural(unidades, "unidade", "unidades")})`;
    if (nLojas) info += ` · ${plural(nLojas, "loja", "lojas")} · ${tempoTexto(cartas.length * cfg.lista_seg_por_carta)}`;
    if (cartas.length > cfg.lista_max) erro = `São ${cartas.length} cartas diferentes; o máximo por lista é ${cfg.lista_max}.`;
    else if (!nLojas) erro = "Marque ao menos uma loja na lousa.";
  }
  if (basicos.length) $("lista-basicos-n").textContent = `(${basicos.length})`;
  $("lista-basicos").closest("label").hidden = !basicos.length;
  $("lista-ignoradas").textContent = ignoradas.length ? `${plural(ignoradas.length, "linha não entendida", "linhas não entendidas")} (marcadas com ?) fica de fora.` : "";
  $("lista-info").textContent = info;
  $("lista-erro").textContent = erro;
  $("lista-buscar").disabled = !cartas.length || Boolean(erro);
}

$("lista").onclick = abrirJanelaLista;
$("lista-cancelar").onclick = fecharJanelaLista;
$("janela-lista").addEventListener("mousedown", (e) => { if (e.target === $("janela-lista")) fecharJanelaLista(); });
$("lista-texto").addEventListener("input", lerListaColada);
$("lista-basicos").addEventListener("change", desenharPrevia);
$("lista-buscar").onclick = async () => {
  const cartas = cartasParaBuscar();
  if (!cartas.length) return;
  if (await buscarLista(cartas)) fecharJanelaLista();
};
$("lista-texto").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && e.ctrlKey && !$("lista-buscar").disabled) $("lista-buscar").click();
});

/* ---------------- busca ---------------- */
async function buscarLista(cartas, semHistorico = false) {
  if (!semHistorico) guardarNoHistorico("\u0000lista");
  const r = await api().buscar_lista(cartas.map((c) => ({ qtd: c.qtd, nome: c.nome })));
  if (r.erro === "sem_bibliotecas") {
    $("lista-erro").textContent = "Para buscar aqui dentro é preciso instalar: pip install requests beautifulsoup4.";
    return false;
  }
  if (r.erro) { $("lista-erro").textContent = r.erro; avisar(r.erro); return false; }
  tela = novaTela();
  tela.sid = r.sid;
  tela.carta = `Lista de ${plural(r.cartas.length, "carta", "cartas")}`;
  tela.nomes = [];  // não há "Apenas nome exato" a consultar: a lista já só traz o nome exato
  tela.ordem = r.lojas.map((l) => l.url);
  tela.lojasTotal = tela.pendentes = r.lojas.length;
  tela.lista = {
    cartas: r.cartas, lojas: r.lojas, vista: "carta", inicio: Date.now(),
    res: Object.fromEntries(r.lojas.map((l) => [l.url, r.cartas.map(() => null)])),
    estado: Object.fromEntries(r.lojas.map((l) => [l.url, { feitas: 0, pausaAte: 0, tentativa: 0, fim: false, desistiu: false }])),
    cancelada: false,
  };
  $("carta").value = "";
  atualizarNavegacao();
  desenhar();
  api().comecar_lista(r.sid);  // só agora: os resultados já têm onde chegar
  return true;
}

function lojaTerminou(e) { return e.fim || e.desistiu; }

function eventoLista(tipo, d) {
  const L = tela.lista;
  if (!L) return;
  const e = L.estado[d.loja];
  if (!e || lojaTerminou(e)) return;
  if (tipo === "lista") {
    L.res[d.loja][d.i] = d.res;
    e.feitas = Math.max(e.feitas, d.i + 1);
  } else if (tipo === "listapausa") {
    e.pausaAte = Date.now() + d.segundos * 1000;
    e.tentativa = d.tentativa;
    ligarRelogioLista();
  } else if (tipo === "listaretoma") {
    e.pausaAte = 0;
  } else if (tipo === "listadesiste" || tipo === "listafim") {
    e.pausaAte = 0;
    if (tipo === "listafim") e.fim = true; else e.desistiu = true;
    tela.pendentes = Math.max(0, tela.pendentes - 1);
    tela.lojasFeitas += 1;
  }
}

async function cancelarLista() {
  const L = tela.lista;
  if (!L || !tela.pendentes) return;
  await api().cancelar();
  L.cancelada = true;
  for (const e of Object.values(L.estado)) { if (!lojaTerminou(e)) { e.desistiu = true; e.pausaAte = 0; } }
  tela.sid = -1;
  tela.pendentes = 0;
  desenhar();
}

// relógio das lojas pausadas: só os números mudam (sem redesenhar a tela)
let relogioLista = null;
function ligarRelogioLista() {
  if (relogioLista) return;
  relogioLista = setInterval(() => {
    const els = document.querySelectorAll("[data-volta-em]");
    if (!els.length && !(tela.lista && Object.values(tela.lista.estado).some((e) => e.pausaAte > Date.now()))) {
      clearInterval(relogioLista); relogioLista = null; return;
    }
    els.forEach((el) => { el.textContent = Math.max(0, Math.ceil((+el.dataset.voltaEm - Date.now()) / 1000)); });
  }, 500);
}

/* ---------------- contas de cada carta em cada loja ---------------- */
// Junta as edições da carta na loja, do menor para o maior preço, até a quantidade pedida.
// Pré-venda e edições sem preço ficam de fora da conta (aparecem ao abrir a carta).
function contaCarta(r, qtd, naoVerificada) {
  if (!r) return { estado: naoVerificada ? "nao_verificada" : "pendente" };
  if (r.status === "found") {
    const ofertas = [];
    let semLer = false;
    for (const it of r.itens) {
      if (!it.ofertas) { semLer = true; continue; }
      for (const o of it.ofertas) {
        const un = typeof o.estoque === "number" ? o.estoque : 1;
        if (o.preco != null && !o.pre && un > 0) ofertas.push({ preco: o.preco, un, url: it.url, o });
      }
    }
    if (!ofertas.length) return semLer ? { estado: "sem_preco", url: r.itens[0] && r.itens[0].url, urls: r.itens.map((i) => i.url) } : { estado: "nao_tem" };
    ofertas.sort((a, b) => a.preco - b.preco);
    const tem = ofertas.reduce((s, o) => s + o.un, 0);
    let falta = qtd, custo = 0;
    const partes = [], urls = [];
    for (const o of ofertas) {
      if (!falta) break;
      const n = Math.min(falta, o.un);
      custo += n * o.preco; falta -= n;
      partes.push({ n, preco: o.preco, o: o.o, url: o.url });
      if (!urls.includes(o.url)) urls.push(o.url);
    }
    return { estado: tem >= qtd ? "completa" : "parcial", tem, leva: qtd - falta, custo, menor: ofertas[0].preco, url: urls[0], urls, partes, primeira: ofertas[0].o };
  }
  if (r.status === "none" || r.status === "soldout") return { estado: "nao_tem" };
  return { estado: "erro" };
}

function contas() {
  const L = tela.lista;
  return L.cartas.map((c, i) => Object.fromEntries(L.lojas.map((l) => {
    const e = L.estado[l.url];
    return [l.url, contaCarta(L.res[l.url][i], c.qtd, e.desistiu)];
  })));
}

const textoOferta = (o) => [o.idioma, o.qualidade, o.extras, o.edicao].filter(Boolean).join(", ");
const textoPartes = (cc) => cc.partes.map((p) => `${p.n} × ${dinheiro(p.preco)} (${textoOferta(p.o)})`).join(" + ");

// idioma (com a bandeira da loja), estado e extras de uma oferta, como nas comandas
function detalhesOferta(o, curto = false) {
  const extras = [];
  if (o.extras) extras.push(`<span class="etq ${/foil/i.test(o.extras) ? "foil" : "q-outro"}">${esc(o.extras.replace(/\s*,\s*/g, ", "))}</span>`);
  if (o.promo) extras.push(`<span class="etq promo">-${o.promo}%</span>`);
  const idioma = curto ? bandeira(o.bandeira, o.idioma) || `<span class="idioma-curto">${esc((o.idioma || "").slice(0, 3))}</span>`
    : `${bandeira(o.bandeira, o.idioma)}<span class="idioma">${esc(o.idioma || "—")}</span>`;
  return `<span class="det-oferta">${idioma}${qualidade(o.qualidade)}${extras.join("")}</span>`;
}
const corDaLoja = (l) => (/^#[0-9a-f]{6}$/i.test(l.cor || "") ? l.cor : "#6b7280");

/* ---------------- desenho ---------------- */
function desenharLista() {
  const L = tela.lista;
  const cs = contas();
  const abas = `<div class="lista-abas">
      <button class="aba${L.vista === "carta" ? " ativa" : ""}" data-vista="carta">Por carta</button>
      <button class="aba${L.vista === "loja" ? " ativa" : ""}" data-vista="loja">Por loja</button>
      <span class="lista-acoes">${tela.pendentes ? '<button class="btn pequeno" data-lista-cancelar>Cancelar a busca</button>' : ""}
      <button class="link" data-lista-editar>Editar a lista</button></span></div>`;
  return `<div class="lista${tela.pendentes ? " rodando" : ""}">${andamento(L)}${avisoFaltando(L, cs)}${abas}${L.vista === "carta" ? vistaPorCarta(L, cs) : vistaPorLoja(L, cs)}</div>`;
}

// cartas que nenhuma loja tem (só depois que a busca termina: antes, ainda podem aparecer)
function cartasFaltando(L, cs) {
  if (tela.pendentes) return [];
  return L.cartas.filter((c, i) => L.lojas.every((l) => ["nao_tem", "erro"].includes(cs[i][l.url].estado)));
}

// aviso no alto do resultado, com o botão para copiar a lista do que falta (para a pessoa atualizar as anotações)
function avisoFaltando(L, cs) {
  const faltam = cartasFaltando(L, cs);
  if (!faltam.length) return "";
  return `<div class="faltando-lista"><span class="fl-texto">⚠ Nenhuma loja tem ${faltam.length === 1 ? "esta carta" : `estas ${faltam.length} cartas`}:
      <b>${faltam.map((c) => esc(c.nome)).join(", ")}</b></span>
    <button class="btn pequeno" data-copiar-faltando title="Copia as cartas que nenhuma loja tem, no formato de lista (quantidade e nome), para colar nas suas anotações">📋 Copiar a lista das que faltam</button></div>`;
}

function andamento(L) {
  if (!tela.pendentes) return "";
  const n = L.cartas.length, agora = Date.now();
  const ativas = L.lojas.filter((l) => !lojaTerminou(L.estado[l.url]));
  const andando = ativas.filter((l) => !(L.estado[l.url].pausaAte > agora));
  const passou = (agora - L.inicio) / 1000;
  const mais = Math.max(1, ...L.lojas.map((l) => L.estado[l.url].feitas));
  const porCarta = mais >= 2 ? passou / mais : cfg.lista_seg_por_carta;
  // falta: a loja mais atrasada, contando a espera de quem está pausada
  const resta = Math.max(0, ...ativas.map((l) => {
    const e = L.estado[l.url];
    return (n - e.feitas) * porCarta + Math.max(0, (e.pausaAte - agora) / 1000);
  }));
  const menos = andando.length ? Math.min(...andando.map((l) => L.estado[l.url].feitas)) : n;
  const titulo = andando.length
    ? `Carta ${Math.min(n, menos + 1)} de ${n}${L.cartas[menos] ? ` · ${esc(L.cartas[menos].nome)}` : ""}`
    : "As lojas pediram para ir devagar: elas voltam sozinhas…";
  const feitasTodas = L.lojas.reduce((s, l) => s + (lojaTerminou(L.estado[l.url]) ? n : L.estado[l.url].feitas), 0);
  const chips = L.lojas.map((l) => {
    const e = L.estado[l.url];
    let t = `${e.feitas}/${n}`, cls = "";
    if (e.fim) { t = "✓ pronta"; cls = "ok"; } else if (e.desistiu) { t = "parou"; cls = "parou"; } else if (e.pausaAte > Date.now()) {
      t = `pausada, volta em <span data-volta-em="${e.pausaAte}">${Math.ceil((e.pausaAte - Date.now()) / 1000)}</span> s`; cls = "pausa";
    }
    return `<span class="chip-loja ${cls}" style="--cor-loja:${corDaLoja(l)}">${esc(l.nome)} · ${t}</span>`;
  }).join("");
  const pct = (feitasTodas / (n * L.lojas.length)) * 100;
  return `<div class="lista-andamento">
      <div class="la-linha"><span><span class="girando"></span>${titulo}</span>
      <span class="la-resta">${tempoTexto(resta).replace("cerca de", "faltam cerca de").replace("menos de 1 minuto", "falta menos de 1 minuto")}</span></div>
      <div class="la-barra"><div style="width:${pct}%"></div></div>
      <div class="la-lojas">${chips}</div></div>`;
}

function celula(cc, melhor) {
  switch (cc.estado) {
    case "pendente": return '<td class="cel pendente">…</td>';
    case "nao_verificada": return '<td class="cel nao-verif" title="A busca parou antes de chegar nesta carta">não verificada</td>';
    case "erro": return '<td class="cel erro" title="Não consegui ler a busca desta carta: abra a carta para ver">⚠ não li</td>';
    case "nao_tem": return '<td class="cel nao-tem">não tem</td>';
    case "sem_preco": return `<td class="cel sem-preco" data-abrir-cel="${esc(cc.url)}" title="A loja tem a carta, mas o preço não foi lido.\nClique para abrir a página da carta nesta loja">tem · preço ? <span class="seta-abrir">↗</span></td>`;
  }
  const dica = `${textoPartes(cc)} = ${dinheiro(cc.custo)}${cc.estado === "parcial" ? ` (a loja só tem ${cc.tem})` : ""}`;
  const un = cc.estado === "parcial" ? `<span class="falta">tem ${cc.tem}</span>` : `<span class="un">${cc.tem} un.</span>`;
  return `<td class="cel ${cc.estado}${melhor ? " melhor" : ""}" data-abrir-cel="${esc(cc.url)}" title="${esc(dica)}${melhor ? "\nMais barata para esta carta" : ""}\nClique para abrir a página da carta nesta loja">
    <div class="cel-linha"><span class="preco">${dinheiro(cc.menor)}</span>${un}<span class="seta-abrir">↗</span></div>${detalhesOferta(cc.primeira)}</td>`;
}

// url da loja mais barata para a carta i, entre as que têm a quantidade toda (null se só uma ou nenhuma tem)
function melhorLoja(L, cs, i) {
  const completas = L.lojas.filter((l) => cs[i][l.url].estado === "completa");
  return completas.length > 1 ? completas.reduce((a, b) => (cs[i][b.url].custo < cs[i][a.url].custo ? b : a)).url : null;
}

function vistaPorCarta(L, cs) {
  const cab = L.lojas.map((l) => `<th class="th-loja" style="--cor-loja:${corDaLoja(l)}">${esc(l.nome)}</th>`).join("");
  const linhas = L.cartas.map((c, i) => {
    const melhor = melhorLoja(L, cs, i);
    const nenhuma = !tela.pendentes && L.lojas.every((l) => ["nao_tem", "erro"].includes(cs[i][l.url].estado));
    return `<tr class="${nenhuma ? "ninguem" : ""}"><td class="carta-lista" data-carta-lista="${i}" title="Ver as edições desta carta em cada loja">
        <span class="qtd">${c.qtd} ×</span> <span class="nome-arte" data-arte="${esc(c.nome)}">${esc(c.nome)}</span></td>
      ${L.lojas.map((l) => celula(cs[i][l.url], l.url === melhor)).join("")}</tr>`;
  }).join("");
  const totais = L.lojas.map((l) => {
    const cc = cs.map((x) => x[l.url]);
    const custo = cc.reduce((s, x) => s + (x.custo || 0), 0);
    const completas = cc.filter((x) => x.estado === "completa").length;
    const emParte = cc.filter((x) => x.estado === "parcial").length;
    const dica = `Esta loja tem ${completas} das ${L.cartas.length} cartas da lista na quantidade pedida` +
      (emParte ? ` e mais ${emParte} em quantidade menor que a pedida` : "") + ".\nO valor soma o que ela tem, até a quantidade pedida.";
    return `<td class="total" title="${esc(dica)}"><b>${dinheiro(custo)}</b><span>tem ${completas} das ${L.cartas.length} cartas</span>` +
      (emParte ? `<span class="em-parte">+ ${emParte} sem a quantidade toda</span>` : "") + "</td>";
  }).join("");
  return `<table class="tabela-lista"><colgroup><col class="c-carta">${L.lojas.map(() => "<col>").join("")}</colgroup>
    <thead><tr><th>Carta</th>${cab}</tr></thead><tbody>${linhas}</tbody>
    <tfoot><tr><td class="total-rotulo" title="Quanto custa comprar em cada loja o que ela tem da lista, até a quantidade pedida">Total do que a loja tem</td>${totais}</tr></tfoot></table>`;
}

function vistaPorLoja(L, cs) {
  return L.lojas.map((l, k) => {
    const tem = [], faltam = [];
    L.cartas.forEach((c, i) => {
      const cc = cs[i][l.url];
      if (["completa", "parcial", "sem_preco"].includes(cc.estado)) tem.push({ c, i, cc });
      if (cc.estado !== "completa" && cc.estado !== "pendente") faltam.push({ c, cc });
    });
    const custo = tem.reduce((s, x) => s + (x.cc.custo || 0), 0);
    const urls = [...new Set(tem.flatMap((x) => x.cc.urls || []))];
    const linhas = tem.map(({ c, i, cc }) => {
      const qtd = cc.estado === "sem_preco" ? `${c.qtd} × ?`
        : (cc.estado === "parcial" ? `<div><span class="falta">só ${cc.leva} de ${c.qtd}</span></div>` : "") +
          cc.partes.map((p) => `<div class="parte" title="${esc(p.o.edicao || "")}"><span class="parte-qtd">${p.n} × ${dinheiro(p.preco)}</span>${detalhesOferta(p.o)}</div>`).join("");
      return `<tr><td class="carta-lista" data-carta-lista="${i}" title="Ver as edições desta carta"><span class="qtd">${c.qtd} ×</span> <span class="nome-arte" data-arte="${esc(c.nome)}">${esc(c.nome)}</span></td>
        <td class="partes">${qtd}</td><td class="preco">${melhorLoja(L, cs, i) === l.url ? '<span class="estrela" title="Mais barata para esta carta, entre as lojas que têm a quantidade toda">★</span> ' : ""}${cc.custo != null ? dinheiro(cc.custo) : "—"}</td>
        <td><button class="abrir" data-abrir="${esc(cc.url)}" title="Abrir a página da carta nesta loja">Abrir ↗</button></td></tr>`;
    }).join("");
    const e = L.estado[l.url];
    const nota = e.desistiu && !L.cancelada ? '<div class="nota-loja">⚠ Esta loja pediu para ir devagar várias vezes e a busca parou nela: as cartas que faltavam ficaram sem verificar.</div>' : "";
    const corpo = tem.length ? `<table class="tabela-loja"><tbody>${linhas}</tbody></table>` : '<div class="nota-loja">Nenhuma carta da lista nesta loja (até agora).</div>';
    const faltaTxt = faltam.length ? `<div class="faltam">Faltam aqui: ${faltam.map(({ c, cc }) => esc(`${cc.estado === "parcial" ? c.qtd - cc.leva : c.qtd} ${c.nome}`)).join(", ")}</div>` : "";
    const logo = /^https:\/\/[^\s"'<>]+\.(jpg|jpeg|png|gif|webp|svg)$/i.test(l.logo || "") ? `<img class="logo" src="${esc(l.logo)}" alt="" onerror="this.remove()">` : "";
    const cor = corDaLoja(l), cor2 = /^#[0-9a-f]{6}$/i.test(l.cor2 || "") ? l.cor2 : cor;
    return `<div class="cartao loja-lista${tem.length ? "" : " apagada"}" style="--cor-loja:${cor};--cor-loja2:${cor2}">
      <div class="cab">${logo}<span class="nome">${esc(l.nome)}</span><span class="pedido">nº ${k + 1}</span>
        <span class="status st-found">${plural(tem.length, "carta", "cartas")} · <b>${dinheiro(custo)}</b></span>
        ${urls.length ? `<button class="abrir" data-abrir-todas="${esc(l.url)}" title="Abre a página de cada carta desta loja no navegador">Abrir todas (${urls.length}) ↗</button>` : ""}
        ${faltam.length ? `<button class="abrir" data-copiar-falta="${esc(l.url)}" title="Copia as cartas que faltam nesta loja, no formato de lista">Copiar o que falta</button>` : ""}</div>
      <div class="corpo">${nota}${corpo}${faltaTxt}</div></div>`;
  }).join("");
}

/* ---------------- rodapé ---------------- */
function resumirLista() {
  const L = tela.lista;
  const cs = contas();
  const n = L.cartas.length;
  const completas = cs.filter((x) => L.lojas.some((l) => x[l.url].estado === "completa")).length;
  const linhas = [{ texto: `Lista de ${plural(n, "carta", "cartas")}: ${completas} ${completas === 1 ? "tem" : "têm"} a quantidade toda em alguma loja.` +
    (L.cancelada ? " (busca cancelada: parte das cartas não foi verificada)" : ""), tipo: "principal" }];
  const paradas = L.lojas.filter((l) => L.estado[l.url].desistiu && !L.cancelada);
  if (paradas.length) linhas.push({ texto: `⚠ ${paradas.map((l) => l.nome).join(", ")}: pediu para ir devagar várias vezes e a busca parou ali. Tente de novo mais tarde.`, tipo: "aviso" });
  const semVer = L.cartas.filter((c, i) => L.lojas.some((l) => cs[i][l.url].estado === "nao_verificada")).length;
  if (semVer) linhas.push({ texto: `${plural(semVer, "carta ficou", "cartas ficaram")} sem verificar em alguma loja: busque a lista de novo mais tarde para completar.`, tipo: "aviso" });
  linhas.push({ texto: "Clique num preço para abrir a carta naquela loja, ou no nome da carta para ver as edições em cada loja (◀ Voltar volta para a lista).", tipo: "dica" });
  avisarLinhas(linhas);
  $("abrir-achadas").disabled = true;
}

/* ---------------- cliques ---------------- */
async function copiarTexto(texto) {
  try { await navigator.clipboard.writeText(texto); return true; } catch { /* tenta do jeito antigo */ }
  const area = document.createElement("textarea");
  area.value = texto; document.body.append(area); area.select();
  const ok = document.execCommand("copy");
  area.remove();
  return ok;
}

function abrirCartaDaLista(i) {
  const L = tela.lista;
  if (tela.pendentes) { avisar("Espere a lista terminar (ou cancele a busca) para abrir uma carta."); return; }
  const c = L.cartas[i];
  guardarNoHistorico("\u0000carta-da-lista");
  const t = novaTela();
  t.sid = -1;
  t.carta = c.nome;
  t.nomes = [];  // a lista já só guardou os itens com o nome exato
  for (const l of L.lojas) {
    const loja = { nome: l.nome, url: l.url, cor: l.cor, cor2: l.cor2, logo: l.logo, padrao: l.padrao };
    const r = L.res[l.url][i];
    t.ordem.push(l.url);
    t.res[l.url] = r ? clonar(r) : { loja, url_busca: "", status: "blocked", msg: "", itens: [] };
  }
  t.lojasTotal = t.lojasFeitas = L.lojas.length;
  tela = t;
  $("carta").value = c.nome;
  textoRecolher(false);
  atualizarNavegacao();
  desenhar();
  $("resultados").scrollTop = 0;
}

// devolve true se o clique era da lista
function cliqueNaLista(e) {
  if (!tela.lista) return false;
  const L = tela.lista;
  const aba = e.target.closest("[data-vista]");
  if (aba) { L.vista = aba.dataset.vista; desenhar(); return true; }
  if (e.target.closest("[data-lista-cancelar]")) { cancelarLista(); return true; }
  if (e.target.closest("[data-lista-editar]")) { abrirJanelaLista(); return true; }
  const todas = e.target.closest("[data-abrir-todas]");
  if (todas) {
    const cs = contas();
    const urls = [...new Set(L.cartas.flatMap((_, i) => cs[i][todas.dataset.abrirTodas].urls || []))];
    (async () => {
      if (urls.length > 10 && !(await perguntar(`Abrir ${urls.length} páginas?`,
        "Cada carta abre numa aba nova do navegador.", "Abrir todas"))) return;
      api().abrir(urls);
    })();
    return true;
  }
  const faltando = e.target.closest("[data-copiar-faltando]");
  if (faltando) {
    const texto = cartasFaltando(L, contas()).map((c) => `${c.qtd} ${c.nome}`).join("\n");
    copiarTexto(texto).then((ok) => {
      faltando.textContent = ok ? "✓ Copiado! Cole nas suas anotações" : "Não consegui copiar";
      setTimeout(() => { if (faltando.isConnected) faltando.textContent = "📋 Copiar a lista das que faltam"; }, 2500);
    });
    return true;
  }
  const copiar = e.target.closest("[data-copiar-falta]");
  if (copiar) {
    const cs = contas(), url = copiar.dataset.copiarFalta;
    const texto = L.cartas.map((c, i) => {
      const cc = cs[i][url];
      if (cc.estado === "completa" || cc.estado === "pendente") return "";
      return `${cc.estado === "parcial" ? c.qtd - cc.leva : c.qtd} ${c.nome}`;
    }).filter(Boolean).join("\n");
    copiarTexto(texto).then((ok) => {
      copiar.textContent = ok ? "✓ Copiado" : "Não consegui copiar";
      setTimeout(() => { if (copiar.isConnected) copiar.textContent = "Copiar o que falta"; }, 1800);
    });
    return true;
  }
  const cel = e.target.closest("[data-abrir-cel]");
  if (cel) { abrirUmaVez(cel.dataset.abrirCel); return true; }  // funciona já durante a busca
  const carta = e.target.closest("[data-carta-lista]");
  if (carta) { abrirCartaDaLista(+carta.dataset.cartaLista); return true; }
  return false;
}
