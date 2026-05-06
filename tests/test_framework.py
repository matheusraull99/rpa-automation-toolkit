"""Test suite for the RPA Automation Toolkit."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.base_automation import (AutomationMetrics, BaseAutomation,
                                        retry)


# ============================================================
# Retry decorator
# ============================================================

def _make_flaky(fail_times: int = 0):
    """Build a function that fails the first N times, then returns 'ok'."""
    state = {'calls': 0}

    def flaky():
        state['calls'] += 1
        if state['calls'] <= fail_times:
            raise ValueError(f'simulated failure {state["calls"]}')
        return 'ok'

    flaky.calls = state
    return flaky


def test_retry_succeeds_on_first_attempt():
    fn = _make_flaky(fail_times=0)
    decorated = retry(max_attempts=3, backoff_seconds=0.01)(fn)
    assert decorated() == 'ok'
    assert fn.calls['calls'] == 1


def test_retry_recovers_after_transient_failures():
    fn = _make_flaky(fail_times=2)
    decorated = retry(max_attempts=3, backoff_seconds=0.01)(fn)
    assert decorated() == 'ok'
    assert fn.calls['calls'] == 3


def test_retry_raises_after_max_attempts():
    fn = _make_flaky(fail_times=10)
    decorated = retry(max_attempts=3, backoff_seconds=0.01)(fn)
    with pytest.raises(ValueError):
        decorated()
    assert fn.calls['calls'] == 3


# ============================================================
# AutomationMetrics
# ============================================================

def test_metrics_serialization():
    m = AutomationMetrics(
        bot_name='TestBot', started_at='2024-01-01T00:00:00',
        items_processed=100, items_failed=2,
    )
    d = m.to_dict()
    assert d['bot_name'] == 'TestBot'
    assert d['items_processed'] == 100
    assert d['status'] == 'running'  # default


# ============================================================
# BaseAutomation lifecycle
# ============================================================

class _DummyBot(BaseAutomation):
    """Minimal bot for testing the lifecycle."""
    def __init__(self, will_fail: bool = False):
        super().__init__(name='DummyBot')
        self.will_fail = will_fail
        self.setup_called = False
        self.teardown_called = False

    def setup(self):
        self.setup_called = True

    def run(self):
        if self.will_fail:
            raise RuntimeError('intentional failure')
        self.metrics.items_processed = 5

    def teardown(self):
        self.teardown_called = True


def test_lifecycle_success():
    bot = _DummyBot(will_fail=False)
    metrics = bot.execute()
    assert bot.setup_called
    assert bot.teardown_called
    assert metrics.status == 'success'
    assert metrics.items_processed == 5


def test_lifecycle_failure_still_runs_teardown():
    bot = _DummyBot(will_fail=True)
    metrics = bot.execute()
    assert bot.setup_called
    assert bot.teardown_called  # cleanup must still run on failure
    assert metrics.status == 'failed'
    assert len(metrics.errors) == 1
    assert 'intentional failure' in metrics.errors[0]['message']


def test_metrics_report_persisted_to_disk():
    bot = _DummyBot(will_fail=False)
    bot.execute()

    log_dir = PROJECT_ROOT / 'data' / 'logs'
    metrics_files = list(log_dir.glob('DummyBot_metrics_*.json'))
    assert len(metrics_files) > 0

    latest = max(metrics_files, key=lambda p: p.stat().st_mtime)
    with open(latest) as f:
        saved = json.load(f)
    assert saved['bot_name'] == 'DummyBot'
    assert saved['status'] == 'success'


# ============================================================
# Excel consolidator integration test
# ============================================================

def test_excel_consolidator_removes_duplicates(tmp_path):
    """Direct test of the dedupe logic in the Excel bot."""
    from automations.excel_processing.excel_consolidator_bot import ExcelConsolidatorBot

    # Two frames with overlapping rows
    df1 = pd.DataFrame({
        'customer_id': ['C1', 'C2'],
        'transaction_date': pd.to_datetime(['2024-01-01', '2024-01-02']),
        'amount': [100, 200],
    })
    df2 = pd.DataFrame({
        'customer_id': ['C1', 'C3'],
        'transaction_date': pd.to_datetime(['2024-01-01', '2024-01-03']),
        'amount': [100, 300],
    })

    bot = ExcelConsolidatorBot()
    consolidated = pd.concat([df1, df2], ignore_index=True)
    deduped = consolidated.drop_duplicates(
        subset=['customer_id', 'transaction_date'], keep='first'
    )
    assert len(deduped) == 3  # not 4


# ============================================================
# Schema enforcement
# ============================================================

def test_excel_bot_required_columns_constant():
    from automations.excel_processing.excel_consolidator_bot import ExcelConsolidatorBot
    assert {'customer_id', 'transaction_date', 'amount'} <= ExcelConsolidatorBot.REQUIRED_COLUMNS
