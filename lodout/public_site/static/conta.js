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

  // ── Ferramentas da lista: busca, filtro e ordem (2026-11-15) ──────────
  // Inventário grande: achar o que importa sem rolar a lista toda. Só
  // reorganiza as linhas que já estão na página; nenhuma consulta nova.
  var ferramentas = document.querySelector("[data-conta-ferramentas]");
  var corpo = document.querySelector(".tabela-conta tbody:not(.corpo-nenhum)");
  var estado = { filtro: "todos", busca: "", ordem: "valor" };

  function semAcento(t) {
    return (t || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/-/g, " ");
  }

  function linhas() {
    return corpo ? Array.prototype.slice.call(corpo.querySelectorAll("tr.linha-posicao")) : [];
  }

  function lucroDe(tr) {
    var v = tr.getAttribute("data-lucro");
    return v === "" || v === null ? null : Number(v);
  }

  function passaFiltro(tr, filtro) {
    var lucro = lucroDe(tr);
    if (filtro === "sem-valor") return tr.classList.contains("linha-sem-custo");
    if (filtro === "lucro") return lucro !== null && lucro > 0;
    if (filtro === "prejuizo") return lucro !== null && lucro < 0;
    return true;
  }

  function aplicar() {
    if (!ferramentas || !corpo) return;
    var todas = linhas();
    var palavras = semAcento(estado.busca).split(/\s+/).filter(Boolean);
    var contagem = { todos: 0, "sem-valor": 0, lucro: 0, prejuizo: 0 };
    var visiveis = 0;
    todas.forEach(function (tr) {
      var texto = semAcento(tr.getAttribute("data-busca"));
      var achou = palavras.every(function (p) { return texto.indexOf(p) !== -1; });
      if (achou) {
        Object.keys(contagem).forEach(function (f) { if (passaFiltro(tr, f)) contagem[f]++; });
      }
      var mostra = achou && passaFiltro(tr, estado.filtro);
      tr.hidden = !mostra;
      if (mostra) visiveis++;
    });
    var chave = {
      valor: function (tr) { return -Number(tr.getAttribute("data-valor") || 0); },
      prejuizo: function (tr) { var l = lucroDe(tr); return l === null ? Infinity : l; },
      lucro: function (tr) { var l = lucroDe(tr); return l === null ? Infinity : -l; },
    }[estado.ordem];
    var ordenadas = todas.slice().sort(function (a, b) {
      if (estado.ordem === "nome") {
        return semAcento(a.querySelector(".link-item").textContent).localeCompare(
          semAcento(b.querySelector(".link-item").textContent), "pt-BR");
      }
      return chave(a) - chave(b) || Number(a.getAttribute("data-ordem")) - Number(b.getAttribute("data-ordem"));
    });
    var nenhum = document.querySelector("[data-conta-nenhum]");
    ordenadas.forEach(function (tr) { corpo.appendChild(tr); });
    if (nenhum) nenhum.hidden = visiveis > 0;
    // A última linha visível fecha a tabela: sem borda de baixo nem canto
    // reto (com filtro, a última do corpo pode estar escondida).
    var ultima = null;
    ordenadas.forEach(function (tr) {
      tr.classList.remove("ultima-visivel");
      if (!tr.hidden) ultima = tr;
    });
    if (ultima) ultima.classList.add("ultima-visivel");
    Object.keys(contagem).forEach(function (f) {
      var el = ferramentas.querySelector('[data-conta-contagem="' + f + '"]');
      if (el) el.textContent = contagem[f];
    });
    var mostrando = ferramentas.querySelector("[data-conta-mostrando]");
    if (mostrando) {
      mostrando.textContent = visiveis === todas.length ? "" :
        "Mostrando " + visiveis + " de " + todas.length + " " + (todas.length === 1 ? "item" : "itens");
    }
  }

  var escolherFiltro = function () {};
  var limparBusca = function () {};
  if (ferramentas && corpo) {
    linhas().forEach(function (tr, i) { tr.setAttribute("data-ordem", i); });
    ferramentas.hidden = false;
    var busca = ferramentas.querySelector("[data-conta-busca]");
    var ordem = ferramentas.querySelector("[data-conta-ordem]");
    limparBusca = function () { if (busca) busca.value = ""; estado.busca = ""; };
    escolherFiltro = function (f) {
      estado.filtro = f;
      Array.prototype.forEach.call(ferramentas.querySelectorAll("[data-conta-filtro]"), function (b) {
        b.setAttribute("aria-pressed", b.getAttribute("data-conta-filtro") === f ? "true" : "false");
      });
      aplicar();
    };
    ferramentas.addEventListener("click", function (e) {
      var botao = e.target.closest("[data-conta-filtro]");
      if (botao) escolherFiltro(botao.getAttribute("data-conta-filtro"));
    });
    if (busca) busca.addEventListener("input", function () { estado.busca = busca.value; aplicar(); });
    // A ordem escolhida fica lembrada neste navegador (só conveniência).
    try {
      var guardada = window.localStorage.getItem("lodout-conta-ordem");
      if (ordem && guardada && ordem.querySelector('option[value="' + guardada + '"]')) {
        ordem.value = guardada;
        estado.ordem = guardada;
      }
    } catch (erro) { /* sem armazenamento: segue o padrão */ }
    if (ordem) ordem.addEventListener("change", function () {
      estado.ordem = ordem.value;
      try { window.localStorage.setItem("lodout-conta-ordem", ordem.value); } catch (erro) { /* ignora */ }
      aplicar();
    });
    var limpar = document.querySelector("[data-conta-limpar]");
    if (limpar) limpar.addEventListener("click", function () {
      limparBusca();
      escolherFiltro("todos");
    });
    aplicar();
  }

  // "Preencher agora" no aviso: mostra só os itens sem valor pago e põe o
  // cursor no primeiro campo (com Enter, a pessoa segue para o próximo).
  var preencher = document.querySelector("[data-preencher]");
  if (preencher && window.fetch && window.FormData) {
    preencher.hidden = false;
    preencher.addEventListener("click", function () {
      if (ferramentas && corpo) {
        limparBusca();
        escolherFiltro("sem-valor");
      }
      var alvo = document.querySelector("tr.linha-sem-custo:not([hidden]) .input-custo");
      if (!alvo) return;
      var suave = !(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
      alvo.scrollIntoView({ block: "center", behavior: suave ? "smooth" : "auto" });
      alvo.focus({ preventScroll: true });
    });
  }

  // ── Atalhos da lista (2026-11-15) ────────────────────────────────────
  // Clicar no preço de "Venda por" copia o número ("53,41") para colar na
  // tela de venda da Steam.
  var avisoCopia = document.querySelector("[data-copiado]");
  document.addEventListener("click", function (e) {
    var botao = e.target.closest && e.target.closest("[data-copiar]");
    if (!botao) return;
    var numero = (botao.textContent.match(/[\d.]+,\d{2}/) || [""])[0];
    if (!numero || !navigator.clipboard) return;
    navigator.clipboard.writeText(numero).then(function () {
      botao.classList.add("copiado");
      botao.setAttribute("data-dica", "copiado");
      if (avisoCopia) avisoCopia.textContent = "Copiado: " + numero;
      setTimeout(function () { botao.classList.remove("copiado"); botao.removeAttribute("data-dica"); }, 1400);
    }, function () {});
  });

  // "informe quanto pagou" leva o cursor ao campo da própria linha.
  document.addEventListener("click", function (e) {
    var botao = e.target.closest && e.target.closest("[data-ir-ao-campo]");
    if (!botao) return;
    var campo = botao.closest("tr") && botao.closest("tr").querySelector(".input-custo");
    if (campo) campo.focus();
  });

  // "/" vai para a busca da lista (como na página inicial).
  document.addEventListener("keydown", function (e) {
    if (e.key !== "/" || e.ctrlKey || e.metaKey || e.altKey) return;
    var alvo = e.target;
    if (alvo && (alvo.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(alvo.tagName))) return;
    var busca = document.querySelector("[data-conta-busca]");
    if (!busca || !busca.offsetParent) return;
    e.preventDefault();
    busca.focus();
  });

  // Cartões do topo e aviso de itens sem valor pago, com os textos que o
  // servidor devolve ao salvar (account._textos_totais).
  function atualizarTotais(totais) {
    if (!totais) return;
    var progresso = document.querySelector("[data-total-progresso]");
    if (progresso && typeof totais.com_valor === "number") {
      progresso.max = totais.total_itens || progresso.max;
      progresso.value = totais.com_valor;
    }
    Array.prototype.forEach.call(document.querySelectorAll("[data-total]"), function (el) {
      var chave = el.getAttribute("data-total");
      if (!(chave in totais)) return;
      if (chave === "aviso_sem_custo") {
        el.textContent = totais[chave];
        var caixa = el.closest(".aviso-sem-custo") || el;
        caixa.hidden = !totais[chave];
      } else {
        texto(el, totais[chave]);
      }
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
      var tr = depois[i].closest("tr");
      if (depois[i].value.trim() === "" && !(tr && tr.hidden)) { proximo = depois[i]; break; }
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
          texto(lucro.querySelector('[data-campo="lucro-valor"]'), d.lucro_fmt || "—");
          texto(lucro.querySelector('[data-campo="lucro-pct"]'), d.lucro_pct_fmt || "");
          lucro.classList.remove("valor-positivo", "valor-negativo");
          if (d.lucro_classe) lucro.classList.add(d.lucro_classe);
        }
        if (d.empate_fmt) linha.classList.remove("linha-sem-custo");
        if (lucro && !d.lucro_classe) lucro.classList.add("celula-sem-valor");
        else if (lucro) lucro.classList.remove("celula-sem-valor");
      }
      atualizarTotais(d.totais);
      if (linha) {
        linha.setAttribute("data-lucro", d.lucro === null || d.lucro === undefined ? "" : String(d.lucro));
        // Contagens dos filtros mudam; a linha só some do filtro atual
        // depois de um instante, pra quem salvou ver o "salvo ✓".
        setTimeout(aplicar, estado.filtro === "todos" ? 0 : 900);
      }
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
