"""Signal scorer classification tests."""
from __future__ import annotations

from signals.signal_scorer import SignalQuality, SignalScorer


def test_perfect_score_high_quality():
    scorer = SignalScorer()
    components = {k: 100.0 for k in scorer.weights}
    breakdown = scorer.score(components)
    assert breakdown.total == 100.0
    assert breakdown.quality == SignalQuality.HIGH_QUALITY


def test_zero_score_rejected():
    scorer = SignalScorer()
    components = {k: 0.0 for k in scorer.weights}
    breakdown = scorer.score(components)
    assert breakdown.total == 0.0
    assert breakdown.quality == SignalQuality.REJECTED


def test_classify_thresholds():
    scorer = SignalScorer()
    assert scorer.classify(90) == SignalQuality.HIGH_QUALITY
    assert scorer.classify(80) == SignalQuality.QUALIFIED
    assert scorer.classify(50) == SignalQuality.REJECTED


def test_is_qualified():
    scorer = SignalScorer()
    assert scorer.is_qualified(75) is True
    assert scorer.is_qualified(74) is False


def test_components_clamped_to_100():
    scorer = SignalScorer()
    # Values above 100 are clamped so total never exceeds 100.
    components = {k: 999.0 for k in scorer.weights}
    breakdown = scorer.score(components)
    assert breakdown.total <= 100.0
