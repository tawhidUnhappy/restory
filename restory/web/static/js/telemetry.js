/* restory — System Telemetry & GPU Banner Monitor */

async function fetchTelemetry() {
    try {
        const res = await fetch('/api/telemetry');
        if (!res.ok) return;
        const data = await res.json();
        
        const gpuSpan = document.getElementById('telemetry-gpu');
        if (gpuSpan && data.gpu) {
            const backend = (data.gpu.backend || 'CPU').toUpperCase();
            const device = data.gpu.device_name ? ` (${data.gpu.device_name})` : '';
            gpuSpan.innerText = `GPU: ${backend}${device}`;
        }
    } catch (e) {
        console.warn('Telemetry fetch error:', e);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    fetchTelemetry();
});