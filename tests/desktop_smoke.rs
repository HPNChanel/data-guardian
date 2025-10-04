use desktop_app::controller::Controller;
use dg_core::api::new_default;
use tempfile::tempdir;
use tokio::fs;

#[tokio::test]
async fn desktop_controller_smoke() {
    let temp = tempdir().expect("tempdir");
    let data_dir = temp.path().join("desktop-data");
    fs::create_dir_all(&data_dir)
        .await
        .expect("create data dir");
    let controller = Controller::new(new_default());
    controller
        .boot("dev", data_dir.clone(), false)
        .await
        .expect("boot controller");

    let file = temp.path().join("hello.txt");
    fs::write(&file, b"hello world").await.expect("write file");

    let encrypted = controller
        .encrypt_file(&file, vec!["user:smoke".into()], vec!["public".into()])
        .await
        .expect("encrypt file");
    let decrypted = controller
        .decrypt_file(&encrypted)
        .await
        .expect("decrypt file");
    let decrypted_bytes = fs::read(&decrypted).await.expect("read decrypted");
    assert_eq!(decrypted_bytes, b"hello world");

    controller.shutdown().await.expect("shutdown");
}
