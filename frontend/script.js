let selectedModels = [];
let prompts = [];

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
                    No Ollama models found. Pull at least 3 models using ollama pull.
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
                prompts: prompts
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

    if (event.type === "summary") {
        status.textContent = `Evaluation completed. Run ID: ${event.data.run_id}`;

        renderRecommendation(event.data);
        renderSummaryTable(event.data);

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

function hidePreviousResults() {
    document.getElementById("recommendation-section").classList.add("hidden");
    document.getElementById("results-section").classList.add("hidden");

    const liveSection = document.getElementById("live-section");
    const progressWrapper = document.getElementById("progress-wrapper");

    if (liveSection) {
        liveSection.classList.add("hidden");
    }

    if (progressWrapper) {
        progressWrapper.classList.add("hidden");
    }
}

function renderRecommendation(data) {
    const section = document.getElementById("recommendation-section");
    const recommendation = document.getElementById("recommendation");

    section.classList.remove("hidden");

    recommendation.innerHTML = `
        <div class="recommendation-grid">
            <div class="recommendation-card">
                <strong>Fastest Model</strong>
                <span>${escapeHtml(data.ranking.fastest_model || "N/A")}</span>
            </div>

            <div class="recommendation-card">
                <strong>Most Detailed Model</strong>
                <span>${escapeHtml(data.ranking.most_detailed_model || "N/A")}</span>
            </div>

            <div class="recommendation-card">
                <strong>Most Reliable Model</strong>
                <span>${escapeHtml(data.ranking.most_reliable_model || "N/A")}</span>
            </div>

            <div class="recommendation-card">
                <strong>Best Balanced Model</strong>
                <span>${escapeHtml(data.ranking.best_balanced_model || "N/A")}</span>
            </div>
        </div>

        <p><strong>Recommendation:</strong> ${escapeHtml(data.ranking.recommendation)}</p>
        <p class="table-note">
            Ranking uses generation latency, speed, reliability, and response size. 
            Cold-start/load time is shown separately but is not used for choosing the best balanced model.
        </p>
    `;
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