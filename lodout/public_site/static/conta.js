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
      // Barra de arrastar (17/11): com as setas do teclado cada passo
      // dispara "change"; salva só quando a pessoa para.
      clearTimeout(metaEspera);
      metaEspera = setTimeout(function () { trocarMeta(campo); }, 400);
      return;
    }
    campo.form.submit();
  });

  // Enquanto arrasta: número ao lado da barra e preços da lista mudam na
  // hora; salvar fica para quando soltar ("change", acima).
  var metaEspera = null;
  document.addEventListener("input", function (e) {
    var barra = e.target;
    if (!barra.matches || !barra.matches(".form-meta-lucro [name=\"meta\"]")) return;
    aplicarMeta(Number(barra.value));
  });

  // Trecho preenchido da barra (--pct no CSS; o atributo style é
  // bloqueado pela CSP, a propriedade via JS não).
  function pintarBarra(barra) {
    var min = Number(barra.min) || 1, max = Number(barra.max) || 100;
    barra.style.setProperty("--pct", ((Number(barra.value) - min) / (max - min) * 100) + "%");
  }
  Array.prototype.forEach.call(document.querySelectorAll('.form-meta-lucro [name="meta"]'), pintarBarra);

  function aplicarMeta(meta) {
    Array.prototype.forEach.call(document.querySelectorAll('.form-meta-lucro input[name="meta"]'), pintarBarra);
    Array.prototype.forEach.call(document.querySelectorAll("[data-meta-lucro-valor]"), function (el) {
      el.textContent = meta + "%";
    });
    Array.prototype.forEach.call(document.querySelectorAll('.form-meta-lucro [name="meta"]'), function (el) {
      el.setAttribute("aria-valuetext", meta + "%");
    });
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
      var pnl = lucroDe(tr);
      var campoCusto = tr.querySelector('input[name="cost"]');
      var custo = campoCusto ? Number(campoCusto.value.replace(/\./g, "").replace(",", ".")) : 0;
      var atingiu = false;
      if (custo > 0 && pnl !== null) {
        var pct = (pnl / custo) * 100;
        atingiu = pct >= meta;
      }
      tr.setAttribute("data-meta-atingida", atingiu ? "1" : "0");
      var lucroEl = tr.querySelector('[data-campo="lucro"]');
      if (lucroEl) {
        var selo = lucroEl.querySelector(".selo-meta-atingida");
        if (atingiu) {
          if (!selo) {
            selo = document.createElement("span");
            selo.className = "selo-meta-atingida";
            selo.textContent = "na meta";
            lucroEl.appendChild(selo);
          }
          selo.title = "Atingiu a meta de " + meta + "% de lucro se vender hoje";
        } else if (selo) {
          selo.remove();
        }
      }
    });
    aplicar();
  }

  // "Quero lucrar X%" sem recarregar (2026-11-15): salva a preferência e
  // recalcula o preço de venda de cada linha aqui mesmo (empate × meta).
  // Uma troca por vez: com a internet lenta, a 1ª resposta chegava por
  // último e a conta ficava com a meta velha, embora a lista mostrasse a
  // nova (revisão 2026-11-16). A escolha feita durante o envio sai depois.
  var metaEnviando = false, metaDeNovo = false;
  function trocarMeta(seletor) {
    var form = seletor.form;
    if (metaEnviando) { metaDeNovo = true; return; }
    metaEnviando = true;
    var enviada = seletor.value;
    var terminar = function () {
      metaEnviando = false;
      if (metaDeNovo) {
        metaDeNovo = false;
        if (seletor.value !== enviada) trocarMeta(seletor);
      }
    };
    fetch(form.action, {
      method: "POST", body: new FormData(form),
      headers: { "Accept": "application/json" }, credentials: "same-origin"
    }).then(function (resp) {
      return resp.ok ? resp.json() : Promise.reject();
    }).then(function (d) {
      if (!d || !d.ok) return Promise.reject();
      aplicarMeta(Number(d.meta));
      terminar();
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
    if (filtro === "fora") return tr.classList.contains("linha-fora");
    if (filtro === "meta") return tr.getAttribute("data-meta-atingida") === "1";
    if (filtro === "lucro") return lucro !== null && lucro > 0;
    if (filtro === "prejuizo") return lucro !== null && lucro < 0;
    return true;
  }

  // Chave de "Nome (A–Z)" calculada uma vez por linha (antes, a cada
  // comparação da ordenação: lento com centenas de itens).
  function itemDe(tr) {
    return tr.getAttribute("data-item") || tr.getAttribute("data-busca") || "";
  }

  function nomeOrdem(tr) {
    if (tr._nomeOrdem === undefined) {
      var link = tr.querySelector(".link-item");
      tr._nomeOrdem = semAcento(link ? link.textContent : "").replace(/^[^a-z0-9]+/, "");
    }
    return tr._nomeOrdem;
  }

  function aplicar() {
    if (!ferramentas || !corpo) return;
    var todas = linhas();
    var palavras = semAcento(estado.busca).split(/\s+/).filter(Boolean);
    var contagem = { todos: 0, "sem-valor": 0, meta: 0, lucro: 0, prejuizo: 0, fora: 0 };
    var visiveis = 0;
    todas.forEach(function (tr) {
      var texto = semAcento(tr.getAttribute("data-busca"));
      var achou = palavras.every(function (p) { return texto.indexOf(p) !== -1; });
      if (achou) {
        Object.keys(contagem).forEach(function (f) { if (passaFiltro(tr, f)) contagem[f]++; });
      }
      var mostra = achou && passaFiltro(tr, estado.filtro);
      // Só mexe na linha que muda: com 500 itens, regravar todas pesava.
      if (tr.hidden === mostra) tr.hidden = !mostra;
      if (mostra) visiveis++;
    });
    // Lotes do mesmo item ficam juntos: a ordem usa o item inteiro (soma
    // dos lotes), como o servidor. Antes cada lote ia para um lado e
    // "lote 1 de 3" aparecia longe do 2 (revisão 2026-11-16).
    var grupos = {};
    todas.forEach(function (tr) {
      var g = grupos[itemDe(tr)] || (grupos[itemDe(tr)] = { valor: 0, lucro: null });
      g.valor += Number(tr.getAttribute("data-valor") || 0);
      var l = lucroDe(tr);
      if (l !== null) g.lucro = (g.lucro || 0) + l;
    });
    var chave = {
      valor: function (g) { return -g.valor; },
      prejuizo: function (g) { return g.lucro === null ? Infinity : g.lucro; },
      lucro: function (g) { return g.lucro === null ? Infinity : -g.lucro; },
    }[estado.ordem];
    var ordenadas = todas.slice().sort(function (a, b) {
      var ia = itemDe(a), ib = itemDe(b);
      var porOrdem = Number(a.getAttribute("data-ordem")) - Number(b.getAttribute("data-ordem"));
      if (estado.ordem === "nome") {
        // Sem "★" e outros símbolos no começo; números em ordem natural
        // ("Teste 2" antes de "Teste 10"); lotes na ordem original.
        return nomeOrdem(a).localeCompare(nomeOrdem(b), "pt-BR", { numeric: true }) ||
          (ia < ib ? -1 : ia > ib ? 1 : 0) || porOrdem;
      }
      return (chave(grupos[ia]) - chave(grupos[ib])) || (ia < ib ? -1 : ia > ib ? 1 : 0) || porOrdem;
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
      // Conta itens, não linhas (lotes do mesmo item contam uma vez), como
      // os cartões do topo (revisão 2026-11-16).
      var soma = 0, itensVisiveis = {}, nVisiveis = 0;
      todas.forEach(function (tr) {
        if (tr.hidden) return;
        soma += Number(tr.getAttribute("data-valor") || 0);
        if (!itensVisiveis[itemDe(tr)]) { itensVisiveis[itemDe(tr)] = true; nVisiveis++; }
      });
      var nTotal = Object.keys(grupos).length;
      mostrando.textContent = visiveis === todas.length || visiveis === 0 ? "" :
        "Mostrando " + nVisiveis + " de " + nTotal + " " + (nTotal === 1 ? "item" : "itens") +
        " · " + (nVisiveis === 1 ? "vale " : "valem ") + reais(soma) + " hoje";
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
    // Vindo de "Informar quanto pagou" na página do item (?busca=nome):
    // mostra só esse item e põe o cursor no primeiro campo sem valor.
    var pedida = "";
    try { pedida = new URLSearchParams(window.location.search).get("busca") || ""; } catch (erro) { /* ignora */ }
    if (pedida && busca) {
      busca.value = pedida;
      estado.busca = pedida;
    }
    limparBusca = function () { if (busca) busca.value = ""; estado.busca = ""; };
    // "Ver quais" no aviso de itens fora do inventário (revisão 30): abre
    // a aba "Fora do inventário" e leva até a lista.
    var irFora = document.querySelector("[data-ir-fora]");
    if (irFora && ferramentas.querySelector('[data-conta-filtro="fora"]')) {
      irFora.hidden = false;
      irFora.addEventListener("click", function () {
        escolherFiltro("fora");
        ferramentas.scrollIntoView({ block: "start", behavior: window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
        var aba = ferramentas.querySelector('[data-conta-filtro="fora"]');
        if (aba) aba.focus({ preventScroll: true });
      });
    }
    // ?filtro=fora (depois de "Devolver com o valor pago", revisão 16/11):
    // abre direto na aba "Fora do inventário".
    try {
      var filtroPedido = new URLSearchParams(window.location.search).get("filtro");
      if (filtroPedido && ferramentas.querySelector('[data-conta-filtro="' + filtroPedido + '"]')) {
        window.setTimeout(function () { escolherFiltro(filtroPedido); }, 0);
      }
    } catch (erro) { /* ignora */ }
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
    var seletor = document.querySelector('.form-meta-lucro [name="meta"]');
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
        ? "Não foi possível salvar agora. Tente de novo em instantes."
        : (r.dados && r.dados.erro) || "Não foi possível salvar. Tente de novo.";
    // Aba velha (saiu e entrou de novo) ou item que saiu em outra aba:
    // só recarregar resolve (revisão 2026-11-16).
    if (r.dados && r.dados.recarregar) {
      var recarregar = document.createElement("button");
      recarregar.type = "button";
      recarregar.className = "acao-texto";
      recarregar.textContent = "Recarregar a página";
      recarregar.addEventListener("click", function () {
        liberarSaida = true;
        window.location.reload();
      });
      aviso.appendChild(recarregar);
    }
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

  // Realces juntados num só quadro: ler offsetWidth em cada célula
  // recalculava a tabela inteira a cada linha, e trocar a meta numa conta
  // de 500 itens travava a página ~3 s (revisão 2026-11-16). Agora é um
  // recálculo só, para todas as células que mudaram.
  var aRealcar = [];
  function realcar(el) {
    if (aRealcar.push(el) > 1) return;
    window.requestAnimationFrame(function () {
      var lote = aRealcar; aRealcar = [];
      lote.forEach(function (e) { e.classList.remove("acabou-de-mudar"); });
      void document.body.offsetWidth; // reinicia a animação se mudar duas vezes
      lote.forEach(function (e) { e.classList.add("acabou-de-mudar"); });
    });
  }

  // Conta pequena (menos de 8 itens não tem a aba "Fora do inventário"):
  // "Ver quais" e ?filtro=fora (depois de "Devolver" ou "Desfazer venda")
  // destacam os itens fora e levam até o primeiro, se ele não estiver à
  // vista (revisão 16/11, rodada 3).
  (function () {
    if (document.querySelector('[data-conta-filtro="fora"]')) return;
    var linhas = document.querySelectorAll("tr.linha-fora");
    if (!linhas.length) return;
    var ir = function (focar) {
      var reduzir = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      linhas[0].scrollIntoView({ block: "nearest", behavior: reduzir ? "auto" : "smooth" });
      Array.prototype.forEach.call(linhas, realcar);
      var alvo = focar && linhas[0].querySelector("a, input, button, summary");
      if (alvo) alvo.focus({ preventScroll: true });
    };
    var botao = document.querySelector("[data-ir-fora]");
    if (botao) { botao.hidden = false; botao.addEventListener("click", function () { ir(true); }); }
    var pedido = null;
    try { pedido = new URLSearchParams(window.location.search).get("filtro"); } catch (erro) { /* ignora */ }
    if (pedido === "fora") window.setTimeout(function () { ir(false); }, 0);
  })();

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
      // Título, texto e botão próprios do form (ex.: item fora do
      // inventário, "Não quero de volta"); sem eles, os da página.
      ["titulo", "texto", "botao"].forEach(function (parte) {
        var el = dialogo.querySelector("[data-dialogo-" + parte + "]");
        if (!el) return;
        if (!el.hasAttribute("data-padrao")) el.setAttribute("data-padrao", el.textContent);
        el.textContent = form.getAttribute("data-dialogo-" + parte) || el.getAttribute("data-padrao");
      });
      dialogo.returnValue = "";
      dialogo.showModal();
      return;
    }
    if (window.confirm(form.getAttribute("data-confirmar") || ("Remover " + nome + " da sua lista? Se ele ainda estiver no seu inventário da Steam, volta na próxima atualização, sem o valor pago."))) {
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
  // "Recarregar a página" num aviso de falha: o valor já não pode ser
  // salvo daqui, então não pergunta "sair do site?".
  var liberarSaida = false;
  window.addEventListener("beforeunload", function (e) {
    if (!liberarSaida && temPendente()) { e.preventDefault(); e.returnValue = ""; }
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
    // Um envio por vez em cada linha: com a internet lenta, o 2º valor
    // podia chegar ao site antes do 1º, e a tela dizia "20,00 salvo ✓"
    // com 10,00 guardado (revisão 2026-11-16). O valor novo espera o
    // envio atual terminar e sai em seguida (só o último digitado).
    if (form.getAttribute("data-enviando")) {
      form.setAttribute("data-de-novo", "1");
      return;
    }
    form.setAttribute("data-enviando", "1");
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
      if (resp.status === 409) return resp.json().then(function (dados) { return { dados: dados }; }, function () { return { falha: "servidor" }; });
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
      // Outro valor espera na fila: a resposta dele atualiza a linha.
      if (form.getAttribute("data-de-novo")) return;
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
          var seloMeta = lucro.querySelector(".selo-meta-atingida");
          if (d.atingiu_meta) {
            if (!seloMeta) {
              seloMeta = document.createElement("span");
              seloMeta.className = "selo-meta-atingida";
              seloMeta.textContent = "na meta";
              lucro.appendChild(seloMeta);
            }
          } else if (seloMeta) {
            seloMeta.remove();
          }
        }
        if (d.empate_fmt) linha.classList.remove("linha-sem-custo");
        else linha.classList.add("linha-sem-custo");
        linha.setAttribute("data-empate", d.empate ? String(d.empate) : "");
        if (d.atingiu_meta !== undefined) {
          linha.setAttribute("data-meta-atingida", d.atingiu_meta ? "1" : "0");
        }
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
      form.removeAttribute("data-enviando");
      if (form.getAttribute("data-de-novo")) {
        form.removeAttribute("data-de-novo");
        if (form.requestSubmit) form.requestSubmit();
      }
    });
  });
  // "Informar quanto pagou" na página do item (?busca=nome): cursor no
  // campo do valor pago desse item (com 8+ itens a busca já filtrou).
  (function () {
    var pedida = "";
    try { pedida = new URLSearchParams(window.location.search).get("busca") || ""; } catch (erro) { return; }
    if (!pedida) return;
    var alvo = semAcento(pedida);
    var linha = Array.prototype.find.call(document.querySelectorAll("tr.linha-sem-custo"), function (tr) {
      return !tr.hidden && semAcento(tr.getAttribute("data-busca") || "").indexOf(alvo) !== -1;
    });
    var campo = linha && linha.querySelector(".input-custo");
    if (campo) { campo.focus({ preventScroll: true }); campo.scrollIntoView({ block: "center" }); }
  })();

  // "Vendi" (revisão 29, 16/11): janela com unidades e quanto o comprador
  // pagou (já com o preço de hoje) e a conta ao vivo. Sem <dialog>, o
  // formulário abre na própria linha (o <details>).
  var dialogoVendi = document.getElementById("dialogo-vendi");
  if (dialogoVendi && typeof dialogoVendi.showModal === "function") {
    var formVendi = dialogoVendi.querySelector("[data-janela-vendi-form]");
    var campoQtd = formVendi.querySelector("[data-janela-vendi-qtd]");
    var campoPreco = formVendi.querySelector("[data-janela-vendi-preco]");
    var contaVendi = formVendi.querySelector("[data-janela-vendi-conta]");
    var tabelaVendi = document.querySelector(".tabela-conta");
    var taxaVendi = Number((tabelaVendi && tabelaVendi.getAttribute("data-taxa")) || 15) / 100;
    var origemVendi = null;
    var custoVendi = null;
    var lerPreco = function () {
      var v = campoPreco.value.replace(/R\$/g, "").replace(/[\s\u00a0]/g, "");
      if (v.indexOf(",") !== -1) v = v.replace(/\./g, "").replace(",", ".");
      return Number(v);
    };
    var contarVenda = function () {
      var preco = lerPreco();
      var qtd = Math.max(1, parseInt(campoQtd.value, 10) || 1);
      contaVendi.textContent = "";
      if (!isFinite(preco) || preco <= 0) return;
      var recebe = preco / (1 + taxaVendi) * qtd;
      contaVendi.appendChild(document.createTextNode("Você recebe ≈ "));
      var forte = document.createElement("strong");
      forte.textContent = reais(recebe);
      contaVendi.appendChild(forte);
      contaVendi.appendChild(document.createTextNode((qtd > 1 ? " pelas " + qtd + "," : "") + " depois da taxa"));
      if (custoVendi !== null) {
        var lucro = recebe - custoVendi * qtd;
        contaVendi.appendChild(document.createTextNode(" · " + (lucro < 0 ? "prejuízo" : "lucro") + " ≈ "));
        var valor = document.createElement("strong");
        valor.className = lucro > 0 ? "valor-positivo" : lucro < 0 ? "valor-negativo" : "";
        valor.textContent = reais(Math.abs(lucro));
        contaVendi.appendChild(valor);
      }
    };
    document.addEventListener("click", function (e) {
      var resumo = e.target.closest && e.target.closest("details[data-vendi] > summary");
      if (!resumo) return;
      e.preventDefault();
      var d = resumo.parentNode;
      origemVendi = resumo;
      formVendi.setAttribute("action", d.getAttribute("data-vendi-acao"));
      formVendi.querySelector("[data-janela-vendi-lote]").value = d.getAttribute("data-vendi-lote") || "";
      dialogoVendi.setAttribute("data-nome-atual", d.getAttribute("data-vendi-nome") || "");
      var qtd = parseInt(d.getAttribute("data-vendi-qtd"), 10) || 1;
      campoQtd.max = String(qtd);
      campoQtd.value = String(qtd);
      formVendi.querySelector("[data-janela-vendi-qtd-campo]").hidden = qtd <= 1;
      formVendi.querySelector("[data-janela-vendi-de]").textContent = "de " + qtd;
      // Preço que vem preenchido (pedido do usuário, 16/11): quem anuncia
      // costuma usar o "Lucrar X%" recomendado na própria linha; sem valor
      // pago, o preço de hoje.
      var trVenda = d.closest("tr");
      var empateVenda = trVenda ? Number(trVenda.getAttribute("data-empate") || 0) : 0;
      var seletorMeta = document.querySelector('.form-meta-lucro [name="meta"]');
      var metaVenda = Number((seletorMeta && seletorMeta.value) || 20);
      var dica = formVendi.querySelector("[data-janela-vendi-dica]");
      var anuncioVenda = d.getAttribute("data-vendi-anuncio");
      if (anuncioVenda) {
        campoPreco.value = anuncioVenda;
        if (dica) dica.textContent = "Já vem o preço do seu anúncio. Corrija se vendeu por outro valor.";
      } else if (empateVenda > 0) {
        campoPreco.value = (Math.round(empateVenda * (1 + metaVenda / 100) * 100) / 100).toFixed(2).replace(".", ",");
        if (dica) dica.textContent = "Já vem o preço para lucrar " + metaVenda + "%, o recomendado na sua conta. Corrija se vendeu por outro valor.";
      } else {
        campoPreco.value = d.getAttribute("data-vendi-preco") || "";
        if (dica) dica.textContent = "Já vem o preço de hoje. Corrija se vendeu por outro valor.";
      }
      var custo = d.getAttribute("data-vendi-custo");
      custoVendi = custo ? Number(custo) : null;
      contarVenda();
      mostrarPasso(1);
      dialogoVendi.showModal();
      campoPreco.focus();
      campoPreco.select();
    });
    campoQtd.addEventListener("input", contarVenda);
    campoPreco.addEventListener("input", contarVenda);
    // Duas confirmações (pedido do usuário, 16/11): "Confirmar venda"
    // mostra o resumo; só o "Sim, vendi" envia.
    var passo1 = formVendi.querySelector("[data-janela-vendi-passo1]");
    var passo2 = formVendi.querySelector("[data-janela-vendi-passo2]");
    var confirmado = formVendi.querySelector("[data-janela-vendi-confirmado]");
    var tituloVenda = dialogoVendi.querySelector(".dialogo-titulo");
    var tituloOriginal = tituloVenda.innerHTML;
    var nomeVenda = function () { return dialogoVendi.getAttribute("data-nome-atual") || ""; };
    var preencher = function (sel, texto) {
      var el = formVendi.querySelector(sel);
      if (el) el.textContent = texto;
      return el;
    };
    var mostrarPasso = function (n) {
      passo1.hidden = n !== 1;
      passo2.hidden = n !== 2;
      confirmado.value = "";
      if (n === 1) {
        tituloVenda.innerHTML = tituloOriginal;
        var nomeEl = tituloVenda.querySelector("[data-janela-vendi-nome]");
        if (nomeEl) nomeEl.textContent = nomeVenda();
      }
    };
    formVendi.addEventListener("submit", function (e) {
      if (!passo2.hidden) { confirmado.value = "1"; normalizarValor(campoPreco); return; }
      e.preventDefault();
      var preco = lerPreco();
      if (!isFinite(preco) || preco <= 0) { campoPreco.focus(); return; }
      var qtd = Math.max(1, parseInt(campoQtd.value, 10) || 1);
      var recebe = preco / (1 + taxaVendi) * qtd;
      tituloVenda.textContent = "Confirmar a venda?";
      var origem = origemVendi ? origemVendi.parentNode : null;
      var attr = function (n) { return origem ? origem.getAttribute(n) || "" : ""; };
      preencher("[data-resumo-item]", attr("data-vendi-nome-curto") || nomeVenda());
      var detalhe = [];
      if (attr("data-vendi-exterior")) detalhe.push(attr("data-vendi-exterior"));
      if (qtd > 1) detalhe.push(qtd + " unidades");
      preencher("[data-resumo-detalhe]", detalhe.join(" · "));
      var img = formVendi.querySelector("[data-resumo-icone]");
      var quadro = formVendi.querySelector("[data-resumo-icone-quadro]");
      quadro.className = "icone-item-quadro icone-item-quadro-compacto" + (attr("data-vendi-icone") ? " icone-item-quadro-com-imagem" : "") + (attr("data-vendi-raridade") ? " " + attr("data-vendi-raridade") : "");
      if (attr("data-vendi-icone")) { img.src = attr("data-vendi-icone"); img.hidden = false; } else { img.removeAttribute("src"); img.hidden = true; }
      preencher("[data-resumo-preco-rotulo]", qtd > 1 ? "O comprador pagou (cada)" : "O comprador pagou");
      preencher("[data-resumo-preco]", reais(preco));
      preencher("[data-resumo-recebe]", reais(recebe));
      preencher("[data-resumo-recebe-rotulo]", qtd > 1 ? "Você recebe (total)" : "Você recebe");
      preencher("[data-resumo-pagou-rotulo]", qtd > 1 ? "Você pagou (total)" : "Você pagou");
      formVendi.querySelector("[data-resumo-pagou-linha]").hidden = custoVendi === null;
      var linhaRes = formVendi.querySelector("[data-resumo-resultado-linha]");
      linhaRes.hidden = custoVendi === null;
      if (custoVendi !== null) {
        preencher("[data-resumo-pagou]", reais(custoVendi * qtd));
        var lucro = recebe - custoVendi * qtd;
        preencher("[data-resumo-resultado-rotulo]", lucro < 0 ? "Prejuízo" : "Lucro");
        preencher("[data-resumo-resultado]", (lucro > 0 ? "+" : lucro < 0 ? "−" : "") + reais(Math.abs(lucro)));
        linhaRes.className = "resumo-venda-resultado" + (lucro > 0 ? " resultado-positivo" : lucro < 0 ? " resultado-negativo" : "");
      }
      mostrarPasso(2);
      tituloVenda.textContent = "Confirmar a venda?";
      formVendi.querySelector("[data-janela-vendi-sim]").focus();
    });
    formVendi.querySelector("[data-janela-vendi-voltar]").addEventListener("click", function () {
      mostrarPasso(1);
      campoPreco.focus();
    });
    formVendi.querySelector("[data-janela-vendi-cancelar]").addEventListener("click", function () { dialogoVendi.close(); });
    dialogoVendi.addEventListener("click", function (e) { if (e.target === dialogoVendi) dialogoVendi.close(); });
    dialogoVendi.addEventListener("close", function () { if (origemVendi) origemVendi.focus(); });
  }

  // "Anunciado por quanto?" (pedido do usuário, 16/11): marcar "Está
  // anunciado" ou "mudar preço" abre a janela, já com o preço "Lucrar X%"
  // da linha (ou o anunciado antes); "Salvar" envia o formulário da linha.
  // Desmarcar envia direto. Sem <dialog>, o campo aparece na linha.
  var dialogoAnuncio = document.getElementById("dialogo-anuncio");
  if (dialogoAnuncio && typeof dialogoAnuncio.showModal === "function") {
    var formJanela = dialogoAnuncio.querySelector("[data-janela-anuncio-form]");
    var campoAnuncio = formJanela.querySelector("[data-janela-anuncio-preco]");
    var contaAnuncio = formJanela.querySelector("[data-janela-anuncio-conta]");
    var dicaAnuncio = formJanela.querySelector("[data-janela-anuncio-dica]");
    var tabelaAnuncio = document.querySelector(".tabela-conta");
    var taxaAnuncio = Number((tabelaAnuncio && tabelaAnuncio.getAttribute("data-taxa")) || 15) / 100;
    var formLinha = null;
    var origemAnuncio = null;
    var lerAnuncio = function () {
      var v = campoAnuncio.value.replace(/R\$/g, "").replace(/[\s\u00a0]/g, "");
      if (v.indexOf(",") !== -1) v = v.replace(/\./g, "").replace(",", ".");
      return Number(v);
    };
    var contarAnuncio = function () {
      contaAnuncio.textContent = "";
      var preco = lerAnuncio();
      if (!formLinha || !isFinite(preco) || preco <= 0) return;
      var recebe = preco / (1 + taxaAnuncio);
      contaAnuncio.appendChild(document.createTextNode("Se vender por esse preço, você recebe ≈ "));
      var forte = document.createElement("strong");
      forte.textContent = reais(recebe);
      contaAnuncio.appendChild(forte);
      var custo = formLinha.getAttribute("data-anuncio-custo");
      if (custo) {
        var lucro = recebe - Number(custo);
        contaAnuncio.appendChild(document.createTextNode(" cada · " + (lucro < 0 ? "prejuízo" : "lucro") + " ≈ "));
        var valor = document.createElement("strong");
        valor.className = lucro > 0 ? "valor-positivo" : lucro < 0 ? "valor-negativo" : "";
        valor.textContent = reais(Math.abs(lucro));
        contaAnuncio.appendChild(valor);
        contaAnuncio.appendChild(document.createTextNode(" cada"));
      } else {
        contaAnuncio.appendChild(document.createTextNode(" cada."));
      }
    };
    var abrirAnuncio = function (form, origem) {
      formLinha = form;
      origemAnuncio = origem;
      formJanela.querySelector("[data-janela-anuncio-nome]").textContent = form.getAttribute("data-anuncio-nome") || "";
      var atual = form.getAttribute("data-anuncio-atual");
      var tr = form.closest("tr");
      var empate = tr ? Number(tr.getAttribute("data-empate") || 0) : 0;
      var seletor = document.querySelector('.form-meta-lucro [name="meta"]');
      var meta = Number((seletor && seletor.value) || 20);
      if (atual) {
        campoAnuncio.value = atual;
        dicaAnuncio.textContent = "O preço que você informou antes. Mude se alterou o anúncio.";
      } else if (empate > 0) {
        campoAnuncio.value = (Math.round(empate * (1 + meta / 100) * 100) / 100).toFixed(2).replace(".", ",");
        dicaAnuncio.textContent = "Já vem o preço para lucrar " + meta + "%, o recomendado na sua conta. Corrija se anunciou por outro valor.";
      } else {
        campoAnuncio.value = form.getAttribute("data-anuncio-preco-hoje") || "";
        dicaAnuncio.textContent = "Já vem o preço de hoje. Corrija se anunciou por outro valor.";
      }
      contarAnuncio();
      dialogoAnuncio.showModal();
      campoAnuncio.focus();
      campoAnuncio.select();
    };
    Array.prototype.forEach.call(document.querySelectorAll("form[data-anuncio]"), function (form) {
      var caixa = form.querySelector('input[name="anunciado"]');
      var mudar = form.querySelector("[data-mudar-anuncio]");
      if (mudar) {
        mudar.hidden = false;
        mudar.addEventListener("click", function () { abrirAnuncio(form, mudar); });
      }
      if (!caixa) return;
      caixa.addEventListener("click", function (e) {
        if (caixa.checked) {
          // Ia marcar: fica desmarcada até "Salvar".
          e.preventDefault();
          abrirAnuncio(form, caixa);
        } else {
          form.submit();
        }
      });
    });
    campoAnuncio.addEventListener("input", contarAnuncio);
    formJanela.addEventListener("submit", function (e) {
      e.preventDefault();
      var preco = lerAnuncio();
      if (!formLinha || !isFinite(preco) || preco <= 0) { campoAnuncio.focus(); return; }
      formLinha.querySelector('input[name="anuncio_preco"]').value = preco.toFixed(2).replace(".", ",");
      formLinha.querySelector('input[name="anunciado"]').checked = true;
      origemAnuncio = null;
      dialogoAnuncio.close();
      formLinha.submit();
    });
    formJanela.querySelector("[data-janela-anuncio-cancelar]").addEventListener("click", function () { dialogoAnuncio.close(); });
    dialogoAnuncio.addEventListener("click", function (e) { if (e.target === dialogoAnuncio) dialogoAnuncio.close(); });
    dialogoAnuncio.addEventListener("close", function () { if (origemAnuncio) origemAnuncio.focus(); });
  }
})();

// Sugestões de nome ao digitar (pedido 17/11): Watchlist e
// "Adicionar um item à mão" pedem o nome exato do Mercado, em inglês.
// Enquanto a pessoa digita (em português ou inglês), /api/sugestoes
// devolve até 8 nomes do catálogo do próprio site, com o preço de hoje.
(function () {
  var campos = document.querySelectorAll("input[data-sugerir]");
  if (!campos.length || !window.fetch) return;
  var lista = document.getElementById("sugestoes-itens");
  if (!lista) {
    lista = document.createElement("datalist");
    lista.id = "sugestoes-itens";
    document.body.appendChild(lista);
  }
  var vistos = {};
  var espera = null;
  var ultima = "";
  function reais(v) { return v.toFixed(2).replace(".", ","); }
  function buscar(campo) {
    var q = campo.value.trim();
    if (q.length < 2 || q === ultima || vistos[q]) return;
    ultima = q;
    fetch("/api/sugestoes?q=" + encodeURIComponent(q), { credentials: "same-origin" })
      .then(function (r) { return r.ok ? r.json() : []; })
      .then(function (itens) {
        if (campo.value.trim() !== q) return; // a pessoa já digitou outra coisa
        lista.textContent = "";
        itens.forEach(function (it) {
          vistos[it.nome] = true;
          var op = document.createElement("option");
          op.value = it.nome;
          op.label = (it.nome_pt !== it.nome ? it.nome_pt : "") +
            (typeof it.preco === "number" ? (it.nome_pt !== it.nome ? " · " : "") + "R$ " + reais(it.preco) : "");
          lista.appendChild(op);
        });
      })
      .catch(function () { /* sem sugestão: o campo continua livre */ });
  }
  function ligar(campo) {
    campo.setAttribute("list", "sugestoes-itens");
    campo.addEventListener("input", function () {
      if (vistos[campo.value]) return;
      clearTimeout(espera);
      espera = setTimeout(function () { buscar(campo); }, 250);
    });
  }
  Array.prototype.forEach.call(campos, ligar);
})();
