/**
 * restory.crop_editor — Interactive HTML5 canvas editor for Paged Manga panel bounding boxes.
 */

let chaptersData = [];
let currentChapter = "";
let currentPageIdx = 0;
let pagesData = [];
let boxesData = {};
let isRtl = true;

let canvas = document.getElementById("editor-canvas");
let ctx = canvas.getContext("2d");
let currentImage = new Image();

let selectedBoxIdx = -1;
let isDrawing = false;
let isDragging = false;
let isResizing = false;
let startX = 0, startY = 0;
let resizeHandleIdx = -1;
const HANDLE_SIZE = 10;

async function init() {
    let res = await fetch("/api/chapter-data");
    let data = await res.json();
    chaptersData = data.chapters || [];
    currentChapter = data.active_chapter || "01";
    isRtl = data.rtl !== false;

    let select = document.getElementById("chapter-select");
    select.innerHTML = "";
    chaptersData.forEach(ch => {
        let opt = document.createElement("option");
        opt.value = ch;
        opt.textContent = `Chapter ${ch}`;
        if (ch === currentChapter) opt.selected = true;
        select.appendChild(opt);
    });

    await loadChapter(currentChapter);
    setupCanvasEvents();
    setupKeyEvents();
}

async function loadChapter(ch) {
    currentChapter = ch;
    let res = await fetch(`/api/page-data?chapter=${ch}`);
    let data = await res.json();
    pagesData = data.pages || [];
    boxesData = data.boxes || { pages: {} };
    currentPageIdx = 0;
    loadCurrentPage();
}

function loadCurrentPage() {
    if (!pagesData || pagesData.length === 0) return;
    let page = pagesData[currentPageIdx];
    document.getElementById("page-indicator").textContent = `Page ${currentPageIdx + 1} / ${pagesData.length}`;

    currentImage.src = `/image/download/${currentChapter}/${page.filename}`;
    currentImage.onload = () => {
        canvas.width = currentImage.width;
        canvas.height = currentImage.height;

        let pagesMap = boxesData.pages || boxesData;
        if (!pagesMap[page.stem]) {
            pagesMap[page.stem] = [];
        }
        selectedBoxIdx = -1;
        render();
        updateLayers();
    };
}

function getBoxes() {
    if (!pagesData[currentPageIdx]) return [];
    let stem = pagesData[currentPageIdx].stem;
    let pagesMap = boxesData.pages || boxesData;
    return pagesMap[stem] || [];
}

function render() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(currentImage, 0, 0);

    let boxes = getBoxes();
    boxes.forEach((b, idx) => {
        if (b.visible === false) return;

        let isSelected = idx === selectedBoxIdx;
        ctx.lineWidth = isSelected ? 5 : 3;
        ctx.strokeStyle = isSelected ? "#22c55e" : (b.locked ? "#f59e0b" : "#ef4444");
        ctx.fillStyle = isSelected ? "rgba(34, 197, 94, 0.15)" : "rgba(239, 68, 68, 0.1)";

        let w = b.x2 - b.x1;
        let h = b.y2 - b.y1;
        ctx.fillRect(b.x1, b.y1, w, h);
        ctx.strokeRect(b.x1, b.y1, w, h);

        ctx.fillStyle = isSelected ? "#22c55e" : "#ef4444";
        ctx.fillRect(b.x1, b.y1, 28, 28);
        ctx.fillStyle = "#ffffff";
        ctx.font = "bold 16px sans-serif";
        ctx.fillText(String(idx + 1), b.x1 + 8, b.y1 + 20);

        if (isSelected && !b.locked) drawHandles(b);
    });
}

function drawHandles(b) {
    ctx.fillStyle = "#ffffff";
    ctx.strokeStyle = "#000000";
    ctx.lineWidth = 1;
    let handles = [
        { x: b.x1, y: b.y1 }, { x: b.x2, y: b.y1 },
        { x: b.x2, y: b.y2 }, { x: b.x1, y: b.y2 }
    ];
    handles.forEach(h => {
        ctx.fillRect(h.x - HANDLE_SIZE / 2, h.y - HANDLE_SIZE / 2, HANDLE_SIZE, HANDLE_SIZE);
        ctx.strokeRect(h.x - HANDLE_SIZE / 2, h.y - HANDLE_SIZE / 2, HANDLE_SIZE, HANDLE_SIZE);
    });
}

function updateLayers() {
    renderLayerStack(getBoxes(), selectedBoxIdx, {
        onSelect: (idx) => { selectedBoxIdx = idx; render(); updateLayers(); }
    });
}

window.toggleLayerVisible = function(idx) {
    let boxes = getBoxes();
    if (boxes[idx]) {
        boxes[idx].visible = boxes[idx].visible === false;
        render();
        updateLayers();
    }
};

window.toggleLayerLock = function(idx) {
    let boxes = getBoxes();
    if (boxes[idx]) {
        boxes[idx].locked = !boxes[idx].locked;
        render();
        updateLayers();
    }
};

window.deleteLayer = function(idx) {
    let boxes = getBoxes();
    boxes.splice(idx, 1);
    selectedBoxIdx = -1;
    render();
    updateLayers();
};

function addFullPageBox() {
    let boxes = getBoxes();
    boxes.push({
        x1: 0, y1: 0, x2: canvas.width, y2: canvas.height,
        z_index: boxes.length, type: "rectangle", locked: false, visible: true, label: "Full Page"
    });
    selectedBoxIdx = boxes.length - 1;
    render();
    updateLayers();
}

function setupCanvasEvents() {
    canvas.addEventListener("mousedown", (e) => {
        let rect = canvas.getBoundingClientRect();
        let scaleX = canvas.width / rect.width;
        let scaleY = canvas.height / rect.height;
        let x = (e.clientX - rect.left) * scaleX;
        let y = (e.clientY - rect.top) * scaleY;

        let boxes = getBoxes();

        if (selectedBoxIdx >= 0 && !boxes[selectedBoxIdx].locked) {
            let b = boxes[selectedBoxIdx];
            let handles = [
                { x: b.x1, y: b.y1 }, { x: b.x2, y: b.y1 },
                { x: b.x2, y: b.y2 }, { x: b.x1, y: b.y2 }
            ];
            for (let i = 0; i < handles.length; i++) {
                if (Math.abs(x - handles[i].x) <= HANDLE_SIZE * 1.5 && Math.abs(y - handles[i].y) <= HANDLE_SIZE * 1.5) {
                    isResizing = true;
                    resizeHandleIdx = i;
                    return;
                }
            }
        }

        for (let i = boxes.length - 1; i >= 0; i--) {
            let b = boxes[i];
            if (!b.locked && b.visible !== false && x >= b.x1 && x <= b.x2 && y >= b.y1 && y <= b.y2) {
                selectedBoxIdx = i;
                isDragging = true;
                startX = x - b.x1;
                startY = y - b.y1;
                render();
                updateLayers();
                return;
            }
        }

        isDrawing = true;
        startX = x;
        startY = y;
        selectedBoxIdx = -1;
    });

    canvas.addEventListener("mousemove", (e) => {
        let rect = canvas.getBoundingClientRect();
        let scaleX = canvas.width / rect.width;
        let scaleY = canvas.height / rect.height;
        let x = (e.clientX - rect.left) * scaleX;
        let y = (e.clientY - rect.top) * scaleY;

        let boxes = getBoxes();

        if (isDrawing) {
            render();
            ctx.strokeStyle = "#22c55e";
            ctx.lineWidth = 2;
            ctx.strokeRect(startX, startY, x - startX, y - startY);
        } else if (isDragging && selectedBoxIdx >= 0) {
            let b = boxes[selectedBoxIdx];
            let w = b.x2 - b.x1;
            let h = b.y2 - b.y1;
            b.x1 = Math.max(0, Math.min(canvas.width - w, x - startX));
            b.y1 = Math.max(0, Math.min(canvas.height - h, y - startY));
            b.x2 = b.x1 + w;
            b.y2 = b.y1 + h;
            render();
        } else if (isResizing && selectedBoxIdx >= 0) {
            let b = boxes[selectedBoxIdx];
            if (resizeHandleIdx === 0) { b.x1 = x; b.y1 = y; }
            else if (resizeHandleIdx === 1) { b.x2 = x; b.y1 = y; }
            else if (resizeHandleIdx === 2) { b.x2 = x; b.y2 = y; }
            else if (resizeHandleIdx === 3) { b.x1 = x; b.y2 = y; }
            render();
        }
    });

    canvas.addEventListener("mouseup", (e) => {
        if (isDrawing) {
            let rect = canvas.getBoundingClientRect();
            let scaleX = canvas.width / rect.width;
            let scaleY = canvas.height / rect.height;
            let x = (e.clientX - rect.left) * scaleX;
            let y = (e.clientY - rect.top) * scaleY;

            let x1 = Math.min(startX, x);
            let y1 = Math.min(startY, y);
            let x2 = Math.max(startX, x);
            let y2 = Math.max(startY, y);

            if (x2 - x1 > 30 && y2 - y1 > 30) {
                let boxes = getBoxes();
                boxes.push({
                    x1: Math.round(x1), y1: Math.round(y1), x2: Math.round(x2), y2: Math.round(y2),
                    z_index: boxes.length, type: "rectangle", locked: false, visible: true, label: "User Box"
                });
                selectedBoxIdx = boxes.length - 1;
                updateLayers();
            }
        }

        isDrawing = false;
        isDragging = false;
        isResizing = false;
        render();
    });
}

function setupKeyEvents() {
    window.addEventListener("keydown", (e) => {
        if (e.key === "ArrowLeft" || e.key.toLowerCase() === "a") prevPage();
        else if (e.key === "ArrowRight" || e.key.toLowerCase() === "d") nextPage();
        else if (e.key.toLowerCase() === "f") addFullPageBox();
        else if (e.key === "Delete" || e.key === "Backspace") {
            if (selectedBoxIdx >= 0) window.deleteLayer(selectedBoxIdx);
        }
        else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
            e.preventDefault();
            saveAndRecrop();
        }
    });
}

function prevPage() { if (currentPageIdx > 0) { currentPageIdx--; loadCurrentPage(); } }
function nextPage() { if (currentPageIdx < pagesData.length - 1) { currentPageIdx++; loadCurrentPage(); } }

async function runRedetect() {
    let page = pagesData[currentPageIdx];
    let engine = document.getElementById("engine-select").value;

    let res = await fetch("/api/redetect", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ chapter: currentChapter, filename: page.filename, engine: engine })
    });
    let data = await res.json();
    let pagesMap = boxesData.pages || boxesData;
    pagesMap[page.stem] = data.boxes || [];
    render();
    updateLayers();
}

function updateRtl(val) { isRtl = val; }
async function switchChapter(ch) { await loadChapter(ch); }

async function saveAndRecrop() {
    let res = await fetch("/api/save-boxes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ chapter: currentChapter, boxes: boxesData, rtl: isRtl })
    });
    if (res.ok) {
        showToast("Saved & Re-Cropped Panels!");
    }
}

async function finishAndContinue() {
    await saveAndRecrop();
    showToast("Finishing Crop Phase & Resuming Pipeline...");
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