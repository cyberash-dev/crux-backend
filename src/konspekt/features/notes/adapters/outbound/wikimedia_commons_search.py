import logging
from collections.abc import Mapping, Sequence

import httpx

from konspekt.features.notes.ports.outbound.notes_llm import ImageCandidate

COMMONS_API_URL = "https://commons.wikimedia.org/w/api.php"
COMMONS_FILE_PAGE_PREFIX = "https://commons.wikimedia.org/wiki/"
USER_AGENT = "konspekt/0.1 (https://github.com/cyberash-dev/konspekt)"
THUMBNAIL_WIDTH = 1200

_RASTER_MIMES = frozenset({"image/jpeg", "image/png"})
_FILE_NAMESPACE = 6

_logger = logging.getLogger(__name__)


class WikimediaCommonsSearch:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client if client is not None else httpx.Client(
            follow_redirects=True, timeout=30.0, headers={"User-Agent": USER_AGENT}
        )

    def search(self, query: str, limit: int) -> Sequence[ImageCandidate]:
        try:
            response = self._client.get(
                COMMONS_API_URL,
                params=_search_params(query, limit),
                headers={"User-Agent": USER_AGENT},
            )
        except httpx.HTTPError as error:
            _logger.warning(
                "notes.commons_search_failed", extra={"query": query, "error": repr(error)}
            )
            return ()
        if response.status_code != 200:
            _logger.warning(
                "notes.commons_search_failed",
                extra={"query": query, "status_code": response.status_code},
            )
            return ()
        try:
            return _candidates(response.json())
        except (ValueError, KeyError, TypeError, AttributeError) as error:
            _logger.warning(
                "notes.commons_search_malformed", extra={"query": query, "error": repr(error)}
            )
            return ()


def _search_params(query: str, limit: int) -> dict[str, str | int]:
    return {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": query,
        "gsrnamespace": _FILE_NAMESPACE,
        "gsrlimit": limit,
        "prop": "imageinfo",
        "iiprop": "url|mime|size|extmetadata",
        "iiurlwidth": THUMBNAIL_WIDTH,
    }


def _candidates(payload: Mapping[str, object]) -> tuple[ImageCandidate, ...]:
    query = payload.get("query")
    if not isinstance(query, Mapping):
        return ()
    pages = query.get("pages")
    if not isinstance(pages, Mapping):
        return ()
    ordered_pages = sorted(pages.values(), key=lambda page: int(page.get("index", 0)))
    candidates: list[ImageCandidate] = []
    for page in ordered_pages:
        candidate = _candidate(page)
        if candidate is not None:
            candidates.append(candidate)
    return tuple(candidates)


def _candidate(page: Mapping[str, object]) -> ImageCandidate | None:
    image_infos = page.get("imageinfo")
    if not isinstance(image_infos, Sequence) or not image_infos:
        return None
    image_info = image_infos[0]
    if image_info.get("mime") not in _RASTER_MIMES:
        return None
    image_url = image_info.get("thumburl") or image_info.get("url")
    if not isinstance(image_url, str):
        return None
    title = str(page["title"])
    return ImageCandidate(
        file_page_url=COMMONS_FILE_PAGE_PREFIX + title.replace(" ", "_"),
        image_url=image_url,
    )
