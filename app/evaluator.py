import json
import time
from collections import defaultdict
from typing import List, AsyncGenerator

from app.metrics import (
    count_words,
    count_characters,
    calculate_words_per_second,
    calculate_tokens_per_second,
    ns_to_seconds
)
from app.nim_judge import NIMJudge
from app.ollama_client import OllamaClient
from app.ranking import build_ranking
from app.schemas import (
    EvaluationReport,
    EvaluationRequest,
    ModelPromptResult,
    ModelSummary,
    QualityScore,
    QualitySummary
)
from app.storage import save_report
from app.utils import generate_run_id
from app.config import NVIDIA_NIM_JUDGE_MODEL


class Evaluator:
    def __init__(self):
        self.ollama_client = OllamaClient()
        self.judge = NIMJudge()

    async def evaluate_single_prompt(
        self,
        model_index: int,
        prompt_index: int,
        model: str,
        category: str,
        prompt: str
    ) -> ModelPromptResult:
        start_time = time.perf_counter()

        try:
            data = await self.ollama_client.generate(
                model=model,
                prompt=prompt,
                keep_alive="10m"
            )

            wall_clock_latency = round(
                time.perf_counter() - start_time,
                3
            )

            response_text = data.get("response", "")

            total_latency_seconds = ns_to_seconds(
                data.get("total_duration")
            )
            load_latency_seconds = ns_to_seconds(
                data.get("load_duration")
            )
            prompt_eval_latency_seconds = ns_to_seconds(
                data.get("prompt_eval_duration")
            )
            generation_latency_seconds = ns_to_seconds(
                data.get("eval_duration")
            )

            if total_latency_seconds <= 0:
                total_latency_seconds = wall_clock_latency

            if generation_latency_seconds <= 0:
                generation_latency_seconds = wall_clock_latency

            word_count = count_words(response_text)
            character_count = count_characters(response_text)
            output_token_count = data.get("eval_count", 0) or 0

            words_per_second = calculate_words_per_second(
                word_count=word_count,
                latency_seconds=generation_latency_seconds
            )

            tokens_per_second = calculate_tokens_per_second(
                token_count=output_token_count,
                generation_latency_seconds=generation_latency_seconds
            )

            return ModelPromptResult(
                model_index=model_index,
                prompt_index=prompt_index,
                model=model,
                category=category,
                prompt=prompt,
                response=response_text,

                total_latency_seconds=total_latency_seconds,
                load_latency_seconds=load_latency_seconds,
                prompt_eval_latency_seconds=prompt_eval_latency_seconds,
                generation_latency_seconds=generation_latency_seconds,

                word_count=word_count,
                character_count=character_count,
                output_token_count=output_token_count,

                words_per_second=words_per_second,
                tokens_per_second=tokens_per_second,

                success=True,
                error=None
            )

        except Exception as error:
            wall_clock_latency = round(
                time.perf_counter() - start_time,
                3
            )

            return ModelPromptResult(
                model_index=model_index,
                prompt_index=prompt_index,
                model=model,
                category=category,
                prompt=prompt,
                response=None,

                total_latency_seconds=wall_clock_latency,
                load_latency_seconds=0.0,
                prompt_eval_latency_seconds=0.0,
                generation_latency_seconds=0.0,

                word_count=0,
                character_count=0,
                output_token_count=0,

                words_per_second=0.0,
                tokens_per_second=0.0,

                success=False,
                error=str(error)
            )

    async def run_evaluation(
        self,
        request: EvaluationRequest
    ) -> EvaluationReport:
        results = []

        for model_index, model in enumerate(request.models):
            for prompt_index, prompt_item in enumerate(request.prompts):
                result = await self.evaluate_single_prompt(
                    model_index=model_index,
                    prompt_index=prompt_index,
                    model=model,
                    category=prompt_item.category,
                    prompt=prompt_item.prompt
                )

                results.append(result)

            try:
                await self.ollama_client.unload_model(model)
            except Exception as error:
                print(f"Warning: Could not unload model {model}: {error}")

        results.sort(
            key=lambda result: (result.model_index, result.prompt_index)
        )

        summary = self.build_summary(
            models=request.models,
            results=results
        )

        quality_scores: List[QualityScore] = []
        quality_summary: List[QualitySummary] = []

        if request.enable_quality_check:
            quality_scores = await self.run_quality_check_by_prompt(results)
            quality_summary = await self.build_quality_summary(
                models=request.models,
                quality_scores=quality_scores
            )

        ranking = build_ranking(summary, quality_summary)

        return EvaluationReport(
            run_id=generate_run_id(),
            models=request.models,
            total_prompts=len(request.prompts),

            enable_quality_check=request.enable_quality_check,
            judge_model=NVIDIA_NIM_JUDGE_MODEL
            if request.enable_quality_check
            else None,

            results=results,
            summary=summary,

            quality_scores=quality_scores,
            quality_summary=quality_summary,

            ranking=ranking
        )

    async def stream_evaluation(
        self,
        request: EvaluationRequest
    ) -> AsyncGenerator[str, None]:
        results = []

        total_tasks = len(request.models) * len(request.prompts)
        completed_tasks = 0

        yield json.dumps({
            "type": "start",
            "message": "Evaluation started.",
            "total_tasks": total_tasks,
            "quality_check_enabled": request.enable_quality_check
        }) + "\n"

        for model_index, model in enumerate(request.models):
            yield json.dumps({
                "type": "model_start",
                "model": model,
                "model_index": model_index,
                "message": f"Started evaluating {model}"
            }) + "\n"

            for prompt_index, prompt_item in enumerate(request.prompts):
                result = await self.evaluate_single_prompt(
                    model_index=model_index,
                    prompt_index=prompt_index,
                    model=model,
                    category=prompt_item.category,
                    prompt=prompt_item.prompt
                )

                results.append(result)
                completed_tasks += 1

                yield json.dumps({
                    "type": "result",
                    "completed_tasks": completed_tasks,
                    "total_tasks": total_tasks,
                    "progress_percent": round(
                        (completed_tasks / total_tasks) * 100,
                        2
                    ),
                    "data": result.model_dump()
                }) + "\n"

            try:
                await self.ollama_client.unload_model(model)

                yield json.dumps({
                    "type": "model_unloaded",
                    "model": model,
                    "message": f"{model} unloaded from memory."
                }) + "\n"

            except Exception as error:
                yield json.dumps({
                    "type": "warning",
                    "model": model,
                    "message": f"Could not unload {model}: {error}"
                }) + "\n"

        results.sort(
            key=lambda result: (result.model_index, result.prompt_index)
        )

        summary = self.build_summary(
            models=request.models,
            results=results
        )

        quality_scores: List[QualityScore] = []
        quality_summary: List[QualitySummary] = []

        if request.enable_quality_check:
            total_judge_calls = len(request.prompts) + 1

            yield json.dumps({
                "type": "judge_start",
                "message": (
                    "Answer Quality Check started. "
                    "NVIDIA NIM will judge all model answers prompt-by-prompt."
                ),
                "judge_model": NVIDIA_NIM_JUDGE_MODEL,
                "estimated_nim_calls": total_judge_calls
            }) + "\n"

            grouped_by_prompt = self.group_results_by_prompt(results)

            completed_judge_calls = 0

            for prompt_index, prompt_results in grouped_by_prompt.items():
                prompt_scores = await self.judge.judge_prompt_responses(
                    prompt_results
                )

                quality_scores.extend(prompt_scores)
                completed_judge_calls += 1

                yield json.dumps({
                    "type": "judge_result",
                    "prompt_index": prompt_index,
                    "completed_judgements": completed_judge_calls,
                    "total_judgements": total_judge_calls,
                    "progress_percent": round(
                        (completed_judge_calls / total_judge_calls) * 100,
                        2
                    ),
                    "data": [
                        score.model_dump()
                        for score in prompt_scores
                    ]
                }) + "\n"

            quality_summary = await self.build_quality_summary(
                models=request.models,
                quality_scores=quality_scores
            )

            completed_judge_calls += 1

            yield json.dumps({
                "type": "judge_summary",
                "completed_judgements": completed_judge_calls,
                "total_judgements": total_judge_calls,
                "progress_percent": 100,
                "data": [
                    item.model_dump()
                    for item in quality_summary
                ]
            }) + "\n"

        ranking = build_ranking(summary, quality_summary)

        report = EvaluationReport(
            run_id=generate_run_id(),
            models=request.models,
            total_prompts=len(request.prompts),

            enable_quality_check=request.enable_quality_check,
            judge_model=NVIDIA_NIM_JUDGE_MODEL
            if request.enable_quality_check
            else None,

            results=results,
            summary=summary,

            quality_scores=quality_scores,
            quality_summary=quality_summary,

            ranking=ranking
        )

        save_report(report)

        yield json.dumps({
            "type": "summary",
            "data": report.model_dump()
        }) + "\n"

    async def run_quality_check_by_prompt(
        self,
        results: List[ModelPromptResult]
    ) -> List[QualityScore]:
        quality_scores: List[QualityScore] = []

        grouped_by_prompt = self.group_results_by_prompt(results)

        for prompt_results in grouped_by_prompt.values():
            prompt_scores = await self.judge.judge_prompt_responses(
                prompt_results
            )
            quality_scores.extend(prompt_scores)

        quality_scores.sort(
            key=lambda score: (score.model_index, score.prompt_index)
        )

        return quality_scores

    async def build_quality_summary(
        self,
        models: List[str],
        quality_scores: List[QualityScore]
    ) -> List[QualitySummary]:
        return await self.judge.summarize_all_models_quality(
            models=models,
            scores=quality_scores
        )

    def group_results_by_prompt(
        self,
        results: List[ModelPromptResult]
    ) -> dict[int, List[ModelPromptResult]]:
        grouped = defaultdict(list)

        for result in results:
            grouped[result.prompt_index].append(result)

        for prompt_index in grouped:
            grouped[prompt_index].sort(
                key=lambda result: result.model_index
            )

        return dict(sorted(grouped.items()))

    def build_summary(
        self,
        models: List[str],
        results: List[ModelPromptResult]
    ) -> List[ModelSummary]:
        grouped_results = defaultdict(list)

        for result in results:
            grouped_results[result.model].append(result)

        summaries = []

        for model in models:
            model_results = grouped_results[model]

            model_results.sort(
                key=lambda result: result.prompt_index
            )

            total_prompts = len(model_results)

            successful_prompts = sum(
                1 for result in model_results
                if result.success
            )

            failed_prompts = total_prompts - successful_prompts

            successful_results = [
                result for result in model_results
                if result.success
            ]

            success_rate = round(
                successful_prompts / total_prompts,
                2
            ) if total_prompts else 0.0

            total_latency_seconds = round(
                sum(
                    result.total_latency_seconds
                    for result in model_results
                ),
                3
            )

            average_total_latency_seconds = round(
                total_latency_seconds / total_prompts,
                3
            ) if total_prompts else 0.0

            total_load_latency_seconds = round(
                sum(
                    result.load_latency_seconds
                    for result in model_results
                ),
                3
            )

            average_load_latency_seconds = round(
                total_load_latency_seconds / total_prompts,
                3
            ) if total_prompts else 0.0

            total_generation_latency_seconds = round(
                sum(
                    result.generation_latency_seconds
                    for result in model_results
                ),
                3
            )

            average_generation_latency_seconds = round(
                total_generation_latency_seconds / total_prompts,
                3
            ) if total_prompts else 0.0

            total_word_count = sum(
                result.word_count for result in model_results
            )

            total_character_count = sum(
                result.character_count for result in model_results
            )

            total_output_token_count = sum(
                result.output_token_count
                for result in model_results
            )

            average_words_per_second = round(
                sum(
                    result.words_per_second
                    for result in successful_results
                )
                / len(successful_results),
                2
            ) if successful_results else 0.0

            average_tokens_per_second = round(
                sum(
                    result.tokens_per_second
                    for result in successful_results
                )
                / len(successful_results),
                2
            ) if successful_results else 0.0

            summaries.append(
                ModelSummary(
                    model=model,
                    total_prompts=total_prompts,
                    successful_prompts=successful_prompts,
                    failed_prompts=failed_prompts,
                    success_rate=success_rate,

                    total_latency_seconds=total_latency_seconds,
                    average_total_latency_seconds=average_total_latency_seconds,

                    total_load_latency_seconds=total_load_latency_seconds,
                    average_load_latency_seconds=average_load_latency_seconds,

                    total_generation_latency_seconds=total_generation_latency_seconds,
                    average_generation_latency_seconds=average_generation_latency_seconds,

                    total_word_count=total_word_count,
                    total_character_count=total_character_count,
                    total_output_token_count=total_output_token_count,

                    average_words_per_second=average_words_per_second,
                    average_tokens_per_second=average_tokens_per_second
                )
            )

        return summaries