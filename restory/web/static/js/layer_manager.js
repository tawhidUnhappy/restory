/* restory — Panel Layer Stack & Z-Index Manager */

function renderLayerList(boxes, selectedIndex, onSelect, onToggleLock, onToggleVisible, onDelete) {
    const listEl = document.getElementById('layer-list');
    if (!listEl) return;
    
    listEl.innerHTML = '';
    
    boxes.forEach((box, idx) => {
        const li = document.createElement('li');
        li.className = `layer-item ${idx === selectedIndex ? 'selected' : ''}`;
        
        const label = document.createElement('span');
        label.innerText = `Panel ${idx + 1} (${box.x2 - box.x1}×${box.y2 - box.y1})`;
        label.onclick = () => onSelect(idx);
        
        const controls = document.createElement('div');
        controls.className = 'layer-controls';
        
        const lockBtn = document.createElement('button');
        lockBtn.className = `layer-btn ${box.locked ? 'active' : ''}`;
        lockBtn.innerHTML = box.locked ? '🔒' : '🔓';
        lockBtn.title = box.locked ? 'Unlock Layer' : 'Lock Layer';
        lockBtn.onclick = (e) => { e.stopPropagation(); onToggleLock(idx); };
        
        const visBtn = document.createElement('button');
        visBtn.className = `layer-btn ${box.visible ? 'active' : ''}`;
        visBtn.innerHTML = box.visible ? '👁️' : '🙈';
        visBtn.title = box.visible ? 'Hide Layer' : 'Show Layer';
        visBtn.onclick = (e) => { e.stopPropagation(); onToggleVisible(idx); };
        
        const delBtn = document.createElement('button');
        delBtn.className = 'layer-btn';
        delBtn.innerHTML = '✕';
        delBtn.title = 'Delete Layer';
        delBtn.onclick = (e) => { e.stopPropagation(); onDelete(idx); };
        
        controls.appendChild(lockBtn);
        controls.appendChild(visBtn);
        controls.appendChild(delBtn);
        
        li.appendChild(label);
        li.appendChild(controls);
        listEl.appendChild(li);
    });
}