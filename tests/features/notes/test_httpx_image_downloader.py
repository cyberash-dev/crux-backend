# @covers analysis:REQ-024
import hashlib
from pathlib import Path

import httpx

from konspekt.features.notes.adapters.outbound.httpx_image_downloader import (
    MAX_IMAGE_BYTES,
    USER_AGENT,
    HttpxExternalImages,
)

PNG_BYTES = b"\x89PNG\r\n\x1a\nfakepixels"
IMAGE_URL = "https://example.com/diagram.png"


def a_downloader_returning(response: httpx.Response) -> HttpxExternalImages:
    def handler(request: httpx.Request) -> httpx.Response:
        return response

    return HttpxExternalImages(client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_png_is_stored_under_sha256_name(tmp_path: Path) -> None:
    downloader = a_downloader_returning(
        httpx.Response(200, headers={"content-type": "image/png"}, content=PNG_BYTES)
    )

    stored_path = downloader.download(IMAGE_URL, str(tmp_path))

    expected_name = hashlib.sha256(IMAGE_URL.encode()).hexdigest() + ".png"
    assert stored_path == str(tmp_path / expected_name)
    assert Path(stored_path).read_bytes() == PNG_BYTES


def test_jpeg_gets_jpg_extension(tmp_path: Path) -> None:
    downloader = a_downloader_returning(
        httpx.Response(200, headers={"content-type": "image/jpeg"}, content=b"jpegdata")
    )

    stored_path = downloader.download(IMAGE_URL, str(tmp_path))

    assert stored_path is not None
    assert stored_path.endswith(".jpg")


def test_non_image_content_type_returns_none(tmp_path: Path) -> None:
    downloader = a_downloader_returning(
        httpx.Response(200, headers={"content-type": "text/html"}, content=b"<html></html>")
    )

    stored_path = downloader.download(IMAGE_URL, str(tmp_path))

    assert stored_path is None
    assert list(tmp_path.iterdir()) == []


def test_oversized_body_returns_none(tmp_path: Path) -> None:
    downloader = a_downloader_returning(
        httpx.Response(
            200,
            headers={"content-type": "image/png"},
            content=b"0" * (MAX_IMAGE_BYTES + 1),
        )
    )

    stored_path = downloader.download(IMAGE_URL, str(tmp_path))

    assert stored_path is None


def test_http_error_status_returns_none(tmp_path: Path) -> None:
    downloader = a_downloader_returning(
        httpx.Response(404, headers={"content-type": "image/png"}, content=b"")
    )

    stored_path = downloader.download(IMAGE_URL, str(tmp_path))

    assert stored_path is None


def test_network_error_returns_none(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    downloader = HttpxExternalImages(
        client=httpx.Client(transport=httpx.MockTransport(handler))
    )

    stored_path = downloader.download(IMAGE_URL, str(tmp_path))

    assert stored_path is None


def test_download_sends_a_descriptive_user_agent(tmp_path: Path) -> None:
    seen_user_agents: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_user_agents.append(request.headers.get("user-agent", ""))
        return httpx.Response(200, content=PNG_BYTES, headers={"content-type": "image/png"})

    downloader = HttpxExternalImages(
        client=httpx.Client(transport=httpx.MockTransport(handler))
    )

    downloader.download(IMAGE_URL, str(tmp_path))

    assert seen_user_agents == [USER_AGENT]
