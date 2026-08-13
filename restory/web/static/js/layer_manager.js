/**
 * restory.web.static.js.layer_manager — Layer stack sidebar manager.
 */

function renderLayerStack(boxes, selectedIndex, callbacks) {
    const listEl = document.getElementById('layer-list');
    if (!listEl) return;
    listEl.innerHTML = '';

    if (!boxes || boxes.length === 0) {
        listEl.innerHTML = '<li style="padding:10px; color:#94a3b8; font-size:0.8rem; text-align:center;">No panel layers on page.</li>';
        return;
    }

    boxes.forEach((box, idx) => {
        const li = document.createElement('li');
        li.className = `layer-item ${idx === selectedIndex ? 'selected' : ''}`;
        
        const w = Math.round(Math.abs(box.x2 - box.x1));
        const h = Math.round(Math.abs(box.y2 - box.y1));
        const label = box.label ? box.label : `Panel #${idx + 1}`;

        li.innerHTML = `
            <span><strong>#${idx + 1}</strong> ${label} <small>(${w}x${h})</small></span>
            <div class="layer-controls">
                <button class="layer-btn ${box.visible ? 'active' : ''}" title="Toggle Visibility" data-action="visible">&eye;</button>
                <button class="layer-btn ${box.locked ? 'active' : ''}" title="Toggle Lock" data-action="lock">&#128274;</button>
                <button class="layer-btn" title="Delete Layer" data-action="delete" style="color:#ef4444;">&times;</button>
            </div>
        `;

        li.addEventListener('click', (e) => {
            const btn = e.target.closest('.layer-btn');
            if (btn) {
                e.stopPropagation();
                const action = btn.dataset.action;
                if (action === 'visible' && callbacks.onToggleVisible) callbacks.onToggleVisible(idx);
                if (action === 'lock' && callbacks.onToggleLock) callbacks.onToggleLock(idx);
                if (action === 'delete' && callbacks.onDelete) callbacks.onDelete(idx);
            } else {
                if (callbacks.onSelect) callbacks.onSelect(idx);
            }
        });

        listEl.appendChild(li);
    });
}