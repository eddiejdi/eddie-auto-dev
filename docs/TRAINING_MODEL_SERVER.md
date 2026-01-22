# Training Run — Model Server (Ollama)

Overview
- This document records the training run performed on the model server (Ollama).
- Script used: `extract_and_train.py` (root of repo).
- Ollama host: `http://192.168.15.2:11434` (configure `OLLAMA_HOST` env if different).

What I ran
1. Collected chat sessions (VS Code Copilot chat) and created a JSONL training
   file in `/home/homelab/myClaude/training_data/`.
2. Generated a Modelfile with contextual system prompt summarizing recent
   interactions.
3. Called Ollama's `/api/create` endpoint to create a new model named
   `eddie-assistant:YYYY-MM-DD` (date of run).

How to reproduce
- Ensure `extract_and_train.py` has access to chat files or prepare a
  `training_YYYY-MM-DD.jsonl` in `/home/homelab/myClaude/training_data/`.
- Run locally:

```bash
python3 extract_and_train.py
```

Notes
- If no VS Code chat files are found, the script will abort early; provide
  training data manually when needed.
- The training step depends on Ollama being reachable at `OLLAMA_HOST`.

Next steps
- Validate the newly created model with representative prompts.
- Add the model to local runbooks and to `specialized_agents` config where
  models are referenced.
- Consider adding a nightly job to extract and refresh model context with
  explicit retention and data governance policies.
