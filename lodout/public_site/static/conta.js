// Página da conta: salvar "quanto paguei" sem recarregar a página
// (plans/archive/conta-inventario.md, fase 3). Sem JavaScript, o
// formulário de cada linha continua funcionando como sempre (POST +
// recarregar). Só a linha salva muda: preço de empate, preço para a meta
// de lucro e o lucro se vender hoje.
(function () {
  "use strict";

  // Com JS, o botão "aplicar" da meta some e a meta aplica ao escolher
  // (mesma regra do app.js, que esta página não carrega).
  document.documentElement.classList.add("js-ativo");
  document.addEventListener("change", function (e) {
    var campo = e.target;
    if (!campo.matches || !campo.matches("[data-enviar-ao-mudar]") || !campo.form) return;
    campo.form.submit();
  });

  // Cartões do topo e aviso de itens sem valor pago, com os textos que o
  // servidor devolve ao salvar (account._textos_totais).
  function atualizarTotais(totais) {
    if (!totais) return;
    Array.prototype.forEach.call(document.querySelectorAll("[data-total]"), function (el) {
      var chave = el.getAttribute("data-total");
      if (!(chave in totais)) return;
      if (chave === "aviso_sem_custo") el.textContent = totais[chave];
      else texto(el, totais[chave]);
      if (chave === "aviso_sem_custo") el.hidden = !totais[chave];
      if (chave === "lucro") {
        el.classList.remove("valor-positivo", "valor-negativo", "card-valor-texto");
        if (totais.lucro_classe) el.classList.add(totais.lucro_classe);
      }
    });
  }

  // Troca o texto e, se mudou, realça de leve (.acabou-de-mudar).
  function texto(el, valor) {
    if (!el) return;
    var mudou = el.textContent.trim() !== String(valor).trim();
    el.textContent = valor;
    if (mudou && el.getAttribute("role") !== "status") realcar(el);
  }

  function realcar(el) {
    el.classList.remove("acabou-de-mudar");
    void el.offsetWidth; // reinicia a animação se mudar duas vezes
    el.classList.add("acabou-de-mudar");
  }

  // Remover pede confirmação (ação destrutiva, AGENTS.md). Sem JS o
  // formulário envia direto, como antes.
  // Com <dialog>, uma janela própria com o botão vermelho; sem ela, o
  // confirm() do navegador.
  var dialogo = document.getElementById("dialogo-remover");
  var formPendente = null;
  var botaoDeOrigem = null;
  if (dialogo && typeof dialogo.showModal === "function") {
    dialogo.addEventListener("close", function () {
      var form = formPendente;
      formPendente = null;
      if (dialogo.returnValue === "remover" && form) {
        form.submit(); // submit() não dispara o evento: não reabre a janela
        return;
      }
      if (botaoDeOrigem) botaoDeOrigem.focus();
    });
    // Clique fora da janela (no fundo escuro) = cancelar.
    dialogo.addEventListener("click", function (e) {
      if (e.target === dialogo) dialogo.close("cancelar");
    });
  }

  document.addEventListener("submit", function (e) {
    var form = e.target;
    if (!form.classList || !form.classList.contains("form-remover")) return;
    var nome = form.getAttribute("data-nome") || "este item";
    e.preventDefault();
    if (dialogo && typeof dialogo.showModal === "function") {
      formPendente = form;
      botaoDeOrigem = form.querySelector("button");
      var alvo = dialogo.querySelector("[data-dialogo-nome]");
      if (alvo) alvo.textContent = nome;
      dialogo.returnValue = "";
      dialogo.showModal();
      return;
    }
    if (window.confirm("Remover " + nome + " da sua lista? Se ele ainda estiver no seu inventário da Steam, volta na próxima atualização, sem o valor pago.")) {
      form.submit();
    }
  });

  // Enter no valor pago salva e leva ao próximo item sem valor, como numa
  // planilha (2026-11-15: com o inventário inteiro, eram vários campos
  // para clicar um a um). Sem próximo, o cursor sai do campo.
  document.addEventListener("keydown", function (e) {
    var campo = e.target;
    if (e.key !== "Enter" || !campo.classList || !campo.classList.contains("input-custo")) return;
    if (!campo.form || !campo.form.classList.contains("salva-sozinho")) return;
    if (campo.value.trim() === "" || !campo.checkValidity()) return; // deixa o navegador avisar
    e.preventDefault();
    if (campo.form.requestSubmit) campo.form.requestSubmit(); else campo.form.submit();
    var campos = Array.prototype.slice.call(document.querySelectorAll(".input-custo"));
    var depois = campos.slice(campos.indexOf(campo) + 1);
    var proximo = null;
    for (var i = 0; i < depois.length; i++) {
      if (depois[i].value.trim() === "") { proximo = depois[i]; break; }
    }
    if (proximo) {
      proximo.focus();
    } else {
      campo.blur();
    }
  });

  // Sair da página com um valor digitado e ainda não salvo (ou salvando)
  // pede confirmação ao navegador, em vez de perder o valor calado.
  var salvando = 0;
  window.addEventListener("beforeunload", function (e) {
    var pendente = salvando > 0;
    Array.prototype.forEach.call(document.querySelectorAll(".form-custo.salva-sozinho"), function (form) {
      var campo = form.querySelector(".input-custo");
      var v = campo ? campo.value.trim() : "";
      if (v !== "" && v !== form.getAttribute("data-ultimo")) pendente = true;
    });
    if (pendente) { e.preventDefault(); e.returnValue = ""; }
  });

  // Com fetch, o valor pago salva sozinho: Enter ou ao sair do campo.
  if (window.fetch && window.FormData) {
    Array.prototype.forEach.call(document.querySelectorAll(".form-custo"), function (form) {
      form.classList.add("salva-sozinho");
      var campo = form.querySelector(".input-custo");
      if (campo) form.setAttribute("data-ultimo", campo.value);
    });
    document.addEventListener("change", function (e) {
      var campo = e.target;
      if (!campo.classList || !campo.classList.contains("input-custo") || !campo.form) return;
      if (campo.form.requestSubmit) campo.form.requestSubmit();
      else campo.form.submit();
    });
  }

  document.addEventListener("submit", function (e) {
    var form = e.target;
    if (!form.classList || !form.classList.contains("form-custo")) return;
    if (!window.fetch || !window.FormData) return;
    e.preventDefault();
    // Enter e "sair do campo" podem disparar juntos: o mesmo valor só
    // é enviado uma vez.
    var campo = form.querySelector(".input-custo");
    var valor = campo ? campo.value.trim() : "";
    if (valor === "" || valor === form.getAttribute("data-ultimo")) return;
    form.setAttribute("data-ultimo", valor);
    salvando++;
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
        form.removeAttribute("data-ultimo");
        texto(aviso, (r.dados && r.dados.erro) || "Não deu para salvar. Tente de novo.");
        if (campo) campo.focus(); // o erro aparece ao lado: foco no campo para corrigir
        if (aviso) aviso.classList.add("custo-erro");
        return;
      }
      var d = r.dados;
      if (aviso) aviso.classList.remove("custo-erro");
      // "20" vira "20,00", como as outras linhas.
      var numero = Number(valor.replace(",", "."));
      if (campo && isFinite(numero) && campo.value.trim() === valor) {
        campo.value = numero.toFixed(2).replace(".", ",");
        form.setAttribute("data-ultimo", campo.value);
      }
      texto(aviso, "salvo ✓");
      if (linha) {
        texto(linha.querySelector('[data-campo="empate"]'), d.empate_fmt || "—");
        texto(linha.querySelector('[data-campo="alvo"]'), d.alvo_fmt || "—");
        var lucro = linha.querySelector('[data-campo="lucro"]');
        if (lucro) {
          texto(lucro, d.lucro_fmt || "—");
          lucro.classList.remove("valor-positivo", "valor-negativo");
          if (d.lucro_classe) lucro.classList.add(d.lucro_classe);
        }
        if (d.empate_fmt) linha.classList.remove("linha-sem-custo");
        if (lucro && !d.lucro_classe) lucro.classList.add("celula-sem-valor");
        else if (lucro) lucro.classList.remove("celula-sem-valor");
      }
      atualizarTotais(d.totais);
      setTimeout(function () { if (aviso && aviso.textContent === "salvo ✓") aviso.textContent = ""; }, 2500);
    }).then(function () {
      salvando--;
    }, function () {
      // Rede caiu ou resposta inesperada: cai no envio normal (o próprio
      // envio leva o valor, então não conta como "não salvo").
      salvando--;
      form.removeAttribute("data-ultimo");
      if (campo) form.setAttribute("data-ultimo", campo.value.trim());
      form.submit();
    }).then(function () {
      if (botao) botao.disabled = false;
    });
  });
})();
