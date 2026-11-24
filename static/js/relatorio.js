// Relatório de custos: filtros de múltipla escolha que atualizam sem recarregar a página,
// e o gráfico do fluxo de pagamentos (Chart.js).
(function () {
  const reais = (v) => v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
  const reduzirMovimento = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  let grafico;

  function desenharGrafico() {
    const fonte = document.getElementById("dados-fluxo");
    const tela = document.getElementById("grafico-fluxo");
    if (grafico) { grafico.destroy(); grafico = null; }
    if (!fonte || !tela || typeof Chart === "undefined") return; // sem Chart.js, a tabela continua disponível
    const dados = JSON.parse(fonte.textContent);
    Chart.defaults.font.family = 'system-ui, "Segoe UI", Roboto, Arial, sans-serif';
    Chart.defaults.color = "#4a5260";
    grafico = new Chart(tela, {
      type: "bar",
      data: {
        labels: dados.map((m) => m.mes),
        datasets: [{ label: "A pagar", data: dados.map((m) => m.valor), backgroundColor: "#0b5cad", borderRadius: 4 }],
      },
      options: {
        animation: reduzirMovimento ? false : undefined,
        plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => reais(c.parsed.y) } } },
        scales: { y: { beginAtZero: true, ticks: { callback: (v) => reais(v) } } },
      },
    });
  }

  const form = document.getElementById("filtros-custos");
  const resultado = document.getElementById("resultado-custos");
  const linkExportar = document.getElementById("link-exportar");
  let controlador;

  function atualizarContadores() {
    form.querySelectorAll("details.multi").forEach((d) => {
      const marcados = d.querySelectorAll("input:checked").length;
      const summary = d.querySelector("summary");
      const indicador = summary.querySelector(".contador, .ajuda");
      indicador.className = marcados ? "contador" : "ajuda";
      indicador.textContent = marcados ? String(marcados) : "Todos";
    });
  }

  async function atualizar() {
    atualizarContadores();
    const params = new URLSearchParams(new FormData(form));
    const consulta = params.toString();
    history.replaceState(null, "", consulta ? "?" + consulta : location.pathname);
    linkExportar.href = linkExportar.href.split("?")[0] + (consulta ? "?" + consulta : "");

    if (controlador) controlador.abort();
    controlador = new AbortController();
    params.set("parcial", "1");
    resultado.setAttribute("aria-busy", "true");
    try {
      const resp = await fetch("?" + params.toString(), { signal: controlador.signal });
      if (!resp.ok) throw new Error("HTTP " + resp.status);
      resultado.innerHTML = await resp.text();
      desenharGrafico();
    } catch (erro) {
      if (erro.name !== "AbortError") {
        resultado.innerHTML = '<p class="mensagem error" role="alert">Não foi possível atualizar o relatório. Tente novamente.</p>';
      }
    } finally {
      resultado.removeAttribute("aria-busy");
    }
  }

  if (form && resultado) {
    form.addEventListener("change", atualizar);
    form.addEventListener("submit", (e) => { e.preventDefault(); atualizar(); });
    form.addEventListener("click", (e) => {
      const botao = e.target.closest("[data-marcar]");
      if (!botao) return;
      const marcar = botao.dataset.marcar === "todos";
      botao.closest("fieldset").querySelectorAll("input[type=checkbox]").forEach((c) => { c.checked = marcar; });
      atualizar();
    });
    // Só um grupo aberto por vez; fecha ao clicar fora ou com Esc.
    const grupos = form.querySelectorAll("details.multi");
    grupos.forEach((d) => d.addEventListener("toggle", () => {
      if (d.open) grupos.forEach((o) => { if (o !== d) o.open = false; });
    }));
    document.addEventListener("click", (e) => { if (!form.contains(e.target)) grupos.forEach((d) => { d.open = false; }); });
    document.addEventListener("keydown", (e) => {
      if (e.key !== "Escape") return;
      const aberto = form.querySelector("details.multi[open]");
      if (aberto) { aberto.open = false; aberto.querySelector("summary").focus(); }
    });
  }

  desenharGrafico();
})();
