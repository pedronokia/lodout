// Página da conta: salvar "quanto paguei" sem recarregar a página
// (plans/pending/conta-inventario.md, fase 3). Sem JavaScript, o
// formulário de cada linha continua funcionando como sempre (POST +
// recarregar). Só a linha salva muda: preço de empate, preço para a meta
// de lucro e o lucro se vender hoje.
(function () {
  "use strict";

  function texto(el, valor) {
    if (el) el.textContent = valor;
  }

  document.addEventListener("submit", function (e) {
    var form = e.target;
    if (!form.classList || !form.classList.contains("form-custo")) return;
    if (!window.fetch || !window.FormData) return;
    e.preventDefault();
    var linha = form.closest("tr");
    var aviso = form.querySelector(".custo-salvo");
    var botao = form.querySelector("button[type=submit]");
    if (botao) botao.disabled = true;
    texto(aviso, "salvando…");
    fetch(form.action, {
      method: "POST",
      body: new FormData(form),
      headers: { "Accept": "application/json" },
      credentials: "same-origin"
    }).then(function (resp) {
      return resp.json().then(function (dados) { return { ok: resp.ok, dados: dados }; });
    }).then(function (r) {
      if (!r.ok || !r.dados.ok) {
        texto(aviso, (r.dados && r.dados.erro) || "Não deu para salvar. Tente de novo.");
        if (aviso) aviso.classList.add("custo-erro");
        return;
      }
      var d = r.dados;
      if (aviso) aviso.classList.remove("custo-erro");
      texto(aviso, "salvo ✓");
      if (linha) {
        texto(linha.querySelector('[data-campo="empate"]'), d.empate_fmt || "informe quanto pagou");
        texto(linha.querySelector('[data-campo="alvo"]'), d.alvo_fmt || "—");
        var lucro = linha.querySelector('[data-campo="lucro"]');
        if (lucro) {
          lucro.textContent = d.lucro_fmt || "—";
          lucro.classList.remove("valor-positivo", "valor-negativo");
          if (d.lucro_classe) lucro.classList.add(d.lucro_classe);
        }
        if (d.empate_fmt) linha.classList.remove("linha-sem-custo");
      }
      setTimeout(function () { if (aviso && aviso.textContent === "salvo ✓") aviso.textContent = ""; }, 2500);
    }).catch(function () {
      // Rede caiu ou resposta inesperada: cai no envio normal.
      form.submit();
    }).then(function () {
      if (botao) botao.disabled = false;
    });
  });
})();
