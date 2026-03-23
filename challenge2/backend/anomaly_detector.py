"""
Anomaly Detection — Isolation Forest model for solar yield anomalies.

Flags when actual solar yield deviates >15% below expected yield (corrected for irradiance).
"""

import logging
import numpy as np
from typing import Optional
from sklearn.ensemble import IsolationForest
from dataclasses import dataclass

logger = logging.getLogger(__name__)

ANOMALY_THRESHOLD_PCT = -15.0  # Flag if >15% below expected
WARNING_THRESHOLD = -0.10      # Isolation Forest score < this = WARNING
CRITICAL_THRESHOLD = -0.30     # Isolation Forest score < this = CRITICAL


@dataclass
class AnomalyResult:
    is_anomaly: bool
    severity: str          # "OK" | "WARNING" | "CRITICAL"
    score: float           # Isolation Forest decision function score
    deviation_pct: float   # % deviation from expected


class SolarAnomalyDetector:
    """
    Isolation Forest-based anomaly detector for solar readings.
    Features: performance_ratio, actual_vs_expected_pct, temp_c, irradiance
    """

    def __init__(self):
        self.model: Optional[IsolationForest] = None
        self._trained = False

    def train(self, historical_df) -> None:
        """
        Train the model on historical solar readings.
        historical_df: DataFrame with columns:
            ['performance_ratio', 'actual_vs_expected_pct', 'temp_c', 'irradiance']
        """
        if len(historical_df) < 10:
            logger.warning("Insufficient data for training (%d rows) — using threshold-only detection", len(historical_df))
            self._trained = False
            return

        X = historical_df[["performance_ratio", "actual_vs_expected_pct", "temp_c", "irradiance"]].values
        self.model = IsolationForest(
            contamination=0.05,  # 5% expected anomaly rate
            random_state=42,
            n_estimators=100,
        )
        self.model.fit(X)
        self._trained = True
        logger.info("Anomaly detection model trained on %d samples", len(X))

    def score_reading(
        self,
        performance_ratio: float,
        actual_vs_expected_pct: float,
        temp_c: float,
        irradiance: float,
    ) -> AnomalyResult:
        """
        Score a single solar reading.
        Returns AnomalyResult with severity label.
        """
        # Primary check: rule-based threshold (always applied)
        is_rule_anomaly = actual_vs_expected_pct < ANOMALY_THRESHOLD_PCT

        if self._trained and self.model is not None:
            X = np.array([[performance_ratio, actual_vs_expected_pct, temp_c, irradiance]])
            score = self.model.decision_function(X)[0]
            is_ml_anomaly = self.model.predict(X)[0] == -1  # -1 = anomaly
        else:
            # Fallback: threshold-based scoring
            score = actual_vs_expected_pct / 100.0  # Normalise
            is_ml_anomaly = is_rule_anomaly

        is_anomaly = is_rule_anomaly or is_ml_anomaly

        if score < CRITICAL_THRESHOLD or actual_vs_expected_pct < -25:
            severity = "CRITICAL"
        elif score < WARNING_THRESHOLD or actual_vs_expected_pct < ANOMALY_THRESHOLD_PCT:
            severity = "WARNING"
        else:
            severity = "OK"

        if severity == "OK":
            is_anomaly = False

        return AnomalyResult(
            is_anomaly=is_anomaly,
            severity=severity,
            score=float(score),
            deviation_pct=float(actual_vs_expected_pct),
        )

    def score_batch(self, readings: list[dict]) -> list[AnomalyResult]:
        """Score a list of readings dicts."""
        return [
            self.score_reading(
                performance_ratio=r["performance_ratio"],
                actual_vs_expected_pct=r["actual_vs_expected_pct"],
                temp_c=r["temp_c"],
                irradiance=r["irradiance"],
            )
            for r in readings
        ]


# Global model instance — shared across requests
detector = SolarAnomalyDetector()


def inject_fault(site_id: str, reduction_pct: float = 60.0) -> None:
    """
    Inject a synthetic fault for evaluator testing.
    Sets the site's next readings to reduction_pct% of expected output.
    """
    from . import data_simulator
    data_simulator.FAULT_INJECTIONS[site_id] = reduction_pct
    logger.warning("Fault injected for site %s: %.0f%% output reduction", site_id, reduction_pct)


def clear_fault(site_id: str) -> None:
    """Clear an injected fault."""
    from . import data_simulator
    data_simulator.FAULT_INJECTIONS.pop(site_id, None)
    logger.info("Fault cleared for site %s", site_id)
