/*
 * Minuteur de suivi de séance (issue #35).
 *
 * Le déroulé chronométré (ordre exact des efforts et repos) est calculé côté
 * serveur par workouts.timer.build_timeline et transmis en JSON — ce script
 * ne fait qu'égrainer cette liste, sans recalculer de minutage.
 *
 * Les sons sont synthétisés via l'API Web Audio plutôt qu'embarqués en
 * fichiers : pas de dépendance externe, pas de question de licence, et un
 * fonctionnement identique hors connexion.
 */
(() => {
    "use strict";

    // Temps laissé pour se mettre en place avant le premier pas — pas encore
    // décompté dans l'avancement de la séance, voir overallPercent().
    const PREP_SECONDS = 5;

    const dialog = document.getElementById("minuteur-modal");
    const opener = document.getElementById("lancer-seance");
    if (!dialog || !opener) return;

    const dataNode = document.getElementById("minuteur-donnees");
    const steps = dataNode ? JSON.parse(dataNode.textContent) : [];
    if (!steps.length) return;

    const phaseEl = document.getElementById("minuteur-phase");
    const exerciseEl = document.getElementById("minuteur-exercice");
    const lapEl = document.getElementById("minuteur-tour");
    const clockEl = document.getElementById("minuteur-horloge");
    const repsEl = document.getElementById("minuteur-reps");
    const progressWrap = document.getElementById("minuteur-progress");
    const percentEl = document.getElementById("minuteur-pourcentage");
    const trackEl = document.getElementById("minuteur-barre");
    const fillEl = document.getElementById("minuteur-remplissage");
    const announceEl = document.getElementById("minuteur-annonce");
    const pauseBtn = document.getElementById("minuteur-pause");
    const nextBtn = document.getElementById("minuteur-suivant");
    const stopBtn = document.getElementById("minuteur-stop");

    let index = -1;
    let remaining = 0;
    let total = 0;
    let intervalId = null;
    let audioCtx = null;
    let currentStepEl = null;

    function tone(frequency, start, duration, type, peakGain) {
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.type = type || "sine";
        osc.frequency.value = frequency;
        gain.gain.setValueAtTime(0.0001, start);
        gain.gain.exponentialRampToValueAtTime(peakGain || 0.2, start + 0.015);
        gain.gain.exponentialRampToValueAtTime(0.0001, start + duration);
        osc.connect(gain).connect(audioCtx.destination);
        osc.start(start);
        osc.stop(start + duration + 0.05);
    }

    // Sinusoïdales et triangulaires uniquement : une onde carrée sonne comme
    // un buzzer d'ancien jeu vidéo, pas comme un repère de salle de sport.
    function playCue(name) {
        if (!audioCtx) return;
        const now = audioCtx.currentTime;
        if (name === "start") {
            tone(523, now, 0.14, "sine");
            tone(784, now + 0.16, 0.2, "sine");
        } else if (name === "end") {
            tone(784, now, 0.16, "sine");
            tone(659, now + 0.18, 0.16, "sine");
            tone(523, now + 0.36, 0.28, "sine");
        } else if (name === "work") {
            tone(880, now, 0.18, "triangle");
        } else if (name === "rest") {
            tone(440, now, 0.22, "sine");
        } else if (name === "tick") {
            // Un bip discret par seconde sur les quatre dernières secondes
            // d'un décompte — la préparation comme un effort chronométré.
            tone(660, now, 0.08, "sine", 0.14);
        }
    }

    function formatClock(seconds) {
        const m = Math.floor(seconds / 60);
        const s = seconds % 60;
        return `${m}:${String(s).padStart(2, "0")}`;
    }

    function highlight(itemId) {
        if (currentStepEl) currentStepEl.classList.remove("ugg-timer__step--current");
        currentStepEl = dialog.querySelector(`.ugg-timer__step[data-item-id="${itemId}"]`);
        if (currentStepEl) {
            currentStepEl.classList.add("ugg-timer__step--current");
            currentStepEl.scrollIntoView({ block: "nearest" });
        }
    }

    function exerciseName(itemId) {
        const el = dialog.querySelector(
            `.ugg-timer__step[data-item-id="${itemId}"] .ugg-timer__step-name`
        );
        return el ? el.textContent : "";
    }

    function stopInterval() {
        if (intervalId) {
            window.clearInterval(intervalId);
            intervalId = null;
        }
    }

    function updateClock() {
        clockEl.textContent = formatClock(Math.max(0, remaining));
    }

    // Avancement de la séance entière (pas de la seule phase en cours) : la
    // préparation ne compte pas encore (index < 0), un pas en répétitions
    // (sans chronomètre) compte pour lui-même dès qu'il est atteint, et un
    // pas chronométré avance en continu au fil de son propre décompte plutôt
    // que par à-coups à chaque changement de pas.
    function overallPercent() {
        if (index < 0) return 0;
        if (index >= steps.length) return 100;
        const step = steps[index];
        const fraction = step.seconds ? (total - remaining) / total : 0;
        return Math.min(100, Math.round(((index + fraction) / steps.length) * 100));
    }

    function updateProgress() {
        const percent = overallPercent();
        fillEl.style.width = `${percent}%`;
        trackEl.setAttribute("aria-valuenow", String(percent));
        const stepNumber = Math.min(Math.max(index + 1, 0), steps.length);
        percentEl.textContent = `${percent} % · ${stepNumber} / ${steps.length}`;
    }

    function tick() {
        remaining -= 1;
        updateClock();
        updateProgress();
        if (remaining > 0 && remaining <= 4) {
            playCue("tick");
        }
        if (remaining <= 0) {
            stopInterval();
            goTo(index + 1);
        }
    }

    function goTo(nextIndex) {
        stopInterval();
        index = nextIndex;
        if (index >= steps.length) {
            finish();
            return;
        }

        const step = steps[index];
        highlight(step.itemId);
        dialog.dataset.phase = step.phase;
        phaseEl.textContent = step.phase === "work" ? "Effort" : "Repos";
        exerciseEl.textContent = exerciseName(step.itemId);
        lapEl.textContent = step.totalLaps > 1 ? `Tour ${step.lap} / ${step.totalLaps}` : "";
        progressWrap.hidden = false;

        if (step.seconds === null) {
            // Effort en répétitions (pyramide) : pas de décompte, confirmation manuelle.
            clockEl.hidden = true;
            repsEl.hidden = false;
            repsEl.textContent = `${step.reps} répétitions`;
            pauseBtn.disabled = true;
        } else {
            clockEl.hidden = false;
            repsEl.hidden = true;
            pauseBtn.disabled = false;
            pauseBtn.textContent = "Pause";
            remaining = step.seconds;
            total = step.seconds;
            updateClock();
            intervalId = window.setInterval(tick, 1000);
        }

        updateProgress();
        playCue(step.phase);
        announceEl.textContent = `${phaseEl.textContent} : ${exerciseEl.textContent}`;
    }

    function finish() {
        stopInterval();
        dialog.dataset.phase = "";
        phaseEl.textContent = "Séance terminée";
        exerciseEl.textContent = "";
        lapEl.textContent = "";
        clockEl.hidden = true;
        repsEl.hidden = true;
        updateProgress();
        progressWrap.hidden = true;
        pauseBtn.disabled = true;
        nextBtn.disabled = true;
        stopBtn.textContent = "Fermer";
        if (currentStepEl) currentStepEl.classList.remove("ugg-timer__step--current");
        currentStepEl = null;
        playCue("end");
        announceEl.textContent = "Séance terminée.";
    }

    function reset() {
        stopInterval();
        index = -1;
        pauseBtn.disabled = false;
        pauseBtn.textContent = "Pause";
        nextBtn.disabled = false;
        stopBtn.textContent = "Arrêter";
    }

    // Cinq secondes pour se mettre en place avant le premier pas, plutôt que
    // de décompter dès la fermeture de la porte du casier.
    function startPrep() {
        stopInterval();
        index = -1;
        const first = steps[0];
        highlight(first.itemId);
        dialog.dataset.phase = "prep";
        phaseEl.textContent = "Préparation";
        exerciseEl.textContent = exerciseName(first.itemId);
        lapEl.textContent = "";

        clockEl.hidden = false;
        repsEl.hidden = true;
        progressWrap.hidden = false;
        pauseBtn.disabled = false;
        pauseBtn.textContent = "Pause";

        remaining = PREP_SECONDS;
        total = PREP_SECONDS;
        updateClock();
        updateProgress();
        announceEl.textContent = `Préparation : ${exerciseEl.textContent}`;
        intervalId = window.setInterval(tick, 1000);
    }

    opener.addEventListener("click", () => {
        if (!audioCtx) {
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            if (AudioContext) audioCtx = new AudioContext();
        } else if (audioCtx.state === "suspended") {
            audioCtx.resume();
        }

        reset();
        dialog.showModal();
        playCue("start");
        startPrep();
    });

    pauseBtn.addEventListener("click", () => {
        if (intervalId) {
            stopInterval();
            pauseBtn.textContent = "Reprendre";
            announceEl.textContent = "Séance en pause.";
        } else if (remaining > 0) {
            intervalId = window.setInterval(tick, 1000);
            pauseBtn.textContent = "Pause";
            announceEl.textContent = "Séance reprise.";
        }
    });

    nextBtn.addEventListener("click", () => goTo(index + 1));
    stopBtn.addEventListener("click", () => dialog.close());

    // Pas de fermeture au clic sur le fond : une séance en cours ne doit pas
    // s'interrompre d'un geste accidentel. Seul « Arrêter » — ou Échap, natif
    // au <dialog> — y met fin ; les deux passent par le même événement
    // « close », qui arrête toujours le décompte.
    dialog.addEventListener("close", stopInterval);
})();
