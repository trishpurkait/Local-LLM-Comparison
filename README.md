# LocalEval

LocalEval is a FastAPI-based Local LLM Evaluation and Comparison Platform using Ollama.

It allows users to compare exactly 3 locally installed Ollama models on the same benchmark prompts and evaluate them using objective metrics.

## Features

- List locally available Ollama models
- Select exactly 3 models
- Run default benchmark prompts
- Add custom prompts
- Compare model responses
- Measure objective performance metrics
- Save evaluation reports as JSON
- View fastest, most detailed, most reliable, and best balanced model

## Metrics

LocalEval currently measures:

- Latency per response
- Average latency per model
- Total latency per model
- Word count
- Character count
- Words per second
- Success rate
- Failure count
- Error messages

## Tech Stack

- FastAPI
- Ollama
- HTML
- CSS
- JavaScript
- JSON storage

## Project Structure

```txt
LocalEval/
│
├── app/
│   ├── main.py
│   ├── config.py
│   ├── ollama_client.py
│   ├── evaluator.py
│   ├── metrics.py
│   ├── schemas.py
│   ├── storage.py
│   ├── ranking.py
│   ├── prompt_loader.py
│   └── utils.py
│
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── script.js
│
├── evaluation/
│   └── prompts.json
│
├── results/
│   └── .gitkeep
│
├── README.md
├── requirements.txt
├── .env.example
└── .gitignore