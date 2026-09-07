import asyncio

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from ibvap_common.stream_auth import verify_resource_token

from app.core.config import Settings, get_settings
from app.preview.frame_cache import frame_cache

router = APIRouter(tags=["preview"])

_BOUNDARY = "ibvapframe"


async def _mjpeg_generator(camera_id: str):
    while True:
        jpeg_bytes = await frame_cache.get(camera_id)
        if jpeg_bytes is not None:
            yield (
                f"--{_BOUNDARY}\r\n"
                "Content-Type: image/jpeg\r\n"
                f"Content-Length: {len(jpeg_bytes)}\r\n\r\n"
            ).encode() + jpeg_bytes + b"\r\n"
        await asyncio.sleep(0.1)  # ~10fps preview regardless of source fps


@router.get("/stream/{camera_id}/mjpeg")
async def mjpeg_stream(
    camera_id: str,
    token: str | None = Query(default=None),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    """Live preview for the Surveillance page's `VideoPlaceholder` slot
    (Frontend Analysis Report §3.2) -- an `<img src=".../mjpeg">` renders
    this directly, no video player library required.

    `token` (M24 security review): this route can't require the usual
    `Authorization` header (an `<img>` tag can't send one), so it instead
    requires the short-lived signed token that `GET /cameras/{id}/stream`
    -- which *is* gated by `require_role` -- mints and embeds in the URL
    it hands out. Without this, the stream was reachable by anyone who
    had (or guessed) a camera_id, regardless of role."""
    verify_resource_token(token, resource=camera_id, settings=settings)
    return StreamingResponse(
        _mjpeg_generator(camera_id),
        media_type=f"multipart/x-mixed-replace; boundary={_BOUNDARY}",
    )
