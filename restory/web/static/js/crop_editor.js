/* restory — Paged Manga Canvas Editor with Canva Alignment Guides */

let activeChapter = "01";
let chaptersList = [];
let pagesList = [];
let currentPageIndex = 0;
let pageBoxesMap = {};
let selectedBoxIndex = -1;
let isRtl = true;

// Canva Alignment Snapping State
let activeAlignmentGuides = []; // { type: 'v'|'h', pos: number }
const SNAP_THRESHOLD = 8;

// Dragging & Interaction State
let isDrawing = false;
let isDraggingBox = false;
let isResizingHandle = -1; // 0: TopLeft, 1: TopRight, 2: BotRight, 3: BotLeft
let dragStartX = 0, dragStartY = 0;
let initialBoxCoords = null;

const canvas = document.getElementById('editor-canvas');
const ctx = canvas ? canvas.getContext('2d') : null;
let currentImage = new Image();

async function initCropEditor() {
    try {
        const res = await fetch('/api/chapter-data');
        const data = await res.json();
        
        chaptersList = data.chapters || [];
        activeChapter = data.active_chapter || (chaptersList[0] || "01");
        isRtl = data.rtl !== undefined ? data.rtl : true;
        
        const rtlTrue = document.getElementById('rtl-true');
        const rtlFalse = document.getElementById('rtl-false');
        if (rtlTrue && rtlFalse) {
            rtlTrue.checked = isRtl;
            rtlFalse.checked = !isRtl;
        }
        
        populateChapterDropdown();
        await loadPageData(activeChapter);
    } catch (e) {
        console.error('Init crop editor failed:', e);
    }
}

function populateChapterDropdown() {
    const select = document.getElementById('chapter-select');
    if (!select) return;
    
    select.innerHTML = '';
    chaptersList.forEach(ch => {
        const opt = document.createElement('option');
        opt.value = ch;
        opt.innerText = `Chapter ${ch}`;
        if (ch === activeChapter) opt.selected = true;
        select.appendChild(opt);
    });
}

async function loadPageData(ch) {
    activeChapter = ch;
    selectedBoxIndex = -1;
    
    const res = await fetch(`/api/page-data?chapter=${ch}`);
    const data = await res.json();
    
    pagesList = data.pages || [];
    currentPageIndex = 0;
    
    const rawBoxes = data.boxes || {};
    pageBoxesMap = rawBoxes.pages || rawBoxes;
    
    if (pagesList.length > 0) {
        renderCurrentPage();
    }
}

function renderCurrentPage() {
    if (pagesList.length === 0) return;
    
    const pageObj = pagesList[currentPageIndex];
    document.getElementById('page-indicator').innerText = `Page ${currentPageIndex + 1} / ${pagesList.length}`;
    
    currentImage = new Image();
    currentImage.onload = () => {
        canvas.width = currentImage.width;
        canvas.height = currentImage.height;
        drawCanvas();
        updateLayerStack();
    };
    currentImage.src = `/image/download/${activeChapter}/${pageObj.filename}`;
}

function getBoxesForCurrentPage() {
    if (pagesList.length === 0) return [];
    const stem = pagesList[currentPageIndex].stem;
    if (!pageBoxesMap[stem]) {
        pageBoxesMap[stem] = [];
    }
    return pageBoxesMap[stem];
}

function drawCanvas() {
    if (!ctx || !currentImage.complete) return;
    
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(currentImage, 0, 0);
    
    const boxes = getBoxesForCurrentPage();
    
    // 1. Draw Panel Bounding Boxes
    boxes.forEach((box, idx) => {
        if (!box.visible) return;
        
        const isSelected = (idx === selectedBoxIndex);
        
        ctx.lineWidth = isSelected ? 4 : 2;
        ctx.strokeStyle = isSelected ? '#ffffff' : '#38bdf8';
        ctx.fillStyle = isSelected ? 'rgba(255, 255, 255, 0.12)' : 'rgba(56, 189, 248, 0.08)';
        
        const bw = box.x2 - box.x1;
        const bh = box.y2 - box.y1;
        
        ctx.fillRect(box.x1, box.y1, bw, bh);
        ctx.strokeRect(box.x1, box.y1, bw, bh);
        
        // Draw Panel Label Badge
        ctx.fillStyle = isSelected ? '#ffffff' : '#38bdf8';
        ctx.fillRect(box.x1, box.y1, 28, 22);
        ctx.fillStyle = '#09090b';
        ctx.font = 'bold 12px sans-serif';
        ctx.fillText(String(idx + 1), box.x1 + 8, box.y1 + 15);
        
        // Draw Canva Resize Handles if Selected
        if (isSelected && !box.locked) {
            drawResizeHandles(box);
        }
    });
    
    // 2. Draw Canva Alignment Guides
    activeAlignmentGuides.forEach(guide => {
        ctx.lineWidth = 1;
        ctx.strokeStyle = '#38bdf8';
        ctx.setLineDash([4, 4]);
        
        ctx.beginPath();
        if (guide.type === 'v') {
            ctx.moveTo(guide.pos, 0);
            ctx.lineTo(guide.pos, canvas.height);
        } else {
            ctx.moveTo(0, guide.pos);
            ctx.lineTo(canvas.width, guide.pos);
        }
        ctx.stroke();
        ctx.setLineDash([]);
    });
}

function drawResizeHandles(box) {
    const handleSize = 10;
    const handles = [
        { x: box.x1, y: box.y1 }, // Top-Left
        { x: box.x2, y: box.y1 }, // Top-Right
        { x: box.x2, y: box.y2 }, // Bot-Right
        { x: box.x1, y: box.y2 }  // Bot-Left
    ];
    
    ctx.fillStyle = '#ffffff';
    ctx.strokeStyle = '#09090b';
    ctx.lineWidth = 2;
    
    handles.forEach(h => {
        ctx.fillRect(h.x - handleSize/2, h.y - handleSize/2, handleSize, handleSize);
        ctx.strokeRect(h.x - handleSize/2, h.y - handleSize/2, handleSize, handleSize);
    });
}

function computeCanvaSnapping(candidateBox, currentBoxIndex) {
    activeAlignmentGuides = [];
    const boxes = getBoxesForCurrentPage();
    let snappedX1 = candidateBox.x1, snappedY1 = candidateBox.y1;
    let snappedX2 = candidateBox.x2, snappedY2 = candidateBox.y2;
    
    const vTargets = [0, canvas.width / 2, canvas.width];
    const hTargets = [0, canvas.height / 2, canvas.height];
    
    boxes.forEach((b, idx) => {
        if (idx === currentBoxIndex || !b.visible) return;
        vTargets.push(b.x1, b.x2, (b.x1 + b.x2) / 2);
        hTargets.push(b.y1, b.y2, (b.y1 + b.y2) / 2);
    });
    
    // Snap Vertical Edges
    vTargets.forEach(vt => {
        if (Math.abs(snappedX1 - vt) < SNAP_THRESHOLD) {
            snappedX1 = vt;
            activeAlignmentGuides.push({ type: 'v', pos: vt });
        }
        if (Math.abs(snappedX2 - vt) < SNAP_THRESHOLD) {
            snappedX2 = vt;
            activeAlignmentGuides.push({ type: 'v', pos: vt });
        }
    });
    
    // Snap Horizontal Edges
    hTargets.forEach(ht => {
        if (Math.abs(snappedY1 - ht) < SNAP_THRESHOLD) {
            snappedY1 = ht;
            activeAlignmentGuides.push({ type: 'h', pos: ht });
        }
        if (Math.abs(snappedY2 - ht) < SNAP_THRESHOLD) {
            snappedY2 = ht;
            activeAlignmentGuides.push({ type: 'h', pos: ht });
        }
    });
    
    return { x1: snappedX1, y1: snappedY1, x2: snappedX2, y2: snappedY2 };
}

// Interactive Mouse Canvas Events
if (canvas) {
    canvas.addEventListener('mousedown', (e) => {
        const rect = canvas.getBoundingClientRect();
        const scaleX = canvas.width / rect.width;
        const scaleY = canvas.height / rect.height;
        
        const mx = (e.clientX - rect.left) * scaleX;
        const my = (e.clientY - rect.top) * scaleY;
        
        const boxes = getBoxesForCurrentPage();
        
        // Right Click: Delete clicked panel
        if (e.button === 2) {
            e.preventDefault();
            const clickedIdx = boxes.findIndex(b => mx >= b.x1 && mx <= b.x2 && my >= b.y1 && my <= b.y2);
            if (clickedIdx !== -1) {
                boxes.splice(clickedIdx, 1);
                selectedBoxIndex = -1;
                drawCanvas();
                updateLayerStack();
            }
            return;
        }
        
        // Check Handle Hits
        if (selectedBoxIndex !== -1) {
            const b = boxes[selectedBoxIndex];
            if (!b.locked) {
                const handleSize = 14;
                const handles = [
                    { x: b.x1, y: b.y1 }, { x: b.x2, y: b.y1 },
                    { x: b.x2, y: b.y2 }, { x: b.x1, y: b.y2 }
                ];
                
                for (let hIdx = 0; hIdx < handles.length; hIdx++) {
                    if (Math.abs(mx - handles[hIdx].x) <= handleSize && Math.abs(my - handles[hIdx].y) <= handleSize) {
                        isResizingHandle = hIdx;
                        dragStartX = mx; dragStartY = my;
                        initialBoxCoords = { ...b };
                        return;
                    }
                }
            }
        }
        
        // Check Box Click / Select
        const hitIdx = boxes.findIndex(b => mx >= b.x1 && mx <= b.x2 && my >= b.y1 && my <= b.y2);
        if (hitIdx !== -1) {
            selectedBoxIndex = hitIdx;
            if (!boxes[hitIdx].locked) {
                isDraggingBox = true;
                dragStartX = mx; dragStartY = my;
                initialBoxCoords = { ...boxes[hitIdx] };
            }
        } else {
            // Start Drawing New Box
            isDrawing = true;
            dragStartX = mx; dragStartY = my;
            boxes.push({
                x1: mx, y1: my, x2: mx, y2: my,
                z_index: boxes.length, type: 'rectangle', locked: false, visible: true, label: ''
            });
            selectedBoxIndex = boxes.length - 1;
        }
        
        drawCanvas();
        updateLayerStack();
    });

    canvas.addEventListener('mousemove', (e) => {
        if (!isDrawing && !isDraggingBox && isResizingHandle === -1) return;
        
        const rect = canvas.getBoundingClientRect();
        const scaleX = canvas.width / rect.width;
        const scaleY = canvas.height / rect.height;
        
        const mx = (e.clientX - rect.left) * scaleX;
        const my = (e.clientY - rect.top) * scaleY;
        
        const boxes = getBoxesForCurrentPage();
        const b = boxes[selectedBoxIndex];
        if (!b) return;
        
        if (isDrawing) {
            b.x1 = Math.min(dragStartX, mx);
            b.y1 = Math.min(dragStartY, my);
            b.x2 = Math.max(dragStartX, mx);
            b.y2 = Math.max(dragStartY, my);
        } else if (isDraggingBox && initialBoxCoords) {
            const dx = mx - dragStartX;
            const dy = my - dragStartY;
            
            const rawBox = {
                x1: initialBoxCoords.x1 + dx,
                y1: initialBoxCoords.y1 + dy,
                x2: initialBoxCoords.x2 + dx,
                y2: initialBoxCoords.y2 + dy
            };
            
            const snapped = computeCanvaSnapping(rawBox, selectedBoxIndex);
            b.x1 = Math.max(0, snapped.x1);
            b.y1 = Math.max(0, snapped.y1);
            b.x2 = Math.min(canvas.width, snapped.x2);
            b.y2 = Math.min(canvas.height, snapped.y2);
        } else if (isResizingHandle !== -1 && initialBoxCoords) {
            let rawBox = { ...b };
            if (isResizingHandle === 0) { rawBox.x1 = mx; rawBox.y1 = my; }
            else if (isResizingHandle === 1) { rawBox.x2 = mx; rawBox.y1 = my; }
            else if (isResizingHandle === 2) { rawBox.x2 = mx; rawBox.y2 = my; }
            else if (isResizingHandle === 3) { rawBox.x1 = mx; rawBox.y2 = my; }
            
            const snapped = computeCanvaSnapping(rawBox, selectedBoxIndex);
            b.x1 = Math.min(snapped.x1, snapped.x2 - 10);
            b.y1 = Math.min(snapped.y1, snapped.y2 - 10);
            b.x2 = Math.max(snapped.x2, snapped.x1 + 10);
            b.y2 = Math.max(snapped.y2, snapped.y1 + 10);
        }
        
        drawCanvas();
    });

    window.addEventListener('mouseup', () => {
        isDrawing = false;
        isDraggingBox = false;
        isResizingHandle = -1;
        activeAlignmentGuides = [];
        drawCanvas();
    });

    canvas.addEventListener('contextmenu', e => e.preventDefault());
}

function updateLayerStack() {
    const boxes = getBoxesForCurrentPage();
    renderLayerList(
        boxes,
        selectedBoxIndex,
        (idx) => { selectedBoxIndex = idx; drawCanvas(); },
        (idx) => { boxes[idx].locked = !boxes[idx].locked; drawCanvas(); },
        (idx) => { boxes[idx].visible = !boxes[idx].visible; drawCanvas(); },
        (idx) => { boxes.splice(idx, 1); selectedBoxIndex = -1; drawCanvas(); updateLayerStack(); }
    );
}

function addFullPageBox() {
    const boxes = getBoxesForCurrentPage();
    boxes.length = 0;
    boxes.push({
        x1: 0, y1: 0, x2: canvas.width, y2: canvas.height,
        z_index: 0, type: 'rectangle', locked: false, visible: true, label: 'full_page'
    });
    selectedBoxIndex = 0;
    drawCanvas();
    updateLayerStack();
}

function prevPage() {
    if (currentPageIndex > 0) {
        currentPageIndex--;
        selectedBoxIndex = -1;
        renderCurrentPage();
    }
}

function nextPage() {
    if (currentPageIndex < pagesList.length - 1) {
        currentPageIndex++;
        selectedBoxIndex = -1;
        renderCurrentPage();
    }
}

async function saveAndRecrop() {
    const stem = pagesList[currentPageIndex].stem;
    const res = await fetch('/api/save-boxes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chapter: activeChapter, boxes: pageBoxesMap, rtl: isRtl })
    });
    
    if (res.ok) {
        showToast("Saved & Re-Cropped!");
    }
}

async function triggerCropExecution() {
    const modal = document.getElementById('progress-modal');
    const engine = document.getElementById('engine-select').value;
    
    if (modal) modal.classList.add('active');
    
    await fetch('/api/start-batch-crop', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chapter: activeChapter, scope: 'chapter', engine: engine, rtl: isRtl })
    });
    
    pollProgress();
}

async function pollProgress() {
    const res = await fetch('/api/crop-progress');
    const data = await res.json();
    
    document.getElementById('modal-msg').innerText = data.message || 'Processing...';
    document.getElementById('modal-counter').innerText = `${data.current} / ${data.total} Pages`;
    
    const pct = data.total > 0 ? (data.current / data.total) * 100 : 0;
    document.getElementById('modal-bar').style.width = `${pct}%`;
    
    if (data.running) {
        setTimeout(pollProgress, 600);
    } else {
        setTimeout(() => {
            document.getElementById('progress-modal').classList.remove('active');
            loadPageData(activeChapter);
        }, 500);
    }
}

function showToast(msg) {
    const toast = document.getElementById('toast');
    if (!toast) return;
    toast.innerText = msg;
    toast.style.opacity = '1';
    setTimeout(() => { toast.style.opacity = '0'; }, 2000);
}

function switchChapter(ch) {
    loadPageData(ch);
}

function updateRtl(val) {
    isRtl = val;
}

function finishAndContinue() {
    fetch('/api/shutdown', { method: 'POST' }).then(() => {
        window.close();
    });
}

// Global Keyboard Shortcuts
window.addEventListener('keydown', (e) => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
    
    if (e.key === 'a' || e.key === 'A' || e.key === 'ArrowLeft') prevPage();
    if (e.key === 'd' || e.key === 'D' || e.key === 'ArrowRight') nextPage();
    if (e.key === 'f' || e.key === 'F') addFullPageBox();
    if (e.key === 'Delete' && selectedBoxIndex !== -1) {
        const boxes = getBoxesForCurrentPage();
        boxes.splice(selectedBoxIndex, 1);
        selectedBoxIndex = -1;
        drawCanvas();
        updateLayerStack();
    }
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        saveAndRecrop();
    }
});

document.addEventListener('DOMContentLoaded', initCropEditor);