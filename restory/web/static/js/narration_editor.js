/* restory — Side-by-Side Narration Script Editor with 1-Click DeepSeek-OCR 2 */

let activeChapter = "01";
let entriesList = [];
let castList = [];

async function initNarrationEditor() {
    const res = await fetch('/api/chapters');
    const data = await res.json();
    
    const select = document.getElementById('chapter-select');
    if (select) {
        select.innerHTML = '';
        (data.chapters || []).forEach(ch => {
            const opt = document.createElement('option');
            opt.value = ch;
            opt.innerText = `Chapter ${ch}`;
            if (ch === data.active) opt.selected = true;
            select.appendChild(opt);
        });
    }
    
    await loadNarrationData(data.active || "01");
}

async function loadNarrationData(ch) {
    activeChapter = ch;
    const res = await fetch(`/api/narration-data?chapter=${ch}`);
    const data = await res.json();
    
    entriesList = data.entries || [];
    castList = data.cast || [];
    
    renderScriptCards();
}

function renderScriptCards() {
    const container = document.getElementById('card-list');
    if (!container) return;
    
    container.innerHTML = '';
    let narratedCount = 0;
    
    entriesList.forEach((entry, idx) => {
        if (entry.narration && entry.narration.trim()) {
            narratedCount++;
        }
        
        const card = document.createElement('div');
        card.className = `entry-card ${!entry.narration ? 'blank-entry' : ''}`;
        
        // 1. Panel Preview & OCR Trigger
        const imgCol = document.createElement('div');
        imgCol.className = 'image-container';
        
        const img = document.createElement('img');
        img.className = 'panel-preview';
        img.src = `/image/panels/${activeChapter}/${entry.image}`;
        
        const ocrBtn = document.createElement('button');
        ocrBtn.className = 'btn-ocr';
        ocrBtn.innerHTML = '🔍 DeepSeek-OCR 2 Speech';
        ocrBtn.onclick = () => triggerPanelOCR(entry.image, idx);
        
        imgCol.appendChild(img);
        imgCol.appendChild(ocrBtn);
        
        // 2. Script Writing Container
        const scriptCol = document.createElement('div');
        scriptCol.className = 'script-container';
        
        const headerRow = document.createElement('div');
        headerRow.className = 'card-header-row';
        
        const label = document.createElement('span');
        label.className = 'panel-label';
        label.innerText = `Panel ${idx + 1}: ${entry.image}`;
        
        const statusTag = document.createElement('span');
        statusTag.className = `status-tag ${entry.narration ? 'tag-ok' : 'tag-blank'}`;
        statusTag.innerText = entry.narration ? 'STORY' : 'BLANK / COVER';
        
        headerRow.appendChild(label);
        headerRow.appendChild(statusTag);
        
        // OCR Output Box
        const ocrBox = document.createElement('div');
        ocrBox.className = 'ocr-box';
        ocrBox.id = `ocr-box-${idx}`;
        ocrBox.style.display = entry.ocr_text ? 'flex' : 'none';
        ocrBox.innerHTML = `
            <div class="ocr-title">
                <span>💬 Dialogue Reference</span>
                <span style="cursor:pointer;" onclick="copyOcrToText(${idx})">📋 Use Text</span>
            </div>
            <div id="ocr-val-${idx}">${entry.ocr_text || ''}</div>
        `;
        
        // Textarea
        const textarea = document.createElement('textarea');
        textarea.placeholder = "Write narration line describing panel action (leave blank for covers/credits)...";
        textarea.value = entry.narration || '';
        textarea.oninput = (e) => {
            entry.narration = e.target.value;
            statusTag.className = `status-tag ${entry.narration ? 'tag-ok' : 'tag-blank'}`;
            statusTag.innerText = entry.narration ? 'STORY' : 'BLANK / COVER';
            updateStatsCounter();
        };
        
        // Meta Controls Row
        const metaRow = document.createElement('div');
        metaRow.className = 'meta-row';
        
        const stem = entry.image.split('.')[0];
        const playBtn = document.createElement('button');
        playBtn.innerText = '🔊 Preview Voice Take';
        playBtn.onclick = () => previewAudio(stem);
        
        metaRow.appendChild(playBtn);
        
        scriptCol.appendChild(headerRow);
        scriptCol.appendChild(ocrBox);
        scriptCol.appendChild(textarea);
        scriptCol.appendChild(metaRow);
        
        card.appendChild(imgCol);
        card.appendChild(scriptCol);
        container.appendChild(card);
    });
    
    updateStatsCounter();
}

async function triggerPanelOCR(filename, idx) {
    const box = document.getElementById(`ocr-box-${idx}`);
    const valEl = document.getElementById(`ocr-val-${idx}`);
    if (box) box.style.display = 'flex';
    if (valEl) valEl.innerText = "Running DeepSeek-OCR 2 Vausal Flow Inference...";
    
    const res = await fetch('/api/ocr-panel', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chapter: activeChapter, filename: filename })
    });
    
    const data = await res.json();
    const extracted = data.ocr_text || "[OCR]: Speech box in panel";
    
    entriesList[idx].ocr_text = extracted;
    if (valEl) valEl.innerText = extracted;
}

function copyOcrToText(idx) {
    const ocrVal = entriesList[idx].ocr_text;
    if (ocrVal) {
        entriesList[idx].narration = ocrVal;
        renderScriptCards();
    }
}

async function previewAudio(stem) {
    const res = await fetch('/api/preview-tts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chapter: activeChapter, stem: stem })
    });
    
    const data = await res.json();
    if (data.audio_url) {
        const audio = new Audio(data.audio_url);
        audio.play();
    }
}

function updateStatsCounter() {
    const nonContainer = entriesList.filter(e => e.narration && e.narration.trim()).length;
    const counter = document.getElementById('stats-counter');
    if (counter) {
        counter.innerText = `${nonContainer} / ${entriesList.length} Narrated`;
    }
}

async function saveNarration() {
    const res = await fetch('/api/save-narration', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chapter: activeChapter, entries: entriesList })
    });
    
    if (res.ok) {
        showToast("Saved narration.json!");
    }
}

async function runNarrationCheck() {
    const res = await fetch('/api/narration-check', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chapter: activeChapter })
    });
    
    const data = await res.json();
    if (data.ok) {
        showToast("Contract Rules Passed!");
    } else {
        alert(`Validation Error:\n${data.error}`);
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
    loadNarrationData(ch);
}

function finishAndContinue() {
    fetch('/api/shutdown', { method: 'POST' }).then(() => {
        window.close();
    });
}

// Key Shortcut (Ctrl+S)
window.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        saveNarration();
    }
});

document.addEventListener('DOMContentLoaded', initNarrationEditor);