use dg_core::api::{new_default, DGConfig, EncryptRequest};
use tempfile::tempdir;

#[tokio::test]
async fn policy_default_allows_encryption() {
    let temp = tempdir().expect("tempdir");
    let data_dir = temp.path().to_path_buf();
    let engine = new_default();
    engine
        .init(DGConfig {
            profile: "dev".into(),
            data_dir: data_dir.clone(),
            telemetry: false,
        })
        .await
        .expect("init");

    let envelope = engine
        .encrypt(EncryptRequest {
            plaintext: b"hello".to_vec(),
            labels: vec!["test".into()],
            recipients: vec!["user".into()],
        })
        .await
        .expect("encrypt");
    let decrypted = engine.decrypt(envelope).await.expect("decrypt");
    assert_eq!(decrypted, b"hello");

    engine.shutdown().await.expect("shutdown");
}
