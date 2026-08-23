"""
Collections Intelligence - Advanced Risk Scoring & Financial Loss Engine
IFRS 9 / Basel II Staging, Non-Linear Sigmoidal Scoring, and Expected Loss (EL = PD x LGD x EAD)

Zolvo Case Study / AI Risk Scoring
"""

import math
import numpy as np
import pandas as pd


# ──────────────────────────────────────────────────────────────
# MODEL AĞIRLIK PROFİLLERİ (Senaryolar / Stres Testi)
# ──────────────────────────────────────────────────────────────
MODEL_PROFILES = {
    "balanced": {
        "name": "Standart / Dengeli Model",
        "description": "Basel II uyumlu dengeli risk modeli.",
        "weights": {
            "overdue": 0.30,
            "amount": 0.20,
            "history": 0.15,
            "contact": 0.10,
            "sector": 0.15,
            "credit": 0.10,
        },
    },
    "stress": {
        "name": "🚨 Makroekonomik Kriz & Stres Testi",
        "description": "Sektörel volatilite ve kredi notu hassasiyetini artıran temkinli model.",
        "weights": {
            "overdue": 0.20,
            "amount": 0.15,
            "history": 0.10,
            "contact": 0.10,
            "sector": 0.25,
            "credit": 0.20,
        },
    },
    "liquidity": {
        "name": "💰 Nakit Akışı & Likidite Odaklı",
        "description": "Açık tutar ve gecikme süresine en yüksek ağırlığı veren tahsilat modeli.",
        "weights": {
            "overdue": 0.35,
            "amount": 0.35,
            "history": 0.10,
            "contact": 0.10,
            "sector": 0.05,
            "credit": 0.05,
        },
    },
}

# Sektör Bazlı Kayıp Oranı (Loss Given Default - LGD)
SECTOR_LGD_MAP = {
    "İnşaat": 0.65,    # Yüksek temerrüt kaybı
    "Perakende": 0.55,
    "Lojistik": 0.45,
    "Üretim": 0.35,
    "Teknoloji": 0.25,
    "Sağlık": 0.15,    # Düşük temerrüt kaybı / yüksek tahsil edilebilirlik
}

SECTOR_RISK_MAP = {
    "İnşaat": 100,
    "Perakende": 80,
    "Lojistik": 60,
    "Üretim": 40,
    "Teknoloji": 20,
    "Sağlık": 10,
}

CREDIT_RATING_RISK_MAP = {
    "A": 10,
    "B": 35,
    "C": 70,
    "D": 100,
}


# ──────────────────────────────────────────────────────────────
# NORMALİZASYON & NON-LINEAR EĞRİLER
# ──────────────────────────────────────────────────────────────
def normalize_overdue_nonlinear(days: float) -> float:
    """
    Doğrusal olmayan (Sigmoidal / Kademeli) gecikme eğrisi.
    - 0-30 gün (Stage 1): Yavaş risk artışı (0-25 puan)
    - 31-89 gün (Stage 2 SICR): Dik risk artışı (25-85 puan)
    - 90+ gün (Stage 3 Default): Temerrüt doygunluğu (85-100 puan)
    """
    if days <= 0:
        return 0.0
    elif days <= 30:
        # 0 - 25 arası yumuşak kavis
        return (days / 30.0) ** 1.3 * 25.0
    elif days <= 90:
        # 25 - 85 arası dikleşen eğri
        ratio = (days - 30.0) / 60.0
        return 25.0 + (ratio ** 0.85) * 60.0
    else:
        # 90+ gün: 85 - 100 arası temerrüt doygunluğu
        over = min(days - 90.0, 30.0) / 30.0
        return 85.0 + over * 15.0


def normalize_amount(amount: float, max_amount: float = 500000) -> float:
    """Açık tutarı logaritmik kavisle 0-100 arasına normalize et"""
    if amount <= 0:
        return 0.0
    # Log ölçeklendirme ile yüksek tutarların etkisini yumuşatırken küçükleri de ayırt et
    log_amt = math.log10(max(amount, 1000))
    log_min = math.log10(1000)
    log_max = math.log10(max_amount)
    score = (log_amt - log_min) / (log_max - log_min) * 100
    return max(0.0, min(100.0, score))


def normalize_payment_history(score: float) -> float:
    """Ödeme geçmişini ters orantılı risk skoruna çevir (100 iyi -> 0 risk)"""
    return max(0.0, min(100.0, 100.0 - score))


def normalize_contact_gap(days: float, max_days: float = 60) -> float:
    """Son iletişimden geçen günü normalize et"""
    return min(max(days / max_days, 0.0), 1.0) * 100.0


def calculate_trend_bonus(trend: int) -> float:
    """
    Trend katkısı:
    -2: Hızlı kötüleşme → +15 puan
    -1: Kötüleşme       → +7 puan
     0: Stabil          →  0 puan
     1: İyileşme        → -5 puan
     2: Hızlı iyileşme  → -10 puan
    """
    bonus_map = {-2: 15.0, -1: 7.0, 0: 0.0, 1: -5.0, 2: -10.0}
    return bonus_map.get(trend, 0.0)


def calculate_compound_penalty(row: pd.Series) -> float:
    """
    Bileşik Risk Çarpanı (Interaction Penalty):
    Aynı anda çoklu kritik risk sinyali varsa (Sektör yüksek + Kredi D/C + Trend Kötüleşen)
    doğrusal toplamın ötesinde risk cezası ekler.
    """
    penalty = 0.0
    high_sector = row.get("sector") in ["İnşaat", "Perakende"]
    bad_credit = row.get("credit_rating") in ["C", "D"]
    bad_trend = row.get("trend", 0) <= -1
    high_overdue = row.get("days_overdue", 0) >= 60

    critical_signals = sum([high_sector, bad_credit, bad_trend, high_overdue])
    if critical_signals >= 3:
        penalty += 8.0
    elif critical_signals == 2:
        penalty += 3.0

    return penalty


# ──────────────────────────────────────────────────────────────
# IFRS 9 STAGING & EXPECTED LOSS (EL = PD x LGD x EAD)
# ──────────────────────────────────────────────────────────────
def calculate_ifrs9_stage(days_overdue: float, risk_score: float, trend: int, credit_rating: str) -> dict:
    """
    IFRS 9 / Basel II Kredi Riski Aşamalandırması:
    - Stage 1 (Performing / Sağlıklı): 0-30 gün gecikme, düşük PD
    - Stage 2 (SICR - Significant Increase in Credit Risk): 31-89 gün veya belirgin bozulma
    - Stage 3 (Credit-Impaired / Temerrüt): 90+ gün veya kritik risk skoru (>=80)
    """
    if days_overdue >= 90 or risk_score >= 80:
        stage = 3
        stage_label = "🔴 Stage 3 (Temerrüt / Default)"
        stage_desc = "Kredi değer düşüklüğü gerçekleşti, acil tahsilat & hukuki takip."
        color = "#fc8181"
    elif days_overdue >= 31 or trend <= -1 or credit_rating == "D" or risk_score >= 55:
        stage = 2
        stage_label = "🟠 Stage 2 (SICR - Önemli Risk Artışı)"
        stage_desc = "Kredi riskinde belirgin artış (SICR), yakın izleme ve e-posta/yapılandırma."
        color = "#f6ad55"
    else:
        stage = 1
        stage_label = "🟢 Stage 1 (Sağlıklı / Performing)"
        stage_desc = "Düşük kredi riski, olağan ticari döngü."
        color = "#68d391"

    return {
        "stage": stage,
        "stage_label": stage_label,
        "stage_desc": stage_desc,
        "stage_color": color,
    }


def calculate_pd(risk_score: float) -> float:
    """
    Risk Skorundan Kalibre Edilmiş Temerrüt Olasılığı (PD - Probability of Default).
    Sigmoid eğrisi ile 0-100 skoru %1 ile %98 arasına eşler.
    """
    # Lojistik dönüşüm: Orta nokta 50 puan, eğim katsayısı 0.075
    z = 0.075 * (risk_score - 50.0)
    pd_val = 1.0 / (1.0 + math.exp(-z))
    # 0.01 ile 0.98 arasına sınırla
    return round(float(np.clip(pd_val, 0.01, 0.98)), 4)


def calculate_expected_loss(row: pd.Series, risk_score: float) -> dict:
    """
    Expected Loss (EL) = PD x LGD x EAD
    - PD: Probability of Default (Temerrüt Olasılığı %)
    - LGD: Loss Given Default (Sektöre özgü Temerrüt Halinde Kayıp Oranı %)
    - EAD: Exposure at Default (Açık Tutar $)
    """
    pd_rate = calculate_pd(risk_score)
    sector = row.get("sector", "Üretim")
    lgd_rate = SECTOR_LGD_MAP.get(sector, 0.40)
    ead_amount = float(row.get("outstanding_amount", 0.0))

    expected_loss = pd_rate * lgd_rate * ead_amount

    return {
        "pd_rate": pd_rate,
        "pd_pct": round(pd_rate * 100, 1),
        "lgd_rate": lgd_rate,
        "lgd_pct": round(lgd_rate * 100, 1),
        "ead_amount": ead_amount,
        "expected_loss": round(expected_loss, 2),
    }


# ──────────────────────────────────────────────────────────────
# KOMPOZİT RİSK SKORLAMA MOTORU
# ──────────────────────────────────────────────────────────────
def calculate_risk_score(row: pd.Series, profile_key: str = "balanced") -> dict:
    """
    Her borçlu için açıklanabilir, non-linear, IFRS 9 uyumlu risk skoru hesapla.
    """
    profile = MODEL_PROFILES.get(profile_key, MODEL_PROFILES["balanced"])
    weights = profile["weights"]

    # Normalize edilmiş 6 faktör
    overdue_norm = normalize_overdue_nonlinear(row["days_overdue"])
    amount_norm = normalize_amount(row["outstanding_amount"])
    history_risk = normalize_payment_history(row["payment_history_score"])
    contact_norm = normalize_contact_gap(row["days_since_contact"])
    sector_risk = SECTOR_RISK_MAP.get(row["sector"], 50.0)
    credit_risk = CREDIT_RATING_RISK_MAP.get(row["credit_rating"], 50.0)
    
    trend_bonus = calculate_trend_bonus(row.get("trend", 0))
    compound_penalty = calculate_compound_penalty(row)

    # Ağırlıklı baz skor
    base_score = (
        overdue_norm * weights["overdue"]
        + amount_norm * weights["amount"]
        + history_risk * weights["history"]
        + contact_norm * weights["contact"]
        + sector_risk * weights["sector"]
        + credit_risk * weights["credit"]
    )

    # Trend bonusu ve bileşik ceza ile nihai skor (0-100 arası sınırla)
    final_score = max(0.0, min(100.0, base_score + trend_bonus + compound_penalty))

    breakdown = {
        "overdue_norm": round(overdue_norm, 1),
        "amount_norm": round(amount_norm, 1),
        "history_risk": round(history_risk, 1),
        "contact_norm": round(contact_norm, 1),
        "sector_risk": round(sector_risk, 1),
        "credit_risk": round(credit_risk, 1),
        "overdue_component": round(overdue_norm * weights["overdue"], 2),
        "amount_component": round(amount_norm * weights["amount"], 2),
        "history_component": round(history_risk * weights["history"], 2),
        "contact_component": round(contact_norm * weights["contact"], 2),
        "sector_component": round(sector_risk * weights["sector"], 2),
        "credit_component": round(credit_risk * weights["credit"], 2),
        "trend_bonus": round(trend_bonus, 2),
        "compound_penalty": round(compound_penalty, 2),
        "base_score": round(base_score, 2),
    }

    # IFRS 9 & Finansal Zarar Metrikleri
    ifrs9 = calculate_ifrs9_stage(
        row["days_overdue"], final_score, row.get("trend", 0), row.get("credit_rating", "B")
    )
    el_data = calculate_expected_loss(row, final_score)

    return {
        "risk_score": round(final_score, 1),
        "score_breakdown": breakdown,
        "ifrs9": ifrs9,
        "el_data": el_data,
    }


def get_action(risk_score: float) -> str:
    """Aksiyon kural eşikleri"""
    if risk_score >= 80:
        return "🔴 Hemen Ara"
    elif risk_score >= 60:
        return "🟠 E-posta At"
    elif risk_score >= 40:
        return "🟡 Takipte Tut"
    else:
        return "🟢 Bekle"


def get_action_en(risk_score: float) -> str:
    """English action label"""
    if risk_score >= 80:
        return "Call Immediately"
    elif risk_score >= 60:
        return "Send Email"
    elif risk_score >= 40:
        return "Monitor"
    else:
        return "Wait"


def get_action_color(risk_score: float) -> str:
    """Streamlit renk kodu"""
    if risk_score >= 80:
        return "red"
    elif risk_score >= 60:
        return "orange"
    elif risk_score >= 40:
        return "yellow"
    else:
        return "green"


def get_trend_label(trend: int) -> str:
    """Trend etiketleri"""
    trend_map = {
        -2: "📉 Hızlı Kötüleşiyor",
        -1: "↘️ Kötüleşiyor",
        0: "➡️ Stabil",
        1: "↗️ İyileşiyor",
        2: "📈 Hızlı İyileşiyor",
    }
    return trend_map.get(trend, "➡️ Stabil")


def score_portfolio(df: pd.DataFrame, profile_key: str = "balanced") -> pd.DataFrame:
    """Tüm portföyü seçilen model profiliyle skorla"""
    results = []

    for _, row in df.iterrows():
        scoring = calculate_risk_score(row, profile_key=profile_key)
        risk_score = scoring["risk_score"]
        breakdown = scoring["score_breakdown"]
        ifrs9 = scoring["ifrs9"]
        el = scoring["el_data"]

        result = {
            "debtor_id": row["debtor_id"],
            "debtor_name": row["debtor_name"],
            "sector": row["sector"],
            "credit_rating": row["credit_rating"],
            "invoice_count": row["invoice_count"],
            "historical_delays": row["historical_delays"],
            "days_overdue": row["days_overdue"],
            "outstanding_amount": row["outstanding_amount"],
            "payment_history_score": row["payment_history_score"],
            "days_since_contact": row["days_since_contact"],
            "trend": row["trend"],
            "trend_label": get_trend_label(row["trend"]),
            "last_contact_date": row["last_contact_date"],
            "invoice_date": row["invoice_date"],
            "risk_score": risk_score,
            "action": get_action(risk_score),
            "action_en": get_action_en(risk_score),
            "action_color": get_action_color(risk_score),
            # IFRS 9 & Finansal Metrikler
            "ifrs9_stage": ifrs9["stage"],
            "ifrs9_stage_label": ifrs9["stage_label"],
            "ifrs9_stage_desc": ifrs9["stage_desc"],
            "ifrs9_stage_color": ifrs9["stage_color"],
            "pd_rate": el["pd_rate"],
            "pd_pct": el["pd_pct"],
            "lgd_rate": el["lgd_rate"],
            "lgd_pct": el["lgd_pct"],
            "expected_loss": el["expected_loss"],
            # Normalize Faktörler (Radar Chart için 0-100)
            "norm_overdue": breakdown["overdue_norm"],
            "norm_amount": breakdown["amount_norm"],
            "norm_history": breakdown["history_risk"],
            "norm_contact": breakdown["contact_norm"],
            "norm_sector": breakdown["sector_risk"],
            "norm_credit": breakdown["credit_risk"],
            # Katkı Bileşenleri
            "score_overdue": breakdown["overdue_component"],
            "score_amount": breakdown["amount_component"],
            "score_history": breakdown["history_component"],
            "score_contact": breakdown["contact_component"],
            "score_sector": breakdown["sector_component"],
            "score_credit": breakdown["credit_component"],
            "score_trend": breakdown["trend_bonus"],
            "score_compound": breakdown["compound_penalty"],
        }
        results.append(result)

    scored_df = pd.DataFrame(results)

    # Risk skoruna göre sırala (en yüksek önce)
    scored_df = scored_df.sort_values("risk_score", ascending=False).reset_index(
        drop=True
    )
    scored_df.index += 1  # 1'den başlat

    return scored_df


if __name__ == "__main__":
    import sys

    sys.stdout.reconfigure(encoding="utf-8")

    from data_generator import generate_mock_debtors

    df = generate_mock_debtors(20)
    scored = score_portfolio(df)

    display = scored[
        [
            "debtor_name",
            "risk_score",
            "ifrs9_stage_label",
            "pd_pct",
            "expected_loss",
            "action_en",
        ]
    ].head(5)

    print("=== ADVANCED RISK SCORING SAMPLE ===")
    print(display.to_string())
