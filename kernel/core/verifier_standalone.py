"""
Kairo Phantom — Standalone Grounding Verifier (P1.3)

A model-independent verifier that re-checks every claimed quote and bounding box
against stored document geometry. It imports NO model client — only Python stdlib.

API:
    verify(claimed_quote, claimed_bbox, stored_geometry) -> Verified | Rejected

Cascade (SPEC §S3):
    NORMALIZE → EXACT → FUZZY(≥0.92) → SEMANTIC(≥0.86, re-verify)
              → VISUAL(IoU≥0.5) → BLOCK

The moat: the verifier independently re-checks every quote/coordinate against
stored geometry. The model can never self-certify a bounding box. Even if the
model reports 0.99 confidence, if the bbox points to whitespace, the verifier
rejects it.

This module can be used as a standalone package without importing the rest of
the kernel. It has zero dependencies on model clients, embedding models, or
inference gateways.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


# ---------------------------------------------------------------------------
# Public types — no model dependency, pure data
# ---------------------------------------------------------------------------

class VerifyMethod(str, Enum):
    """Which cascade stage produced the verification."""
    EXACT = "exact"
    FUZZY = "fuzzy"
    SEMANTIC = "semantic"
    VISUAL = "visual"
    BLOCK = "block"


class RejectReason(str, Enum):
    """Why the verifier rejected the claim."""
    OFF_PAGE = "off_page"
    EMPTY_QUOTE = "empty_quote"
    NO_MATCH = "no_match"
    BBOX_MISMATCH = "bbox_mismatch"
    WHITESPACE = "whitespace"


@dataclass(frozen=True)
class BBox:
    """Bounding box in page coordinates (pixels or points)."""
    x0: float
    y0: float
    x1: float
    y1: float

    def __post_init__(self) -> None:
        if self.x0 > self.x1 or self.y0 > self.y1:
            raise ValueError(
                f"Invalid bbox: ({self.x0},{self.y0}) to ({self.x1},{self.y1})"
            )

    @property
    def area(self) -> float:
        return (self.x1 - self.x0) * (self.y1 - self.y0)


@dataclass(frozen=True)
class StoredRegion:
    """A region of stored document geometry with its text and bbox.

    This is the auditable record — the geometry stored at index time.
    The verifier compares claims against this, never against model output.
    """
    text: str
    bbox: BBox
    page: int = 1
    region_id: str = ""


@dataclass(frozen=True)
class PageBounds:
    """Page dimensions for off-page detection."""
    width: float
    height: float


@dataclass(frozen=True)
class Verified:
    """The verifier accepted the claim."""
    method: VerifyMethod
    matched_text: str
    matched_bbox: BBox
    matched_region_id: str
    similarity: float       # text similarity score for the matching stage
    iou: float              # IoU between claimed_bbox and matched_bbox
    page: int = 1


@dataclass(frozen=True)
class Rejected:
    """The verifier rejected the claim — it must not be rendered."""
    reason: RejectReason
    best_similarity: float  # best text similarity found across all regions
    best_iou: float         # best IoU found across all regions
    detail: str = ""


# ---------------------------------------------------------------------------
# Geometry helpers — pure math, no model dependency
# ---------------------------------------------------------------------------

def compute_iou(a: BBox, b: BBox) -> float:
    """Intersection-over-Union between two bounding boxes."""
    ix0 = max(a.x0, b.x0)
    iy0 = max(a.y0, b.y0)
    ix1 = min(a.x1, b.x1)
    iy1 = min(a.y1, b.y1)

    inter_w = ix1 - ix0
    inter_h = iy1 - iy0
    if inter_w <= 0 or inter_h <= 0:
        return 0.0

    inter_area = inter_w * inter_h
    union_area = a.area + b.area - inter_area
    if union_area <= 0:
        return 0.0

    return inter_area / union_area


def bbox_within_page(bbox: BBox, page: PageBounds | None) -> bool:
    """Check that a bbox is within page bounds (not off-page)."""
    if page is None:
        return True  # no page bounds provided, skip check
    if bbox.x0 < 0 or bbox.y0 < 0:
        return False
    if bbox.x1 > page.width or bbox.y1 > page.height:
        return False
    return True


def bbox_over_whitespace(claimed_bbox: BBox, regions: list[StoredRegion],
                         iou_threshold: float = 0.1) -> bool:
    """Check if a bbox is over whitespace (no significant overlap with any region)."""
    for region in regions:
        if compute_iou(claimed_bbox, region.bbox) >= iou_threshold:
            return False
    return True


# ---------------------------------------------------------------------------
# Text helpers — pure string processing, no model dependency
# ---------------------------------------------------------------------------

def normalize_text(text: str) -> str:
    """NORMALIZE step: strip whitespace/case/punctuation/number-format variants."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s\-\.]', '', text)
    text = " ".join(text.split())
    text = re.sub(r'[\$\u20ac\u00a3\u00a5]', '', text)
    return text


def levenshtein_ratio(s1: str, s2: str) -> float:
    """Levenshtein similarity ratio between two strings (0.0 to 1.0)."""
    s1 = s1.lower()
    s2 = s2.lower()
    if s1 == s2:
        return 1.0
    if len(s1) == 0 or len(s2) == 0:
        return 0.0

    rows = len(s1) + 1
    cols = len(s2) + 1
    dist = [[0] * cols for _ in range(rows)]

    for i in range(1, rows):
        dist[i][0] = i
    for j in range(1, cols):
        dist[0][j] = j

    for col in range(1, cols):
        for row in range(1, rows):
            cost = 0 if s1[row - 1] == s2[col - 1] else 1
            dist[row][col] = min(
                dist[row - 1][col] + 1,
                dist[row][col - 1] + 1,
                dist[row - 1][col - 1] + cost,
            )

    return 1.0 - (dist[rows - 1][cols - 1] / max(len(s1), len(s2)))


def best_fuzzy_match(value: str, text: str) -> tuple[float, int, int]:
    """Scan word windows in text for best fuzzy substring match.
    Returns (best_ratio, start_char, end_char).
    """
    val_norm = normalize_text(value)
    if not val_norm:
        return 0.0, 0, 0

    val_words = val_norm.split()
    n = len(val_words)

    words_spans = []
    for m in re.finditer(r'\S+', text):
        words_spans.append((m.group(0), m.start(), m.end()))

    if not words_spans:
        return 0.0, 0, 0

    best_ratio = 0.0
    best_span = (0, 0)

    for length in range(max(1, n - 1), min(len(words_spans) + 1, n + 3)):
        for i in range(len(words_spans) - length + 1):
            window = words_spans[i:i + length]
            sub_text = text[window[0][1]:window[-1][2]]
            sub_norm = normalize_text(sub_text)
            ratio = levenshtein_ratio(val_norm, sub_norm)
            if ratio > best_ratio:
                best_ratio = ratio
                best_span = (window[0][1], window[-1][2])

    return best_ratio, best_span[0], best_span[1]


def jaccard_similarity(s1: str, s2: str) -> float:
    """Jaccard similarity between token sets of two strings (0.0 to 1.0).

    This is a deterministic text-similarity measure that requires NO model.
    It replaces embedding-based cosine similarity in the standalone verifier
    so the module has zero model-client dependencies.
    """
    tokens1 = set(normalize_text(s1).split())
    tokens2 = set(normalize_text(s2).split())
    if not tokens1 and not tokens2:
        return 1.0
    if not tokens1 or not tokens2:
        return 0.0
    intersection = tokens1 & tokens2
    union = tokens1 | tokens2
    return len(intersection) / len(union)


def semantic_re_verify(claimed_quote: str, region_text: str) -> bool:
    """Re-verification for the SEMANTIC stage: require at least one content
    word from the claim to appear in the region text.

    This prevents pure topic-overlap from passing when the actual claim
    content is absent.
    """
    claim_words = set(normalize_text(claimed_quote).split())
    region_words = set(normalize_text(region_text).split())
    # Filter out very short tokens (stop-word-like)
    claim_content = {w for w in claim_words if len(w) > 2}
    if not claim_content:
        return len(claim_words) > 0 and len(claim_words & region_words) > 0
    return len(claim_content & region_words) > 0


# ---------------------------------------------------------------------------
# Standalone Verifier — the trust boundary
# ---------------------------------------------------------------------------

class StandaloneVerifier:
    """Model-independent grounding verifier.

    Implements the full cascade:
    NORMALIZE → EXACT → FUZZY(≥0.92) → SEMANTIC(≥0.86, re-verify)
              → VISUAL(IoU≥0.5) → BLOCK

    Every text-matching stage (EXACT, FUZZY, SEMANTIC) also verifies that the
    claimed bbox overlaps the matched region by IoU≥0.5. This is the key
    anti-hallucination check: a VLM can hallucinate text that appears in the
    document, but if its bbox points to whitespace, the IoU check fails and
    the claim is rejected.

    The VISUAL stage is a bbox-first fallback: if text matching failed but
    the claimed bbox overlaps a stored region by IoU≥0.5, and the claimed
    quote appears in that region's text, it is accepted as a visual match.
    This handles OCR-degraded text where exact/fuzzy matching may fail but
    the spatial location is correct.
    """

    def __init__(
        self,
        fuzzy_threshold: float = 0.92,
        semantic_threshold: float = 0.86,
        visual_iou_threshold: float = 0.5,
    ) -> None:
        self.fuzzy_threshold = fuzzy_threshold
        self.semantic_threshold = semantic_threshold
        self.visual_iou_threshold = visual_iou_threshold

    def verify(
        self,
        claimed_quote: str,
        claimed_bbox: BBox,
        stored_geometry: list[StoredRegion],
        page_bounds: PageBounds | None = None,
    ) -> Verified | Rejected:
        """Verify a claimed quote and bbox against stored document geometry.

        Args:
            claimed_quote: The text the model claims to have found.
            claimed_bbox: The bounding box the model claims the text is at.
            stored_geometry: The stored document regions (text + bbox).
            page_bounds: Optional page dimensions for off-page detection.

        Returns:
            Verified if the claim passes any cascade stage, Rejected otherwise.
        """
        if not stored_geometry:
            return Rejected(
                reason=RejectReason.NO_MATCH,
                best_similarity=0.0,
                best_iou=0.0,
                detail="no stored geometry",
            )

        # 0. Off-page check
        if page_bounds is not None and not bbox_within_page(claimed_bbox, page_bounds):
            return Rejected(
                reason=RejectReason.OFF_PAGE,
                best_similarity=0.0,
                best_iou=0.0,
                detail=f"bbox {claimed_bbox} outside page {page_bounds}",
            )

        # 1. NORMALIZE
        norm_quote = normalize_text(claimed_quote)
        if not norm_quote:
            return Rejected(
                reason=RejectReason.EMPTY_QUOTE,
                best_similarity=0.0,
                best_iou=0.0,
                detail="claimed quote is empty after normalization",
            )

        best_sim = 0.0
        best_iou = 0.0

        # 2. EXACT — text appears verbatim in a stored region AND bbox overlaps
        for region in stored_geometry:
            norm_region = normalize_text(region.text)
            if norm_quote in norm_region:
                iou = compute_iou(claimed_bbox, region.bbox)
                best_iou = max(best_iou, iou)
                best_sim = 1.0
                if iou >= self.visual_iou_threshold:
                    return Verified(
                        method=VerifyMethod.EXACT,
                        matched_text=region.text,
                        matched_bbox=region.bbox,
                        matched_region_id=region.region_id,
                        similarity=1.0,
                        iou=iou,
                        page=region.page,
                    )

        # 3. FUZZY (≥0.92) — fuzzy text match AND bbox overlaps
        best_fuzzy_ratio = 0.0
        best_fuzzy_region = None
        for region in stored_geometry:
            ratio, _, _ = best_fuzzy_match(claimed_quote, region.text)
            if ratio > best_fuzzy_ratio:
                best_fuzzy_ratio = ratio
                best_fuzzy_region = region

        if best_fuzzy_region and best_fuzzy_ratio >= self.fuzzy_threshold:
            iou = compute_iou(claimed_bbox, best_fuzzy_region.bbox)
            best_iou = max(best_iou, iou)
            best_sim = max(best_sim, best_fuzzy_ratio)
            if iou >= self.visual_iou_threshold:
                return Verified(
                    method=VerifyMethod.FUZZY,
                    matched_text=best_fuzzy_region.text,
                    matched_bbox=best_fuzzy_region.bbox,
                    matched_region_id=best_fuzzy_region.region_id,
                    similarity=best_fuzzy_ratio,
                    iou=iou,
                    page=best_fuzzy_region.page,
                )

        # 4. SEMANTIC (≥0.86, re-verify) — semantic text match AND bbox overlaps
        best_sem_score = 0.0
        best_sem_region = None
        for region in stored_geometry:
            score = jaccard_similarity(claimed_quote, region.text)
            if score > best_sem_score:
                best_sem_score = score
                best_sem_region = region

        if best_sem_region and best_sem_score >= self.semantic_threshold:
            best_sim = max(best_sim, best_sem_score)
            if semantic_re_verify(claimed_quote, best_sem_region.text):
                iou = compute_iou(claimed_bbox, best_sem_region.bbox)
                best_iou = max(best_iou, iou)
                if iou >= self.visual_iou_threshold:
                    return Verified(
                        method=VerifyMethod.SEMANTIC,
                        matched_text=best_sem_region.text,
                        matched_bbox=best_sem_region.bbox,
                        matched_region_id=best_sem_region.region_id,
                        similarity=best_sem_score,
                        iou=iou,
                        page=best_sem_region.page,
                    )

        # 5. VISUAL (IoU≥0.5) — bbox-first fallback with text verification
        #    If text matching failed but the bbox overlaps a stored region,
        #    and the claimed quote appears in that region, accept as visual match.
        for region in stored_geometry:
            iou = compute_iou(claimed_bbox, region.bbox)
            best_iou = max(best_iou, iou)
            if iou >= self.visual_iou_threshold:
                # Verify the claimed quote appears in this region
                norm_region = normalize_text(region.text)
                if norm_quote in norm_region:
                    return Verified(
                        method=VerifyMethod.VISUAL,
                        matched_text=region.text,
                        matched_bbox=region.bbox,
                        matched_region_id=region.region_id,
                        similarity=1.0,
                        iou=iou,
                        page=region.page,
                    )
                # Try fuzzy match in this region
                fuzzy_ratio, _, _ = best_fuzzy_match(claimed_quote, region.text)
                if fuzzy_ratio >= self.fuzzy_threshold:
                    return Verified(
                        method=VerifyMethod.VISUAL,
                        matched_text=region.text,
                        matched_bbox=region.bbox,
                        matched_region_id=region.region_id,
                        similarity=fuzzy_ratio,
                        iou=iou,
                        page=region.page,
                    )

        # 6. BLOCK — no stage passed
        # Determine the most informative reject reason
        if best_sim >= self.fuzzy_threshold or best_sim >= self.semantic_threshold:
            # Text matched but bbox didn't overlap
            reason = RejectReason.BBOX_MISMATCH
            detail = (
                f"text matched (sim={best_sim:.3f}) but bbox IoU={best_iou:.3f} "
                f"< {self.visual_iou_threshold}"
            )
        elif best_iou >= self.visual_iou_threshold:
            # Bbox overlapped a region but text didn't match
            reason = RejectReason.NO_MATCH
            detail = (
                f"bbox overlapped (IoU={best_iou:.3f}) but text didn't match "
                f"(best_sim={best_sim:.3f})"
            )
        elif bbox_over_whitespace(claimed_bbox, stored_geometry):
            reason = RejectReason.WHITESPACE
            detail = f"bbox over whitespace, no region overlap (best_iou={best_iou:.3f})"
        else:
            reason = RejectReason.NO_MATCH
            detail = f"no match (best_sim={best_sim:.3f}, best_iou={best_iou:.3f})"

        return Rejected(
            reason=reason,
            best_similarity=best_sim,
            best_iou=best_iou,
            detail=detail,
        )


# ---------------------------------------------------------------------------
# Convenience function for simple usage
# ---------------------------------------------------------------------------

def verify(
    claimed_quote: str,
    claimed_bbox: BBox,
    stored_geometry: list[StoredRegion],
    page_bounds: PageBounds | None = None,
) -> Verified | Rejected:
    """One-shot verification using a default StandaloneVerifier instance."""
    return StandaloneVerifier().verify(
        claimed_quote, claimed_bbox, stored_geometry, page_bounds
    )