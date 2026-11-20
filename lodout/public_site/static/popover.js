// Balões e menus feitos com <details> ("Cores da borda", menu "⋯" dos
// itens): fecham ao clicar fora ou com Esc. Saiu do app.js (revisão
// 20/11) porque o Ranking não carrega o app.js e o balão de lá não
// fechava com Esc. Ao fechar com Esc, o foco volta para o botão.
(function () {
  "use strict";
  var SELETOR = ".menu-acoes-item[open], .popover-legenda[open]";
  document.addEventListener("click", function (e) {
    document.querySelectorAll(SELETOR).forEach(function (det) {
      if (!det.contains(e.target)) det.open = false;
    });
  });
  document.addEventListener("keydown", function (e) {
    if (e.key !== "Escape") return;
    document.querySelectorAll(SELETOR).forEach(function (det) {
      var tinhaFoco = det.contains(document.activeElement);
      det.open = false;
      var resumo = det.querySelector("summary");
      if (tinhaFoco && resumo) resumo.focus();
    });
  });
})();
