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
 *
 * Agrandissement avec zoom/déplacement (issue #80, chartjs-plugin-zoom
 * vendoré, core/static/core/js/chartjs-plugin-zoom.min.js) : l'aperçu reste
 * une image statique, une instance Chart.js *distincte* est créée dans la
 * lightbox (`.ugg-lightbox`, `:target`, CSS pur) — un canvas caché par
 * `display:none` a une taille nulle, Chart.js ne peut donc pas y dessiner
 * avant que la bascule CSS ne le rende visible. La création est différée à
 * l'ouverture plutôt qu'anticipée, sur l'évènement `hashchange` que produit
 * le clic sur l'ancre même sans script pour la bascule elle-même.
 */
(function () {
    "use strict";

    let charts = {};
    let largeCharts = {};
    let lastData = null;

    const CHART_DEFS = {
        weight: { type: "line", label: "Poids (kg)" },
        volume: { type: "bar", label: "Heures" },
        pace: { type: "line", label: "Allure (min/km)" },
        steps: { type: "bar", label: "Pas" },
    };

    if (typeof Chart !== "undefined" && typeof ChartZoom !== "undefined") {
        Chart.register(ChartZoom);
    }

    function token(name) {
        return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    }

    function destroyAll(map) {
        Object.values(map).forEach(function (chart) {
            if (chart) chart.destroy();
        });
    }

    function destroyCharts() {
        destroyAll(charts);
        destroyAll(largeCharts);
        charts = {};
        largeCharts = {};
    }

    function baseScales() {
        return {
            x: { grid: { color: token("--ugg-border") }, ticks: { color: token("--ugg-text-muted") } },
            y: { grid: { color: token("--ugg-border") }, ticks: { color: token("--ugg-text-muted") } },
        };
    }

    function zoomOptions() {
        return {
            pan: { enabled: true, mode: "x" },
            zoom: {
                wheel: { enabled: true },
                pinch: { enabled: true },
                drag: { enabled: false },
                mode: "x",
            },
        };
    }

    function buildConfig(def, series, withZoom) {
        const isBar = def.type === "bar";
        const dataset = isBar
            ? { label: def.label, data: series.values, backgroundColor: token("--ugg-accent") }
            : {
                  label: def.label,
                  data: series.values,
                  borderColor: token("--ugg-accent"),
                  backgroundColor: token("--ugg-accent"),
                  tension: 0.3,
                  pointRadius: withZoom ? 3 : 2,
              };
        const scales = isBar
            ? { x: { grid: { display: false }, ticks: baseScales().x.ticks }, y: baseScales().y }
            : baseScales();

        return {
            type: def.type,
            data: { labels: series.labels, datasets: [dataset] },
            options: {
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    zoom: withZoom ? zoomOptions() : undefined,
                },
                scales: scales,
            },
        };
    }

    function renderPreview(key) {
        const def = CHART_DEFS[key];
        const canvas = document.getElementById("chart-" + key);
        const series = lastData[key];
        if (!canvas || !series.labels.length) return null;
        return new Chart(canvas, buildConfig(def, series, false));
    }

    function renderCharts() {
        const node = document.getElementById("health-chart-data");
        if (!node || typeof Chart === "undefined") return;

        destroyCharts();
        lastData = JSON.parse(node.textContent);

        Object.keys(CHART_DEFS).forEach(function (key) {
            charts[key] = renderPreview(key);
        });

        // La lightbox peut déjà être ouverte au premier rendu — hash déjà
        // présent dans l'URL au chargement (lien partagé, rechargement
        // pendant qu'un graphique est agrandi) — pas seulement au clic, seul
        // moment où `hashchange` se déclenche.
        handleHashChange();
    }

    function openLargeChart(key) {
        const def = CHART_DEFS[key];
        const canvas = document.getElementById("chart-" + key + "-large");
        if (!def || !canvas || !lastData || largeCharts[key]) return;
        const series = lastData[key];
        if (!series || !series.labels.length) return;
        largeCharts[key] = new Chart(canvas, buildConfig(def, series, true));
    }

    function handleHashChange() {
        const match = /^#graphique-(weight|volume|pace|steps)$/.exec(location.hash);
        if (!match) return;
        // Différé d'une frame : la bascule CSS `:target` doit avoir rendu le
        // panneau visible avant que Chart.js ne mesure son canvas.
        requestAnimationFrame(function () {
            openLargeChart(match[1]);
        });
    }

    document.addEventListener("click", function (event) {
        const button = event.target.closest("[data-chart-reset-zoom]");
        if (!button) return;
        const chart = largeCharts[button.dataset.chartResetZoom];
        if (chart && typeof chart.resetZoom === "function") chart.resetZoom();
    });

    document.addEventListener("DOMContentLoaded", renderCharts);
    document.body.addEventListener("htmx:afterSettle", renderCharts);
    window.addEventListener("hashchange", handleHashChange);
})();
