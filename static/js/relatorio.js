// Gráfico do fluxo de pagamentos no relatório de custos.
(function () {
  const fonte = document.getElementById("dados-fluxo");
  const tela = document.getElementById("grafico-fluxo");
  if (!fonte || !tela || typeof Chart === "undefined") return; // sem Chart.js, a tabela continua disponível
  const dados = JSON.parse(fonte.textContent);
  const reais = (v) => v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
  const reduzirMovimento = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  Chart.defaults.font.family = 'system-ui, "Segoe UI", Roboto, Arial, sans-serif';
  Chart.defaults.color = "#4a5260";
  new Chart(tela, {
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
})();
