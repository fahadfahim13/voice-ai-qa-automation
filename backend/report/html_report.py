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
body{font:14px/1.45 -apple-system,Segoe UI,Roboto,sans-serif;color:#1f2937;margin:24px}
h1{margin:0 0 4px;color:#111827}h2{margin:24px 0 8px;color:#111827}
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
</style></head><body>
<h1>BizFinder Voice QA — Suite report</h1>
<p class="muted">{{ started_at }} → {{ finished_at }} · {{ n_total }} calls · avg score {{ '%.2f' % avg_overall_score }}</p>
<p>Business: <em>{{ business_summary }}</em></p>

<h2>Summary</h2>
<table>
<tr><th>Total</th><th>Passed</th><th>Failed</th><th>Errors</th><th>Avg score</th></tr>
<tr><td>{{ n_total }}</td><td class="pass">{{ n_passed }}</td><td class="fail">{{ n_failed }}</td><td class="err">{{ n_errors }}</td><td>{{ '%.2f' % avg_overall_score }}</td></tr>
</table>

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
  <p class="muted">elapsed {{ '%.1f' % c.elapsed_seconds }}s · session {{ c.artifacts.session_id or '—' }}</p>
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
