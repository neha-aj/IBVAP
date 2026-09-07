from ibvap_common.errors import ApiError

from app.capture.base import FrameSource
from app.capture.file_source import FileFrameSource
from app.capture.rtsp_source import RtspFrameSource
from app.capture.webcam_source import WebcamFrameSource
from app.core.config import Settings


def build_frame_source(
    *, camera_type: str, source_url: str | None, settings: Settings, initial_generation: int = 0
) -> FrameSource:
    if camera_type == "file":
        if not source_url:
            raise ApiError(status_code=422, title="Camera has no uploaded file yet")
        return FileFrameSource(source_url, loop=settings.loop_file_sources, initial_generation=initial_generation)

    if camera_type in ("webcam", "usb"):
        if not source_url:
            raise ApiError(status_code=422, title="Camera has no device source configured")
        return WebcamFrameSource(source_url, target_fps=float(settings.capture_fps))

    if camera_type in ("rtsp", "ip"):
        if not source_url:
            raise ApiError(status_code=422, title="Camera has no stream URL configured")
        return RtspFrameSource(source_url, target_fps=float(settings.capture_fps))

    raise ApiError(status_code=422, title=f"Unsupported camera type '{camera_type}'")
