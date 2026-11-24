// Filtros da lista de licenças sem recarregar a página (RF07).
// Sem JavaScript, o formulário continua funcionando pelo botão "Filtrar" (<noscript>).
(function () {
  const form = document.getElementById("filtros");
  const resultado = document.getElementById("resultado");
  const linkExportar = document.getElementById("link-exportar");
  if (!form || !resultado) return;

  let espera;
  let controlador;

  async function atualizar() {
    const params = new URLSearchParams(new FormData(form));
    for (const [chave, valor] of [...params]) if (!valor) params.delete(chave);

    // Mantém a URL e o link de exportação em sincronia com os filtros.
    const consulta = params.toString();
    history.replaceState(null, "", consulta ? "?" + consulta : location.pathname);
    linkExportar.href = linkExportar.href.split("?")[0] + (consulta ? "?" + consulta : "");

    if (controlador) controlador.abort();
    controlador = new AbortController();
    params.set("parcial", "1");
    resultado.setAttribute("aria-busy", "true");
    try {
      const resp = await fetch("?" + params.toString(), {
        headers: { "X-Requested-With": "fetch" },
        signal: controlador.signal,
      });
      if (!resp.ok) throw new Error("HTTP " + resp.status);
      resultado.innerHTML = await resp.text();
    } catch (erro) {
      if (erro.name !== "AbortError") {
        resultado.innerHTML = '<p class="erro" role="alert">Não foi possível atualizar a lista. Tente novamente.</p>';
      }
    } finally {
      resultado.removeAttribute("aria-busy");
    }
  }

  form.addEventListener("change", atualizar);
  form.addEventListener("input", (e) => {
    if (e.target.type !== "search") return;
    clearTimeout(espera);
    espera = setTimeout(atualizar, 300); // espera a pessoa parar de digitar
  });
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    atualizar();
  });
})();
