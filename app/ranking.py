from typing import List, Optional

from app.schemas import ModelSummary, QualitySummary, RankingResult


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


def get_best_quality_model(
    quality_summary: List[QualitySummary]
) -> Optional[str]:
    valid_quality = [
        item for item in quality_summary
        if item.average_overall_quality > 0
    ]

    if not valid_quality:
        return None

    return max(
        valid_quality,
        key=lambda item: item.average_overall_quality
    ).model


def normalize(value: float, max_value: float) -> float:
    if max_value <= 0:
        return 0.0

    return value / max_value


def get_best_balanced_model(
    summary: List[ModelSummary],
    quality_summary: List[QualitySummary]
) -> Optional[str]:
    successful_models = [
        item for item in summary
        if item.successful_prompts > 0
    ]

    if not successful_models:
        return None

    quality_map = {
        item.model: item.average_overall_quality
        for item in quality_summary
    }

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

    max_quality = max(quality_map.values()) if quality_map else 0.0

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

        quality_value = quality_map.get(item.model, 0.0)

        if max_quality > 0:
            quality_score = normalize(quality_value, max_quality)
        else:
            quality_score = 0.0

        if quality_map:
            score = (
                reliability_score * 0.25
                + quality_score * 0.35
                + speed_score * 0.20
                + detail_score * 0.10
                + latency_score * 0.10
            )
        else:
            score = (
                reliability_score * 0.40
                + speed_score * 0.30
                + detail_score * 0.20
                + latency_score * 0.10
            )

        return score

    return max(successful_models, key=balanced_score).model


def build_ranking(
    summary: List[ModelSummary],
    quality_summary: List[QualitySummary] | None = None
) -> RankingResult:
    quality_summary = quality_summary or []

    fastest = get_fastest_model(summary)
    most_detailed = get_most_detailed_model(summary)
    most_reliable = get_most_reliable_model(summary)
    best_quality = get_best_quality_model(quality_summary)
    best_balanced = get_best_balanced_model(summary, quality_summary)

    if best_balanced and best_quality:
        recommendation = (
            f"{best_balanced} is the best overall choice for this evaluation run. "
            f"It gives the strongest trade-off between local performance, reliability, "
            f"response detail, and judged answer quality. "
            f"{best_quality} had the strongest judged answer quality."
        )
    elif best_balanced:
        recommendation = (
            f"{best_balanced} is the best choice based on objective local metrics. "
            f"It gives the best trade-off between reliability, generation speed, "
            f"response detail, and generation latency. "
            f"Answer quality scoring was not enabled or not available."
        )
    else:
        recommendation = (
            "No successful responses were generated, so LocalEval could not recommend a model."
        )

    return RankingResult(
        fastest_model=fastest,
        most_detailed_model=most_detailed,
        most_reliable_model=most_reliable,
        best_quality_model=best_quality,
        best_balanced_model=best_balanced,
        recommendation=recommendation
    )