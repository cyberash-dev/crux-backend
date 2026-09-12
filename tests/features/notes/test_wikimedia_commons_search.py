# @covers analysis:EXT-012
import json
from urllib.parse import parse_qs

import httpx

from konspekt.features.notes.adapters.outbound.wikimedia_commons_search import (
    WikimediaCommonsSearch,
)
from konspekt.features.notes.ports.outbound.notes_llm import ImageCandidate


def a_page(
    page_id: int,
    index: int,
    title: str,
    mime: str,
    thumb_url: str | None = "https://upload.wikimedia.org/thumb/1200px-x.jpg",
) -> dict[str, object]:
    image_info: dict[str, object] = {
        "url": "https://upload.wikimedia.org/x.jpg",
        "mime": mime,
        "width": 3000,
        "height": 2000,
        "extmetadata": {"LicenseShortName": {"value": "CC BY-SA 4.0"}},
    }
    if thumb_url is not None:
        image_info["thumburl"] = thumb_url
    return {
        "pageid": page_id,
        "ns": 6,
        "title": title,
        "index": index,
        "imageinfo": [image_info],
    }


def a_recorded_response() -> dict[str, object]:
    return {
        "batchcomplete": "",
        "query": {
            "pages": {
                "30": a_page(30, 2, "File:Ulna and radius.png", "image/png", thumb_url=None),
                "10": a_page(10, 1, "File:Radius ulna anterior.jpg", "image/jpeg"),
                "20": a_page(20, 3, "File:Radius diagram.svg", "image/svg+xml"),
            }
        },
    }


class RecordingTransport:
    def __init__(self, response: httpx.Response | Exception) -> None:
        self.requests: list[httpx.Request] = []
        self._response = response

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


def a_search(transport: RecordingTransport) -> WikimediaCommonsSearch:
    return WikimediaCommonsSearch(
        client=httpx.Client(transport=httpx.MockTransport(transport.handler))
    )


def test_recorded_response_is_mapped_to_raster_candidates_in_index_order() -> None:
    transport = RecordingTransport(httpx.Response(200, json=a_recorded_response()))

    candidates = a_search(transport).search("radius ulna bones anterior view", limit=3)

    assert list(candidates) == [
        ImageCandidate(
            file_page_url="https://commons.wikimedia.org/wiki/File:Radius_ulna_anterior.jpg",
            image_url="https://upload.wikimedia.org/thumb/1200px-x.jpg",
        ),
        ImageCandidate(
            file_page_url="https://commons.wikimedia.org/wiki/File:Ulna_and_radius.png",
            image_url="https://upload.wikimedia.org/x.jpg",
        ),
    ]


def test_request_follows_the_consumer_contract() -> None:
    transport = RecordingTransport(httpx.Response(200, json=a_recorded_response()))

    a_search(transport).search("radius ulna", limit=3)

    request = transport.requests[0]
    assert request.method == "GET"
    assert request.url.scheme == "https"
    assert request.url.host == "commons.wikimedia.org"
    assert request.url.path == "/w/api.php"
    params = parse_qs(request.url.query.decode())
    assert params["action"] == ["query"]
    assert params["format"] == ["json"]
    assert params["generator"] == ["search"]
    assert params["gsrsearch"] == ["radius ulna"]
    assert params["gsrnamespace"] == ["6"]
    assert params["gsrlimit"] == ["3"]
    assert params["prop"] == ["imageinfo"]
    assert params["iiprop"] == ["url|mime|size|extmetadata"]
    assert params["iiurlwidth"] == ["1200"]
    assert request.headers["user-agent"] == "konspekt/0.1 (https://github.com/cyberash-dev/konspekt)"


def test_non_200_response_yields_no_candidates() -> None:
    transport = RecordingTransport(httpx.Response(503, text="unavailable"))

    candidates = a_search(transport).search("radius ulna", limit=3)

    assert list(candidates) == []


def test_malformed_json_yields_no_candidates() -> None:
    transport = RecordingTransport(httpx.Response(200, text="<html>not json</html>"))

    candidates = a_search(transport).search("radius ulna", limit=3)

    assert list(candidates) == []


def test_payload_without_pages_yields_no_candidates() -> None:
    transport = RecordingTransport(httpx.Response(200, json={"batchcomplete": ""}))

    candidates = a_search(transport).search("radius ulna", limit=3)

    assert list(candidates) == []


def test_network_error_yields_no_candidates() -> None:
    transport = RecordingTransport(httpx.ConnectError("connection refused"))

    candidates = a_search(transport).search("radius ulna", limit=3)

    assert list(candidates) == []


def test_page_without_imageinfo_is_skipped() -> None:
    payload = a_recorded_response()
    payload["query"]["pages"]["10"].pop("imageinfo")
    transport = RecordingTransport(httpx.Response(200, content=json.dumps(payload).encode()))

    candidates = a_search(transport).search("radius ulna", limit=3)

    assert [candidate.file_page_url for candidate in candidates] == [
        "https://commons.wikimedia.org/wiki/File:Ulna_and_radius.png"
    ]
