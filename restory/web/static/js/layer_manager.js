/**
 * restory.layer_manager — Z-Index stacking, visibility, and lock controls for panel boxes.
 */

function renderLayerStack(boxes, selectedIdx, callbacks) {
    let listEl = document.getElementById("layer-list");
    if (!listEl) return;
    listEl.innerHTML = "";

    boxes.forEach((b, idx) => {
        let li = document.createElement("li");
        li.className = `layer-item ${idx === selectedIdx ? 'selected' : ''}`;

        let isLocked = b.locked || false;
        let isVisible = b.visible !== false;

        li.innerHTML = `
            <span><strong>#${idx + 1}</strong> ${b.label || 'Panel'} (${Math.round(b.x2 - b.x1)}x${Math.round(b.y2 - b.y1)})</span>
            <div class="layer-controls">
                <button class="layer-btn ${isVisible ? 'active' : ''}" title="Toggle Visibility" onclick="event.stopPropagation(); window.toggleLayerVisible(${idx})">${isVisible ? '👁' : '🙈'}</button>
                <button class="layer-btn ${isLocked ? 'active' : ''}" title="Toggle Lock" onclick="event.stopPropagation(); window.toggleLayerLock(${idx})">${isLocked ? '🔒' : '🔓'}</button>
                <button class="layer-btn" title="Delete" style="color:var(--danger)" onclick="event.stopPropagation(); window.deleteLayer(${idx})">🗑</button>
            </div>
        `;

        li.onclick = () => callbacks.onSelect(idx);
        listEl.appendChild(li);
    });
}