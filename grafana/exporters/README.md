Eddie WhatsApp Prometheus exporter

Purpose
-------
Simple exporter that exposes training and inference metrics consumed by the Grafana dashboard `eddie-whatsapp-model.json`.

Metrics produced (expected keys in JSON file):
- `train_accuracy`, `val_accuracy`
- `train_loss`, `val_loss`
- `inference_requests_total` (cumulative count)
- `latency_p95` (seconds)
- `indexed_documents_total`
- `models` object mapping model name -> 1|0 (loaded)

Quick start
-----------
1. Install dependencies (on the server):

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

2. Run exporter (default ports 9102 metrics, 9103 push):

```bash
EXPORTER_METRICS_FILE=/var/lib/eddie/whatsapp_metrics.json \
RAG_API_URL=http://127.0.0.1:8001/api/v1/rag/context \
python3 eddie_whatsapp_exporter.py --port 9102 --push-port 9103
```

3. Configure Prometheus scrape job:

```yaml
- job_name: 'eddie_whatsapp'
  static_configs:
    - targets: ['192.168.15.2:9102']
```

4. Update Grafana datasource to point to that Prometheus, then import `grafana/dashboards/eddie-whatsapp-model.json`.

Updating metrics from training/serving
-------------------------------------
Your training/serve scripts should update the JSON file used by the exporter, e.g.:

```json
{
  "train_accuracy": 0.92,
  "val_accuracy": 0.90,
  "train_loss": 0.21,
  "val_loss": 0.23,
  "inference_requests_total": 12345,
  "latency_p95": 0.18,
  "indexed_documents_total": 78,
  "models": {"deepseek-coder-v2:16b": 1, "qwen2.5-coder:7b": 0}
}
```

Or push new metrics via HTTP POST:

```bash
curl -X POST http://192.168.15.2:9103/push -H 'Content-Type: application/json' -d @metrics.json
```

Systemd service example
-----------------------
Create `/etc/systemd/system/eddie-whatsapp-exporter.service` with:

```
[Unit]
Description=Eddie WhatsApp Prometheus Exporter
After=network.target

[Service]
User=homelab
WorkingDirectory=/home/homelab/eddie-auto-dev/grafana/exporters
Environment=EXPORTER_METRICS_FILE=/var/lib/eddie/whatsapp_metrics.json
ExecStart=/home/homelab/venv/bin/python3 eddie_whatsapp_exporter.py --port 9102 --push-port 9103
Restart=always

[Install]
WantedBy=multi-user.target
```

Then enable:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now eddie-whatsapp-exporter
sudo journalctl -u eddie-whatsapp-exporter -f
```

Notes
-----
- The exporter is intentionally simple: it reads a JSON state file (atomic write) and exposes the supplied values as Prometheus metrics.
- If you prefer a push gateway workflow, you can adapt the scripts to push via the `/push` endpoint or directly push to Prometheus Pushgateway.
