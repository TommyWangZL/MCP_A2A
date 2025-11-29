"""Database initialization using your professor's `database_setup.py` script."""

from datetime import datetime
import sqlite3
from typing import Optional

from config import DB_PATH
from database_setup import DatabaseSetup  # You must provide this file


def init_db_with_professor_script(db_path: Optional[str] = None) -> None:
    """Initialize the SQLite DB using the professor's script,
    then add your premium sample records (customer 12345).
    """
    if db_path is None:
        db_path = DB_PATH

    # Use professor's helper exactly as intended
    db = DatabaseSetup(db_path)
    db.connect()
    db.create_tables()
    db.create_triggers()
    db.insert_sample_data()
    db.close()

    # Add your premium sample
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Premium Auto Parts customer 12345
    cur.execute(
        """
        INSERT OR IGNORE INTO customers (id, name, email, phone, status)
        VALUES (12345, 'Premium Auto Parts Inc.', 'support@premiumauto.com',
                '+1-555-0999', 'active')
        """
    )

    # A sample ticket for that customer
    cur.execute(
        """
        INSERT INTO tickets (customer_id, issue, status, priority, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            12345,
            "Subscription renewal question",
            "resolved",
            "low",
            datetime.utcnow().isoformat(),
        ),
    )

    conn.commit()
    conn.close()
    print(f"Database initialized at {db_path} using database_setup.py")
