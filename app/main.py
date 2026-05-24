from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.config import FRONTEND_DIR
from app.evaluator import Evaluator
from app.ollama_client import OllamaClient
from app.prompt_loader import load_default_prompts
from app.schemas import EvaluationRequest
from app.storage import save_report, load_report, list_reports



app = FastAPI(
    title="LocalEval",
    description="Local LLM Evaluation and Comparison Platform using FastAPI and Ollama",
    version="1.0.0"
)


app.mount(
    "/static",
    StaticFiles(directory=FRONTEND_DIR),
    name="static"
)


@app.get("/")
async def serve_frontend():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "message": "LocalEval backend is running."
    }


@app.get("/models")
async def get_models():
    try:
        client = OllamaClient()
        models = await client.list_models()
        return {"models": models}

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to fetch Ollama models. "
                "Make sure Ollama is installed and running. "
                f"Error: {error}"
            )
        )


@app.get("/default-prompts")
async def get_default_prompts():
    try:
        prompts = load_default_prompts()
        return {"prompts": prompts}

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to load default prompts: {error}"
        )


@app.post("/evaluate")
async def evaluate_models(request: EvaluationRequest):
    if not 2 <= len(request.models) <= 5:
        raise HTTPException(
            status_code=400,
            detail="Please select between 2 and 5 models."
        )

    if len(set(request.models)) != len(request.models):
        raise HTTPException(
            status_code=400,
            detail="Please select unique models only."
        )

    evaluator = Evaluator()
    report = await evaluator.run_evaluation(request)
    save_report(report)

    return report


@app.post("/evaluate-stream")
async def evaluate_models_stream(request: EvaluationRequest):
    if not 2 <= len(request.models) <= 5:
        raise HTTPException(
            status_code=400,
            detail="Please select between 2 and 5 models."
        )

    if len(set(request.models)) != len(request.models):
        raise HTTPException(
            status_code=400,
            detail="Please select unique models only."
        )

    evaluator = Evaluator()

    return StreamingResponse(
        evaluator.stream_evaluation(request),
        media_type="application/x-ndjson"
    )


@app.get("/results/{run_id}")
async def get_result(run_id: str):
    try:
        return load_report(run_id)

    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Result not found."
        )


@app.get("/history")
async def get_history():
    return {"runs": list_reports()}