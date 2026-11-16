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
    if (campo.form.classList.contains("form-meta-lucro") && window.fetch) {
      trocarMeta(campo);
      return;
    }
    campo.form.submit();
  });

  // "Quero lucrar X%" sem recarregar (2026-11-15): salva a preferência e
  // recalcula o preço de venda de cada linha aqui mesmo (empate × meta).
  function trocarMeta(seletor) {
    var form = seletor.form;
    fetch(form.action, {
      method: "POST", body: new FormData(form),
      headers: { "Accept": "application/json" }, credentials: "same-origin"
    }).then(function (resp) {
      return resp.ok ? resp.json() : Promise.reject();
    }).then(function (d) {
      if (!d || !d.ok) return Promise.reject();
      var meta = Number(d.meta);
      Array.prototype.forEach.call(document.querySelectorAll("[data-meta-rotulo]"), function (el) {
        el.textContent = "Lucrar " + meta + "%";
      });
      Array.prototype.forEach.call(document.querySelectorAll("[data-meta-num]"), function (el) {
        el.textContent = String(meta);
      });
      Array.prototype.forEach.call(document.querySelectorAll("tr.linha-posicao"), function (tr) {
        var empate = Number(tr.getAttribute("data-empate") || 0);
        if (!empate) return;
        texto(tr.querySelector('[data-campo="alvo"]'), reais(empate * (1 + meta / 100)));
        titulosVenda(tr);
      });
    }).catch(function () { form.submit(); });
  }

  // Valor colado ou digitado do jeito brasileiro ("R$ 1.234,56") vira
  // "1234,56" antes de validar e salvar.
  function normalizarValor(campo) {
    var v = campo.value.replace(/R\$/g, "").replace(/[\s\u00a0]/g, "");
    if (v.indexOf(",") !== -1) v = v.replace(/\./g, "");
    if (v !== campo.value) campo.value = v;
  }

  // ── Ferramentas da lista: busca, filtro e ordem (2026-11-15) ──────────
  // Inventário grande: achar o que importa sem rolar a lista toda. Só
  // reorganiza as linhas que já estão na página; nenhuma consulta nova.
  var ferramentas = document.querySelector("[data-conta-ferramentas]");
  var corpo = document.querySelector(".tabela-conta tbody:not(.corpo-nenhum)");
  var estado = { filtro: "todos", busca: "", ordem: "valor" };

  function semAcento(t) {
    return (t || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/-/g, " ");
  }

  var formatoReais = window.Intl ? new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }) : null;
  function reais(v) {
    return formatoReais ? formatoReais.format(v) : "R$ " + v.toFixed(2).replace(".", ",");
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
        // Sem "★" e outros símbolos no começo; lotes do mesmo item na
        // ordem original (lote 1 antes do 2).
        var na = semAcento(a.querySelector(".link-item").textContent).replace(/^[^a-z0-9]+/, "");
        var nb = semAcento(b.querySelector(".link-item").textContent).replace(/^[^a-z0-9]+/, "");
        return na.localeCompare(nb, "pt-BR") || Number(a.getAttribute("data-ordem")) - Number(b.getAttribute("data-ordem"));
      }
      return chave(a) - chave(b) || Number(a.getAttribute("data-ordem")) - Number(b.getAttribute("data-ordem"));
    });
    var nenhum = document.querySelector("[data-conta-nenhum]");
    // Mover uma linha tira o cursor do campo que está nela (e o "change"
    // ao perder o foco salvaria um valor pela metade). Com um valor pago
    // sendo digitado, a ordem espera; esconder/mostrar linhas não mexe
    // no cursor e continua valendo.
    var ativo = document.activeElement;
    var digitando = ativo && ativo.classList && ativo.classList.contains("input-custo") && corpo.contains(ativo);
    var mudou = ordenadas.some(function (tr, i) { return todas[i] !== tr; });
    if (mudou && !digitando) ordenadas.forEach(function (tr) { corpo.appendChild(tr); });
    if (nenhum) {
      nenhum.hidden = visiveis > 0;
      // Numa busca, a mensagem fala da busca (antes dizia "filtro").
      var nenhumTexto = nenhum.querySelector("[data-nenhum-texto]");
      var nenhumBotao = nenhum.querySelector("[data-conta-limpar]");
      var termo = estado.busca.trim();
      if (nenhumTexto) nenhumTexto.textContent = termo ? "Nenhum item com “" + termo + "”." : "Nenhum item com esse filtro.";
      if (nenhumBotao) nenhumBotao.textContent = termo ? "Limpar a busca" : "Mostrar todos";
    }
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
      // Filtro sem nenhum item: mais apagado (continua clicável).
      var bt = el && el.closest(".conta-filtro");
      if (bt) bt.classList.toggle("conta-filtro-vazio", contagem[f] === 0 && f !== estado.filtro);
    });
    var mostrando = ferramentas.querySelector("[data-conta-mostrando]");
    if (mostrando) {
      var soma = 0;
      todas.forEach(function (tr) { if (!tr.hidden) soma += Number(tr.getAttribute("data-valor") || 0); });
      mostrando.textContent = visiveis === todas.length || visiveis === 0 ? "" :
        "Mostrando " + visiveis + " de " + todas.length + " " + (todas.length === 1 ? "item" : "itens") +
        " · " + (visiveis === 1 ? "vale " : "valem ") + reais(soma) + " hoje";
    }
    // Títulos de coluna: qual está ordenando (leitor de tela e seta).
    Array.prototype.forEach.call(document.querySelectorAll(".tabela-conta th[data-ordenar-coluna]"), function (th) {
      var col = th.getAttribute("data-ordenar-coluna");
      var ativo = col === estado.ordem || (col === "lucro" && estado.ordem === "prejuizo");
      if (!ativo) { th.removeAttribute("aria-sort"); return; }
      th.setAttribute("aria-sort", estado.ordem === "nome" || estado.ordem === "prejuizo" ? "ascending" : "descending");
    });
  }

  var escolherFiltro = function () {};
  var limparBusca = function () {};
  if (ferramentas && corpo) {
    linhas().forEach(function (tr, i) { tr.setAttribute("data-ordem", i); });
    ferramentas.hidden = false;
    // "Como ler esta tabela" entra na barra, ao lado do "Ordenar" (no
    // celular, uma linha a menos). Sem JavaScript fica onde está.
    var comoLer = document.querySelector(".como-ler");
    var mostrandoEl = ferramentas.querySelector("[data-conta-mostrando]");
    if (comoLer) ferramentas.insertBefore(comoLer, mostrandoEl);
    var busca = ferramentas.querySelector("[data-conta-busca]");
    var ordem = ferramentas.querySelector("[data-conta-ordem]");
    // Botão "Buscar" (celular, revisão 2026-11-16): com a lista longa, a
    // busca fica lá em cima; depois de passar dela, um botão volta até ela
    // e já põe o cursor no campo. No computador o CSS esconde (tem o "/").
    var irBusca = document.querySelector("[data-ir-busca]");
    if (irBusca && busca) {
      // Só aparece rolando para cima (sinal de quer voltar); lendo a lista
      // para baixo some, para não cobrir preços (revisão 2026-11-16).
      var ultimoY = window.scrollY;
      var mostrarIrBusca = function () {
        var y = window.scrollY;
        if (ferramentas.getBoundingClientRect().bottom > 0) irBusca.hidden = true;
        else if (y < ultimoY - 4) irBusca.hidden = false;
        else if (y > ultimoY + 4) irBusca.hidden = true;
        if (Math.abs(y - ultimoY) > 4) ultimoY = y;
      };
      document.addEventListener("scroll", mostrarIrBusca, { passive: true });
      irBusca.addEventListener("click", function () {
        var reduzir = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        var topo = document.querySelector("header.topo");
        var folga = (topo ? topo.getBoundingClientRect().height : 0) + 8;
        var destino = ferramentas.getBoundingClientRect().top + window.scrollY - folga;
        // Muito longe (lista grande): pula direto, rolar suave levaria segundos.
        var longe = Math.abs(window.scrollY - destino) > 3 * window.innerHeight;
        busca.focus({ preventScroll: true });
        // "instant" fura o scroll-behavior: smooth do CSS; navegador antigo
        // que não conhece o valor recusa, e cai no "auto".
        try {
          window.scrollTo({ top: destino, behavior: reduzir || longe ? "instant" : "smooth" });
        } catch (erro) {
          window.scrollTo(0, destino);
        }
      });
      mostrarIrBusca();
    }
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
    if (busca) {
      busca.addEventListener("input", function () { estado.busca = busca.value; aplicar(); });
      // Esc limpa a busca (e sai do campo, se já estava vazia).
      busca.addEventListener("keydown", function (e) {
        if (e.key !== "Escape") return;
        if (busca.value) { busca.value = ""; estado.busca = ""; aplicar(); e.preventDefault(); }
        else { busca.blur(); }
      });
    }
    // Clicar no título da coluna ordena (Lucro alterna entre maior lucro
    // e maior prejuízo); o seletor "Ordenar" acompanha.
    function escolherOrdem(valor) {
      estado.ordem = valor;
      if (ordem) ordem.value = valor;
      try { window.localStorage.setItem("lodout-conta-ordem", valor); } catch (erro) { /* ignora */ }
      aplicar();
    }
    Array.prototype.forEach.call(document.querySelectorAll(".tabela-conta th[data-ordenar-coluna]"), function (th) {
      var col = th.getAttribute("data-ordenar-coluna");
      var botao = document.createElement("button");
      botao.type = "button";
      botao.className = "ordenar-coluna";
      botao.innerHTML = th.innerHTML + '<span class="ordenar-seta" aria-hidden="true"></span>';
      botao.addEventListener("click", function () {
        if (col === "lucro") escolherOrdem(estado.ordem === "prejuizo" ? "lucro" : "prejuizo");
        else escolherOrdem(col);
      });
      th.innerHTML = "";
      th.appendChild(botao);
    });
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
      botao.setAttribute("data-dica", "copiado · cole em “O comprador paga”");
      if (avisoCopia) avisoCopia.textContent = "Copiado: " + numero + ". Na Steam, cole no campo O comprador paga.";
      setTimeout(function () { botao.classList.remove("copiado"); botao.removeAttribute("data-dica"); }, 2600);
    }, function () {});
  });

  // Dica do preço de venda: o que o comprador paga e o que sobra para
  // a pessoa (2026-11-15: o usuário colou o preço em "Você recebe" e a
  // Steam somou a taxa de novo).
  function titulosVenda(tr) {
    var tabela = tr.closest("table");
    var taxa = Number((tabela && tabela.getAttribute("data-taxa")) || 15) / 100;
    var seletor = document.querySelector('select[name="meta"]');
    var meta = Number((seletor && seletor.value) || 20) / 100;
    var empate = Number(tr.getAttribute("data-empate") || 0);
    if (!empate) return;
    var pago = empate / (1 + taxa);
    var pares = [["empate", empate, pago], ["alvo", empate * (1 + meta), pago * (1 + meta)]];
    var item = tr.querySelector(".link-item");
    var nome = item ? (item.getAttribute("title") || item.textContent) : "";
    pares.forEach(function (par) {
      var campo = tr.querySelector('[data-campo="' + par[0] + '"]');
      var b = campo && campo.closest("[data-copiar]");
      if (!b) return;
      b.title = "O comprador paga " + reais(par[1]) + " · você recebe ≈ " + reais(par[2]) +
        ". Clique para copiar e cole em “O comprador paga” na Steam.";
      b.setAttribute("aria-label", "Copiar " + reais(par[1]) + ", preço " +
        (par[0] === "empate" ? "sem prejuízo" : "para lucrar " + Math.round(meta * 100) + "%") +
        (nome ? " de " + nome : ""));
    });
  }
  Array.prototype.forEach.call(document.querySelectorAll("tr.linha-posicao"), titulosVenda);

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

  // "Buscando seu inventário…": lê esta página de novo, do próprio site
  // (sem consultar a Steam), até a busca acabar. No máximo 12 vezes por
  // aba, pra nunca virar um laço.
  // Revisão 2026-11-16: com a lista na tela ("Atualizar agora"), recarregar
  // no meio da digitação abria o "Sair do site?" do navegador. Agora espera
  // a pessoa terminar (campo com foco, valor não salvo ou janela aberta) e,
  // depois das 12 tentativas, diz o que fazer em vez de ficar em "Buscando…".
  var buscando = document.querySelector("[data-recarregar-enquanto-busca]");
  if (buscando) {
    var tentativas = 0;
    try { tentativas = Number(window.sessionStorage.getItem("lodout-conta-recarga") || 0); } catch (erro) { tentativas = 12; }
    var ocupado = function () {
      var ativo = document.activeElement;
      return temPendente() || !!document.querySelector("dialog[open]") ||
        !!(ativo && ativo.matches && ativo.matches("input, select, textarea"));
    };
    var tentar = function () {
      if (ocupado()) { setTimeout(tentar, 5000); return; }
      try { window.sessionStorage.setItem("lodout-conta-recarga", String(tentativas + 1)); } catch (erro) { /* ignora */ }
      window.location.reload();
    };
    if (tentativas < 12) {
      setTimeout(tentar, 5000);
    } else {
      buscando.classList.remove("status-inventario-buscando");
      buscando.textContent = "A busca do seu inventário está demorando mais que o normal. ";
      var recarregar = document.createElement("button");
      recarregar.type = "button";
      recarregar.className = "acao-texto";
      recarregar.textContent = "Recarregar a página";
      recarregar.addEventListener("click", function () {
        try { window.sessionStorage.removeItem("lodout-conta-recarga"); } catch (erro) { /* ignora */ }
        window.location.reload();
      });
      buscando.appendChild(recarregar);
    }
  } else {
    try { window.sessionStorage.removeItem("lodout-conta-recarga"); } catch (erro) { /* ignora */ }
  }

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
      if (chave === "falta_texto") {
        var cartao = el.closest("[data-card-falta]");
        if (totais[chave]) {
          texto(el, totais[chave]);
          if (cartao) cartao.classList.remove("card-pronto");
        } else if (cartao && !cartao.classList.contains("card-pronto")) {
          // Acabou de preencher o último: o cartão comemora em vez de sumir.
          cartao.classList.add("card-pronto");
          var rotulo = cartao.querySelector("[data-falta-rotulo]");
          if (rotulo) rotulo.textContent = "Valor pago";
          el.textContent = "Tudo preenchido";
          var botaoPreencher = cartao.querySelector("[data-preencher]");
          if (botaoPreencher) botaoPreencher.hidden = true;
          // Quem estava no filtro "Sem valor pago" não fica com a lista vazia.
          if (estado.filtro === "sem-valor") setTimeout(function () { escolherFiltro("todos"); }, 1000);
        }
      } else if (chave === "falta_sub") {
        var c2 = el.closest("[data-card-falta]");
        el.textContent = totais[chave] || (c2 && c2.classList.contains("card-pronto") ? "lucro e preços completos" : "");
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
  // Aviso de "não salvou" ao lado do campo. O valor digitado continua no
  // campo (e o aviso de sair da página com valor não salvo continua valendo).
  function avisarFalha(aviso, r) {
    if (!aviso) return;
    aviso.removeAttribute("data-marca");
    aviso.classList.add("custo-erro");
    if (r.falha === "login") {
      aviso.textContent = "Seu login expirou. ";
      var entrar = document.createElement("a");
      entrar.href = aviso.closest("[data-login-url]") ? aviso.closest("[data-login-url]").getAttribute("data-login-url") : "/login";
      entrar.textContent = "Entrar de novo";
      aviso.appendChild(entrar);
      return;
    }
    aviso.textContent = r.falha === "rede"
      ? "Sem conexão: não salvou. Tente de novo."
      : r.falha === "pressa"
        ? "Muitos valores em pouco tempo: espere alguns segundos e aperte Enter de novo."
      : r.falha === "servidor"
        ? "Não deu para salvar agora. Tente de novo em instantes."
        : (r.dados && r.dados.erro) || "Não deu para salvar. Tente de novo.";
  }

  // "confira: bem acima do preço": tocar mostra o porquê.
  document.addEventListener("click", function (e) {
    var bt = e.target.closest && e.target.closest("button.confira");
    if (!bt) return;
    var explica = document.getElementById(bt.getAttribute("aria-controls"));
    if (!explica) return;
    var abrir = explica.hidden;
    explica.hidden = !abrir;
    bt.setAttribute("aria-expanded", abrir ? "true" : "false");
  });

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
    normalizarValor(campo);
    if (campo.value.trim() === "") {
      // Apagou o número de um item que tinha valor: Enter tira o valor.
      if (campo.form.getAttribute("data-ultimo")) {
        e.preventDefault();
        if (campo.form.requestSubmit) campo.form.requestSubmit(); else campo.form.submit();
      }
      return;
    }
    if (!campo.checkValidity()) return; // deixa o navegador avisar
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

  // ↑ e ↓ no valor pago mudam de item (só os visíveis), como numa planilha.
  document.addEventListener("keydown", function (e) {
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    var campo = e.target;
    if (!campo.classList || !campo.classList.contains("input-custo")) return;
    var campos = Array.prototype.slice.call(document.querySelectorAll(".input-custo")).filter(function (c) {
      var tr = c.closest("tr");
      return !(tr && tr.hidden);
    });
    var i = campos.indexOf(campo) + (e.key === "ArrowDown" ? 1 : -1);
    if (i < 0 || i >= campos.length) return;
    e.preventDefault();
    campos[i].focus();
    campos[i].select();
  });

  // Sair da página com um valor digitado e ainda não salvo (ou salvando)
  // pede confirmação ao navegador, em vez de perder o valor calado.
  var salvando = 0;
  function temPendente() {
    var pendente = salvando > 0;
    Array.prototype.forEach.call(document.querySelectorAll(".form-custo.salva-sozinho"), function (form) {
      var campo = form.querySelector(".input-custo");
      var v = campo ? campo.value.trim() : "";
      if (v !== "" && v !== form.getAttribute("data-ultimo")) pendente = true;
    });
    return pendente;
  }
  window.addEventListener("beforeunload", function (e) {
    if (temPendente()) { e.preventDefault(); e.returnValue = ""; }
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
      normalizarValor(campo);
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
    var anterior = form.getAttribute("data-ultimo") || "";
    // Campo apagado num item que tinha valor: tira o valor pago.
    var limpar = valor === "" && anterior !== "";
    if ((valor === "" && !limpar) || valor === anterior) return;
    form.setAttribute("data-ultimo", valor);
    var dadosForm = new FormData(form);
    if (limpar) dadosForm.append("limpar", "1");
    salvando++;
    var linha = form.closest("tr");
    var aviso = form.querySelector(".custo-salvo");
    var botao = form.querySelector("button[type=submit]");
    if (botao) botao.disabled = true;
    texto(aviso, "salvando…");
    // redirect "manual": login expirado responde com redirecionamento para
    // entrar (que vai à Steam); seguir daria erro de rede. Revisão
    // 2026-11-16: falha ao salvar fica na página, com o valor no campo e
    // um aviso ao lado -- antes caía no envio normal e saía da conta.
    fetch(form.action, {
      method: "POST",
      body: dadosForm,
      headers: { "Accept": "application/json" },
      credentials: "same-origin",
      redirect: "manual"
    }).then(function (resp) {
      if (resp.type === "opaqueredirect" || resp.status === 401 || resp.status === 403) return { falha: "login" };
      if (resp.status === 429) return { falha: "pressa" };
      return resp.json().then(function (dados) {
        return { ok: resp.ok, dados: dados };
      }, function () { return { falha: "servidor" }; });
    }, function () { return { falha: "rede" }; }).then(function (r) {
      if (r.falha || !r.ok || !r.dados || !r.dados.ok) {
        form.removeAttribute("data-ultimo");
        avisarFalha(aviso, r);
        if (campo) campo.focus(); // o erro aparece ao lado: foco no campo para corrigir
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
      // "salvo ✓ · desfazer": volta ao valor de antes (ou a nenhum).
      if (aviso) {
        aviso.textContent = limpar ? "valor apagado " : "salvo ✓ ";
        var desfazer = document.createElement("button");
        desfazer.type = "button";
        desfazer.className = "botao-desfazer";
        desfazer.textContent = "desfazer";
        desfazer.addEventListener("click", function () {
          if (!campo) return;
          campo.value = anterior;
          if (form.requestSubmit) form.requestSubmit(); else form.submit();
          campo.focus();
        });
        aviso.appendChild(desfazer);
        var marca = String(Date.now());
        aviso.setAttribute("data-marca", marca);
        // Some depois de 15 s (eram 6 s, curto para quem lê devagar ou
        // usa leitor de tela) e nunca enquanto o mouse ou o foco estão
        // no "desfazer" (revisão 2026-11-16).
        var sumir = function () {
          if (aviso.getAttribute("data-marca") !== marca) return;
          if (aviso.matches(":hover") || aviso.contains(document.activeElement)) { setTimeout(sumir, 3000); return; }
          aviso.textContent = ""; aviso.removeAttribute("data-marca");
        };
        setTimeout(sumir, 15000);
      }
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
        else linha.classList.add("linha-sem-custo");
        linha.setAttribute("data-empate", d.empate ? String(d.empate) : "");
        titulosVenda(linha);
        var confira = linha.querySelector('[data-campo="confira"]');
        if (confira) {
          confira.textContent = d.confira || "";
          var explica = document.getElementById(confira.getAttribute("aria-controls"));
          if (explica && !d.confira) { explica.hidden = true; confira.setAttribute("aria-expanded", "false"); }
        }
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
