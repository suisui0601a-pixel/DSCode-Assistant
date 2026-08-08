"""SQLite persistence for local DSCode Assistant chat history."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import ChatMessage, ChatSession, MessageRole, MessageStatus
from .settings import SettingsManager


DATABASE_FILENAME = "dscode_assistant.db"
SCHEMA_VERSION = "1"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


class Database:
    """Manage the local SQLite database and chat history."""

    def __init__(self, settings_manager: SettingsManager | None = None) -> None:
        self._settings_manager = settings_manager or SettingsManager()
        self._database_path = (
            self._settings_manager.get_data_dir() / DATABASE_FILENAME
        )
        self._connection: sqlite3.Connection | None = None

    @property
    def database_path(self) -> Path:
        """Return the path of the local SQLite database."""
        return self._database_path

    def initialize(self) -> None:
        """Open the database and create the initial schema when needed."""
        if self._connection is not None:
            return

        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")

        try:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    prompt_id TEXT,
                    model TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'completed',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (session_id)
                        REFERENCES chat_sessions(id)
                        ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS app_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id
                    ON chat_messages (session_id, id);
                """
            )
            connection.execute(
                """
                INSERT OR IGNORE INTO app_meta (key, value)
                VALUES ('schema_version', ?)
                """,
                (SCHEMA_VERSION,),
            )
            connection.commit()
        except sqlite3.Error:
            connection.close()
            raise

        self._connection = connection

    def create_session(
        self,
        title: str,
        model: str,
        prompt_id: str | None = None,
    ) -> ChatSession:
        """Create and return a new chat session."""
        connection = self._require_connection()
        now = _utc_now_iso()

        with connection:
            cursor = connection.execute(
                """
                INSERT INTO chat_sessions (
                    title, prompt_id, model, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (title, prompt_id, model, now, now),
            )

        return ChatSession(
            id=cursor.lastrowid,
            title=title,
            prompt_id=prompt_id,
            model=model,
            created_at=_parse_datetime(now),
            updated_at=_parse_datetime(now),
        )

    def list_sessions(self) -> list[ChatSession]:
        """Return all sessions with the most recently updated first."""
        connection = self._require_connection()
        rows = connection.execute(
            """
            SELECT id, title, prompt_id, model, created_at, updated_at
            FROM chat_sessions
            ORDER BY updated_at DESC, id DESC
            """
        ).fetchall()
        return [self._session_from_row(row) for row in rows]

    def get_messages(self, session_id: int) -> list[ChatMessage]:
        """Return all messages for a session in insertion order."""
        connection = self._require_connection()
        rows = connection.execute(
            """
            SELECT id, session_id, role, content, status, created_at, updated_at
            FROM chat_messages
            WHERE session_id = ?
            ORDER BY id ASC
            """,
            (session_id,),
        ).fetchall()
        return [self._message_from_row(row) for row in rows]

    def add_message(
        self,
        session_id: int,
        role: MessageRole,
        content: str,
        status: MessageStatus = MessageStatus.COMPLETED,
    ) -> ChatMessage:
        """Add and return a message in an existing chat session."""
        connection = self._require_connection()
        now = _utc_now_iso()

        with connection:
            cursor = connection.execute(
                """
                INSERT INTO chat_messages (
                    session_id, role, content, status, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (session_id, role.value, content, status.value, now, now),
            )
            connection.execute(
                """
                UPDATE chat_sessions
                SET updated_at = ?
                WHERE id = ?
                """,
                (now, session_id),
            )

        return ChatMessage(
            id=cursor.lastrowid,
            session_id=session_id,
            role=role,
            content=content,
            status=status,
            created_at=_parse_datetime(now),
            updated_at=_parse_datetime(now),
        )

    def update_message(
        self,
        message_id: int,
        content: str,
        status: MessageStatus | None = None,
    ) -> ChatMessage:
        """Update message content and optionally its status."""
        connection = self._require_connection()
        now = _utc_now_iso()

        with connection:
            if status is None:
                cursor = connection.execute(
                    """
                    UPDATE chat_messages
                    SET content = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (content, now, message_id),
                )
            else:
                cursor = connection.execute(
                    """
                    UPDATE chat_messages
                    SET content = ?, status = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (content, status.value, now, message_id),
                )

            if cursor.rowcount == 0:
                raise ValueError(f"Message {message_id} does not exist.")

            row = connection.execute(
                """
                SELECT id, session_id, role, content, status, created_at, updated_at
                FROM chat_messages
                WHERE id = ?
                """,
                (message_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"Message {message_id} does not exist.")

            connection.execute(
                """
                UPDATE chat_sessions
                SET updated_at = ?
                WHERE id = ?
                """,
                (now, row["session_id"]),
            )

        return self._message_from_row(row)

    def rename_session(self, session_id: int, title: str) -> None:
        """Rename a chat session."""
        connection = self._require_connection()
        now = _utc_now_iso()

        with connection:
            cursor = connection.execute(
                """
                UPDATE chat_sessions
                SET title = ?, updated_at = ?
                WHERE id = ?
                """,
                (title, now, session_id),
            )

        if cursor.rowcount == 0:
            raise ValueError(f"Session {session_id} does not exist.")

    def delete_session(self, session_id: int) -> None:
        """Delete a session and its messages through foreign-key cascading."""
        connection = self._require_connection()
        with connection:
            connection.execute(
                "DELETE FROM chat_sessions WHERE id = ?",
                (session_id,),
            )

    def clear_history(self) -> None:
        """Delete all local chat sessions and messages."""
        connection = self._require_connection()
        with connection:
            connection.execute("DELETE FROM chat_sessions")

    def close(self) -> None:
        """Close the SQLite connection."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def _require_connection(self) -> sqlite3.Connection:
        if self._connection is None:
            raise RuntimeError("Database.initialize() must be called first.")
        return self._connection

    @staticmethod
    def _session_from_row(row: sqlite3.Row) -> ChatSession:
        return ChatSession(
            id=row["id"],
            title=row["title"],
            prompt_id=row["prompt_id"],
            model=row["model"],
            created_at=_parse_datetime(row["created_at"]),
            updated_at=_parse_datetime(row["updated_at"]),
        )

    @staticmethod
    def _message_from_row(row: sqlite3.Row) -> ChatMessage:
        return ChatMessage(
            id=row["id"],
            session_id=row["session_id"],
            role=MessageRole(row["role"]),
            content=row["content"],
            status=MessageStatus(row["status"]),
            created_at=_parse_datetime(row["created_at"]),
            updated_at=_parse_datetime(row["updated_at"]),
        )
