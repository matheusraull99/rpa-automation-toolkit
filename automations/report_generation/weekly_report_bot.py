"""
Report Generation Automation
============================
Reads a clean dataset and generates a formatted PDF report with
charts, summary tables, and an executive narrative.

Real-world equivalent
---------------------
Every Monday, an analyst opens 5 Excel files, makes 4 charts, copies
them into PowerPoint, writes a summary, exports to PDF, and emails
to the leadership team. A bot does it in 20 seconds, every Monday,
identical formatting.

UiPath equivalent
-----------------
  - Excel scope (Read Range)
  - Build Data Table for chart data
  - Generate chart in matplotlib (Python integration)
  - Word/PDF document creation activities
  - Send Outlook Mail Message
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.utils.base_automation import BaseAutomation

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = PROJECT_ROOT / 'data' / 'output'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    'figure.dpi': 100, 'savefig.dpi': 150, 'savefig.bbox': 'tight',
    'font.size': 10, 'axes.titleweight': 'bold',
})


class WeeklyReportBot(BaseAutomation):
    """Generates a weekly sales PDF report from consolidated data."""

    def __init__(self):
        super().__init__(name='WeeklyReportBot')
        self.df: pd.DataFrame | None = None

    def setup(self) -> None:
        """Load the consolidated dataset (or generate if missing)."""
        consolidated_path = OUTPUT_DIR / 'consolidated_sales.xlsx'
        if consolidated_path.exists():
            self.df = pd.read_excel(consolidated_path)
            self.df['transaction_date'] = pd.to_datetime(self.df['transaction_date'])
            self.logger.info(f'Loaded {len(self.df)} rows from consolidated file')
        else:
            self.logger.info('No consolidated file found — generating sample data')
            np.random.seed(42)
            self.df = pd.DataFrame({
                'transaction_date': pd.date_range('2024-01-01', periods=500, freq='h'),
                'amount': np.random.uniform(10, 500, 500).round(2),
                'branch': np.random.choice(['North', 'South', 'East'], 500),
                'customer_id': [f'CUST{i:04d}' for i in np.random.randint(1, 100, 500)],
            })

    def _build_chart(self) -> Path:
        """Daily revenue trend chart."""
        daily = (self.df.groupby(self.df['transaction_date'].dt.date)['amount']
                        .sum().reset_index())
        daily.columns = ['date', 'revenue']

        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(daily['date'], daily['revenue'], color='#2563eb',
                linewidth=2, marker='o', markersize=4)
        ax.fill_between(daily['date'], daily['revenue'], alpha=0.2, color='#2563eb')
        ax.set_title('Daily Revenue')
        ax.set_ylabel('Revenue (R$)')
        ax.set_xlabel('Date')
        ax.grid(True, alpha=0.3)

        chart_path = OUTPUT_DIR / 'daily_revenue.png'
        plt.savefig(chart_path)
        plt.close()
        return chart_path

    def _build_branch_chart(self) -> Path:
        """Revenue by branch."""
        branch = self.df.groupby('branch')['amount'].sum().sort_values(ascending=True)

        fig, ax = plt.subplots(figsize=(8, 4))
        ax.barh(branch.index, branch.values, color=['#16a34a', '#f59e0b', '#dc2626'])
        ax.set_title('Revenue by Branch')
        ax.set_xlabel('Revenue (R$)')
        for i, v in enumerate(branch.values):
            ax.text(v, i, f'  R$ {v:,.0f}', va='center', fontsize=9)

        chart_path = OUTPUT_DIR / 'revenue_by_branch.png'
        plt.savefig(chart_path)
        plt.close()
        return chart_path

    def run(self) -> None:
        self.logger.info('Building charts...')
        chart1 = self._build_chart()
        chart2 = self._build_branch_chart()

        # Summary metrics for the executive narrative
        total_revenue = float(self.df['amount'].sum())
        n_transactions = len(self.df)
        avg_ticket = total_revenue / n_transactions
        unique_customers = int(self.df['customer_id'].nunique())
        top_branch = self.df.groupby('branch')['amount'].sum().idxmax()

        self.logger.info('Building report HTML/PDF...')
        report_html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Weekly Sales Report</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
         max-width: 800px; margin: 40px auto; color: #1f2937; padding: 0 20px; }}
  h1 {{ color: #1e40af; border-bottom: 3px solid #2563eb; padding-bottom: 10px; }}
  h2 {{ color: #374151; margin-top: 30px; }}
  .metric-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; margin: 30px 0; }}
  .metric {{ background: #f3f4f6; padding: 16px 20px; border-radius: 8px; border-left: 4px solid #2563eb; }}
  .metric-label {{ font-size: 13px; color: #6b7280; text-transform: uppercase; }}
  .metric-value {{ font-size: 28px; font-weight: 600; margin-top: 4px; }}
  img {{ max-width: 100%; margin: 20px 0; border-radius: 8px; }}
  .footer {{ margin-top: 60px; color: #9ca3af; font-size: 13px; border-top: 1px solid #e5e7eb; padding-top: 20px; }}
</style>
</head>
<body>
  <h1>Weekly Sales Report</h1>
  <p>Generated by <strong>WeeklyReportBot</strong> on {datetime.now():%Y-%m-%d %H:%M}</p>

  <h2>Executive Summary</h2>
  <p>Total revenue for the period reached <strong>R$ {total_revenue:,.2f}</strong> across
  <strong>{n_transactions:,}</strong> transactions and <strong>{unique_customers}</strong>
  unique customers. Average ticket was <strong>R$ {avg_ticket:.2f}</strong>.
  Top-performing branch: <strong>{top_branch}</strong>.</p>

  <div class="metric-grid">
    <div class="metric"><div class="metric-label">Total Revenue</div>
      <div class="metric-value">R$ {total_revenue / 1000:,.1f}K</div></div>
    <div class="metric"><div class="metric-label">Transactions</div>
      <div class="metric-value">{n_transactions:,}</div></div>
    <div class="metric"><div class="metric-label">Average Ticket</div>
      <div class="metric-value">R$ {avg_ticket:.2f}</div></div>
    <div class="metric"><div class="metric-label">Unique Customers</div>
      <div class="metric-value">{unique_customers}</div></div>
  </div>

  <h2>Daily Revenue Trend</h2>
  <img src="{chart1.name}" alt="Daily Revenue">

  <h2>Revenue by Branch</h2>
  <img src="{chart2.name}" alt="Revenue by Branch">

  <div class="footer">
    Generated automatically by RPA Toolkit · No manual edits required ·
    <a href="https://github.com/matheusraull99/rpa-automation-toolkit">github.com/matheusraull99/rpa-automation-toolkit</a>
  </div>
</body>
</html>
        """.strip()

        report_path = OUTPUT_DIR / 'weekly_report.html'
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report_html)

        self.metrics.items_processed = n_transactions
        self.logger.info(f'Saved -> {report_path}')


if __name__ == '__main__':
    WeeklyReportBot().execute()
