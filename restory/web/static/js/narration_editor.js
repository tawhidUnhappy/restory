/**
 * restory.web.static.js.narration_editor — Side-by-Side Narration Editor Script.
 */

let activeChapter = "01";
let entriesData = [];

async function initNarrationEditor() {
    await fetchChapters();
    await fetchNarrationData();
    setupHotkeys();
}

async function fetchChapters() {
    try {
        const res = await fetch('/api/chapters');
        const data = await res.json();
        const select = document.getElementById('chapter-select');
        if (select) {
            select.innerHTML = '';
            (data.chapters || []).forEach(ch => {
                const opt = document.createElement('option');
                opt.value = ch;
                opt.textContent = `Chapter ${ch}`;
                if (ch === data.active) opt.selected = true;
                select.appendChild(opt);
            });
            activeChapter = data.active;
        }
    } catch (e) {
        console.error('Failed to load chapters:', e);
    }
}

async function fetchNarrationData() {
    try {
        const res = await fetch(`/api/narration-data?chapter=${activeChapter}`);
        const data = await res.json();
        entriesData = data.entries || [];
        renderCards();
    } catch (e) {
        console.error('Failed to load narration data:', e);
    }
}

function renderCards() {
    const container = document.getElementById('card-list');
    if (!container) return;
    container.innerHTML = '';

    let narratedCount = 0;

    entriesData.forEach((entry, idx) => {
        if (entry.narration && entry.narration.trim()) narratedCount++;

        const card = document.createElement('div');
        const isBlank = !entry.narration || !entry.narration.trim();
        card.className = `entry-card ${isBlank ? 'blank-entry' : ''}`;

        card.innerHTML = `
            <div class="image-container">
                <img class="panel-preview" src="/image/panels/${activeChapter}/${entry.image}" alt="${entry.image}" />
            </div>
            <div class="script-container">
                <div class="card-header-row">
                    <span class="panel-label">Panel #${idx + 1}: ${entry.image}</span>
                    <span class="status-tag ${isBlank ? 'tag-blank' : 'tag-ok'}">
                        ${isBlank ? 'BLANK / COVER' : 'NARRATED'}
                    </span>
                </div>
                <textarea 
                    placeholder="Enter narration text for panel #${idx + 1} (leave blank for covers/credits)..."
                    data-index="${idx}"
                    oninput="handleInput(this)"
                >${entry.narration || ''}</textarea>
                <div class="meta-row">
                    <div class="field-group">
                        <label>Beat ID:</label>
                        <input type="text" value="${entry.beat_id || ''}" onchange="updateBeatId(${idx}, this.value)" />
                    </div>
                    <div class="field-group">
                        <label>Pause After (ms):</label>
                        <input type="number" value="${entry.pause_after_ms || 0}" step="100" style="width:80px;" onchange="updatePause(${idx}, this.value)" />
                    </div>
                    <button style="padding: 4px 10px; font-size: 0.78rem;" onclick="previewTTS('${entry.image}')">&#9654; Preview Audio</button>
                </div>
            </div>
        `;
        container.appendChild(card);
    });

    const stats = document.getElementById('stats-counter');
    if (stats) {
        stats.textContent = `${narratedCount} / ${entriesData.length} Narrated`;
    }
}

function handleInput(textarea) {
    const idx = parseInt(textarea.dataset.index, 10);
    entriesData[idx].narration = textarea.value;

    const card = textarea.closest('.entry-card');
    const tag = card.querySelector('.status-tag');
    const isBlank = !textarea.value || !textarea.value.trim();

    if (isBlank) {
        card.classList.add('blank-entry');
        tag.className = 'status-tag tag-blank';
        tag.textContent = 'BLANK / COVER';
    } else {
        card.classList.remove('blank-entry');
        tag.className = 'status-tag tag-ok';
        tag.textContent = 'NARRATED';
    }

    let narratedCount = entriesData.filter(e => e.narration && e.narration.trim()).length;
    const stats = document.getElementById('stats-counter');
    if (stats) stats.textContent = `${narratedCount} / ${entriesData.length} Narrated`;
}

function updateBeatId(idx, val) {
    entriesData[idx].beat_id = val;
}

function updatePause(idx, val) {
    entriesData[idx].pause_after_ms = parseInt(val, 10) || 0;
}

async function previewTTS(imgName) {
    const stem = imgName.substring(0, imgName.lastIndexOf('.')) || imgName;
    showToast('Generating draft audio preview...');
    try {
        const res = await fetch('/api/preview-tts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ chapter: activeChapter, stem: stem })
        });
        const data = await res.json();
        if (data.status === 'ok' && data.audio_url) {
            const audio = new Audio(data.audio_url + '?t=' + Date.now());
            audio.play();
        }
    } catch (e) {
        console.error('Preview failed:', e);
    }
}

async function switchChapter(ch) {
    activeChapter = ch;
    await fetchNarrationData();
}

async function saveNarration() {
    try {
        const res = await fetch('/api/save-narration', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ chapter: activeChapter, entries: entriesData })
        });
        const data = await res.json();
        if (data.status === 'ok') showToast('Saved narration.json!');
    } catch (e) {
        console.error('Save failed:', e);
    }
}

async function runNarrationCheck() {
    try {
        const res = await fetch('/api/narration-check', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ chapter: activeChapter })
        });
        const data = await res.json();
        if (data.ok) {
            showToast('Contract Check PASSED!');
        } else {
            alert('Narration Check Failed: ' + data.error);
        }
    } catch (e) {
        console.error('Check failed:', e);
    }
}

async function finishAndContinue() {
    await saveNarration();
    try {
        await fetch('/api/shutdown', { method: 'POST' });
    } catch (e) {}
    window.close();
}

function setupHotkeys() {
    window.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
            e.preventDefault();
            saveNarration();
        }
    });
}

function showToast(msg) {
    const toast = document.getElementById('toast');
    if (!toast) return;
    toast.textContent = msg;
    toast.style.opacity = '1';
    setTimeout(() => { toast.style.opacity = '0'; }, 2200);
}

document.addEventListener('DOMContentLoaded', initNarrationEditor);