# IBVAP

Intelligent Border Video Analytics Platform -- a full-stack surveillance/video-analytics system: a microservices backend (detection, tracking, ANPR, PPE, fire/smoke, tamper, person/vehicle re-identification, rules-based alerting) plus a React frontend (live surveillance, alerts, events, analytics dashboards).

This repo is a combined, point-in-time snapshot of two actively-developed repos, published here as a single copy to share:

- **[`backend/`](backend/)** -- the microservices backend. See [`backend/README.md`](backend/README.md) for architecture, setup, and how to run the whole stack with `docker compose up`.
- **[`frontend/`](frontend/)** -- the React frontend. See [`frontend/README.md`](frontend/README.md) to run it against the backend.

Each folder is self-contained with its own dependencies and its own README -- start there.
