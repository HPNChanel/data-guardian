use std::{fs, path::Path};

fn main() {
    if let Err(err) = ensure_icon() {
        panic!("failed to prepare Tauri icon: {err}");
    }

    tauri_build::build()
}

fn ensure_icon() -> Result<(), Box<dyn std::error::Error>> {
    const ICON_BASE64: &str = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGMAAQAABQABDQottAAAAABJRU5ErkJggg==";

    let icon_dir = Path::new("icons");
    if !icon_dir.exists() {
        fs::create_dir_all(icon_dir)?;
    }

    let icon_path = icon_dir.join("icon.png");
    if icon_path.exists() {
        return Ok(());
    }

    let icon_bytes = base64::decode(ICON_BASE64)?;
    fs::write(icon_path, icon_bytes)?;
    Ok(())
}
