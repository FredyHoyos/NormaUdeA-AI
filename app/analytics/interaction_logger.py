"""Módulo de registro de interacciones en SQLite para el Copiloto UdeA.

Utiliza sqlite3 nativo (sin dependencias adicionales) para máxima portabilidad.
Registra: timestamp, pregunta, intención, confianza y tiempo de procesamiento.
"""

from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator

logger = logging.getLogger(__name__)

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS interactions (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp            TEXT    NOT NULL,
    question             TEXT    NOT NULL,
    intent_category      TEXT    NOT NULL DEFAULT 'general',
    confidence           REAL    NOT NULL DEFAULT 0.0,
    processing_time_ms   REAL    NOT NULL DEFAULT 0.0,
    documents_used_count INTEGER NOT NULL DEFAULT 0,
    model_provider       TEXT    NOT NULL DEFAULT 'unknown',
    notes                TEXT    NOT NULL DEFAULT ''
);
"""

_INSERT_SQL = """
INSERT INTO interactions
    (timestamp, question, intent_category, confidence,
     processing_time_ms, documents_used_count, model_provider, notes)
VALUES (?, ?, ?, ?, ?, ?, ?, ?);
"""

_SELECT_RECENT_SQL = """
SELECT id, timestamp, question, intent_category, confidence,
       processing_time_ms, documents_used_count, model_provider, notes
FROM   interactions
ORDER  BY id DESC
LIMIT  ?;
"""


class InteractionLogger:
    """Logger de interacciones basado en SQLite (thread-safe por conexión)."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_table()

    # ------------------------------------------------------------------
    # Internos
    # ------------------------------------------------------------------

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _ensure_table(self) -> None:
        with self._connect() as conn:
            conn.execute(_CREATE_TABLE_SQL)
        logger.debug("Tabla 'interactions' lista en %s", self.db_path)

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def log_interaction(
        self,
        question: str,
        intent_category: str,
        confidence: float,
        processing_time_ms: float,
        documents_used_count: int = 0,
        model_provider: str = "unknown",
        notes: str = "",
    ) -> None:
        """Registra una interacción del usuario en la base de datos."""
        timestamp = datetime.now(tz=timezone.utc).isoformat()
        try:
            with self._connect() as conn:
                conn.execute(
                    _INSERT_SQL,
                    (
                        timestamp,
                        question[:1000],          # truncar si es muy larga
                        intent_category[:64],
                        round(float(confidence), 4),
                        round(float(processing_time_ms), 2),
                        int(documents_used_count),
                        model_provider[:64],
                        notes[:500],
                    ),
                )
            logger.debug("Interacción registrada: [%s] confianza=%.3f t=%.0f ms",
                         intent_category, confidence, processing_time_ms)
        except Exception as exc:
            logger.warning("No se pudo registrar la interacción en SQLite: %s", exc)

    def get_recent_interactions(self, limit: int = 50) -> list[dict]:
        """Retorna las últimas `limit` interacciones como lista de dicts."""
        try:
            with self._connect() as conn:
                rows = conn.execute(_SELECT_RECENT_SQL, (limit,)).fetchall()
            return [dict(row) for row in rows]
        except Exception as exc:
            logger.warning("No se pudo leer interactions de SQLite: %s", exc)
            return []

    def get_stats(self) -> dict:
        """Retorna estadísticas básicas de uso."""
        _STATS_SQL = """
        SELECT
            COUNT(*)                                AS total_queries,
            ROUND(AVG(confidence), 3)               AS avg_confidence,
            ROUND(AVG(processing_time_ms), 1)       AS avg_time_ms,
            ROUND(MIN(processing_time_ms), 1)       AS min_time_ms,
            ROUND(MAX(processing_time_ms), 1)       AS max_time_ms
        FROM interactions;
        """
        try:
            with self._connect() as conn:
                row = conn.execute(_STATS_SQL).fetchone()
            return dict(row) if row else {}
        except Exception as exc:
            logger.warning("No se pudo calcular stats: %s", exc)
            return {}
