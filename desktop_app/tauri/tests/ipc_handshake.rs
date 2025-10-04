use anyhow::Result;
use desktop_app::controller::Controller;
use dg_core::api::new_default;
use serde_json::json;
use tempfile::tempdir;
use tokio::fs;

#[tokio::test]
async fn policy_denies_encryption_when_rule_matches() -> Result<()> {
    let temp = tempdir()?;
    let data_dir = temp.path().join("core");
    fs::create_dir_all(&data_dir).await?;
    let policy = json!({
        "default_allow": true,
        "rules": [
            {
                "subject": "local-user",
                "action": "encrypt",
                "resource": "*",
                "effect": "deny"
            }
        ]
    });
    fs::write(data_dir.join("policy.json"), serde_json::to_vec_pretty(&policy)?).await?;

    let controller = Controller::new(new_default());
    controller.boot("dev", data_dir.clone(), false).await?;

    let source = temp.path().join("blocked.txt");
    fs::write(&source, b"blocked").await?;

    let result = controller
        .encrypt_file(&source, vec!["beta".into()], vec!["internal".into()])
        .await;
    assert!(result.is_err(), "policy should block encryption");

    controller.shutdown().await?;
    Ok(())
}
