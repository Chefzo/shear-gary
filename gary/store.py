"""SQLite storage for requests, photo metadata, approvals, attempts, and the audit log.

The audit table is append-only at this API. The database file lives under the
local data directory and is gitignored.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from gary.errors import NotFoundError, SafetyError
from gary.models import (
    ALLOWED_MODES,
    Approval,
    Attempt,
    AuditEntry,
    Photo,
    Request,
)
from gary.util import dump_json, utcnow

SCHEMA = """
CREATE TABLE IF NOT EXISTS requests (
    id TEXT PRIMARY KEY,
    module_id TEXT NOT NULL,
    channel TEXT NOT NULL,
    sender_label TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL,
    triage_class TEXT NOT NULL CHECK (triage_class IN ('emergency', 'routine', 'needs_review')),
    triage_rule TEXT,
    triage_reason TEXT NOT NULL,
    triage_limitation TEXT NOT NULL,
    escalation TEXT NOT NULL CHECK (escalation IN ('human_required', 'none')),
    status TEXT NOT NULL CHECK (status IN ('escalated', 'routine_logged'))
);

CREATE TABLE IF NOT EXISTS photos (
    id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL REFERENCES requests(id),
    filename TEXT NOT NULL,
    content_type TEXT,
    size_bytes INTEGER,
    sha256 TEXT,
    stored_relative_path TEXT,
    note TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS approvals (
    id TEXT PRIMARY KEY,
    request_id TEXT REFERENCES requests(id),
    action_type TEXT NOT NULL CHECK (action_type IN ('outbound_message', 'spend')),
    summary TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'approved', 'denied', 'executed')),
    requested_at TEXT NOT NULL,
    decided_at TEXT,
    decided_by TEXT,
    decision_note TEXT,
    executed_at TEXT
);

CREATE TABLE IF NOT EXISTS outbound_attempts (
    id TEXT PRIMARY KEY,
    approval_id TEXT NOT NULL REFERENCES approvals(id),
    adapter TEXT NOT NULL,
    mode TEXT NOT NULL CHECK (mode IN ('dry_run', 'disabled', 'blocked')),
    delivered INTEGER NOT NULL CHECK (delivered = 0),
    detail TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT,
    detail_json TEXT NOT NULL
);
"""


class Store:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.data_dir / "gary.sqlite"
        self.photos_dir = self.data_dir / "photos"
        self.photos_dir.mkdir(parents=True, exist_ok=True)
        self._tx: sqlite3.Connection | None = None
        self._init_db()

    def _init_db(self) -> None:
        conn = self._open()
        try:
            conn.executescript(SCHEMA)
            conn.execute("PRAGMA user_version = 1")
            conn.commit()
        finally:
            conn.close()

    def _open(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @contextmanager
    def transaction(self) -> Iterator[Store]:
        if self._tx is not None:
            yield self
            return
        conn = self._open()
        try:
            self._tx = conn
            yield self
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._tx = None
            conn.close()

    @contextmanager
    def _run(self) -> Iterator[sqlite3.Connection]:
        if self._tx is not None:
            yield self._tx
            return
        conn = self._open()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def insert_request(self, request: Request) -> None:
        with self._run() as conn:
            conn.execute(
                """
                INSERT INTO requests (
                    id, module_id, channel, sender_label, body, created_at,
                    triage_class, triage_rule, triage_reason, triage_limitation,
                    escalation, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request.id,
                    request.module_id,
                    request.channel,
                    request.sender_label,
                    request.body,
                    request.created_at,
                    request.triage_class,
                    request.triage_rule,
                    request.triage_reason,
                    request.triage_limitation,
                    request.escalation,
                    request.status,
                ),
            )

    def insert_photo(self, photo: Photo) -> None:
        with self._run() as conn:
            conn.execute(
                """
                INSERT INTO photos (
                    id, request_id, filename, content_type, size_bytes, sha256,
                    stored_relative_path, note, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    photo.id,
                    photo.request_id,
                    photo.filename,
                    photo.content_type,
                    photo.size_bytes,
                    photo.sha256,
                    photo.stored_relative_path,
                    photo.note,
                    photo.created_at,
                ),
            )

    def insert_approval(self, approval: Approval) -> None:
        with self._run() as conn:
            conn.execute(
                """
                INSERT INTO approvals (
                    id, request_id, action_type, summary, payload_json, status,
                    requested_at, decided_at, decided_by, decision_note, executed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    approval.id,
                    approval.request_id,
                    approval.action_type,
                    approval.summary,
                    dump_json(approval.payload),
                    approval.status,
                    approval.requested_at,
                    approval.decided_at,
                    approval.decided_by,
                    approval.decision_note,
                    approval.executed_at,
                ),
            )

    def decide_approval(
        self,
        approval_id: str,
        decision: str,
        decided_by: str,
        decision_note: str | None,
        decided_at: str,
    ) -> Approval:
        with self._run() as conn:
            before = conn.total_changes
            conn.execute(
                """
                UPDATE approvals
                SET status = ?, decided_at = ?, decided_by = ?, decision_note = ?
                WHERE id = ? AND status = 'pending'
                """,
                (decision, decided_at, decided_by, decision_note, approval_id),
            )
            if conn.total_changes - before != 1:
                existing = self._approval_on(conn, approval_id)
                if existing is None:
                    raise NotFoundError(f"approval not found: {approval_id}")
                raise SafetyError("this approval is already decided")
            approval = self._approval_on(conn, approval_id)
        if approval is None:
            raise NotFoundError(f"approval not found: {approval_id}")
        return approval

    def mark_approval_executed(self, approval_id: str, executed_at: str) -> Approval:
        with self._run() as conn:
            before = conn.total_changes
            conn.execute(
                """
                UPDATE approvals
                SET status = 'executed', executed_at = ?
                WHERE id = ? AND status = 'approved'
                """,
                (executed_at, approval_id),
            )
            if conn.total_changes - before != 1:
                raise SafetyError("only an approved, not-yet-executed item can be recorded as executed")
            approval = self._approval_on(conn, approval_id)
        if approval is None:
            raise NotFoundError(f"approval not found: {approval_id}")
        return approval

    def insert_attempt(self, attempt: Attempt) -> None:
        if attempt.delivered:
            raise SafetyError("refusing to store a delivered attempt")
        if attempt.mode not in ALLOWED_MODES:
            raise SafetyError("attempt mode must be dry_run, disabled, or blocked")
        with self._run() as conn:
            conn.execute(
                """
                INSERT INTO outbound_attempts (
                    id, approval_id, adapter, mode, delivered, detail, created_at
                ) VALUES (?, ?, ?, ?, 0, ?, ?)
                """,
                (
                    attempt.id,
                    attempt.approval_id,
                    attempt.adapter,
                    attempt.mode,
                    attempt.detail,
                    attempt.created_at,
                ),
            )

    def audit(
        self,
        actor: str,
        action: str,
        entity_type: str,
        entity_id: str | None,
        detail: dict,
        ts: str | None = None,
    ) -> None:
        with self._run() as conn:
            conn.execute(
                """
                INSERT INTO audit_log (ts, actor, action, entity_type, entity_id, detail_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (ts or utcnow(), actor, action, entity_type, entity_id, dump_json(detail)),
            )

    def get_request(self, request_id: str) -> Request:
        with self._run() as conn:
            row = conn.execute("SELECT * FROM requests WHERE id = ?", (request_id,)).fetchone()
        if row is None:
            raise NotFoundError(f"request not found: {request_id}")
        return _request(row)

    def list_requests(self) -> list[Request]:
        with self._run() as conn:
            rows = conn.execute("SELECT * FROM requests ORDER BY created_at, id").fetchall()
        return [_request(row) for row in rows]

    def list_photos(self, request_id: str) -> list[Photo]:
        with self._run() as conn:
            rows = conn.execute(
                "SELECT * FROM photos WHERE request_id = ? ORDER BY created_at, id",
                (request_id,),
            ).fetchall()
        return [_photo(row) for row in rows]

    def get_approval(self, approval_id: str) -> Approval:
        with self._run() as conn:
            approval = self._approval_on(conn, approval_id)
        if approval is None:
            raise NotFoundError(f"approval not found: {approval_id}")
        return approval

    def list_approvals(self, request_id: str | None = None) -> list[Approval]:
        with self._run() as conn:
            if request_id is None:
                rows = conn.execute("SELECT * FROM approvals ORDER BY requested_at, id").fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM approvals WHERE request_id = ? ORDER BY requested_at, id",
                    (request_id,),
                ).fetchall()
        return [_approval(row) for row in rows]

    def list_attempts(self, approval_id: str | None = None) -> list[Attempt]:
        with self._run() as conn:
            if approval_id is None:
                rows = conn.execute(
                    "SELECT * FROM outbound_attempts ORDER BY created_at, id"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM outbound_attempts WHERE approval_id = ? ORDER BY created_at, id",
                    (approval_id,),
                ).fetchall()
        return [_attempt(row) for row in rows]

    def list_audit(self, limit: int = 100) -> list[AuditEntry]:
        with self._run() as conn:
            rows = conn.execute(
                "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [_audit(row) for row in reversed(rows)]

    def _approval_on(self, conn: sqlite3.Connection, approval_id: str) -> Approval | None:
        row = conn.execute("SELECT * FROM approvals WHERE id = ?", (approval_id,)).fetchone()
        if row is None:
            return None
        return _approval(row)


def _request(row: sqlite3.Row) -> Request:
    return Request(
        id=row["id"],
        module_id=row["module_id"],
        channel=row["channel"],
        sender_label=row["sender_label"],
        body=row["body"],
        created_at=row["created_at"],
        triage_class=row["triage_class"],
        triage_rule=row["triage_rule"],
        triage_reason=row["triage_reason"],
        triage_limitation=row["triage_limitation"],
        escalation=row["escalation"],
        status=row["status"],
    )


def _photo(row: sqlite3.Row) -> Photo:
    return Photo(
        id=row["id"],
        request_id=row["request_id"],
        filename=row["filename"],
        content_type=row["content_type"],
        size_bytes=row["size_bytes"],
        sha256=row["sha256"],
        stored_relative_path=row["stored_relative_path"],
        note=row["note"],
        created_at=row["created_at"],
    )


def _approval(row: sqlite3.Row) -> Approval:
    return Approval(
        id=row["id"],
        request_id=row["request_id"],
        action_type=row["action_type"],
        summary=row["summary"],
        payload=json.loads(row["payload_json"]),
        status=row["status"],
        requested_at=row["requested_at"],
        decided_at=row["decided_at"],
        decided_by=row["decided_by"],
        decision_note=row["decision_note"],
        executed_at=row["executed_at"],
    )


def _attempt(row: sqlite3.Row) -> Attempt:
    return Attempt(
        id=row["id"],
        approval_id=row["approval_id"],
        adapter=row["adapter"],
        mode=row["mode"],
        delivered=bool(row["delivered"]),
        detail=row["detail"],
        created_at=row["created_at"],
    )


def _audit(row: sqlite3.Row) -> AuditEntry:
    return AuditEntry(
        id=row["id"],
        ts=row["ts"],
        actor=row["actor"],
        action=row["action"],
        entity_type=row["entity_type"],
        entity_id=row["entity_id"],
        detail=json.loads(row["detail_json"]),
    )
