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
// Resultados de uma carta que podem ser reaproveitados ao editar a lista (a carta foi lida mesmo)
const reaproveitavel = (r) => r && ["found", "none", "soldout"].includes(r.status);

async function buscarLista(cartas, semHistorico = false) {
  // a lista na tela, se for recente: as cartas que continuam nela não são buscadas de novo
  const anterior = tela.lista && (Date.now() - tela.tempo) / 1000 <= cfg.velho_depois ? { lista: tela.lista, tempo: tela.tempo } : null;
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
  // reaproveita, de cada loja, as cartas já lidas na lista anterior (mesmo nome); o resto é buscado
  const antes = anterior ? new Map(anterior.lista.cartas.map((c, j) => [norm(c.nome), j])) : new Map();
  const res = {}, estado = {}, buscar = {};
  let reaproveitadas = 0;
  for (const l of r.lojas) {
    const velhos = anterior && anterior.lista.res[l.url];
    res[l.url] = r.cartas.map((c) => {
      const j = antes.get(norm(c.nome));
      const v = velhos && j !== undefined ? velhos[j] : null;
      return reaproveitavel(v) ? clonar(v) : null;
    });
    buscar[l.url] = res[l.url].map((v, i) => (v ? -1 : i)).filter((i) => i >= 0);
    reaproveitadas += r.cartas.length - buscar[l.url].length;
    estado[l.url] = { feitas: r.cartas.length - buscar[l.url].length, aBuscar: buscar[l.url].length, buscadas: 0,
      pausaAte: 0, tentativa: 0, fim: false, desistiu: false };
  }
  if (reaproveitadas) tela.tempo = anterior.tempo;  // vale a idade da busca mais antiga: depois de 30 min, refaz tudo
  tela.lista = { cartas: r.cartas, lojas: r.lojas, vista: anterior ? anterior.lista.vista : "carta", inicio: Date.now(),
    res, estado, cancelada: false, reaproveitadas };
  $("carta").value = "";
  atualizarNavegacao();
  desenhar();
  api().comecar_lista(r.sid, reaproveitadas ? buscar : null);  // só agora: os resultados já têm onde chegar
  return true;
}

function lojaTerminou(e) { return e.fim || e.desistiu; }

function eventoLista(tipo, d) {
  const L = tela.lista;
  if (!L) return;
  const e = L.estado[d.loja];
  if (!e || lojaTerminou(e)) return;
  if (tipo === "lista") {
    if (!L.res[d.loja][d.i]) e.feitas += 1;
    L.res[d.loja][d.i] = d.res;
    e.buscadas += 1;
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

// imagem da carta tirada das edições já lidas (a da loja pedida primeiro; senão, de qualquer loja).
// Com ela, a arte aparece na hora ao parar o mouse; sem ela, o Python consulta o Scryfall.
function imagemDaCarta(L, i, lojaUrl) {
  const urls = [lojaUrl, ...L.lojas.map((l) => l.url)].filter(Boolean);
  for (const u of urls) {
    const r = L.res[u] && L.res[u][i];
    for (const it of (r && r.itens) || []) {
      const img = (it.ofertas || []).map((o) => o.imagem).find(Boolean);
      if (img) return img;
    }
  }
  return "";
}

function nomeNaLista(L, c, i, lojaUrl = "") {
  const liga = c.liga ? `<button class="abrir liga" data-abrir="${esc(c.liga)}" title="Ver esta carta na LigaMagic, no navegador, para comparar preços">LigaMagic ↗</button>` : "";
  return `<span class="nome-linha"><span class="qtd">${c.qtd} ×</span> <span class="nome-arte" data-arte="${esc(c.nome)}" data-imagem="${esc(imagemDaCarta(L, i, lojaUrl))}">${esc(c.nome)}</span>${liga}</span>`;
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
      <button class="aba${L.vista === "carrinho" ? " ativa" : ""}" data-vista="carrinho">🛒 Carrinho mais barato</button>
      <span class="lista-acoes">${tela.pendentes ? '<button class="btn pequeno" data-lista-cancelar>Cancelar a busca</button>' : ""}
      <button class="link" data-lista-editar>Editar a lista</button></span></div>`;
  return `<div class="lista${tela.pendentes ? " rodando" : ""}">${andamento(L)}${avisoFaltando(L, cs)}${abas}${L.vista === "carta" ? vistaPorCarta(L, cs) : L.vista === "carrinho" ? vistaCarrinho(L, cs) : vistaPorLoja(L, cs)}</div>`;
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
    <button class="btn pequeno" data-copiar-faltando title="Copia as cartas que nenhuma loja tem, no formato de lista (quantidade e nome)">📋 Copiar lista de faltantes</button></div>`;
}

function andamento(L) {
  if (!tela.pendentes) return "";
  const n = L.cartas.length, agora = Date.now();
  const ativas = L.lojas.filter((l) => !lojaTerminou(L.estado[l.url]));
  const andando = ativas.filter((l) => !(L.estado[l.url].pausaAte > agora));
  const passou = (agora - L.inicio) / 1000;
  const mais = Math.max(1, ...L.lojas.map((l) => L.estado[l.url].buscadas));
  const porCarta = mais >= 2 ? passou / mais : cfg.lista_seg_por_carta;
  // falta: a loja mais atrasada, contando a espera de quem está pausada
  const resta = Math.max(0, ...ativas.map((l) => {
    const e = L.estado[l.url];
    return (e.aBuscar - e.buscadas) * porCarta + Math.max(0, (e.pausaAte - agora) / 1000);
  }));
  const menos = andando.length ? Math.min(...andando.map((l) => L.estado[l.url].feitas)) : n;
  // a carta da vez: a primeira ainda sem resultado na loja mais atrasada
  const atrasada = andando.find((l) => L.estado[l.url].feitas === menos);
  const proxima = atrasada ? L.res[atrasada.url].findIndex((v) => !v) : -1;
  const titulo = andando.length
    ? `Carta ${Math.min(n, menos + 1)} de ${n}${proxima >= 0 ? ` · ${esc(L.cartas[proxima].nome)}` : ""}` +
      (L.reaproveitadas ? ' <span class="la-reap">(as que já estavam na lista não são buscadas de novo)</span>' : "")
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
        ${nomeNaLista(L, c, i)}</td>
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
      return `<tr><td class="carta-lista" data-carta-lista="${i}" title="Ver as edições desta carta">${nomeNaLista(L, c, i, l.url)}</td>
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

/* ---------------- carrinho mais barato ---------------- */
// Escolhe de que loja comprar cada carta pelo menor total: as cartas mais o frete de cada loja usada
// (as lojas que vêm no programa têm frete grátis pela parceria; o frete vale só para as adicionadas).
// Primeiro o carrinho leva o máximo de unidades da lista; entre os que levam o mesmo, fica o mais barato
// (e, no empate, o de menos lojas). A mesma carta pode vir de duas lojas (2 aqui, 2 ali). Com frete,
// testa todas as combinações de lojas (até CARRINHO_MAX_LOJAS): o resultado é o melhor, não um palpite.
// Sem frete, comprar cada unidade onde ela é mais barata já é o melhor. Nenhuma requisição: usa o que a
// busca da lista já trouxe (as edições mais baratas de cada loja, até a quantidade pedida).
const CARRINHO_MAX_LOJAS = 12;

// cartas: [{qtd}]; unidades[i][url]: [{n, preco, o, url}]; lojas: [{url, frete}]
function montarCarrinho(cartas, unidades, lojas) {
  // todas as unidades de cada carta, do menor para o maior preço (de qualquer loja)
  const juntas = cartas.map((_, i) => lojas.flatMap((l, k) => (unidades[i][l.url] || []).map((p) => ({ ...p, k })))
    .sort((a, b) => a.preco - b.preco || a.k - b.k));
  const avaliar = (mascara) => {
    let un = 0, custo = 0, usadas = 0;
    const escolha = juntas.map((ps, i) => {
      let falta = cartas[i].qtd;
      const partes = [];
      for (const p of ps) {
        if (!falta) break;
        if (!(mascara & (1 << p.k))) continue;
        const n = Math.min(falta, p.n);
        partes.push({ ...p, n });
        custo += n * p.preco; falta -= n; usadas |= 1 << p.k;
      }
      un += cartas[i].qtd - falta;
      return partes;
    });
    const frete = lojas.reduce((s, l, k) => s + (usadas & (1 << k) ? l.frete : 0), 0);
    let nLojas = 0;
    for (let k = 0; k < lojas.length; k++) if (usadas & (1 << k)) nLojas++;
    return { un, custo, frete, total: custo + frete, nLojas, escolha };
  };
  const todas = (1 << lojas.length) - 1;
  const semEscolha = avaliar(todas);  // cada unidade onde é mais barata
  if (lojas.every((l) => !l.frete) || lojas.length > CARRINHO_MAX_LOJAS) return { melhor: semEscolha, semEscolha };
  let melhor = semEscolha;
  for (let m = 1; m < todas; m++) {
    const r = avaliar(m);
    if (r.un > melhor.un || (r.un === melhor.un && (r.total < melhor.total - 0.005 ||
        (Math.abs(r.total - melhor.total) <= 0.005 && r.nLojas < melhor.nLojas)))) melhor = r;
  }
  return { melhor, semEscolha };
}

let ultimoCarrinho = { urls: {}, faltam: "" };  // para os botões "Abrir todas" e "Copiar" do carrinho

function vistaCarrinho(L, cs) {
  const fora = L.fora || {};
  const frete = Math.max(0, Number(cfg.frete) || 0);
  const ativas = L.lojas.filter((l) => !fora[l.url]);
  const lojas = ativas.map((l) => ({ url: l.url, frete: l.padrao ? 0 : frete }));
  const unidades = L.cartas.map((_, i) => Object.fromEntries(ativas.map((l) => {
    const cc = cs[i][l.url];
    return [l.url, ["completa", "parcial"].includes(cc.estado) ? cc.partes : []];
  })));
  const { melhor, semEscolha } = montarCarrinho(L.cartas, unidades, lojas);

  // o que cada loja leva
  const porLoja = Object.fromEntries(ativas.map((l) => [l.url, []]));
  melhor.escolha.forEach((partes, i) => {
    for (const p of partes) {
      const url = lojas[p.k].url, linhas = porLoja[url];
      const ja = linhas.find((x) => x.i === i);
      if (ja) ja.partes.push(p); else linhas.push({ i, partes: [p] });
    }
  });
  ultimoCarrinho = { urls: {}, faltam: "" };

  const completas = melhor.escolha.filter((ps, i) => ps.reduce((s, p) => s + p.n, 0) >= L.cartas[i].qtd).length;
  const usadas = ativas.filter((l) => porLoja[l.url].length);
  const temAdicionadas = L.lojas.some((l) => !l.padrao);
  const parcial = tela.pendentes ? '<span class="cr-parcial">parcial: a busca ainda está andando</span>' : "";
  const freteTxt = melhor.frete ? ` <span class="cr-det">(cartas ${dinheiro(melhor.custo)} + frete ${dinheiro(melhor.frete)})</span>` : "";
  const campoFrete = temAdicionadas ? `<label class="cr-frete" title="As lojas que vêm no programa têm frete grátis (parceria). Este valor vale para cada loja que você adicionou e entra na conta: com frete, o carrinho tenta usar menos lojas.">
      Frete de cada loja adicionada: R$ <input type="number" min="0" max="500" step="1" value="${frete}" data-frete></label>` : "";
  const economia = semEscolha.un === melhor.un && semEscolha.total > melhor.total + 0.005
    ? `<div class="cr-compara">Comprando cada carta onde ela é mais barata: ${dinheiro(semEscolha.total)} em ${plural(semEscolha.nLojas, "loja", "lojas")} (com frete). Este carrinho economiza <b>${dinheiro(semEscolha.total - melhor.total)}</b>.</div>` : "";
  const tiradas = L.lojas.filter((l) => fora[l.url]);
  const foraTxt = tiradas.length ? `<div class="cr-fora">Fora do carrinho: ${tiradas.map((l) =>
    `<button class="link" data-devolver-loja="${esc(l.url)}" title="Pôr esta loja de volta no carrinho">↩ ${esc(l.nome)}</button>`).join(" ")}</div>` : "";
  const resumo = `<div class="carrinho-resumo">
      <div class="cr-linha"><span class="cr-total">Total: <b>${dinheiro(melhor.total)}</b>${freteTxt}</span>
        <span>em ${plural(usadas.length, "loja", "lojas")}</span><span>· ${completas} de ${L.cartas.length} cartas completas</span>${parcial}</div>
      ${campoFrete}${economia}${foraTxt}</div>`;

  const comandas = L.lojas.map((l, k) => {
    const linhas = porLoja[l.url];
    if (!linhas || !linhas.length) return "";
    const custo = linhas.reduce((s, x) => s + x.partes.reduce((t, p) => t + p.n * p.preco, 0), 0);
    const urls = [...new Set(linhas.flatMap((x) => x.partes.map((p) => p.url)))];
    ultimoCarrinho.urls[l.url] = urls;
    const corpo = linhas.map(({ i, partes }) => {
      const c = L.cartas[i];
      const aqui = partes.reduce((s, p) => s + p.n, 0);
      const divide = aqui < c.qtd ? `<div><span class="cr-divide">${aqui} de ${c.qtd} aqui</span></div>` : "";
      const sub = partes.reduce((s, p) => s + p.n * p.preco, 0);
      return `<tr><td class="carta-lista" data-carta-lista="${i}" title="Ver as edições desta carta em cada loja">${nomeNaLista(L, c, i, l.url)}</td>
        <td class="partes">${divide}${partes.map((p) => `<div class="parte" title="${esc(p.o.edicao || "")}"><span class="parte-qtd">${p.n} × ${dinheiro(p.preco)}</span>${detalhesOferta(p.o)}</div>`).join("")}</td>
        <td class="preco">${dinheiro(sub)}</td>
        <td><button class="abrir" data-abrir="${esc(partes[0].url)}" title="Abrir a página da carta nesta loja">Abrir ↗</button></td></tr>`;
    }).join("");
    const freteLoja = l.padrao ? '<span class="cr-gratis" title="Loja da parceria">frete grátis</span>' : frete ? `<span class="cr-det">+ frete ${dinheiro(frete)}</span>` : "";
    const logo = /^https:\/\/[^\s"'<>]+\.(jpg|jpeg|png|gif|webp|svg)$/i.test(l.logo || "") ? `<img class="logo" src="${esc(l.logo)}" alt="" onerror="this.remove()">` : "";
    const cor = corDaLoja(l), cor2 = /^#[0-9a-f]{6}$/i.test(l.cor2 || "") ? l.cor2 : cor;
    return `<div class="cartao loja-lista" style="--cor-loja:${cor};--cor-loja2:${cor2}">
      <div class="cab">${logo}<span class="nome">${esc(l.nome)}</span><span class="pedido">nº ${k + 1}</span>
        <span class="status st-found">${plural(linhas.length, "carta", "cartas")} · <b>${dinheiro(custo)}</b></span>${freteLoja}
        <button class="abrir" data-abrir-carrinho="${esc(l.url)}" title="Abre no navegador a página de cada carta que o carrinho leva desta loja">Abrir todas (${urls.length}) ↗</button>
        <button class="tirar-loja" data-tirar-loja="${esc(l.url)}" title="Tirar esta loja do carrinho (a conta é refeita sem ela)" aria-label="Tirar ${esc(l.nome)} do carrinho">✕</button></div>
      <div class="corpo"><table class="tabela-loja"><tbody>${corpo}</tbody></table></div></div>`;
  }).join("");

  const sobra = ativas.filter((l) => !porLoja[l.url].length);
  const sobraTxt = usadas.length && sobra.length ? `<div class="cr-sobra">Sem nada no carrinho: ${sobra.map((l) => esc(l.nome)).join(", ")}.</div>` : "";

  // cartas que o carrinho não completa
  const faltam = [];
  L.cartas.forEach((c, i) => {
    const leva = melhor.escolha[i].reduce((s, p) => s + p.n, 0);
    if (leva >= c.qtd) return;
    const estados = L.lojas.map((l) => cs[i][l.url].estado);
    const porque = leva ? `só ${leva} de ${c.qtd}`
      : estados.includes("pendente") ? "ainda buscando"
      : estados.includes("sem_preco") ? "preço não lido: abra a carta"
      : estados.includes("nao_verificada") || estados.includes("erro") ? "não verificada em alguma loja"
      : tiradas.length && tiradas.some((l) => ["completa", "parcial"].includes(cs[i][l.url].estado)) ? "só nas lojas tiradas"
      : "nenhuma loja tem";
    faltam.push({ c, falta: c.qtd - leva, porque });
  });
  ultimoCarrinho.faltam = faltam.map((x) => `${x.falta} ${x.c.nome}`).join("\n");
  const faltaTxt = faltam.length ? `<div class="faltando-lista cr-faltam"><span class="fl-texto">${faltam.length === 1 ? "1 carta não entra" : `${faltam.length} cartas não entram`} no carrinho:
      ${faltam.map((x) => `<b>${esc(x.c.nome)}</b> (${esc(x.porque)})`).join(", ")}</span>
    <button class="btn pequeno" data-copiar-carrinho title="Copia o que falta comprar, no formato de lista (quantidade e nome)">📋 Copiar lista de faltantes</button></div>` : "";

  const vazio = !usadas.length ? `<div class="nota-loja">${tela.pendentes ? "O carrinho vai sendo montado conforme as cartas chegam." : "Nenhuma carta da lista com preço nas lojas do carrinho."}</div>` : "";
  return resumo + faltaTxt + comandas + vazio + sobraTxt;
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
  avisarLinhas(L.cancelada ? linhas : linhas.concat(linhaDuracao()));
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

let freteTimer = null;
$("resultados").addEventListener("input", (e) => {
  const campo = e.target.closest("[data-frete]");
  if (!campo || !tela.lista) return;
  const v = Math.max(0, Math.min(500, Number(String(campo.value).replace(",", ".")) || 0));
  cfg.frete = v;
  clearTimeout(freteTimer);
  freteTimer = setTimeout(() => { api().salvar_frete(v); desenhar(); }, 400);  // espera a pessoa parar de digitar
});

// devolve true se o clique era da lista
function cliqueNaLista(e) {
  if (!tela.lista) return false;
  if (e.target.closest("[data-abrir]")) return false;  // "Abrir ↗" e "LigaMagic ↗": app.js abre no navegador
  const L = tela.lista;
  const aba = e.target.closest("[data-vista]");
  if (aba) { L.vista = aba.dataset.vista; desenhar(); return true; }
  if (e.target.closest("[data-lista-cancelar]")) { cancelarLista(); return true; }
  if (e.target.closest("[data-lista-editar]")) { abrirJanelaLista(); return true; }
  const tirar = e.target.closest("[data-tirar-loja]");
  if (tirar) { L.fora = { ...(L.fora || {}), [tirar.dataset.tirarLoja]: true }; desenhar(); return true; }
  const devolver = e.target.closest("[data-devolver-loja]");
  if (devolver) { const f = { ...(L.fora || {}) }; delete f[devolver.dataset.devolverLoja]; L.fora = f; desenhar(); return true; }
  const doCarrinho = e.target.closest("[data-abrir-carrinho]");
  if (doCarrinho) {
    const urls = ultimoCarrinho.urls[doCarrinho.dataset.abrirCarrinho] || [];
    (async () => {
      if (urls.length > 10 && !(await perguntar(`Abrir ${urls.length} páginas?`,
        "Cada carta abre numa aba nova do navegador.", "Abrir todas"))) return;
      api().abrir(urls);
    })();
    return true;
  }
  const copiarCarrinho = e.target.closest("[data-copiar-carrinho]");
  if (copiarCarrinho) {
    copiarTexto(ultimoCarrinho.faltam).then((ok) => {
      copiarCarrinho.textContent = ok ? "✓ Copiado! Cole nas suas anotações" : "Não consegui copiar";
      setTimeout(() => { if (copiarCarrinho.isConnected) copiarCarrinho.textContent = "📋 Copiar lista de faltantes"; }, 2500);
    });
    return true;
  }
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
      setTimeout(() => { if (faltando.isConnected) faltando.textContent = "📋 Copiar lista de faltantes"; }, 2500);
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
