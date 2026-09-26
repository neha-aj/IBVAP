"""Trained fighting-detection model: a small LSTM over a short window of
two people's pose-joint sequences, fine-tuned separately from this
codebase (Colab, on the Kaggle "Real Life Violence Situations" dataset via
extracted MediaPipe landmarks). This runs alongside, not instead of,
event-alert-service's own proximity+erratic-motion heuristic
(`rules/fighting.py`) -- the two are independent signals from two
different services, each capable of firing "Fighting Detected" on its own;
if this trained detector is disabled or its weights file is missing, the
heuristic is unaffected and keeps working exactly as before.

Why this lives in pose-service, not event-alert-service: the raw per-joint
landmark data this model needs only exists here, where MediaPipe already
computes it -- event-alert-service only ever sees reduced track
bounding-boxes, never joint geometry. Threading raw landmarks through
Redis into event-alert-service just to run a model would mean carrying a
much larger payload per frame for every consumer, for a capability only
this one detector needs.

Known simplification, disclosed rather than hidden: the training data
paired at most 2 people per clip, sorted left-to-right, sampled evenly
across each ~seconds-long clip. Live, there's no per-pair track identity
here (pose-service doesn't consume tracking-service's track ids at all --
see reconcile_manager.py's own docstring on why), so this instead buffers
whichever 2 people are currently closest together in each sampled frame
(pose-service's own `sample_interval_seconds`, not the training clips'
frame rate) into a per-camera rolling window, re-evaluating who
"currently closest" is every tick. If the closest pair changes identity
between sampled frames, the sequence buffer mixes two different pairs --
a real, accepted approximation gap between the training distribution and
this live input, not a bug."""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable

import numpy as np

from ibvap_common.logging import get_logger

from app.schemas.pose import PoseReading
from app.streaming.event_client import EventClient

logger = get_logger(__name__)

_LANDMARK_COUNT = 33
_FEATURES_PER_PERSON = _LANDMARK_COUNT * 3


class _FightingClassifierNet:
    """Deferred torch import, same reasoning as PoseLandmarkerModel's
    deferred mediapipe import -- importing this module must not require
    torch to be installed unless a TrainedFightingDetector is actually
    constructed."""

    def __new__(cls, *, input_size: int, hidden_size: int):
        import torch.nn as nn

        class FightingClassifier(nn.Module):
            def __init__(self) -> None:
                super().__init__()
                self.lstm = nn.LSTM(input_size, hidden_size, batch_first=True)
                self.fc = nn.Linear(hidden_size, 2)

            def forward(self, x):
                _, (h_n, _) = self.lstm(x)
                return self.fc(h_n[-1])

        return FightingClassifier()


def _pair_distance(a: PoseReading, b: PoseReading) -> float:
    return float(((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5)


def select_closest_pair(readings: list[PoseReading], *, proximity_threshold: float) -> tuple[int, int] | None:
    """Pure, torch-free: the indices (left, right -- sorted by x to match
    the training data's own ordering convention) of the two currently-
    closest readings, or None if fewer than two people are present or
    nobody is within `proximity_threshold`. Split out from
    TrainedFightingDetector.check so this selection logic is unit-testable
    without a real model checkpoint."""
    if len(readings) < 2:
        return None
    best_pair: tuple[int, int] | None = None
    best_distance = proximity_threshold
    for i in range(len(readings)):
        for j in range(i + 1, len(readings)):
            distance = _pair_distance(readings[i], readings[j])
            if distance <= best_distance:
                best_distance = distance
                best_pair = (i, j)
    if best_pair is None:
        return None
    i, j = best_pair
    return (j, i) if readings[j].x < readings[i].x else (i, j)


class TrainedFightingDetector:
    """One shared instance across every camera (unlike PoseLandmarkerModel,
    one per camera for MediaPipe's own threading reasons -- see
    reconcile_manager.py) -- loading the same small LSTM weights per camera
    would be pure waste, and torch inference here has none of MediaPipe's
    per-instance-per-thread constraint."""

    def __init__(
        self,
        *,
        model_path: str,
        seq_len: int,
        pair_proximity_threshold: float,
        confidence_threshold: float,
        cooldown_seconds: float,
        event_client: EventClient,
        now: Callable[[], float] = time.monotonic,
    ) -> None:
        import torch

        checkpoint = torch.load(model_path, map_location="cpu", weights_only=False)
        input_size = checkpoint["input_size"]
        self._seq_len = checkpoint.get("seq_len", seq_len)
        hidden_size = checkpoint["state_dict"]["lstm.weight_hh_l0"].shape[1]

        self._torch = torch
        self._model = _FightingClassifierNet(input_size=input_size, hidden_size=hidden_size)
        self._model.load_state_dict(checkpoint["state_dict"])
        self._model.eval()

        self._pair_proximity_threshold = pair_proximity_threshold
        self._confidence_threshold = confidence_threshold
        self._cooldown_seconds = cooldown_seconds
        self._event_client = event_client
        self._now = now

        self._buffers: dict[str, deque[np.ndarray]] = {}
        self._last_alert_at: dict[str, float] = {}

    async def check(self, camera_id: str, readings: list[PoseReading], landmarks: list[np.ndarray]) -> None:
        pair = select_closest_pair(readings, proximity_threshold=self._pair_proximity_threshold)
        if pair is None:
            return  # fewer than two people, or nobody close enough right now
        i, j = pair
        frame_vector = np.concatenate([landmarks[i], landmarks[j]])

        buffer = self._buffers.setdefault(camera_id, deque(maxlen=self._seq_len))
        buffer.append(frame_vector)
        if len(buffer) < self._seq_len:
            return

        sequence = np.stack(buffer)
        with self._torch.no_grad():
            logits = self._model(self._torch.tensor(sequence).unsqueeze(0).float())
            probabilities = self._torch.softmax(logits, dim=1)[0]
            fighting_confidence = float(probabilities[1])

        if fighting_confidence < self._confidence_threshold:
            return

        now = self._now()
        last = self._last_alert_at.get(camera_id)
        if last is not None and (now - last) < self._cooldown_seconds:
            return
        self._last_alert_at[camera_id] = now

        await self._event_client.report_fighting(camera_id=camera_id, confidence=fighting_confidence)
        logger.info("fighting_trained_model_fired", camera_id=camera_id, confidence=round(fighting_confidence, 4))


def load_if_enabled(
    *,
    model_path: str,
    seq_len: int,
    pair_proximity_threshold: float,
    confidence_threshold: float,
    cooldown_seconds: float,
    event_client: EventClient,
) -> TrainedFightingDetector | None:
    """Best-effort: a missing/corrupt weights file must not stop the
    service from starting -- it just means this detector never fires,
    same graceful-degradation shape as fire-smoke-service's and
    anpr-service's own trained-model loaders."""
    try:
        detector = TrainedFightingDetector(
            model_path=model_path,
            seq_len=seq_len,
            pair_proximity_threshold=pair_proximity_threshold,
            confidence_threshold=confidence_threshold,
            cooldown_seconds=cooldown_seconds,
            event_client=event_client,
        )
        logger.info("fighting_trained_model_loaded", model_path=model_path)
        return detector
    except Exception as exc:  # noqa: BLE001 -- any load failure disables this detector, never crashes startup
        logger.warning("fighting_trained_model_load_failed", model_path=model_path, error=str(exc))
        return None
