// Encomenda sugerida (Ranking e página do item): clicar no valor copia o
// número ("53,41") para colar no preço da encomenda na Steam (pedido do
// usuário, 17/11). Sem JS, o valor continua visível para copiar à mão.
(function () {
  "use strict";
  var aviso = document.querySelector("[data-copiado]");
  document.addEventListener("click", function (e) {
    var botao = e.target.closest && e.target.closest("[data-copiar-preco]");
    if (!botao) return;
    var numero = botao.getAttribute("data-copiar-preco");
    if (!numero) return;
    var avisar = function (ok) {
      botao.classList.toggle("copiado", ok);
      botao.setAttribute("data-dica", ok ? "copiado" : "não deu: copie à mão");
      if (aviso) aviso.textContent = ok
        ? "Copiado: " + numero + ". Na Steam, cole no preço da encomenda."
        : "Não foi possível copiar. O valor é " + numero + ".";
      clearTimeout(botao._copiadoT);
      botao._copiadoT = setTimeout(function () {
        botao.classList.remove("copiado");
        botao.removeAttribute("data-dica");
      }, ok ? 2000 : 3500);
    };
    // Sem a API moderna (navegador antigo, página sem HTTPS) ou com ela
    // bloqueada: tenta o jeito antigo antes de desistir (polimento 17/11:
    // antes, nada acontecia e a pessoa não sabia por quê).
    var antigo = function () {
      var campo = document.createElement("textarea");
      campo.value = numero;
      campo.setAttribute("readonly", "");
      campo.className = "visualmente-oculto";
      document.body.appendChild(campo);
      campo.select();
      var ok = false;
      try { ok = document.execCommand("copy"); } catch (err) { ok = false; }
      document.body.removeChild(campo);
      botao.focus();
      avisar(ok);
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(numero).then(function () { avisar(true); }, antigo);
    } else {
      antigo();
    }
  });
})();
