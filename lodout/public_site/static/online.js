// "N pessoas no site agora" no rodapé (pedido do usuário, 17/11). Cada aba
// aberta avisa o servidor a cada minuto, só enquanto está visível, com um
// código aleatório guardado no sessionStorage da aba (some quando ela
// fecha). Sem cookie (credentials: "omit"), sem ligação com a conta. O
// servidor guarda o código por no máximo 10 minutos (online.py).
(function () {
  if (!window.fetch || !window.crypto || !window.crypto.getRandomValues) return;
  var CHAVE = "lodout_aba";
  var id = null;
  try { id = sessionStorage.getItem(CHAVE); } catch (e) { /* sem storage: código só desta página */ }
  if (!id || !/^[0-9a-f]{32}$/.test(id)) {
    var bytes = new Uint8Array(16);
    window.crypto.getRandomValues(bytes);
    id = Array.prototype.map.call(bytes, function (b) { return ("0" + b.toString(16)).slice(-2); }).join("");
    try { sessionStorage.setItem(CHAVE, id); } catch (e) { /* ignora */ }
  }
  function mostrar(n) {
    var el = document.querySelector("[data-online]");
    if (!el) return;
    if (!(n >= 1)) { el.hidden = true; return; }
    var num = el.querySelector("[data-online-n]");
    var rotulo = el.querySelector("[data-online-rotulo]");
    if (num) num.textContent = n.toLocaleString("pt-BR");
    if (rotulo) rotulo.textContent = n === 1 ? "pessoa online" : "pessoas online";
    el.hidden = false;
  }
  function avisar() {
    if (document.visibilityState === "hidden") return;
    fetch("/api/online", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: id }),
      credentials: "omit",
      keepalive: true
    }).then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) { if (d && typeof d.agora === "number") mostrar(d.agora); })
      .catch(function () { /* sem rede: o número fica como estava */ });
  }
  avisar();
  setInterval(avisar, 60000);
  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "visible") avisar();
  });
})();
