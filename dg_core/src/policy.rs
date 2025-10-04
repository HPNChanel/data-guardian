use std::sync::Arc;

use globset::{Glob, GlobMatcher};
use serde::{Deserialize, Serialize};
use tokio::sync::RwLock;

#[derive(Clone)]
pub struct PolicyEngine {
    inner: ArcPolicy,
}

type ArcPolicy = Arc<RwLock<CompiledPolicy>>;

#[derive(Default)]
struct CompiledPolicy {
    rules: Vec<CompiledRule>,
    default_allow: bool,
}

#[derive(Clone)]
struct CompiledRule {
    subject: GlobMatcher,
    action: GlobMatcher,
    resource: GlobMatcher,
    effect: PolicyEffect,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct PolicyDocument {
    #[serde(default = "default_allow_true")]
    default_allow: bool,
    #[serde(default)]
    rules: Vec<PolicyRule>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct PolicyRule {
    subject: String,
    action: String,
    resource: String,
    #[serde(default)]
    effect: PolicyEffect,
}

#[derive(Debug, Clone, Serialize, Deserialize, Copy, PartialEq, Eq, Default)]
#[serde(rename_all = "lowercase")]
enum PolicyEffect {
    #[default]
    Allow,
    Deny,
}

fn default_allow_true() -> bool {
    true
}

impl PolicyEngine {
    pub async fn from_bytes(bytes: Vec<u8>) -> Result<Self, String> {
        let document: PolicyDocument = serde_json::from_slice(&bytes)
            .map_err(|err| format!("invalid policy format: {err}"))?;
        Self::from_document(document).await
    }

    pub async fn default() -> Result<Self, String> {
        Self::from_document(PolicyDocument {
            default_allow: true,
            rules: vec![],
        })
        .await
    }

    async fn from_document(doc: PolicyDocument) -> Result<Self, String> {
        let mut compiled = CompiledPolicy {
            rules: Vec::new(),
            default_allow: doc.default_allow,
        };

        for rule in doc.rules {
            let subject = Glob::new(&rule.subject)
                .map_err(|err| format!("invalid subject glob: {err}"))?
                .compile_matcher();
            let action = Glob::new(&rule.action)
                .map_err(|err| format!("invalid action glob: {err}"))?
                .compile_matcher();
            let resource = Glob::new(&rule.resource)
                .map_err(|err| format!("invalid resource glob: {err}"))?
                .compile_matcher();
            compiled.rules.push(CompiledRule {
                subject,
                action,
                resource,
                effect: rule.effect,
            });
        }

        Ok(Self {
            inner: std::sync::Arc::new(RwLock::new(compiled)),
        })
    }

    pub async fn evaluate(
        &self,
        subject: &str,
        action: &str,
        resource: &str,
    ) -> Result<bool, String> {
        let guard = self.inner.read().await;
        for rule in &guard.rules {
            if rule.subject.is_match(subject)
                && rule.action.is_match(action)
                && rule.resource.is_match(resource)
            {
                return Ok(rule.effect == PolicyEffect::Allow);
            }
        }

        Ok(guard.default_allow)
    }
}
