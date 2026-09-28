// Case « Tout sélectionner » par région du corps (issue #106, workouts/partials/muscle_regions.html).
// Aucune case native ne peut refléter l'état de plusieurs autres en CSS seul :
// même exception assumée que le minuteur de séance (CLAUDE.md).
(() => {
    function boxesFor(toggle) {
        return toggle
            .closest("fieldset")
            .querySelectorAll('input[type="checkbox"]:not([data-muscle-region-toggle])');
    }

    function syncToggle(toggle) {
        const boxes = [...boxesFor(toggle)];
        const checked = boxes.filter((box) => box.checked).length;
        toggle.checked = checked > 0 && checked === boxes.length;
        toggle.indeterminate = checked > 0 && checked < boxes.length;
    }

    document.addEventListener("change", (event) => {
        const toggle = event.target.closest("[data-muscle-region-toggle]");
        if (toggle) {
            boxesFor(toggle).forEach((box) => {
                box.checked = toggle.checked;
            });
            toggle.indeterminate = false;
            return;
        }

        const fieldset = event.target.closest("fieldset");
        const relatedToggle = fieldset?.querySelector("[data-muscle-region-toggle]");
        if (relatedToggle && event.target !== relatedToggle) {
            syncToggle(relatedToggle);
        }
    });

    document.querySelectorAll("[data-muscle-region-toggle]").forEach(syncToggle);
})();
