//! Local memory merge primitives.
//!
//! The former LAN transport disclosed and accepted memory without authenticated,
//! encrypted peer pairing. Network entry points now fail closed until a reviewed
//! protocol provides identity, authorization, AEAD, replay protection, rotation,
//! and bounded resource use.

use anyhow::Result;
use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};

pub const LAN_SYNC_DISABLED_REASON: &str =
    "LAN sync is disabled: authenticated, encrypted peer pairing is not implemented";

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LanPeer {
    pub addr: String,
    pub hostname: String,
    pub vault_entries: u64,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct SyncEntry {
    pub id: String,
    pub content: String,
    pub app_context: String,
    pub context_key: String,
    pub tags: String,
    pub timestamp: i64,
    pub is_ground_truth: bool,
}

pub struct LanSync {
    db_path: PathBuf,
}

impl LanSync {
    pub fn new(vault_dir: &Path) -> Self {
        Self {
            db_path: vault_dir.join("mem_machine.db"),
        }
    }

    /// Fail closed until authenticated, encrypted pairing exists.
    pub fn discover_peers(&self, _timeout_ms: u64) -> Result<Vec<LanPeer>> {
        network_sync_disabled()
    }

    /// Fail closed without binding a listener.
    pub fn start_server(&self) -> Result<()> {
        network_sync_disabled()
    }

    /// Fail closed before parsing or connecting to an untrusted address.
    pub fn pull_from_peer(&self, _peer_addr: &str) -> Result<usize> {
        network_sync_disabled()
    }

    fn count_entries(&self) -> Result<u64> {
        if !self.db_path.exists() {
            return Ok(0);
        }
        let conn = rusqlite::Connection::open(&self.db_path)?;
        let n = conn
            .query_row("SELECT COUNT(*) FROM semantic_memory", [], |r| {
                r.get::<_, i64>(0)
            })
            .unwrap_or(0);
        Ok(n as u64)
    }

    fn merge_entries(&self, entries: &[SyncEntry]) -> Result<usize> {
        if entries.is_empty() {
            return Ok(0);
        }
        std::fs::create_dir_all(self.db_path.parent().unwrap_or(std::path::Path::new(".")))?;
        let conn = rusqlite::Connection::open(&self.db_path)?;
        conn.execute_batch(
            "CREATE TABLE IF NOT EXISTS semantic_memory (
               id TEXT PRIMARY KEY, timestamp INTEGER, content TEXT, full_episode TEXT,
               embedding BLOB, app_context TEXT, context_key TEXT,
               is_ground_truth INTEGER DEFAULT 0,
               storage_strength REAL DEFAULT 1.0, retrieval_strength REAL DEFAULT 1.0,
               tags TEXT)",
        )?;
        let mut merged = 0;
        for e in entries {
            let affected = conn.execute(
                "INSERT OR IGNORE INTO semantic_memory \
                 (id, timestamp, content, full_episode, app_context, context_key, is_ground_truth, tags) \
                 VALUES (?1, ?2, ?3, '', ?4, ?5, ?6, ?7)",
                rusqlite::params![e.id, e.timestamp, e.content, e.app_context,
                    e.context_key, if e.is_ground_truth { 1 } else { 0 }, e.tags])?;
            merged += affected;
        }
        Ok(merged)
    }
}

fn network_sync_disabled<T>() -> Result<T> {
    Err(anyhow::anyhow!(LAN_SYNC_DISABLED_REASON))
}

pub async fn run_lan_sync_command(args: &[String]) -> Result<()> {
    let vault = dirs::home_dir().unwrap_or_default().join(".kairo-phantom");
    let sync = LanSync::new(&vault);

    let subcmd = args.first().map(|s| s.as_str()).unwrap_or("discover");
    match subcmd {
        "discover" => {
            let peers = sync.discover_peers(3000)?;
            if peers.is_empty() {
                println!("  No peers found.");
            }
            for p in &peers {
                println!(
                    "  ✅ {} — {} ({} entries)",
                    p.hostname, p.addr, p.vault_entries
                );
            }
        }
        "pull" => {
            let peer = args.get(1).map(String::as_str).unwrap_or("");
            if peer.is_empty() {
                println!("Usage: kairo memory sync pull <ip:port>");
                return Ok(());
            }
            let n = sync.pull_from_peer(peer)?;
            println!("✅ Merged {n} new preference entries from {peer}");
        }
        "serve" => {
            sync.start_server()?;
        }
        _ => println!("Usage: kairo memory sync <discover|pull <peer>|serve>"),
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[test]
    fn test_new_empty_vault() {
        let d = tempdir().unwrap();
        let sync = LanSync::new(d.path());
        assert_eq!(sync.count_entries().unwrap(), 0);
    }

    #[test]
    fn test_merge_empty() {
        let d = tempdir().unwrap();
        let sync = LanSync {
            db_path: d.path().join("mem_machine.db"),
        };
        let merged = sync.merge_entries(&[]).unwrap();
        assert_eq!(merged, 0);
    }

    #[test]
    fn test_merge_entries() {
        let d = tempdir().unwrap();
        let sync = LanSync {
            db_path: d.path().join("mem_machine.db"),
        };
        let entries = vec![SyncEntry {
            id: "test-id-001".into(),
            content: "Prefer bullets".into(),
            app_context: "Word".into(),
            context_key: "format".into(),
            tags: "lan,test".into(),
            timestamp: 1700000000,
            is_ground_truth: true,
        }];
        let merged = sync.merge_entries(&entries).unwrap();
        assert_eq!(merged, 1, "Should merge 1 entry");
        // Merge again — no duplicate
        let merged2 = sync.merge_entries(&entries).unwrap();
        assert_eq!(merged2, 0, "Duplicate should be ignored");
    }
}
