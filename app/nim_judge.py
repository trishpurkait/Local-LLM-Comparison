import json
import time
from collections import defaultdict
from typing import Any, Dict, List

import httpx

from app.config import (
    NVIDIA_NIM_API_KEY,
    NVIDIA_NIM_BASE_URL,
    NVIDIA_NIM_JUDGE_MODEL,
    NVIDIA_NIM_TIMEOUT
)
from app.schemas import ModelPromptResult, QualityScore, QualitySummary


class NIMJudge:
    def __init__(
        self,
        api_key: str = NVIDIA_NIM_API_KEY,
        base_url: str = NVIDIA_NIM_BASE_URL,
        model: str = NVIDIA_NIM_JUDGE_MODEL
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def judge_prompt_responses(
        self,
        prompt_results: List[ModelPromptResult]
    ) -> List[QualityScore]:
        """
        Judge all model responses for the same prompt in one NVIDIA NIM call.

        Example:
        Prompt 1:
            Model A response
            Model B response
            Model C response

        One NIM call returns scores for all models.
        """
        if not prompt_results:
            return []

        start_time = time.perf_counter()

        if not self.is_configured():
            return [
                self._failed_score(
                    result=result,
                    error="NVIDIA_NIM_API_KEY is missing."
                )
                for result in prompt_results
            ]

        successful_results = [
            result for result in prompt_results
            if result.success and result.response
        ]

        failed_results = [
            result for result in prompt_results
            if not result.success or not result.response
        ]

        failed_scores = [
            self._failed_score(
                result=result,
                error="Model response was unsuccessful or empty."
            )
            for result in failed_results
        ]

        if not successful_results:
            return failed_scores

        judge_prompt = self._build_prompt_comparison_judge_prompt(
            successful_results
        )

        try:
            raw_text = await self._call_nim(judge_prompt)
            parsed_items = self._parse_json_list_response(raw_text)

            judge_latency = round(time.perf_counter() - start_time, 3)

            score_map: Dict[str, Dict[str, Any]] = {}

            for item in parsed_items:
                key = self._make_key(
                    model_index=item.get("model_index"),
                    prompt_index=item.get("prompt_index")
                )
                score_map[key] = item

            quality_scores = []

            for result in successful_results:
                key = self._make_key(
                    model_index=result.model_index,
                    prompt_index=result.prompt_index
                )

                parsed = score_map.get(key)

                if not parsed:
                    quality_scores.append(
                        self._failed_score(
                            result=result,
                            error="Judge response missing score for this model.",
                            judge_latency_seconds=judge_latency
                        )
                    )
                    continue

                quality_scores.append(
                    QualityScore(
                        model_index=result.model_index,
                        prompt_index=result.prompt_index,
                        model=result.model,
                        category=result.category,

                        matches_question=self._clamp_score(
                            parsed.get("matches_question")
                        ),
                        easy_to_understand=self._clamp_score(
                            parsed.get("easy_to_understand")
                        ),
                        covers_enough_detail=self._clamp_score(
                            parsed.get("covers_enough_detail")
                        ),
                        factually_reliable=self._clamp_score(
                            parsed.get("factually_reliable")
                        ),
                        follows_instructions=self._clamp_score(
                            parsed.get("follows_instructions")
                        ),
                        overall_quality=self._clamp_score(
                            parsed.get("overall_quality")
                        ),

                        short_feedback=str(
                            parsed.get(
                                "short_feedback",
                                "No feedback provided."
                            )
                        ),

                        judge_latency_seconds=judge_latency,
                        judge_success=True,
                        judge_error=None
                    )
                )

            all_scores = quality_scores + failed_scores

            all_scores.sort(
                key=lambda score: (score.model_index, score.prompt_index)
            )

            return all_scores

        except Exception as error:
            judge_latency = round(time.perf_counter() - start_time, 3)

            return [
                self._failed_score(
                    result=result,
                    error=str(error),
                    judge_latency_seconds=judge_latency
                )
                for result in prompt_results
            ]

    async def summarize_all_models_quality(
        self,
        models: List[str],
        scores: List[QualityScore]
    ) -> List[QualitySummary]:
        """
        Generate all model-level summaries in one NVIDIA NIM call.

        This replaces:
            one summary call per model

        with:
            one summary call for all models
        """
        fallback_summaries = self._build_fallback_quality_summaries(
            models=models,
            scores=scores
        )

        if not self.is_configured():
            return fallback_summaries

        successful_scores = [
            score for score in scores
            if score.judge_success
        ]

        if not successful_scores:
            return fallback_summaries

        summary_prompt = self._build_all_models_summary_prompt(
            fallback_summaries=fallback_summaries,
            scores=successful_scores
        )

        try:
            raw_text = await self._call_nim(summary_prompt)
            parsed_items = self._parse_json_list_response(raw_text)

            parsed_map = {
                str(item.get("model")): item
                for item in parsed_items
                if item.get("model")
            }

            final_summaries: List[QualitySummary] = []

            for fallback in fallback_summaries:
                parsed = parsed_map.get(fallback.model)

                if not parsed:
                    final_summaries.append(fallback)
                    continue

                final_summaries.append(
                    QualitySummary(
                        model=fallback.model,

                        average_matches_question=fallback.average_matches_question,
                        average_easy_to_understand=fallback.average_easy_to_understand,
                        average_covers_enough_detail=fallback.average_covers_enough_detail,
                        average_factually_reliable=fallback.average_factually_reliable,
                        average_follows_instructions=fallback.average_follows_instructions,
                        average_overall_quality=fallback.average_overall_quality,

                        simple_summary=str(
                            parsed.get(
                                "simple_summary",
                                fallback.simple_summary
                            )
                        ),
                        strength=str(
                            parsed.get("strength", fallback.strength)
                        ),
                        weakness=str(
                            parsed.get("weakness", fallback.weakness)
                        ),
                        best_for=str(
                            parsed.get("best_for", fallback.best_for)
                        )
                    )
                )

            return final_summaries

        except Exception:
            return fallback_summaries

    async def _call_nim(self, prompt: str) -> str:
        url = f"{self.base_url}/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a strict but fair LLM evaluation judge. "
                        "Always return valid JSON only. "
                        "Do not include markdown or explanations outside JSON."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.1,
            "max_tokens": 1800
        }

        async with httpx.AsyncClient(timeout=NVIDIA_NIM_TIMEOUT) as client:
            response = await client.post(
                url,
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            data = response.json()

        return data["choices"][0]["message"]["content"]

    def _build_prompt_comparison_judge_prompt(
        self,
        prompt_results: List[ModelPromptResult]
    ) -> str:
        first_result = prompt_results[0]

        responses = []

        for result in prompt_results:
            responses.append(
                {
                    "model_index": result.model_index,
                    "prompt_index": result.prompt_index,
                    "model": result.model,
                    "category": result.category,
                    "response": result.response
                }
            )

        return f"""
You are comparing multiple local LLM responses to the same prompt.

Score each model response from 1 to 10 using these user-friendly criteria:

- matches_question: Did the answer address the user's prompt?
- easy_to_understand: Is the answer clear and easy to understand?
- covers_enough_detail: Does it provide enough useful detail?
- factually_reliable: Is it factually correct based on general knowledge?
- follows_instructions: Did it follow format, length, and specific instructions?
- overall_quality: Overall usefulness of the answer.

Important rules:
- Judge each response independently, but compare them side-by-side for consistency.
- Do not reward long answers unless they are useful.
- Penalize wrong answers, refusals, missing instructions, and irrelevant content.
- Return valid JSON only.
- Return a JSON array.
- Include one object per model response.

Original Prompt Category:
{first_result.category}

Original Prompt:
{first_result.prompt}

Model Responses:
{json.dumps(responses, indent=2, ensure_ascii=False)}

Return only valid JSON in this exact structure:
[
  {{
    "model_index": 0,
    "prompt_index": 0,
    "model": "model-name",
    "matches_question": 8,
    "easy_to_understand": 8,
    "covers_enough_detail": 7,
    "factually_reliable": 8,
    "follows_instructions": 9,
    "overall_quality": 8,
    "short_feedback": "Brief feedback in one sentence."
  }}
]
""".strip()

    def _build_all_models_summary_prompt(
        self,
        fallback_summaries: List[QualitySummary],
        scores: List[QualityScore]
    ) -> str:
        model_data = []

        scores_by_model = defaultdict(list)

        for score in scores:
            scores_by_model[score.model].append(score)

        for summary in fallback_summaries:
            model_scores = scores_by_model.get(summary.model, [])

            feedback_items = [
                {
                    "category": score.category,
                    "overall_quality": score.overall_quality,
                    "feedback": score.short_feedback
                }
                for score in model_scores
            ]

            model_data.append(
                {
                    "model": summary.model,
                    "average_matches_question": summary.average_matches_question,
                    "average_easy_to_understand": summary.average_easy_to_understand,
                    "average_covers_enough_detail": summary.average_covers_enough_detail,
                    "average_factually_reliable": summary.average_factually_reliable,
                    "average_follows_instructions": summary.average_follows_instructions,
                    "average_overall_quality": summary.average_overall_quality,
                    "feedback_items": feedback_items
                }
            )

        return f"""
Create plain-English summaries for each model based on quality scores.

The user wants to know which local LLM is best suited for their system and work.

For each model, provide:
- simple_summary: short explanation for normal users
- strength: main strength
- weakness: main weakness
- best_for: practical use case

Return valid JSON only.
Return a JSON array.
Include one object per model.

Model quality data:
{json.dumps(model_data, indent=2, ensure_ascii=False)}

Return only valid JSON in this exact structure:
[
  {{
    "model": "model-name",
    "simple_summary": "Short plain-English summary.",
    "strength": "Main strength.",
    "weakness": "Main weakness.",
    "best_for": "Best use case."
  }}
]
""".strip()

    def _parse_json_list_response(self, text: str) -> List[Dict[str, Any]]:
        cleaned = text.strip()

        if cleaned.startswith("```json"):
            cleaned = cleaned.replace("```json", "", 1).strip()

        if cleaned.startswith("```"):
            cleaned = cleaned.replace("```", "", 1).strip()

        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()

        start = cleaned.find("[")
        end = cleaned.rfind("]")

        if start == -1 or end == -1:
            raise ValueError(f"Judge did not return a JSON array: {text}")

        json_text = cleaned[start:end + 1]
        parsed = json.loads(json_text)

        if not isinstance(parsed, list):
            raise ValueError("Judge JSON response is not a list.")

        return parsed

    def _build_fallback_quality_summaries(
        self,
        models: List[str],
        scores: List[QualityScore]
    ) -> List[QualitySummary]:
        summaries = []

        for model in models:
            model_scores = [
                score for score in scores
                if score.model == model and score.judge_success
            ]

            if not model_scores:
                summaries.append(
                    QualitySummary(
                        model=model,
                        average_matches_question=0.0,
                        average_easy_to_understand=0.0,
                        average_covers_enough_detail=0.0,
                        average_factually_reliable=0.0,
                        average_follows_instructions=0.0,
                        average_overall_quality=0.0,
                        simple_summary="Quality review was not available for this model.",
                        strength="Not enough judged responses.",
                        weakness="Quality scoring failed or was skipped.",
                        best_for="Unknown"
                    )
                )
                continue

            avg_matches = self._average(
                score.matches_question for score in model_scores
            )
            avg_clarity = self._average(
                score.easy_to_understand for score in model_scores
            )
            avg_detail = self._average(
                score.covers_enough_detail for score in model_scores
            )
            avg_reliable = self._average(
                score.factually_reliable for score in model_scores
            )
            avg_instruction = self._average(
                score.follows_instructions for score in model_scores
            )
            avg_overall = self._average(
                score.overall_quality for score in model_scores
            )

            summaries.append(
                QualitySummary(
                    model=model,
                    average_matches_question=avg_matches,
                    average_easy_to_understand=avg_clarity,
                    average_covers_enough_detail=avg_detail,
                    average_factually_reliable=avg_reliable,
                    average_follows_instructions=avg_instruction,
                    average_overall_quality=avg_overall,
                    simple_summary=(
                        f"{model} received an average quality score of "
                        f"{avg_overall}/10."
                    ),
                    strength="See detailed quality scores.",
                    weakness="See detailed quality scores.",
                    best_for="General use"
                )
            )

        return summaries

    def _failed_score(
        self,
        result: ModelPromptResult,
        error: str,
        judge_latency_seconds: float = 0.0
    ) -> QualityScore:
        return QualityScore(
            model_index=result.model_index,
            prompt_index=result.prompt_index,
            model=result.model,
            category=result.category,

            matches_question=0.0,
            easy_to_understand=0.0,
            covers_enough_detail=0.0,
            factually_reliable=0.0,
            follows_instructions=0.0,
            overall_quality=0.0,

            short_feedback="Quality review failed.",
            judge_latency_seconds=judge_latency_seconds,
            judge_success=False,
            judge_error=error
        )

    def _clamp_score(self, value: Any) -> float:
        try:
            score = float(value)
        except (TypeError, ValueError):
            return 0.0

        return round(max(0.0, min(10.0, score)), 2)

    def _average(self, values) -> float:
        values = list(values)

        if not values:
            return 0.0

        return round(sum(values) / len(values), 2)

    def _make_key(self, model_index: Any, prompt_index: Any) -> str:
        return f"{model_index}:{prompt_index}"