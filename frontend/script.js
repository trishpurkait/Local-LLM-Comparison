let selectedModels = [];
let prompts = [];
let currentRunId = null;

let latencyChart = null;
let tokensChart = null;
let wordsChart = null;
let successChart = null;

/* ============================================
   MODEL LOADING
   ============================================ */
async function loadModels() {
    const modelList = document.getElementById("model-list");
    modelList.innerHTML = `<div class="empty-state"><span class="empty-icon mono">⟳</span><p>Scanning Ollama for installed models...</p></div>`;

    try {
        const response = await fetch("/models");
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Failed to load models.");
        }

        if (!data.models || data.models.length === 0) {
            modelList.innerHTML = `<div class="error-box">No Ollama models found. Pull at least 2 models using <code>ollama pull &lt;model&gt;</code></div>`;
            return;
        }

        selectedModels = [];
        updateSelectedCount();

        modelList.innerHTML = "";
        modelList.className = "model-grid";

        data.models.forEach(model => {
            const div = document.createElement("div");
            div.className = "model-item";
            div.dataset.model = model;

            div.innerHTML = `
                <label>
                    <input type="checkbox" value="${escapeHtml(model)}" onchange="toggleModel(this)">
                    ${escapeHtml(model)}
                </label>
            `;

            modelList.appendChild(div);
        });

    } catch (error) {
        modelList.innerHTML = `<div class="error-box">${escapeHtml(error.message)}</div>`;
    }
}

function toggleModel(checkbox) {
    const model = checkbox.value;
    const item = checkbox.closest(".model-item");

    if (checkbox.checked) {
        if (selectedModels.length >= 5) {
            checkbox.checked = false;
            showToast("You can select up to 5 models only.");
            return;
        }
        selectedModels.push(model);
        item.classList.add("selected");
    } else {
        selectedModels = selectedModels.filter(m => m !== model);
        item.classList.remove("selected");
    }

    updateSelectedCount();
}

function updateSelectedCount() {
    const el = document.getElementById("selected-count");
    el.textContent = `${selectedModels.length} selected`;
}

/* ============================================
   PROMPT MANAGEMENT
   ============================================ */
async function loadDefaultPrompts() {
    const promptList = document.getElementById("prompt-list");
    promptList.innerHTML = `<div class="empty-state"><span class="empty-icon mono">⟳</span><p>Loading default prompts...</p></div>`;

    try {
        const response = await fetch("/default-prompts");
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Failed to load default prompts.");
        }

        prompts = data.prompts;
        renderPrompts();

    } catch (error) {
        promptList.innerHTML = `<div class="error-box">${escapeHtml(error.message)}</div>`;
    }
}

function addCustomPrompt() {
    const textarea = document.getElementById("custom-prompt");
    const promptText = textarea.value.trim();

    if (!promptText) {
        showToast("Please enter a custom prompt first.");
        return;
    }

    prompts.push({ category: "custom", prompt: promptText });
    textarea.value = "";
    renderPrompts();
}

function removePrompt(index) {
    prompts.splice(index, 1);
    renderPrompts();
}

function renderPrompts() {
    const promptList = document.getElementById("prompt-list");
    promptList.innerHTML = "";

    if (prompts.length === 0) {
        promptList.innerHTML = `<div class="empty-state"><span class="empty-icon mono">[ ]</span><p>No prompts loaded yet.</p></div>`;
        return;
    }

    prompts.forEach((item, index) => {
        const div = document.createElement("div");
        div.className = "prompt-item";

        div.innerHTML = `
            <div class="prompt-content">
                <div class="prompt-category">${escapeHtml(item.category)}</div>
                <div class="prompt-text">${escapeHtml(item.prompt)}</div>
            </div>
            <button class="btn-danger" onclick="removePrompt(${index})">✕</button>
        `;

        promptList.appendChild(div);
    });
}

/* ============================================
   EVALUATION
   ============================================ */
async function runEvaluation() {
    const status = document.getElementById("status");
    const liveSection = document.getElementById("live-section");
    const liveResults = document.getElementById("live-results");
    const progressWrapper = document.getElementById("progress-wrapper");
    const progressFill = document.getElementById("progress-fill");
    const progressText = document.getElementById("progress-text");

    if (selectedModels.length < 2 || selectedModels.length > 5) {
        showToast("Please select between 2 and 5 models.");
        return;
    }

    if (prompts.length === 0) {
        showToast("Please add at least one prompt.");
        return;
    }

    hidePreviousResults();
    currentRunId = null;

    liveSection.classList.remove("hidden");
    progressWrapper.classList.remove("hidden");

    liveResults.innerHTML = "";
    progressFill.style.width = "0%";
    progressText.textContent = "0%";

    status.textContent = "Initializing evaluation...";

    try {
        const response = await fetch("/evaluate-stream", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                models: selectedModels,
                prompts: prompts,
                enable_quality_check: document.getElementById("enable-quality-check").checked
            })
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || "Evaluation failed.");
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            buffer = lines.pop();

            for (const line of lines) {
                if (!line.trim()) continue;
                const event = JSON.parse(line);
                handleStreamEvent(event);
            }
        }

    } catch (error) {
        status.textContent = error.message;
    }
}

function handleStreamEvent(event) {
    const status = document.getElementById("status");
    const progressFill = document.getElementById("progress-fill");
    const progressText = document.getElementById("progress-text");

    if (event.type === "start") {
        status.textContent = event.message;
        return;
    }

    if (event.type === "model_start") {
        status.textContent = `Evaluating ${event.model}...`;
        return;
    }

    if (event.type === "result") {
        const percent = event.progress_percent || 0;
        progressFill.style.width = `${percent}%`;
        progressText.textContent = `${percent}% completed`;
        renderLiveResult(event.data);
        return;
    }

    if (event.type === "model_unloaded") {
        status.textContent = event.message;
        return;
    }

    if (event.type === "warning") {
        status.textContent = event.message;
        return;
    }

    if (event.type === "judge_start") {
        status.textContent = `${event.message} Estimated NIM calls: ${event.estimated_nim_calls}`;
        return;
    }

    if (event.type === "judge_result") {
        const percent = event.progress_percent || 0;
        status.textContent = `Answer Quality Check running... ${percent}% completed`;
        progressFill.style.width = `${percent}%`;
        progressText.textContent = `Quality check: ${percent}% completed`;
        return;
    }

    if (event.type === "judge_summary") {
        status.textContent = "Answer Quality Check completed.";
        progressFill.style.width = "100%";
        progressText.textContent = "Quality check completed";
        return;
    }

    if (event.type === "summary") {
        currentRunId = event.data.run_id;
        status.textContent = `Evaluation completed. Run ID: ${event.data.run_id}`;

        renderRecommendation(event.data);
        renderQualitySection(event.data);
        renderSummaryTable(event.data);
        renderCharts(event.data);
        loadHistory();

        return;
    }
}

/* ============================================
   RENDER LIVE RESULT
   ============================================ */
function renderLiveResult(result) {
    const liveResults = document.getElementById("live-results");

    const box = document.createElement("div");
    box.className = "live-result";

    const statusClass = result.success ? "status-success" : "status-fail";
    const statusText = result.success ? "✓ Success" : "✗ Failed";

    box.innerHTML = `
        <div class="live-result-header">
            <span class="badge">${escapeHtml(result.model)} · ${escapeHtml(result.category)}</span>
            <span class="${statusClass}">${statusText}</span>
        </div>

        <p style="font-size:13px; color: var(--text-secondary); margin-bottom:10px;">
            <strong style="color:var(--text-dim); font-family:var(--font-mono); font-size:11px; text-transform:uppercase; letter-spacing:0.06em;">Prompt</strong><br>
            ${escapeHtml(result.prompt)}
        </p>

        <div class="metric-grid">
            <div class="metric-card">
                <strong>Total Time</strong>
                <span>${result.total_latency_seconds}s</span>
            </div>
            <div class="metric-card">
                <strong>Cold Start</strong>
                <span>${result.load_latency_seconds}s</span>
            </div>
            <div class="metric-card">
                <strong>Prompt Eval</strong>
                <span>${result.prompt_eval_latency_seconds}s</span>
            </div>
            <div class="metric-card">
                <strong>Generation</strong>
                <span>${result.generation_latency_seconds}s</span>
            </div>
            <div class="metric-card">
                <strong>Words/Sec</strong>
                <span>${result.words_per_second}</span>
            </div>
            <div class="metric-card">
                <strong>Tokens/Sec</strong>
                <span>${result.tokens_per_second}</span>
            </div>
            <div class="metric-card">
                <strong>Words</strong>
                <span>${result.word_count}</span>
            </div>
            <div class="metric-card">
                <strong>Characters</strong>
                <span>${result.character_count}</span>
            </div>
            <div class="metric-card">
                <strong>Output Tokens</strong>
                <span>${result.output_token_count}</span>
            </div>
        </div>

        ${result.error ? `<div class="error-box" style="margin-top:10px;"><strong>Error:</strong> ${escapeHtml(result.error)}</div>` : ""}

        <div class="live-result-response">${escapeHtml(result.response || "No response")}</div>
    `;

    liveResults.appendChild(box);
    box.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

/* ============================================
   RENDER RECOMMENDATION
   ============================================ */
function renderRecommendation(data) {
    const section = document.getElementById("recommendation-section");
    const recommendation = document.getElementById("recommendation");

    section.classList.remove("hidden");

    const fastestModel    = data.ranking.fastest_model || "N/A";
    const detailedModel   = data.ranking.most_detailed_model || "N/A";
    const reliableModel   = data.ranking.most_reliable_model || "N/A";
    const qualityModel    = data.ranking.best_quality_model || "N/A";
    const balancedModel   = data.ranking.best_balanced_model || "N/A";

    recommendation.innerHTML = `
        <div class="decision-grid">
            <div class="decision-card primary-decision">
                <strong>Best for Your System</strong>
                <span>${escapeHtml(balancedModel)}</span>
                <p>Best overall trade-off between speed, reliability, response detail, and quality.</p>
            </div>

            <div class="decision-card">
                <strong>Best Answer Quality</strong>
                <span>${escapeHtml(qualityModel)}</span>
                <p>Recommended when answer usefulness and correctness matter most.</p>
            </div>

            <div class="decision-card">
                <strong>Fastest Model</strong>
                <span>${escapeHtml(fastestModel)}</span>
                <p>Recommended when you care most about lower generation time.</p>
            </div>

            <div class="decision-card">
                <strong>Most Detailed</strong>
                <span>${escapeHtml(detailedModel)}</span>
                <p>Recommended when longer and more detailed responses matter.</p>
            </div>

            <div class="decision-card">
                <strong>Most Reliable</strong>
                <span>${escapeHtml(reliableModel)}</span>
                <p>Recommended when fewer failures and stable completion matter most.</p>
            </div>
        </div>

        <div class="recommendation-text">${escapeHtml(data.ranking.recommendation)}</div>

        <p class="table-note mono">Performance metrics are measured locally. Quality scores are produced by NVIDIA NIM when Answer Quality Check is enabled.</p>
    `;
}

/* ============================================
   RENDER QUALITY SECTION
   ============================================ */
function renderQualitySection(data) {
    const section = document.getElementById("quality-section");
    const qualitySummaryDiv = document.getElementById("quality-summary");
    const tbody = document.querySelector("#quality-table tbody");

    if (!data.enable_quality_check || !data.quality_summary || data.quality_summary.length === 0) {
        section.classList.add("hidden");
        return;
    }

    section.classList.remove("hidden");
    qualitySummaryDiv.innerHTML = "";
    tbody.innerHTML = "";

    const grid = document.createElement("div");
    grid.className = "quality-grid";

    data.quality_summary.forEach(item => {
        const card = document.createElement("div");
        card.className = "quality-card";

        card.innerHTML = `
            <strong>${escapeHtml(item.model)}</strong>
            <span>${item.average_overall_quality}/10</span>
            <p><strong>Best for:</strong> ${escapeHtml(item.best_for)}</p>
            <p>${escapeHtml(item.simple_summary)}</p>
            <p><strong>Strength:</strong> ${escapeHtml(item.strength)}</p>
            <p><strong>Weakness:</strong> ${escapeHtml(item.weakness)}</p>
        `;

        grid.appendChild(card);

        const row = document.createElement("tr");
        row.innerHTML = `
            <td>${escapeHtml(item.model)}</td>
            <td>${item.average_matches_question}</td>
            <td>${item.average_easy_to_understand}</td>
            <td>${item.average_covers_enough_detail}</td>
            <td>${item.average_factually_reliable}</td>
            <td>${item.average_follows_instructions}</td>
            <td>${item.average_overall_quality}</td>
        `;

        tbody.appendChild(row);
    });

    qualitySummaryDiv.appendChild(grid);
}

/* ============================================
   RENDER SUMMARY TABLE
   ============================================ */
function renderSummaryTable(data) {
    const section = document.getElementById("results-section");
    const tbody = document.querySelector("#summary-table tbody");

    section.classList.remove("hidden");
    tbody.innerHTML = "";

    data.summary.forEach(item => {
        const row = document.createElement("tr");
        row.innerHTML = `
            <td>${escapeHtml(item.model)}</td>
            <td>${Math.round(item.success_rate * 100)}%</td>
            <td>${item.average_generation_latency_seconds}s</td>
            <td>${item.total_generation_latency_seconds}s</td>
            <td>${item.total_load_latency_seconds}s</td>
            <td>${item.average_words_per_second}</td>
            <td>${item.average_tokens_per_second}</td>
            <td>${item.total_word_count}</td>
            <td>${item.failed_prompts}</td>
        `;
        tbody.appendChild(row);
    });
}

/* ============================================
   RENDER CHARTS
   ============================================ */
function renderCharts(data) {
    const chartSection = document.getElementById("chart-section");
    chartSection.classList.remove("hidden");

    const labels      = data.summary.map(i => i.model);
    const latencyData = data.summary.map(i => i.average_generation_latency_seconds);
    const tokensData  = data.summary.map(i => i.average_tokens_per_second);
    const wordsData   = data.summary.map(i => i.total_word_count);
    const successData = data.summary.map(i => Math.round(i.success_rate * 100));

    const accent  = "#e8ff47";
    const blue    = "#3b82f6";
    const green   = "#34d399";
    const orange  = "#fb923c";

    latencyChart = createOrUpdateChart(latencyChart, "latencyChart", "Avg Generation Latency (s)", labels, latencyData, accent);
    tokensChart  = createOrUpdateChart(tokensChart,  "tokensChart",  "Tokens/Sec", labels, tokensData, blue);
    wordsChart   = createOrUpdateChart(wordsChart,   "wordsChart",   "Total Words", labels, wordsData, green);
    successChart = createOrUpdateChart(successChart, "successChart", "Success Rate (%)", labels, successData, orange);
}

function createOrUpdateChart(existing, canvasId, label, labels, values, color) {
    if (existing) existing.destroy();

    const ctx = document.getElementById(canvasId).getContext("2d");

    return new Chart(ctx, {
        type: "bar",
        data: {
            labels,
            datasets: [{
                label,
                data: values,
                backgroundColor: color + "33",
                borderColor: color,
                borderWidth: 2,
                borderRadius: 6,
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    labels: {
                        color: "#8892a0",
                        font: { family: "'JetBrains Mono', monospace", size: 11 }
                    }
                }
            },
            scales: {
                x: {
                    ticks: {
                        color: "#8892a0",
                        font: { family: "'JetBrains Mono', monospace", size: 10 }
                    },
                    grid: { color: "#1e2329" }
                },
                y: {
                    beginAtZero: true,
                    ticks: {
                        color: "#8892a0",
                        font: { family: "'JetBrains Mono', monospace", size: 10 }
                    },
                    grid: { color: "#1e2329" }
                }
            }
        }
    });
}

/* ============================================
   HISTORY
   ============================================ */
async function loadHistory() {
    const historyList = document.getElementById("history-list");
    historyList.innerHTML = `<div class="empty-state"><span class="empty-icon mono">⟳</span><p>Loading history...</p></div>`;

    try {
        const response = await fetch("/history");
        const data = await response.json();

        if (!response.ok) throw new Error(data.detail || "Failed to load history.");

        renderHistory(data.runs || []);

    } catch (error) {
        historyList.innerHTML = `<div class="error-box">${escapeHtml(error.message)}</div>`;
    }
}

function renderHistory(runs) {
    const historyList = document.getElementById("history-list");

    if (!runs || runs.length === 0) {
        historyList.innerHTML = `<div class="empty-state"><span class="empty-icon mono">~</span><p>No evaluation history found.</p></div>`;
        return;
    }

    historyList.innerHTML = "";

    const grid = document.createElement("div");
    grid.className = "history-grid";

    runs.forEach(run => {
        const div = document.createElement("div");
        div.className = "history-item";

        const models = Array.isArray(run.models) ? run.models.join(", ") : "N/A";
        const bestModel = run.ranking?.best_balanced_model || "N/A";

        div.innerHTML = `
            <div class="history-meta">
                <strong>${escapeHtml(run.run_id || "Unknown Run")}</strong>
                <p>${escapeHtml(models)} · ${run.total_prompts || 0} prompts</p>
            </div>
            <div style="display:flex; align-items:center; gap:10px; flex-wrap:wrap;">
                <span class="history-best">⭐ ${escapeHtml(bestModel)}</span>
                <button class="btn-outline btn-sm" onclick="viewHistoryReport('${escapeHtml(run.run_id)}')">View ↗</button>
            </div>
        `;

        grid.appendChild(div);
    });

    historyList.appendChild(grid);
}

async function viewHistoryReport(runId) {
    const status = document.getElementById("status");

    try {
        const response = await fetch(`/results/${runId}`);
        const data = await response.json();

        if (!response.ok) throw new Error(data.detail || "Failed to load report.");

        currentRunId = data.run_id;
        status.textContent = `Loaded run: ${data.run_id}`;

        document.getElementById("live-section").classList.add("hidden");
        document.getElementById("progress-wrapper").classList.add("hidden");

        renderRecommendation(data);
        renderQualitySection(data);
        renderSummaryTable(data);
        renderCharts(data);

        window.scrollTo({ top: document.getElementById("recommendation-section").offsetTop - 20, behavior: "smooth" });

    } catch (error) {
        status.textContent = error.message;
    }
}

/* ============================================
   UTILITIES
   ============================================ */
function hidePreviousResults() {
    ["recommendation-section", "quality-section", "results-section", "chart-section", "live-section", "progress-wrapper"]
        .forEach(id => document.getElementById(id)?.classList.add("hidden"));
}

function showToast(message) {
    // Simple toast fallback
    const existing = document.querySelector(".toast");
    if (existing) existing.remove();

    const toast = document.createElement("div");
    toast.className = "toast";
    toast.textContent = message;
    toast.style.cssText = `
        position: fixed; bottom: 24px; right: 24px; z-index: 9999;
        background: #1e2329; border: 1px solid #e8ff47;
        color: #e8eaf0; padding: 12px 20px; border-radius: 10px;
        font-family: 'JetBrains Mono', monospace; font-size: 13px;
        box-shadow: 0 8px 24px rgba(0,0,0,0.5);
        animation: slide-in 0.2s ease;
    `;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}

function escapeHtml(text) {
    if (text === null || text === undefined) return "";
    return String(text)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

window.addEventListener("load", () => {
    loadHistory();
});