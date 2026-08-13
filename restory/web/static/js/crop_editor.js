/**
 * restory.web.static.js.crop_editor — Canvas Editor with Canva-style Dragging & Dynamic Cursors.
 */

let activeChapter = "01";
let pageList = [];
let currentPageIndex = 0;
let boxesData = {}; // stem -> array of boxes
let currentImage = new Image();
let imageLoaded = false;
let rtlDirection = true;
let selectedBoxIndex = -1;

// Drag & Resize State
let isDrawing = false;
let isDragging = false;
let isResizing = false;
let resizeHandle = null;
let dragStartX = 0;
let dragStartY = 0;
let initialBoxCoords = null;

const canvas = document.getElementById('editor-canvas');
const ctx = canvas.getContext('2d');
const HANDLE_RADIUS = 7;

async function initEditor() {
    setupEventListeners();
    await fetchChapterData();
    await fetchPageData();
}

async function fetchChapterData() {
    try {
        const res = await fetch('/api/chapter-data');
        const data = await res.json();
        rtlDirection = data.rtl !== false;
        
        const rtlTrue = document.getElementById('rtl-true');
        const rtlFalse = document.getElementById('rtl-false');
        if (rtlTrue && rtlFalse) {
            rtlTrue.checked = rtlDirection;
            rtlFalse.checked = !rtlDirection;
        }

        const select = document.getElementById('chapter-select');
        if (select) {
            select.innerHTML = '';
            data.chapters.forEach(ch => {
                const opt = document.createElement('option');
                opt.value = ch;
                opt.textContent = `Chapter ${ch}`;
                if (ch === data.active_chapter) opt.selected = true;
                select.appendChild(opt);
            });
            activeChapter = data.active_chapter;
        }
    } catch (e) {
        console.error('Failed to load chapter data:', e);
    }
}

async function fetchPageData() {
    try {
        const res = await fetch(`/api/page-data?chapter=${activeChapter}`);
        const data = await res.json();
        pageList = data.pages || [];
        boxesData = data.boxes.pages || data.boxes || {};
        currentPageIndex = 0;
        selectedBoxIndex = -1;
        loadCurrentPage();
    } catch (e) {
        console.error('Failed to load page data:', e);
    }
}

function loadCurrentPage() {
    if (pageList.length === 0) return;
    const pInfo = pageList[currentPageIndex];
    document.getElementById('page-indicator').textContent = `Page ${currentPageIndex + 1} / ${pageList.length}`;
    
    imageLoaded = false;
    currentImage = new Image();
    currentImage.src = `/image/download/${activeChapter}/${pInfo.filename}`;
    currentImage.onload = () => {
        canvas.width = currentImage.width;
        canvas.height = currentImage.height;
        imageLoaded = true;
        renderCanvas();
        updateSidebar();
    };
}

function getCurrentBoxes() {
    if (pageList.length === 0) return [];
    const stem = pageList[currentPageIndex].stem;
    if (!boxesData[stem]) boxesData[stem] = [];
    return boxesData[stem];
}

function renderCanvas() {
    if (!imageLoaded) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(currentImage, 0, 0);

    const boxes = getCurrentBoxes();
    boxes.forEach((box, idx) => {
        if (!box.visible) return;

        const x1 = Math.min(box.x1, box.x2);
        const y1 = Math.min(box.y1, box.y2);
        const w = Math.abs(box.x2 - box.x1);
        const h = Math.abs(box.y2 - box.y1);

        const isSelected = idx === selectedBoxIndex;

        // Box Fill & Stroke
        ctx.fillStyle = isSelected ? 'rgba(56, 189, 248, 0.22)' : 'rgba(34, 197, 94, 0.16)';
        ctx.strokeStyle = isSelected ? '#38bdf8' : '#22c55e';
        ctx.lineWidth = isSelected ? 3 : 2;

        ctx.fillRect(x1, y1, w, h);
        ctx.strokeRect(x1, y1, w, h);

        // Panel Number Badge
        ctx.fillStyle = isSelected ? '#38bdf8' : '#22c55e';
        ctx.fillRect(x1, y1, Math.min(w, 36), 22);
        ctx.fillStyle = '#090d16';
        ctx.font = 'bold 13px sans-serif';
        ctx.fillText(`${idx + 1}`, x1 + 8, y1 + 16);

        // Render Handles for selected box
        if (isSelected && !box.locked) {
            drawHandles(x1, y1, w, h);
        }
    });
}

function drawHandles(x, y, w, h) {
    const handles = getHandleCoords(x, y, w, h);
    ctx.fillStyle = '#ffffff';
    ctx.strokeStyle = '#38bdf8';
    ctx.lineWidth = 2;

    Object.values(handles).forEach(pt => {
        ctx.beginPath();
        ctx.arc(pt.x, pt.y, HANDLE_RADIUS, 0, 2 * Math.PI);
        ctx.fill();
        ctx.stroke();
    });
}

function getHandleCoords(x, y, w, h) {
    return {
        nw: { x: x, y: y },
        ne: { x: x + w, y: y },
        se: { x: x + w, y: y + h },
        sw: { x: x, y: y + h },
        n:  { x: x + w / 2, y: y },
        s:  { x: x + w / 2, y: y + h },
        w:  { x: x, y: y + h / 2 },
        e:  { x: x + w, y: y + h / 2 },
    };
}

/**
 * Canva-style Mouse Coordinate Mapper: Clamps coordinates seamlessly even when dragging outside canvas.
 */
function getCanvasMousePos(e) {
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;

    let x = Math.round((e.clientX - rect.left) * scaleX);
    let y = Math.round((e.clientY - rect.top) * scaleY);

    // Canva-style clamping to image boundaries
    x = Math.max(0, Math.min(x, canvas.width));
    y = Math.max(0, Math.min(y, canvas.height));

    return { x, y };
}

/**
 * Dynamic Cursor & Icon Changes based on hover state.
 */
function updateDynamicCursor(pos) {
    if (isDragging) {
        canvas.style.cursor = 'grabbing';
        return;
    }
    if (isResizing) {
        canvas.style.cursor = getHandleCursorIcon(resizeHandle);
        return;
    }

    const boxes = getCurrentBoxes();
    if (selectedBoxIndex >= 0 && selectedBoxIndex < boxes.length) {
        const b = boxes[selectedBoxIndex];
        if (!b.locked) {
            const x1 = Math.min(b.x1, b.x2);
            const y1 = Math.min(b.y1, b.y2);
            const w = Math.abs(b.x2 - b.x1);
            const h = Math.abs(b.y2 - b.y1);
            const handles = getHandleCoords(x1, y1, w, h);

            for (const [key, pt] of Object.entries(handles)) {
                if (Math.hypot(pos.x - pt.x, pos.y - pt.y) <= HANDLE_RADIUS * 1.6) {
                    canvas.style.cursor = getHandleCursorIcon(key);
                    return;
                }
            }
        }
    }

    // Check box hover
    for (let i = boxes.length - 1; i >= 0; i--) {
        const b = boxes[i];
        const x1 = Math.min(b.x1, b.x2);
        const x2 = Math.max(b.x1, b.x2);
        const y1 = Math.min(b.y1, b.y2);
        const y2 = Math.max(b.y1, b.y2);

        if (pos.x >= x1 && pos.x <= x2 && pos.y >= y1 && pos.y <= y2) {
            canvas.style.cursor = 'grab';
            return;
        }
    }

    canvas.style.cursor = 'crosshair';
}

function getHandleCursorIcon(handle) {
    switch (handle) {
        case 'nw': case 'se': return 'nwse-resize';
        case 'ne': case 'sw': return 'nesw-resize';
        case 'n':  case 's':  return 'ns-resize';
        case 'e':  case 'w':  return 'ew-resize';
        default: return 'pointer';
    }
}

function deleteBoxAt(pos) {
    const boxes = getCurrentBoxes();
    for (let i = boxes.length - 1; i >= 0; i--) {
        const b = boxes[i];
        if (b.locked) continue;
        const x1 = Math.min(b.x1, b.x2);
        const x2 = Math.max(b.x1, b.x2);
        const y1 = Math.min(b.y1, b.y2);
        const y2 = Math.max(b.y1, b.y2);

        if (pos.x >= x1 && pos.x <= x2 && pos.y >= y1 && pos.y <= y2) {
            boxes.splice(i, 1);
            selectedBoxIndex = -1;
            showToast('Panel box deleted');
            renderCanvas();
            updateSidebar();
            return true;
        }
    }
    return false;
}

function setupEventListeners() {
    // Right-click deletes panel box
    canvas.addEventListener('contextmenu', (e) => {
        e.preventDefault();
        const pos = getCanvasMousePos(e);
        deleteBoxAt(pos);
    });

    canvas.addEventListener('mousedown', (e) => {
        if (e.button === 2) return; // Right-click handled by contextmenu
        const pos = getCanvasMousePos(e);
        const boxes = getCurrentBoxes();

        // Check handle click on selected box
        if (selectedBoxIndex >= 0 && selectedBoxIndex < boxes.length) {
            const b = boxes[selectedBoxIndex];
            if (!b.locked) {
                const x1 = Math.min(b.x1, b.x2);
                const y1 = Math.min(b.y1, b.y2);
                const w = Math.abs(b.x2 - b.x1);
                const h = Math.abs(b.y2 - b.y1);
                const handles = getHandleCoords(x1, y1, w, h);

                for (const [key, pt] of Object.entries(handles)) {
                    if (Math.hypot(pos.x - pt.x, pos.y - pt.y) <= HANDLE_RADIUS * 1.6) {
                        isResizing = true;
                        resizeHandle = key;
                        initialBoxCoords = { ...b };
                        return;
                    }
                }
            }
        }

        // Check box click
        let clickedIdx = -1;
        for (let i = boxes.length - 1; i >= 0; i--) {
            const b = boxes[i];
            const x1 = Math.min(b.x1, b.x2);
            const x2 = Math.max(b.x1, b.x2);
            const y1 = Math.min(b.y1, b.y2);
            const y2 = Math.max(b.y1, b.y2);

            if (pos.x >= x1 && pos.x <= x2 && pos.y >= y1 && pos.y <= y2) {
                clickedIdx = i;
                break;
            }
        }

        if (clickedIdx >= 0) {
            selectedBoxIndex = clickedIdx;
            const b = boxes[selectedBoxIndex];
            if (!b.locked) {
                isDragging = true;
                dragStartX = pos.x;
                dragStartY = pos.y;
                initialBoxCoords = { ...b };
            }
            renderCanvas();
            updateSidebar();
        } else {
            // Start drawing new Canva-style box
            selectedBoxIndex = -1;
            isDrawing = true;
            dragStartX = pos.x;
            dragStartY = pos.y;
            const newBox = { x1: pos.x, y1: pos.y, x2: pos.x, y2: pos.y, z_index: boxes.length, visible: true, locked: false, label: 'manual' };
            boxes.push(newBox);
            selectedBoxIndex = boxes.length - 1;
        }
    });

    window.addEventListener('mousemove', (e) => {
        if (!imageLoaded) return;
        const pos = getCanvasMousePos(e);
        updateDynamicCursor(pos);

        const boxes = getCurrentBoxes();

        if (isDrawing && selectedBoxIndex >= 0) {
            const b = boxes[selectedBoxIndex];
            b.x2 = pos.x;
            b.y2 = pos.y;
            renderCanvas();
        } else if (isDragging && selectedBoxIndex >= 0) {
            const dx = pos.x - dragStartX;
            const dy = pos.y - dragStartY;
            const b = boxes[selectedBoxIndex];
            b.x1 = initialBoxCoords.x1 + dx;
            b.x2 = initialBoxCoords.x2 + dx;
            b.y1 = initialBoxCoords.y1 + dy;
            b.y2 = initialBoxCoords.y2 + dy;
            renderCanvas();
        } else if (isResizing && selectedBoxIndex >= 0) {
            const b = boxes[selectedBoxIndex];
            if (resizeHandle === 'nw') { b.x1 = pos.x; b.y1 = pos.y; }
            if (resizeHandle === 'ne') { b.x2 = pos.x; b.y1 = pos.y; }
            if (resizeHandle === 'se') { b.x2 = pos.x; b.y2 = pos.y; }
            if (resizeHandle === 'sw') { b.x1 = pos.x; b.y2 = pos.y; }
            if (resizeHandle === 'n')  { b.y1 = pos.y; }
            if (resizeHandle === 's')  { b.y2 = pos.y; }
            if (resizeHandle === 'w')  { b.x1 = pos.x; }
            if (resizeHandle === 'e')  { b.x2 = pos.x; }
            renderCanvas();
        }
    });

    window.addEventListener('mouseup', () => {
        if (isDrawing || isDragging || isResizing) {
            isDrawing = false;
            isDragging = false;
            isResizing = false;

            if (selectedBoxIndex >= 0) {
                const boxes = getCurrentBoxes();
                const b = boxes[selectedBoxIndex];
                if (b) {
                    const x1 = Math.min(b.x1, b.x2);
                    const x2 = Math.max(b.x1, b.x2);
                    const y1 = Math.min(b.y1, b.y2);
                    const y2 = Math.max(b.y1, b.y2);

                    if (x2 - x1 < 18 || y2 - y1 < 18) {
                        boxes.splice(selectedBoxIndex, 1);
                        selectedBoxIndex = -1;
                    } else {
                        b.x1 = x1; b.x2 = x2; b.y1 = y1; b.y2 = y2;
                    }
                }
            }
            renderCanvas();
            updateSidebar();
        }
    });

    // Keyboard Shortcuts
    window.addEventListener('keydown', (e) => {
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT' || e.target.tagName === 'TEXTAREA') return;

        // Key 'F': Set Single Full-Page Box
        if (e.key === 'f' || e.key === 'F') {
            e.preventDefault();
            addFullPageBox();
            return;
        }

        // Delete / Backspace: Remove selected box
        if (e.key === 'Delete' || e.key === 'Backspace') {
            if (selectedBoxIndex >= 0) {
                e.preventDefault();
                const boxes = getCurrentBoxes();
                boxes.splice(selectedBoxIndex, 1);
                selectedBoxIndex = -1;
                renderCanvas();
                updateSidebar();
            }
            return;
        }

        // Navigation
        if (e.key === 'a' || e.key === 'A' || e.key === 'ArrowLeft') prevPage();
        if (e.key === 'd' || e.key === 'D' || e.key === 'ArrowRight') nextPage();

        // Save
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
            e.preventDefault();
            saveAndRecrop();
        }
    });
}

function updateSidebar() {
    renderLayerStack(getCurrentBoxes(), selectedBoxIndex, {
        onSelect: (idx) => { selectedBoxIndex = idx; renderCanvas(); updateSidebar(); },
        onToggleVisible: (idx) => { const b = getCurrentBoxes()[idx]; if (b) b.visible = !b.visible; renderCanvas(); updateSidebar(); },
        onToggleLock: (idx) => { const b = getCurrentBoxes()[idx]; if (b) b.locked = !b.locked; renderCanvas(); updateSidebar(); },
        onDelete: (idx) => { getCurrentBoxes().splice(idx, 1); selectedBoxIndex = -1; renderCanvas(); updateSidebar(); },
    });
}

/**
 * Key 'F' Action: Clear all existing boxes on page and replace with single full-page box.
 */
function addFullPageBox() {
    if (!imageLoaded) return;
    const boxes = getCurrentBoxes();
    boxes.length = 0; // Clear all existing boxes
    boxes.push({
        x1: 0,
        y1: 0,
        x2: currentImage.width,
        y2: currentImage.height,
        z_index: 0,
        type: "rectangle",
        locked: false,
        visible: true,
        label: "full_page"
    });
    selectedBoxIndex = 0;
    showToast('Page set to single full-page panel');
    renderCanvas();
    updateSidebar();
}

function prevPage() {
    if (currentPageIndex > 0) {
        currentPageIndex--;
        selectedBoxIndex = -1;
        loadCurrentPage();
    }
}

function nextPage() {
    if (currentPageIndex < pageList.length - 1) {
        currentPageIndex++;
        selectedBoxIndex = -1;
        loadCurrentPage();
    }
}

async function switchChapter(ch) {
    activeChapter = ch;
    await fetchPageData();
}

async function updateRtl(val) {
    rtlDirection = val;
    try {
        const boxes = getCurrentBoxes();
        const res = await fetch('/api/sort-boxes', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ boxes: boxes, rtl: rtlDirection })
        });
        const data = await res.json();
        if (data.sorted_boxes) {
            const stem = pageList[currentPageIndex].stem;
            boxesData[stem] = data.sorted_boxes;
            renderCanvas();
            updateSidebar();
        }
    } catch (e) {
        console.error('Failed to sort boxes:', e);
    }
}

async function runRedetect() {
    if (pageList.length === 0) return;
    const engine = document.getElementById('engine-select').value;
    const filename = pageList[currentPageIndex].filename;
    
    showToast(`Running ${engine.toUpperCase()} detection live...`);
    try {
        const res = await fetch('/api/redetect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ chapter: activeChapter, filename: filename, engine: engine })
        });
        const data = await res.json();
        if (data.status === 'ok') {
            const stem = pageList[currentPageIndex].stem;
            boxesData[stem] = data.boxes || [];
            selectedBoxIndex = -1;
            showToast('Page re-detected live!');
            renderCanvas();
            updateSidebar();
        }
    } catch (e) {
        console.error('Re-detect failed:', e);
    }
}

async function saveAndRecrop() {
    try {
        const res = await fetch('/api/save-boxes', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ chapter: activeChapter, boxes: { pages: boxesData }, rtl: rtlDirection })
        });
        const data = await res.json();
        if (data.status === 'ok') {
            showToast('Saved & Re-Cropped panels!');
        }
    } catch (e) {
        console.error('Save failed:', e);
    }
}

async function finishAndContinue() {
    await saveAndRecrop();
    try {
        await fetch('/api/shutdown', { method: 'POST' });
    } catch (e) {}
    window.close();
}

function showToast(msg) {
    const toast = document.getElementById('toast');
    if (!toast) return;
    toast.textContent = msg;
    toast.style.opacity = '1';
    setTimeout(() => { toast.style.opacity = '0'; }, 2200);
}

document.addEventListener('DOMContentLoaded', initEditor);