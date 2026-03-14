/**
 * Lexora API Client
 * Shared fetch wrapper for all frontend pages.
 */

const API_BASE = "http://localhost:8000";


async function processPDF(file) {

    const formData = new FormData();
    formData.append("file", file);

    const res = await fetch(`${API_BASE}/v1/process-pdf`, {
        method: "POST",
        body: formData
    });

    if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to process PDF");
    }

    return res.json();
}


/**
 * Process a PDF with real-time progress updates via SSE.
 * @param {File}     file        The PDF file to upload.
 * @param {Function} onProgress  Called with (step, label) for each pipeline stage.
 * @returns {Promise<Object>}    The final result JSON (same shape as processPDF).
 */
async function processPDFWithProgress(file, onProgress) {

    const formData = new FormData();
    formData.append("file", file);

    const res = await fetch(`${API_BASE}/v1/process-pdf-stream`, {
        method: "POST",
        body: formData
    });

    if (!res.ok) {
        let detail = "Failed to process PDF";
        try { const err = await res.json(); detail = err.detail || detail; } catch (_) {}
        throw new Error(detail);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let finalResult = null;

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // SSE events are separated by double newlines
        const parts = buffer.split("\n\n");
        buffer = parts.pop(); // last part may be incomplete

        for (const part of parts) {
            if (!part.trim()) continue;

            const lines = part.split("\n");
            let eventType = "";
            let data = "";

            for (const line of lines) {
                if (line.startsWith("event: ")) eventType = line.slice(7);
                else if (line.startsWith("data: "))  data = line.slice(6);
            }

            if (eventType === "progress" && onProgress) {
                const payload = JSON.parse(data);
                onProgress(payload.step, payload.label);
            } else if (eventType === "result") {
                finalResult = JSON.parse(data);
            } else if (eventType === "error") {
                const payload = JSON.parse(data);
                throw new Error(payload.detail || "Pipeline error");
            }
        }
    }

    if (!finalResult) throw new Error("Stream ended without a result");
    return finalResult;
}


async function analyzeText(text) {

    const res = await fetch(`${API_BASE}/v1/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text })
    });

    if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to analyze text");
    }

    return res.json();
}


async function transformText(text) {

    const res = await fetch(`${API_BASE}/v1/transform`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text })
    });

    if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to transform text");
    }

    return res.json();
}
