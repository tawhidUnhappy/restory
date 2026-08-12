/**
 * restory.narration_editor — Side-by-side scriptwriting UI with draft TTS audio preview and contract check.
 */

let chaptersData = [];
let currentChapter = "";
let entriesData = [];

async function init() {
    let res = await fetch("/api/chapters");
    let data = await res.json();
    chaptersData = data.chapters || [];
    currentChapter = data.active || "01";

    let select = document.getElementById("chapter-select");
    select.innerHTML = "";
    chaptersData.forEach(ch => {
        let opt = document.createElement("option");
        opt.value = ch;
        opt.textContent = `Chapter ${ch}`;
        if (ch === currentChapter) opt.selected = true;
        select.appendChild(opt);
    });

    await loadNarration(currentChapter);
    setupKeyEvents();
}

async function loadNarration(ch) {
    currentChapter = ch;
    let res = await fetch(`/api/narration-data?chapter=${ch}`);
    let data = await res.json();
    entriesData = data.entries || [];
    renderCards();
}

function renderCards() {
    let container = document.getElementById("card-list");
    if (!container) return;
    container.innerHTML = "";
    let narratedCount = 0;

    entriesData.forEach((entry, idx) => {
        let isBlank = !entry.narration || entry.narration.trim() === "";
        if (!isBlank) narratedCount++;

        let stem = entry.image ? entry.image.split(".")[0] : `panel_${idx}`;
        let card = document.createElement("div");
        card.className = `entry-card ${isBlank ? 'blank-entry' : ''}`;

        card.innerHTML = `
            <div class="image-container">
                <img class="panel-preview" src="/image/panels/${currentChapter}/${entry.image}" alt="${entry.image}">
                <div class="image-meta" style="display:flex; justify-content:space-between; font-size:0.8rem; color:var(--text-muted);">
                    <span><strong>#${idx + 1}</strong> ${entry.image}</span>
                    <span class="status-tag ${isBlank ? 'tag-blank' : 'tag-ok'}">${isBlank ? 'BLANK / COVER' : 'STORY'}</span>
                </div>
            </div>

            <div class="script-container">
                <textarea id="text-${idx}" placeholder="Write YouTube recap narration here..." oninput="updateEntryText(${idx}, this.value)">${entry.narration || ""}</textarea>

                <div class="meta-row">
                    <div class="field-group">
                        <label>Beat ID:</label>
                        <input type="text" value="${entry.beat_id || ''}" onchange="entriesData[${idx}].beat_id = this.value">
                    </div>
                    <div class="field-group">
                        <label>Pause (ms):</label>
                        <input type="number" style="width:80px;" value="${entry.pause_after_ms || 0}" step="100" onchange="entriesData[${idx}].pause_after_ms = parseInt(this.value) || 0">
                    </div>
                    <button onclick="previewAudio(${idx}, '${stem}')">🔊 Draft TTS Preview</button>
                    <button onclick="setBlank(${idx})">Set Blank ("")</button>
                </div>
            </div>
        `;

        container.appendChild(card);
    });

    document.getElementById("stats-counter").textContent = `${narratedCount} / ${entriesData.length} Narrated`;
}

function updateEntryText(idx, val) {
    entriesData[idx].narration = val;
    let isBlank = !val || val.trim() === "";
    let cards = document.querySelectorAll(".entry-card");
    if (cards[idx]) {
        if (isBlank) cards[idx].classList.add("blank-entry");
        else cards[idx].classList.remove("blank-entry");
    }
}

function setBlank(idx) {
    let textarea = document.getElementById(`text-${idx}`);
    if (textarea) textarea.value = "";
    updateEntryText(idx, "");
}

async function previewAudio(idx, stem) {
    let text = entriesData[idx].narration;
    let res = await fetch("/api/preview-tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ chapter: currentChapter, stem: stem, text: text })
    });
    let data = await res.json();
    if (data.audio_url) {
        let audio = new Audio(data.audio_url + `?t=${Date.now()}`);
        audio.play();
    }
}

async function saveNarration() {
    let res = await fetch("/api/save-narration", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ chapter: currentChapter, entries: entriesData })
    });
    if (res.ok) showToast("narration.json saved successfully!");
}

async function runNarrationCheck() {
    let res = await fetch("/api/narration-check", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ chapter: currentChapter })
    });
    let data = await res.json();
    if (data.ok) alert("Narration Contract Check Passed!");
    else alert(`Contract Error:\n${data.error}`);
}

async function finishAndContinue() {
    await saveNarration();
    showToast("Finishing Script Phase & Resuming Pipeline...");
    setTimeout(async () => {
        await fetch("/api/shutdown", { method: "POST" });
        window.close();
    }, 1000);
}

function setupKeyEvents() {
    window.addEventListener("keydown", (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
            e.preventDefault();
            saveNarration();
        }
    });
}

function showToast(msg) {
    let t = document.getElementById("toast");
    t.textContent = msg;
    t.style.opacity = "1";
    setTimeout(() => { t.style.opacity = "0"; }, 2500);
}

window.onload = init;