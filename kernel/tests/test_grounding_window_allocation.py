"""Exact legacy scores/spans, and allocation-free impossible window rejection."""
from dataclasses import replace
from unittest.mock import patch

import pytest
from hypothesis import given, settings, strategies as st
from kernel.core import grounding
from kernel.core.data_model import BBox, Chunk, GroundingMethod
from kernel.tests.test_grounding_cutoff import legacy_window_scan


@given(st.text(alphabet='ab cd.-İ界🙂\t\n!?', max_size=110),
       st.text(alphabet='ab cd.-İ界🙂\t\n!?', max_size=240),
       st.sampled_from([0., .5, .86, .92, 1.]))
@settings(max_examples=120, deadline=None, derandomize=True)
def test_prefix_pruning_preserves_legacy_scores_spans(value, text, cutoff):
    score, span = legacy_window_scan(value, text)
    expected = (score, span) if score >= cutoff else (0., (0, 0))
    assert grounding.best_fuzzy_match(value, text, score_cutoff=cutoff) == expected


@pytest.mark.parametrize('value,text', [
    ('ab', '! ! ! ab ! ab'),
    ('İab', 'zz İab xx İab'),
    ('a'*230, ('b'*250+' ')*12),
    ('wanted value', 'not here '*600+'wanted value '+'other words '*600),
    ('quick brown fox', 'The QUICK brown fox! and QUICK brown fox!'),
])
def test_empty_tokens_truncation_subsampling_and_ties(value, text):
    for cutoff in (0., .5, .92, 1.):
        score, span = legacy_window_scan(value, text)
        expected = (score, span) if score >= cutoff else (0., (0, 0))
        assert grounding.best_fuzzy_match(value, text, score_cutoff=cutoff) == expected


def test_impossible_windows_do_not_allocate_histogram_intersections():
    # Baseline computes allocations for feasible lengths; proof of avoided work,
    # not an unstable timing assertion or a grounding/status relaxation.
    def forbidden(*args):
        raise AssertionError('Counter intersection allocation in hot fuzzy loop')
    with patch.object(grounding.Counter, '__and__', forbidden):
        assert grounding.best_fuzzy_match('abc def', 'abx def '*50, score_cutoff=.92) == (0., (0, 0))


def test_source_bbox_and_mutated_same_id_never_reuse_stale_evidence():
    verifier = grounding.GroundingVerifierImpl(fuzzy_threshold=.9)
    bbox = BBox(1, 2, 3, 4)
    first = Chunk(chunk_id='same-id', text='vendor Acme Corporation then Acme Corporation', page=3, bbox=bbox)
    method, anchors = verifier.verify('Acme Corporatin', '', [first])
    assert method == GroundingMethod.FUZZY
    assert anchors[0].bbox == bbox and anchors[0].page == 3
    assert first.text[slice(*anchors[0].char_span)] == 'Acme Corporation'
    changed = replace(first, text='unrelated banana shake', page=8, bbox=BBox(8, 8, 9, 9))
    assert verifier.verify('Acme Corporatin', '', [changed]) == (GroundingMethod.BLOCK, ())
