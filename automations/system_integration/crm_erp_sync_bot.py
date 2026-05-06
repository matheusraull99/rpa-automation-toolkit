"""
System Integration Automation
==============================
Synchronizes data between two systems that don't talk to each other
natively: a "CRM" (source of truth for customers) and an "ERP"
(source of truth for invoices).

Real-world equivalent
---------------------
Many mid-sized companies have legacy systems that don't expose APIs
or whose APIs are incomplete. The analyst-on-shift exports CSV from
System A, opens System B, manually pastes data, and confirms record
by record. A bot does it correctly, fast, and leaves an audit trail.

UiPath equivalent
-----------------
  - Excel scope (Read Range from CRM export)
  - HTTP Request (POST to ERP API) — or screen automation if no API
  - For Each Row + decision logic
  - Try Catch with rollback on partial failures
  - Send notification (Slack/Email) on completion

This Python version uses two SQLite databases as stand-ins for the
two systems. The pattern is identical.
"""

from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.utils.base_automation import BaseAutomation, retry

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / 'data' / 'output'
DATA_DIR.mkdir(parents=True, exist_ok=True)


class CrmErpSyncBot(BaseAutomation):
    """Syncs new and updated customers from CRM to ERP."""

    CRM_DB = DATA_DIR / 'crm.db'
    ERP_DB = DATA_DIR / 'erp.db'

    def __init__(self):
        super().__init__(name='CrmErpSyncBot')
        self.crm: sqlite3.Connection | None = None
        self.erp: sqlite3.Connection | None = None

    def setup(self) -> None:
        """Initialize the two databases with sample data."""
        self.logger.info('Setting up CRM and ERP source databases...')
        self._seed_crm()
        self._seed_erp()
        self.crm = sqlite3.connect(self.CRM_DB)
        self.erp = sqlite3.connect(self.ERP_DB)

    def _seed_crm(self) -> None:
        """Populate CRM with 100 customers, some recently updated."""
        np.random.seed(42)
        if self.CRM_DB.exists():
            self.CRM_DB.unlink()
        conn = sqlite3.connect(self.CRM_DB)
        try:
            conn.execute("""
                CREATE TABLE customers (
                    customer_id    TEXT PRIMARY KEY,
                    name           TEXT NOT NULL,
                    email          TEXT NOT NULL,
                    tax_id         TEXT NOT NULL,
                    updated_at     TEXT NOT NULL
                )
            """)
            now = datetime.now()
            rows = []
            for i in range(1, 101):
                # Half of customers updated in last 24h
                hours_ago = np.random.uniform(0, 48)
                rows.append((
                    f'CUST{i:04d}',
                    f'Customer {i}',
                    f'customer{i}@example.com',
                    f'{np.random.randint(10**10, 10**11)}',
                    (now - timedelta(hours=hours_ago)).isoformat()
                ))
            conn.executemany('INSERT INTO customers VALUES (?,?,?,?,?)', rows)
            conn.commit()
        finally:
            conn.close()

    def _seed_erp(self) -> None:
        """ERP starts with 80 customers (CRM has 100 — 20 are 'new')."""
        if self.ERP_DB.exists():
            self.ERP_DB.unlink()
        conn = sqlite3.connect(self.ERP_DB)
        try:
            conn.execute("""
                CREATE TABLE customers (
                    customer_id    TEXT PRIMARY KEY,
                    name           TEXT NOT NULL,
                    email          TEXT NOT NULL,
                    tax_id         TEXT NOT NULL,
                    synced_at      TEXT NOT NULL
                )
            """)
            now = datetime.now() - timedelta(days=2)
            rows = [(f'CUST{i:04d}', f'OLD Name {i}', f'old{i}@example.com',
                     f'{1234567890 + i}', now.isoformat())
                    for i in range(1, 81)]
            conn.executemany('INSERT INTO customers VALUES (?,?,?,?,?)', rows)
            conn.commit()
        finally:
            conn.close()

    @retry(max_attempts=3, backoff_seconds=1.0)
    def _fetch_crm_updates(self, hours: int = 24) -> pd.DataFrame:
        """Get customers updated in the last `hours` hours from CRM."""
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        return pd.read_sql(
            'SELECT * FROM customers WHERE updated_at >= ?',
            self.crm, params=(cutoff,)
        )

    def _upsert_to_erp(self, row: pd.Series) -> str:
        """Insert or update one customer in ERP. Returns 'inserted' or 'updated'."""
        existing = self.erp.execute(
            'SELECT customer_id FROM customers WHERE customer_id = ?',
            (row['customer_id'],)
        ).fetchone()

        synced = datetime.now().isoformat()
        if existing:
            self.erp.execute(
                """UPDATE customers
                   SET name=?, email=?, tax_id=?, synced_at=?
                   WHERE customer_id=?""",
                (row['name'], row['email'], row['tax_id'], synced, row['customer_id'])
            )
            return 'updated'

        self.erp.execute(
            'INSERT INTO customers VALUES (?,?,?,?,?)',
            (row['customer_id'], row['name'], row['email'], row['tax_id'], synced)
        )
        return 'inserted'

    def run(self) -> None:
        updates = self._fetch_crm_updates(hours=24)
        self.logger.info(f'Fetched {len(updates)} updated customers from CRM')

        inserted, updated = 0, 0
        for _, row in updates.iterrows():
            try:
                action = self._upsert_to_erp(row)
                if action == 'inserted':
                    inserted += 1
                else:
                    updated += 1
                self.metrics.items_processed += 1
            except Exception as e:
                self.metrics.items_failed += 1
                self.metrics.errors.append({
                    'customer_id': row['customer_id'],
                    'message': str(e),
                })
                self.logger.error(f'Failed to sync {row["customer_id"]}: {e}')

        self.erp.commit()
        self.logger.info(f'Sync complete | inserted={inserted} updated={updated} '
                         f'failed={self.metrics.items_failed}')

    def teardown(self) -> None:
        if self.crm: self.crm.close()
        if self.erp: self.erp.close()


if __name__ == '__main__':
    CrmErpSyncBot().execute()
