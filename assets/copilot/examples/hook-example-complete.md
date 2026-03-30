# Hook Example

Arquivo exemplo: `.github/hooks/example-post-edit.json`

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "type": "command",
        "command": "python tools/copilot_hooks/example.py",
        "timeout": 15
      }
    ]
  }
}
```

Use este formato quando precisar automatizar validacoes ou enriquecimento de contexto apos uso de ferramenta.
