use anyhow::Result;
use desktop_app::controller::Controller;
use dg_core::api::new_default;
use tempfile::tempdir;
use tokio::fs;

#[tokio::test]
async fn controller_round_trip_encrypt_decrypt() -> Result<()> {
    let temp = tempdir()?;
    let data_dir = temp.path().join("data");
    fs::create_dir_all(&data_dir).await?;
    let controller = Controller::new(new_default());
    controller
        .boot("dev", data_dir.clone(), false)
        .await
        .expect("boot controller");

    let source = temp.path().join("message.txt");
    fs::write(&source, b"classified payload").await?;

    let envelope_path = controller
        .encrypt_file(&source, vec!["alpha".into()], vec!["confidential".into()])
        .await?;
    assert!(envelope_path.exists());

    let recovered_path = controller.decrypt_file(&envelope_path).await?;
    let contents = fs::read(&recovered_path).await?;
    assert_eq!(contents, b"classified payload");

    controller.shutdown().await?;
    Ok(())
}
