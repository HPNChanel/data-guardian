use anyhow::Result;
use desktop_app::controller::Controller;
use dg_core::api::new_default;
use serde_json::json;
use tempfile::tempdir;
use tokio::fs;

#[tokio::test]
async fn happy_path_encrypt_decrypt_shutdown() -> Result<()> {
    let temp = tempdir()?;
    let data_dir = temp.path().join("guardian");
    fs::create_dir_all(&data_dir).await?;
    let controller = Controller::new(new_default());
    controller.boot("dev", data_dir.clone(), false).await?;

    let subject = "local-user";
    assert!(
        controller
            .check_access(subject, "encrypt", "resource")
            .await?
    );

    let original = temp.path().join("note.txt");
    fs::write(&original, b"temporary secret").await?;
    let env_path = controller
        .encrypt_file(
            &original,
            vec!["user:a".into()],
            vec!["confidential".into()],
        )
        .await?;
    let decrypted = controller.decrypt_file(&env_path).await?;
    let decrypted_bytes = fs::read(&decrypted).await?;
    assert_eq!(decrypted_bytes, b"temporary secret");

    controller.shutdown().await?;
    Ok(())
}

#[tokio::test]
async fn policy_denies_flow() -> Result<()> {
    let temp = tempdir()?;
    let data_dir = temp.path().join("guardian");
    fs::create_dir_all(&data_dir).await?;
    let policy = json!({
        "default_allow": false,
        "rules": [
            {"subject": "local-user", "action": "decrypt", "resource": "*", "effect": "allow"}
        ]
    });
    fs::write(
        data_dir.join("policy.json"),
        serde_json::to_vec_pretty(&policy)?,
    )
    .await?;

    let controller = Controller::new(new_default());
    controller.boot("dev", data_dir.clone(), false).await?;

    let file = temp.path().join("classified.bin");
    fs::write(&file, b"payload").await?;
    let result = controller
        .encrypt_file(&file, vec!["user:b".into()], vec!["secret".into()])
        .await;
    assert!(result.is_err(), "encryption should be denied");

    controller.shutdown().await?;
    Ok(())
}

#[tokio::test]
async fn corrupt_envelope_fails_to_decrypt() -> Result<()> {
    let temp = tempdir()?;
    let data_dir = temp.path().join("guardian");
    fs::create_dir_all(&data_dir).await?;
    let controller = Controller::new(new_default());
    controller.boot("dev", data_dir.clone(), false).await?;

    let original = temp.path().join("text.txt");
    fs::write(&original, b"original").await?;
    let env_path = controller
        .encrypt_file(&original, vec!["user:c".into()], vec!["internal".into()])
        .await?;

    let mut envelope = serde_json::from_slice::<serde_json::Value>(&fs::read(&env_path).await?)?;
    envelope["payload"] = serde_json::Value::String("!!not-base64!!".into());
    fs::write(&env_path, serde_json::to_vec(&envelope)?).await?;

    let result = controller.decrypt_file(&env_path).await;
    assert!(result.is_err(), "corrupt envelope should fail");

    controller.shutdown().await?;
    Ok(())
}
