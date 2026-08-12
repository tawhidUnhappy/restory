/**
 * restory.webtoon_editor — Interactive webtoon strip cut manipulator and motion keyframer.
 */

let chaptersData = [];
let currentChapter = "";
let webtoonData = { cuts: [], panels: [] };
let selectedCutIdx = -1;

async function init() {
    let res = await fetch("/api/webtoon-data");
    let data = await res.json();
    currentChapter = data.chapter || "01";
    webtoonData = data.webtoon_data || { cuts: [0], panels: [] };

    renderStrip();
    setupKeyEvents();
}

function renderStrip() {
    let container = document.getElementById("canvas-container");
    if (!container) return;
    container.innerHTML = "";
    container.style.width = `${webtoonData.canvas_width || 800}px`;
    container.style.height = `${webtoonData.total_height || 10000}px`;

    let cuts = webtoonData.cuts || [0];
    cuts.forEach((cutY, idx) => {
        if (idx === 0 || idx === cuts.length - 1) return;

        let line = document.createElement("div");
        line.className = "cut-line-marker";
        line.style.top = `${cutY}px`;

        let handle = document.createElement("div");
        handle.className = "cut-handle";
        handle.innerHTML = `<span>Cut #${idx} (Y: ${cutY})</span> <button onclick="deleteCut(${idx})">🗑</button>`;
        line.appendChild(handle);

        setupDragCut(line, idx);
        container.appendChild(line);
    });

    document.getElementById("cuts-counter").textContent = `${cuts.length - 1} Panel Slices`;
}

function setupDragCut(lineEl, cutIdx) {
    let isDragging = false;

    lineEl.addEventListener("mousedown", (e) => {
        isDragging = true;
        e.stopPropagation();
    });

    window.addEventListener("mousemove", (e) => {
        if (!isDragging) return;
        let containerRect = document.getElementById("canvas-container").getBoundingClientRect();
        let newY = Math.round(e.clientY - containerRect.top);
        if (newY > 0 && newY < webtoonData.total_height) {
            webtoonData.cuts[cutIdx] = newY;
            lineEl.style.top = `${newY}px`;
        }
    });

    window.addEventListener("mouseup", () => {
        if (isDragging) {
            isDragging = false;
            webtoonData.cuts.sort((a, b) => a - b);
            renderStrip();
        }
    });
}

function addCutAtCenter() {
    let viewport = document.getElementById("viewport");
    let centerY = Math.round(viewport.scrollTop + viewport.clientHeight / 2);
    webtoonData.cuts.push(centerY);
    webtoonData.cuts.sort((a, b) => a - b);
    renderStrip();
}

function deleteCut(idx) {
    webtoonData.cuts.splice(idx, 1);
    renderStrip();
}

function setupKeyEvents() {
    window.addEventListener("keydown", (e) => {
        if (e.key.toLowerCase() === "s") addCutAtCenter();
        else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
            e.preventDefault();
            saveWebtoon();
        }
    });
}

async function saveWebtoon() {
    let res = await fetch("/api/save-webtoon", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ chapter: currentChapter, webtoon_data: webtoonData })
    });
    if (res.ok) {
        showToast("Webtoon Metadata Saved & Panels Cropped!");
    }
}

async function finishAndContinue() {
    await saveWebtoon();
    showToast("Finishing Webtoon Crop & Resuming Pipeline...");
    setTimeout(async () => {
        await fetch("/api/shutdown", { method: "POST" });
        window.close();
    }, 1000);
}

function showToast(msg) {
    let t = document.getElementById("toast");
    t.textContent = msg;
    t.style.opacity = "1";
    setTimeout(() => { t.style.opacity = "0"; }, 2500);
}

window.onload = init;