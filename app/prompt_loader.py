import json
from typing import List

from app.config import PROMPTS_FILE
from app.schemas import PromptItem


def load_default_prompts() -> List[PromptItem]:
    if not PROMPTS_FILE.exists():
        raise FileNotFoundError("Default prompts file not found.")

    with PROMPTS_FILE.open("r", encoding="utf-8") as file:
        data = json.load(file)

    return [PromptItem(**item) for item in data]