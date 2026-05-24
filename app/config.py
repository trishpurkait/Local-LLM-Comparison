import os
from pathlib import Path
from dotenv import load_dotenv


load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "300"))

FRONTEND_DIR = BASE_DIR / "frontend"
RESULTS_DIR = BASE_DIR / "results"
PROMPTS_FILE = BASE_DIR / "evaluation" / "prompts.json"