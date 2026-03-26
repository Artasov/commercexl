from __future__ import annotations

from typing import Protocol


class MediaRequestLike(Protocol):
    def url_for(self, name: str, **path_params: object) -> str: ...


def build_media_url(
        request: MediaRequestLike | None,
        value: str | None,
        *,
        media_url: str = "/media",
) -> str | None:
    if not value:
        return None
    normalized = value if value.startswith("/") else f"{media_url.rstrip('/')}/{value}"
    if request is None:
        return normalized
    try:
        return str(request.url_for("media", path=value))
    except Exception:
        return normalized
