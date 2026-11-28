// Busca rápida (Spotlight, Ctrl+K ou "/") e alternador de Filtros do
// cabeçalho. Fica separado do app.js para funcionar em todas as páginas
// que renderizam o cabeçalho (incluindo Ranking, Método, Status e Conta),
// sem puxar scripts exclusivos da home/item nem conflitar com conta.js.
(function () {
  "use strict";

  var overlay = document.getElementById("spotlight-overlay");
  var input = document.getElementById("spotlight-input");
  var resultados = document.getElementById("spotlight-resultados");
  var fecharBtn = document.getElementById("spotlight-fechar");
  var gatilhoBtn = document.getElementById("gatilho-spotlight");

  function campoEmFoco() {
    var ativo = document.activeElement;
    return !!(ativo && (ativo.tagName === "INPUT"
      || ativo.tagName === "TEXTAREA"
      || ativo.tagName === "SELECT"
      || ativo.isContentEditable));
  }

  function escapeHtml(s) {
    if (!s) return "";
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function classeNota(score) {
    if (score >= 70) return "nota-alta";
    if (score >= 45) return "nota-media";
    return "nota-baixa";
  }

  if (overlay && input && resultados) {
    var debounceTimer = null;
    var indiceAtivo = -1;
    var seqBusca = 0;
    var controlador = null;
    // Dica curta em tela estreita: a longa ("Buscar entre 33.000 skins e
    // caixas...") era cortada no meio em 320px (27/11).
    var dicaLonga = input.getAttribute("placeholder") || "";

    function cancelarBuscaPendente() {
      clearTimeout(debounceTimer);
      seqBusca++;
      if (controlador) {
        try { controlador.abort(); } catch (e) {}
        controlador = null;
      }
    }

    function limparAtivo() {
      indiceAtivo = -1;
      input.removeAttribute("aria-activedescendant");
    }

    function mostrarMensagem(classe, texto) {
      limparAtivo();
      input.setAttribute("aria-expanded", "false");
      resultados.innerHTML = '<div class="' + classe + '"><p class="spotlight-dica-texto">' + escapeHtml(texto) + "</p></div>";
    }

    function abrirSpotlight() {
      cancelarBuscaPendente();
      var estreita = window.matchMedia && window.matchMedia("(max-width: 640px)").matches;
      input.setAttribute("placeholder", estreita ? "Buscar skin ou caixa" : dicaLonga);
      overlay.hidden = false;
      overlay.removeAttribute("aria-hidden");
      input.value = "";
      mostrarMensagem(
        "spotlight-dica-inicial",
        "Digite o nome em português ou inglês para buscar instantaneamente no catálogo e nas notas do Lodout."
      );
      setTimeout(function () { input.focus(); }, 50);
    }

    function fecharSpotlight() {
      cancelarBuscaPendente();
      limparAtivo();
      input.setAttribute("aria-expanded", "false");
      overlay.hidden = true;
      overlay.setAttribute("aria-hidden", "true");
      if (gatilhoBtn) gatilhoBtn.focus();
    }

    if (gatilhoBtn) {
      gatilhoBtn.addEventListener("click", function (e) {
        e.preventDefault();
        abrirSpotlight();
      });
    }
    if (fecharBtn) {
      fecharBtn.addEventListener("click", fecharSpotlight);
    }
    // Toque fora da janela fecha (27/11: no celular não havia como sair
    // sem o botão quando ele ficava fora da tela).
    overlay.addEventListener("click", function (e) {
      if (!e.target.closest(".spotlight-modal")) fecharSpotlight();
    });

    function atualizarAtivo(itens) {
      for (var i = 0; i < itens.length; i++) {
        if (i === indiceAtivo) {
          itens[i].classList.add("spotlight-item-ativo");
          itens[i].setAttribute("aria-selected", "true");
          if (itens[i].id) input.setAttribute("aria-activedescendant", itens[i].id);
          itens[i].scrollIntoView({ block: "nearest" });
        } else {
          itens[i].classList.remove("spotlight-item-ativo");
          itens[i].setAttribute("aria-selected", "false");
        }
      }
    }

    document.addEventListener("keydown", function (e) {
      if ((e.ctrlKey || e.metaKey) && !e.altKey && e.key && e.key.toLowerCase() === "k") {
        e.preventDefault();
        if (overlay.hidden) abrirSpotlight();
        else fecharSpotlight();
        return;
      }
      if (overlay.hidden) {
        if (e.key === "/" && !e.ctrlKey && !e.metaKey && !e.altKey && !campoEmFoco()) {
          e.preventDefault();
          abrirSpotlight();
        }
        return;
      }
      if (e.key === "Escape") {
        e.preventDefault();
        fecharSpotlight();
        return;
      }
      // Tab fica dentro da busca aberta (janela modal): do último item volta
      // para o primeiro, e Shift+Tab faz o caminho inverso (27/11).
      if (e.key === "Tab") {
        var focaveis = Array.prototype.filter.call(
          overlay.querySelectorAll("input, button, a[href]"),
          function (el) { return el.offsetParent !== null && !el.disabled; }
        );
        if (focaveis.length) {
          var primeiro = focaveis[0];
          var ultimo = focaveis[focaveis.length - 1];
          var dentro = overlay.contains(document.activeElement);
          if (e.shiftKey && (document.activeElement === primeiro || !dentro)) {
            e.preventDefault();
            ultimo.focus();
          } else if (!e.shiftKey && (document.activeElement === ultimo || !dentro)) {
            e.preventDefault();
            primeiro.focus();
          }
        }
        return;
      }
      var itens = resultados.querySelectorAll(".spotlight-item");
      if (!itens.length) return;
      if (e.key === "ArrowDown") {
        e.preventDefault();
        indiceAtivo = (indiceAtivo + 1) % itens.length;
        atualizarAtivo(itens);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        indiceAtivo = (indiceAtivo - 1 + itens.length) % itens.length;
        atualizarAtivo(itens);
      } else if (e.key === "Enter") {
        if (indiceAtivo >= 0 && itens[indiceAtivo]) {
          e.preventDefault();
          itens[indiceAtivo].click();
        }
      }
    });

    input.addEventListener("input", function () {
      cancelarBuscaPendente();
      var q = input.value.trim();
      if (q.length < 2) {
        mostrarMensagem("spotlight-dica-inicial", "Digite pelo menos 2 letras para buscar...");
        return;
      }
      var minhaSeq = seqBusca;
      debounceTimer = setTimeout(function () {
        var opcoes = {};
        if (window.AbortController) {
          controlador = new AbortController();
          opcoes.signal = controlador.signal;
        }
        fetch("/api/sugestoes?q=" + encodeURIComponent(q), opcoes)
          .then(function (res) {
            if (res.status === 429) return { erro: "limite" };
            if (!res.ok) return { erro: "servidor" };
            return res.json().then(function (lista) { return { lista: lista }; });
          })
          .then(function (resp) {
            // Descarta resposta antiga se o usuário já alterou ou fechou a busca.
            if (minhaSeq !== seqBusca || overlay.hidden || input.value.trim() !== q) return;
            if (resp.erro === "limite") {
              mostrarMensagem("spotlight-sem-resultado", "Muitas buscas seguidas — aguarde alguns segundos.");
              return;
            }
            if (resp.erro || !Array.isArray(resp.lista)) {
              mostrarMensagem("spotlight-sem-resultado", "Não foi possível buscar agora. Tente novamente.");
              return;
            }
            var lista = resp.lista;
            limparAtivo();
            if (!lista.length) {
              mostrarMensagem("spotlight-sem-resultado", 'Nenhum item encontrado para "' + q + '".');
              return;
            }
            var html = "";
            for (var i = 0; i < lista.length; i++) {
              var item = lista[i];
              var imgHtml = item.icon_url
                ? '<img class="spotlight-item-img" src="' + escapeHtml(item.icon_url) + '" alt="" width="36" height="36" loading="lazy">'
                : '<span class="icone-item-placeholder"></span>';
              var scoreHtml = (typeof item.score === "number")
                ? '<span class="spotlight-item-score ' + classeNota(item.score) + '">Nota ' + Math.round(item.score) + "</span>"
                : '<span class="spotlight-item-sem-score">Catálogo</span>';
              var precoHtml = item.preco_fmt ? '<span class="spotlight-item-preco">' + escapeHtml(item.preco_fmt) + "</span>" : "";
              var rarClasse = item.raridade_classe ? " " + escapeHtml(item.raridade_classe) : "";
              html += '<a id="spotlight-opt-' + i + '" class="spotlight-item' + rarClasse + '" href="' + escapeHtml(item.url || ("/item/" + encodeURIComponent(item.nome))) + '" role="option" aria-selected="false">' +
                '<span class="spotlight-item-img-wrap' + rarClasse + '">' + imgHtml + "</span>" +
                '<div class="spotlight-item-info">' +
                  '<strong class="spotlight-item-nome" translate="no">' + escapeHtml(item.nome_pt || item.nome) + "</strong>" +
                  (item.nome_pt && item.nome_pt !== item.nome ? '<span class="spotlight-item-sub">' + escapeHtml(item.nome) + "</span>" : "") +
                "</div>" +
                '<div class="spotlight-item-lado">' +
                  precoHtml +
                  scoreHtml +
                "</div>" +
              "</a>";
            }
            resultados.innerHTML = html;
            input.setAttribute("aria-expanded", "true");
          })
          .catch(function (err) {
            if (err && err.name === "AbortError") return;
            if (minhaSeq !== seqBusca || overlay.hidden) return;
            mostrarMensagem("spotlight-sem-resultado", "Não foi possível buscar agora. Tente novamente.");
          });
      }, 150);
    });
  }

  // Alternador do painel de Filtros integrado à barra de pesquisa do topo.
  var btnFiltroTopo = document.getElementById("gatilho-filtros-topo");
  var detFiltros = document.querySelector(".filtros-mais");
  var btnFecharPopover = document.getElementById("fechar-filtros-popover");
  var btnFiltroSpotlight = document.getElementById("spotlight-filtro-btn");

  function alternarFiltros(forcar) {
    if (!detFiltros) {
      window.location.href = "/?abrir_filtros=1";
      return;
    }
    var novoEstado = (typeof forcar === "boolean") ? forcar : !detFiltros.open;
    detFiltros.open = novoEstado;
    if (btnFiltroTopo) {
      btnFiltroTopo.setAttribute("aria-expanded", novoEstado ? "true" : "false");
    }
    if (novoEstado) {
      var reduzir = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      detFiltros.scrollIntoView({ behavior: reduzir ? "auto" : "smooth", block: "nearest" });
      // Foco vai para o primeiro campo do painel (auditoria 28/11): a
      // página rolava até os filtros, mas o Tab seguia pelo topo e por
      // ~15 links antes de chegar lá.
      var primeiro = detFiltros.querySelector(".filtros-mais-corpo input:not([type=hidden]), .filtros-mais-corpo select, .filtros-mais-corpo button, .filtros-mais-corpo a[href]");
      if (primeiro) primeiro.focus({ preventScroll: true });
    } else {
      devolverFoco();
    }
  }

  // Fechou com o foco lá dentro: ele volta para o botão que abriu.
  function devolverFoco() {
    if (btnFiltroTopo && detFiltros.contains(document.activeElement)) btnFiltroTopo.focus();
  }

  if (btnFiltroTopo) {
    btnFiltroTopo.addEventListener("click", function (e) {
      e.preventDefault();
      alternarFiltros();
    });
  }

  if (btnFecharPopover) {
    btnFecharPopover.addEventListener("click", function (e) {
      e.preventDefault();
      alternarFiltros(false);
    });
  }

  if (btnFiltroSpotlight) {
    btnFiltroSpotlight.addEventListener("click", function (e) {
      e.preventDefault();
      if (fecharBtn) fecharBtn.click();
      setTimeout(function () { alternarFiltros(true); }, 120);
    });
  }

  if (detFiltros) {
    detFiltros.addEventListener("toggle", function () {
      if (btnFiltroTopo) {
        btnFiltroTopo.setAttribute("aria-expanded", detFiltros.open ? "true" : "false");
      }
    });

    document.addEventListener("click", function (e) {
      if (!detFiltros.open) return;
      if (detFiltros.contains(e.target) || (btnFiltroTopo && btnFiltroTopo.contains(e.target))) return;
      detFiltros.open = false;
      if (btnFiltroTopo) btnFiltroTopo.setAttribute("aria-expanded", "false");
    });

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && detFiltros.open) {
        detFiltros.open = false;
        if (btnFiltroTopo) btnFiltroTopo.setAttribute("aria-expanded", "false");
        devolverFoco();
      }
    });
  }

  if (window.location.search.indexOf("abrir_filtros=1") !== -1 && detFiltros) {
    detFiltros.open = true;
    if (btnFiltroTopo) btnFiltroTopo.setAttribute("aria-expanded", "true");
  }
})();
