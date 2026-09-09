/// Holds the streamed tokens and tracks word-by-word acceptance.
#[derive(Debug, Default)]
pub struct GhostBuffer {
    /// The full generated text (both alternatives)
    pub text_a: String,
    pub text_b: String,
    /// Which alternative is currently selected (false = A, true = B)
    pub using_b: bool,
    /// UTF-8 byte offset through the text the user has "word-accepted"
    pub accepted_chars: usize,
}

impl GhostBuffer {
    pub fn active_text(&self) -> &str {
        if self.using_b {
            &self.text_b
        } else {
            &self.text_a
        }
    }

    fn boundary(&self) -> usize {
        let text = self.active_text();
        let mut offset = self.accepted_chars.min(text.len());
        while !text.is_char_boundary(offset) {
            offset -= 1;
        }
        offset
    }

    pub fn accepted_text(&self) -> &str {
        let text = self.active_text();
        &text[..self.boundary()]
    }

    /// Accept the next word boundary
    pub fn accept_next_word(&mut self) {
        let text = self.active_text();
        let start = self.boundary();
        let remaining = &text[start..];
        // Find next word boundary (space after a non-space)
        let mut found = false;
        let mut i = 0;
        for (idx, ch) in remaining.char_indices() {
            if ch.is_whitespace() && found {
                i = idx + ch.len_utf8();
                break;
            }
            if !ch.is_whitespace() {
                found = true;
            }
            i = idx + ch.len_utf8();
        }
        self.accepted_chars = (start + i).min(text.len());
    }

    /// Un-accept the last word
    pub fn undo_last_word(&mut self) {
        let text = self.active_text();
        let accepted = text[..self.boundary()].trim_end_matches(char::is_whitespace);
        self.accepted_chars = accepted
            .char_indices()
            .rev()
            .find(|(_, ch)| ch.is_whitespace())
            .map(|(i, ch)| i + ch.len_utf8())
            .unwrap_or(0);
    }

    pub fn toggle_alternative(&mut self) {
        self.using_b = !self.using_b;
        // Reset word-by-word acceptance when switching
        self.accepted_chars = 0;
    }
}
