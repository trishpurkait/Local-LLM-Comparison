from typing import List, Optional
from pydantic import BaseModel, Field


class PromptItem(BaseModel):
    category: str = Field(..., example="reasoning")
    prompt: str = Field(..., example="Explain why the sky appears blue.")


class EvaluationRequest(BaseModel):
    models: List[str] = Field(..., min_length=2, max_length=5)
    prompts: List[PromptItem] = Field(..., min_length=1)


class ModelPromptResult(BaseModel):
    model_index: int
    prompt_index: int
    model: str
    category: str
    prompt: str
    response: Optional[str]

    total_latency_seconds: float
    load_latency_seconds: float
    prompt_eval_latency_seconds: float
    generation_latency_seconds: float

    word_count: int
    character_count: int
    output_token_count: int

    words_per_second: float
    tokens_per_second: float

    success: bool
    error: Optional[str] = None


class ModelSummary(BaseModel):
    model: str
    total_prompts: int
    successful_prompts: int
    failed_prompts: int
    success_rate: float

    total_latency_seconds: float
    average_total_latency_seconds: float

    total_load_latency_seconds: float
    average_load_latency_seconds: float

    total_generation_latency_seconds: float
    average_generation_latency_seconds: float

    total_word_count: int
    total_character_count: int
    total_output_token_count: int

    average_words_per_second: float
    average_tokens_per_second: float


class RankingResult(BaseModel):
    fastest_model: Optional[str]
    most_detailed_model: Optional[str]
    most_reliable_model: Optional[str]
    best_balanced_model: Optional[str]
    recommendation: str


class EvaluationReport(BaseModel):
    run_id: str
    models: List[str]
    total_prompts: int
    results: List[ModelPromptResult]
    summary: List[ModelSummary]
    ranking: RankingResult