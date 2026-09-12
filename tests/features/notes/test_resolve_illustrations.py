# @covers analysis:REQ-027
# @covers analysis:INV-022
# @covers analysis:ASM-022
# @covers analysis:DLT-028
# @covers analysis:DLT-029
import logging
from collections.abc import Sequence

import pytest

from konspekt.features.notes.application.resolve_illustrations import IllustrationResolver
from konspekt.features.notes.domain.illustration import (
    GENERATED_CAPTION_LABEL_BY_LANGUAGE,
    PERFECT_SCORE_THRESHOLD,
    SUITABLE_SCORE_THRESHOLD,
    CandidateAssessment,
    IllustrationConfig,
    IllustrationRequest,
)
from konspekt.features.notes.domain.notes import BlockKind, FigureProvenance
from konspekt.features.notes.ports.outbound.notes_llm import ImageCandidate
from konspekt.shared.budget import BudgetExceededError

IMAGES_DIR = "images"
FILE_PAGE_URL = "https://commons.wikimedia.org/wiki/File:Radius_ulna.jpg"
IMAGE_URL = "https://upload.wikimedia.org/radius_ulna.jpg"


class FakeSearch:
    def __init__(
        self,
        candidates: Sequence[ImageCandidate] = (),
        error: Exception | None = None,
    ) -> None:
        self.calls: list[tuple[str, int]] = []
        self._candidates = tuple(candidates)
        self._error = error

    def search(self, query: str, limit: int) -> Sequence[ImageCandidate]:
        self.calls.append((query, limit))
        if self._error is not None:
            raise self._error
        return self._candidates[:limit]


class FakeDownloader:
    def __init__(self, failing_urls: frozenset[str] = frozenset()) -> None:
        self.calls: list[str] = []
        self._failing_urls = failing_urls

    def download(self, image_url: str, dest_dir: str) -> str | None:
        self.calls.append(image_url)
        if image_url in self._failing_urls:
            return None
        return f"{dest_dir}/{image_url.rsplit('/', 1)[-1]}"


class FakeGenerator:
    def __init__(self, is_available: bool = True) -> None:
        self.calls: list[tuple[str, str, str]] = []
        self._is_available = is_available

    def generate(self, prompt: str, dest_dir: str, file_stem: str) -> str | None:
        self.calls.append((prompt, dest_dir, file_stem))
        if not self._is_available:
            return None
        return f"{dest_dir}/{file_stem}.png"


class FakeVision:
    def __init__(
        self,
        assessments_by_path: dict[str, CandidateAssessment] | None = None,
        error: Exception | None = None,
        grades_everything: CandidateAssessment | None = None,
    ) -> None:
        self.calls: list[tuple[str, str]] = []
        self._assessments_by_path = assessments_by_path or {}
        self._error = error
        self._grades_everything = grades_everything

    def assess(self, image_path: str, purpose: str) -> CandidateAssessment:
        self.calls.append((image_path, purpose))
        if self._error is not None:
            raise self._error
        if self._grades_everything is not None:
            return self._grades_everything
        return self._assessments_by_path.get(image_path, CandidateAssessment(score=0))


def perfect() -> CandidateAssessment:
    return CandidateAssessment(score=PERFECT_SCORE_THRESHOLD)


def suitable(score: int) -> CandidateAssessment:
    assert SUITABLE_SCORE_THRESHOLD <= score < PERFECT_SCORE_THRESHOLD
    return CandidateAssessment(score=score)


def a_request(purpose: str = "Лучевая и локтевая кости, вид спереди") -> IllustrationRequest:
    return IllustrationRequest(
        purpose=purpose,
        search_query="radius ulna bones anterior view",
        generation_prompt="Educational illustration of the radius and ulna",
        insert_index=1,
    )


def a_candidate(index: int = 0) -> ImageCandidate:
    return ImageCandidate(
        file_page_url=f"{FILE_PAGE_URL}{index or ''}",
        image_url=f"https://upload.wikimedia.org/radius_ulna{index or ''}.jpg",
    )


def a_resolver(
    search: FakeSearch | None = None,
    downloader: FakeDownloader | None = None,
    generator: FakeGenerator | None = None,
    vision: FakeVision | None = None,
    config: IllustrationConfig = IllustrationConfig(),
) -> IllustrationResolver:
    return IllustrationResolver(
        search=search if search is not None else FakeSearch(),
        downloader=downloader if downloader is not None else FakeDownloader(),
        generator=generator if generator is not None else FakeGenerator(),
        vision=vision if vision is not None else FakeVision(),
        images_dir=IMAGES_DIR,
        config=config,
    )


def test_perfect_commons_candidate_becomes_commons_figure() -> None:
    resolver = a_resolver(
        search=FakeSearch([a_candidate()]),
        vision=FakeVision({f"{IMAGES_DIR}/radius_ulna.jpg": perfect()}),
    )

    figures = resolver.resolve({"s1": a_request()}, language="ru")

    figure = figures["s1"]
    assert figure is not None
    assert figure.kind is BlockKind.FIGURE
    assert figure.provenance is FigureProvenance.COMMONS
    assert figure.source_ref == FILE_PAGE_URL
    assert figure.image_path == f"{IMAGES_DIR}/radius_ulna.jpg"
    assert figure.caption == "Лучевая и локтевая кости, вид спереди"


def test_search_is_limited_to_configured_candidate_count() -> None:
    search = FakeSearch([a_candidate()])
    config = IllustrationConfig()

    a_resolver(search=search, config=config).resolve({"s1": a_request()}, language="ru")

    assert search.calls == [("radius ulna bones anterior view", config.commons_candidates)]


def test_second_candidate_is_used_when_first_is_unsuitable() -> None:
    vision = FakeVision({f"{IMAGES_DIR}/radius_ulna1.jpg": perfect()})
    resolver = a_resolver(search=FakeSearch([a_candidate(0), a_candidate(1)]), vision=vision)

    figures = resolver.resolve({"s1": a_request()}, language="ru")

    assert figures["s1"] is not None
    assert figures["s1"].source_ref == a_candidate(1).file_page_url
    assert [path for path, _ in vision.calls] == [
        f"{IMAGES_DIR}/radius_ulna.jpg",
        f"{IMAGES_DIR}/radius_ulna1.jpg",
    ]


def test_candidate_that_fails_to_download_is_skipped_without_vision_check() -> None:
    vision = FakeVision(grades_everything=perfect())
    resolver = a_resolver(
        search=FakeSearch([a_candidate(0), a_candidate(1)]),
        downloader=FakeDownloader(failing_urls=frozenset({a_candidate(0).image_url})),
        vision=vision,
    )

    figures = resolver.resolve({"s1": a_request()}, language="ru")

    assert figures["s1"] is not None
    assert figures["s1"].source_ref == a_candidate(1).file_page_url
    assert len(vision.calls) == 1


def test_without_perfect_commons_a_perfect_generated_figure_carries_the_ai_caption() -> None:
    generator = FakeGenerator()
    resolver = a_resolver(
        search=FakeSearch([a_candidate()]),
        generator=generator,
        vision=FakeVision({f"{IMAGES_DIR}/illustration_s1.png": perfect()}),
        config=IllustrationConfig(allow_generation=True),
    )

    figures = resolver.resolve({"s1": a_request()}, language="ru")

    figure = figures["s1"]
    assert figure is not None
    assert figure.provenance is FigureProvenance.GENERATED
    assert figure.source_ref == "generated:codex"
    assert figure.image_path == f"{IMAGES_DIR}/illustration_s1.png"
    assert figure.caption == (
        "Лучевая и локтевая кости, вид спереди "
        f"({GENERATED_CAPTION_LABEL_BY_LANGUAGE['ru']})"
    )
    assert generator.calls == [
        ("Educational illustration of the radius and ulna", IMAGES_DIR, "illustration_s1")
    ]


@pytest.mark.parametrize("language", ["en", "de"])
def test_generated_caption_label_falls_back_to_english(language: str) -> None:
    resolver = a_resolver(
        vision=FakeVision(grades_everything=perfect()),
        config=IllustrationConfig(allow_generation=True),
    )

    figures = resolver.resolve({"s1": a_request()}, language=language)

    assert figures["s1"] is not None
    assert figures["s1"].caption is not None
    assert figures["s1"].caption.endswith(f"({GENERATED_CAPTION_LABEL_BY_LANGUAGE['en']})")


def test_file_stem_is_derived_from_section_id_as_safe_name() -> None:
    generator = FakeGenerator()

    a_resolver(
        generator=generator,
        vision=FakeVision(grades_everything=perfect()),
        config=IllustrationConfig(allow_generation=True),
    ).resolve({"s1.2": a_request()}, language="ru")

    assert generator.calls[0][2] == "illustration_s1_2"


def test_generation_cap_drops_requests_beyond_configured_maximum() -> None:
    config = IllustrationConfig(allow_generation=True)
    generator = FakeGenerator()
    resolver = a_resolver(
        generator=generator,
        vision=FakeVision(grades_everything=perfect()),
        config=config,
    )
    requests = {
        f"s{index}": a_request() for index in range(config.max_generated_per_lecture + 1)
    }

    figures = resolver.resolve(requests, language="ru")

    assert len(generator.calls) == config.max_generated_per_lecture
    assert sum(figure is None for figure in figures.values()) == 1
    assert sum(figure is not None for figure in figures.values()) == config.max_generated_per_lecture


def test_everything_unsuitable_drops_request() -> None:
    resolver = a_resolver(search=FakeSearch([a_candidate()]), vision=FakeVision())

    figures = resolver.resolve({"s1": a_request()}, language="ru")

    assert figures == {"s1": None}


def test_unavailable_generator_without_suitable_commons_drops_request() -> None:
    resolver = a_resolver(
        generator=FakeGenerator(is_available=False),
        vision=FakeVision(grades_everything=perfect()),
        config=IllustrationConfig(allow_generation=True),
    )

    figures = resolver.resolve({"s1": a_request()}, language="ru")

    assert figures == {"s1": None}


def test_grading_stops_at_the_first_perfect_candidate() -> None:
    vision = FakeVision(grades_everything=perfect())
    resolver = a_resolver(search=FakeSearch([a_candidate(0), a_candidate(1)]), vision=vision)

    figures = resolver.resolve({"s1": a_request()}, language="ru")

    assert figures["s1"] is not None
    assert figures["s1"].source_ref == a_candidate(0).file_page_url
    assert len(vision.calls) == 1


def test_generation_disabled_takes_best_suitable_by_score_without_invoking_generator() -> None:
    generator = FakeGenerator()
    vision = FakeVision(
        {
            f"{IMAGES_DIR}/radius_ulna.jpg": suitable(55),
            f"{IMAGES_DIR}/radius_ulna1.jpg": suitable(70),
        }
    )
    resolver = a_resolver(
        search=FakeSearch([a_candidate(0), a_candidate(1)]),
        generator=generator,
        vision=vision,
    )

    figures = resolver.resolve({"s1": a_request()}, language="ru")

    assert figures["s1"] is not None
    assert figures["s1"].provenance is FigureProvenance.COMMONS
    assert figures["s1"].source_ref == a_candidate(1).file_page_url
    assert generator.calls == []


def test_equal_scores_keep_the_earlier_search_rank() -> None:
    vision = FakeVision(
        {
            f"{IMAGES_DIR}/radius_ulna.jpg": suitable(70),
            f"{IMAGES_DIR}/radius_ulna1.jpg": suitable(70),
        }
    )
    resolver = a_resolver(search=FakeSearch([a_candidate(0), a_candidate(1)]), vision=vision)

    figures = resolver.resolve({"s1": a_request()}, language="ru")

    assert figures["s1"] is not None
    assert figures["s1"].source_ref == a_candidate(0).file_page_url


def test_generated_below_perfect_falls_back_to_best_suitable_commons() -> None:
    vision = FakeVision(
        {
            f"{IMAGES_DIR}/radius_ulna.jpg": suitable(60),
            f"{IMAGES_DIR}/illustration_s1.png": suitable(84),
        }
    )
    resolver = a_resolver(
        search=FakeSearch([a_candidate()]),
        vision=vision,
        config=IllustrationConfig(allow_generation=True),
    )

    figures = resolver.resolve({"s1": a_request()}, language="ru")

    assert figures["s1"] is not None
    assert figures["s1"].provenance is FigureProvenance.COMMONS
    assert figures["s1"].source_ref == FILE_PAGE_URL


def test_vision_check_raising_counts_as_unconfirmed() -> None:
    resolver = a_resolver(
        search=FakeSearch([a_candidate()]), vision=FakeVision(error=RuntimeError("boom"))
    )

    figures = resolver.resolve({"s1": a_request()}, language="ru")

    assert figures == {"s1": None}


def test_search_failure_falls_through_to_generation_when_enabled() -> None:
    generator = FakeGenerator()
    resolver = a_resolver(
        search=FakeSearch(error=RuntimeError("network down")),
        generator=generator,
        vision=FakeVision(grades_everything=perfect()),
        config=IllustrationConfig(allow_generation=True),
    )

    figures = resolver.resolve({"s1": a_request()}, language="ru")

    assert figures["s1"] is not None
    assert figures["s1"].provenance is FigureProvenance.GENERATED
    assert len(generator.calls) == 1


def test_budget_exceeded_in_vision_check_propagates() -> None:
    resolver = a_resolver(
        search=FakeSearch([a_candidate()]),
        vision=FakeVision(error=BudgetExceededError(1.0, 1.0, 0.5)),
    )

    with pytest.raises(BudgetExceededError):
        resolver.resolve({"s1": a_request()}, language="ru")


def test_dropped_request_is_logged_with_reason() -> None:
    resolver = a_resolver(search=FakeSearch([a_candidate()]), vision=FakeVision())
    logger = logging.getLogger("konspekt.features.notes.application.resolve_illustrations")
    captured_records: list[logging.LogRecord] = []

    class RecordingHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            captured_records.append(record)

    handler = RecordingHandler()
    logger.addHandler(handler)
    try:
        resolver.resolve({"s1": a_request()}, language="ru")
    finally:
        logger.removeHandler(handler)

    assert len(captured_records) == 1
    assert captured_records[0].levelno == logging.WARNING
    assert captured_records[0].section_id == "s1"
    assert captured_records[0].reason == "no_candidate_at_least_suitable"


def test_empty_request_map_resolves_to_empty_result() -> None:
    assert a_resolver().resolve({}, language="ru") == {}
