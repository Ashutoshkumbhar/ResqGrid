import json
import os
import sqlite3
from typing import Any, Dict, List, Optional

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
DB_PATH = os.path.join(DATA_DIR, "audit.sqlite3")


def _connect() -> sqlite3.Connection:
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            decision_type TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            settlement_id TEXT,
            resource_id TEXT,
            inputs_summary TEXT,
            output TEXT,
            reason TEXT
        )
        """
    )
    conn.commit()
    return conn


def log_decision(
    decision_type: str,
    inputs_summary: Optional[Dict[str, Any]] = None,
    output: Optional[Dict[str, Any]] = None,
    reason: Optional[str] = None,
    settlement_id: Optional[str] = None,
    resource_id: Optional[str] = None,
) -> Dict[str, Any]:
    conn = _connect()
    try:
        cursor = conn.execute(
            """
            INSERT INTO audit_log (decision_type, timestamp, settlement_id, resource_id, inputs_summary, output, reason)
            VALUES (?, datetime('now'), ?, ?, ?, ?, ?)
            """,
            (
                decision_type,
                settlement_id,
                resource_id,
                json.dumps(inputs_summary or {}, sort_keys=True),
                json.dumps(output or {}, sort_keys=True),
                reason or "",
            ),
        )
        conn.commit()
        row_id = cursor.lastrowid
    finally:
        conn.close()
    return {
        "id": row_id,
        "decisionType": decision_type,
        "timestamp": __import__('datetime').datetime.utcnow().isoformat(timespec='seconds') + 'Z',
        "settlementId": settlement_id,
        "resourceId": resource_id,
        "inputsSummary": inputs_summary or {},
        "output": output or {},
        "reason": reason or "",
    }


def list_audit_entries(limit: int = 100) -> List[Dict[str, Any]]:
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT id, decision_type, timestamp, settlement_id, resource_id, inputs_summary, output, reason
            FROM audit_log
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    finally:
        conn.close()
    entries = []
    for row in rows:
        entries.append({
            "id": row["id"],
            "decisionType": row["decision_type"],
            "timestamp": row["timestamp"],
            "settlementId": row["settlement_id"],
            "resourceId": row["resource_id"],
            "inputsSummary": json.loads(row["inputs_summary"] or "{}"),
            "output": json.loads(row["output"] or "{}"),
            "reason": row["reason"],
        })
    return entries
