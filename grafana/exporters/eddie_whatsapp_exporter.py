#!/usr/bin/env python3
"""Prometheus exporter for Eddie_whatsapp model metrics.

Usage:
  EXPORTER_METRICS_FILE=/var/lib/eddie/whatsapp_metrics.json \
  RAG_API_URL=http://127.0.0.1:8001/api/v1/rag/context \
  python3 eddie_whatsapp_exporter.py --port 9102

This exporter reads a JSON metrics file (written by your training/serving scripts)
and exposes the following metrics (names expected by the Grafana dashboard):
- eddie_whatsapp_train_accuracy (gauge)
- eddie_whatsapp_val_accuracy (gauge)
- eddie_whatsapp_train_loss (gauge)
- eddie_whatsapp_val_loss (gauge)
- eddie_whatsapp_inference_requests_total (counter)
- eddie_whatsapp_latency_seconds (summary / gauge for p95 provided)
- eddie_whatsapp_indexed_documents_total (gauge)
- eddie_whatsapp_model_loaded (gauge by model)

Also provides a simple HTTP push endpoint (/push) to update the metrics file atomically.
"""

import argparse
import json
import logging
import os
import signal
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from io import BytesIO
from typing import Dict

import requests
from prometheus_client import start_http_server
from prometheus_client.core import GaugeMetricFamily, CounterMetricFamily, REGISTRY

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

METRICS_FILE_DEFAULT = os.environ.get(
    "EXPORTER_METRICS_FILE",
    "/var/lib/eddie/whatsapp_metrics.json",
)
RAG_API_URL = os.environ.get("RAG_API_URL")
PORT_DEFAULT = int(os.environ.get("EXPORTER_PORT", "9102"))


class EddieWhatsappCollector:
    def __init__(self, metrics_path: str, rag_api_url: str = None):
        self.metrics_path = metrics_path
        self.rag_api_url = rag_api_url

    def load_metrics(self) -> Dict:
        data = {}
        try:
            if os.path.exists(self.metrics_path):
                with open(self.metrics_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            else:
                logging.debug("metrics file not found: %s", self.metrics_path)
        except Exception:
            logging.exception("failed reading metrics file")
        # optionally query RAG API for indexed documents if available
        if self.rag_api_url and not data.get("indexed_documents_total"):
            try:
                resp = requests.get(self.rag_api_url, params={"query": "__internal_count_docs__", "n_results": 1}, timeout=5)
                if resp.ok:
                    j = resp.json()
                    # expect j to include a top-level count or similar; this is best-effort
                    if isinstance(j, dict) and j.get("count") is not None:
                        data["indexed_documents_total"] = int(j.get("count"))
            except Exception:
                logging.debug("rag query failed")
        return data

    def collect(self):
        metrics = self.load_metrics()
        # Gauges
        g_train_acc = GaugeMetricFamily("eddie_whatsapp_train_accuracy", "Training accuracy", value=metrics.get("train_accuracy", 0.0))
        g_val_acc = GaugeMetricFamily("eddie_whatsapp_val_accuracy", "Validation accuracy", value=metrics.get("val_accuracy", 0.0))
        g_train_loss = GaugeMetricFamily("eddie_whatsapp_train_loss", "Training loss", value=metrics.get("train_loss", 0.0))
        g_val_loss = GaugeMetricFamily("eddie_whatsapp_val_loss", "Validation loss", value=metrics.get("val_loss", 0.0))
        g_indexed = GaugeMetricFamily("eddie_whatsapp_indexed_documents_total", "Indexed documents total", value=metrics.get("indexed_documents_total", 0))

        yield g_train_acc
        yield g_val_acc
        yield g_train_loss
        yield g_val_loss
        yield g_indexed

        # Counter (expose as CounterMetricFamily with single sample)
        try:
            reqs = int(metrics.get("inference_requests_total", 0))
        except Exception:
            reqs = 0
        c_reqs = CounterMetricFamily("eddie_whatsapp_inference_requests_total", "Total inference requests", value=reqs)
        yield c_reqs

        # Latency: expose p95 as gauge seconds
        try:
            p95 = float(metrics.get("latency_p95", 0.0))
        except Exception:
            p95 = 0.0
        g_lat_p95 = GaugeMetricFamily("eddie_whatsapp_latency_seconds_p95", "P95 latency seconds", value=p95)
        yield g_lat_p95

        # model loaded map
        models = metrics.get("models", {}) or {}
        if isinstance(models, dict):
            g_model = GaugeMetricFamily("eddie_whatsapp_model_loaded", "Model loaded (1) or not (0)", labels=["model"])
            for m, v in models.items():
                try:
                    val = 1 if int(v) else 0
                except Exception:
                    val = 0
                g_model.add_metric([m], val)
            yield g_model


class PushHandler(BaseHTTPRequestHandler):
    """Allow simple POST pushes to update the metrics file.
    POST /push with JSON body will overwrite metrics file.
    """

    def do_POST(self):
        if self.path != "/push":
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("content-length", 0))
        body = self.rfile.read(length) if length else b""
        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"invalid json")
            return
        # atomic write
        tmp = self.server.metrics_path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            os.replace(tmp, self.server.metrics_path)
            logging.info("metrics file updated via push")
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
        except Exception:
            logging.exception("failed to write metrics file")
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b"error")

    def log_message(self, format, *args):
        # silence default logging
        logging.debug("http: " + format, *args)


def run_http_push_server(port: int, metrics_path: str):
    server = HTTPServer(("0.0.0.0", port), PushHandler)
    server.metrics_path = metrics_path
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    logging.info("push server running on :%d (POST /push)", port)
    return server


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=PORT_DEFAULT, help="exporter port")
    parser.add_argument("--push-port", type=int, default=PORT_DEFAULT + 1, help="push HTTP port for updates")
    parser.add_argument("--metrics-file", default=METRICS_FILE_DEFAULT)
    parser.add_argument("--rag-api", default=RAG_API_URL)
    args = parser.parse_args()

    logging.info("starting eddie_whatsapp_exporter on port %d", args.port)

    collector = EddieWhatsappCollector(metrics_path=args.metrics_file, rag_api_url=args.rag_api)
    REGISTRY.register(collector)

    # start prometheus metrics server
    start_http_server(args.port)
    # start small push server to accept metric updates
    run_http_push_server(args.push_port, args.metrics_file)

    # keep running
    def _handle_sig(sig, frame):
        logging.info("received signal, exiting")
        sys.exit(0)

    signal.signal(signal.SIGINT, _handle_sig)
    signal.signal(signal.SIGTERM, _handle_sig)

    logging.info("exporter ready; metrics file=%s", args.metrics_file)
    while True:
        signal.pause()


if __name__ == "__main__":
    main()
