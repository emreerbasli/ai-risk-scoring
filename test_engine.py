"""
Unit Test Suite for AI Risk Scoring Engine
Validates non-linear curves, IFRS 9 staging, Expected Loss formulas, and scenario weights.

Run: python -m unittest test_engine.py
"""

import unittest
import pandas as pd
import numpy as np
from scoring_engine import (
    normalize_overdue_nonlinear,
    normalize_amount,
    normalize_payment_history,
    normalize_contact_gap,
    calculate_ifrs9_stage,
    calculate_pd,
    calculate_expected_loss,
    calculate_risk_score,
    score_portfolio,
    MODEL_PROFILES,
    SECTOR_LGD_MAP,
)
from data_generator import generate_mock_debtors


class TestRiskScoringEngine(unittest.TestCase):

    def test_model_profile_weights_sum_to_one(self):
        """Tüm model senaryolarının ağırlık toplamı tam olarak 1.00 (%100) olmalıdır."""
        for key, profile in MODEL_PROFILES.items():
            total_weight = sum(profile["weights"].values())
            self.assertAlmostEqual(
                total_weight, 1.00, places=4,
                msg=f"{key} model profilinin ağırlık toplamı 1.00 değil: {total_weight}"
            )

    def test_overdue_nonlinear_boundaries(self):
        """Gecikme eğrisi sınır koşullarını ve IFRS 9 kademeli artışını doğrula."""
        self.assertEqual(normalize_overdue_nonlinear(0), 0.0)
        self.assertEqual(normalize_overdue_nonlinear(-10), 0.0)
        self.assertAlmostEqual(normalize_overdue_nonlinear(30), 25.0, places=1)
        self.assertAlmostEqual(normalize_overdue_nonlinear(90), 85.0, places=1)
        self.assertEqual(normalize_overdue_nonlinear(120), 100.0)
        self.assertEqual(normalize_overdue_nonlinear(300), 100.0)
        self.assertEqual(normalize_overdue_nonlinear(None), 0.0)

    def test_ifrs9_staging_logic(self):
        """IFRS 9 Kredi aşamalandırma mantığını doğrula."""
        # Stage 1: 0-30 gün ve düşük risk
        s1 = calculate_ifrs9_stage(days_overdue=10, risk_score=25.0, trend=0, credit_rating="A")
        self.assertEqual(s1["stage"], 1)

        # Stage 2: 31-89 gün veya kötüleşen trend veya Rating D
        s2 = calculate_ifrs9_stage(days_overdue=45, risk_score=60.0, trend=-1, credit_rating="C")
        self.assertEqual(s2["stage"], 2)

        # Stage 3: 90+ gün veya risk skoru >= 80
        s3_overdue = calculate_ifrs9_stage(days_overdue=95, risk_score=70.0, trend=0, credit_rating="B")
        self.assertEqual(s3_overdue["stage"], 3)
        s3_score = calculate_ifrs9_stage(days_overdue=20, risk_score=85.0, trend=0, credit_rating="D")
        self.assertEqual(s3_score["stage"], 3)

    def test_expected_loss_mathematical_precision(self):
        """Expected Loss (EL = PD x LGD x EAD) formülünün matematiksel doğruluğu."""
        row = pd.Series({
            "sector": "İnşaat",
            "outstanding_amount": 100000.0,
        })
        # İnşaat LGD: 0.65
        lgd = SECTOR_LGD_MAP["İnşaat"]
        self.assertEqual(lgd, 0.65)

        # Risk skoru 50 -> PD tam %50 (0.50)
        pd_rate = calculate_pd(50.0)
        self.assertAlmostEqual(pd_rate, 0.50, places=2)

        el_res = calculate_expected_loss(row, risk_score=50.0)
        expected_el = pd_rate * 0.65 * 100000.0
        self.assertAlmostEqual(el_res["expected_loss"], expected_el, places=1)

    def test_risk_score_range_and_stability(self):
        """Risk skorunun daima 0 ile 100 arasında sınırlandığını test et."""
        df = generate_mock_debtors(50, seed=42)
        scored = score_portfolio(df)
        self.assertEqual(len(scored), 50)
        self.assertTrue((scored["risk_score"] >= 0.0).all())
        self.assertTrue((scored["risk_score"] <= 100.0).all())
        self.assertTrue((scored["expected_loss"] >= 0.0).all())

    def test_empty_dataframe_protection(self):
        """Boş veri seti verildiğinde sistemin çökmemesini doğrula."""
        empty_df = pd.DataFrame()
        result = score_portfolio(empty_df)
        self.assertTrue(result.empty)


if __name__ == "__main__":
    unittest.main()
