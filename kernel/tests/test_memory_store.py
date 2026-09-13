"""
Kairo Phantom — MemoryStore unit tests for Entity, ModelVersion, User, and Action nodes.
"""


from kernel.core.data_model import (
    Action,
    ActionKind,
    ActionStatus,
    Entity,
    ModelVersion,
    User,
    Document,
    Chunk,
    Extraction,
    BBox
)
from kernel.sidecar.memory_store import MemoryStoreImpl


def test_entity_ops():
    """Test upsert and get operations for Entity node."""
    store = MemoryStoreImpl(":memory:")
    entity = Entity(
        entity_id="entity-1",
        kind="person",
        value="Margaret Chen",
        normalized="Margaret Chen",
    )
    store.upsert_entity(entity)
    retrieved = store.get_entity("entity-1")
    assert retrieved is not None
    assert retrieved.entity_id == "entity-1"
    assert retrieved.kind == "person"
    assert retrieved.value == "Margaret Chen"
    assert retrieved.normalized == "Margaret Chen"

    # Test non-existent
    assert store.get_entity("non-existent") is None


def test_model_version_ops():
    """Test upsert and get operations for ModelVersion node."""
    store = MemoryStoreImpl(":memory:")
    mv = ModelVersion(
        model_id="mv-1",
        name="llama3-8b-local",
        weights_hash="hash-1234",
        tier=1,
    )
    store.upsert_model_version(mv)
    retrieved = store.get_model_version("mv-1")
    assert retrieved is not None
    assert retrieved.model_id == "mv-1"
    assert retrieved.name == "llama3-8b-local"
    assert retrieved.weights_hash == "hash-1234"
    assert retrieved.tier == 1

    # Test non-existent
    assert store.get_model_version("non-existent") is None


def test_user_ops():
    """Test upsert and get operations for User node."""
    store = MemoryStoreImpl(":memory:")
    user = User(user_id="user-1")
    store.upsert_user(user)
    retrieved = store.get_user("user-1")
    assert retrieved is not None
    assert retrieved.user_id == "user-1"

    # Test non-existent
    assert store.get_user("non-existent") is None


def test_action_ops():
    """Test upsert and get operations for Action node."""
    store = MemoryStoreImpl(":memory:")
    
    # Needs Document, Chunk, and Extraction for Action.ext_id foreign key constraint
    doc = Document(doc_id="doc-1", source_path="memo.txt", sha256="abc")
    chunk = Chunk(chunk_id="chunk-1", doc_id="doc-1", page=1, bbox=BBox(0, 0, 1, 1), text="text")
    ext = Extraction(ext_id="ext-1", pack_id="wedge", field_name="author", value="val", chunk_id="chunk-1")
    
    store.upsert_document(doc)
    store.upsert_chunk(chunk)
    store.record_extraction(ext)

    action = Action(
        action_id="act-1",
        ext_id="ext-1",
        kind=ActionKind.SUGGEST,
        target_app="notepad",
        payload={"value": "Dr. Margaret Chen"},
        confidence=0.9,
        status=ActionStatus.PENDING,
    )
    store.upsert_action(action)
    retrieved = store.get_action("act-1")
    assert retrieved is not None
    assert retrieved.action_id == "act-1"
    assert retrieved.ext_id == "ext-1"
    assert retrieved.kind == ActionKind.SUGGEST
    assert retrieved.target_app == "notepad"
    assert retrieved.payload == {"value": "Dr. Margaret Chen"}
    assert retrieved.confidence == 0.9
    assert retrieved.status == ActionStatus.PENDING

    # Test non-existent
    assert store.get_action("non-existent") is None


def test_stats_property():
    """Test stats counts all nodes including new ones."""
    store = MemoryStoreImpl(":memory:")
    assert store.stats["entities"] == 0
    assert store.stats["model_versions"] == 0
    assert store.stats["users"] == 0
    assert store.stats["actions"] == 0

    entity = Entity(entity_id="entity-1", kind="person", value="A", normalized="A")
    store.upsert_entity(entity)
    assert store.stats["entities"] == 1

    mv = ModelVersion(model_id="mv-1", name="B", weights_hash="C", tier=1)
    store.upsert_model_version(mv)
    assert store.stats["model_versions"] == 1

    user = User(user_id="user-1")
    store.upsert_user(user)
    assert store.stats["users"] == 1

    # Check that doc, chunk, ext are stored before action
    doc = Document(doc_id="doc-1", source_path="memo.txt", sha256="abc")
    chunk = Chunk(chunk_id="chunk-1", doc_id="doc-1", page=1, bbox=BBox(0, 0, 1, 1), text="text")
    ext = Extraction(ext_id="ext-1", pack_id="wedge", field_name="author", value="val", chunk_id="chunk-1")
    store.upsert_document(doc)
    store.upsert_chunk(chunk)
    store.record_extraction(ext)

    action = Action(action_id="act-1", ext_id="ext-1", kind=ActionKind.SUGGEST, target_app="notepad", payload={})
    store.upsert_action(action)
    assert store.stats["actions"] == 1
