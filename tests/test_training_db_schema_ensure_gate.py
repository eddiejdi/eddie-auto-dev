"""Regression: schema ensure must not re-run heavy DDL when already current.

Background: crypto-exporter created TrainingDatabase() on every Prometheus scrape,
re-running PROFILE_MIGRATION_SQL (ALTER TABLE on btc.decisions) → deadlocks with
trading agents holding RowShareLock on trades/decisions.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import training_db as tdb


def _reset_schema_cache() -> None:
    tdb._SCHEMA_ENSURED_DSNS.clear()


def test_ensure_schema_skips_when_process_cache_hit() -> None:
    _reset_schema_cache()
    db = object.__new__(tdb.TrainingDatabase)
    db.dsn = "postgresql://test/cache-hit"
    tdb._SCHEMA_ENSURED_DSNS.add(db.dsn)

    with patch.object(db, "_get_conn") as get_conn:
        db._ensure_schema()
        get_conn.assert_not_called()


def test_ensure_schema_skips_migration_when_version_current() -> None:
    _reset_schema_cache()
    db = object.__new__(tdb.TrainingDatabase)
    db.dsn = "postgresql://test/version-current"

    cur = MagicMock()
    # SELECT version → already at SCHEMA_VERSION
    cur.fetchone.return_value = (tdb.SCHEMA_VERSION,)

    conn = MagicMock()
    conn.cursor.return_value = cur

    class _CM:
        def __enter__(self):
            return conn

        def __exit__(self, *args):
            return False

    with patch.object(db, "_get_conn", return_value=_CM()):
        with patch.object(db, "_apply_schema_migration") as apply_mig:
            db._ensure_schema()
            apply_mig.assert_not_called()

    assert db.dsn in tdb._SCHEMA_ENSURED_DSNS

    # Second call: process cache only
    with patch.object(db, "_get_conn") as get_conn:
        db._ensure_schema()
        get_conn.assert_not_called()


def test_ensure_schema_runs_migration_when_version_stale() -> None:
    _reset_schema_cache()
    db = object.__new__(tdb.TrainingDatabase)
    db.dsn = "postgresql://test/version-stale"

    cur = MagicMock()
    cur.fetchone.return_value = (0,)  # stale

    conn = MagicMock()
    conn.cursor.return_value = cur

    class _CM:
        def __enter__(self):
            return conn

        def __exit__(self, *args):
            return False

    with patch.object(db, "_get_conn", return_value=_CM()):
        with patch.object(db, "_apply_schema_migration") as apply_mig:
            db._ensure_schema()
            apply_mig.assert_called_once_with(cur)

    assert db.dsn in tdb._SCHEMA_ENSURED_DSNS


def test_exporter_conversion_snapshot_does_not_import_training_db() -> None:
    """Scrape path must query conversion_* via MetricsCollector only."""
    from pathlib import Path

    src = Path("btc_trading_agent/prometheus_exporter.py").read_text(encoding="utf-8")
    # Method body present
    assert "def conversion_metrics_snapshot(self)" in src
    assert "FROM conversion_requests" in src
    # Old deadlock path removed from scrape
    assert "TrainingDatabase().conversion_metrics_snapshot" not in src
    assert "get_collector().conversion_metrics_snapshot()" in src
