use std::time::Duration;

use anyhow::Result;
use data_guardian_desktop::bridge::{BridgeClient, BridgeConfig, Endpoint, RpcRequest};
use serde_json::json;
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::net::{TcpListener, TcpStream};

#[tokio::test]
async fn bridge_round_trip_tcp() -> Result<()> {
    let listener = TcpListener::bind("127.0.0.1:0").await?;
    let address = listener.local_addr()?;

    tokio::spawn(async move {
        if let Ok((stream, _)) = listener.accept().await {
            handle_connection(stream).await.unwrap();
        }
    });

    let config = BridgeConfig::new(vec![Endpoint::Tcp(address)]).with_timeout(Duration::from_millis(500));
    let client = BridgeClient::connect(config).await?;

    let request = RpcRequest {
        id: "test".into(),
        method: "echo".into(),
        params: Some(json!({ "payload": "ping" })),
    };

    let response = client.send_request(request).await?;
    let payload = response.result.expect("result expected");
    assert_eq!(payload["method"], "echo");
    assert_eq!(payload["params"]["payload"], "ping");

    Ok(())
}

async fn handle_connection(stream: TcpStream) -> Result<()> {
    let (reader, mut writer) = stream.into_split();
    let mut reader = BufReader::new(reader);
    let mut line = Vec::new();

    while reader.read_until(b'\n', &mut line).await? != 0 {
        let request: serde_json::Value = serde_json::from_slice(&line)?;
        line.clear();

        let response = json!({
            "jsonrpc": "2.0",
            "id": request["id"].clone(),
            "result": {
                "method": request["method"].clone(),
                "params": request["params"].clone()
            }
        });

        let mut bytes = serde_json::to_vec(&response)?;
        bytes.push(b'\n');
        writer.write_all(&bytes).await?;
        writer.flush().await?;
    }

    Ok(())
}
