# Changelog (extra)

## 2026-02-02

- Fix: systemd `Environment` with percent-signs in `DATABASE_URL` must escape `%` as `%%`. See `docs/operacoes/diretor-systemd-override.md` for details and remediation steps. This resolves the `Failed to resolve specifiers` error that prevented the `diretor` agent from polling the DB.
