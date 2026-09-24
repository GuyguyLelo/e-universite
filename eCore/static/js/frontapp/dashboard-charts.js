(function () {
  const dataEl = document.getElementById("dashboard-charts-data");
  if (!dataEl || typeof ApexCharts === "undefined") {
    return;
  }

  let charts = {};
  try {
    charts = JSON.parse(dataEl.textContent);
  } catch (e) {
    return;
  }

  const fontFamily = '"Plus Jakarta Sans", "Outfit", system-ui, sans-serif';
  const colors = ["#003E82", "#007FFF", "#0057B8", "#CE1126", "#C89600", "#4DA3FF"];
  const grid = { borderColor: "#e2e8f0", strokeDashArray: 4 };
  const chartHeight = 200;
  const baseChart = {
    fontFamily: fontFamily,
    toolbar: { show: false },
    animations: { enabled: true, speed: 500 },
  };

  function hasData(series) {
    if (!series) return false;
    if (Array.isArray(series[0])) return series.some((row) => row.some((n) => n > 0));
    if (typeof series[0] === "object" && series[0] !== null && "data" in series[0]) {
      return series.some((s) => (s.data || []).some((n) => n > 0));
    }
    return series.some((n) => n > 0);
  }

  function showEmpty(el) {
    const node = document.querySelector(el);
    if (node) {
      node.innerHTML = '<p class="portal-chart__empty">Aucune donnée disponible pour ce graphique.</p>';
    }
  }

  const faculte = charts.filieres_faculte || {};
  if (hasData(faculte.series)) {
    new ApexCharts(document.querySelector("#chart-filieres-faculte"), {
      chart: { ...baseChart, type: "bar", height: chartHeight },
      series: [{ name: "Filières", data: faculte.series }],
      xaxis: {
        categories: faculte.labels,
        labels: { style: { fontSize: "11px", colors: "#64748b" } },
      },
      yaxis: {
        labels: { style: { fontSize: "11px", colors: "#64748b" } },
        tickAmount: 4,
      },
      colors: ["#007FFF"],
      plotOptions: { bar: { borderRadius: 6, columnWidth: "52%" } },
      dataLabels: { enabled: false },
      grid: grid,
      tooltip: { theme: "light" },
    }).render();
  } else {
    showEmpty("#chart-filieres-faculte");
  }

  const statut = charts.inscriptions_statut || {};
  if (hasData(statut.series)) {
    new ApexCharts(document.querySelector("#chart-inscriptions-statut"), {
      chart: { ...baseChart, type: "donut", height: chartHeight },
      series: statut.series,
      labels: statut.labels,
      colors: colors,
      legend: { position: "bottom", fontSize: "10px", offsetY: 0 },
      dataLabels: { enabled: true, style: { fontSize: "10px" } },
      plotOptions: {
        pie: {
          donut: {
            size: "68%",
            labels: {
              show: true,
              total: {
                show: true,
                label: "Total",
                fontSize: "12px",
                fontWeight: 600,
              },
            },
          },
        },
      },
      stroke: { width: 2, colors: ["#fff"] },
    }).render();
  } else {
    showEmpty("#chart-inscriptions-statut");
  }

  const sessions = charts.sessions_semestre || {};
  const sessionsSeries = sessions.series || [];
  if (hasData(sessionsSeries)) {
    new ApexCharts(document.querySelector("#chart-sessions-semestre"), {
      chart: { ...baseChart, type: "bar", height: chartHeight, stacked: false },
      series: sessionsSeries,
      xaxis: {
        categories: sessions.labels,
        labels: { style: { fontSize: "11px", colors: "#64748b" } },
      },
      yaxis: {
        labels: { style: { fontSize: "11px", colors: "#64748b" } },
        tickAmount: 4,
      },
      colors: ["#007FFF", "#003E82"],
      plotOptions: { bar: { borderRadius: 5, columnWidth: "48%" } },
      legend: { position: "top", horizontalAlign: "right", fontSize: "10px", offsetY: -4 },
      dataLabels: { enabled: false },
      grid: grid,
    }).render();
  } else {
    showEmpty("#chart-sessions-semestre");
  }

  const mois = charts.inscriptions_mois || {};
  if (hasData(mois.series)) {
    new ApexCharts(document.querySelector("#chart-inscriptions-mois"), {
      chart: { ...baseChart, type: "area", height: chartHeight },
      series: [{ name: "Inscriptions", data: mois.series }],
      xaxis: {
        categories: mois.labels,
        labels: { style: { fontSize: "11px", colors: "#64748b" } },
      },
      yaxis: {
        labels: { style: { fontSize: "11px", colors: "#64748b" } },
        tickAmount: 4,
      },
      colors: ["#003E82"],
      fill: {
        type: "gradient",
        gradient: {
          shadeIntensity: 0.4,
          opacityFrom: 0.45,
          opacityTo: 0.05,
        },
      },
      stroke: { curve: "smooth", width: 2.5 },
      dataLabels: { enabled: false },
      grid: grid,
      markers: { size: 3, strokeWidth: 0 },
    }).render();
  } else {
    showEmpty("#chart-inscriptions-mois");
  }

  const delib = charts.deliberations_statut || {};
  if (hasData(delib.series)) {
    new ApexCharts(document.querySelector("#chart-deliberations-statut"), {
      chart: { ...baseChart, type: "donut", height: chartHeight },
      series: delib.series,
      labels: delib.labels,
      colors: ["#003E82", "#007FFF", "#CE1126", "#C89600"],
      legend: { position: "bottom", fontSize: "10px", offsetY: 0 },
      plotOptions: {
        pie: {
          donut: { size: "65%" },
        },
      },
      stroke: { width: 2, colors: ["#fff"] },
    }).render();
  } else {
    showEmpty("#chart-deliberations-statut");
  }
})();
