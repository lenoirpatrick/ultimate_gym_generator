/*
 * Graphiques de la page d'analyse (issue #72), sur Chart.js (vendoré,
 * core/static/core/js/chart.min.js). Les données voyagent en JSON via
 * `json_script` (health/partials/dashboard_results.html) plutôt que par un
 * appel réseau séparé — même technique que le minuteur de séance.
 *
 * Le bloc de résultats est remplacé par HTMX à chaque changement de filtre
 * (#73) : `htmx:afterSettle` redéclenche le rendu, en détruisant les
 * instances Chart.js précédentes avant d'en recréer — sans cela, chaque
 * filtrage empilerait un graphique fantôme sur le canvas réutilisé.
 */
(function () {
    "use strict";

    let charts = {};

    function token(name) {
        return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    }

    function destroyCharts() {
        Object.values(charts).forEach(function (chart) {
            if (chart) chart.destroy();
        });
        charts = {};
    }

    function baseScales() {
        return {
            x: { grid: { color: token("--ugg-border") }, ticks: { color: token("--ugg-text-muted") } },
            y: { grid: { color: token("--ugg-border") }, ticks: { color: token("--ugg-text-muted") } },
        };
    }

    function renderLine(canvasId, series, label) {
        const canvas = document.getElementById(canvasId);
        if (!canvas || !series.labels.length) return null;
        return new Chart(canvas, {
            type: "line",
            data: {
                labels: series.labels,
                datasets: [
                    {
                        label: label,
                        data: series.values,
                        borderColor: token("--ugg-accent"),
                        backgroundColor: token("--ugg-accent"),
                        tension: 0.3,
                        pointRadius: 2,
                    },
                ],
            },
            options: { plugins: { legend: { display: false } }, scales: baseScales() },
        });
    }

    function renderBars(canvasId, series, label) {
        const canvas = document.getElementById(canvasId);
        if (!canvas || !series.labels.length) return null;
        return new Chart(canvas, {
            type: "bar",
            data: {
                labels: series.labels,
                datasets: [{ label: label, data: series.values, backgroundColor: token("--ugg-accent") }],
            },
            options: {
                plugins: { legend: { display: false } },
                scales: { x: { grid: { display: false }, ticks: baseScales().x.ticks }, y: baseScales().y },
            },
        });
    }

    function renderCharts() {
        const node = document.getElementById("health-chart-data");
        if (!node || typeof Chart === "undefined") return;

        destroyCharts();
        const data = JSON.parse(node.textContent);

        charts.weight = renderLine("chart-weight", data.weight, "Poids (kg)");
        charts.volume = renderBars("chart-volume", data.volume, "Heures");
        charts.pace = renderLine("chart-pace", data.pace, "Allure (min/km)");
        charts.steps = renderBars("chart-steps", data.steps, "Pas");
    }

    document.addEventListener("DOMContentLoaded", renderCharts);
    document.body.addEventListener("htmx:afterSettle", renderCharts);
})();
