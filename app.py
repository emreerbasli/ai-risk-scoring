"""
Collections Intelligence - Streamlit Dashboard
AI Risk Scoring — B2B Debtor Prioritization Platform

Çalıştırma: streamlit run app.py
Demo modu: Cloudflare Worker çalışmıyorsa mock LLM açıklamaları döner.
"""

# Demo modu için mock açıklamalar
_MOCK_TR = {
    "🔴 Hemen Ara": [
        "{days} günlük gecikme ve {amount} USD açık tutarıyla kritik risk eşiğini aşmış olan bu borçlu için, {sector} sektörünün yüksek volatilitesi göz önünde bulundurulduğunda derhal telefon görüşmesi başlatılması önerilir.",
        "Ödeme geçmişi skoru düşük olan ve son {contact} gündür hiç iletişim kurulmamış bu borçlu için kritik risk seviyesi nedeniyle acil tahsilat görüşmesi kritik önem taşımaktadır.",
    ],
    "🟠 E-posta At": [
        "Borçlunun {days} günlük gecikmesi ve kötüleşen ödeme trendi, yazılı iletişim yoluyla ödeme planı talep edilmesini gerektirmektedir; {sector} sektörü riski bu kararı desteklemektedir.",
        "Yüksek risk skoruna rağmen ödeme geçmişi orta düzeyde olan bu borçlu için, resmi bir e-posta ile ödeme hatırlatması ve şartların netleştirilmesi tavsiye edilir.",
    ],
    "🟡 Takipte Tut": [
        "Borçlunun ödeme geçmişi nispeten olumlu olup mevcut {days} günlük gecikme henüz kritik seviyeye ulaşmamıştır; sistematik takip yeterli olacaktır.",
        "Orta risk seviyesindeki bu borçlu için periyodik izleme yeterlidir; herhangi bir olumsuz trend tespitinde aksiyon kademesi yükseltilmelidir.",
    ],
    "🟢 Bekle": [
        "Bu borçlunun güçlü ödeme geçmişi ve düşük gecikme süresi göz önünde bulundurulduğunda, müdahale gerektiren bir risk faktörü bulunmamaktadır.",
        "Düşük risk profiline sahip olan bu borçlu için bekleme stratejisi uygundur; mevcut ödeme davranışı devam ettiği sürece aksiyon alınmasına gerek yoktur.",
    ],
}

_MOCK_EN = {
    "🔴 Hemen Ara": [
        "With {days} days overdue and an outstanding balance of {amount} USD, this debtor has exceeded the critical risk threshold; immediate phone contact is strongly recommended given the high volatility in the {sector} sector.",
        "This debtor's low payment history score combined with {contact} days of no contact places them firmly in the critical action category requiring immediate collection outreach.",
    ],
    "🟠 E-posta At": [
        "The debtor's {days}-day overdue status and deteriorating payment trend warrant a formal written communication requesting a payment plan, particularly given the {sector} sector risk premium.",
        "Despite an elevated risk score, the debtor's moderate payment history suggests a structured email reminder with clear payment terms would be the appropriate next step.",
    ],
    "🟡 Takipte Tut": [
        "The debtor's relatively positive payment history and manageable {days}-day overdue period do not yet warrant escalation; systematic monitoring is the appropriate response.",
        "At this moderate risk level, periodic monitoring is sufficient; the action tier should be elevated if any negative trend is detected.",
    ],
    "🟢 Bekle": [
        "This debtor's strong payment history and minimal overdue period present no actionable risk factors at this time.",
        "The low-risk profile of this debtor makes a wait strategy appropriate; no intervention is needed as long as current payment behavior continues.",
    ],
}


def get_mock_explanation(debtor_row, lang_code: str = "tr") -> str:
    """API çağrısı yapmadan borçluya özgü mock açıklama döndür."""
    pool = _MOCK_TR if lang_code == "tr" else _MOCK_EN
    action = debtor_row["action"]
    templates = pool.get(action, pool["🟢 Bekle"])
    template = templates[hash(str(debtor_row["debtor_id"])) % len(templates)]
    return template.format(
        days=debtor_row.get("days_overdue", "?"),
        amount=f"{debtor_row.get('outstanding_amount', 0):,.0f}",
        sector=debtor_row.get("sector", ""),
        contact=debtor_row.get("days_since_contact", "?"),
    )


import streamlit as st
import io
import os
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go

# Modüller
from data_generator import generate_mock_debtors
from scoring_engine import score_portfolio
from llm_engine import get_single_explanation

# ──────────────────────────────────────────────────────────────
# SAYFA AYARLARI
# ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Zolvo Collection AI | Zolvo PoC",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────────────────────
# CSS STİLLERİ
# ──────────────────────────────────────────────────────────────
st.markdown(
    """
<style>
    /* Ana arka plan */
    .stApp {
        background: linear-gradient(135deg, #0a0e1a 0%, #0d1526 50%, #0a1020 100%);
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0d1829 0%, #0a1420 100%);
        border-right: 1px solid rgba(99, 179, 237, 0.15);
    }

    /* Metrik kartları */
    [data-testid="stMetric"] {
        background: rgba(15, 25, 50, 0.8);
        border: 1px solid rgba(99, 179, 237, 0.2);
        border-radius: 12px;
        padding: 16px;
        backdrop-filter: blur(10px);
    }

    [data-testid="stMetric"] label {
        color: #90cdf4 !important;
        font-size: 0.8rem !important;
        font-weight: 600 !important;
        text-transform: uppercase;
        letter-spacing: 1px;
    }

    [data-testid="stMetricValue"] {
        color: #e2e8f0 !important;
        font-size: 1.8rem !important;
        font-weight: 700 !important;
    }

    /* Header */
    .main-header {
        background: linear-gradient(135deg, rgba(10,20,45,0.95), rgba(15,30,60,0.95));
        border: 1px solid rgba(99, 179, 237, 0.25);
        border-radius: 16px;
        padding: 28px 36px;
        margin-bottom: 24px;
        backdrop-filter: blur(20px);
    }

    .main-header h1 {
        color: #e2e8f0;
        font-size: 2rem;
        font-weight: 800;
        margin: 0;
        letter-spacing: -0.5px;
    }

    .main-header p {
        color: #718096;
        font-size: 0.9rem;
        margin: 6px 0 0 0;
    }

    .zolvo-badge {
        display: inline-block;
        background: linear-gradient(135deg, #3182ce, #2b6cb0);
        color: white;
        font-size: 0.7rem;
        font-weight: 700;
        padding: 3px 10px;
        border-radius: 20px;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        margin-bottom: 8px;
    }

    /* Risk renk etiketleri */
    .risk-critical {
        background: linear-gradient(135deg, #c53030, #9b2c2c);
        color: white;
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: 700;
        font-size: 0.78rem;
        display: inline-block;
    }
    .risk-high {
        background: linear-gradient(135deg, #c05621, #9c4221);
        color: white;
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: 700;
        font-size: 0.78rem;
        display: inline-block;
    }
    .risk-medium {
        background: linear-gradient(135deg, #b7791f, #975a16);
        color: white;
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: 700;
        font-size: 0.78rem;
        display: inline-block;
    }
    .risk-low {
        background: linear-gradient(135deg, #276749, #22543d);
        color: white;
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: 700;
        font-size: 0.78rem;
        display: inline-block;
    }

    /* Borçlu detay kartı */
    .debtor-card {
        background: rgba(15, 25, 50, 0.9);
        border: 1px solid rgba(99, 179, 237, 0.2);
        border-radius: 12px;
        padding: 20px;
        margin: 8px 0;
        backdrop-filter: blur(10px);
    }

    /* Açıklama kutusu */
    .explanation-box {
        background: linear-gradient(135deg, rgba(49, 130, 206, 0.1), rgba(43, 108, 176, 0.05));
        border-left: 3px solid #3182ce;
        border-radius: 0 8px 8px 0;
        padding: 14px 18px;
        margin: 10px 0;
        font-size: 0.92rem;
        color: #cbd5e0;
        line-height: 1.6;
    }

    /* Bilgi kutusu */
    .info-box {
        background: rgba(49, 130, 206, 0.08);
        border: 1px solid rgba(99, 179, 237, 0.2);
        border-radius: 10px;
        padding: 14px 18px;
        margin: 8px 0;
        font-size: 0.85rem;
        color: #90cdf4;
    }

    /* Dataframe stili */
    .stDataFrame {
        border-radius: 12px;
        overflow: hidden;
    }

    /* Butonlar */
    .stButton > button {
        background: linear-gradient(135deg, #3182ce, #2b6cb0);
        color: white;
        border: none;
        border-radius: 8px;
        font-weight: 600;
        padding: 8px 20px;
        transition: all 0.2s;
    }

    .stButton > button:hover {
        background: linear-gradient(135deg, #4299e1, #3182ce);
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(49, 130, 206, 0.4);
    }

    /* Skor çubuk */
    .score-bar-container {
        background: rgba(255,255,255,0.05);
        border-radius: 10px;
        height: 8px;
        width: 100%;
        margin: 4px 0;
    }

    /* Section başlıkları */
    .section-title {
        color: #90cdf4;
        font-size: 0.75rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        margin-bottom: 16px;
        padding-bottom: 8px;
        border-bottom: 1px solid rgba(99, 179, 237, 0.15);
    }

    /* Genel metin renkleri */
    h1, h2, h3 { color: #e2e8f0 !important; }
    p, li { color: #a0aec0; }

    /* Selectbox */
    .stSelectbox label { color: #90cdf4 !important; }

    /* Multiselect */
    .stMultiSelect label { color: #90cdf4 !important; }

    /* Slider */
    .stSlider label { color: #90cdf4 !important; }

    /* Toggle */
    .stToggle label { color: #90cdf4 !important; }

    /* Progress */
    .stProgress > div > div {
        border-radius: 10px;
    }

    /* Divider */
    hr { border-color: rgba(99, 179, 237, 0.15) !important; }
</style>
""",
    unsafe_allow_html=True,
)


# ──────────────────────────────────────────────────────────────
# VERİ YÜKLEME (Cache ile)
# ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_portfolio():
    """Portföyü yükle ve skorla"""
    df = generate_mock_debtors(50)
    scored = score_portfolio(df)
    return scored


# ──────────────────────────────────────────────────────────────
# SIDEBAR
# ──────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        """
    <div style='text-align: center; padding: 20px 0;'>
        <div style='font-size: 2.5rem;'>🏦</div>
        <div style='color: #e2e8f0; font-weight: 800; font-size: 1.1rem; margin-top: 8px;'>
            Zolvo Collection AI
        </div>
        <div style='color: #4a6fa5; font-size: 0.75rem; margin-top: 4px; letter-spacing: 1px;'>
            ZOLVO POC
        </div>
    </div>
    <hr>
    """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="section-title">🔍 Filtreler</div>', unsafe_allow_html=True)

    # Aksiyon filtresi
    action_options = [
        "Tümü",
        "🔴 Hemen Ara",
        "🟠 E-posta At",
        "🟡 Takipte Tut",
        "🟢 Bekle",
    ]
    selected_action = st.selectbox("Aksiyon Tipi", action_options)

    # Risk skor aralığı
    score_range = st.slider("Risk Skoru Aralığı", 0, 100, (0, 100), step=5)

    # Min. açık tutar
    min_amount = st.number_input(
        "Min. Açık Tutar (USD)", min_value=0, value=0, step=1000
    )

    # Max. gecikme günü
    max_overdue = st.slider("Maks. Gecikme Günü", 0, 120, 120, step=5)

    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown('<div class="section-title">⚙️ Ayarlar</div>', unsafe_allow_html=True)

    # Dil seçimi
    lang = st.selectbox("LLM Açıklama Dili", ["Türkçe", "English"])
    lang_code = "tr" if lang == "Türkçe" else "en"

    st.markdown("<hr>", unsafe_allow_html=True)

    if st.button("🔄 Portföyü Yenile"):
        st.cache_data.clear()
        st.rerun()

    st.markdown(
        """
    <div style='margin-top: 20px; padding: 12px; background: rgba(49,130,206,0.08);
         border-radius: 8px; border: 1px solid rgba(99,179,237,0.15);'>
        <div style='color: #4a6fa5; font-size: 0.7rem; font-weight: 700;
             text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px;'>
            Risk Formülü
        </div>
        <div style='color: #718096; font-size: 0.75rem; line-height: 1.8;'>
            📅 Gecikme Günü: <b style='color:#90cdf4'>%30</b><br>
            💰 Açık Tutar: <b style='color:#90cdf4'>%20</b><br>
            📊 Ödeme Geçmişi: <b style='color:#90cdf4'>%15</b><br>
            🏢 Sektör Riski: <b style='color:#90cdf4'>%15</b><br>
            💳 Kredi Notu: <b style='color:#90cdf4'>%10</b><br>
            📞 Son İletişim: <b style='color:#90cdf4'>%10</b><br>
            📈 Trend: <b style='color:#90cdf4'>±bonus</b>
        </div>
    </div>
    """,
        unsafe_allow_html=True,
    )

    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown(
        """
    <div style='padding: 12px; background: rgba(26,54,93,0.35);
         border-radius: 8px; border: 1px solid rgba(99,179,237,0.12);'>
        <div style='color: #4a6fa5; font-size: 0.7rem; font-weight: 700;
             text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px;'>
            📖 Bu Proje Hakkında
        </div>
        <div style='color: #718096; font-size: 0.73rem; line-height: 1.8;'>
            Kural tabanlı risk skoru + Llama 3.3 70B açıklaması
            ile B2B tahsilat zekası PoC'u.<br><br>
            <b style='color:#63b3ed'>Stack:</b> Python · Streamlit · Groq<br>
            <b style='color:#63b3ed'>Güvenlik:</b> Cloudflare Workers<br>
            <b style='color:#63b3ed'>Model:</b> Llama 3.3 70B
        </div>
        <div style='margin-top: 10px;'>
            <a href='https://github.com/emreerbasli/ai-risk-scoring'
               target='_blank'
               style='color: #63b3ed; font-size: 0.73rem; text-decoration: none;'>
                🔗 GitHub Repo ↗
            </a>
        </div>
    </div>
    """,
        unsafe_allow_html=True,
    )



# ──────────────────────────────────────────────────────────────
# ANA İÇERİK
# ──────────────────────────────────────────────────────────────

# Header
st.markdown(
    """
<div class="main-header">
    <div class="zolvo-badge">Zolvo PoC · Haziran 2026</div>
    <h1>🏦 Zolvo Collection AI Dashboard</h1>
    <p>AI destekli borçlu önceliklendirme sistemi · Açıklanabilir kural tabanlı skorlama + Groq LLM açıklama motoru</p>
</div>
""",
    unsafe_allow_html=True,
)

# Veri yükle
df = load_portfolio()

# Filtre uygula
filtered_df = df.copy()

if selected_action != "Tümü":
    filtered_df = filtered_df[filtered_df["action"] == selected_action]

filtered_df = filtered_df[
    (filtered_df["risk_score"] >= score_range[0])
    & (filtered_df["risk_score"] <= score_range[1])
    & (filtered_df["outstanding_amount"] >= min_amount)
    & (filtered_df["days_overdue"] <= max_overdue)
]


# ──────────────────────────────────────────────────────────────
# PORTFÖY ÖZETİ - METRİKLER
# ──────────────────────────────────────────────────────────────
st.markdown('<div class="section-title">📊 Portföy Özeti</div>', unsafe_allow_html=True)

col1, col2, col3, col4, col5 = st.columns(5)

total_debtors = len(df)
critical_count = len(df[df["risk_score"] >= 80])
high_risk_count = len(df[(df["risk_score"] >= 60) & (df["risk_score"] < 80)])
total_outstanding = df["outstanding_amount"].sum()
avg_overdue = df["days_overdue"].mean()

with col1:
    st.metric(
        "Toplam Borçlu", f"{total_debtors}", help="Portföydeki toplam borçlu sayısı"
    )

with col2:
    st.metric(
        "🔴 Kritik (Hemen Ara)",
        f"{critical_count}",
        delta=f"%{critical_count/total_debtors*100:.0f} portföy",
        delta_color="inverse",
    )

with col3:
    st.metric(
        "🟠 Yüksek Risk",
        f"{high_risk_count}",
        delta=f"%{high_risk_count/total_debtors*100:.0f} portföy",
        delta_color="inverse",
    )

with col4:
    st.metric(
        "💰 Toplam Açık Tutar",
        f"${total_outstanding:,.0f}",
        help="Tüm portföydeki toplam açık fatura tutarı",
    )

with col5:
    st.metric(
        "📅 Ort. Gecikme",
        f"{avg_overdue:.0f} gün",
        delta=f"Maks: {df['days_overdue'].max()} gün",
        delta_color="inverse",
    )

st.markdown("<hr>", unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────
# AKSİYON DAĞILIMI
# ──────────────────────────────────────────────────────────────
st.markdown(
    '<div class="section-title">⚡ Bugünün Aksiyonları</div>', unsafe_allow_html=True
)

action_counts = df["action"].value_counts()
col_a1, col_a2, col_a3, col_a4 = st.columns(4)

action_data = [
    ("🔴 Hemen Ara", "red", "#fc8181"),
    ("🟠 E-posta At", "orange", "#f6ad55"),
    ("🟡 Takipte Tut", "yellow", "#f6e05e"),
    ("🟢 Bekle", "green", "#68d391"),
]

for col, (action, color, hex_color) in zip(
    [col_a1, col_a2, col_a3, col_a4], action_data
):
    count = action_counts.get(action, 0)
    pct = count / total_debtors * 100
    with col:
        st.markdown(
            f"""
        <div style='background: rgba(15,25,50,0.9); border: 1px solid rgba(99,179,237,0.15);
             border-radius: 12px; padding: 16px; text-align: center;
             border-top: 3px solid {hex_color};'>
            <div style='font-size: 1.8rem; font-weight: 800; color: {hex_color};'>{count}</div>
            <div style='color: #718096; font-size: 0.8rem; margin-top: 4px;'>{action}</div>
            <div style='color: #4a6fa5; font-size: 0.72rem; margin-top: 4px;'>%{pct:.0f} portföy</div>
        </div>
        """,
            unsafe_allow_html=True,
        )

st.markdown("<br>", unsafe_allow_html=True)
st.markdown('<div class="section-title">🏢 Portföy Sektörel Dağılımı</div>', unsafe_allow_html=True)

fig_sector = px.pie(
    filtered_df, 
    names="sector", 
    values="outstanding_amount", 
    hole=0.4,
    color_discrete_sequence=px.colors.qualitative.Pastel
)
fig_sector.update_layout(
    margin=dict(t=20, b=20, l=20, r=20),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#e2e8f0"),
    showlegend=True,
    height=300
)
st.plotly_chart(fig_sector, use_container_width=True)

st.markdown("<br>", unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────
# 🚨 KRİTİK UYARILAR — En Yüksek Riskli 5 Borçlu
# ──────────────────────────────────────────────────────────────
st.markdown(
    '<div class="section-title">🚨 Kritik Uyarılar — En Yüksek Riskli 5 Borçlu</div>',
    unsafe_allow_html=True,
)

top5 = df.nlargest(5, "risk_score")
cols_top5 = st.columns(5)

for col_t5, (_, row_t5) in zip(cols_top5, top5.iterrows()):
    risk_t5 = row_t5["risk_score"]
    if risk_t5 >= 80:
        border_c = "#fc8181"
        bg_c = "rgba(197,48,48,0.12)"
    elif risk_t5 >= 60:
        border_c = "#f6ad55"
        bg_c = "rgba(192,86,33,0.12)"
    else:
        border_c = "#f6e05e"
        bg_c = "rgba(183,121,31,0.12)"

    name_t5 = row_t5["debtor_name"]
    name_short = name_t5[:16] + "…" if len(name_t5) > 16 else name_t5

    with col_t5:
        st.markdown(
            f"""
        <div style='background: {bg_c}; border: 1px solid {border_c};
             border-top: 3px solid {border_c};
             border-radius: 10px; padding: 12px; text-align: center;'>
            <div style='font-size: 0.7rem; color: #718096;
                 text-transform: uppercase; letter-spacing: 0.5px;
                 margin-bottom: 4px; white-space: nowrap;
                 overflow: hidden; text-overflow: ellipsis;'
                 title='{name_t5}'>
                {name_short}
            </div>
            <div style='font-size: 1.6rem; font-weight: 900; color: {border_c};'>
                {risk_t5:.0f}
            </div>
            <div style='font-size: 0.62rem; color: #4a6fa5;'>/ 100</div>
            <div style='font-size: 0.67rem; color: #a0aec0; margin-top: 4px;'>
                {row_t5['days_overdue']}g · ${row_t5['outstanding_amount']/1000:.0f}K
            </div>
            <div style='font-size: 0.62rem; color: #718096; margin-top: 2px;'>
                {row_t5['sector']}
            </div>
        </div>
        """,
            unsafe_allow_html=True,
        )

st.markdown("<br>", unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────
# RİSK SKORU DAĞILIM HİSTOGRAMI
# ──────────────────────────────────────────────────────────────
st.markdown(
    '<div class="section-title">📊 Risk Skoru Dağılımı</div>',
    unsafe_allow_html=True,
)

fig_hist = go.Figure()
fig_hist.add_trace(go.Histogram(
    x=df["risk_score"],
    nbinsx=20,
    marker=dict(
        color=df["risk_score"],
        colorscale=[
            [0.0, "#276749"],
            [0.4, "#b7791f"],
            [0.6, "#c05621"],
            [1.0, "#c53030"],
        ],
        line=dict(color="rgba(255,255,255,0.05)", width=1),
    ),
    hovertemplate="Skor: %{x}<br>Borçlu Sayısı: %{y}<extra></extra>",
))
fig_hist.update_layout(
    margin=dict(t=10, b=30, l=0, r=0),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#a0aec0"),
    xaxis=dict(
        title="Risk Skoru",
        showgrid=True,
        gridcolor="rgba(255,255,255,0.05)",
        color="#718096",
        range=[0, 100],
    ),
    yaxis=dict(
        title="Borçlu Sayısı",
        showgrid=True,
        gridcolor="rgba(255,255,255,0.05)",
        color="#718096",
    ),
    bargap=0.05,
    height=220,
    showlegend=False,
)

col_hist1, col_hist2 = st.columns([2, 1])
with col_hist1:
    st.plotly_chart(fig_hist, use_container_width=True)
with col_hist2:
    st.markdown(
        f"""
    <div style='padding: 16px; background: rgba(15,25,50,0.8);
         border: 1px solid rgba(99,179,237,0.15); border-radius: 10px;
         margin-top: 8px;'>
        <div style='color: #4a6fa5; font-size: 0.7rem; font-weight: 700;
             text-transform: uppercase; letter-spacing: 1px; margin-bottom: 12px;'>
            İstatistikler
        </div>
        <div style='display: grid; grid-template-columns: 1fr 1fr; gap: 10px;'>
            <div>
                <div style='color: #718096; font-size: 0.68rem;'>Ortalama</div>
                <div style='color: #e2e8f0; font-weight: 700;'>{df['risk_score'].mean():.1f}</div>
            </div>
            <div>
                <div style='color: #718096; font-size: 0.68rem;'>Medyan</div>
                <div style='color: #e2e8f0; font-weight: 700;'>{df['risk_score'].median():.1f}</div>
            </div>
            <div>
                <div style='color: #718096; font-size: 0.68rem;'>Maks.</div>
                <div style='color: #fc8181; font-weight: 700;'>{df['risk_score'].max():.1f}</div>
            </div>
            <div>
                <div style='color: #718096; font-size: 0.68rem;'>Min.</div>
                <div style='color: #68d391; font-weight: 700;'>{df['risk_score'].min():.1f}</div>
            </div>
        </div>
    </div>
    """,
        unsafe_allow_html=True,
    )

st.markdown("<hr>", unsafe_allow_html=True)




# ──────────────────────────────────────────────────────────────
# BORÇLU TABLOSU
# ──────────────────────────────────────────────────────────────
st.markdown(
    f'<div class="section-title">📋 Borçlu Tablosu ({len(filtered_df)} sonuç)</div>',
    unsafe_allow_html=True,
)

# Görüntülenecek kolonlar
display_cols = {
    "debtor_name": "Borçlu Adı",
    "sector": "Sektör",
    "credit_rating": "Kredi Notu",
    "risk_score": "Risk Skoru",
    "action": "Aksiyon",
    "days_overdue": "Gecikme (gün)",
    "outstanding_amount": "Açık Tutar ($)",
    "payment_history_score": "Ödeme Geçmişi",
    "days_since_contact": "Son İletişim (gün)",
    "trend_label": "Trend",
    "last_contact_date": "Son İletişim Tarihi",
}

display_df = filtered_df[list(display_cols.keys())].copy()
display_df.columns = list(display_cols.values())
display_df["Açık Tutar ($)"] = display_df["Açık Tutar ($)"].apply(
    lambda x: f"${x:,.0f}"
)
display_df["Ödeme Geçmişi"] = display_df["Ödeme Geçmişi"].apply(
    lambda x: f"{x:.0f}/100"
)
display_df["Risk Skoru"] = display_df["Risk Skoru"].apply(lambda x: f"{x:.1f}/100")

st.dataframe(
    display_df,
    width="stretch",
    height=420,
)

# CSV Export
csv_buffer = io.StringIO()
export_df = filtered_df[
    [
        "debtor_id",
        "debtor_name",
        "risk_score",
        "action",
        "action_en",
        "days_overdue",
        "outstanding_amount",
        "payment_history_score",
        "days_since_contact",
        "trend_label",
        "last_contact_date",
    ]
].copy()
export_df.to_csv(csv_buffer, index=False)

col_exp1, col_exp2 = st.columns([1, 5])
with col_exp1:
    st.download_button(
        label="📥 CSV İndir",
        data=csv_buffer.getvalue().encode("utf-8-sig"),
        file_name=f"collections_report_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv",
    )

st.markdown("<hr>", unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────
# DETAYLI BORÇLU ANALİZİ
# ──────────────────────────────────────────────────────────────
st.markdown(
    '<div class="section-title">🔬 Detaylı Borçlu Analizi</div>', unsafe_allow_html=True
)

# Borçlu seç — debtor_id ile seçim (isim örtüşmesi bug'unu önler)
debtor_options = filtered_df["debtor_name"].tolist()
debtor_ids = filtered_df["debtor_id"].tolist()
if debtor_options:
    selected_debtor = st.selectbox(
        "Borçlu Seç",
        options=debtor_ids,
        format_func=lambda did: filtered_df.loc[
            filtered_df["debtor_id"] == did, "debtor_name"
        ].values[0],
    )
    debtor_row = filtered_df[filtered_df["debtor_id"] == selected_debtor].iloc[0]

    col_d1, col_d2 = st.columns([1.2, 1])

    with col_d1:
        # Risk skoru görsel
        risk = debtor_row["risk_score"]

        if risk >= 80:
            risk_class = "risk-critical"
            risk_bg = "rgba(197,48,48,0.1)"
            risk_border = "#c53030"
        elif risk >= 60:
            risk_class = "risk-high"
            risk_bg = "rgba(192,86,33,0.1)"
            risk_border = "#c05621"
        elif risk >= 40:
            risk_class = "risk-medium"
            risk_bg = "rgba(183,121,31,0.1)"
            risk_border = "#b7791f"
        else:
            risk_class = "risk-low"
            risk_bg = "rgba(39,103,73,0.1)"
            risk_border = "#276749"

        st.markdown(
            f"""
        <div style='background: {risk_bg}; border: 1px solid {risk_border};
             border-radius: 12px; padding: 20px; margin-bottom: 16px;'>
            <div style='font-size: 1.1rem; font-weight: 700; color: #e2e8f0; margin-bottom: 12px;'>
                {debtor_row['debtor_name']}
            </div>
            <div style='display: flex; align-items: center; gap: 16px;'>
                <div>
                    <div style='color: #718096; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 1px;'>Risk Skoru</div>
                    <div style='font-size: 2.5rem; font-weight: 900; color: {risk_border};'>{risk:.0f}</div>
                    <div style='color: #718096; font-size: 0.72rem;'>/100</div>
                </div>
                <div style='flex: 1;'>
                    <div style='color: #718096; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 6px;'>Önerilen Aksiyon</div>
                    <div class='{risk_class}'>{debtor_row['action']}</div>
                    <div style='color: #4a6fa5; font-size: 0.72rem; margin-top: 6px;'>{debtor_row['trend_label']}</div>
                </div>
            </div>
        </div>
        """,
            unsafe_allow_html=True,
        )

        # Detay grid
        st.markdown(
            f"""
        <div class="debtor-card">
            <div style='display: grid; grid-template-columns: 1fr 1fr; gap: 12px;'>
                <div>
                    <div style='color: #4a6fa5; font-size: 0.7rem; text-transform: uppercase; letter-spacing: 1px;'>Gecikme Günü</div>
                    <div style='color: #e2e8f0; font-weight: 700; font-size: 1.2rem;'>{debtor_row['days_overdue']} gün</div>
                </div>
                <div>
                    <div style='color: #4a6fa5; font-size: 0.7rem; text-transform: uppercase; letter-spacing: 1px;'>Açık Tutar</div>
                    <div style='color: #e2e8f0; font-weight: 700; font-size: 1.2rem;'>${debtor_row['outstanding_amount']:,.0f}</div>
                </div>
                <div>
                    <div style='color: #4a6fa5; font-size: 0.7rem; text-transform: uppercase; letter-spacing: 1px;'>Ödeme Geçmişi</div>
                    <div style='color: #e2e8f0; font-weight: 700; font-size: 1.2rem;'>{debtor_row['payment_history_score']:.0f}/100</div>
                </div>
                <div>
                    <div style='color: #4a6fa5; font-size: 0.7rem; text-transform: uppercase; letter-spacing: 1px;'>Son İletişim</div>
                    <div style='color: #e2e8f0; font-weight: 700; font-size: 1.2rem;'>{debtor_row['days_since_contact']} gün önce</div>
                </div>
            </div>
        </div>
        """,
            unsafe_allow_html=True,
        )

    with col_d2:
        st.markdown("**📊 Skor Bileşenleri (Açıklanabilirlik)**")

        components = [
            ("📅 Gecikme Günü (%30)", debtor_row["score_overdue"], 30),
            ("💰 Açık Tutar (%20)", debtor_row["score_amount"], 20),
            ("📊 Ödeme Geçmişi (%15)", debtor_row["score_history"], 15),
            ("🏢 Sektör Riski (%15)", debtor_row["score_sector"], 15),
            ("💳 Kredi Notu (%10)", debtor_row["score_credit"], 10),
            ("📞 Son İletişim (%10)", debtor_row["score_contact"], 10),
        ]

        for label, value, max_val in components:
            pct = min(value / max_val, 1.0) if max_val > 0 else 0
            st.markdown(
                f"""
            <div style='margin-bottom: 12px;'>
                <div style='display: flex; justify-content: space-between; margin-bottom: 4px;'>
                    <span style='color: #a0aec0; font-size: 0.8rem;'>{label}</span>
                    <span style='color: #e2e8f0; font-weight: 700; font-size: 0.85rem;'>{value:.1f}</span>
                </div>
                <div style='background: rgba(255,255,255,0.05); border-radius: 10px; height: 6px;'>
                    <div style='background: linear-gradient(90deg, #3182ce, #63b3ed);
                         width: {pct*100:.0f}%; height: 100%; border-radius: 10px;'></div>
                </div>
            </div>
            """,
                unsafe_allow_html=True,
            )
        # Sparkline (Historical Delays)
        delays = debtor_row.get("historical_delays", [])
        if delays:
            st.markdown("<br>", unsafe_allow_html=True)
            fig_spark = px.line(
                y=delays, 
                title="Geçmiş 6 Fatura Gecikme Trendi (Gün)",
                markers=True
            )
            fig_spark.update_layout(
                margin=dict(t=30, b=10, l=0, r=0),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#a0aec0", size=11),
                xaxis=dict(title=None, showgrid=False, zeroline=False, showticklabels=False),
                yaxis=dict(title=None, showgrid=True, gridcolor="rgba(255,255,255,0.1)"),
                height=150
            )
            fig_spark.update_traces(line_color="#63b3ed", marker=dict(size=6, color="#90cdf4"))
            st.plotly_chart(fig_spark, use_container_width=True)

        # Trend kutusunu her zaman göster (0 ise stabil)
        trend_color = (
            "#fc8181"
            if debtor_row["score_trend"] > 0
            else ("#68d391" if debtor_row["score_trend"] < 0 else "#90cdf4")
        )
        trend_sign = "+" if debtor_row["score_trend"] > 0 else ""
        st.markdown(
            f"""
        <div style='background: rgba(15,25,50,0.8); border: 1px solid rgba(99,179,237,0.15);
             border-radius: 8px; padding: 10px 14px; margin-top: 8px;'>
            <span style='color: #718096; font-size: 0.8rem;'>📈 Trend Bonusu: </span>
            <span style='color: {trend_color}; font-weight: 700;'>
                {trend_sign}{debtor_row['score_trend']:.0f} puan
            </span>
            <span style='color: #4a6fa5; font-size: 0.75rem;'> · {debtor_row['trend_label']}</span>
        </div>
        """,
            unsafe_allow_html=True,
        )

    # LLM Açıklama
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        "**🤖 AI Karar Açıklaması** *(Groq · Llama 3.3 70B · Karar vermez, açıklar)*"
    )

    col_llm1, col_llm2, col_llm3 = st.columns([1.2, 1, 3])
    with col_llm1:
        generate_btn = st.button("✨ Açıklama Üret (Gerçek API)", key="gen_explanation")
    with col_llm2:
        demo_btn = st.button("🎭 Demo Açıklama", key="gen_demo",
                             help="API key gerektirmez — örnek açıklama gösterir")

    if generate_btn:
        with st.spinner(
            f"Llama 3.3 70B ile {debtor_row['debtor_name']} için açıklama üretiliyor..."
        ):
            try:
                explanation = get_single_explanation(debtor_row, lang_code)
                api_source = f"⚡ Groq · Llama 3.3 70B · {lang}"
            except Exception:
                explanation = get_mock_explanation(debtor_row, lang_code)
                api_source = "🎭 Demo Modu (API erişilemiyor — örnek açıklama)"

        st.markdown(
            f"""
        <div class="explanation-box">
            🤖 <strong>{debtor_row['debtor_name']}</strong><br><br>
            {explanation}
            <br><br>
            <span style='color: #4a6fa5; font-size: 0.72rem;'>
                {api_source} · Bu açıklama karar değildir — nihai onay insan yöneticiye aittir.
            </span>
        </div>
        """,
            unsafe_allow_html=True,
        )

    if demo_btn:
        explanation = get_mock_explanation(debtor_row, lang_code)
        st.markdown(
            f"""
        <div class="explanation-box">
            🤖 <strong>{debtor_row['debtor_name']}</strong><br><br>
            {explanation}
            <br><br>
            <span style='color: #4a6fa5; font-size: 0.72rem;'>
                🎭 Demo Modu · Gerçek Groq API çağrısı yapılmamıştır.
                Bu açıklama karar değildir — nihai onay insan yöneticiye aittir.
            </span>
        </div>
        """,
            unsafe_allow_html=True,
        )


else:
    st.info("Filtrelerle eşleşen borçlu bulunamadı. Filtreleri genişletin.")


st.markdown("<hr>", unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────
# FOOTER
# ──────────────────────────────────────────────────────────────
st.markdown(
    """
<div style='text-align: center; padding: 20px; color: #4a6fa5; font-size: 0.78rem;'>
    <b style='color: #718096;'>Zolvo Collection AI PoC</b> ·
    Zolvo Case Study · Oktavis × Tessera Lab · Haziran 2026<br>
    Python · Streamlit · Groq API (Llama 3.3 70B) · Açıklanabilir Kural Tabanlı Skorlama
</div>
""",
    unsafe_allow_html=True,
)
