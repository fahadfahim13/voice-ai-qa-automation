"""HTML + PDF report generator. WeasyPrint is optional; we degrade gracefully."""

from __future__ import annotations

import json
from pathlib import Path

from jinja2 import Template

REPORT_TEMPLATE = Template(
    r"""
<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>BizFinder Voice QA — {{ suite_id }}</title>
<style>
:root{
  --ink:#eef1f7;--ink-soft:#cdd3e0;--muted:#a3acc2;
  --line:rgba(255,255,255,.08);--line-strong:rgba(255,255,255,.16);
  --card:rgba(255,255,255,.045);--card-hover:rgba(255,255,255,.07);--card-solid:#14171f;
  --brand:#7c5cff;--brand-2:#9b8cff;
  --good:#34d399;--good-bg:rgba(52,211,153,.12);--bad:#f87171;--bad-bg:rgba(248,113,113,.12);--warn:#fbbf24;--warn-bg:rgba(251,191,36,.12);
  --shadow:0 1px 0 rgba(255,255,255,.06) inset,0 2px 8px rgba(0,0,0,.45),0 18px 44px -20px rgba(0,0,0,.75);
  --glow:0 0 28px -8px rgba(124,92,255,.5);
  --ease:cubic-bezier(.22,.61,.36,1);
  --radius:18px;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%;scrollbar-width:thin;scrollbar-color:rgba(255,255,255,.18) transparent}
body{
  font:15px/1.6 "Inter",-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  color:var(--ink-soft);margin:0;padding:32px 20px 72px;min-height:100vh;
  background:#080a0f;position:relative;overflow-x:hidden;
  -webkit-font-smoothing:antialiased;-moz-osx-font-smoothing:grayscale;text-rendering:optimizeLegibility;
}
::-webkit-scrollbar{width:11px;height:11px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:rgba(255,255,255,.12);border-radius:999px;border:3px solid transparent;background-clip:content-box}
::-webkit-scrollbar-thumb:hover{background:rgba(255,255,255,.20);background-clip:content-box}
/* Animated near-black / OLED backdrop with a minimal indigo-violet glow */
body::before{
  content:"";position:fixed;inset:-20%;z-index:-2;
  background:
    radial-gradient(60% 50% at 20% 0%,rgba(124,92,255,.10),transparent 60%),
    radial-gradient(50% 50% at 88% 8%,rgba(80,70,229,.08),transparent 60%),
    linear-gradient(160deg,#0b0d13,#080a0f);
  background-size:160% 160%;
  animation:bgShift 24s ease-in-out infinite;
}
body::after{
  content:"";position:fixed;inset:0;z-index:-1;pointer-events:none;
  background:radial-gradient(100% 80% at 50% -10%,rgba(124,92,255,.06),transparent 60%);
}
@keyframes bgShift{
  0%{background-position:0% 50%}50%{background-position:100% 50%}100%{background-position:0% 50%}
}
.wrap{max-width:1120px;margin:0 auto}

/* Hero */
.hero{
  background:linear-gradient(135deg,#5b3fd6,#7c5cff);
  color:#fff;border-radius:24px;padding:30px 34px;box-shadow:var(--shadow);
  position:relative;overflow:hidden;animation:rise .7s var(--ease) both;
}
.hero::after{content:"";position:absolute;inset:0;background:radial-gradient(60% 120% at 90% -20%,rgba(255,255,255,.25),transparent 60%);pointer-events:none}
.hero .eyebrow{font-size:12px;letter-spacing:.18em;text-transform:uppercase;opacity:.85;margin:0 0 6px;font-weight:600}
.hero h1{margin:0;font-size:clamp(24px,3.6vw,34px);font-weight:750;letter-spacing:-.025em;line-height:1.1}
.hero .meta{margin:16px 0 0;display:flex;flex-wrap:wrap;gap:8px}
.hero .pill{background:rgba(255,255,255,.16);border:1px solid rgba(255,255,255,.22);backdrop-filter:blur(4px);border-radius:999px;padding:5px 13px;font-size:12.5px;font-weight:500;font-variant-numeric:tabular-nums}
.hero .biz{margin:14px 0 0;font-size:13.5px;opacity:.92}

/* Sections + cards */
section{margin-top:30px;animation:rise .7s var(--ease) both}
section:nth-of-type(2){animation-delay:.06s}
section:nth-of-type(3){animation-delay:.12s}
section:nth-of-type(4){animation-delay:.18s}
h2{margin:0 0 4px;font-size:19px;font-weight:750;letter-spacing:-.02em;color:var(--ink)}
h2 .lead{font-weight:400;color:var(--muted);font-size:13px;display:block;margin-top:3px}
.card{background:var(--card);backdrop-filter:blur(10px);border:1px solid var(--line);border-radius:var(--radius);box-shadow:var(--shadow);padding:20px 22px;margin-top:14px}
.muted{color:var(--muted)}

/* Stat tiles */
.stats{display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin-top:16px}
.stat{background:var(--card);backdrop-filter:blur(10px);border:1px solid var(--line);border-radius:16px;box-shadow:var(--shadow);padding:18px 18px;transition:transform .3s var(--ease),border-color .3s var(--ease),background .3s var(--ease),box-shadow .3s var(--ease);animation:rise .55s var(--ease) both}
.stat:nth-child(1){animation-delay:.05s}.stat:nth-child(2){animation-delay:.10s}.stat:nth-child(3){animation-delay:.15s}.stat:nth-child(4){animation-delay:.20s}.stat:nth-child(5){animation-delay:.25s}
.stat:hover{transform:translateY(-4px);border-color:var(--line-strong);background:var(--card-hover);box-shadow:var(--shadow),var(--glow)}
.stat .k{font-size:12px;text-transform:uppercase;letter-spacing:.09em;color:var(--muted);font-weight:600}
.stat .v{font-size:30px;font-weight:750;line-height:1.1;margin-top:6px;letter-spacing:-.02em;font-variant-numeric:tabular-nums}
.stat.s-pass .v{color:var(--good)}.stat.s-fail .v{color:var(--bad)}.stat.s-err .v{color:var(--warn)}

/* Tables */
.tablewrap{overflow-x:auto;-webkit-overflow-scrolling:touch;border-radius:12px}
table{border-collapse:collapse;width:100%;font-size:13.5px;font-variant-numeric:tabular-nums}
th,td{padding:10px 12px;text-align:left;vertical-align:top;border-bottom:1px solid var(--line)}
th{background:rgba(255,255,255,.05);color:var(--muted);font-weight:650;font-size:12px;text-transform:uppercase;letter-spacing:.04em;position:sticky;top:0}
tbody tr{transition:background .15s ease}
tbody tr:hover{background:rgba(124,92,255,.10)}
td:last-child,th:last-child{border-right:0}

.pass{color:var(--good);font-weight:650}.fail{color:var(--bad);font-weight:650}.err{color:var(--warn);font-weight:650}
.evidence{font-style:italic;color:var(--ink-soft)}

/* Score bar */
.bar{display:inline-block;height:9px;background:rgba(255,255,255,.10);border-radius:999px;width:120px;max-width:40vw;vertical-align:middle;overflow:hidden;position:relative}
.bar > div{height:100%;background:linear-gradient(90deg,#10b981,#34d399);border-radius:999px;transform-origin:left;animation:grow 1s var(--ease) both;position:relative;overflow:hidden}
.bar > div::after{content:"";position:absolute;inset:0;background:linear-gradient(100deg,transparent 20%,rgba(255,255,255,.45) 50%,transparent 80%);transform:translateX(-120%);animation:sheen 1.6s var(--ease) .9s 1 both}
.bar.warn > div{background:linear-gradient(90deg,#f59e0b,#fbbf24)}
.bar.bad > div{background:linear-gradient(90deg,#ef4444,#f87171)}

/* Chips */
.chip{display:inline-block;background:rgba(124,92,255,.14);color:#c7bbff;border:1px solid rgba(124,92,255,.25);border-radius:999px;padding:3px 11px;margin:0 6px 6px 0;font-size:11.5px;font-weight:550}

/* Coverage grid */
.coverage-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:16px;margin-top:14px}
.coverage-grid .card{margin-top:0;padding:16px 16px}
.coverage-grid h4{margin:0 0 10px;font-size:13.5px;color:var(--ink);text-transform:capitalize;font-weight:650}
.coverage-grid table{font-size:12.5px}

/* Calls */
.call{background:var(--card);backdrop-filter:blur(10px);border:1px solid var(--line);border-radius:var(--radius);box-shadow:var(--shadow);padding:20px 22px;margin-top:16px;border-left:4px solid var(--muted);transition:transform .25s var(--ease),border-color .25s var(--ease),background .25s var(--ease),box-shadow .25s var(--ease);animation:rise .55s var(--ease) both}
.call:nth-of-type(1){animation-delay:.04s}.call:nth-of-type(2){animation-delay:.08s}.call:nth-of-type(3){animation-delay:.12s}.call:nth-of-type(4){animation-delay:.16s}.call:nth-of-type(5){animation-delay:.20s}.call:nth-of-type(6){animation-delay:.24s}
.call:hover{transform:translateY(-2px);border-color:var(--line-strong);background:var(--card-hover);box-shadow:var(--shadow),var(--glow)}
.call.is-pass{border-left-color:var(--good)}
.call.is-fail{border-left-color:var(--bad)}
.call.is-err{border-left-color:var(--warn)}
.call h3{margin:0;display:flex;align-items:center;flex-wrap:wrap;gap:10px;font-size:16px;letter-spacing:-.01em}
.badge{font-size:11px;font-weight:700;letter-spacing:.05em;padding:3px 10px;border-radius:999px}
.badge.pass{color:var(--good);background:var(--good-bg)}
.badge.fail{color:var(--bad);background:var(--bad-bg)}
.badge.err{color:var(--warn);background:var(--warn-bg)}
.call .score{margin-left:auto;font-size:13px;color:var(--muted);font-weight:600;font-variant-numeric:tabular-nums}
.call .title{margin:10px 0 0;font-weight:650;font-size:14.5px}
.call .summary{margin:12px 0 0;color:var(--ink-soft)}
.audiobox{margin-top:12px}
details{margin:12px 0 0}
summary{cursor:pointer;color:var(--brand-2);font-weight:600;font-size:13.5px;user-select:none}
summary::marker{color:var(--brand-2)}
audio{display:block;width:100%;margin:10px 0 0}
.audio-judge{margin-top:14px;font-size:13px;color:var(--ink-soft);background:rgba(255,255,255,.04);border:1px solid var(--line);border-radius:12px;padding:12px 14px}

@keyframes rise{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:none}}
@keyframes grow{from{transform:scaleX(0)}to{transform:scaleX(1)}}
@keyframes sheen{from{transform:translateX(-120%)}to{transform:translateX(120%)}}

/* Responsive */
@media (max-width:860px){
  .stats{grid-template-columns:repeat(2,1fr)}
}
@media (max-width:560px){
  body{padding:18px 12px 56px}
  .hero{padding:22px 20px;border-radius:20px}
  .card,.call{padding:16px 16px}
  .stats{grid-template-columns:repeat(2,1fr);gap:10px}
  .stat .v{font-size:24px}
  .call h3{font-size:15px}
  .call .score{margin-left:0;width:100%}
}
@media (prefers-reduced-motion:reduce){
  *,body::before{animation:none!important;transition:none!important}
}
/* Clean, LIGHT, static layout for the PDF render (dark UI is screen-only) */
@media print{
  body{background:#fff;padding:0;color:#0f172a}
  body::before,body::after{display:none}
  .wrap{max-width:none}
  .card,.call,.stat{box-shadow:none;backdrop-filter:none;background:#fff;border:1px solid #e5e7eb;color:#1f2937}
  .hero{box-shadow:none;background:linear-gradient(135deg,#5b3fd6,#7c5cff)}
  h2,.coverage-grid h4,.call h3{color:#111827}
  .muted,.call .score,.stat .k{color:#6b7280}
  .summary,.evidence,.title{color:#374151}
  th{background:#f3f4f6;color:#374151}
  td,th{border-color:#e5e7eb}
  .bar{background:#e9edf5}
  .chip{background:#eef2ff;color:#3730a3;border-color:#e0e7ff}
  .audio-judge{background:#f9fafb;border-color:#e5e7eb;color:#374151}
  .pass{color:#047857}.fail{color:#b91c1c}.err{color:#a16207}
  .stat.s-pass .v{color:#047857}.stat.s-fail .v{color:#b91c1c}.stat.s-err .v{color:#a16207}
  .badge.pass{color:#047857;background:#ecfdf5}.badge.fail{color:#b91c1c;background:#fef2f2}.badge.err{color:#a16207;background:#fffbeb}
  *{animation:none!important}
}
</style></head><body>
<div class="wrap">

<header class="hero">
  <p class="eyebrow">BizFinder Voice QA</p>
  <h1>Suite report</h1>
  <div class="meta">
    <span class="pill">{{ started_at }} → {{ finished_at }}</span>
    <span class="pill">{{ n_total }} calls</span>
    <span class="pill">avg score {{ '%.2f' % avg_overall_score }}</span>
  </div>
  <p class="biz">Business: <em>{{ business_summary }}</em></p>
</header>

<section>
<h2>Summary</h2>
<div class="stats">
  <div class="stat"><div class="k">Total</div><div class="v">{{ n_total }}</div></div>
  <div class="stat s-pass"><div class="k">Passed</div><div class="v">{{ n_passed }}</div></div>
  <div class="stat s-fail"><div class="k">Failed</div><div class="v">{{ n_failed }}</div></div>
  <div class="stat s-err"><div class="k">Errors</div><div class="v">{{ n_errors }}</div></div>
  <div class="stat"><div class="k">Avg score</div><div class="v">{{ '%.2f' % avg_overall_score }}</div></div>
</div>
</section>

{% if coverage_by_axis %}
<section>
<h2>Coverage by axis<span class="lead">How many scenarios exercised each value of each test axis, and how they fared.</span></h2>
<div class="coverage-grid">
{% for axis, values in coverage_by_axis.items() %}
  <div class="card">
    <h4>{{ axis }}</h4>
    <div class="tablewrap">
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
  </div>
{% endfor %}
</div>
</section>
{% endif %}

{% if failure_breakdown %}
<section>
<h2>Failure breakdown<span class="lead">Every criterion that scored below 0.4, across all failing scenarios — grouped by criterion.</span></h2>
<div class="card">
<div class="tablewrap">
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
</div>
</div>
</section>
{% endif %}

<section>
<h2>Calls</h2>
{% for c in calls %}
  {% set v = c.text_verdict %}
  <article class="call {% if c.error %}is-err{% elif v and v.pass_fail %}is-pass{% elif v %}is-fail{% else %}is-err{% endif %}">
  <h3>
    <span>{{ c.scenario_id }}</span>
    {% if c.error %}<span class="badge err">ERROR</span>
    {% elif v and v.pass_fail %}<span class="badge pass">PASS</span>
    {% elif v %}<span class="badge fail">FAIL</span>
    {% else %}<span class="badge err">NO VERDICT</span>
    {% endif %}
    {% if v %}<span class="score">overall {{ '%.2f' % v.overall_score }}</span>{% endif %}
  </h3>
  {% if c.scenario_title %}<p class="title">{{ c.scenario_title }}</p>{% endif %}
  {% if c.axes %}<p style="margin:10px 0 0">{% for ax, vv in c.axes.items() %}<span class="chip">{{ ax }}: {{ vv }}</span>{% endfor %}</p>{% endif %}
  <p class="muted" style="margin:10px 0 0;font-size:12.5px">elapsed {{ '%.1f' % c.elapsed_seconds }}s · session {{ c.artifacts.session_id or '—' }}</p>
  {% if c.artifacts and c.artifacts.full_call_audio %}
    <details class="audiobox"><summary>Listen to the full call (caller L · bot R)</summary>
      <audio controls preload="none" src="call_{{ c.scenario_id }}/full_call.wav"></audio>
    </details>
  {% endif %}
  {% if c.error %}<p class="fail" style="margin:12px 0 0">Error: {{ c.error }}</p>{% endif %}
  {% if v %}
  <p class="summary">{{ v.summary }}</p>
  <div class="tablewrap" style="margin-top:12px">
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
  </div>
  {% endif %}
  {% if c.audio_verdict and not c.audio_verdict.get('error') %}
    <p class="audio-judge"><strong>Audio judge:</strong>
       tts_pron {{ '%.2f' % c.audio_verdict.tts_pronunciation }} ·
       audio {{ '%.2f' % c.audio_verdict.audio_quality }} ·
       naturalness {{ '%.2f' % c.audio_verdict.naturalness }}
       {% if c.audio_verdict.issues %}<br>Issues: {{ c.audio_verdict.issues|join(', ') }}{% endif %}
    </p>
  {% endif %}
  </article>
{% endfor %}
</section>

</div>
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
