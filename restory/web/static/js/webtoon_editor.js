/* restory — Webtoon Strip Cut Line Editor */

let activeChapter = "01";
let webtoonData = { canvas_width: 800, total_height: 0, cuts: [0] };
let pagesList = [];

async function initWebtoonEditor() {
    const res = await fetch('/api/chapter-data');
    const data = await res.json();
    
    const select = document.getElementById('chapter-select');
    if (select) {
        select.innerHTML = '';
        (data.chapters || []).forEach(ch => {
            const opt = document.createElement('option');
            opt.value = ch;
            opt.innerText = `Chapter ${ch}`;
            if (ch === data.active_chapter) opt.selected = true;
            select.appendChild(opt);
        });
    }
    
    await loadWebtoonData(data.active_chapter || "01");
}

async function loadWebtoonData(ch) {
    activeChapter = ch;
    const res = await fetch(`/api/webtoon-data?chapter=${ch}`);
    const data = await res.json();
    
    pagesList = data.pages || [];
    webtoonData = data.webtoon_data || { cuts: [0] };
    
    renderStripCanvas();
}

function renderStripCanvas() {
    const container = document.getElementById('canvas-container');
    if (!container) return;
    
    container.innerHTML = '';
    const vScroll = new VirtualStripContainer(container, pagesList, activeChapter);
    vScroll.renderAllPages();
    
    // Render Horizontal Cut Markers
    const cuts = webtoonData.cuts || [];
    document.getElementById('cuts-counter').innerText = `${Math.max(0, cuts.length - 1)} Panels`;
    
    cuts.forEach((cutY, idx) => {
        if (idx === 0 || idx === cuts.length - 1) return; // Skip top & bottom boundaries
        
        const line = document.createElement('div');
        line.className = 'cut-line-marker';
        line.style.top = `${cutY}px`;
        
        const handle = document.createElement('div');
        handle.className = 'cut-handle';
        handle.innerText = `Cut ${idx}`;
        line.appendChild(handle);
        
        makeCutDraggable(line, idx);
        container.appendChild(line);
    });
}

function makeCutDraggable(lineEl, cutIndex) {
    let startY = 0, initialTop = 0;
    
    lineEl.addEventListener('mousedown', (e) => {
        startY = e.clientY;
        initialTop = webtoonData.cuts[cutIndex];
        
        const onMouseMove = (moveEvt) => {
            const dy = moveEvt.clientY - startY;
            const newY = Math.max(0, initialTop + dy);
            webtoonData.cuts[cutIndex] = newY;
            lineEl.style.top = `${newY}px`;
        };
        
        const onMouseUp = () => {
            window.removeEventListener('mousemove', onMouseMove);
            window.removeEventListener('mouseup', onMouseUp);
            webtoonData.cuts.sort((a, b) => a - b);
        };
        
        window.addEventListener('mousemove', onMouseMove);
        window.addEventListener('mouseup', onMouseUp);
    });
}

function addCutAtCenter() {
    const viewport = document.getElementById('viewport');
    const scrollY = viewport ? viewport.scrollTop + 300 : 500;
    
    webtoonData.cuts.push(Math.round(scrollY));
    webtoonData.cuts.sort((a, b) => a - b);
    renderStripCanvas();
}

async function saveWebtoon() {
    const res = await fetch('/api/save-webtoon', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chapter: activeChapter, webtoon_data: webtoonData })
    });
    
    if (res.ok) {
        showToast("Webtoon Panels Saved!");
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
    loadWebtoonData(ch);
}

function finishAndContinue() {
    fetch('/api/shutdown', { method: 'POST' }).then(() => {
        window.close();
    });
}

document.addEventListener('DOMContentLoaded', initWebtoonEditor);