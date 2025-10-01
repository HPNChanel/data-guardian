use std::fmt;
use std::net::{SocketAddr, ToSocketAddrs};
use std::path::{Path, PathBuf};

use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum TransportKind {
    Auto,
    Unix,
    NamedPipe,
    Tcp,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Endpoint {
    Unix(PathBuf),
    NamedPipe(String),
    Tcp(SocketAddr),
}

impl Endpoint {
    pub fn kind(&self) -> TransportKind {
        match self {
            Endpoint::Unix(_) => TransportKind::Unix,
            Endpoint::NamedPipe(_) => TransportKind::NamedPipe,
            Endpoint::Tcp(_) => TransportKind::Tcp,
        }
    }

    pub fn display(&self) -> String {
        match self {
            Endpoint::Unix(path) => path.display().to_string(),
            Endpoint::NamedPipe(name) => name.clone(),
            Endpoint::Tcp(addr) => addr.to_string(),
        }
    }

    pub fn from_user_input(kind: TransportKind, value: &str) -> Result<Self> {
        match kind {
            TransportKind::Unix => Ok(Endpoint::Unix(Path::new(value).to_path_buf())),
            TransportKind::NamedPipe => Ok(Endpoint::NamedPipe(value.to_string())),
            TransportKind::Tcp => {
                let mut addrs = value
                    .to_socket_addrs()
                    .with_context(|| format!("invalid tcp endpoint '{value}'"))?;
                addrs
                    .next()
                    .map(Endpoint::Tcp)
                    .context("tcp endpoint resolved to no addresses")
            }
            TransportKind::Auto => anyhow::bail!("cannot derive endpoint for auto transport"),
        }
    }
}

impl fmt::Display for Endpoint {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.display())
    }
}
