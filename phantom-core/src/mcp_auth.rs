// phantom-core/src/mcp_auth.rs
//! MCP Authorization and Enterprise SSO

use tracing::warn;

pub struct McpAuthorizer {
    pub sso_provider: String,
}

impl McpAuthorizer {
    pub fn new(sso_provider: &str) -> Self {
        Self {
            sso_provider: sso_provider.to_string(),
        }
    }

    pub fn authorize_tool_scoped_request(&self, agent_id: &str, tool: &str) -> bool {
        warn!(
            "MCP OAuth authorization is unavailable via {}; denying agent {} tool {}",
            self.sso_provider, agent_id, tool
        );
        false
    }
}
