"""
Collections Intelligence - Groq LLM Explanation Engine
Explainable AI (XAI) for B2B Debt Collection & Financial Risk

Model: Llama 3.3 70B via Groq API
Includes IFRS 9 Staging and Expected Loss (EL = PD x LGD x EAD) context.
"""

import os
import time
import pandas as pd
from groq import Groq

_DEFAULT_MODEL = "llama-3.3-70b-versatile"


def get_groq_client():
    """Groq client'ı başlat (Cloudflare edge proxy üzerinden)"""
    return Groq(
        api_key="secured-by-cloudflare",
        base_url="https://zolvo-groq-proxy.emrezeynoel.workers.dev"
    )


def build_explanation_prompt(row: pd.Series, language: str = "tr") -> str:
    """
    Borçlu verilerinden zengin finansal bağlamlı LLM prompt'u oluştur.
    LLM karar vermez, analiste açıklanabilir stratejik özet sunar.
    """
    trend_map = {
        -2: "hızla kötüleşiyor (-15 puan)",
        -1: "kötüleşiyor (-7 puan)",
        0: "stabil",
        1: "iyileşiyor (+5 puan)",
        2: "hızla iyileşiyor (+10 puan)",
    }
    trend_text = trend_map.get(row.get("trend", 0), "stabil")

    action_clean = (
        str(row.get("action", ""))
        .replace("🔴 ", "")
        .replace("🟠 ", "")
        .replace("🟡 ", "")
        .replace("🟢 ", "")
    )

    stage_label = row.get("ifrs9_stage_label", "Stage 2")
    pd_pct = row.get("pd_pct", 50.0)
    lgd_pct = row.get("lgd_pct", 40.0)
    el_amount = row.get("expected_loss", 0.0)
    out_amount = row.get("outstanding_amount", 0.0)

    if language == "tr":
        prompt = f"""Sen kurumsal bir Fintech Kredi Riski ve Collections Intelligence AI uzmanısın.
Aşağıdaki B2B borçlu profili için önerilen aksiyonun finansal gerekçesini 2 kısa cümleyle açıkla.

BAĞLAM:
- Borçlu: {row.get('debtor_name')}
- Sektör / LGD: {row.get('sector', 'Bilinmiyor')} (Temerrüt Kaybı: %{lgd_pct})
- Kredi Notu: {row.get('credit_rating', 'Bilinmiyor')}
- IFRS 9 Kredi Aşaması: {stage_label}
- Temerrüt Olasılığı (PD): %{pd_pct}
- Beklenen Finansal Zarar (EL): ${el_amount:,.0f} USD (Toplam Açık: ${out_amount:,.0f} USD)
- Gecikme Süresi: {row.get('days_overdue', 0)} gün (Ödeme Trendi: {trend_text})
- Ödeme Geçmişi: {row.get('payment_history_score', 50)}/100 | Son İletişim: {row.get('days_since_contact', 0)} gün önce
- Kompozit Risk Skoru: {row.get('risk_score', 0)}/100
- Önerilen Aksiyon: {action_clean}

KURAL: Sadece açıkla ve risk faktörlerine vurgu yap, nihai kararı insan yöneticiye bırak.
Maksimum 2 cümle. Profesyonel finansal Türkçe ton kullan."""
    else:
        prompt = f"""You are an enterprise Fintech Credit Risk & Collections Intelligence AI expert.
Explain in 2 concise sentences the financial rationale behind the recommended action for this B2B debtor.

CONTEXT:
- Debtor: {row.get('debtor_name')}
- Sector / LGD: {row.get('sector', 'Unknown')} (Loss Given Default: {lgd_pct}%)
- Credit Rating: {row.get('credit_rating', 'Unknown')}
- IFRS 9 Stage: {stage_label}
- Probability of Default (PD): {pd_pct}%
- Expected Loss (EL): ${el_amount:,.0f} USD (Outstanding Exposure: ${out_amount:,.0f} USD)
- Overdue Period: {row.get('days_overdue', 0)} days (Payment Trend: {trend_text})
- Payment History: {row.get('payment_history_score', 50)}/100 | Last Contact: {row.get('days_since_contact', 0)} days ago
- Composite Risk Score: {row.get('risk_score', 0)}/100
- Recommended Action: {action_clean}

RULE: Only explain and highlight specific financial risk drivers. Do NOT make the final executive decision.
Maximum 2 sentences. Professional quantitative tone in English."""

    return prompt


def generate_explanation(
    client: Groq, row: pd.Series, language: str = "tr", model: str = _DEFAULT_MODEL
) -> str:
    """Tek bir borçlu için Groq API'si ile açıklama üret"""
    prompt = build_explanation_prompt(row, language)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "Sen kurumsal kredi riski ve tahsilat istihbaratı alanında uzmanlaşmış bir XAI (Explainable AI) motorusun. Net, analitik ve kanıta dayalı çıktılar üretirsin.",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=180,
            temperature=0.25,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"[API Hatası: {str(e)[:80]}]"


def get_single_explanation(row: pd.Series, language: str = "tr") -> str:
    """Dashboard'da tek borçlu için on-demand açıklama"""
    client = get_groq_client()
    return generate_explanation(client, row, language)
