// Ranking (17/11, pedidos do usuário):
// - clicar no "Encomenda até" copia o número ("53,41") para colar no
//   preço da encomenda na Steam;
// - a barra "Quero lucrar" recalcula o "Encomenda até" de cada item na
//   hora. Quem entrou na conta: salva a meta (a mesma da "Minha conta").
//   Sem login: guarda só neste navegador.
// Sem JS, os valores continuam visíveis (meta de 20% ou a da conta).
(function () {
  "use strict";
  var aviso = document.querySelector("[data-copiado]");
  document.addEventListener("click", function (e) {
    var botao = e.target.closest && e.target.closest("[data-copiar-preco]");
    if (!botao) return;
    var numero = botao.getAttribute("data-copiar-preco");
    if (!numero || !navigator.clipboard) return;
    navigator.clipboard.writeText(numero).then(function () {
      botao.classList.add("copiado");
      botao.setAttribute("data-dica", "copiado");
      if (aviso) aviso.textContent = "Copiado: " + numero + ". Na Steam, cole no preço da encomenda.";
      clearTimeout(botao._copiadoT);
      botao._copiadoT = setTimeout(function () {
        botao.classList.remove("copiado");
        botao.removeAttribute("data-dica");
      }, 2000);
    }, function () {});
  });

  var form = document.querySelector("[data-meta-lucro]");
  var barra = form && form.querySelector('[name="meta"]');
  if (!barra) return;
  var saida = form.querySelector("[data-meta-lucro-valor]");
  var tabela = document.querySelector(".tabela-top20");
  var taxa = Number((tabela && tabela.getAttribute("data-taxa")) || 15) / 100;
  var local = form.hasAttribute("data-meta-local");
  var CHAVE = "lodout_meta_encomenda";

  function reais(v) {
    var p = v.toFixed(2).split(".");
    return "R$ " + p[0].replace(/\B(?=(\d{3})+(?!\d))/g, ".") + "," + p[1];
  }

  // Mesma conta do servidor (encomenda.info): preço de hoje sem a taxa,
  // dividido por (1 + meta).
  function pintar() {
    var min = Number(barra.min) || 1, max = Number(barra.max) || 100;
    barra.style.setProperty("--pct", ((Number(barra.value) - min) / (max - min) * 100) + "%");
  }
  pintar();

  function aplicar(meta) {
    pintar();
    saida.textContent = meta + "%";
    barra.setAttribute("aria-valuetext", meta + "%");
    Array.prototype.forEach.call(document.querySelectorAll("[data-meta-num]"), function (el) {
      el.textContent = String(meta);
    });
    Array.prototype.forEach.call(document.querySelectorAll("[data-preco-hoje]"), function (b) {
      var preco = Number(b.getAttribute("data-preco-hoje"));
      if (!(preco > 0)) return;
      var ate = Math.round(preco / (1 + taxa) / (1 + meta / 100) * 100) / 100;
      var numero = ate.toFixed(2).replace(".", ",");
      var valor = b.querySelector("[data-encomenda-valor]");
      if (valor) valor.textContent = reais(ate);
      b.setAttribute("data-copiar-preco", numero);
      b.title = "Copiar " + numero + ": na Steam, cole no preço da encomenda";
      b.setAttribute("aria-label", "Copiar " + reais(ate) + ", preço máximo da encomenda de " +
        (b.getAttribute("data-nome") || "") + " para lucrar " + meta + "%");
    });
  }

  if (local) {
    form.hidden = false;
    var guardada = null;
    try { guardada = Number(window.localStorage.getItem(CHAVE)); } catch (e) { guardada = null; }
    if (guardada >= 1 && guardada <= 100 && guardada !== Number(barra.value)) {
      barra.value = String(guardada);
      aplicar(guardada);
    }
  }

  barra.addEventListener("input", function () { aplicar(Number(barra.value)); });

  // Salvar: só quando a pessoa solta a barra (e para de apertar setas).
  var espera = null, enviando = false, deNovo = false;
  function salvarNaConta() {
    if (enviando) { deNovo = true; return; }
    enviando = true;
    var enviada = barra.value;
    fetch(form.action, {
      method: "POST", body: new FormData(form),
      headers: { "Accept": "application/json" }, credentials: "same-origin"
    }).then(function (resp) {
      return resp.ok ? resp.json() : Promise.reject();
    }).then(function () {
      enviando = false;
      if (deNovo) { deNovo = false; if (barra.value !== enviada) salvarNaConta(); }
    }).catch(function () { form.submit(); });
  }
  barra.addEventListener("change", function () {
    clearTimeout(espera);
    espera = setTimeout(function () {
      if (local) {
        try { window.localStorage.setItem(CHAVE, barra.value); } catch (e) { /* sem armazenamento: só nesta visita */ }
      } else if (window.fetch) {
        salvarNaConta();
      } else {
        form.submit();
      }
    }, 400);
  });
  form.addEventListener("submit", function (e) {
    if (local) e.preventDefault();
  });
})();
