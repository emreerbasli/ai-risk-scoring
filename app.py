"""
Collections Intelligence - Advanced Streamlit Dashboard
AI Risk Scoring — B2B Debtor Prioritization & Financial Risk Platform
IFRS 9 / Basel II Quantitative Credit Framework & What-If Simulator

Çalıştırma: streamlit run app.py
"""

import io
import os
from datetime import datetime
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Modüller
from data_generator import generate_mock_debtors
from scoring_engine import (
    score_portfolio,
    calculate_risk_score,
    get_action,
    get_action_en,
    get_action_color,
    get_trend_label,
    MODEL_PROFILES,
)
from llm_engine import get_single_explanation

# ──────────────────────────────────────────────────────────────
# DEMO MODU MOCK AÇIKLAMALARI (Zengin Finansal Bağlam)
# ──────────────────────────────────────────────────────────────
_MOCK_TR = {
    "🔴 Hemen Ara": [
        "Borçlu IFRS 9 {stage} aşamasında olup, %{pd} temerrüt olasılığı ve {sector} sektöründeki %{lgd} LGD oranı nedeniyle ${el} USD beklenen finansal zarar riski taşımaktadır; derhal acil tahsilat ve telefon araması önerilir.",
        "Son {contact} gündür temasa geçilmeyen ve {days} günlük gecikmesi bulunan borçlunun kredi notu ve olumsuz trendi doğrultusunda beklenen zarar ${el} USD'ye ulaşmıştır; derhal üst düzey tahsilat görüşmesi başlatılmalıdır.",
    ],
    "🟠 E-posta At": [
        "Borçlu IFRS 9 {stage} (SICR) kapsamında olup, %{pd} temerrüt ihtimali ve kötüleşen ödeme trendi doğrultusunda resmi bir yazılı ihtarname ve ödeme planı yapılandırması gönderilmesi tavsiye edilir.",
        "Yüksek risk skoru ve ${el} USD beklenen finansal kayıp karşısında, borçlunun geçmiş performansı gözetilerek şartların netleştirildiği resmi bir e-posta hatırlatması stratejik olarak uygundur.",
    ],
    "🟡 Takipte Tut": [
        "Borçlu IFRS 9 {stage} sınırında yer almakta olup, mevcut {days} günlük gecikme ve %{pd} temerrüt olasılığı henüz doğrudan icrai müdahale gerektirmemekte, periyodik risk izlemesi yeterli görülmektedir.",
        "Orta risk seviyesindeki borçlunun beklenen zararı (${el} USD) kontrol edilebilir düzeydedir; haftalık periyotlarla ödeme akışı takip edilmelidir.",
    ],
    "🟢 Bekle": [
        "Borçlu IFRS 9 {stage} (Sağlıklı) kategorisinde yer almaktadır; %{pd} gibi düşük temerrüt olasılığı ve güçlü ödeme geçmişi nedeniyle müdahaleye gerek yoktur.",
        "Finansal riski son derece düşük olan borçlu için bekleme stratejisi geçerlidir; rutin faturalama döngüsü izlenmektedir.",
    ],
}

_MOCK_EN = {
    "🔴 Hemen Ara": [
        "The debtor is in IFRS 9 {stage} with a {pd}% Probability of Default and {sector} sector LGD of {lgd}%, resulting in an Expected Loss of ${el} USD; immediate executive collection calls are required.",
        "With {days} days overdue, negative payment momentum, and ${el} USD at risk, immediate high-priority intervention is needed before default saturation occurs.",
    ],
    "🟠 E-posta At": [
        "Classified under IFRS 9 {stage} (SICR), the debtor exhibits an elevated default probability of {pd}%; structured formal email communication with revised payment milestones is advised.",
        "Given the deteriorating trend and ${el} USD expected exposure, a formal reminder letter should be dispatched to protect portfolio liquidity.",
    ],
    "🟡 Takipte Tut": [
        "Debtor remains within IFRS 9 {stage} boundaries; the {days}-day overdue duration and {pd}% default risk warrant systematic monitoring rather than aggressive escalation.",
        "Expected loss of ${el} USD is within manageable parameters; maintain close observation for any secondary rating migration.",
    ],
    "🟢 Bekle": [
        "Debtor is firmly in IFRS 9 {stage} (Performing); strong historical discipline and minimal default likelihood ({pd}%) require no operational intervention.",
        "Low-risk portfolio asset with sound payment history; continue standard billing schedule without active collection follow-up.",
    ],
}


def get_mock_explanation(debtor_row, lang_code: str = "tr") -> str:
    """Borçluya özgü dinamik mock açıklama oluştur"""
    pool = _MOCK_TR if lang_code == "tr" else _MOCK_EN
    action = debtor_row["action"]
    templates = pool.get(action, pool["🟢 Bekle"])
    template = templates[hash(str(debtor_row.get("debtor_id", "sim_1"))) % len(templates)]
    return template.format(
        stage=debtor_row.get("ifrs9_stage_label", "Stage 2"),
        pd=debtor_row.get("pd_pct", 50.0),
        lgd=debtor_row.get("lgd_pct", 40.0),
        el=f"{debtor_row.get('expected_loss', 0):,.0f}",
        days=debtor_row.get("days_overdue", "?"),
        amount=f"{debtor_row.get('outstanding_amount', 0):,.0f}",
        sector=debtor_row.get("sector", ""),
        contact=debtor_row.get("days_since_contact", "?"),
    )


# ──────────────────────────────────────────────────────────────
# SAYFA AYARLARI & CSS
# ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Risk Scoring | B2B Collections Intelligence",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
)

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
        background: rgba(15, 25, 50, 0.85);
        border: 1px solid rgba(99, 179, 237, 0.2);
        border-radius: 12px;
        padding: 16px;
        backdrop-filter: blur(10px);
    }

    [data-testid="stMetric"] label {
        color: #90cdf4 !important;
        font-size: 0.78rem !important;
        font-weight: 700 !important;
        text-transform: uppercase;
        letter-spacing: 1px;
    }

    [data-testid="stMetricValue"] {
        color: #e2e8f0 !important;
        font-size: 1.7rem !important;
        font-weight: 800 !important;
    }

    /* Header */
    .main-header {
        background: linear-gradient(135deg, rgba(10,20,45,0.95), rgba(15,30,60,0.95));
        border: 1px solid rgba(99, 179, 237, 0.25);
        border-radius: 16px;
        padding: 24px 32px;
        margin-bottom: 20px;
        backdrop-filter: blur(20px);
    }

    .main-header h1 {
        color: #e2e8f0;
        font-size: 1.9rem;
        font-weight: 800;
        margin: 0;
        letter-spacing: -0.5px;
    }

    .main-header p {
        color: #718096;
        font-size: 0.88rem;
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

    .debtor-card {
        background: rgba(15, 25, 50, 0.9);
        border: 1px solid rgba(99, 179, 237, 0.2);
        border-radius: 12px;
        padding: 18px;
        margin: 8px 0;
        backdrop-filter: blur(10px);
    }

    .explanation-box {
        background: linear-gradient(135deg, rgba(49, 130, 206, 0.12), rgba(43, 108, 176, 0.06));
        border-left: 3px solid #3182ce;
        border-radius: 0 8px 8px 0;
        padding: 16px 20px;
        margin: 10px 0;
        font-size: 0.92rem;
        color: #cbd5e0;
        line-height: 1.6;
    }

    .section-title {
        color: #90cdf4;
        font-size: 0.75rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        margin-bottom: 14px;
        padding-bottom: 6px;
        border-bottom: 1px solid rgba(99, 179, 237, 0.15);
    }

    /* Tabs stili */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        background: rgba(15, 25, 50, 0.6);
        border: 1px solid rgba(99, 179, 237, 0.2);
        border-radius: 8px 8px 0 0;
        padding: 10px 20px;
        color: #a0aec0;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #1a365d, #2b6cb0) !important;
        color: #ffffff !important;
        border-color: #63b3ed !important;
    }

    h1, h2, h3 { color: #e2e8f0 !important; }
    p, li { color: #a0aec0; }
    hr { border-color: rgba(99, 179, 237, 0.15) !important; }
</style>
""",
    unsafe_allow_html=True,
)


# ──────────────────────────────────────────────────────────────
# VERİ YÜKLEME
# ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_raw_debtors():
    """Ham portföy verisini yükle"""
    return generate_mock_debtors(50)


# ──────────────────────────────────────────────────────────────
# SIDEBAR: SENARYOLAR, FİLTRELER & AYARLAR
# ──────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        """
    <div style='text-align: center; padding: 16px 0;'>
        <div style='font-size: 2.3rem;'>🏦</div>
        <div style='color: #e2e8f0; font-weight: 800; font-size: 1.1rem; margin-top: 6px;'>
            AI Risk Scoring
        </div>
        <div style='color: #4a6fa5; font-size: 0.72rem; margin-top: 2px; letter-spacing: 1.2px;'>
            IFRS 9 & BASEL II ENGINE
        </div>
    </div>
    <hr>
    """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="section-title">🎛️ Risk Modeli Profili</div>', unsafe_allow_html=True)
    scenario_options = {
        "balanced": "⚖️ Standart / Dengeli Model",
        "stress": "🚨 Makroekonomik Kriz & Stres Testi",
        "liquidity": "💰 Nakit Akışı & Likidite Odaklı",
    }
    selected_scenario_key = st.selectbox(
        "Model Senaryosu",
        options=list(scenario_options.keys()),
        format_func=lambda k: scenario_options[k],
        help="Model ağırlıklarını ve stres testi parametrelerini dinamik olarak günceller.",
    )
    current_profile = MODEL_PROFILES[selected_scenario_key]
    st.caption(f"ℹ️ *{current_profile['description']}*")

    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown('<div class="section-title">🔍 Portföy Filtreleri</div>', unsafe_allow_html=True)

    stage_options = ["Tümü", "Stage 1 (Sağlıklı)", "Stage 2 (SICR)", "Stage 3 (Temerrüt)"]
    selected_stage = st.selectbox("IFRS 9 Kredi Aşaması", stage_options)

    action_options = ["Tümü", "🔴 Hemen Ara", "🟠 E-posta At", "🟡 Takipte Tut", "🟢 Bekle"]
    selected_action = st.selectbox("Aksiyon Tipi", action_options)

    score_range = st.slider("Risk Skoru Aralığı", 0, 100, (0, 100), step=5)
    min_amount = st.number_input("Min. Açık Tutar (USD)", min_value=0, value=0, step=5000)

    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown('<div class="section-title">⚙️ Sistem Ayarları</div>', unsafe_allow_html=True)

    lang = st.selectbox("LLM Açıklama Dili", ["Türkçe", "English"])
    lang_code = "tr" if lang == "Türkçe" else "en"

    if st.button("🔄 Portföyü Yeniden Üret"):
        st.cache_data.clear()
        st.rerun()

    weights = current_profile["weights"]
    st.markdown(
        f"""
    <div style='margin-top: 14px; padding: 12px; background: rgba(49,130,206,0.08);
         border-radius: 8px; border: 1px solid rgba(99,179,237,0.15);'>
        <div style='color: #4a6fa5; font-size: 0.68rem; font-weight: 700;
             text-transform: uppercase; letter-spacing: 1px; margin-bottom: 6px;'>
            Aktif Model Ağırlıkları
        </div>
        <div style='color: #718096; font-size: 0.72rem; line-height: 1.7;'>
            📅 Non-Linear Gecikme: <b style='color:#90cdf4'>%{weights['overdue']*100:.0f}</b><br>
            💰 Açık Tutar (Log): <b style='color:#90cdf4'>%{weights['amount']*100:.0f}</b><br>
            🏢 Sektör Riski (LGD): <b style='color:#90cdf4'>%{weights['sector']*100:.0f}</b><br>
            💳 Kredi Notu (PD): <b style='color:#90cdf4'>%{weights['credit']*100:.0f}</b><br>
            📊 Ödeme Geçmişi: <b style='color:#90cdf4'>%{weights['history']*100:.0f}</b><br>
            📞 İletişim Aralığı: <b style='color:#90cdf4'>%{weights['contact']*100:.0f}</b>
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
        <div style='color: #4a6fa5; font-size: 0.68rem; font-weight: 700;
             text-transform: uppercase; letter-spacing: 1px; margin-bottom: 6px;'>
            📖 Proje Hakkında
        </div>
        <div style='color: #718096; font-size: 0.72rem; line-height: 1.7;'>
            IFRS 9 Staging · Expected Loss (EL)<br>
            Llama 3.3 70B XAI · Cloudflare Edge<br>
            Python · Streamlit · Plotly
        </div>
        <div style='margin-top: 8px;'>
            <a href='https://github.com/emreerbasli/ai-risk-scoring' target='_blank'
               style='color: #63b3ed; font-size: 0.72rem; text-decoration: none;'>
                🔗 GitHub Repo ↗
            </a>
        </div>
    </div>
    """,
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────────────────────────
# HEADER & VERİ HAZIRLAMA
# ──────────────────────────────────────────────────────────────
st.markdown(
    """
<div class="main-header">
    <div class="zolvo-badge">IFRS 9 & Basel II Uyumlu · Collections Intelligence</div>
    <h1>🏦 AI Risk Scoring & Financial Loss Platform</h1>
    <p>Non-linear risk modelleme · Beklenen Finansal Zarar (EL = PD × LGD × EAD) · Llama 3.3 70B Açıklanabilir AI (XAI)</p>
</div>
""",
    unsafe_allow_html=True,
)

raw_df = load_raw_debtors()
df = score_portfolio(raw_df, profile_key=selected_scenario_key)

# Sekmeler
tab_portfolio, tab_simulator = st.tabs([
    "📊 Portföy Analitiği & Borçlu Listesi",
    "🧮 Canlı Borçlu Simülatörü (What-If Calculator)",
])


# ══════════════════════════════════════════════════════════════
# SEKME 1: PORTFÖY ANALİTİĞİ & BORÇLU LİSTESİ
# ══════════════════════════════════════════════════════════════
with tab_portfolio:
    filtered_df = df.copy()

    if selected_action != "Tümü":
        filtered_df = filtered_df[filtered_df["action"] == selected_action]

    if selected_stage == "Stage 1 (Sağlıklı)":
        filtered_df = filtered_df[filtered_df["ifrs9_stage"] == 1]
    elif selected_stage == "Stage 2 (SICR)":
        filtered_df = filtered_df[filtered_df["ifrs9_stage"] == 2]
    elif selected_stage == "Stage 3 (Temerrüt)":
        filtered_df = filtered_df[filtered_df["ifrs9_stage"] == 3]

    filtered_df = filtered_df[
        (filtered_df["risk_score"] >= score_range[0])
        & (filtered_df["risk_score"] <= score_range[1])
        & (filtered_df["outstanding_amount"] >= min_amount)
    ]

    # 1. KPI Metrikleri
    st.markdown('<div class="section-title">📊 Portföy Finansal Risk Özeti</div>', unsafe_allow_html=True)
    col1, col2, col3, col4, col5 = st.columns(5)

    total_debtors = len(df)
    total_outstanding = df["outstanding_amount"].sum()
    total_expected_loss = df["expected_loss"].sum()
    avg_pd = df["pd_pct"].mean()
    stage3_count = len(df[df["ifrs9_stage"] == 3])

    with col1:
        st.metric(
            "Toplam Portföy",
            f"${total_outstanding:,.0f}",
            delta=f"{total_debtors} Borçlu",
            help="Portföydeki toplam açık alacak tutarı.",
        )

    with col2:
        st.metric(
            "💰 Beklenen Zarar (EL)",
            f"${total_expected_loss:,.0f}",
            delta=f"%{total_expected_loss/total_outstanding*100:.1f} Portföy Riski",
            delta_color="inverse",
            help="Expected Loss = PD x LGD x EAD toplamı. Temerrüt durumunda kaybedilmesi beklenen tutar.",
        )

    with col3:
        st.metric(
            "🔴 Stage 3 (Temerrüt)",
            f"{stage3_count}",
            delta=f"%{stage3_count/total_debtors*100:.0f} Portföy",
            delta_color="inverse",
            help="IFRS 9 uyarınca 90+ gün gecikmeli veya kritik riskli temerrüt aşamasındaki borçlular.",
        )

    with col4:
        st.metric(
            "📉 Ort. Temerrüt Olasılığı",
            f"%{avg_pd:.1f}",
            delta="Portföy PD Benchmark",
            help="Tüm portföyün risk skorundan hesaplanan ortalama Probability of Default (PD) oranı.",
        )

    with col5:
        st.metric(
            "📅 Ort. Gecikme",
            f"{df['days_overdue'].mean():.0f} gün",
            delta=f"Maks: {df['days_overdue'].max():.0f} gün",
            delta_color="inverse",
        )

    st.markdown("<hr>", unsafe_allow_html=True)

    # 2. Kritik Uyarılar (Top 5 Risk)
    st.markdown('<div class="section-title">🚨 Kritik Uyarılar — En Yüksek Riskli 5 Borçlu</div>', unsafe_allow_html=True)
    top5 = df.nlargest(5, "risk_score")
    cols_top5 = st.columns(5)

    for col_t5, (_, row_t5) in zip(cols_top5, top5.iterrows()):
        border_c = row_t5["ifrs9_stage_color"]
        bg_c = "rgba(197,48,48,0.12)" if row_t5["ifrs9_stage"] == 3 else "rgba(192,86,33,0.12)"
        name_short = row_t5["debtor_name"][:16] + "…" if len(row_t5["debtor_name"]) > 16 else row_t5["debtor_name"]

        with col_t5:
            st.markdown(
                f"""
            <div style='background: {bg_c}; border: 1px solid {border_c};
                 border-top: 3px solid {border_c};
                 border-radius: 10px; padding: 12px; text-align: center;'>
                <div style='font-size: 0.68rem; color: #718096;
                     text-transform: uppercase; letter-spacing: 0.5px;
                     white-space: nowrap; overflow: hidden; text-overflow: ellipsis;'
                     title='{row_t5["debtor_name"]}'>
                    {name_short}
                </div>
                <div style='font-size: 1.55rem; font-weight: 900; color: {border_c}; margin: 2px 0;'>
                    {row_t5['risk_score']:.0f}
                </div>
                <div style='font-size: 0.62rem; color: #4a6fa5;'>EL: <b style='color:#fc8181'>${row_t5['expected_loss']/1000:.1f}K</b></div>
                <div style='font-size: 0.65rem; color: #a0aec0; margin-top: 4px;'>
                    {row_t5['days_overdue']}g · PD %{row_t5['pd_pct']:.0f}
                </div>
                <div style='font-size: 0.62rem; color: #718096;'>{row_t5['sector']}</div>
            </div>
            """,
                unsafe_allow_html=True,
            )

    st.markdown("<br>", unsafe_allow_html=True)

    # 3. Analitik Grafikler
    col_g1, col_g2 = st.columns([1, 1])

    with col_g1:
        st.markdown('<div class="section-title">🏢 Sektörel Açık Tutar & LGD Dağılımı</div>', unsafe_allow_html=True)
        if not filtered_df.empty:
            fig_sector = px.pie(
                filtered_df,
                names="sector",
                values="outstanding_amount",
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Pastel,
            )
            fig_sector.update_layout(
                margin=dict(t=10, b=10, l=10, r=10),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#e2e8f0"),
                height=260,
            )
            st.plotly_chart(fig_sector, use_container_width=True)
        else:
            st.info("Filtre kriterlerine uygun veri yok.")

    with col_g2:
        st.markdown('<div class="section-title">📊 Risk Skoru Dağılımı (Histogram)</div>', unsafe_allow_html=True)
        fig_hist = go.Figure()
        fig_hist.add_trace(
            go.Histogram(
                x=df["risk_score"],
                nbinsx=18,
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
            )
        )
        fig_hist.update_layout(
            margin=dict(t=10, b=20, l=10, r=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#a0aec0", size=10),
            xaxis=dict(title="Risk Skoru", showgrid=True, gridcolor="rgba(255,255,255,0.05)", color="#718096", range=[0, 100]),
            yaxis=dict(title="Borçlu", showgrid=True, gridcolor="rgba(255,255,255,0.05)", color="#718096"),
            bargap=0.06,
            height=260,
            showlegend=False,
        )
        st.plotly_chart(fig_hist, use_container_width=True)

    st.markdown("<hr>", unsafe_allow_html=True)

    # 4. Borçlu Tablosu
    st.markdown(f'<div class="section-title">📋 Portföy Tablosu ({len(filtered_df)} borçlu listeleniyor)</div>', unsafe_allow_html=True)
    display_cols = {
        "debtor_name": "Borçlu Adı",
        "sector": "Sektör",
        "ifrs9_stage_label": "IFRS 9 Aşaması",
        "risk_score": "Risk Skoru",
        "pd_pct": "PD (%)",
        "expected_loss": "Beklenen Zarar (EL $)",
        "outstanding_amount": "Açık Tutar ($)",
        "action": "Aksiyon",
        "days_overdue": "Gecikme (gün)",
        "credit_rating": "Kredi Notu",
        "trend_label": "Trend",
    }

    if not filtered_df.empty:
        display_df = filtered_df[list(display_cols.keys())].copy()
        display_df.columns = list(display_cols.values())
        display_df["Beklenen Zarar (EL $)"] = display_df["Beklenen Zarar (EL $)"].apply(lambda x: f"${x:,.0f}")
        display_df["Açık Tutar ($)"] = display_df["Açık Tutar ($)"].apply(lambda x: f"${x:,.0f}")
        display_df["PD (%)"] = display_df["PD (%)"].apply(lambda x: f"%{x:.1f}")
        display_df["Risk Skoru"] = display_df["Risk Skoru"].apply(lambda x: f"{x:.1f}/100")
        st.dataframe(display_df, width="stretch", height=380)

        # CSV Export
        csv_buffer = io.StringIO()
        export_df = filtered_df[
            [
                "debtor_id", "debtor_name", "sector", "credit_rating", "ifrs9_stage",
                "risk_score", "pd_pct", "lgd_pct", "expected_loss", "outstanding_amount",
                "days_overdue", "action", "trend_label"
            ]
        ].copy()
        export_df.to_csv(csv_buffer, index=False)

        col_exp1, _ = st.columns([1, 5])
        with col_exp1:
            st.download_button(
                label="📥 CSV Portföy Raporu İndir",
                data=csv_buffer.getvalue().encode("utf-8-sig"),
                file_name=f"collections_risk_report_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv",
            )
    else:
        st.info("Seçilen filtre kriterlerine uygun borçlu bulunamadı.")

    st.markdown("<hr>", unsafe_allow_html=True)

    # 5. Bireysel Borçlu Analizi & XAI
    st.markdown('<div class="section-title">🔬 Bireysel Borçlu Analizi & XAI Karar Açıklaması</div>', unsafe_allow_html=True)
    debtor_ids = filtered_df["debtor_id"].tolist()

    if debtor_ids:
        selected_debtor = st.selectbox(
            "Analiz Edilecek Borçluyu Seçin",
            options=debtor_ids,
            format_func=lambda did: filtered_df.loc[filtered_df["debtor_id"] == did, "debtor_name"].values[0],
        )
        debtor_row = filtered_df[filtered_df["debtor_id"] == selected_debtor].iloc[0]

        col_d1, col_d2 = st.columns([1.1, 1.2])

        with col_d1:
            risk = debtor_row["risk_score"]
            stage_color = debtor_row["ifrs9_stage_color"]
            bg_card = "rgba(197,48,48,0.1)" if risk >= 80 else ("rgba(192,86,33,0.1)" if risk >= 60 else "rgba(39,103,73,0.1)")

            st.markdown(
                f"""
            <div style='background: {bg_card}; border: 1px solid {stage_color};
                 border-radius: 12px; padding: 18px; margin-bottom: 14px;'>
                <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;'>
                    <span style='font-size: 1.15rem; font-weight: 800; color: #e2e8f0;'>
                        {debtor_row['debtor_name']}
                    </span>
                    <span style='background: rgba(0,0,0,0.3); border: 1px solid {stage_color}; color: {stage_color};
                                 font-size: 0.72rem; font-weight: 700; padding: 3px 10px; border-radius: 12px;'>
                        {debtor_row['ifrs9_stage_label']}
                    </span>
                </div>
                <div style='display: flex; align-items: center; gap: 20px;'>
                    <div>
                        <div style='color: #718096; font-size: 0.68rem; text-transform: uppercase;'>Risk Skoru</div>
                        <div style='font-size: 2.3rem; font-weight: 900; color: {stage_color};'>{risk:.0f}</div>
                        <div style='color: #718096; font-size: 0.68rem;'>/ 100</div>
                    </div>
                    <div style='flex: 1; border-left: 1px solid rgba(255,255,255,0.1); padding-left: 16px;'>
                        <div style='color: #718096; font-size: 0.68rem; text-transform: uppercase;'>Önerilen Aksiyon</div>
                        <div style='font-size: 1.05rem; font-weight: 800; color: #e2e8f0;'>{debtor_row['action']}</div>
                        <div style='color: #4a6fa5; font-size: 0.72rem; margin-top: 4px;'>{debtor_row['trend_label']}</div>
                    </div>
                </div>
            </div>
            """,
                unsafe_allow_html=True,
            )

            st.markdown(
                f"""
            <div class="debtor-card">
                <div style='display: grid; grid-template-columns: 1fr 1fr; gap: 12px;'>
                    <div>
                        <div style='color: #4a6fa5; font-size: 0.68rem; text-transform: uppercase;'>Beklenen Zarar (EL)</div>
                        <div style='color: #fc8181; font-weight: 800; font-size: 1.25rem;'>${debtor_row['expected_loss']:,.0f}</div>
                    </div>
                    <div>
                        <div style='color: #4a6fa5; font-size: 0.68rem; text-transform: uppercase;'>Açık Tutar (EAD)</div>
                        <div style='color: #e2e8f0; font-weight: 800; font-size: 1.25rem;'>${debtor_row['outstanding_amount']:,.0f}</div>
                    </div>
                    <div>
                        <div style='color: #4a6fa5; font-size: 0.68rem; text-transform: uppercase;'>Temerrüt Olasılığı (PD)</div>
                        <div style='color: #e2e8f0; font-weight: 700; font-size: 1.1rem;'>%{debtor_row['pd_pct']:.1f}</div>
                    </div>
                    <div>
                        <div style='color: #4a6fa5; font-size: 0.68rem; text-transform: uppercase;'>Temerrüt Kaybı (LGD)</div>
                        <div style='color: #e2e8f0; font-weight: 700; font-size: 1.1rem;'>%{debtor_row['lgd_pct']:.0f} ({debtor_row['sector']})</div>
                    </div>
                </div>
            </div>
            """,
                unsafe_allow_html=True,
            )

            delays = debtor_row.get("historical_delays", [])
            if delays:
                fig_spark = px.line(
                    y=delays,
                    title="📈 Geçmiş 6 Fatura Gecikme Seyri (Gün)",
                    markers=True,
                )
                fig_spark.update_layout(
                    margin=dict(t=30, b=10, l=0, r=0),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#a0aec0", size=10),
                    xaxis=dict(title=None, showgrid=False, zeroline=False, showticklabels=False),
                    yaxis=dict(title=None, showgrid=True, gridcolor="rgba(255,255,255,0.08)"),
                    height=130,
                )
                fig_spark.update_traces(line_color="#63b3ed", marker=dict(size=5, color="#90cdf4"))
                st.plotly_chart(fig_spark, use_container_width=True)

        with col_d2:
            categories = ["Gecikme Süresi", "Açık Tutar", "Sektör Riski", "Kredi Notu Riski", "Ödeme Geçmişi Riski", "İletişim Aralığı"]
            debtor_values = [
                debtor_row["norm_overdue"], debtor_row["norm_amount"], debtor_row["norm_sector"],
                debtor_row["norm_credit"], debtor_row["norm_history"], debtor_row["norm_contact"]
            ]
            benchmark_values = [
                df["norm_overdue"].mean(), df["norm_amount"].mean(), df["norm_sector"].mean(),
                df["norm_credit"].mean(), df["norm_history"].mean(), df["norm_contact"].mean()
            ]

            fig_radar = go.Figure()
            fig_radar.add_trace(go.Scatterpolar(
                r=benchmark_values + [benchmark_values[0]],
                theta=categories + [categories[0]],
                fill=None,
                name="Portföy Ortalaması",
                line=dict(color="#718096", dash="dash", width=1.5),
            ))
            fig_radar.add_trace(go.Scatterpolar(
                r=debtor_values + [debtor_values[0]],
                theta=categories + [categories[0]],
                fill="toself",
                name=debtor_row["debtor_name"],
                line=dict(color="#63b3ed", width=2),
                fillcolor="rgba(99, 179, 237, 0.25)",
            ))
            fig_radar.update_layout(
                polar=dict(
                    radialaxis=dict(visible=True, range=[0, 100], showticklabels=False, gridcolor="rgba(255,255,255,0.08)"),
                    angularaxis=dict(color="#a0aec0", gridcolor="rgba(255,255,255,0.08)"),
                    bgcolor="rgba(0,0,0,0)",
                ),
                margin=dict(t=25, b=20, l=40, r=40),
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#e2e8f0", size=10),
                height=260,
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
            )
            st.markdown("**🕸️ 6 Boyutlu Risk Radarı (Borçlu vs. Portföy Ortalaması)**")
            st.plotly_chart(fig_radar, use_container_width=True)

            st.markdown(
                f"""
            <div style='background: rgba(15,25,50,0.8); border: 1px solid rgba(99,179,237,0.15);
                 border-radius: 8px; padding: 10px 14px; margin-top: 4px; display: flex; justify-content: space-between;'>
                <span style='color: #718096; font-size: 0.78rem;'>
                    📈 Trend Bonusu: <b style='color:#90cdf4'>{debtor_row['score_trend']:+.0f} puan</b>
                </span>
                <span style='color: #718096; font-size: 0.78rem;'>
                    ⚠️ Bileşik Risk Cezası: <b style='color:#fc8181'>+{debtor_row['score_compound']:.0f} puan</b>
                </span>
            </div>
            """,
                unsafe_allow_html=True,
            )

        # XAI LLM
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("**🤖 AI Karar Açıklaması** *(Llama 3.3 70B · IFRS 9 & Expected Loss Destekli XAI)*")

        col_llm1, col_llm2, _ = st.columns([1.2, 1, 3])
        with col_llm1:
            generate_btn = st.button("✨ Açıklama Üret (Gerçek API)", key="gen_explanation")
        with col_llm2:
            demo_btn = st.button("🎭 Demo Açıklama", key="gen_demo", help="API anahtarı olmadan dinamik mock açıklama üretir")

        if generate_btn:
            with st.spinner(f"Llama 3.3 70B ile {debtor_row['debtor_name']} için finansal karar gerekçesi analiz ediliyor..."):
                try:
                    explanation = get_single_explanation(debtor_row, lang_code)
                    api_source = f"⚡ Groq · Llama 3.3 70B · {lang}"
                except Exception:
                    explanation = get_mock_explanation(debtor_row, lang_code)
                    api_source = "🎭 Demo Modu (Canlı API yedeklemesi)"

            st.markdown(
                f"""
            <div class="explanation-box">
                🤖 <strong>{debtor_row['debtor_name']}</strong> — <em>{debtor_row['ifrs9_stage_label']}</em><br><br>
                {explanation}
                <br><br>
                <span style='color: #4a6fa5; font-size: 0.72rem;'>
                    {api_source} · Bu açıklama karar destek niteliğindedir; nihai onay tahsilat yöneticisine aittir.
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
                🤖 <strong>{debtor_row['debtor_name']}</strong> — <em>{debtor_row['ifrs9_stage_label']}</em><br><br>
                {explanation}
                <br><br>
                <span style='color: #4a6fa5; font-size: 0.72rem;'>
                    🎭 Demo Modu · Örnek XAI Çıktısı (API anahtarı gerektirmez). Nihai onay tahsilat yöneticisine aittir.
                </span>
            </div>
            """,
                unsafe_allow_html=True,
            )


# ══════════════════════════════════════════════════════════════
# SEKME 2: CANLI BORÇLU SİMÜLATÖRÜ (WHAT-IF CALCULATOR)
# ══════════════════════════════════════════════════════════════
with tab_simulator:
    st.markdown('<div class="section-title">🧮 Canlı Borçlu Risk & Finansal Zarar Simülatörü</div>', unsafe_allow_html=True)
    st.caption("Farklı finansal parametreler girerek risk skorunun, IFRS 9 aşamasının, beklenen zararın ve AI önerisinin anlık değişimini simüle edin.")

    col_sim_in1, col_sim_in2, col_sim_in3 = st.columns(3)

    with col_sim_in1:
        sim_name = st.text_input("Borçlu Firma Adı", value="Örnek Teknoloji A.Ş.")
        sim_sector = st.selectbox("Faaliyet Sektörü", ["İnşaat", "Perakende", "Lojistik", "Üretim", "Teknoloji", "Sağlık"], index=4)
        sim_credit = st.selectbox("Kredi Notu", ["A", "B", "C", "D"], index=1)

    with col_sim_in2:
        sim_amount = st.number_input("Açık Fatura Tutarı (USD)", min_value=1000, max_value=2000000, value=85000, step=5000)
        sim_overdue = st.slider("Vadesi Geçen Gün Sayısı", 0, 150, 42)
        sim_history = st.slider("Geçmiş Ödeme Performans Puanı (0-100)", 0, 100, 68)

    with col_sim_in3:
        sim_contact = st.slider("Son İletişimden Geçen Gün", 0, 90, 14)
        sim_trend_label = st.selectbox("Son 6 Fatura Trendi", [
            "📈 Hızlı İyileşiyor (+2)", "↗️ İyileşiyor (+1)", "➡️ Stabil (0)", "↘️ Kötüleşiyor (-1)", "📉 Hızlı Kötüleşiyor (-2)"
        ], index=2)
        trend_map_sim = {
            "📈 Hızlı İyileşiyor (+2)": 2, "↗️ İyileşiyor (+1)": 1, "➡️ Stabil (0)": 0,
            "↘️ Kötüleşiyor (-1)": -1, "📉 Hızlı Kötüleşiyor (-2)": -2
        }
        sim_trend = trend_map_sim[sim_trend_label]

    # Simülasyon Hesabı
    sim_row = pd.Series({
        "debtor_id": "sim_custom_1",
        "debtor_name": sim_name,
        "sector": sim_sector,
        "credit_rating": sim_credit,
        "outstanding_amount": sim_amount,
        "days_overdue": sim_overdue,
        "payment_history_score": sim_history,
        "days_since_contact": sim_contact,
        "trend": sim_trend,
    })

    sim_res = calculate_risk_score(sim_row, profile_key=selected_scenario_key)
    sim_score = sim_res["risk_score"]
    sim_ifrs9 = sim_res["ifrs9"]
    sim_el = sim_res["el_data"]
    sim_action = get_action(sim_score)
    sim_action_en = get_action_en(sim_score)
    sim_trend_str = get_trend_label(sim_trend)

    sim_row_scored = pd.Series({
        **sim_row.to_dict(),
        "risk_score": sim_score,
        "action": sim_action,
        "action_en": sim_action_en,
        "ifrs9_stage": sim_ifrs9["stage"],
        "ifrs9_stage_label": sim_ifrs9["stage_label"],
        "pd_pct": sim_el["pd_pct"],
        "lgd_pct": sim_el["lgd_pct"],
        "expected_loss": sim_el["expected_loss"],
        "trend_label": sim_trend_str,
    })

    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown(f'<div class="section-title">📊 Simülasyon Sonuçları: {sim_name}</div>', unsafe_allow_html=True)

    col_sr1, col_sr2, col_sr3, col_sr4, col_sr5 = st.columns(5)
    with col_sr1:
        st.metric("Hesaplanan Risk Skoru", f"{sim_score:.0f}/100", delta=sim_action)
    with col_sr2:
        st.metric("IFRS 9 Aşaması", sim_ifrs9["stage_label"].split("(")[0].strip(), delta=sim_ifrs9["stage_label"].split("(")[1].replace(")", "").strip())
    with col_sr3:
        st.metric("Temerrüt İhtimali (PD)", f"%{sim_el['pd_pct']:.1f}")
    with col_sr4:
        st.metric("Temerrüt Kaybı (LGD)", f"%{sim_el['lgd_pct']:.0f} ({sim_sector})")
    with col_sr5:
        st.metric("💰 Beklenen Zarar (EL)", f"${sim_el['expected_loss']:,.0f}", delta_color="inverse")

    # Radar & Simülasyon Açıklaması
    col_srad1, col_srad2 = st.columns([1.1, 1])

    with col_srad1:
        st.markdown("**🕸️ Simüle Edilen Borçlunun Risk Profili**")
        sim_breakdown = sim_res["score_breakdown"]
        sim_radar_vals = [
            sim_breakdown["overdue_norm"], sim_breakdown["amount_norm"], sim_breakdown["sector_risk"],
            sim_breakdown["credit_risk"], sim_breakdown["history_risk"], sim_breakdown["contact_norm"]
        ]
        sim_benchmark = [
            df["norm_overdue"].mean(), df["norm_amount"].mean(), df["norm_sector"].mean(),
            df["norm_credit"].mean(), df["norm_history"].mean(), df["norm_contact"].mean()
        ]

        fig_sim_radar = go.Figure()
        fig_sim_radar.add_trace(go.Scatterpolar(
            r=sim_benchmark + [sim_benchmark[0]],
            theta=["Gecikme Süresi", "Açık Tutar", "Sektör Riski", "Kredi Notu", "Ödeme Geçmişi", "İletişim"] + ["Gecikme Süresi"],
            fill=None,
            name="Portföy Benchmark",
            line=dict(color="#718096", dash="dash", width=1.5),
        ))
        fig_sim_radar.add_trace(go.Scatterpolar(
            r=sim_radar_vals + [sim_radar_vals[0]],
            theta=["Gecikme Süresi", "Açık Tutar", "Sektör Riski", "Kredi Notu", "Ödeme Geçmişi", "İletişim"] + ["Gecikme Süresi"],
            fill="toself",
            name=sim_name,
            line=dict(color="#68d391" if sim_score < 50 else "#fc8181", width=2),
            fillcolor="rgba(104, 211, 145, 0.2)" if sim_score < 50 else "rgba(252, 129, 129, 0.2)",
        ))
        fig_sim_radar.update_layout(
            polar=dict(
                radialaxis=dict(visible=True, range=[0, 100], showticklabels=False, gridcolor="rgba(255,255,255,0.08)"),
                angularaxis=dict(color="#a0aec0", gridcolor="rgba(255,255,255,0.08)"),
                bgcolor="rgba(0,0,0,0)",
            ),
            margin=dict(t=25, b=20, l=40, r=40),
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#e2e8f0", size=10),
            height=260,
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
        )
        st.plotly_chart(fig_sim_radar, use_container_width=True)

    with col_srad2:
        st.markdown("**🤖 Simülasyon AI Karar Açıklaması**")
        sim_demo_exp = get_mock_explanation(sim_row_scored, lang_code)
        st.markdown(
            f"""
        <div class="explanation-box" style='margin-top: 10px;'>
            🤖 <strong>{sim_name}</strong> — <em>{sim_ifrs9['stage_label']}</em><br><br>
            {sim_demo_exp}
            <br><br>
            <span style='color: #4a6fa5; font-size: 0.72rem;'>
                ⚡ Stratejik AI Karar Analizi · Simülasyon Modu · Aktif Model: {current_profile['name']}
            </span>
        </div>
        """,
            unsafe_allow_html=True,
        )


st.markdown("<hr>", unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────
# FOOTER
# ──────────────────────────────────────────────────────────────
st.markdown(
    """
<div style='text-align: center; padding: 18px; color: #4a6fa5; font-size: 0.75rem;'>
    <b style='color: #718096;'>AI Risk Scoring Platform</b> · IFRS 9 & Basel II Quantitative Credit Framework<br>
    Python · Streamlit · Groq API (Llama 3.3 70B) · Non-Linear Risk Modeling · Expected Loss Engine
</div>
""",
    unsafe_allow_html=True,
)
