import re
from typing import Optional, List

from app.schemas import ModelPromptResult


def count_words(text: Optional[str]) -> int:
    if not text:
        return 0

    words = re.findall(r"\b\w+\b", text)
    return len(words)


def count_characters(text: Optional[str]) -> int:
    if not text:
        return 0

    return len(text)


def calculate_words_per_second(word_count: int, latency_seconds: float) -> float:
    if latency_seconds <= 0:
        return 0.0

    return round(word_count / latency_seconds, 2)


def calculate_success_rate(results: List[ModelPromptResult]) -> float:
    if not results:
        return 0.0

    successful = sum(1 for result in results if result.success)
    return round(successful / len(results), 2)

def ns_to_seconds(value: int | float | None) -> float:
    if not value:
        return 0.0

    return round(value / 1_000_000_000, 3)


def calculate_tokens_per_second(token_count: int, generation_latency_seconds: float) -> float:
    if generation_latency_seconds <= 0:
        return 0.0

    return round(token_count / generation_latency_seconds, 2)
