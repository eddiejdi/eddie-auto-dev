# Training Run Results (extract_and_train.py) - 2026-01-22

Summary
- Script run: `extract_and_train.py` (with local `training_data` directory).
- Ollama host used: http://192.168.15.2:11434 (default `OLLAMA_HOST`).

Outcome
- No VS Code chat files were found for today; the script aborted early with
  message `❌ Nenhum chat encontrado hoje!`.
- No training model was created.

Next steps
- Provide training data under `training_data/` (repo root) named
  `training_YYYY-MM-DD.jsonl`, or place VS Code chat files in the expected
  locations and re-run the script.
- Alternatively, run a manual training flow by preparing a small JSONL file and
  POSTing a Modelfile to the Ollama `/api/create` endpoint as described in
  `docs/TRAINING_MODEL_SERVER.md`.

Logs
- Console output saved in terminal; re-run with `python3 extract_and_train.py`
  after placing training input files to reproduce.
