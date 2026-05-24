import time
from collections import defaultdict
from typing import List
import json
from typing import AsyncGenerator

from app.metrics import (
    count_words,
    count_characters,
    calculate_words_per_second,
    calculate_tokens_per_second,
    ns_to_seconds
)
from app.ollama_client import OllamaClient
from app.ranking import build_ranking
from app.schemas import (
    EvaluationReport,
    EvaluationRequest,
    ModelPromptResult,
    ModelSummary
)
from app.utils import generate_run_id

from app.storage import save_report


class Evaluator:
    def __init__(self):
        self.ollama_client = OllamaClient()

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
            print(f"Model: {model} | Prompt: {prompt}... | Response: {response_text}...")

            total_latency_seconds = ns_to_seconds(data.get("total_duration"))
            load_latency_seconds = ns_to_seconds(data.get("load_duration"))
            prompt_eval_latency_seconds = ns_to_seconds(data.get("prompt_eval_duration"))
            generation_latency_seconds = ns_to_seconds(data.get("eval_duration"))

            # Fallback if Ollama does not return timing values
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

        # Stable mode:
        # Run all prompts for one model first,
        # then unload that model before moving to the next model.
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

            # Unload current model from RAM/VRAM before next model starts
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

        ranking = build_ranking(summary)

        report = EvaluationReport(
            run_id=generate_run_id(),
            models=request.models,
            total_prompts=len(request.prompts),
            results=results,
            summary=summary,
            ranking=ranking
        )

        return report
    
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
            "total_tasks": total_tasks
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
                    "progress_percent": round((completed_tasks / total_tasks) * 100, 2),
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

        ranking = build_ranking(summary)

        report = EvaluationReport(
            run_id=generate_run_id(),
            models=request.models,
            total_prompts=len(request.prompts),
            results=results,
            summary=summary,
            ranking=ranking
        )

        save_report(report)

        yield json.dumps({
            "type": "summary",
            "data": report.model_dump()
        }) + "\n"

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
                sum(result.total_latency_seconds for result in model_results),
                3
            )

            average_total_latency_seconds = round(
                total_latency_seconds / total_prompts,
                3
            ) if total_prompts else 0.0

            total_load_latency_seconds = round(
                sum(result.load_latency_seconds for result in model_results),
                3
            )

            average_load_latency_seconds = round(
                total_load_latency_seconds / total_prompts,
                3
            ) if total_prompts else 0.0

            total_generation_latency_seconds = round(
                sum(result.generation_latency_seconds for result in model_results),
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
                result.output_token_count for result in model_results
            )

            average_words_per_second = round(
                sum(result.words_per_second for result in successful_results)
                / len(successful_results),
                2
            ) if successful_results else 0.0

            average_tokens_per_second = round(
                sum(result.tokens_per_second for result in successful_results)
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