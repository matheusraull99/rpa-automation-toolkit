"""Generate architecture diagram and dashboard preview."""
import sys
from pathlib import Path

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

IMG = Path('/home/claude/rpa-automation-toolkit/images')
IMG.mkdir(exist_ok=True)

plt.rcParams.update({'figure.dpi': 100, 'savefig.dpi': 150, 'savefig.bbox': 'tight'})


def plot_architecture():
    fig, ax = plt.subplots(figsize=(13, 8))
    ax.set_xlim(0, 13)
    ax.set_ylim(0, 8)
    ax.axis('off')

    # Orchestrator (top center)
    orch = FancyBboxPatch((4, 6.3), 5, 1, boxstyle='round,pad=0.1',
                           edgecolor='#1e40af', facecolor='#dbeafe', linewidth=2)
    ax.add_patch(orch)
    ax.text(6.5, 6.8, 'Orchestrator', ha='center', va='center',
            fontsize=14, fontweight='bold', color='#1e40af')

    # Base framework (under orchestrator)
    base = FancyBboxPatch((4.5, 4.8), 4, 0.9, boxstyle='round,pad=0.1',
                           edgecolor='#7c3aed', facecolor='#ede9fe', linewidth=2)
    ax.add_patch(base)
    ax.text(6.5, 5.25, 'BaseAutomation\n(logging · retry · metrics)',
            ha='center', va='center', fontsize=10, color='#5b21b6')

    # Four bots
    bots = [
        ('Web Scraper\nBot', 0.5, 2.5, '#16a34a', '#dcfce7'),
        ('Excel Consolidator\nBot', 3.7, 2.5, '#f59e0b', '#fef3c7'),
        ('Report Generator\nBot', 6.9, 2.5, '#dc2626', '#fee2e2'),
        ('CRM-ERP Sync\nBot', 10.1, 2.5, '#0891b2', '#cffafe'),
    ]
    for name, x, y, edge, fill in bots:
        bot = FancyBboxPatch((x, y), 2.6, 1.4, boxstyle='round,pad=0.1',
                              edgecolor=edge, facecolor=fill, linewidth=2)
        ax.add_patch(bot)
        ax.text(x + 1.3, y + 0.7, name, ha='center', va='center',
                fontsize=10, fontweight='bold', color=edge)
        # Arrow from base to bot
        ax.annotate('', xy=(x + 1.3, y + 1.4), xytext=(6.5, 4.8),
                    arrowprops=dict(arrowstyle='->', color='#9ca3af', lw=1.5))

    # Outputs
    outputs = FancyBboxPatch((3.5, 0.3), 6, 1, boxstyle='round,pad=0.1',
                              edgecolor='#374151', facecolor='#f3f4f6', linewidth=2)
    ax.add_patch(outputs)
    ax.text(6.5, 0.8, 'Outputs · CSV · Excel · PDF · Database · Logs',
            ha='center', va='center', fontsize=11, color='#374151')

    for _, x, y, _, _ in bots:
        ax.annotate('', xy=(x + 1.3, 1.3), xytext=(x + 1.3, 2.5),
                    arrowprops=dict(arrowstyle='->', color='#9ca3af', lw=1.5))

    # Title
    ax.text(6.5, 7.8, 'RPA Automation Toolkit — Architecture',
            ha='center', va='center', fontsize=15, fontweight='bold', color='#1f2937')

    plt.tight_layout()
    plt.savefig(IMG / 'architecture.png')
    plt.close()
    print('saved architecture.png')


def plot_run_metrics():
    """Visualize a sample orchestrator run."""
    import json
    summary_path = Path('/home/claude/rpa-automation-toolkit/data/logs/orchestrator_summary.json')
    if summary_path.exists():
        with open(summary_path) as f:
            metrics = json.load(f)
    else:
        # Fallback mock
        metrics = [
            {'bot_name': 'PublicAPIScraperBot', 'duration_seconds': 0.10,
             'items_processed': 10, 'status': 'success'},
            {'bot_name': 'ExcelConsolidatorBot', 'duration_seconds': 0.31,
             'items_processed': 3, 'status': 'success'},
            {'bot_name': 'WeeklyReportBot', 'duration_seconds': 0.40,
             'items_processed': 592, 'status': 'success'},
            {'bot_name': 'CrmErpSyncBot', 'duration_seconds': 0.03,
             'items_processed': 47, 'status': 'success'},
        ]

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    names = [m['bot_name'].replace('Bot', '') for m in metrics]
    durations = [m['duration_seconds'] for m in metrics]
    items = [m['items_processed'] for m in metrics]
    colors = ['#16a34a' if m['status'] == 'success' else '#dc2626' for m in metrics]

    axes[0].barh(names, durations, color=colors)
    axes[0].set_title('Bot Execution Time', fontweight='bold')
    axes[0].set_xlabel('Duration (seconds)')
    axes[0].invert_yaxis()
    for i, v in enumerate(durations):
        axes[0].text(v + 0.01, i, f'{v:.2f}s', va='center', fontsize=9)

    axes[1].barh(names, items, color=colors)
    axes[1].set_title('Items Processed', fontweight='bold')
    axes[1].set_xlabel('Count')
    axes[1].invert_yaxis()
    for i, v in enumerate(items):
        axes[1].text(v, i, f'  {v:,}', va='center', fontsize=9)

    plt.tight_layout()
    plt.savefig(IMG / 'run_metrics.png')
    plt.close()
    print('saved run_metrics.png')


if __name__ == '__main__':
    plot_architecture()
    plot_run_metrics()
