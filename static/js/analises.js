// Tela Análises: gráficos com Chart.js e filtros que atualizam sem recarregar a página.
(function () {
  const COR = {
    vigente: "#16a34a", vence90: "#fde047", vence30: "#eab308", vencida: "#dc2626",
    primaria: "#0b5cad", texto: "#4a5260", grade: "#e3e7ee",
  };
  // Paleta para séries por unidade (distinguíveis e com contraste sobre branco).
  const PALETA = ["#0b5cad", "#7c3aed", "#0f766e", "#c2410c", "#be185d", "#4d7c0f", "#1d4ed8", "#a16207"];
  const reduzirMovimento = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  let graficos = [];

  function base(extra) {
    return Object.assign({
      responsive: true,
      maintainAspectRatio: false,
      animation: reduzirMovimento ? false : undefined,
      plugins: { legend: { position: "bottom", labels: { usePointStyle: true, boxWidth: 8 } } },
    }, extra);
  }

  function criar(id, config) {
    const tela = document.getElementById(id);
    if (tela) graficos.push(new Chart(tela, config));
  }

  function desenhar() {
    graficos.forEach((g) => g.destroy());
    graficos = [];
    const fonte = document.getElementById("dados-analises");
    if (!fonte || typeof Chart === "undefined") return; // sem Chart.js, as tabelas continuam disponíveis
    const d = JSON.parse(fonte.textContent);
    Chart.defaults.font.family = 'system-ui, "Segoe UI", Roboto, Arial, sans-serif';
    Chart.defaults.color = COR.texto;
    Chart.defaults.borderColor = COR.grade;

    // 1. Conformidade por unidade (100% empilhado)
    const pct = (lista, chave) => lista.map((u) => {
      const total = u.vigente + u.vence_90 + u.vence_30 + u.vencida;
      return total ? +(100 * u[chave] / total).toFixed(1) : 0;
    });
    criar("g-cenario", {
      type: "bar",
      data: {
        labels: d.cenario.map((u) => u.unidade),
        datasets: [
          { label: "Vigente", data: pct(d.cenario, "vigente"), backgroundColor: COR.vigente },
          { label: "31 a 90 dias", data: pct(d.cenario, "vence_90"), backgroundColor: COR.vence90 },
          { label: "Até 30 dias", data: pct(d.cenario, "vence_30"), backgroundColor: COR.vence30 },
          { label: "Vencida", data: pct(d.cenario, "vencida"), backgroundColor: COR.vencida },
        ],
      },
      options: base({
        indexAxis: "y",
        scales: { x: { stacked: true, max: 100, ticks: { callback: (v) => v + "%" } }, y: { stacked: true } },
        plugins: { legend: { position: "bottom", labels: { usePointStyle: true, boxWidth: 8 } },
          tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${c.parsed.x}%` } } },
      }),
    });

    // 4. Conformidade mês a mês (eixo começa perto do menor valor, para as quedas ficarem visíveis)
    const valoresEvo = [d.evolucao.geral, ...d.evolucao.unidades.map((u) => u.valores)].flat().filter((v) => v !== null);
    const minimoEvo = valoresEvo.length ? Math.max(0, Math.floor((Math.min(...valoresEvo) - 5) / 10) * 10) : 0;
    criar("g-evolucao", {
      type: "line",
      data: {
        labels: d.evolucao.meses,
        datasets: [
          { label: "Geral", data: d.evolucao.geral, borderColor: "#1b1f24", backgroundColor: "#1b1f24", borderWidth: 3, tension: .25, spanGaps: true },
          ...d.evolucao.unidades.map((u, i) => ({
            label: u.nome, data: u.valores, borderColor: PALETA[i % PALETA.length], backgroundColor: PALETA[i % PALETA.length],
            borderWidth: 1.5, borderDash: [5, 4], tension: .25, pointRadius: 2, spanGaps: true,
          })),
        ],
      },
      options: base({
        scales: { y: { min: minimoEvo, max: 100, ticks: { callback: (v) => v + "%" } } },
        plugins: { legend: { position: "bottom", labels: { usePointStyle: true, boxWidth: 8 } },
          tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${c.parsed.y}%` } } },
      }),
    });

    // 5. Renovações por mês
    criar("g-renovacoes", {
      type: "bar",
      data: {
        labels: d.renovacoes.map((r) => r.mes),
        datasets: [
          { label: "No prazo", data: d.renovacoes.map((r) => r.no_prazo), backgroundColor: COR.vigente },
          { label: "Em atraso", data: d.renovacoes.map((r) => r.atraso), backgroundColor: COR.vencida },
        ],
      },
      options: base({ scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true, ticks: { precision: 0 } } } }),
    });

    // 8. Antecedência média
    criar("g-antecedencia", {
      type: "bar",
      data: {
        labels: d.antecedencia.map((a) => a.unidade),
        datasets: [{
          label: "Dias de antecedência (média)",
          data: d.antecedencia.map((a) => a.media),
          backgroundColor: d.antecedencia.map((a) => (a.media < 0 ? COR.vencida : a.media < 30 ? COR.vence30 : COR.vigente)),
        }],
      },
      options: base({
        indexAxis: "y",
        plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => `${c.parsed.x} dias` } } },
        scales: { x: { title: { display: true, text: "dias antes do vencimento" } } },
      }),
    });

    // 7. Vencimentos por unidade
    criar("g-vencimentos", {
      type: "bar",
      data: {
        labels: d.vencimentos.meses,
        datasets: d.vencimentos.series.map((s, i) => ({ label: s.nome, data: s.valores, backgroundColor: PALETA[i % PALETA.length] })),
      },
      options: base({ scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true, ticks: { precision: 0 } } } }),
    });
  }

  // Filtros (abrir/fechar, "Marcar todos" e contadores ficam em filtros_multi.js)
  const form = document.getElementById("filtros-analises");
  const resultado = document.getElementById("resultado-analises");
  let controlador;

  async function atualizar() {
    const params = new URLSearchParams(new FormData(form));
    history.replaceState(null, "", "?" + params.toString());
    if (controlador) controlador.abort();
    controlador = new AbortController();
    params.set("parcial", "1");
    resultado.setAttribute("aria-busy", "true");
    try {
      const resp = await fetch("?" + params.toString(), { signal: controlador.signal });
      if (!resp.ok) throw new Error("HTTP " + resp.status);
      resultado.innerHTML = await resp.text();
      desenhar();
    } catch (erro) {
      if (erro.name !== "AbortError") {
        resultado.innerHTML = '<p class="mensagem error" role="alert">Não foi possível atualizar as análises. Tente novamente.</p>';
      }
    } finally {
      resultado.removeAttribute("aria-busy");
    }
  }

  if (form && resultado) {
    form.addEventListener("change", atualizar);
    form.addEventListener("submit", (e) => { e.preventDefault(); atualizar(); });
  }
  desenhar();
})();
