// Gráficos do painel de conformidade com Chart.js (RF09).
(function () {
  const fonte = document.getElementById("dados-graficos");
  if (!fonte || typeof Chart === "undefined") return; // sem Chart.js, as tabelas continuam disponíveis
  const dados = JSON.parse(fonte.textContent);

  Chart.defaults.font.family = 'system-ui, "Segoe UI", Roboto, Arial, sans-serif';
  Chart.defaults.color = "#4a5260";
  const reduzirMovimento = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const opcoes = {
    animation: reduzirMovimento ? false : undefined,
    plugins: { legend: { display: false } },
    scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
  };

  const venc = document.getElementById("grafico-vencimentos");
  if (venc) {
    new Chart(venc, {
      type: "bar",
      data: {
        labels: dados.vencimentos.map((v) => v.mes),
        datasets: [{ label: "Licenças que vencem", data: dados.vencimentos.map((v) => v.quantidade), backgroundColor: "#0b5cad" }],
      },
      options: opcoes,
    });
  }

  const pend = document.getElementById("grafico-pendencias");
  if (pend) {
    new Chart(pend, {
      type: "bar",
      data: {
        labels: dados.pendencias.map((p) => p.orgao),
        datasets: [{ label: "Pendências", data: dados.pendencias.map((p) => p.quantidade), backgroundColor: "#dc2626" }],
      },
      options: { ...opcoes, indexAxis: "y", scales: { x: { beginAtZero: true, ticks: { precision: 0 } } } },
    });
  }
})();
