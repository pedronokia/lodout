(function () {
  ["notas", "favoritos", "comparar", "ultima_visita", "buscas_salvas"].forEach(function (k) {
    ["galaseca_", "skinvault_"].forEach(function (prefixoAntigo) {
      try {
        var antigo = localStorage.getItem(prefixoAntigo + k);
        if (antigo === null) return;
        if (localStorage.getItem("lodout_" + k) === null) {
          localStorage.setItem("lodout_" + k, antigo);
        }
        localStorage.removeItem(prefixoAntigo + k);
      } catch (e) {}
    });
  });
})();
function anunciar(msg) {
  try {
    var regiao = document.getElementById("anuncio-ao-vivo");
    if (!regiao) {
      regiao = document.createElement("div");
      regiao.id = "anuncio-ao-vivo";
      regiao.className = "visualmente-oculto";
      regiao.setAttribute("role", "status");
      regiao.setAttribute("aria-live", "polite");
      document.body.appendChild(regiao);
    }
    regiao.textContent = "";
    setTimeout(function () { regiao.textContent = msg; }, 50);
  } catch (e) {}
}
document.documentElement.classList.add("js-ativo");
document.addEventListener("change", function (e) {
  var campo = e.target;
  if (!campo.matches || !campo.matches("[data-enviar-ao-mudar]") || !campo.form) return;
  campo.form.submit();
});
document.addEventListener("click", function (e) {
  var btn = e.target.closest(".botao-copiar");
  if (!btn) return;
  var texto = btn.getAttribute("data-copiar") || btn.getAttribute("data-copiar-link");
  if (!texto || !navigator.clipboard) return;
  navigator.clipboard.writeText(texto).then(function () {
    var label = btn.querySelector(".texto-copiar");
    if (!label) return;
    var original = label.textContent;
    var originalAria = btn.getAttribute("aria-label");
    label.textContent = "Copiado";
    anunciar("Copiado");
    btn.classList.add("copiado");
    btn.setAttribute("aria-label", "Copiado");
    setTimeout(function () {
      label.textContent = original;
      btn.classList.remove("copiado");
      if (originalAria) btn.setAttribute("aria-label", originalAria);
      else btn.removeAttribute("aria-label");
    }, 1200);
  }).catch(function () {});
});
document.addEventListener("click", function (e) {
  var btn = e.target.closest(".botao-recolher-motivo");
  if (!btn) return;
  var detalhes = btn.closest("details");
  if (detalhes) detalhes.open = false;
});
document.addEventListener("submit", function (e) {
  var form = e.target;
  if (!form.querySelector) return;
  var btn = form.querySelector(".botao-remover[type=\"submit\"]");
  if (!btn) return;
  if (!window.confirm("Remover? Essa ação não pode ser desfeita.")) {
    e.preventDefault();
  }
});
document.addEventListener("error", function (e) {
  if (e.target.matches && e.target.matches(".icone-item")) {
    e.target.classList.add("icone-item-indisponivel");
    var quadro = e.target.closest(".icone-item-quadro");
    if (quadro) quadro.classList.remove("icone-item-quadro-com-imagem");
  }
}, true);
// ==========================================================================
// Busca e Filtragem Instantânea no Navegador (0ms UX)
// ==========================================================================
(function () {
  var campo = document.getElementById("campo-busca");
  if (!campo) return;

  function normalizar(txt) {
    if (!txt) return "";
    return txt.toString().toLowerCase()
      .normalize("NFD").replace(/[\u0300-\u036f]/g, "")
      .trim();
  }

  var cards = document.querySelectorAll(".grade-cards .cartao-item, .cartao-item");
  var rows = document.querySelectorAll(".tabela-itens tbody tr, .tabela-candidatos tbody tr");
  var hero = document.querySelector(".hero-destaque");
  var heroNomeNorm = hero ? normalizar(hero.querySelector(".hero-destaque-nome") ? hero.querySelector(".hero-destaque-nome").textContent : "") : "";
  var itens = [];

  // Pré-indexa os cards da vitrine
  cards.forEach(function (el) {
    var nomeEl = el.querySelector(".cartao-item-nome, .link-item");
    var nome = el.getAttribute("data-nome") || (nomeEl ? nomeEl.textContent : "") || el.textContent || "";
    itens.push({
      el: el,
      tipo: "card",
      nomeNorm: normalizar(nome)
    });
  });

  // Pré-indexa as linhas da tabela
  rows.forEach(function (el) {
    var nomeEl = el.querySelector(".link-item");
    var nome = el.getAttribute("data-nome") || (nomeEl ? nomeEl.textContent : "") || el.textContent || "";
    itens.push({
      el: el,
      tipo: "row",
      nomeNorm: normalizar(nome)
    });
  });

  var debounceTimer = null;
  function executarFiltro() {
    var termo = normalizar(campo.value);
    var termos = termo ? termo.split(/\s+/).filter(Boolean) : [];
    var visiveis = 0;

    // Filtra o hero card em destaque se presente
    if (hero) {
      var heroBateu = true;
      if (termos.length > 0) {
        for (var ht = 0; ht < termos.length; ht++) {
          if (heroNomeNorm.indexOf(termos[ht]) === -1) {
            heroBateu = false;
            break;
          }
        }
      }
      if (heroBateu || termos.length === 0) {
        hero.removeAttribute("hidden");
        hero.style.removeProperty("display");
      } else {
        hero.setAttribute("hidden", "");
        hero.style.setProperty("display", "none", "important");
      }
    }

    for (var i = 0; i < itens.length; i++) {
      var it = itens[i];
      var bateu = true;

      if (termos.length > 0) {
        for (var t = 0; t < termos.length; t++) {
          if (it.nomeNorm.indexOf(termos[t]) === -1) {
            bateu = false;
            break;
          }
        }
      }

      if (bateu) {
        it.el.removeAttribute("hidden");
        it.el.style.removeProperty("display");
        visiveis++;
      } else {
        it.el.setAttribute("hidden", "");
        it.el.style.setProperty("display", "none", "important");
      }
    }

    try {
      var url = new URL(window.location.href);
      if (campo.value.trim()) {
        url.searchParams.set("q", campo.value.trim());
      } else {
        url.searchParams.delete("q");
      }
      window.history.replaceState({}, "", url.toString());
    } catch (e) {}

    var avisoVazio = document.getElementById("busca-instantanea-vazia");
    if (termo && visiveis === 0 && itens.length > 0) {
      if (!avisoVazio) {
        avisoVazio = document.createElement("div");
        avisoVazio.id = "busca-instantanea-vazia";
        avisoVazio.className = "card card-aviso-vazio";
        avisoVazio.style.margin = "20px 0";
        avisoVazio.style.textAlign = "center";
        avisoVazio.style.padding = "24px 16px";
        var container = document.querySelector(".grade-cards, .tabela-wrap, .tabela-candidatos");
        if (container && container.parentNode) {
          container.parentNode.insertBefore(avisoVazio, container);
        }
      }
      avisoVazio.innerHTML = '<p style="color: rgba(255,255,255,0.7); margin: 0;">Nenhum item corresponde a "<strong>' +
        campo.value.replace(/</g, "&lt;").replace(/>/g, "&gt;") + '</strong>" nesta página.</p>';
      avisoVazio.removeAttribute("hidden");
    } else if (avisoVazio) {
      avisoVazio.setAttribute("hidden", "");
    }
  }

  // Atalho "/" para focar o campo de busca
  document.addEventListener("keydown", function (e) {
    if (e.key === "/" && !e.ctrlKey && !e.metaKey) {
      var ativo = document.activeElement;
      var campoAberto = ativo && (ativo.tagName === "INPUT"
        || ativo.tagName === "TEXTAREA" || ativo.tagName === "SELECT");
      if (campoAberto) return;
      e.preventDefault();
      campo.focus();
    } else if (e.key === "Escape" && document.activeElement === campo) {
      campo.value = "";
      executarFiltro();
      campo.blur();
    }
  });

  campo.addEventListener("input", function () {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(executarFiltro, 30);
  });

  var form = campo.closest("form");
  if (form) {
    form.addEventListener("submit", function (e) {
      executarFiltro();
    });
  }
})();
(function () {
  var CHAVE = "lodout_notas";
  function lerTudo() {
    try {
      return JSON.parse(localStorage.getItem(CHAVE) || "{}");
    } catch (e) { return {}; }
  }
  function botaoDoCampo(campo) {
    var celula = campo.closest(".celula-item");
    return celula ? celula.querySelector(".botao-nota-toggle") : null;
  }
  try {
    var notas = lerTudo();
    document.querySelectorAll(".input-tag-local").forEach(function (campo) {
      var item = campo.getAttribute("data-item");
      if (!notas[item]) return;
      campo.value = notas[item];
      campo.hidden = false;
      var botao = botaoDoCampo(campo);
      if (botao) {
        botao.classList.add("tem-nota");
        botao.setAttribute("aria-expanded", "true");
      }
    });
  } catch (e) {}
  document.addEventListener("click", function (e) {
    var botao = e.target.closest(".botao-nota-toggle");
    if (!botao) return;
    var celula = botao.closest(".celula-item");
    var campo = celula && celula.querySelector(".input-tag-local");
    if (!campo) return;
    campo.hidden = !campo.hidden;
    botao.setAttribute("aria-expanded", String(!campo.hidden));
    if (!campo.hidden) campo.focus();
  });
  document.addEventListener("change", function (e) {
    if (!e.target.classList || !e.target.classList.contains("input-tag-local")) return;
    try {
      var todas = lerTudo();
      var item = e.target.getAttribute("data-item");
      if (e.target.value) {
        todas[item] = e.target.value;
      } else {
        delete todas[item];
      }
      localStorage.setItem(CHAVE, JSON.stringify(todas));
    } catch (e) {}
    var botao = botaoDoCampo(e.target);
    if (botao) botao.classList.toggle("tem-nota", !!e.target.value);
  });
  document.addEventListener("blur", function (e) {
    if (!e.target.classList || !e.target.classList.contains("input-tag-local")) return;
    if (e.target.value) return;
    e.target.hidden = true;
    var botao = botaoDoCampo(e.target);
    if (botao) botao.setAttribute("aria-expanded", "false");
  }, true);
})();
(function () {
  var CHAVE = "lodout_favoritos";
  function lerTudo() {
    try {
      return JSON.parse(localStorage.getItem(CHAVE) || "{}");
    } catch (e) { return {}; }
  }
  function salvar(todos) {
    try { localStorage.setItem(CHAVE, JSON.stringify(todos)); } catch (e) {}
  }
  function pintarBotao(btn, favoritado) {
    btn.classList.toggle("favoritado", favoritado);
    btn.setAttribute("aria-pressed", String(favoritado));
    var nome = btn.getAttribute("data-favorito-label") || btn.getAttribute("data-favorito");
    btn.setAttribute(
      "aria-label",
      (favoritado ? "Remover " : "Favoritar ") + nome + (favoritado ? " dos favoritos" : "")
    );
  }
  function aplicarEstadoInicial() {
    var favoritos = lerTudo();
    document.querySelectorAll(".botao-favorito").forEach(function (btn) {
      var item = btn.getAttribute("data-favorito");
      pintarBotao(btn, !!favoritos[item]);
    });
  }
  try { aplicarEstadoInicial(); } catch (e) {}
  function mostrarFavoritosFora(nomes) {
    var texto = document.getElementById("texto-sem-favoritos");
    var lista = document.getElementById("lista-favoritos-fora");
    if (!texto || !lista) return;
    lista.textContent = "";
    if (!nomes.length) {
      texto.textContent = "Nenhum favorito ainda. Toque na estrela de um item para salvar.";
      lista.hidden = true;
      return;
    }
    texto.textContent = nomes.length === 1
      ? "Seu favorito está em outra página da lista:"
      : "Seus " + nomes.length + " favoritos estão em outras páginas da lista:";
    nomes.sort().forEach(function (nome) {
      var li = document.createElement("li");
      var a = document.createElement("a");
      a.href = "/item/" + encodeURIComponent(nome);
      a.textContent = nome;
      li.appendChild(a);
      lista.appendChild(li);
    });
    lista.hidden = false;
  }
  document.addEventListener("click", function (e) {
    var btn = e.target.closest(".botao-favorito");
    if (!btn) return;
    try {
      var favoritos = lerTudo();
      var item = btn.getAttribute("data-favorito");
      var novoEstado = !favoritos[item];
      if (novoEstado) { favoritos[item] = true; } else { delete favoritos[item]; }
      salvar(favoritos);
      pintarBotao(btn, novoEstado);
      if (novoEstado) {
        btn.classList.remove("favoritando");
        void btn.offsetWidth; // força reflow pra reiniciar a animação em cliques seguidos
        btn.classList.add("favoritando");
      }
    } catch (e) {}
  });
  document.addEventListener("click", function (e) {
    var botao = e.target.closest("#botao-favoritos");
    if (!botao) return;
    try {
      var favoritos = lerTudo();
      var ativo = botao.classList.toggle("ativo");
      var algumVisivel = false;
      document.querySelectorAll("table.tabela-candidatos tbody tr[data-nome], .grade-cards .cartao-item[data-nome]").forEach(function (linha) {
        var botaoLinha = linha.querySelector(".botao-favorito");
        if (!botaoLinha) return;
        var item = botaoLinha.getAttribute("data-favorito");
        var escondida = ativo && !favoritos[item];
        linha.style.display = escondida ? "none" : "";
        if (!escondida) algumVisivel = true;
      });
      botao.setAttribute("aria-pressed", String(ativo));
      var semNenhum = ativo && !algumVisivel;
      document.querySelectorAll("table.tabela-candidatos, .grade-cards").forEach(function (t) {
        t.style.display = semNenhum ? "none" : "";
      });
      document.querySelectorAll(".paginacao").forEach(function (nav) {
        nav.hidden = ativo;
      });
      var msgVazio = document.getElementById("msg-sem-favoritos");
      if (msgVazio) {
        msgVazio.hidden = !semNenhum;
        mostrarFavoritosFora(Object.keys(favoritos));
      }
    } catch (e) {}
  });
})();
(function () {
  var CHAVE = "lodout_comparar";
  var MAX = 3;
  function ler() {
    try { return JSON.parse(sessionStorage.getItem(CHAVE) || "[]"); } catch (e) { return []; }
  }
  function salvar(lista) {
    try { sessionStorage.setItem(CHAVE, JSON.stringify(lista)); } catch (e) {}
  }
  var timerLimite = null;
  function avisarLimite() {
    var barra = document.getElementById("barra-comparar");
    if (!barra) return;
    var texto = barra.querySelector(".texto-comparar");
    var aviso = barra.querySelector(".aviso-comparar");
    if (!texto || !aviso) return;
    texto.hidden = true;
    aviso.hidden = false;
    barra.classList.add("barra-comparar-limite");
    clearTimeout(timerLimite);
    timerLimite = setTimeout(function () {
      texto.hidden = false;
      aviso.hidden = true;
      barra.classList.remove("barra-comparar-limite");
    }, 3000);
  }
  function atualizarBarra() {
    var lista = ler();
    var barra = document.getElementById("barra-comparar");
    if (!barra) return;
    if (lista.length < 1) { barra.hidden = true; return; }
    barra.hidden = false;
    var contagem = barra.querySelector(".contagem-comparar");
    if (contagem) contagem.textContent = lista.length;
    var link = barra.querySelector(".link-comparar");
    if (link) link.href = "/comparar?nomes=" + lista.map(encodeURIComponent).join(",");
  }
  try {
    var selecionados = ler();
    document.querySelectorAll(".checkbox-comparar").forEach(function (cb) {
      cb.checked = selecionados.indexOf(cb.getAttribute("data-comparar")) !== -1;
    });
    atualizarBarra();
  } catch (e) {}
  document.addEventListener("change", function (e) {
    if (!e.target.classList || !e.target.classList.contains("checkbox-comparar")) return;
    var lista = ler();
    var nome = e.target.getAttribute("data-comparar");
    if (e.target.checked) {
      if (lista.length >= MAX) {
        e.target.checked = false;
        anunciar("Limite de " + MAX + " itens pra comparar. Desmarque um pra trocar.");
        avisarLimite();
        return;
      }
      lista.push(nome);
    } else {
      lista = lista.filter(function (n) { return n !== nome; });
    }
    salvar(lista);
    atualizarBarra();
    anunciar(lista.length + " de " + MAX + " selecionados pra comparar");
  });
  document.addEventListener("click", function (e) {
    if (e.target.id !== "botao-limpar-comparar") return;
    salvar([]);
    document.querySelectorAll(".checkbox-comparar").forEach(function (cb) { cb.checked = false; });
    atualizarBarra();
    anunciar("Seleção pra comparar limpa");
  });
})();
(function () {
  var CHAVE = "lodout_ultima_visita";
  function lerAnterior() {
    try { return JSON.parse(localStorage.getItem(CHAVE) || "{}"); } catch (e) { return {}; }
  }
  try {
    var anterior = lerAnterior();
    var atual = {};
    document.querySelectorAll("table.tabela-candidatos tbody tr[data-nome], .grade-cards .cartao-item[data-nome]").forEach(function (tr) {
      var nome = tr.getAttribute("data-nome");
      var nota = parseInt(tr.getAttribute("data-nota"), 10);
      if (!nome || isNaN(nota)) return;
      atual[nome] = nota;
      var antes = anterior[nome];
      if (antes === undefined || antes === nota) return;
      var celulaNota = tr.querySelector(".celula-nota, .cartao-item-nota-area");
      if (!celulaNota) return;
      var subiu = nota > antes;
      var selo = document.createElement("span");
      selo.className = "selo-mudou-nota " + (subiu ? "tendencia-alta" : "tendencia-baixa");
      selo.title = "Nota " + (subiu ? "subiu" : "caiu") + " de " + antes + " pra " + nota + " desde sua última visita";
      selo.setAttribute("aria-label", "Nota " + (subiu ? "subiu" : "caiu") + " " + Math.abs(nota - antes) + " pontos desde sua última visita");
      var seta = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      seta.setAttribute("class", "icone-ui icone-ui-seta-" + (subiu ? "cima" : "baixo"));
      seta.setAttribute("viewBox", "0 0 24 24");
      seta.setAttribute("aria-hidden", "true");
      seta.setAttribute("focusable", "false");
      var tracado = document.createElementNS("http://www.w3.org/2000/svg", "path");
      tracado.setAttribute("d", subiu ? "m18 15-6-6-6 6M12 9v12" : "m18 9-6 6-6-6m6 6V3");
      seta.appendChild(tracado);
      selo.appendChild(seta);
      selo.appendChild(document.createTextNode(" " + Math.abs(nota - antes)));
      celulaNota.appendChild(selo);
    });
    if (Object.keys(atual).length) localStorage.setItem(CHAVE, JSON.stringify(atual));
  } catch (e) {}
})();
document.addEventListener("keydown", function (e) {
  if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
  var ativo = document.activeElement;
  var campoAberto = ativo && (ativo.tagName === "INPUT"
    || ativo.tagName === "TEXTAREA" || ativo.tagName === "SELECT");
  if (campoAberto) return;
  var id = e.key === "ArrowLeft" ? "link-pagina-anterior" : "link-pagina-seguinte";
  var link = document.getElementById(id);
  if (!link) return;
  e.preventDefault();
  link.click();
});
if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/sw.js").catch(function () {});
}
(function () {
  var topo = document.querySelector("header.topo");
  if (!topo) return;
  function atualizar() {
    document.documentElement.style.setProperty(
      "--altura-topo", topo.getBoundingClientRect().height + "px");
  }
  try {
    atualizar();
    if (window.ResizeObserver) new ResizeObserver(atualizar).observe(topo);
    else window.addEventListener("resize", atualizar);
  } catch (e) {}
})();
(function () {
  var botao = document.getElementById("botao-topo");
  if (!botao) return;
  function atualizar() {
    botao.hidden = window.scrollY < 600;
  }
  document.addEventListener("scroll", atualizar, { passive: true });
  botao.addEventListener("click", function () {
    var reduzirMovimento = window.matchMedia
      && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    window.scrollTo({ top: 0, behavior: reduzirMovimento ? "auto" : "smooth" });
  });
  try { atualizar(); } catch (e) {}
})();
(function () {
  function contarFavoritos() {
    try {
      var favoritos = JSON.parse(localStorage.getItem("lodout_favoritos") || "{}");
      return Object.keys(favoritos).length;
    } catch (e) { return 0; }
  }
  function atualizarBadge() {
    var badge = document.getElementById("contagem-favoritos");
    if (!badge) return;
    var n = contarFavoritos();
    badge.textContent = n;
    badge.hidden = n === 0;
  }
  try { atualizarBadge(); } catch (e) {}
  document.addEventListener("click", function (e) {
    if (e.target.closest(".botao-favorito") || e.target.id === "botao-favoritos") {
      setTimeout(atualizarBadge, 0);
    }
  });
  document.addEventListener("keydown", function (e) {
    if (e.key !== "f" && e.key !== "F") return;
    var ativo = document.activeElement;
    var campoAberto = ativo && (ativo.tagName === "INPUT"
      || ativo.tagName === "TEXTAREA" || ativo.tagName === "SELECT");
    if (campoAberto) return;
    var botao = document.getElementById("botao-favoritos");
    if (botao) botao.click();
  });
})();
(function () {
  var jaPrefetchado = {};
  document.addEventListener("mouseover", function (e) {
    var link = e.target.closest('a.link-secundario[href^="/item/"]');
    if (!link || jaPrefetchado[link.href]) return;
    jaPrefetchado[link.href] = true;
    var tag = document.createElement("link");
    tag.rel = "prefetch";
    tag.href = link.href;
    document.head.appendChild(tag);
  });
})();
(function () {
  var barra = document.createElement("div");
  barra.className = "barra-carregamento";
  barra.setAttribute("aria-hidden", "true");
  document.body.prepend(barra);
  function iniciarCarregamento() {
    var reduzirMovimento = window.matchMedia
      && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    barra.classList.toggle("sem-animacao", !!reduzirMovimento);
    void barra.offsetWidth;
    barra.classList.add("ativa");
  }
  document.addEventListener("click", function (e) {
    if (e.defaultPrevented || e.button !== 0) return;
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    var link = e.target.closest("a[href]");
    if (!link || link.target === "_blank" || link.hasAttribute("download")) return;
    var href = link.getAttribute("href");
    if (!href || href.charAt(0) === "#"
        || href.indexOf("mailto:") === 0 || href.indexOf("tel:") === 0
        || href.indexOf("javascript:") === 0) return;
    iniciarCarregamento();
  });
  document.addEventListener("submit", function (e) {
    if (e.defaultPrevented || e.target.target === "_blank") return;
    iniciarCarregamento();
  });
})();
(function () {
  var overlay = document.getElementById("spotlight-overlay");
  var input = document.getElementById("spotlight-input");
  var resultados = document.getElementById("spotlight-resultados");
  var fecharBtn = document.getElementById("spotlight-fechar");
  var gatilhoBtn = document.getElementById("gatilho-spotlight");
  if (!overlay || !input || !resultados) return;
  var debounceTimer = null;
  var indiceAtivo = -1;
  function abrirSpotlight() {
    overlay.hidden = false;
    overlay.removeAttribute("aria-hidden");
    input.value = "";
    indiceAtivo = -1;
    resultados.innerHTML = '<div class="spotlight-dica-inicial"><p class="spotlight-dica-texto">Digite o nome em português ou inglês para buscar instantaneamente no catálogo e nas notas do Lodout.</p></div>';
    setTimeout(function () { input.focus(); }, 50);
  }
  function fecharSpotlight() {
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
  overlay.addEventListener("click", function (e) {
    if (e.target === overlay) fecharSpotlight();
  });
  document.addEventListener("keydown", function (e) {
    if ((e.ctrlKey || e.metaKey) && e.key && e.key.toLowerCase() === "k") {
      e.preventDefault();
      if (overlay.hidden) abrirSpotlight();
      else fecharSpotlight();
      return;
    }
    if (overlay.hidden) return;
    if (e.key === "Escape") {
      e.preventDefault();
      fecharSpotlight();
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
  function atualizarAtivo(itens) {
    for (var i = 0; i < itens.length; i++) {
      if (i === indiceAtivo) {
        itens[i].classList.add("spotlight-item-ativo");
        itens[i].scrollIntoView({ block: "nearest" });
      } else {
        itens[i].classList.remove("spotlight-item-ativo");
      }
    }
  }
  input.addEventListener("input", function () {
    clearTimeout(debounceTimer);
    var q = input.value.trim();
    if (q.length < 2) {
      resultados.innerHTML = '<div class="spotlight-dica-inicial"><p class="spotlight-dica-texto">Digite pelo menos 2 letras para buscar...</p></div>';
      return;
    }
    debounceTimer = setTimeout(function () {
      fetch("/api/sugestoes?q=" + encodeURIComponent(q))
        .then(function (res) { return res.json(); })
        .then(function (lista) {
          indiceAtivo = -1;
          if (!lista || !lista.length) {
            resultados.innerHTML = '<div class="spotlight-sem-resultado"><p>Nenhum item encontrado para "' + escapeHtml(q) + '".</p></div>';
            return;
          }
          var html = "";
          for (var i = 0; i < lista.length; i++) {
            var item = lista[i];
            var imgHtml = item.icon_url
              ? '<img class="spotlight-item-img" src="' + escapeHtml(item.icon_url) + '" alt="" width="36" height="36" loading="lazy">'
              : '<span class="icone-item-placeholder"></span>';
            var scoreHtml = (typeof item.score === "number")
              ? '<span class="spotlight-item-score nota-' + Math.min(100, Math.max(0, item.score)) + '">Nota ' + item.score + '</span>'
              : '<span class="spotlight-item-sem-score">Catálogo</span>';
            var precoHtml = item.preco_fmt ? '<span class="spotlight-item-preco">' + escapeHtml(item.preco_fmt) + '</span>' : '';
            var rarClasse = item.raridade_classe ? ' ' + escapeHtml(item.raridade_classe) : '';
            html += '<a class="spotlight-item' + rarClasse + '" href="' + escapeHtml(item.url || ("/item/" + encodeURIComponent(item.nome))) + '" role="option">' +
              '<span class="spotlight-item-img-wrap' + rarClasse + '">' + imgHtml + '</span>' +
              '<div class="spotlight-item-info">' +
                '<strong class="spotlight-item-nome" translate="no">' + escapeHtml(item.nome_pt || item.nome) + '</strong>' +
                (item.nome_pt && item.nome_pt !== item.nome ? '<span class="spotlight-item-sub">' + escapeHtml(item.nome) + '</span>' : '') +
              '</div>' +
              '<div class="spotlight-item-lado">' +
                precoHtml +
                scoreHtml +
              '</div>' +
            '</a>';
          }
          resultados.innerHTML = html;
        })
        .catch(function () {});
    }, 150);
  });
  function escapeHtml(s) {
    if (!s) return "";
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }
})();
(function () {
  var box = document.querySelector(".simulador-encomenda-box");
  if (!box) return;
  var input = document.getElementById("sim-input-encomenda");
  var slider = document.getElementById("sim-slider-encomenda");
  var precoAtual = parseFloat(box.getAttribute("data-preco-atual")) || 0;
  var maiorEncomenda = parseFloat(box.getAttribute("data-maior-encomenda")) || 0;
  var elEmpate = document.getElementById("sim-empate-val");
  var elLucro = document.getElementById("sim-lucro-val");
  var elRetorno = document.getElementById("sim-retorno-pct");
  var elFila = document.getElementById("sim-fila-status");
  var elFilaDesc = document.getElementById("sim-fila-desc");
  var btnCopiarSimOferta = document.getElementById("btn-copiar-sim-oferta");

  // Mesmo formato do resto do site (fmt.brl): "R$ 1.234,56" e prejuízo
  // como "−R$ 2,82" (revisão 19/11: saía "R$ -2,82").
  function formatarBrl(val) {
    var p = Math.abs(val).toFixed(2).split(".");
    var txt = "R$ " + p[0].replace(/\B(?=(\d{3})+(?!\d))/g, ".") + "," + p[1];
    return (Math.round(val * 100) < 0 ? "\u2212" : "") + txt;
  }
  // O campo aceita "58,95" ou "58.95" (e "1.234,56").
  function lerValor(txt) {
    var v = String(txt || "").replace(/R\$|\s/g, "");
    if (v.indexOf(",") !== -1) v = v.replace(/\./g, "").replace(",", ".");
    return parseFloat(v);
  }
  function escreverValor(val) {
    return val.toFixed(2).replace(".", ",");
  }
  function calcular(valorPago) {
    if (isNaN(valorPago) || valorPago <= 0) return;
    if (btnCopiarSimOferta) {
      btnCopiarSimOferta.setAttribute("data-copiar-preco", escreverValor(valorPago));
    }
    var pontoEmpate = valorPago * 1.15;
    if (elEmpate) elEmpate.textContent = formatarBrl(pontoEmpate);
    if (precoAtual > 0) {
      var liquidoVenda = precoAtual / 1.15;
      var lucroLiquido = liquidoVenda - valorPago;
      var retornoPct = (lucroLiquido / valorPago) * 100;
      if (elLucro) {
        elLucro.textContent = (Math.round(lucroLiquido * 100) > 0 ? "+" : "") + formatarBrl(lucroLiquido);
        elLucro.className = "simulador-metrica-val " + (lucroLiquido >= 0 ? "texto-positivo" : "texto-perigo");
      }
      if (elRetorno) {
        elRetorno.textContent = (retornoPct > 0.05 ? "+" : retornoPct < -0.05 ? "\u2212" : "") + Math.abs(retornoPct).toFixed(1).replace(".", ",") + "% depois da taxa";
        elRetorno.className = "simulador-metrica-sub " + (retornoPct >= 0 ? "texto-positivo" : "texto-perigo");
      }
    }
    if (elFila && elFilaDesc) {
      if (maiorEncomenda > 0) {
        if (valorPago > maiorEncomenda) {
          elFila.textContent = "Na frente da fila";
          elFila.className = "simulador-fila-status texto-positivo";
          elFilaDesc.textContent = "Acima da maior encomenda (" + formatarBrl(maiorEncomenda) + ")";
        } else if (Math.abs(valorPago - maiorEncomenda) < 0.01) {
          elFila.textContent = "Empatado no topo";
          elFila.className = "simulador-fila-status texto-alerta";
          elFilaDesc.textContent = "Igual à maior encomenda";
        } else {
          elFila.textContent = "Atrás da fila";
          elFila.className = "simulador-fila-status texto-muted";
          elFilaDesc.textContent = "Maior encomenda: " + formatarBrl(maiorEncomenda);
        }
      } else {
        elFila.textContent = "Oferta aberta";
        elFilaDesc.textContent = "Fila desconhecida";
      }
    }
  }

  if (input && slider) {
    input.addEventListener("input", function () {
      var val = lerValor(input.value);
      if (!isNaN(val)) {
        slider.value = val;
        calcular(val);
      }
    });
    slider.addEventListener("input", function () {
      var val = parseFloat(slider.value);
      input.value = escreverValor(val);
      calcular(val);
    });
    var valInicial = lerValor(input.value);
    if (!isNaN(valInicial)) calcular(valInicial);

  }
})();

/* Helper de Toast e Botão Compartilhar */
(function () {
  var toast = document.getElementById("toast-notificacao");
  var toastTimer = null;

  function mostrarToast(msg) {
    if (!toast) return;
    toast.textContent = msg;
    toast.hidden = false;
    toast.classList.add("visivel");
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(function () {
      toast.classList.remove("visivel");
      setTimeout(function () { toast.hidden = true; }, 300);
    }, 3000);
  }
  window.lodoutToast = mostrarToast;

  var btnCompartilhar = document.querySelector(".botao-compartilhar");
  if (btnCompartilhar) {
    btnCompartilhar.addEventListener("click", function () {
      var nome = btnCompartilhar.getAttribute("data-nome") || "";
      var nota = btnCompartilhar.getAttribute("data-nota") || "";
      var preco = btnCompartilhar.getAttribute("data-preco") || "";
      var url = btnCompartilhar.getAttribute("data-url") || window.location.href;

      var texto = "🔥 " + nome + " no Lodout\n" +
                  "📊 Nota: " + nota + " · Preço: " + preco + "\n" +
                  "Análise completa e simulador de lucro no link:\n" + url;

      function ativarSucesso() {
        btnCompartilhar.classList.add("copiado");
        var txtSpan = btnCompartilhar.querySelector(".texto-compartilhar");
        if (txtSpan) txtSpan.textContent = "Copiado!";
        mostrarToast("✓ Resumo e link da skin copiados!");
        setTimeout(function () {
          btnCompartilhar.classList.remove("copiado");
          if (txtSpan) txtSpan.textContent = "Compartilhar";
        }, 2200);
      }

      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(texto).then(ativarSucesso).catch(function () {
          mostrarToast("Link do item: " + url);
        });
      } else {
        mostrarToast("Link do item: " + url);
      }
    });
  }
})();

// Alternador suave para painel de "+ Filtros" do catálogo
(function () {
  var btnFiltros = document.getElementById("gatilho-filtros-toggle");
  var detFiltros = document.querySelector(".filtros-mais");
  if (!btnFiltros || !detFiltros) return;
  btnFiltros.addEventListener("click", function () {
    detFiltros.open = !detFiltros.open;
    btnFiltros.setAttribute("aria-expanded", detFiltros.open ? "true" : "false");
  });
  detFiltros.addEventListener("toggle", function () {
    btnFiltros.setAttribute("aria-expanded", detFiltros.open ? "true" : "false");
  });
})();
