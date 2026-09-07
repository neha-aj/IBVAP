"""Read-only shape for `GET /cameras/{id}/detections/current` (API Spec §2).

Mirrors `detection-service/app/schemas/detection.py` field-for-field -- per
Implementation Guide §3 ("no service imports another service's package"),
each service that needs this shape defines its own copy rather than a
cross-service import; `ibvap_common` is the only shared code path, and this
shape is specific to the detection pipeline's contract, not cross-cutting
infra, so it doesn't belong there.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict

# "animal" added Phase 2 M21.
DetectionType = Literal["person", "vehicle", "animal"]


class _CamelModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class BoundingBox(_CamelModel):
    x: float
    y: float
    width: float
    height: float


class DetectionRead(_CamelModel):
    id: str
    cameraId: str
    type: DetectionType
    confidence: float
    trackId: str | None = None
    bbox: BoundingBox
