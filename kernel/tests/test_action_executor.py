"""
Tests for ActionExecutor.
"""


from kernel.core.data_model import (
    Action,
    ActionKind,
    BBox,
    Chunk,
    Document,
    Extraction,
    Suggestion,
)
from kernel.core.provenance import ProvenanceLogImpl
from kernel.sidecar.action_executor import ActionExecutorImpl


def test_suggest_action():
    """Test that suggestion is generated with full provenance."""
    prov = ProvenanceLogImpl()
    doc = Document(doc_id="doc-1", source_path="memo.txt", sha256="abc", page_count=1)
    chunk = Chunk(chunk_id="chunk-1", doc_id="doc-1", page=1, bbox=BBox(0,0,1,1), text="Dr. Margaret Chen")
    ext = Extraction(ext_id="ext-1", pack_id="wedge", field_name="author", value="Dr. Margaret Chen", chunk_id="chunk-1")
    action = Action(action_id="act-1", ext_id="ext-1", kind=ActionKind.SUGGEST, target_app="notepad", payload={"value": "Dr. Margaret Chen"}, confidence=0.9)

    prov.register_document(doc)
    prov.register_chunk(chunk)
    prov.register_extraction(ext)
    prov.register_action(action)

    executor = ActionExecutorImpl(prov)
    sugg = executor.suggest(action)

    assert isinstance(sugg, Suggestion)
    assert sugg.action == action
    assert sugg.provenance.is_complete
    assert sugg.confidence == 0.9
    assert "notepad" in sugg.display_text


def test_apply_autonomous_write_rejected():
    """Test that apply() without human_confirm=True fails."""
    prov = ProvenanceLogImpl()
    action = Action(action_id="act-1", ext_id="ext-1", kind=ActionKind.SUGGEST, target_app="notepad", payload={"value": "Dr. Margaret Chen"})
    executor = ActionExecutorImpl(prov)

    res = executor.apply(action, human_confirm=False)
    assert not res.success
    assert "CUA violation" in res.error


def test_apply_out_of_allowlist_refused():
    """Test that apply() to an app not in the allowlist is refused."""
    prov = ProvenanceLogImpl()
    action = Action(action_id="act-1", ext_id="ext-1", kind=ActionKind.SUGGEST, target_app="malicious_app", payload={"value": "Dr. Margaret Chen"})
    executor = ActionExecutorImpl(prov)

    res = executor.apply(action, human_confirm=True)
    assert not res.success
    assert "CUA Refused" in res.error


def test_apply_mismatched_payload_fails():
    """Test that apply() fails verification if payload value contradicts extraction."""
    prov = ProvenanceLogImpl()
    doc = Document(doc_id="doc-1", source_path="memo.txt", sha256="abc", page_count=1)
    chunk = Chunk(chunk_id="chunk-1", doc_id="doc-1", page=1, bbox=BBox(0,0,1,1), text="Dr. Margaret Chen")
    ext = Extraction(ext_id="ext-1", pack_id="wedge", field_name="author", value="Dr. Margaret Chen", chunk_id="chunk-1")
    
    # Payload has a different name
    action = Action(action_id="act-1", ext_id="ext-1", kind=ActionKind.SUGGEST, target_app="notepad", payload={"value": "Viktor Petrov"})

    prov.register_document(doc)
    prov.register_chunk(chunk)
    prov.register_extraction(ext)
    prov.register_action(action)

    executor = ActionExecutorImpl(prov)
    res = executor.apply(action, human_confirm=True)
    assert not res.success
    assert "Verification failed" in res.error


def test_apply_success():
    """Test successful application and verification of action."""
    prov = ProvenanceLogImpl()
    doc = Document(doc_id="doc-1", source_path="memo.txt", sha256="abc", page_count=1)
    chunk = Chunk(chunk_id="chunk-1", doc_id="doc-1", page=1, bbox=BBox(0,0,1,1), text="Dr. Margaret Chen")
    ext = Extraction(ext_id="ext-1", pack_id="wedge", field_name="author", value="Dr. Margaret Chen", chunk_id="chunk-1")
    action = Action(action_id="act-1", ext_id="ext-1", kind=ActionKind.SUGGEST, target_app="notepad", payload={"value": "Dr. Margaret Chen"})

    prov.register_document(doc)
    prov.register_chunk(chunk)
    prov.register_extraction(ext)
    prov.register_action(action)

    executor = ActionExecutorImpl(prov)
    res = executor.apply(action, human_confirm=True)
    assert res.success
    assert res.post_state is not None
    assert res.post_state["status"] == "verified"
    assert res.post_state["app"] == "notepad"
