import os
from pathlib import Path
from dotenv import load_dotenv


load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "300"))

NVIDIA_NIM_API_KEY = os.getenv("NVIDIA_NIM_API_KEY", "")
NVIDIA_NIM_BASE_URL = os.getenv(
    "NVIDIA_NIM_BASE_URL",
    "https://integrate.api.nvidia.com/v1"
)
NVIDIA_NIM_JUDGE_MODEL = os.getenv(
    "NVIDIA_NIM_JUDGE_MODEL",
    "meta/llama-3.1-70b-instruct"
)
NVIDIA_NIM_TIMEOUT = int(os.getenv("NVIDIA_NIM_TIMEOUT", "120"))

FRONTEND_DIR = BASE_DIR / "frontend"
RESULTS_DIR = BASE_DIR / "results"
PROMPTS_FILE = BASE_DIR / "evaluation" / "prompts.json"