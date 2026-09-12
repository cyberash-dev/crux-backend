import hashlib
from pathlib import Path

import httpx

MAX_IMAGE_BYTES = 10 * 1024 * 1024
USER_AGENT = "konspekt/0.1 (https://github.com/cyberash-dev/konspekt)"

_EXTENSION_BY_CONTENT_TYPE = {"image/png": ".png", "image/jpeg": ".jpg"}


class HttpxExternalImages:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client if client is not None else httpx.Client(
            follow_redirects=True, timeout=30.0
        )

    def download(self, image_url: str, dest_dir: str) -> str | None:
        try:
            response = self._client.get(image_url, headers={"User-Agent": USER_AGENT})
        except httpx.HTTPError:
            return None
        if response.status_code != 200:
            return None
        content_type = response.headers.get("content-type", "").split(";")[0].strip()
        extension = _EXTENSION_BY_CONTENT_TYPE.get(content_type)
        if extension is None:
            return None
        if len(response.content) > MAX_IMAGE_BYTES:
            return None
        file_name = hashlib.sha256(image_url.encode()).hexdigest() + extension
        stored_path = Path(dest_dir) / file_name
        stored_path.write_bytes(response.content)
        return str(stored_path)
