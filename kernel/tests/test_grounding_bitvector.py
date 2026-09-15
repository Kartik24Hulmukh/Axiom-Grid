"""Differential checks against the previous exact rolling-row DP.
The historical truncation and length-ratio guards are intentionally unchanged;
this performance patch does not certify long-field grounding semantics.
"""
import itertools

from hypothesis import given, settings, strategies as st

from kernel.core.grounding import levenshtein_ratio


def reference(a, b):
    a, b = a.lower(), b.lower()
    if a == b:
        return 1.0
    if not a or not b or min(len(a), len(b)) / max(len(a), len(b)) < 0.5:
        return 0.0
    a, b = a[:200], b[:200]
    previous = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        current = [i]
        for j, y in enumerate(b, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j-1] + (x != y)))
        previous = current
    return 1.0 - previous[-1] / max(len(a), len(b))


def test_exhaustive_small_alphabet():
    words = ["".join(chars) for n in range(5) for chars in itertools.product("ab", repeat=n)]
    for a in words:
        for b in words:
            assert levenshtein_ratio(a, b) == reference(a, b)


@given(st.text(max_size=240), st.text(max_size=240))
@settings(max_examples=200, deadline=None)
def test_unicode_matches_reference(a, b):
    assert levenshtein_ratio(a, b) == reference(a, b)


def test_long_similar_strings_and_case_expansion():
    for a, b in [("a" * 200, "a" * 199 + "b"), ("abc" * 100, "acb" * 100), ("İ" * 150, "i" * 150)]:
        assert levenshtein_ratio(a, b) == reference(a, b)
