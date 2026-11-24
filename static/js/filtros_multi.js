// Comportamento dos filtros de múltipla escolha (form.filtros-multi), compartilhado pelas telas.
// - só uma lista aberta por vez; fecha ao clicar fora ou com Esc;
// - "Marcar todos" / "Limpar" marcam as caixas e avisam a tela com um evento "change" no formulário;
// - o contador de cada botão ("Unidades 2" ou "Todos") acompanha as marcações.
(function () {
  document.querySelectorAll("form.filtros-multi").forEach((form) => {
    const grupos = form.querySelectorAll("details.multi");

    function atualizarContadores() {
      grupos.forEach((d) => {
        const marcados = d.querySelectorAll("input:checked").length;
        const indicador = d.querySelector("summary .contador, summary .ajuda");
        indicador.className = marcados ? "contador" : "ajuda";
        indicador.textContent = marcados ? String(marcados) : "Todos";
      });
    }

    form.addEventListener("change", atualizarContadores);
    form.addEventListener("click", (e) => {
      const botao = e.target.closest("[data-marcar]");
      if (!botao) return;
      const marcar = botao.dataset.marcar === "todos";
      botao.closest("fieldset").querySelectorAll("input[type=checkbox]").forEach((c) => { c.checked = marcar; });
      form.dispatchEvent(new Event("change", { bubbles: true }));
    });
    grupos.forEach((d) => d.addEventListener("toggle", () => {
      if (d.open) grupos.forEach((o) => { if (o !== d) o.open = false; });
    }));
    document.addEventListener("click", (e) => {
      if (!form.contains(e.target)) grupos.forEach((d) => { d.open = false; });
    });
    document.addEventListener("keydown", (e) => {
      if (e.key !== "Escape") return;
      const aberto = form.querySelector("details.multi[open]");
      if (aberto) { aberto.open = false; aberto.querySelector("summary").focus(); }
    });
  });
})();
