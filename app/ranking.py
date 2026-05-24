from typing import List, Optional

from app.schemas import ModelSummary, RankingResult


def get_fastest_model(summary: List[ModelSummary]) -> Optional[str]:
    successful_models = [
        item for item in summary
        if item.successful_prompts > 0
    ]

    if not successful_models:
        return None

    return min(
        successful_models,
        key=lambda item: item.average_generation_latency_seconds
    ).model


def get_most_detailed_model(summary: List[ModelSummary]) -> Optional[str]:
    successful_models = [
        item for item in summary
        if item.successful_prompts > 0
    ]

    if not successful_models:
        return None

    return max(
        successful_models,
        key=lambda item: item.total_word_count
    ).model


def get_most_reliable_model(summary: List[ModelSummary]) -> Optional[str]:
    successful_models = [
        item for item in summary
        if item.total_prompts > 0
    ]

    if not successful_models:
        return None

    return max(
        successful_models,
        key=lambda item: item.success_rate
    ).model


def normalize(value: float, max_value: float) -> float:
    if max_value <= 0:
        return 0.0

    return value / max_value


def get_best_balanced_model(summary: List[ModelSummary]) -> Optional[str]:
    successful_models = [
        item for item in summary
        if item.successful_prompts > 0
    ]

    if not successful_models:
        return None

    max_tokens_per_second = max(
        item.average_tokens_per_second
        for item in successful_models
    )

    max_word_count = max(
        item.total_word_count
        for item in successful_models
    )

    max_generation_latency = max(
        item.average_generation_latency_seconds
        for item in successful_models
    )

    def balanced_score(item: ModelSummary) -> float:
        reliability_score = item.success_rate

        speed_score = normalize(
            item.average_tokens_per_second,
            max_tokens_per_second
        )

        detail_score = normalize(
            item.total_word_count,
            max_word_count
        )

        if max_generation_latency <= 0:
            latency_score = 0.0
        else:
            latency_score = 1 - normalize(
                item.average_generation_latency_seconds,
                max_generation_latency
            )

        score = (
            reliability_score * 0.40
            + speed_score * 0.30
            + detail_score * 0.20
            + latency_score * 0.10
        )

        return score

    return max(successful_models, key=balanced_score).model


def build_ranking(summary: List[ModelSummary]) -> RankingResult:
    fastest = get_fastest_model(summary)
    most_detailed = get_most_detailed_model(summary)
    most_reliable = get_most_reliable_model(summary)
    best_balanced = get_best_balanced_model(summary)

    if best_balanced:
        recommendation = (
            f"{best_balanced} is the best balanced model for this evaluation run. "
            f"It gives the best overall trade-off between reliability, generation speed, "
            f"response detail, and generation latency on your current system. "
            f"Cold-start/load time is shown separately but is not used for ranking."
        )
    else:
        recommendation = (
            "No successful responses were generated, so LocalEval could not recommend a model."
        )

    return RankingResult(
        fastest_model=fastest,
        most_detailed_model=most_detailed,
        most_reliable_model=most_reliable,
        best_balanced_model=best_balanced,
        recommendation=recommendation
    )