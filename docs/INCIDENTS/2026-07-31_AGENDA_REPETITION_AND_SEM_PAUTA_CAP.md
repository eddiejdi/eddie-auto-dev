# 2026-07-31 — Agenda Diária: eco de data / 1h forçada em SEM_PAUTA

**Severidade:** média (qualidade editorial; publicação inicial inadequada)  
**Domínio:** agenda diária / TTS / Telegram / YouTube  
**Status:** mitigado e regenerado; publicado após correção  

---

## Sintoma

Prévia regenerada via Telegram (~09:40) com:

- **~46 min** de áudio (`locution.wav` ~116 MB)
- **Data** (“sexta-feira, 31 de julho de 2026” / “trinta e um de julho…”) em **quase todo bloco** (~17× no STT, ~29× no script)
- **“Sem compromissos formais”** ecoado **~27×** (STT)
- Quase **zero silêncio** entre blocos (bed sob fala; parede contínua)
- Source do dia com **~66 palavras** de fato real (sem pauta formal + itens Direita Já)
- Expansão textual **~64×** sobre a fonte

Usuário: *“gerou muito conteúdo e expressões repetidas, cada bloco está repetindo a data”*.

Não havia botão **Rejeitar/descartar** no Telegram — só Aprovar e Gerar de novo.

---

## Diagnóstico

### Causa raiz

1. `classify_source_mode` → **SEM_PAUTA** (correto).
2. Plano modular ainda usava meta de **3600 s** → **20 segmentos × ~180 s**.
3. Com áudio &lt; 1 h, `max_length_retries` gerava **segments_extra** (mais ~11 blocos) com o **mesmo template** (reabertura + data + âncora).
4. Prompts de segmento **não proibiam** repetir a data; cada bloco re-incluía o `source.txt` completo.
5. Mesa de Editor em SEM_PAUTA **preservava volume** (piso 72%) em vez de cortar eco.
6. Cues: vazamento residual (`{{`, “Pause 2” ouvido no STT em trecho da edição longa).

### Confirmação por STT (GPU0, faster-whisper small)

- Host: `192.168.15.2`, CUDA float16, modelo ao lado do residual trading (~+750 MiB).
- Duração STT: **45,9 min** · 637 segmentos · gaps VAD ≥0,8 s: **1** (0,88 s).
- N-gram top: `sexta feira 31 de julho de` **12×**.
- Artefatos: `artifacts/daily_agenda/2026-07-31/qa/{transcript.txt,qa_report.md}`.

### Painel

Regeneração via Telegram **não aparecia** em `:8093` até existir `POST /api/job/report` + `PanelJobReporter` no broadcast (jobs só do `/api/run` eram visíveis).

---

## Mitigação (código)

| Área | Mudança |
|------|---------|
| SEM_PAUTA | `sem_pauta_max_duration_seconds=720`, `sem_pauta_max_segments=6` |
| Extras | `sem_pauta_allow_extras=false` (default) |
| Data | prompt + `strip_date_echo` só abertura |
| Âncora | `strip_redundant_no_agenda_opener` nos blocos 2+ |
| TTS | strip `Pause N` / `{{` residual |
| Pausas | gap 1,5 s · pause entre blocos 2,0 s |
| Telegram | botão **⏹️ Não publicar / descartar** (`dag:X:`) |
| Painel | `daily_agenda_job_status.PanelJobReporter` + `/api/job/report` |

Arquivos principais:

- `tools/daily_agenda_segments.py`
- `tools/daily_agenda_config.py`
- `tools/daily_agenda_approval.py`
- `tools/run_daily_agenda_broadcast.py`
- `tools/daily_agenda_job_status.py`
- `tools/test_cpu_tts_from_generated_text.py`
- `scripts/daily_agenda_panel_server.py`

Runbook: `docs/DAILY_AGENDA_BROADCAST.md`.

---

## Regeneração e publicação

| Campo | Valor |
|-------|--------|
| Start regen com fixes | ~2026-07-31 12:33 (workstation) |
| Log | `/tmp/daily_agenda_fixed_2026-07-31.log` |
| Plano | `mode=sem_pauta`, **4 segmentos**, alvo **720 s** |
| Áudio final | **~5,0 min** (303 s) |
| Data no spoken | **1×** |
| “Sem compromissos” | **1×** |
| Prévia Telegram | ~12:59 (msgs 19725 / 19726) |
| Aprovação | @Eddiejdi **13:06** |
| YouTube | https://www.youtube.com/watch?v=O6v6H28gsiU |
| `publish_meta.json` | `O6v6H28gsiU` · título *Agenda Diária — Flávio Bolsonaro — 31/07/2026* |

Nota: o áudio ficou **abaixo do teto 720 s** (modelos curtos + validadores), o que é preferível ao eco de 46 min.

---

## Lições

1. **SEM_PAUTA ≠ preencher 1 h** — teto curto e proibição de extras são obrigatórios.
2. **Fonte curta + N segmentos longos** = alucinação/padding; medir densidade (palavras faladas / palavras do source).
3. **Aprovação** precisa de **descartar**, não só republicar/regenerar.
4. **Observabilidade**: jobs de Telegram/systemd devem reportar ao painel (`DAILY_AGENDA_PANEL_URL`).
5. QA de áudio (STT na GPU) é barato o bastante para validar eco de data antes de publicar.

---

## Follow-ups (opcional)

- [ ] Editor SEM_PAUTA: em vez de “preservar rascunho” por piso de palavras, **cortar eco** (data / no-agenda / geo).
- [ ] Bloquear publicação se STT/heurística detectar data &gt; 2× ou no-agenda &gt; 3×.
- [ ] Timer systemd de broadcast no host certo + reporter sempre ativo.
- [ ] Cache faster-whisper no homelab para QA recorrente.
