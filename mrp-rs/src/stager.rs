use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::Mutex;

use crate::MrpError;

static STAGE_DIR: Mutex<Option<PathBuf>> = Mutex::new(None);

fn get_stage_dir() -> PathBuf {
    let mut guard = STAGE_DIR.lock().unwrap();
    if let Some(ref dir) = *guard {
        return dir.clone();
    }
    let dir = std::env::temp_dir().join(format!("mrp_staged_{}", std::process::id()));
    fs::create_dir_all(&dir).expect("failed to create stage dir");
    *guard = Some(dir.clone());
    dir
}

pub fn stage_files(files: &HashMap<String, String>) -> Result<HashMap<String, String>, MrpError> {
    if files.is_empty() {
        return Ok(HashMap::new());
    }
    let mut staged = HashMap::new();
    for (name, uri) in files {
        staged.insert(name.clone(), stage_one(name, uri)?);
    }
    Ok(staged)
}

fn stage_one(name: &str, uri: &str) -> Result<String, MrpError> {
    // Local file
    if !uri.contains("://") || uri.starts_with("file://") {
        let path = if let Some(stripped) = uri.strip_prefix("file://") {
            stripped
        } else {
            uri
        };
        if !Path::new(path).exists() {
            return Err(MrpError::FileNotFound(format!(
                "file not found for '{name}': {path}"
            )));
        }
        return Ok(path.to_string());
    }

    // HTTP(S) — download to stage dir
    if uri.starts_with("http://") || uri.starts_with("https://") {
        let dest_dir = get_stage_dir().join(name);
        fs::create_dir_all(&dest_dir)
            .map_err(|e| MrpError::Staging(format!("failed to create stage subdir: {e}")))?;
        let filename = uri
            .rsplit('/')
            .next()
            .unwrap_or("download");
        let dest = dest_dir.join(filename);
        let resp = ureq::get(uri)
            .call()
            .map_err(|e| MrpError::Staging(format!("HTTP download failed for '{name}': {e}")))?;
        let mut reader = resp.into_body().into_reader();
        let mut file = fs::File::create(&dest)
            .map_err(|e| MrpError::Staging(format!("failed to create staged file: {e}")))?;
        std::io::copy(&mut reader, &mut file)
            .map_err(|e| MrpError::Staging(format!("failed to write staged file: {e}")))?;
        return Ok(dest.to_string_lossy().to_string());
    }

    Err(MrpError::Config(format!(
        "unsupported URI scheme for '{name}': {uri}"
    )))
}

pub fn cleanup() {
    let mut guard = STAGE_DIR.lock().unwrap();
    if let Some(ref dir) = *guard {
        let _ = fs::remove_dir_all(dir);
    }
    *guard = None;
}
