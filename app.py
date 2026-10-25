"""PakarAC: antarmuka palet Lagoon. Jalankan python -m streamlit run app.py."""
import sqlite3
import streamlit as st
import konsultasi
import basis_pengetahuan
import riwayat
from penyimpanan import Penyimpanan

CSS = '''
<style>
:root {--lagoon:#506F71;--foam:#8FB8B3;--aqua:#CAE0DA;--mist:#EAF3EF;--ivory:#FBFCFA;--ink:#263F41;--muted:#617A7B;--line:#D6E4DE;}
html,body,[class*="css"] {font-family:Arial, sans-serif;}
.stApp {background:var(--mist);color:var(--ink);}
[data-testid="stAppViewContainer"] {background:var(--mist);}
[data-testid="stHeader"] {background:var(--mist);}
.block-container {padding-top:2.3rem;padding-bottom:2rem;max-width:1520px;}
h1,h2,h3,h4 {color:var(--ink)!important;letter-spacing:-.025em;}
h1 {font-size:2.15rem!important;margin-bottom:.1rem!important;}
h2 {font-size:1.35rem!important;} h3 {font-size:1.12rem!important;}
p,li,label {color:var(--ink);} [data-testid="stCaptionContainer"] p {color:var(--muted);font-size:.82rem;line-height:1.5;}
[data-testid="stSidebar"] {background:var(--ivory);border-right:1px solid var(--line);}
[data-testid="stSidebar"]>div:first-child {padding-top:2rem;}
.brand {display:flex;align-items:center;gap:12px;margin:0 0 30px 0;}
.brand-icon {background:var(--lagoon);color:white;border-radius:14px;width:46px;height:46px;display:grid;place-items:center;font-size:30px;}
.brand-title {font-size:27px;font-weight:800;letter-spacing:-1px;color:var(--ink);}
.brand-sub {font-size:12px;color:var(--muted);margin-top:2px;}
[data-testid="stSidebar"] [data-testid="stRadio"]>label {display:none;}
[data-testid="stSidebar"] [role="radiogroup"] {gap:10px;}
[data-testid="stSidebar"] [role="radiogroup"] label {padding:13px 15px;border-radius:11px;width:100%;margin:0;box-sizing:border-box;transition:background .15s;}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {background:var(--lagoon);box-shadow:0 5px 14px #506f7120;}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) p {color:white!important;font-weight:600;}
[data-testid="stSidebar"] [role="radiogroup"] label>div:first-child {display:none;}
[data-testid="stSidebar"] [role="radiogroup"] label p {font-size:.95rem;}
.sidebar-note {margin-top:28px;padding:16px;background:var(--mist);border-radius:12px;color:var(--muted);font-size:12px;line-height:1.65;}
.eyebrow {color:var(--lagoon);font-weight:700;font-size:11px;letter-spacing:1.8px;text-transform:uppercase;margin-bottom:8px;}
.page-sub {color:var(--muted);font-size:15px;margin:0 0 22px;}
.section-head {display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:10px;}
.pill {display:inline-block;background:var(--aqua);color:#36595A;font-size:12px;font-weight:600;border-radius:20px;padding:5px 11px;}
[data-testid="stVerticalBlockBorderWrapper"]>div {border-color:var(--line)!important;border-radius:15px!important;background:var(--ivory);}
[data-testid="stVerticalBlockBorderWrapper"] {box-shadow:0 3px 12px #36595a04;}
[data-testid="stExpander"] {border-color:var(--line)!important;background:var(--ivory);border-radius:10px!important;}
[data-testid="stExpander"] summary:hover {color:var(--lagoon)!important;}
[data-testid="stAlert"] {border-radius:12px;background:var(--aqua);color:var(--ink);}
[data-testid="stAlert"] p {color:var(--ink);}
.stButton>button,.stDownloadButton>button,.stLinkButton>a {border-radius:9px;border:1px solid var(--line);font-weight:600;min-height:42px;background:var(--ivory);color:var(--lagoon);}
.stButton>button:hover,.stDownloadButton>button:hover,.stLinkButton>a:hover {border-color:var(--lagoon);color:var(--lagoon);background:var(--mist);}
.stButton>button[kind="primary"],button[data-testid="stBaseButton-primary"],button[data-testid="stBaseButton-primaryFormSubmit"] {background:var(--lagoon)!important;border-color:var(--lagoon)!important;color:white!important;}
.stButton>button[kind="primary"] p {color:white!important;}
.stButton>button[kind="primary"]:hover {background:#405C5E!important;}
[data-testid="stTextInput"] input,[data-testid="stDateInput"] input,[data-testid="stNumberInput"] input {background:var(--ivory);color:var(--ink);}
[data-baseweb="input"],[data-baseweb="select"]>div {background:var(--ivory)!important;border-color:var(--line)!important;border-radius:9px!important;}
input {accent-color:var(--lagoon)!important;}
[data-baseweb="radio"]>div:first-child {background-color:var(--lagoon)!important;}
[data-baseweb="tag"] {background:var(--aqua)!important;color:var(--ink)!important;}
button[data-baseweb="tab"] {padding:12px 20px;color:var(--muted)!important;}
button[data-baseweb="tab"][aria-selected="true"] {color:var(--lagoon)!important;font-weight:700;}
[data-baseweb="tab-highlight"] {background:var(--lagoon)!important;}
[data-testid="stMetric"] {background:var(--ivory);border:1px solid var(--line);border-radius:14px;padding:18px 22px;}
[data-testid="stMetricValue"] {font-size:2rem;color:var(--ink);}
.result-summary {padding:20px;background:linear-gradient(120deg,var(--mist),var(--aqua));border:1px solid var(--line);border-radius:12px;margin:8px 0 18px;}
.result-summary h3 {margin:5px 0 12px;font-size:1.25rem!important;line-height:1.45;}
.cf-badge {display:inline-block;background:var(--lagoon);color:white;padding:7px 13px;border-radius:24px;font-size:13px;font-weight:700;}
.empty-result {text-align:center;padding:28px 12px;color:var(--muted);}
.empty-icon {font-size:42px;line-height:1.5;color:var(--foam);}
.step {display:flex;gap:10px;margin:12px 0;align-items:flex-start;line-height:1.65;font-size:14px;}
.step-no {background:var(--aqua);color:#36595A;border-radius:50%;min-width:25px;height:25px;display:grid;place-items:center;font-size:12px;font-weight:700;}
.footer {border-top:1px solid var(--line);margin-top:30px;padding-top:16px;text-align:right;font-size:11px;color:var(--muted);}
.small-label {font-size:12px;color:var(--muted);margin:0 0 4px;}
.rule-table {border:1px solid var(--line);border-radius:10px;overflow:auto;max-height:420px;margin-bottom:16px;}
.rule-table table {width:100%;border-collapse:collapse;font-size:13px;}
.rule-table th {background:var(--mist);padding:13px 12px;text-align:left;position:sticky;top:0;}
.rule-table td {padding:12px;border-top:1px solid var(--line);vertical-align:top;line-height:1.5;}
.rule-table tr:nth-child(even) td {background:#f4f8f5;}
.rule-table tr.selected td {background:var(--aqua);}
@media(max-width:800px) {.block-container{padding:1.2rem 1rem;}h1{font-size:1.8rem!important;}[data-testid="stHorizontalBlock"]{flex-wrap:wrap;}[data-testid="stHorizontalBlock"]>[data-testid="stColumn"]{min-width:min(100%,320px);}.rule-table{font-size:12px;}}
</style>
'''

def main():
    """Navigasi tiga halaman; tema dipusatkan agar mudah dikustomisasi."""
    st.set_page_config(page_title='PakarAC · Sistem Pakar AC',page_icon='❄️',layout='wide',initial_sidebar_state='expanded')
    st.markdown(CSS,unsafe_allow_html=True)
    with st.sidebar:
        st.markdown('<div class="brand"><div class="brand-icon">❄</div><div><div class="brand-title">PakarAC</div><div class="brand-sub">Sistem Pakar AC Split</div></div></div>',unsafe_allow_html=True)
        page=st.radio('Menu',['Konsultasi AC','Basis Pengetahuan','Riwayat'],key='navigation')
        st.markdown('<div class="sidebar-note"><b>Kenali gejalanya.<br>Temukan langkah awalnya.</b><br><br>Diagnosis berdasarkan aturan dan pengamatan kondisi AC Anda.</div>',unsafe_allow_html=True)
    try:
        repo=Penyimpanan()
        {'Konsultasi AC':konsultasi.render,'Basis Pengetahuan':basis_pengetahuan.render,'Riwayat':riwayat.render}[page](repo)
    except (ValueError,OSError,sqlite3.Error) as exc:
        st.error(f'Aplikasi tidak dapat menyelesaikan operasi: {exc}')
        st.info('Periksa file JSON, izin folder proyek, dan database. Jangan hapus riwayat untuk memperbaiki error.')
    st.markdown('<div class="footer">PakarAC · Prototipe pembelajaran · Forward chaining + Certainty Factor</div>',unsafe_allow_html=True)

if __name__=='__main__':
    main()
