/**
 * restory.web.static.js.telemetry — Telemetry polling script.
 */

async function pollTelemetry() {
    try {
        const resp = await fetch('/api/telemetry');
        if (!resp.ok) return;
        const data = await resp.json();
        const gpuEl = document.getElementById('telemetry-gpu');
        if (gpuEl && data.gpu) {
            const name = data.gpu.device_name || data.gpu.backend || 'CPU';
            gpuEl.textContent = `GPU: ${name}`;
        }
    } catch (err) {
        console.warn('Telemetry fetch failed:', err);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    pollTelemetry();
    setInterval(pollTelemetry, 15000);
});