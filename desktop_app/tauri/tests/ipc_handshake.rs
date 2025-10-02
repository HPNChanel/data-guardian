use std::time::Duration;

use data_guardian_desktop::bridge::{BridgeClient, Endpoint};
use data_guardian_desktop::process::ProcessConfig;
use data_guardian_desktop::runtime_paths::runtime_config_dir;

#[cfg(target_family = "unix")]
use tempfile::tempdir;

#[cfg(target_family = "unix")]
use tokio::net::UnixListener;

#[tokio::test]
async fn default_endpoints_are_local_only() {
    let config = ProcessConfig::default();
    match &config.socket_endpoint {
        Endpoint::Unix(path) => {
            let runtime_dir = runtime_config_dir().expect("runtime directory");
            let expected_parent = runtime_dir.join("ipc");
            assert!(
                path.starts_with(&expected_parent),
                "socket should live under the runtime ipc directory"
            );
        }
        Endpoint::NamedPipe(name) => {
            assert!(name.starts_with(r"\\.\\pipe\\"), "named pipe should live under the Windows local namespace");
        }
        Endpoint::Tcp(_) => panic!("tcp should not be the primary transport"),
    }

    #[cfg(not(feature = "debug-tcp-fallback"))]
    assert!(config.tcp_fallback.is_none(), "tcp fallback must be disabled by default");
}

#[cfg(target_family = "unix")]
#[tokio::test]
async fn unix_probe_completes_handshake() {
    let temp_dir = tempdir().expect("temporary directory");
    let socket_path = temp_dir.path().join("ipc.sock");
    let listener = UnixListener::bind(&socket_path).expect("bind socket");
    let accept_task = tokio::spawn(async move {
        let (_stream, _) = listener.accept().await.expect("client connection");
    });

    BridgeClient::probe_endpoint(&Endpoint::Unix(socket_path.clone()), Duration::from_millis(250))
        .await
        .expect("probe unix endpoint");

    accept_task.abort();
}
