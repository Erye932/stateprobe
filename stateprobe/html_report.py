"""HTML report generator.

Produces a self-contained HTML file with:
- Radar chart (current vs target) via Chart.js CDN
- Alignment score gauge
- Pollution sources list with explanations + paper citations
- Concrete rewrite suggestions with copy-paste examples

No build step, no server — just open the .html in a browser.
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Dict

from stateprobe.models import Axis, Report


_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>StateProbe Report — {target_label}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
                 "Microsoft YaHei", "Helvetica Neue", Arial, sans-serif;
    background: #0a0e1a;
    color: #e5e7eb;
    line-height: 1.6;
    padding: 32px 16px;
  }}
  .container {{
    max-width: 960px;
    margin: 0 auto;
  }}
  header {{
    text-align: center;
    margin-bottom: 32px;
  }}
  h1 {{
    font-size: 28px;
    font-weight: 700;
    background: linear-gradient(120deg, #60a5fa, #a78bfa);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin-bottom: 4px;
  }}
  .subtitle {{
    color: #94a3b8;
    font-size: 14px;
  }}
  .card {{
    background: #111827;
    border: 1px solid #1f2937;
    border-radius: 12px;
    padding: 24px;
    margin-bottom: 20px;
  }}
  .card h2 {{
    font-size: 18px;
    margin-bottom: 16px;
    color: #f3f4f6;
    display: flex;
    align-items: center;
    gap: 8px;
  }}
  .card h2 .badge {{
    font-size: 11px;
    padding: 2px 8px;
    border-radius: 999px;
    background: #1f2937;
    color: #94a3b8;
    font-weight: 400;
  }}
  .prompt-box {{
    background: #0f172a;
    border-left: 3px solid #60a5fa;
    padding: 12px 16px;
    font-family: "SF Mono", Menlo, Consolas, monospace;
    font-size: 13px;
    color: #cbd5e1;
    white-space: pre-wrap;
    word-break: break-word;
    border-radius: 4px;
  }}
  .target-info {{
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    align-items: baseline;
    margin-bottom: 8px;
  }}
  .target-name {{
    font-size: 16px;
    font-weight: 600;
    color: #a78bfa;
  }}
  .target-desc {{
    color: #94a3b8;
    font-size: 13px;
  }}
  .chart-wrapper {{
    position: relative;
    height: 480px;
    margin: 8px auto;
  }}
  .alignment {{
    display: flex;
    align-items: center;
    gap: 12px;
    margin-top: 12px;
    padding: 12px 16px;
    background: #0f172a;
    border-radius: 8px;
  }}
  .alignment-label {{
    color: #94a3b8;
    font-size: 13px;
  }}
  .alignment-score {{
    font-size: 22px;
    font-weight: 700;
  }}
  .alignment-score.good {{ color: #34d399; }}
  .alignment-score.mid  {{ color: #fbbf24; }}
  .alignment-score.bad  {{ color: #f87171; }}
  .pollution-item {{
    background: #0f172a;
    border-left: 3px solid #f87171;
    padding: 12px 16px;
    margin-bottom: 12px;
    border-radius: 4px;
  }}
  .pollution-item.positive {{ border-left-color: #34d399; }}
  .pollution-axis {{
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: #94a3b8;
    margin-bottom: 4px;
  }}
  .pollution-text {{
    font-family: "SF Mono", Menlo, Consolas, monospace;
    color: #fcd34d;
    background: #1f2937;
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 13px;
    display: inline-block;
    margin-bottom: 6px;
  }}
  .pollution-explanation {{
    color: #cbd5e1;
    font-size: 14px;
    margin-bottom: 6px;
  }}
  .pollution-citation {{
    color: #6b7280;
    font-size: 11px;
    font-style: italic;
  }}
  .suggestion-item {{
    background: #0f172a;
    border-left: 3px solid #60a5fa;
    padding: 12px 16px;
    margin-bottom: 12px;
    border-radius: 4px;
  }}
  .suggestion-axis {{
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: #94a3b8;
    margin-bottom: 4px;
  }}
  .suggestion-action {{
    display: inline-block;
    font-size: 10px;
    padding: 1px 6px;
    border-radius: 3px;
    margin-left: 4px;
    text-transform: uppercase;
    font-weight: 600;
  }}
  .suggestion-action.add {{
    background: rgba(52, 211, 153, 0.2);
    color: #34d399;
  }}
  .suggestion-action.remove {{
    background: rgba(248, 113, 113, 0.2);
    color: #f87171;
  }}
  .suggestion-desc {{
    color: #e5e7eb;
    font-size: 14px;
    margin-bottom: 8px;
  }}
  .suggestion-example {{
    background: #1e293b;
    padding: 8px 12px;
    border-radius: 4px;
    font-family: "SF Mono", Menlo, Consolas, monospace;
    font-size: 13px;
    color: #93c5fd;
    white-space: pre-wrap;
  }}
  .axis-readings {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 12px;
  }}
  .axis-row {{
    background: #0f172a;
    padding: 10px 12px;
    border-radius: 6px;
  }}
  .axis-row-label {{
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 6px;
    font-size: 13px;
  }}
  .axis-row-name {{ color: #e5e7eb; font-weight: 500; }}
  .axis-row-value {{ color: #94a3b8; font-variant-numeric: tabular-nums; }}
  .axis-row-bar {{
    position: relative;
    height: 6px;
    background: #1f2937;
    border-radius: 3px;
    overflow: hidden;
  }}
  .axis-row-bar-fill {{
    position: absolute;
    top: 0; left: 0; bottom: 0;
    background: linear-gradient(90deg, #60a5fa, #a78bfa);
    border-radius: 3px;
  }}
  .axis-row-bar-target {{
    position: absolute;
    top: -2px; bottom: -2px;
    width: 2px;
    background: #fbbf24;
  }}
  .axis-row-extremes {{
    display: flex;
    justify-content: space-between;
    font-size: 10px;
    color: #6b7280;
    margin-top: 2px;
  }}
  footer {{
    text-align: center;
    color: #4b5563;
    font-size: 12px;
    margin-top: 24px;
    padding: 16px;
  }}
  footer a {{ color: #60a5fa; text-decoration: none; }}
  .empty-msg {{
    color: #6b7280;
    text-align: center;
    padding: 16px;
    font-size: 14px;
    font-style: italic;
  }}
</style>
</head>
<body>
<div class="container">

  <header>
    <h1>StateProbe</h1>
    <div class="subtitle">Prompt 状态诊断报告 · 当前坐标 vs 目标坐标</div>
  </header>

  <div class="card">
    <h2>原始 Prompt <span class="badge">输入</span></h2>
    <div class="prompt-box">{prompt_html}</div>
  </div>

  <div class="card">
    <h2>目标状态 <span class="badge">target</span></h2>
    <div class="target-info">
      <span class="target-name">{target_label}</span>
      <span class="target-desc">{target_desc}</span>
    </div>
  </div>

  <div class="card">
    <h2>坐标系雷达图 <span class="badge">激活向量</span></h2>
    <div class="chart-wrapper">
      <canvas id="radar"></canvas>
    </div>
    <div class="alignment">
      <span class="alignment-label">与目标对齐度</span>
      <span class="alignment-score {alignment_class}">{alignment_pct}%</span>
    </div>
  </div>

  <div class="card">
    <h2>各轴读数详情</h2>
    <div class="axis-readings">
      {axis_readings_html}
    </div>
  </div>

  <div class="card">
    <h2>污染源 <span class="badge">{pollution_count} 条</span></h2>
    {pollution_html}
  </div>

  <div class="card">
    <h2>改写建议 <span class="badge">{suggestion_count} 条</span></h2>
    {suggestions_html}
  </div>

  <footer>
    Powered by <a href="https://github.com">StateProbe</a> ·
    理论基础: Anthropic Persona Vectors (arXiv:2507.21509), DeepSeek-R1 (arXiv:2501.12948)
  </footer>

</div>

<script>
const labels = {labels_json};
const currentData = {current_json};
const targetData = {target_json};

const ctx = document.getElementById('radar').getContext('2d');
new Chart(ctx, {{
  type: 'radar',
  data: {{
    labels: labels,
    datasets: [
      {{
        label: '当前激活',
        data: currentData,
        backgroundColor: 'rgba(96, 165, 250, 0.25)',
        borderColor: '#60a5fa',
        borderWidth: 2,
        pointBackgroundColor: '#60a5fa',
        pointRadius: 4,
      }},
      {{
        label: '目标坐标',
        data: targetData,
        backgroundColor: 'rgba(251, 191, 36, 0.10)',
        borderColor: '#fbbf24',
        borderWidth: 2,
        borderDash: [6, 4],
        pointBackgroundColor: '#fbbf24',
        pointRadius: 4,
      }},
    ],
  }},
  options: {{
    responsive: true,
    maintainAspectRatio: false,
    plugins: {{
      legend: {{
        position: 'top',
        labels: {{ color: '#e5e7eb', font: {{ size: 13 }} }},
      }},
      tooltip: {{
        callbacks: {{
          label: function(ctx) {{
            return ctx.dataset.label + ': ' + (ctx.parsed.r * 100).toFixed(0) + '%';
          }}
        }}
      }}
    }},
    scales: {{
      r: {{
        suggestedMin: 0,
        suggestedMax: 1,
        ticks: {{
          stepSize: 0.25,
          color: '#6b7280',
          backdropColor: 'transparent',
          callback: v => Math.round(v * 100) + '%',
        }},
        grid: {{ color: '#1f2937' }},
        angleLines: {{ color: '#1f2937' }},
        pointLabels: {{
          color: '#cbd5e1',
          font: {{ size: 12, weight: '500' }},
        }},
      }},
    }},
  }},
}});
</script>
</body>
</html>
"""


def _alignment_class(score: float) -> str:
    if score >= 0.80:
        return "good"
    if score >= 0.55:
        return "mid"
    return "bad"


def _format_axis_readings(report: Report) -> str:
    rows = []
    for axis in Axis:
        reading = report.readings[axis]
        target_val = report.target.coordinates.get(axis, 0.5)
        rows.append(
            f"""<div class="axis-row">
  <div class="axis-row-label">
    <span class="axis-row-name">{html.escape(axis.label_zh)}</span>
    <span class="axis-row-value">{reading.value*100:.0f}% / 目标 {target_val*100:.0f}%</span>
  </div>
  <div class="axis-row-bar">
    <div class="axis-row-bar-fill" style="width: {reading.value*100:.1f}%"></div>
    <div class="axis-row-bar-target" style="left: {target_val*100:.1f}%"></div>
  </div>
  <div class="axis-row-extremes">
    <span>{html.escape(axis.low_end_zh)}</span>
    <span>{html.escape(axis.high_end_zh)}</span>
  </div>
</div>"""
        )
    return "\n".join(rows)


def _format_pollution(report: Report) -> str:
    sources = report.pollution_sources
    if not sources:
        return '<div class="empty-msg">未检测到显著污染源。</div>'
    # Sort by weight desc for impact-first display.
    sources_sorted = sorted(sources, key=lambda s: s.weight, reverse=True)
    items = []
    for src in sources_sorted:
        cls = "positive" if src.direction < 0 else ""
        sign = "↓" if src.direction < 0 else "↑"
        items.append(
            f"""<div class="pollution-item {cls}">
  <div class="pollution-axis">{html.escape(src.axis.label_zh)} {sign} 权重 {src.weight:.2f}</div>
  <div><span class="pollution-text">{html.escape(src.matched_text)}</span></div>
  <div class="pollution-explanation">{html.escape(src.explanation_zh)}</div>
  <div class="pollution-citation">依据: {html.escape(src.citation)}</div>
</div>"""
        )
    return "\n".join(items)


def _format_suggestions(report: Report) -> str:
    if not report.suggestions:
        return '<div class="empty-msg">✓ 当前 prompt 已经对齐目标坐标，无需改写。</div>'
    items = []
    for sug in report.suggestions:
        example_html = ""
        if sug.example_zh:
            example_html = (
                f'<div class="suggestion-example">{html.escape(sug.example_zh)}</div>'
            )
        items.append(
            f"""<div class="suggestion-item">
  <div class="suggestion-axis">
    {html.escape(sug.axis.label_zh)}
    <span class="suggestion-action {html.escape(sug.action)}">{html.escape(sug.action)}</span>
  </div>
  <div class="suggestion-desc">{html.escape(sug.description_zh)}</div>
  {example_html}
</div>"""
        )
    return "\n".join(items)


def render_html(report: Report) -> str:
    """Render a complete, self-contained HTML report."""
    labels = [axis.label_zh for axis in Axis]
    current_data = [report.readings[axis].value for axis in Axis]
    target_data = [report.target.coordinates.get(axis, 0.5) for axis in Axis]

    return _TEMPLATE.format(
        prompt_html=html.escape(report.prompt),
        target_label=html.escape(report.target.label_zh),
        target_desc=html.escape(report.target.description_zh),
        alignment_pct=f"{report.alignment_score * 100:.0f}",
        alignment_class=_alignment_class(report.alignment_score),
        axis_readings_html=_format_axis_readings(report),
        pollution_count=len(report.pollution_sources),
        pollution_html=_format_pollution(report),
        suggestion_count=len(report.suggestions),
        suggestions_html=_format_suggestions(report),
        labels_json=json.dumps(labels, ensure_ascii=False),
        current_json=json.dumps(current_data),
        target_json=json.dumps(target_data),
    )


def write_report(report: Report, output_path: Path) -> Path:
    """Render and write the HTML report to disk. Returns the path written."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_html(report), encoding="utf-8")
    return output_path
