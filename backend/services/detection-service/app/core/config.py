from functools import lru_cache

from ibvap_common.settings import CommonSettings


class Settings(CommonSettings):
    service_name: str = "detection-service"

    # Camera Management Service (M2) -- source of truth for which cameras
    # exist, used the same way Ingestion (M3) discovers cameras to open.
    camera_service_url: str = "http://camera-service:8000"
    camera_refresh_interval_seconds: int = 15

    # Redis Streams consumer group (SAS §5.2, §11 at-least-once processing).
    consumer_group_name: str = "detection-service"
    frames_read_count: int = 5
    frames_block_ms: int = 2000

    # How many entries to keep per `cam:{id}:detections` stream before
    # trimming (SAS §11 backpressure), mirroring ingestion's frame_stream_maxlen.
    detections_stream_maxlen: int = 500

    # TTL on the `cam:{id}:current_detections` cache key that powers
    # `GET /cameras/{id}/detections/current` and the live overlay -- short
    # enough that a stalled/offline camera's overlay clears itself rather
    # than showing stale boxes forever.
    current_detections_ttl_seconds: int = 5

    # Inference tuning. Ultralytics downloads this on first use if missing --
    # pointed at the mounted `detection-models` volume (docker-compose.yml)
    # so the ~6MB download survives container recreation.
    # yolov8s (small) over the default yolov8n (nano) -- meaningfully better
    # recall on small/distant objects (e.g. a background vehicle) at a still
    # CPU-feasible cost for this low-fps pipeline.
    model_path: str = "/srv/models/yolov8s.pt"
    confidence_threshold: float = 0.4
    # Backend selection: "onnx" requires an exported .onnx at `onnx_model_path`
    # and the optional `onnx` dependency group; otherwise falls back to the
    # Ultralytics/torch runner (GPU if available, else CPU) -- SAS §3/§9
    # "GPU if available, ONNX Runtime CPU fallback".
    inference_backend: str = "auto"
    onnx_model_path: str = "/srv/models/yolov8n.onnx"
    onnx_input_size: int = 640


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
