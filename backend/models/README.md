# Trained model weights

Not committed to git (see `.gitignore`) -- these are large binary artifacts,
trained outside this repo (Colab, `IBVAP_FireSmoke_ANPR_Training.ipynb`) and
bind-mounted into their services by `docker-compose.yml`.

To populate this folder on a fresh checkout, place:

- `fire_smoke_best.pt` -- YOLOv8s fine-tuned on the D-Fire dataset (fire/smoke).
  Used by `fire-smoke-service` when `USE_TRAINED_FIRE_SMOKE_MODEL=true`.
- `license_plate_best.pt` -- YOLOv8s fine-tuned on Roboflow's
  `license-plate-recognition-rxg4e` dataset. Used by `anpr-service` when
  `USE_TRAINED_PLATE_MODEL=true`.
- `fighting_classifier.pt` -- a small LSTM over 2-person MediaPipe pose-
  landmark sequences, trained on the Kaggle "Real Life Violence Situations"
  dataset. Used by `pose-service` when `USE_TRAINED_FIGHTING_MODEL=true`.
  Independent of, not a replacement for, event-alert-service's own
  proximity+erratic-motion fighting heuristic -- both can fire.

All three flags default to `false` (the original heuristic/classical path)
until you've placed the matching file here and verified it live -- no
service will fail to start if a file is missing, it just falls back.
