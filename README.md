# LocalEval

**LocalEval** is a FastAPI-based benchmarking platform for locally installed Ollama models. Run structured evaluations across 2–5 models simultaneously, measure objective performance metrics, and get a clear recommendation for which model fits your hardware and workflow best.

---

## Screenshots

### Decision Dashboard
![Decision Dashboard](screenshots/decision-dashboard.png)

### Answer Quality Summary
![Answer Quality Summary](screenshots/answer-quality-summary.png)

### Quality Scores Table
![Quality Scores Table](screenshots/quality-scores-table.png)

### Performance Charts
![Performance Charts](screenshots/performance-charts.png)

---

## What It Does

LocalEval runs the same set of prompts across all selected models and produces a side-by-side comparison across latency, throughput, reliability, and optionally answer quality. Everything runs on your machine — no telemetry, no cloud calls (unless you enable the optional NIM quality judge).

---

## Features

- **Model Discovery** — automatically lists all locally installed Ollama models
- **Flexible Prompt Suite** — run the built-in benchmark set, add custom prompts, or combine both
- **Live Streaming Output** — results appear in real time as each prompt completes
- **Objective Performance Metrics** — latency, throughput, word count, success rate, and more
- **Decision Dashboard** — ranked recommendations across five categories
- **Optional Quality Check** — external NVIDIA NIM judge (Llama 3.1 70B) scores answer quality
- **Performance Charts** — bar charts for all key metrics
- **Evaluation History** — stored as JSON, reloadable at any time

---

## Metrics Measured

| Metric | Description |
|---|---|
| Generation Latency | Time to generate the response (excludes cold start) |
| Cold Start | Initial model load time (usually happens once) |
| Prompt Eval Latency | Time to process the input prompt |
| Total Latency | End-to-end time per response |
| Words / Second | Output throughput |
| Tokens / Second | Token-level throughput |
| Word Count | Total words generated across all prompts |
| Character Count | Total characters generated |
| Output Token Count | Total output tokens generated |
| Success Rate | Fraction of prompts that completed without error |
| Failure Count | Number of failed prompt attempts |

---

## Rankings

After evaluation, LocalEval recommends one model per use case:

- **Best for Your System** — best overall trade-off across all metrics
- **Best Answer Quality** — highest NIM quality score (requires quality check enabled)
- **Fastest Model** — lowest average generation latency
- **Most Detailed** — highest total word output
- **Most Reliable** — fewest failures and most consistent completions

---

## Answer Quality Check (Optional)

When enabled, each model response is evaluated by an external NVIDIA NIM judge model (Llama 3.1 70B) across six dimensions:

| Dimension | Description |
|---|---|
| Matches Question | Does the response address what was asked? |
| Easy to Understand | Is the response clear and readable? |
| Covers Enough Detail | Is the level of detail appropriate? |
| Factually Reliable | Is the information accurate? |
| Follows Instructions | Did the model follow the prompt's intent? |
| Overall Quality | Composite score out of 10 |

Quality scores are guidance — treat them as a signal, not ground truth.

---

## Tech Stack

- **FastAPI** — backend API and streaming
- **Ollama** — local model inference
- **HTML / CSS / JavaScript** — frontend (no build step required)
- **Chart.js** — performance visualization
- **JSON** — result storage

---

## Project Structure

```
Local-LLM-Comparison/
│
├── app/
│   ├── __init__.py
│   ├── config.py          # Env config: Ollama URL, NIM keys, paths
│   ├── evaluator.py       # Evaluation runner and streaming logic
│   ├── main.py            # FastAPI app, routes, static file serving
│   ├── metrics.py         # Latency, throughput, word count calculations
│   ├── nim_judge.py       # NVIDIA NIM quality judge integration
│   ├── ollama_client.py   # Ollama API client
│   ├── prompt_loader.py   # Load prompts from prompts.json
│   ├── ranking.py         # Model ranking and recommendation logic
│   ├── schemas.py         # Pydantic models (request/response shapes)
│   ├── storage.py         # Save and load JSON reports
│   └── utils.py           # Shared utilities
│
├── evaluation/
│   └── prompts.json       # Default benchmark prompt suite
│
├── frontend/
│   ├── index.html         # Main UI
│   ├── script.js          # Frontend logic, streaming, charts
│   └── style.css          # Styling
│
├── results/               # Saved evaluation reports (gitignored)
├── screenshots/           # UI screenshots for README
│
├── .env                   # Local environment variables (gitignored)
├── .gitignore
├── README.md
├── requirements.txt
└── setup.py
```

---

## Setup

**Prerequisites:** Python 3.9+, Ollama installed and running, at least 2 models pulled.

```bash
# Clone the repo
git clone https://github.com/trishpurkait/Local-LLM-Comparison.git
cd Local-LLM-Comparison

# Install dependencies
pip install -r requirements.txt
pip install -e .

# Configure environment (optional)
# Copy the variables below into a .env file in the project root

# Start the server
uvicorn app.main:app --reload
```

Then open `http://localhost:8000` in your browser.

---

## Environment Variables

Create a `.env` file in the project root with any of these:

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `REQUEST_TIMEOUT` | `300` | Ollama request timeout in seconds |
| `NVIDIA_NIM_API_KEY` | — | Required only if quality check is enabled |
| `NVIDIA_NIM_BASE_URL` | `https://integrate.api.nvidia.com/v1` | NIM API base URL |
| `NVIDIA_NIM_JUDGE_MODEL` | `meta/llama-3.1-70b-instruct` | Judge model used for quality scoring |
| `NVIDIA_NIM_TIMEOUT` | `120` | NIM request timeout in seconds |

---

## Usage

1. **Select Models** — click "Scan Ollama" to discover installed models, select 2–5
2. **Load Prompts** — use the default benchmark suite or add your own custom prompts
3. **Quality Check** *(optional)* — toggle on to enable the NVIDIA NIM judge
4. **Run** — click "Run Benchmark" and watch results stream in live
5. **Review** — check the Decision Dashboard, Performance Charts, and Comparison Table
6. **History** — past evaluations are saved as JSON and reloadable at any time

---

## License

MIT