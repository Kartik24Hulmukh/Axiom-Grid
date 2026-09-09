use axiom_grid::{
    crdt::CrdtSession,
    ghost_buffer::GhostBuffer,
    ghost_session::{ConfidenceBand, GhostSession, SessionState},
    ollama_bootstrap::{download_allowed, model_matches},
};
#[test]
fn unicode_boundaries_and_undo() {
    let mut b = GhostBuffer {
        text_a: "你好 世界 🌍".into(),
        ..Default::default()
    };
    b.accept_next_word();
    assert_eq!(b.accepted_text(), "你好 ");
    b.accept_next_word();
    assert_eq!(b.accepted_text(), "你好 世界 ");
    b.undo_last_word();
    assert_eq!(b.accepted_text(), "你好 ");
    b.undo_last_word();
    assert_eq!(b.accepted_text(), "");
}
#[test]
fn every_external_offset_is_safe() {
    let mut b = GhostBuffer {
        text_a: "é🙂中\tword\nend".into(),
        ..Default::default()
    };
    for offset in 0..40 {
        b.accepted_chars = offset;
        let _ = b.accepted_text();
        b.accept_next_word();
        b.undo_last_word();
    }
}
#[test]
fn whitespace_and_alternative_reset() {
    let mut b = GhostBuffer {
        text_a: "one\ttwo\nthree".into(),
        text_b: "另一个".into(),
        ..Default::default()
    };
    b.accept_next_word();
    assert_eq!(b.accepted_text(), "one\t");
    b.accept_next_word();
    assert_eq!(b.accepted_text(), "one\ttwo\n");
    b.toggle_alternative();
    assert_eq!(b.accepted_text(), "");
    b.accept_next_word();
    assert_eq!(b.accepted_text(), "另一个");
}
#[tokio::test]
async fn acceptance_is_async_and_review_gated() {
    let mut s = GhostSession::new("Write a useful clear reply", 0, ConfidenceBand::High);
    s.push_token_a("Hello 🌍").await;
    assert!(s.accept_all().await.is_err());
    s.finish_stream();
    assert!(s.status_line().await.contains("HIGH"));
    assert_eq!(s.accept_all().await.unwrap(), "Hello 🌍");
    assert_eq!(s.state, SessionState::Accepted);
    assert!(s.accept_all().await.is_err());
}
#[tokio::test]
async fn cancellation_is_terminal_and_drops_late_tokens() {
    let mut s = GhostSession::new("prompt", 0, ConfidenceBand::High);
    s.push_token_a("before").await;
    s.cancel();
    s.push_token_a("late").await;
    s.push_token_b("late").await;
    s.finish_stream();
    assert_eq!(s.state, SessionState::Cancelled);
    assert!(s.accept_all().await.is_err());
    let b = s.buffer.lock().await;
    assert_eq!(b.text_a, "before");
    assert!(b.text_b.is_empty());
}
#[tokio::test]
async fn empty_and_low_confidence_are_not_accepted() {
    let mut s = GhostSession::new("prompt", 0, ConfidenceBand::High);
    s.finish_stream();
    assert!(s.accept_all().await.is_err());
    s.push_token_a("text").await;
    s.confidence = ConfidenceBand::Low;
    assert!(s.accept_all().await.is_err());
}
#[test]
fn model_identity_is_not_a_prefix() {
    assert!(model_matches("model", "model:latest"));
    assert!(model_matches("model:7b", "model:7b"));
    assert!(!model_matches("model:7b", "model:7b-instruct"));
    assert!(!model_matches("model", "model:27b"));
    assert!(!model_matches("", ""));
}
#[test]
fn download_policy_is_explicit_and_offline_wins() {
    for offline in [None, Some("0"), Some("1")] {
        for consent in [None, Some("0"), Some("1")] {
            assert_eq!(
                download_allowed(offline, consent),
                offline != Some("1") && consent == Some("1")
            );
        }
    }
}
#[test]
fn crdt_unicode_replacement_uses_document_offsets() {
    let c = CrdtSession::new(1);
    for text in ["你好 🌍", "é", "", "replacement", "🙂🙂"] {
        c.insert_human_text(text);
        c.insert_ai_text(text);
        assert_eq!(c.get_human_text(), text);
    }
}
