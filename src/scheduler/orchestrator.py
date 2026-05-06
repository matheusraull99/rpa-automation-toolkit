"""
Orchestrator
============
Runs all automations sequentially, collects their metrics, and
produces a summary HTML dashboard for the operations team.

Why an orchestrator?
--------------------
In production RPA, you don't run bots one by one — you have a
schedule (e.g., 6 AM Mon-Fri) that triggers a chain. UiPath
Orchestrator is the commercial product for this. Here we have a
simpler version that demonstrates the same role.
"""

from __future__ import annotations

import importlib
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

LOG_DIR = PROJECT_ROOT / 'data' / 'logs'
OUTPUT_DIR = PROJECT_ROOT / 'data' / 'output'

BOT_REGISTRY = [
    'automations.web_scraping.api_scraper_bot.PublicAPIScraperBot',
    'automations.excel_processing.excel_consolidator_bot.ExcelConsolidatorBot',
    'automations.report_generation.weekly_report_bot.WeeklyReportBot',
    'automations.system_integration.crm_erp_sync_bot.CrmErpSyncBot',
]


def _load_class(path: str):
    module_path, class_name = path.rsplit('.', 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def run_all():
    print('=' * 70)
    print('RPA Toolkit — Orchestrator')
    print('=' * 70)

    all_metrics = []
    for bot_path in BOT_REGISTRY:
        try:
            BotCls = _load_class(bot_path)
            bot = BotCls()
            metrics = bot.execute()
            all_metrics.append(metrics.to_dict())
        except Exception as e:
            all_metrics.append({
                'bot_name': bot_path.split('.')[-1],
                'status': 'failed',
                'errors': [{'message': str(e)}],
                'started_at': datetime.now().isoformat(),
            })
            print(f'\n!! {bot_path} crashed before execution: {e}\n')

    _write_summary_dashboard(all_metrics)


def _write_summary_dashboard(metrics_list: list[dict]):
    """Generate an HTML dashboard summarizing the run."""
    rows_html = ''
    for m in metrics_list:
        status = m.get('status', 'unknown')
        color = {'success': '#16a34a', 'partial': '#f59e0b',
                 'failed': '#dc2626'}.get(status, '#6b7280')
        rows_html += f"""
        <tr>
            <td>{m.get('bot_name', '?')}</td>
            <td><span style="color: {color}; font-weight: 600;">{status.upper()}</span></td>
            <td>{m.get('duration_seconds', 0)} s</td>
            <td>{m.get('items_processed', 0)}</td>
            <td>{m.get('items_failed', 0)}</td>
        </tr>
        """

    successful = sum(1 for m in metrics_list if m.get('status') == 'success')
    total = len(metrics_list)
    success_rate = (successful / total * 100) if total else 0

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>RPA Run Dashboard</title>
<style>
  body {{ font-family: -apple-system, sans-serif; max-width: 900px; margin: 40px auto;
         color: #1f2937; padding: 0 20px; }}
  h1 {{ color: #1e40af; border-bottom: 3px solid #2563eb; padding-bottom: 10px; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
  th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #e5e7eb; }}
  th {{ background: #f3f4f6; font-size: 13px; text-transform: uppercase; }}
  .summary {{ background: #f3f4f6; padding: 20px; border-radius: 8px;
              border-left: 4px solid #2563eb; margin: 20px 0; }}
</style></head><body>
<h1>🤖 RPA Run Dashboard</h1>
<p>Generated {datetime.now():%Y-%m-%d %H:%M:%S}</p>

<div class="summary">
  <strong>{successful}/{total}</strong> bots succeeded
  ({success_rate:.0f}% success rate)
</div>

<table>
  <thead><tr>
    <th>Bot</th><th>Status</th><th>Duration</th>
    <th>Processed</th><th>Failed</th>
  </tr></thead>
  <tbody>
{rows_html}
  </tbody>
</table>

<p style="color: #9ca3af; margin-top: 40px; font-size: 13px;">
  See <code>data/logs/</code> for individual bot metrics and full logs.
</p>
</body></html>"""

    out = OUTPUT_DIR / 'orchestrator_dashboard.html'
    with open(out, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'\nDashboard saved: {out}')

    # Also save raw metrics for downstream tools
    with open(LOG_DIR / 'orchestrator_summary.json', 'w', encoding='utf-8') as f:
        json.dump(metrics_list, f, indent=2, ensure_ascii=False)


if __name__ == '__main__':
    run_all()
