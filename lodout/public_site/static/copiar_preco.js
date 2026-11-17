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
})();
