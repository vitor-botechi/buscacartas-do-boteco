"use strict";
/* Tutorial "Como funciona?": um passeio pelos botões e funções principais, com um destaque em volta de
   cada um e um balão com pouco texto. Para mostrar os resultados, a área de resultados recebe uma busca
   de exemplo (desenhada com as mesmas funções da tela, sem nenhuma requisição); ao terminar, a tela
   volta a ser o que era. Enquanto isso, desenhar() não mexe nos resultados (tutorialAtivo, em app.js).
   Na primeira vez que o programa abre, o botão chama atenção com um convite; abrir o tutorial ou
   dispensar o convite grava "tutorial_visto" no config.json (Ponte.marcar_tutorial_visto). */

const BANDEIRAS = "https://www.lmcorp.com.br/images/bandeiras/";

// busca de exemplo: uma loja com a carta (um item já com as edições e outro ainda sem) e uma sem
function resultadosDeExemplo() {
  const oferta = (edicao, idioma, qualidade, estoque, preco, mais = {}) => ({
    edicao, idioma, qualidade, estoque, preco, extras: "", preco_original: null, promo: 0, pre: false, pre_data: "",
    obs: "", bandeira: BANDEIRAS + (idioma === "Português" ? "pt" : "en") + ".svg", edicao_cod: "", imagem: "", fotos: 0, ...mais,
  });
  const loja = (nome, url, cor) => ({ nome, url, cor, cor2: "", logo: "", padrao: true });
  const comCarta = {
    loja: loja("Loja de exemplo", "https://exemplo.invalid/a", "#a1361f"), url_busca: "", status: "found", msg: "",
    itens: [
      { nome: "Anel Solar / Sol Ring", url: "https://exemplo.invalid/a/1", liga: "https://www.ligamagic.com.br/?view=cards/card&card=Sol%20Ring", exato: true, ofertas: [
        oferta("Commander 2014", "Inglês", "SP", 1, 8.4),
        oferta("Commander 2016", "Português", "NM", 3, 12),
        oferta("Commander Masters", "Inglês", "NM", 2, 14.9, { preco_original: 19.9, promo: 25 }),
        oferta("Foundations (Promos)", "Inglês", "NM", 1, 21.89, { extras: "Foil" }),
      ] },
      { nome: "Sol Ring (Human)", url: "https://exemplo.invalid/a/2", liga: "https://www.ligamagic.com.br/?view=cards/card&card=Sol%20Ring", exato: false, ofertas: null },
    ],
  };
  const semCarta = { loja: loja("Outra loja", "https://exemplo.invalid/b", "#1e4f8a"), url_busca: "", status: "none", msg: "", itens: [] };
  return [comCarta, semCarta];
}

function desenharExemplo() {
  const exemplo = novaTela();
  exemplo.carta = "Sol Ring";
  for (const r of resultadosDeExemplo()) { exemplo.ordem.push(r.loja.url); exemplo.res[r.loja.url] = r; }
  const real = tela;
  tela = exemplo;  // blocoLoja lê o estado da tela: por um instante, é o do exemplo
  try { $("resultados").innerHTML = tela.ordem.map(blocoLoja).join(""); } finally { tela = real; }
  $("resultados").scrollTop = 0;
}

const no = (sel) => () => document.querySelector(sel);
const PASSOS = [
  { titulo: "Bem-vindo ao boteco!", texto: "Em um minutinho eu te mostro como achar suas cartas nas lojas." },
  { alvo: () => [$("lojas"), document.querySelector(".todas"), $("adicionar")], lado: "direita",
    titulo: "Escolha as lojas", texto: "Ligue as lojas onde quer procurar. Arraste ⠿ para mudar a ordem." },
  { alvo: no(".busca"), titulo: "Digite a carta", texto: "Em português ou inglês. Depois é só apertar Enter ou clicar em Buscar." },
  { alvo: () => $("colar"), titulo: "Copiou o nome?", texto: "Volte para cá e aperte Enter duas vezes: o 1º cola, o 2º busca." },
  { alvo: no("#resultados .cartao > .cab"),
    titulo: "Uma comanda por loja", texto: "Verde: a loja tem a carta. Clique no nome da loja para abrir ou fechar." },
  { alvo: no("#resultados .item:not(.fechado) .corpo"),
    titulo: "Edições e preços", texto: "Do mais barato ao mais caro. Clique numa linha para abrir na loja e comprar. Pare o mouse no nome para ver a arte da carta." },
  { alvo: no("#resultados .item-cab .liga"),
    titulo: "Compare com a LigaMagic", texto: "Abre a carta na LigaMagic, no seu navegador, para comparar os preços." },
  { alvo: no("#resultados .item-cab .pedir"),
    titulo: "Muitos resultados?", texto: "Aí o preço vem quando você pede: clique aqui, ou em “Carregar todos os preços” na loja." },
  { alvo: () => $("exato").closest("label"), titulo: "Só a carta certa", texto: "Marque para esconder as cartas de nome parecido." },
  { alvo: () => $("ajuda"), titulo: "Pronto!", texto: "Quer ver de novo? É só clicar aqui.", fim: "Bora buscar!" },
];

let passoAtual = 0;
let rolagemAntes = 0;

function abrirTutorial() {
  fecharConvite();
  if (tutorialAtivo) return;
  esconderArte();
  tutorialAtivo = true;
  rolagemAntes = $("resultados").scrollTop;
  desenharExemplo();
  $("tour").hidden = false;
  irPara(0);
}

function fecharTutorial() {
  if (!tutorialAtivo) return;
  tutorialAtivo = false;
  $("tour").hidden = true;
  desenhar();  // a tela volta a ser o que era (inclusive o que chegou de uma busca durante o tutorial)
  $("resultados").scrollTop = rolagemAntes;
  $("carta").focus();
}

function irPara(i) {
  if (i < 0) return;
  if (i >= PASSOS.length) { fecharTutorial(); return; }
  passoAtual = i;
  const p = PASSOS[i];
  $("tour-titulo").textContent = p.titulo;
  $("tour-texto").textContent = p.texto;
  $("tour-pontos").innerHTML = PASSOS.map((_, k) => `<i class="${k === i ? "atual" : ""}"></i>`).join("");
  $("tour-voltar").hidden = i === 0;
  $("tour-pular").hidden = i === PASSOS.length - 1;
  $("tour-proximo").textContent = p.fim || (i === 0 ? "Bora!" : "Próximo");
  posicionarTour();
  $("tour-proximo").focus();
}

function retanguloDoAlvo(p) {
  if (!p.alvo) return null;
  const els = [].concat(p.alvo()).filter(Boolean);
  if (!els.length) return null;
  const rs = els.map((el) => el.getBoundingClientRect());
  const folga = 6;
  return {
    left: Math.min(...rs.map((r) => r.left)) - folga, top: Math.min(...rs.map((r) => r.top)) - folga,
    right: Math.max(...rs.map((r) => r.right)) + folga, bottom: Math.max(...rs.map((r) => r.bottom)) + folga,
  };
}

function posicionarTour() {
  if (!tutorialAtivo) return;
  const p = PASSOS[passoAtual];
  const foco = $("tour-foco"), balao = $("tour-balao");
  const W = innerWidth, H = innerHeight, m = 12, d = 14;
  const r = retanguloDoAlvo(p);
  const bw = balao.offsetWidth, bh = balao.offsetHeight;
  if (!r) {  // sem alvo: balão no meio, tela toda escurecida
    Object.assign(foco.style, { left: `${W / 2}px`, top: `${H / 2}px`, width: "0px", height: "0px" });
    foco.classList.add("sem-alvo");
    balao.style.left = `${(W - bw) / 2}px`; balao.style.top = `${(H - bh) / 2}px`;
    return;
  }
  foco.classList.remove("sem-alvo");
  Object.assign(foco.style, { left: `${r.left}px`, top: `${r.top}px`, width: `${r.right - r.left}px`, height: `${r.bottom - r.top}px` });
  const dentro = (x, y) => x >= m && y >= m && x + bw <= W - m && y + bh <= H - m;
  const xAlinhado = Math.min(Math.max(m, r.left), W - bw - m);
  const yAlinhado = Math.min(Math.max(m, r.top), H - bh - m);
  const opcoes = {
    baixo: [xAlinhado, r.bottom + d], direita: [r.right + d, yAlinhado],
    cima: [xAlinhado, r.top - d - bh], esquerda: [r.left - d - bw, yAlinhado],
  };
  const ordem = [p.lado, "baixo", "direita", "cima", "esquerda"].filter(Boolean);
  const lugar = ordem.map((k) => opcoes[k]).find(([x, y]) => dentro(x, y)) || [W - bw - m, H - bh - m];
  balao.style.left = `${lugar[0]}px`; balao.style.top = `${lugar[1]}px`;
}

/* ---- convite da primeira vez ---- */
function fecharConvite() {
  if ($("convite").hidden && !$("ajuda").classList.contains("chamando")) return;
  $("convite").hidden = true;
  $("ajuda").classList.remove("chamando");
  api().marcar_tutorial_visto();
}

function prepararTutorial(visto) {
  if (visto) return;
  $("ajuda").classList.add("chamando");
  $("convite").hidden = false;
}

$("ajuda").onclick = abrirTutorial;
$("convite").addEventListener("click", (e) => {
  if (e.target.closest("#convite-fechar")) fecharConvite();
  else abrirTutorial();
});
$("tour-proximo").onclick = () => irPara(passoAtual + 1);
$("tour-voltar").onclick = () => irPara(passoAtual - 1);
$("tour-pular").onclick = fecharTutorial;
window.addEventListener("resize", posicionarTour);
// com o tutorial aberto, o teclado só serve a ele (Enter não busca, Alt+← não volta a busca)
window.addEventListener("keydown", (e) => {
  if (!tutorialAtivo) return;
  if (e.key === "Tab") return;  // Tab passa pelos botões do balão
  const acoes = { Escape: fecharTutorial, ArrowRight: () => irPara(passoAtual + 1), ArrowLeft: () => irPara(passoAtual - 1) };
  e.preventDefault(); e.stopPropagation();
  if (acoes[e.key]) acoes[e.key]();
  else if (e.key === "Enter" || e.key === " ") document.activeElement?.closest?.("#tour-balao button")?.click();
}, true);
