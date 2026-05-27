let selectedModels = [];
let prompts = [];
let currentRunId = null;

let latencyChart = null;
let tokensChart = null;
let wordsChart = null;
let successChart = null;

async function loadModels() {
    const modelList = document.getElementById("model-list");
    modelList.innerHTML = "Loading local Ollama models...";

    try {
        const response = await fetch("/models");
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Failed to load models.");
        }

        if (!data.models || data.models.length === 0) {
            modelList.innerHTML = `
                <p class="error">
                    No Ollama models found. Pull at least 2 models using ollama pull.
                </p>
            `;
            return;
        }

        selectedModels = [];
        updateSelectedCount();

        modelList.innerHTML = "";

        data.models.forEach(model => {
            const div = document.createElement("div");
            div.className = "model-item";

            div.innerHTML = `
                <label>
                    <input type="checkbox" value="${escapeHtml(model)}" onchange="toggleModel(this)">
                    ${escapeHtml(model)}
                </label>
            `;

            modelList.appendChild(div);
        });

    } catch (error) {
        modelList.innerHTML = `<p class="error">${escapeHtml(error.message)}</p>`;
    }
}

function toggleModel(checkbox) {
    const model = checkbox.value;

    if (checkbox.checked) {
        if (selectedModels.length >= 5) {
            checkbox.checked = false;
            alert("You can select up to 5 models only.");
            return;
        }

        selectedModels.push(model);
    } else {
        selectedModels = selectedModels.filter(item => item !== model);
    }

    updateSelectedCount();
}

function updateSelectedCount() {
    const selectedCount = document.getElementById("selected-count");
    selectedCount.textContent = `${selectedModels.length} selected`;
}

async function loadDefaultPrompts() {
    const promptList = document.getElementById("prompt-list");
    promptList.innerHTML = "Loading default prompts...";

    try {
        const response = await fetch("/default-prompts");
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Failed to load default prompts.");
        }

        prompts = data.prompts;
        renderPrompts();

    } catch (error) {
        promptList.innerHTML = `<p class="error">${escapeHtml(error.message)}</p>`;
    }
}

function addCustomPrompt() {
    const textarea = document.getElementById("custom-prompt");
    const promptText = textarea.value.trim();

    if (!promptText) {
        alert("Please enter a custom prompt first.");
        return;
    }

    prompts.push({
        category: "custom",
        prompt: promptText
    });

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
        promptList.innerHTML = "<p>No prompts selected yet.</p>";
        return;
    }

    prompts.forEach((item, index) => {
        const div = document.createElement("div");
        div.className = "prompt-item";

        div.innerHTML = `
            <strong>${index + 1}. ${escapeHtml(item.category)}</strong>
            <p>${escapeHtml(item.prompt)}</p>
            <button onclick="removePrompt(${index})">Remove</button>
        `;

        promptList.appendChild(div);
    });
}

async function runEvaluation() {
    const status = document.getElementById("status");
    const liveSection = document.getElementById("live-section");
    const liveResults = document.getElementById("live-results");
    const progressWrapper = document.getElementById("progress-wrapper");
    const progressFill = document.getElementById("progress-fill");
    const progressText = document.getElementById("progress-text");

    if (selectedModels.length < 2 || selectedModels.length > 5) {
        alert("Please select between 2 and 5 models.");
        return;
    }

    if (prompts.length === 0) {
        alert("Please add at least one prompt.");
        return;
    }

    hidePreviousResults();

    currentRunId = null;

    liveSection.classList.remove("hidden");
    progressWrapper.classList.remove("hidden");

    liveResults.innerHTML = "";
    progressFill.style.width = "0%";
    progressText.textContent = "0%";

    status.textContent = "Running evaluation. Results will appear as each prompt completes...";

    try {
        const response = await fetch("/evaluate-stream", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
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

            if (done) {
                break;
            }

            buffer += decoder.decode(value, { stream: true });

            const lines = buffer.split("\n");
            buffer = lines.pop();

            for (const line of lines) {
                if (!line.trim()) {
                    continue;
                }

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

function renderLiveResult(result) {
    const liveResults = document.getElementById("live-results");

    const box = document.createElement("div");
    box.className = "live-result";

    box.innerHTML = `
        <div class="live-result-header">
            <span class="badge">${escapeHtml(result.model)} | ${escapeHtml(result.category)}</span>
            <span><strong>Status:</strong> ${result.success ? "Success" : "Failed"}</span>
        </div>

        <p><strong>Prompt:</strong> ${escapeHtml(result.prompt)}</p>

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

            <div class="metric-card">
                <strong>Words/Sec</strong>
                <span>${result.words_per_second}</span>
            </div>

            <div class="metric-card">
                <strong>Tokens/Sec</strong>
                <span>${result.tokens_per_second}</span>
            </div>
        </div>

        ${result.error ? `<p class="error"><strong>Error:</strong> ${escapeHtml(result.error)}</p>` : ""}

        <p><strong>Response:</strong></p>
        <div class="live-result-response">
            ${escapeHtml(result.response || "No response")}
        </div>
    `;

    liveResults.appendChild(box);

    box.scrollIntoView({
        behavior: "smooth",
        block: "nearest"
    });
}

function renderRecommendation(data) {
    const section = document.getElementById("recommendation-section");
    const recommendation = document.getElementById("recommendation");

    section.classList.remove("hidden");

    const fastestModel = data.ranking.fastest_model || "N/A";
    const detailedModel = data.ranking.most_detailed_model || "N/A";
    const reliableModel = data.ranking.most_reliable_model || "N/A";
    const qualityModel = data.ranking.best_quality_model || "N/A";
    const balancedModel = data.ranking.best_balanced_model || "N/A";

    recommendation.innerHTML = `
        <div class="decision-grid">
            <div class="decision-card primary-decision">
                <strong>Best for Your Current System</strong>
                <span>${escapeHtml(balancedModel)}</span>
                <p>Best overall trade-off between speed, reliability, response detail, and quality.</p>
            </div>

            <div class="decision-card">
                <strong>Best Answer Quality</strong>
                <span>${escapeHtml(qualityModel)}</span>
                <p>Recommended when answer usefulness and correctness matter most.</p>
            </div>

            <div class="decision-card">
                <strong>Best for Quick Answers</strong>
                <span>${escapeHtml(fastestModel)}</span>
                <p>Recommended when you care most about lower generation time.</p>
            </div>

            <div class="decision-card">
                <strong>Best for Detailed Answers</strong>
                <span>${escapeHtml(detailedModel)}</span>
                <p>Recommended when longer and more detailed responses are useful.</p>
            </div>

            <div class="decision-card">
                <strong>Most Reliable</strong>
                <span>${escapeHtml(reliableModel)}</span>
                <p>Recommended when fewer failures and stable completion matter most.</p>
            </div>
        </div>

        <p><strong>Plain Recommendation:</strong> ${escapeHtml(data.ranking.recommendation)}</p>

        <p class="table-note">
            Performance metrics are measured locally. Quality scores are produced by NVIDIA NIM when Answer Quality Check is enabled.
        </p>
    `;
}

function renderQualitySection(data) {
    const section = document.getElementById("quality-section");
    const qualitySummaryDiv = document.getElementById("quality-summary");
    const tbody = document.querySelector("#quality-table tbody");

    if (
        !data.enable_quality_check ||
        !data.quality_summary ||
        data.quality_summary.length === 0
    ) {
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

function renderCharts(data) {
    const chartSection = document.getElementById("chart-section");
    chartSection.classList.remove("hidden");

    const labels = data.summary.map(item => item.model);

    const latencyData = data.summary.map(item => item.average_generation_latency_seconds);
    const tokensData = data.summary.map(item => item.average_tokens_per_second);
    const wordsData = data.summary.map(item => item.total_word_count);
    const successData = data.summary.map(item => Math.round(item.success_rate * 100));

    latencyChart = createOrUpdateChart(
        latencyChart,
        "latencyChart",
        "Avg Generation Latency (s)",
        labels,
        latencyData
    );

    tokensChart = createOrUpdateChart(
        tokensChart,
        "tokensChart",
        "Tokens/Sec",
        labels,
        tokensData
    );

    wordsChart = createOrUpdateChart(
        wordsChart,
        "wordsChart",
        "Total Words",
        labels,
        wordsData
    );

    successChart = createOrUpdateChart(
        successChart,
        "successChart",
        "Success Rate (%)",
        labels,
        successData
    );
}

function createOrUpdateChart(existingChart, canvasId, label, labels, values) {
    if (existingChart) {
        existingChart.destroy();
    }

    const ctx = document.getElementById(canvasId).getContext("2d");

    return new Chart(ctx, {
        type: "bar",
        data: {
            labels: labels,
            datasets: [
                {
                    label: label,
                    data: values
                }
            ]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    display: true
                }
            },
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
}

async function loadHistory() {
    const historyList = document.getElementById("history-list");
    historyList.innerHTML = "Loading history...";

    try {
        const response = await fetch("/history");
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Failed to load history.");
        }

        renderHistory(data.runs || []);

    } catch (error) {
        historyList.innerHTML = `<p class="error">${escapeHtml(error.message)}</p>`;
    }
}

function renderHistory(runs) {
    const historyList = document.getElementById("history-list");

    if (!runs || runs.length === 0) {
        historyList.innerHTML = "<p>No evaluation history found.</p>";
        return;
    }

    historyList.innerHTML = "";

    runs.forEach(run => {
        const div = document.createElement("div");
        div.className = "history-item";

        const models = Array.isArray(run.models)
            ? run.models.join(", ")
            : "N/A";

        const bestModel = run.ranking && run.ranking.best_balanced_model
            ? run.ranking.best_balanced_model
            : "N/A";

        div.innerHTML = `
            <strong>${escapeHtml(run.run_id || "Unknown Run")}</strong>
            <p><strong>Models:</strong> ${escapeHtml(models)}</p>
            <p><strong>Total Prompts:</strong> ${run.total_prompts || 0}</p>
            <p><strong>Best for Current System:</strong> ${escapeHtml(bestModel)}</p>

            <div class="history-actions">
                <button onclick="viewHistoryReport('${escapeHtml(run.run_id)}')">View Result</button>
            </div>
        `;

        historyList.appendChild(div);
    });
}

async function viewHistoryReport(runId) {
    const status = document.getElementById("status");

    try {
        const response = await fetch(`/results/${runId}`);
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Failed to load report.");
        }

        currentRunId = data.run_id;

        status.textContent = `Loaded previous report. Run ID: ${data.run_id}`;

        document.getElementById("live-section").classList.add("hidden");
        document.getElementById("progress-wrapper").classList.add("hidden");

        renderRecommendation(data);
        renderQualitySection(data);
        renderSummaryTable(data);
        renderCharts(data);

        window.scrollTo({
            top: document.getElementById("recommendation-section").offsetTop - 20,
            behavior: "smooth"
        });

    } catch (error) {
        status.textContent = error.message;
    }
}

function hidePreviousResults() {
    document.getElementById("recommendation-section").classList.add("hidden");
    document.getElementById("quality-section").classList.add("hidden");
    document.getElementById("results-section").classList.add("hidden");
    document.getElementById("chart-section").classList.add("hidden");

    const liveSection = document.getElementById("live-section");
    const progressWrapper = document.getElementById("progress-wrapper");

    if (liveSection) {
        liveSection.classList.add("hidden");
    }

    if (progressWrapper) {
        progressWrapper.classList.add("hidden");
    }
}

function escapeHtml(text) {
    if (text === null || text === undefined) {
        return "";
    }

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