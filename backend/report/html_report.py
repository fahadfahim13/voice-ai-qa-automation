"""HTML + PDF report generator. WeasyPrint is optional; we degrade gracefully."""

from __future__ import annotations

import json
from pathlib import Path

from jinja2 import Template

REPORT_TEMPLATE = Template(
    r"""
<!doctype html>
<html><head><meta charset="utf-8"><title>BizFinder Voice QA — {{ suite_id }}</title>
<style>
body{font:14px/1.45 -apple-system,Segoe UI,Roboto,sans-serif;color:#1f2937;margin:24px;max-width:1100px}
h1{margin:0 0 4px;color:#111827}h2{margin:24px 0 8px;color:#111827}h3{margin:18px 0 4px}
.muted{color:#6b7280}
table{border-collapse:collapse;width:100%;margin:12px 0;font-size:13px}
th,td{border:1px solid #e5e7eb;padding:6px 8px;text-align:left;vertical-align:top}
th{background:#f3f4f6}
.pass{color:#047857;font-weight:600}.fail{color:#b91c1c;font-weight:600}.err{color:#a16207;font-weight:600}
.bar{display:inline-block;height:8px;background:#e5e7eb;border-radius:4px;width:120px;vertical-align:middle}
.bar > div{height:100%;background:#10b981;border-radius:4px}
.bar.warn > div{background:#f59e0b}
.bar.bad > div{background:#ef4444}
.evidence{font-style:italic;color:#374151}
.chip{display:inline-block;background:#eef2ff;color:#3730a3;border-radius:10px;padding:1px 8px;margin:0 4px 4px 0;font-size:11px}
.coverage-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px}
.coverage-grid h4{margin:0 0 4px;font-size:13px;color:#374151;text-transform:capitalize}
.coverage-grid table{margin:0;font-size:12px}
details{margin:8px 0}
summary{cursor:pointer;color:#4338ca}
audio{display:block;width:100%;margin:6px 0}
</style></head><body>
<h1>BizFinder Voice QA — Suite report</h1>
<p class="muted">{{ started_at }} → {{ finished_at }} · {{ n_total }} calls · avg score {{ '%.2f' % avg_overall_score }}</p>
<p>Business: <em>{{ business_summary }}</em></p>

<h2>Summary</h2>
<table>
<tr><th>Total</th><th>Passed</th><th>Failed</th><th>Errors</th><th>Avg score</th></tr>
<tr><td>{{ n_total }}</td><td class="pass">{{ n_passed }}</td><td class="fail">{{ n_failed }}</td><td class="err">{{ n_errors }}</td><td>{{ '%.2f' % avg_overall_score }}</td></tr>
</table>

{% if coverage_by_axis %}
<h2>Coverage by axis</h2>
<p class="muted">How many scenarios exercised each value of each test axis, and how they fared.</p>
<div class="coverage-grid">
{% for axis, values in coverage_by_axis.items() %}
  <div>
    <h4>{{ axis }}</h4>
    <table>
      <tr><th>Value</th><th>Total</th><th class="pass">Pass</th><th class="fail">Fail</th><th class="err">Err</th><th>Avg</th></tr>
      {% for vname, b in values.items() %}
      <tr>
        <td>{{ vname }}</td>
        <td>{{ b.total }}</td>
        <td class="pass">{{ b.passed }}</td>
        <td class="fail">{{ b.failed }}</td>
        <td class="err">{{ b.errors }}</td>
        <td>{{ '%.2f' % b.avg_score }}</td>
      </tr>
      {% endfor %}
    </table>
  </div>
{% endfor %}
</div>
{% endif %}

{% if failure_breakdown %}
<h2>Failure breakdown</h2>
<p class="muted">Every criterion that scored below 0.4, across all failing scenarios — grouped by criterion.</p>
<table>
  <tr><th>Criterion</th><th>Scenario</th><th>Title</th><th>Score</th><th>Evidence</th></tr>
{% for row in failure_breakdown %}
  <tr>
    <td>{{ row.criterion }}</td>
    <td>{{ row.scenario_id }}</td>
    <td>{{ row.title }}</td>
    <td class="fail">{{ '%.2f' % row.score }}</td>
    <td><span class="evidence">{{ row.evidence }}</span><br>{{ row.rationale }}</td>
  </tr>
{% endfor %}
</table>
{% endif %}

<h2>Calls</h2>
{% for c in calls %}
  {% set v = c.text_verdict %}
  <h3>{{ c.scenario_id }} —
    {% if c.error %}<span class="err">ERROR</span>
    {% elif v and v.pass_fail %}<span class="pass">PASS</span>
    {% elif v %}<span class="fail">FAIL</span>
    {% else %}<span class="err">NO VERDICT</span>
    {% endif %}
    {% if v %} · overall {{ '%.2f' % v.overall_score }}{% endif %}
  </h3>
  {% if c.scenario_title %}<p><strong>{{ c.scenario_title }}</strong></p>{% endif %}
  {% if c.axes %}<p>{% for ax, vv in c.axes.items() %}<span class="chip">{{ ax }}: {{ vv }}</span>{% endfor %}</p>{% endif %}
  <p class="muted">elapsed {{ '%.1f' % c.elapsed_seconds }}s · session {{ c.artifacts.session_id or '—' }}</p>
  {% if c.artifacts and c.artifacts.full_call_audio %}
    <details><summary>Listen to the full call (caller L · bot R)</summary>
      <audio controls preload="none" src="call_{{ c.scenario_id }}/full_call.wav"></audio>
    </details>
  {% endif %}
  {% if c.error %}<p class="fail">Error: {{ c.error }}</p>{% endif %}
  {% if v %}
  <p>{{ v.summary }}</p>
  <table>
    <tr><th>Criterion</th><th>Score</th><th></th><th>Evidence</th></tr>
  {% for cr in v.criteria %}
    <tr>
      <td>{{ cr.name }}</td>
      <td>{{ '%.2f' % cr.score }}</td>
      <td><span class="bar {% if cr.score < 0.4 %}bad{% elif cr.score < 0.7 %}warn{% endif %}"><div style="width:{{ (cr.score*100)|round(0) }}%"></div></span></td>
      <td><span class="evidence">{{ cr.evidence }}</span><br>{{ cr.rationale }}</td>
    </tr>
  {% endfor %}
  </table>
  {% endif %}
  {% if c.audio_verdict and not c.audio_verdict.get('error') %}
    <p><strong>Audio judge:</strong>
       tts_pron {{ '%.2f' % c.audio_verdict.tts_pronunciation }} ·
       audio {{ '%.2f' % c.audio_verdict.audio_quality }} ·
       naturalness {{ '%.2f' % c.audio_verdict.naturalness }}
       {% if c.audio_verdict.issues %}<br>Issues: {{ c.audio_verdict.issues|join(', ') }}{% endif %}
    </p>
  {% endif %}
{% endfor %}

</body></html>
"""
)


def render_html(suite_dict: dict, suite_id: str = "") -> str:
    return REPORT_TEMPLATE.render(suite_id=suite_id, **suite_dict)


def write_report(suite_path: Path) -> tuple[Path, Path | None]:
    """Reads suite.json next to suite_path (or suite_path itself), writes report.html
    + (optionally) report.pdf. Returns paths.
    """
    if suite_path.is_dir():
        suite_path = suite_path / "suite.json"
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    html = render_html(suite, suite_id=suite_path.parent.name)
    html_path = suite_path.parent / "report.html"
    html_path.write_text(html, encoding="utf-8")

    pdf_path: Path | None = None
    try:
        from weasyprint import HTML  # type: ignore

        pdf_path = suite_path.parent / "report.pdf"
        HTML(string=html, base_url=str(suite_path.parent)).write_pdf(str(pdf_path))
    except Exception:
        pass

    return html_path, pdf_path
