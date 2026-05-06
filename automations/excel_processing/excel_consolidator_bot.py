"""
Excel Processing Automation
============================
Reads multiple Excel files from an input folder, applies cleaning
and transformation rules, then produces a consolidated report.

Real-world equivalent
---------------------
This is the bread-and-butter of RPA in finance and operations: a
person spends 4 hours every Monday opening 12 Excel files from
different teams, copying ranges, fixing formats, and pasting into a
master sheet. A bot does it in 30 seconds, every Monday, with zero
manual error.

UiPath equivalent
-----------------
  - For Each File in Folder
  - Read Range (Excel scope)
  - Filter / Sort Data Table
  - Merge Data Table
  - Write Range

Cleaning rules applied
----------------------
  - Strip whitespace from string columns
  - Standardize column names (snake_case)
  - Convert string dates to datetime
  - Remove duplicates on (customer_id, transaction_date)
  - Validate required columns exist
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.utils.base_automation import BaseAutomation

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
INPUT_DIR = PROJECT_ROOT / 'data' / 'input'
OUTPUT_DIR = PROJECT_ROOT / 'data' / 'output'
INPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class ExcelConsolidatorBot(BaseAutomation):
    """Consolidates multiple Excel files into a single clean dataset."""

    REQUIRED_COLUMNS = {'customer_id', 'transaction_date', 'amount'}

    def __init__(self):
        super().__init__(name='ExcelConsolidatorBot')
        self.frames: list[pd.DataFrame] = []

    def setup(self) -> None:
        """Generate sample input files if folder is empty (so demo runs out of the box)."""
        existing = list(INPUT_DIR.glob('*.xlsx'))
        if existing:
            self.logger.info(f'Found {len(existing)} existing input files')
            return

        self.logger.info('No input files found — generating samples for demo')
        np.random.seed(42)
        for i, branch in enumerate(['North', 'South', 'East'], start=1):
            n = 200
            df = pd.DataFrame({
                'Customer ID':       [f'CUST{j:04d}' for j in np.random.randint(1, 100, n)],
                ' Transaction Date': pd.date_range('2024-01-01', periods=n, freq='h'),
                'AMOUNT':            np.random.uniform(10, 500, n).round(2),
                'Branch':            branch,
                'Notes':             [f'  note {j}  ' for j in range(n)],
            })
            # Inject duplicates
            df = pd.concat([df, df.head(10)], ignore_index=True)
            path = INPUT_DIR / f'sales_{branch.lower()}.xlsx'
            df.to_excel(path, index=False)
            self.logger.info(f'  -> {path.name}')

    @staticmethod
    def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
        """snake_case + strip whitespace from column names."""
        df.columns = (
            df.columns.str.strip()
                      .str.lower()
                      .str.replace(r'\s+', '_', regex=True)
        )
        return df

    @staticmethod
    def _strip_strings(df: pd.DataFrame) -> pd.DataFrame:
        for col in df.select_dtypes(include='object').columns:
            df[col] = df[col].astype(str).str.strip()
        return df

    def _validate_columns(self, df: pd.DataFrame, source: str) -> bool:
        missing = self.REQUIRED_COLUMNS - set(df.columns)
        if missing:
            self.logger.warning(f'{source} missing columns: {missing}')
            return False
        return True

    def run(self) -> None:
        files = list(INPUT_DIR.glob('*.xlsx'))
        self.logger.info(f'Processing {len(files)} files...')

        for f in files:
            try:
                df = pd.read_excel(f)
                df = self._normalize_columns(df)
                df = self._strip_strings(df)
                if not self._validate_columns(df, f.name):
                    self.metrics.items_failed += 1
                    continue
                df['source_file'] = f.name
                self.frames.append(df)
                self.metrics.items_processed += 1
                self.logger.info(f'  ok: {f.name} ({len(df)} rows)')
            except Exception as e:
                self.metrics.items_failed += 1
                self.metrics.errors.append({'file': f.name, 'message': str(e)})
                self.logger.error(f'  fail: {f.name} -> {e}')

        if not self.frames:
            self.logger.warning('No frames to consolidate')
            return

        consolidated = pd.concat(self.frames, ignore_index=True)
        before = len(consolidated)
        consolidated = consolidated.drop_duplicates(
            subset=['customer_id', 'transaction_date'], keep='first'
        )
        after = len(consolidated)
        self.logger.info(f'Removed {before - after} duplicate rows')

        output_path = OUTPUT_DIR / 'consolidated_sales.xlsx'
        consolidated.to_excel(output_path, index=False)
        self.logger.info(f'Saved {after} rows -> {output_path}')


if __name__ == '__main__':
    bot = ExcelConsolidatorBot()
    bot.execute()
