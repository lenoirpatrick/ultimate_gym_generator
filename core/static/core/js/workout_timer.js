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

    // Délai entre deux photos d'un même exercice, dans le panneau du tiers
    // bas (issue #35 suite) — voir startPhotoRotation().
    const PHOTO_INTERVAL_MS = 5000;

    // Repos entre exercices et récupération entre tours/blocs (issue #44
    // suite) se distinguent par le libellé — jamais la seule couleur — mais
    // partagent la même tonalité : les deux sont une pause, pas un effort.
    const PHASE_LABELS = { work: "Effort", rest: "Repos", recovery: "Récupération" };

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
    const currentPanel = document.getElementById("minuteur-exercice-actuel");
    const currentPhoto = document.getElementById("minuteur-exercice-actuel-photo");
    const currentName = document.getElementById("minuteur-exercice-actuel-nom");
    const currentEquipment = document.getElementById("minuteur-exercice-actuel-materiel");
    const currentMuscles = document.getElementById("minuteur-exercice-actuel-muscles");

    let index = -1;
    let remaining = 0;
    let total = 0;
    let intervalId = null;
    // Fonction rebranchée par Pause/Reprendre : celle d'un pas normal (tick)
    // ou celle d'une préparation (prepTick), selon ce qui tournait avant la
    // pause (issue #61).
    let activeIntervalCallback = null;
    // Décompte propre à une préparation (5 s), distinct de `remaining`/`total`
    // qui restent figés sur le dernier pas réellement joué tant qu'elle dure —
    // c'est ce qui garde la préparation hors de l'avancement de la séance.
    let prepRemaining = 0;
    // Index du pas visé par la préparation en cours, ou `null` hors
    // préparation — permet à « Passer » d'y couper court (issue #61).
    let pendingPrepIndex = null;
    let audioCtx = null;
    let currentStepEl = null;
    let photoRotationId = null;
    let photoUrls = [];
    let photoIndex = 0;
    let wakeLock = null;

    // Le web ne donne accès à aucun réglage de luminosité matérielle : le plus
    // proche disponible est d'empêcher l'écran de s'éteindre ou de s'assombrir
    // pendant la séance (issue #53). Dégradation silencieuse si l'API est
    // absente (Safari desktop, anciens navigateurs) — comportement inchangé.
    async function requestWakeLock() {
        if (!("wakeLock" in navigator)) return;
        try {
            wakeLock = await navigator.wakeLock.request("screen");
        } catch {
            wakeLock = null;
        }
    }

    function releaseWakeLock() {
        if (wakeLock) {
            wakeLock.release().catch(() => {});
            wakeLock = null;
        }
    }

    // Le verrou se relâche automatiquement quand l'onglet perd la visibilité
    // (contrainte de la spec) — on le redemande au retour, tant que le
    // minuteur est toujours ouvert.
    document.addEventListener("visibilitychange", () => {
        if (document.visibilityState === "visible" && dialog.open) {
            requestWakeLock();
        }
    });

    function tone(frequency, start, duration, type, peakGain) {
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.type = type || "sine";
        osc.frequency.value = frequency;
        gain.gain.setValueAtTime(0.0001, start);
        gain.gain.exponentialRampToValueAtTime(peakGain || 0.38, start + 0.015);
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
            // Arpège montant (do-mi-sol-do) plutôt qu'une séquence descendante :
            // une fin de séance se fête, elle ne se referme pas simplement.
            tone(523, now, 0.14, "sine");
            tone(659, now + 0.15, 0.14, "sine");
            tone(784, now + 0.3, 0.14, "sine");
            tone(1047, now + 0.45, 0.35, "sine");
        } else if (name === "work") {
            tone(880, now, 0.18, "triangle");
        } else if (name === "rest" || name === "recovery") {
            tone(440, now, 0.22, "sine");
        } else if (name === "tick") {
            // Un bip discret par seconde sur les quatre dernières secondes
            // d'un décompte — la préparation comme un effort chronométré.
            tone(660, now, 0.08, "sine", 0.3);
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
            updateCurrentExercisePanel(currentStepEl);
        }
    }

    function stopPhotoRotation() {
        if (photoRotationId) {
            window.clearInterval(photoRotationId);
            photoRotationId = null;
        }
    }

    function showCurrentPhoto() {
        if (photoUrls.length) {
            currentPhoto.src = photoUrls[photoIndex];
            currentPhoto.alt = "";
            currentPhoto.hidden = false;
        } else {
            currentPhoto.hidden = true;
            currentPhoto.removeAttribute("src");
        }
    }

    // Une photo de plus toutes les 5 s quand l'exercice en compte plusieurs
    // (issue #35 suite) — la vignette de la timeline, elle, reste fixe.
    function startPhotoRotation() {
        stopPhotoRotation();
        if (photoUrls.length > 1) {
            photoRotationId = window.setInterval(() => {
                photoIndex = (photoIndex + 1) % photoUrls.length;
                showCurrentPhoto();
            }, PHOTO_INTERVAL_MS);
        }
    }

    // Panneau du tiers bas de l'écran : relit la ligne de la timeline plutôt
    // que de dupliquer nom/matériel/muscles dans le JSON du minuteur.
    function updateCurrentExercisePanel(stepEl) {
        const name = stepEl.querySelector(".ugg-timer__step-name");

        currentPanel.hidden = false;
        currentName.textContent = name ? name.textContent : "";
        currentEquipment.textContent = stepEl.dataset.equipment || "";

        if (stepEl.dataset.muscles) {
            currentMuscles.hidden = false;
            currentMuscles.textContent = stepEl.dataset.muscles;
        } else {
            currentMuscles.hidden = true;
        }

        photoUrls = stepEl.dataset.photos ? stepEl.dataset.photos.split("|") : [];
        photoIndex = 0;
        showCurrentPhoto();
        startPhotoRotation();
    }

    function exerciseName(itemId) {
        const el = dialog.querySelector(
            `.ugg-timer__step[data-item-id="${itemId}"] .ugg-timer__step-name`
        );
        return el ? el.textContent : "";
    }

    // Pendant une pause (repos, récupération), affiche l'exercice qui arrive
    // plutôt que celui qu'on vient de terminer (issue #59) : le prochain pas
    // d'effort dans l'ordre chronologique du minuteur.
    function nextWorkExerciseName(fromIndex) {
        for (let i = fromIndex + 1; i < steps.length; i += 1) {
            if (steps[i].phase === "work") return exerciseName(steps[i].itemId);
        }
        return null;
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

    // Une reprise après une récupération de tour/bloc redonne 5 s de
    // préparation, comme au tout début de la séance (issue #61).
    function needsPrep(nextIndex) {
        return (
            nextIndex > 0 && nextIndex < steps.length && steps[nextIndex - 1].phase === "recovery"
        );
    }

    function goTo(nextIndex) {
        stopInterval();
        if (needsPrep(nextIndex)) {
            runPrep(nextIndex);
            return;
        }
        activateStep(nextIndex);
    }

    function activateStep(nextIndex) {
        pendingPrepIndex = null;
        index = nextIndex;
        if (index >= steps.length) {
            finish();
            return;
        }

        const step = steps[index];
        highlight(step.itemId);
        dialog.dataset.phase = step.phase;
        phaseEl.textContent = PHASE_LABELS[step.phase] || "Repos";
        if (step.phase === "work") {
            exerciseEl.textContent = exerciseName(step.itemId);
        } else {
            const upcoming = nextWorkExerciseName(index);
            exerciseEl.textContent = upcoming ? `Suivant : ${upcoming}` : exerciseName(step.itemId);
        }
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
            activeIntervalCallback = tick;
            intervalId = window.setInterval(activeIntervalCallback, 1000);
        }

        updateProgress();
        playCue(step.phase);
        announceEl.textContent = `${phaseEl.textContent} : ${exerciseEl.textContent}`;
    }

    function finish() {
        stopInterval();
        stopPhotoRotation();
        photoUrls = [];
        activeIntervalCallback = null;
        pendingPrepIndex = null;
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
        currentPanel.hidden = true;
        playCue("end");
        announceEl.textContent = "Séance terminée.";
    }

    function reset() {
        stopInterval();
        index = -1;
        pendingPrepIndex = null;
        pauseBtn.disabled = false;
        pauseBtn.textContent = "Pause";
        nextBtn.disabled = false;
        stopBtn.textContent = "Arrêter";
    }

    // Cinq secondes pour se mettre en place avant un pas d'effort : au tout
    // début de la séance, et après chaque récupération entre tours/blocs
    // (issue #61) — le même sas, généralisé. `remaining`/`total` restent
    // figés sur le dernier pas réellement joué pendant qu'elle dure : c'est
    // ce qui garde la préparation hors de l'avancement de la séance
    // (overallPercent ne s'appuie que sur eux, jamais sur prepRemaining).
    function runPrep(nextIndex) {
        stopInterval();
        pendingPrepIndex = nextIndex;
        const nextStep = steps[nextIndex];
        highlight(nextStep.itemId);
        dialog.dataset.phase = "prep";
        phaseEl.textContent = "Préparation";
        exerciseEl.textContent = exerciseName(nextStep.itemId);
        lapEl.textContent =
            nextStep.totalLaps > 1 ? `Tour ${nextStep.lap} / ${nextStep.totalLaps}` : "";

        clockEl.hidden = false;
        repsEl.hidden = true;
        progressWrap.hidden = false;
        pauseBtn.disabled = false;
        pauseBtn.textContent = "Pause";

        prepRemaining = PREP_SECONDS;
        clockEl.textContent = formatClock(prepRemaining);
        updateProgress();
        announceEl.textContent = `Préparation : ${exerciseEl.textContent}`;
        activeIntervalCallback = () => prepTick(nextIndex);
        intervalId = window.setInterval(activeIntervalCallback, 1000);
    }

    function prepTick(nextIndex) {
        prepRemaining -= 1;
        clockEl.textContent = formatClock(Math.max(0, prepRemaining));
        if (prepRemaining > 0 && prepRemaining <= 4) {
            playCue("tick");
        }
        if (prepRemaining <= 0) {
            stopInterval();
            activateStep(nextIndex);
        }
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
        requestWakeLock();
        setupMediaSession();
        playCue("start");
        runPrep(0);
    });

    // Extraites en fonctions nommées pour être aussi déclenchables par les
    // touches multimédias du clavier sur poste de bureau (issue #55).
    function togglePause() {
        if (pauseBtn.disabled) return;
        if (intervalId) {
            stopInterval();
            stopPhotoRotation();
            pauseBtn.textContent = "Reprendre";
            announceEl.textContent = "Séance en pause.";
        } else if (activeIntervalCallback) {
            intervalId = window.setInterval(activeIntervalCallback, 1000);
            startPhotoRotation();
            pauseBtn.textContent = "Pause";
            announceEl.textContent = "Séance reprise.";
        }
    }

    function skipStep() {
        if (nextBtn.disabled) return;
        // Une préparation en cours (issue #61) est un sas, pas un pas à part
        // entière : « Passer » y coupe court directement au pas visé, plutôt
        // que de la redéclencher (goTo la relancerait, `needsPrep` restant vrai).
        if (pendingPrepIndex !== null) {
            stopInterval();
            activateStep(pendingPrepIndex);
            return;
        }
        goTo(index + 1);
    }

    pauseBtn.addEventListener("click", togglePause);
    nextBtn.addEventListener("click", skipStep);
    stopBtn.addEventListener("click", () => dialog.close());

    // Aucune API web ne permet de piloter une appli tierce (Spotify, lecteur
    // du téléphone…) — barrière de sécurité du navigateur. Sur poste de
    // bureau seulement (≥ 40rem), les touches multimédias du clavier
    // pilotent donc le minuteur lui-même ; rien n'est affiché à l'écran, et
    // rien n'est enregistré sur mobile.
    const desktopQuery = window.matchMedia("(min-width: 40rem)");

    function setSessionHandler(action, handler) {
        try {
            navigator.mediaSession.setActionHandler(action, handler);
        } catch {
            // Action non supportée par ce navigateur : ignorée silencieusement.
        }
    }

    function setupMediaSession() {
        if (!("mediaSession" in navigator) || !desktopQuery.matches) return;
        setSessionHandler("play", togglePause);
        setSessionHandler("pause", togglePause);
        setSessionHandler("nexttrack", skipStep);
    }

    function teardownMediaSession() {
        if (!("mediaSession" in navigator)) return;
        setSessionHandler("play", null);
        setSessionHandler("pause", null);
        setSessionHandler("nexttrack", null);
    }

    // Pas de fermeture au clic sur le fond : une séance en cours ne doit pas
    // s'interrompre d'un geste accidentel. Seul « Arrêter » — ou Échap, natif
    // au <dialog> — y met fin ; les deux passent par le même événement
    // « close », qui arrête toujours le décompte et le défilement des photos.
    dialog.addEventListener("close", () => {
        stopInterval();
        stopPhotoRotation();
        releaseWakeLock();
        teardownMediaSession();
    });
})();
