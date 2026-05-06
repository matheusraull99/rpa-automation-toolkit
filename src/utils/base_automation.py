"""
RPA Base Framework
==================
Common foundation for every automation in this toolkit. Handles:

  - Structured logging (file + console)
  - Retry logic with exponential backoff
  - Performance metrics (duration, items processed, errors)
  - Standardized error handling and reporting

Why a base class?
-----------------
In production RPA, every bot needs to: log what it did, retry on
transient failures, report metrics, and write to a known output path.
Without a shared base, those concerns get re-implemented (badly) in
every bot. UiPath solves this with REFramework — this is the Python
equivalent for the toolkit.
"""

from __future__ import annotations

import functools
import json
import logging
import time
import traceback
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
LOG_DIR = PROJECT_ROOT / 'data' / 'logs'
LOG_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class AutomationMetrics:
    """Standardized metrics every bot reports back to the orchestrator."""
    bot_name: str
    started_at: str
    finished_at: str = ''
    duration_seconds: float = 0.0
    items_processed: int = 0
    items_failed: int = 0
    status: str = 'running'           # running | success | partial | failed
    errors: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def retry(max_attempts: int = 3, backoff_seconds: float = 2.0):
    """
    Decorator: retry a function on exception with exponential backoff.

    Standard pattern for any RPA bot that talks to the network or to a
    flaky desktop app. UiPath has the same concept built-in via the
    Retry Scope activity.
    """
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    wait = backoff_seconds * (2 ** (attempt - 1))
                    logging.warning(
                        f'{fn.__name__} failed on attempt {attempt}/{max_attempts}: {e}. '
                        f'Retrying in {wait:.1f}s'
                    )
                    if attempt < max_attempts:
                        time.sleep(wait)
            raise last_exception
        return wrapper
    return decorator


class BaseAutomation(ABC):
    """
    Abstract base for every automation. Subclass and implement run().

    Lifecycle
    ---------
    1. __init__       : sets up logger and metrics
    2. setup()        : optional pre-run hook (open browser, connect API…)
    3. run()          : main work — must be implemented by subclass
    4. teardown()     : optional cleanup (close browser, write output…)
    5. report()       : persists metrics to JSON for the dashboard
    """

    def __init__(self, name: str | None = None):
        self.name = name or self.__class__.__name__
        self.metrics = AutomationMetrics(
            bot_name=self.name,
            started_at=datetime.now().isoformat()
        )
        self._setup_logger()

    def _setup_logger(self) -> None:
        """File + console logger with bot name embedded."""
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(logging.INFO)
        self.logger.handlers.clear()

        formatter = logging.Formatter(
            '%(asctime)s | %(name)-25s | %(levelname)-7s | %(message)s',
            datefmt='%H:%M:%S'
        )

        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        self.logger.addHandler(ch)

        log_file = LOG_DIR / f'{self.name}_{datetime.now():%Y%m%d}.log'
        fh = logging.FileHandler(log_file, encoding='utf-8')
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)

    def setup(self) -> None:
        """Override to initialize resources (browser, API client, etc.)."""
        pass

    @abstractmethod
    def run(self) -> Any:
        """Main automation logic. Subclasses must implement this."""
        ...

    def teardown(self) -> None:
        """Override to release resources."""
        pass

    def report(self) -> None:
        """Persist metrics so the orchestrator can pick them up."""
        report_path = LOG_DIR / f'{self.name}_metrics_{datetime.now():%Y%m%d_%H%M%S}.json'
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(self.metrics.to_dict(), f, indent=2, ensure_ascii=False)
        self.logger.info(f'Metrics saved to {report_path}')

    def execute(self) -> AutomationMetrics:
        """
        Standard entry point. Wraps run() with timing, error capture,
        and guaranteed metrics reporting (even on failure).
        """
        start = time.time()
        self.logger.info(f'==> Starting {self.name}')

        try:
            self.setup()
            self.run()
            self.metrics.status = (
                'success' if self.metrics.items_failed == 0 else 'partial'
            )
        except Exception as e:
            self.metrics.status = 'failed'
            self.metrics.errors.append({
                'type': type(e).__name__,
                'message': str(e),
                'traceback': traceback.format_exc(),
            })
            self.logger.error(f'{self.name} failed: {e}')
        finally:
            try:
                self.teardown()
            except Exception as e:
                self.logger.warning(f'teardown error: {e}')

            self.metrics.finished_at = datetime.now().isoformat()
            self.metrics.duration_seconds = round(time.time() - start, 2)

            self.logger.info(
                f'<== {self.name} finished | status={self.metrics.status} | '
                f'duration={self.metrics.duration_seconds}s | '
                f'processed={self.metrics.items_processed} | '
                f'failed={self.metrics.items_failed}'
            )
            self.report()

        return self.metrics
