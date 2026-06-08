"""Premium visual theme for the Streamlit operator dashboard.

Pure presentation: this module injects CSS only and changes **no** behaviour.
``inject_theme`` is idempotent-safe to call once per page render (the cost is a
single ``st.markdown`` of a static stylesheet). It gives the dashboard:

- an animated, slowly drifting gradient backdrop (subtle, premium),
- glass-card styling for metrics / expanders / tables,
- refined typography, buttons, inputs and sidebar,
- gentle entrance animations and hover transitions,
- responsive tweaks so the app stays usable on phones and large displays.

Selectors lean on Streamlit's stable ``data-testid`` hooks so functionality is
untouched; if a selector ever drifts the page still works, it just looks plainer.
"""

from __future__ import annotations

_THEME_CSS = """
<style>
:root{
  --brand:#7c5cff;--brand-2:#9b8cff;
  --text:#eef1f7;--muted:#a3acc2;--dim:#7b8499;
  --line:rgba(255,255,255,.08);--line-strong:rgba(255,255,255,.16);
  --card:rgba(255,255,255,.045);--card-hover:rgba(255,255,255,.07);
  --shadow:0 1px 0 rgba(255,255,255,.06) inset,0 2px 8px rgba(0,0,0,.45),0 18px 44px -20px rgba(0,0,0,.75);
  --glow:0 0 28px -8px rgba(124,92,255,.5);
  --ease:cubic-bezier(.22,.61,.36,1);
  --radius:16px;
}

/* Premium scrollbar */
*{scrollbar-width:thin;scrollbar-color:rgba(255,255,255,.18) transparent}
::-webkit-scrollbar{width:11px;height:11px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:rgba(255,255,255,.12);border-radius:999px;border:3px solid transparent;background-clip:content-box}
::-webkit-scrollbar-thumb:hover{background:rgba(255,255,255,.20);background-clip:content-box}

/* Animated near-black / OLED backdrop with a minimal indigo-violet glow */
.stApp{
  background:
    radial-gradient(60% 50% at 20% 0%,rgba(124,92,255,.10),transparent 60%),
    radial-gradient(50% 50% at 88% 8%,rgba(80,70,229,.08),transparent 60%),
    #080a0f;
  background-size:160% 160%;
  animation:bgShift 30s ease-in-out infinite;
}
@keyframes bgShift{
  0%{background-position:0% 50%}50%{background-position:100% 50%}100%{background-position:0% 50%}
}

/* Translucent top header so the backdrop shows through */
[data-testid="stHeader"]{background:transparent}

/* Typography */
html,body,[class*="css"]{
  font-family:"Inter",-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  -webkit-font-smoothing:antialiased;-moz-osx-font-smoothing:grayscale;text-rendering:optimizeLegibility;
}
h1,h2,h3{letter-spacing:-.02em;color:var(--text)}
h1{font-weight:750}

/* Main content gets a gentle entrance */
.block-container{animation:rise .6s var(--ease) both;padding-top:3.2rem}
@keyframes rise{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}

/* Metric tiles → frosted dark cards */
[data-testid="stMetric"]{
  background:var(--card);backdrop-filter:blur(10px);
  border:1px solid var(--line);border-radius:var(--radius);
  box-shadow:var(--shadow);padding:16px 18px;
  transition:transform .3s var(--ease),border-color .3s var(--ease),background .3s var(--ease),box-shadow .3s var(--ease);
}
[data-testid="stMetric"]:hover{transform:translateY(-4px);border-color:var(--line-strong);background:var(--card-hover);box-shadow:var(--shadow),var(--glow)}
[data-testid="stMetricLabel"]{color:var(--muted);font-weight:600;letter-spacing:.02em}
[data-testid="stMetricValue"]{color:var(--text);font-weight:750;letter-spacing:-.02em;font-variant-numeric:tabular-nums}

/* Expanders → frosted dark cards */
[data-testid="stExpander"]{
  background:var(--card);backdrop-filter:blur(10px);
  border:1px solid var(--line)!important;border-radius:var(--radius)!important;
  box-shadow:var(--shadow);overflow:hidden;transition:border-color .25s var(--ease),background .25s var(--ease),box-shadow .25s var(--ease);
}
[data-testid="stExpander"]:hover{border-color:var(--line-strong);background:var(--card-hover);box-shadow:var(--shadow),var(--glow)}
[data-testid="stExpander"] summary{font-weight:600;color:var(--text)}

/* Buttons */
.stButton>button,.stFormSubmitButton>button{
  border-radius:999px;border:1px solid transparent;font-weight:600;
  background:linear-gradient(135deg,#6d4dff,#9b7bff);color:#fff;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.25),0 8px 22px -10px rgba(124,92,255,.8);
  transition:transform .2s var(--ease),box-shadow .2s var(--ease),filter .2s var(--ease);
}
.stButton>button:hover,.stFormSubmitButton>button:hover{
  transform:translateY(-2px);filter:brightness(1.08);
  box-shadow:inset 0 1px 0 rgba(255,255,255,.3),0 14px 32px -12px rgba(124,92,255,.95),var(--glow);color:#fff;
}
.stButton>button:active,.stFormSubmitButton>button:active{transform:translateY(0)}

/* Inputs */
[data-baseweb="input"],[data-baseweb="select"]>div{
  border-radius:12px!important;background:#101319!important;border-color:var(--line)!important;
}
.stTextInput input{border-radius:12px;color:var(--text)}

/* Tables / dataframes */
[data-testid="stTable"],[data-testid="stDataFrame"]{
  background:var(--card);backdrop-filter:blur(8px);
  border:1px solid var(--line);border-radius:var(--radius);
  box-shadow:var(--shadow);overflow:hidden;
}
[data-testid="stTable"] td,[data-testid="stTable"] th{border-color:var(--line);color:var(--text)}
[data-testid="stTable"] th{color:var(--muted)}

/* Sidebar */
[data-testid="stSidebar"]{
  background:rgba(16,19,25,.72);backdrop-filter:blur(12px);
  border-right:1px solid var(--line);
}
[data-testid="stSidebar"] .stButton>button{
  background:linear-gradient(135deg,#6d4dff,#9b7bff);
}

/* Alerts a touch softer */
[data-testid="stAlert"]{border-radius:14px}

/* Charts sit on a card */
[data-testid="stVegaLiteChart"],[data-testid="stArrowVegaLiteChart"]{
  background:var(--card);border-radius:var(--radius);padding:8px;
  border:1px solid var(--line);box-shadow:var(--shadow);
}

/* Responsive */
@media (max-width:640px){
  .block-container{padding-left:1rem;padding-right:1rem;padding-top:2.4rem}
  [data-testid="stMetric"]{padding:12px 14px}
  [data-testid="stMetricValue"]{font-size:1.4rem}
}
@media (min-width:1600px){
  .block-container{max-width:1500px}
}
@media (prefers-reduced-motion:reduce){
  .stApp,.block-container,*{animation:none!important;transition:none!important}
}
</style>
"""


def inject_theme() -> None:
    """Inject the premium dashboard stylesheet. Call once near the top of a render."""
    import streamlit as st  # lazy: Streamlit-only dependency

    st.markdown(_THEME_CSS, unsafe_allow_html=True)
