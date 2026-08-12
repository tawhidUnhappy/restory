/**
 * restory.telemetry — Hardware status and system readiness banner fetcher.
 */

async function initTelemetry() {
    try {
        let res = await fetch("/api/telemetry");
        if (!res.ok) return;
        let data = await res.json();
        let gpu = data.gpu || {};

        let bannerEl = document.getElementById("telemetry-gpu");
        if (bannerEl) {
            if (gpu.cuda) {
                bannerEl.textContent = `GPU: CUDA (${gpu.device_name || 'NVIDIA'})`;
            } else if (gpu.backend === "mps") {
                bannerEl.textContent = "GPU: Apple Silicon MPS";
            } else {
                bannerEl.textContent = "Hardware: CPU Mode";
            }
        }
    } catch (err) {
        console.warn("Telemetry fetch failed:", err);
    }
}

document.addEventListener("DOMContentLoaded", initTelemetry);