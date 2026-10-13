"""Acceptance-aware pruning must not invent or discard accepted matches."""
import re

from hypothesis import given, settings
from hypothesis import strategies as st

from kernel.core.grounding import (
    best_fuzzy_match,
    levenshtein_ratio,
    normalize_text,
)


def legacy_window_scan(value, text):
    norm = normalize_text(value)
    if not norm:
        return 0.0, (0, 0)
    n = len(norm.split())
    spans = [(m.start(), m.end()) for m in re.finditer(r"\S+", text)]
    score, span, scanned = 0.0, (0, 0), 0
    for length in range(max(1, n - 1), min(len(spans) + 1, n + 3)):
        size = len(spans) - length + 1
        indices = range(size) if size <= 500 else (int(i * size / 500) for i in range(500))
        for i in indices:
            if scanned >= 500:
                break
            scanned += 1
            window = (spans[i][0], spans[i + length - 1][1])
            ratio = levenshtein_ratio(norm, normalize_text(text[slice(*window)]))
            if ratio > score:
                score, span = ratio, window
        if scanned >= 500:
            break
    return score, span


@given(st.text(alphabet="abc def.-İ", max_size=220),
       st.text(alphabet="abc def.-İ", max_size=400),
       st.sampled_from([0.5, 0.75, 0.86, 0.92, 1.0]))
@settings(max_examples=400, deadline=None)
def test_cutoff_preserves_all_accepted_scores_and_spans(value, text, cutoff):
    score, span = legacy_window_scan(value, text)
    assert best_fuzzy_match(value, text) == (score, span)
    pruned, pruned_span = best_fuzzy_match(value, text, score_cutoff=cutoff)
    if score >= cutoff:
        assert (pruned, pruned_span) == (score, span)
    else:
        assert pruned == 0


def test_normalization_and_repeated_match_keep_first_anchor():
    text = "wrong value; The QUICK brown fox. filler THE quick brown FOX."
    assert best_fuzzy_match("the quick brown fox", text, score_cutoff=.92) == best_fuzzy_match(
        "the quick brown fox", text)


@given(st.text(max_size=100), st.text(max_size=220))
@settings(max_examples=250, deadline=None)
def test_unicode_token_preparation_matches_whole_window_normalization(value, text):
    assert best_fuzzy_match(value, text) == legacy_window_scan(value, text)


def test_window_cap_and_subsampling_preserve_historical_anchor():
    text = "not here " * 600 + "wanted value " + "other words " * 600
    assert best_fuzzy_match("wanted value", text) == legacy_window_scan("wanted value", text)