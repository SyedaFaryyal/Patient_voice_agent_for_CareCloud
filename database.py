"""
Persistence layer - SQLite.
Chosen over Postgres for zero-setup within the 3-hour window (documented
trade-off in README).
"""
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

DB_PATH = "patients.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS patients (
    patient_id TEXT PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    date_of_birth TEXT NOT NULL,          -- stored as YYYY-MM-DD
    sex TEXT NOT NULL,                     -- Male | Female | Other | Decline to Answer
    phone_number TEXT NOT NULL,            -- 10 digits, no formatting
    email TEXT,
    address_line_1 TEXT NOT NULL,
    address_line_2 TEXT,
    city TEXT NOT NULL,
    state TEXT NOT NULL,
    zip_code TEXT NOT NULL,
    insurance_provider TEXT,
    insurance_member_id TEXT,
    preferred_language TEXT DEFAULT 'English',
    emergency_contact_name TEXT,
    emergency_contact_phone TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT
);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        conn.commit()
        # Seed 1 demo record if empty
        cur = conn.execute("SELECT COUNT(*) FROM patients WHERE deleted_at IS NULL")
        if cur.fetchone()[0] == 0:
            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                """INSERT INTO patients
                (patient_id, first_name, last_name, date_of_birth, sex, phone_number,
                 email, address_line_1, city, state, zip_code, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (str(uuid.uuid4()), "Jane", "Doe", "1990-05-14", "Female",
                 "5551234567", "jane.doe@example.com", "123 Main St",
                 "Austin", "TX", "78701", now, now),
            )
            conn.commit()


def _row_to_dict(row) -> dict:
    return {k: row[k] for k in row.keys()}


def find_by_phone(phone_number: str):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM patients WHERE phone_number = ? AND deleted_at IS NULL",
            (phone_number,),
        ).fetchone()
    return _row_to_dict(row) if row else None


def get_by_id(patient_id: str):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM patients WHERE patient_id = ? AND deleted_at IS NULL",
            (patient_id,),
        ).fetchone()
    return _row_to_dict(row) if row else None


def list_patients(last_name=None, date_of_birth=None, phone_number=None):
    query = "SELECT * FROM patients WHERE deleted_at IS NULL"
    params = []
    if last_name:
        query += " AND last_name = ? COLLATE NOCASE"
        params.append(last_name)
    if date_of_birth:
        query += " AND date_of_birth = ?"
        params.append(date_of_birth)
    if phone_number:
        query += " AND phone_number = ?"
        params.append(phone_number)
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_dict(r) for r in rows]


def create_patient(data: dict) -> dict:
    patient_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    fields = {
        "patient_id": patient_id,
        "first_name": data["first_name"],
        "last_name": data["last_name"],
        "date_of_birth": data["date_of_birth"],
        "sex": data["sex"],
        "phone_number": data["phone_number"],
        "email": data.get("email"),
        "address_line_1": data["address_line_1"],
        "address_line_2": data.get("address_line_2"),
        "city": data["city"],
        "state": data["state"],
        "zip_code": data["zip_code"],
        "insurance_provider": data.get("insurance_provider"),
        "insurance_member_id": data.get("insurance_member_id"),
        "preferred_language": data.get("preferred_language", "English"),
        "emergency_contact_name": data.get("emergency_contact_name"),
        "emergency_contact_phone": data.get("emergency_contact_phone"),
        "created_at": now,
        "updated_at": now,
    }
    cols = ", ".join(fields.keys())
    placeholders = ", ".join(["?"] * len(fields))
    with get_conn() as conn:
        conn.execute(
            f"INSERT INTO patients ({cols}) VALUES ({placeholders})",
            list(fields.values()),
        )
        conn.commit()
    return get_by_id(patient_id)


def update_patient(patient_id: str, data: dict):
    existing = get_by_id(patient_id)
    if not existing:
        return None
    allowed = [
        "first_name", "last_name", "date_of_birth", "sex", "phone_number",
        "email", "address_line_1", "address_line_2", "city", "state", "zip_code",
        "insurance_provider", "insurance_member_id", "preferred_language",
        "emergency_contact_name", "emergency_contact_phone",
    ]
    updates = {k: v for k, v in data.items() if k in allowed and v is not None}
    if not updates:
        return existing
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
    with get_conn() as conn:
        conn.execute(
            f"UPDATE patients SET {set_clause} WHERE patient_id = ?",
            list(updates.values()) + [patient_id],
        )
        conn.commit()
    return get_by_id(patient_id)


def soft_delete_patient(patient_id: str) -> bool:
    existing = get_by_id(patient_id)
    if not existing:
        return False
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            "UPDATE patients SET deleted_at = ?, updated_at = ? WHERE patient_id = ?",
            (now, now, patient_id),
        )
        conn.commit()
    return True
