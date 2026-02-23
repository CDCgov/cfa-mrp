use std::fs;
use std::path::Path;

use serde_json::Value;
use sha2::{Digest, Sha256};

use crate::environment::toml_to_json;

pub fn load_toml(path: &Path) -> Value {
    let contents = fs::read_to_string(path).expect("failed to read TOML file");
    let table: toml::Value = contents.parse().expect("failed to parse TOML");
    toml_to_json(table)
}

pub fn apply_overrides(config: &Value, overrides: &[&str]) -> Value {
    let mut config = config.clone();
    for item in overrides {
        let (key, value) = item
            .split_once('=')
            .unwrap_or_else(|| panic!("invalid override (missing '='): {item}"));

        let parts: Vec<&str> = key.trim().split('.').collect();
        let parsed = parse_value(value.trim());

        let mut target = &mut config;
        for part in &parts[..parts.len() - 1] {
            if !target.get(*part).is_some_and(|v| v.is_object()) {
                target[*part] = Value::Object(Default::default());
            }
            target = target.get_mut(*part).unwrap();
        }
        target[*parts.last().unwrap()] = parsed;
    }
    config
}

pub fn parse_value(s: &str) -> Value {
    match s.to_lowercase().as_str() {
        "true" => return Value::Bool(true),
        "false" => return Value::Bool(false),
        _ => {}
    }
    if let Ok(i) = s.parse::<i64>() {
        return Value::Number(serde_json::Number::from(i));
    }
    if let Ok(f) = s.parse::<f64>() {
        if let Some(n) = serde_json::Number::from_f64(f) {
            return Value::Number(n);
        }
    }
    Value::String(s.to_string())
}

pub fn resolve_input(config: &Value, base_dir: Option<&Path>) -> Value {
    let raw = config.get("input");
    let path_str = match raw.and_then(|v| v.as_str()) {
        Some(s) => s,
        None => return config.clone(),
    };

    let mut config = config.clone();
    let mut path = std::path::PathBuf::from(path_str);
    if let Some(base) = base_dir {
        if !path.is_absolute() {
            path = base.join(path);
        }
    }
    let contents = fs::read_to_string(&path).expect("failed to read input file");
    let input: Value = serde_json::from_str(&contents).expect("failed to parse input JSON");
    config["input"] = input;
    config
}

fn select_profile<'a>(section: &'a Value, profile_name: Option<&str>) -> &'a Value {
    let profiles = match section.get("profile").and_then(|v| v.as_object()) {
        Some(p) => p,
        None => return section,
    };

    if let Some(name) = profile_name {
        if let Some(prof) = profiles.get(name) {
            return prof;
        }
    }
    if let Some(def) = profiles.get("default") {
        return def;
    }
    profiles.values().next().unwrap_or(section)
}

pub fn build_run_json(config: &Value) -> Value {
    build_run_json_with_options(config, None, None, None)
}

pub fn build_run_json_with_options(
    config: &Value,
    staged_files: Option<&serde_json::Map<String, Value>>,
    output_dir: Option<&str>,
    output_profile: Option<&str>,
) -> Value {
    let mut result = config.clone();

    // Strip command/args from runtime
    if let Some(runtime) = result.get_mut("runtime") {
        if let Some(profiles) = runtime.get_mut("profile").and_then(|v| v.as_object_mut()) {
            for prof in profiles.values_mut() {
                if let Some(obj) = prof.as_object_mut() {
                    obj.remove("command");
                    obj.remove("args");
                }
            }
        } else if let Some(obj) = runtime.as_object_mut() {
            obj.remove("command");
            obj.remove("args");
        }
    }

    // Staged files override raw URIs
    if let Some(files) = staged_files {
        result
            .as_object_mut()
            .unwrap()
            .entry("model")
            .or_insert_with(|| Value::Object(Default::default()))
            .as_object_mut()
            .unwrap()
            .insert("files".to_string(), Value::Object(files.clone()));
    }

    // Default to stdout output
    if result.get("output").is_none() {
        result["output"] = serde_json::json!({"spec": "stdout"});
    }

    // Override filesystem output dir if requested
    if let Some(dir) = output_dir {
        let output = result.get("output").unwrap();
        let selected = select_profile(output, output_profile);
        if selected.get("spec").and_then(|v| v.as_str()) == Some("filesystem") {
            let output_mut = result.get_mut("output").unwrap();
            if output_mut
                .get("profile")
                .and_then(|v| v.as_object())
                .is_some()
            {
                let profiles = output_mut
                    .get_mut("profile")
                    .unwrap()
                    .as_object_mut()
                    .unwrap();
                // Determine target name without holding an immutable borrow
                let target_name = if let Some(p) = output_profile {
                    if profiles.contains_key(p) {
                        p.to_string()
                    } else if profiles.contains_key("default") {
                        "default".to_string()
                    } else {
                        profiles.keys().next().unwrap().clone()
                    }
                } else if profiles.contains_key("default") {
                    "default".to_string()
                } else {
                    profiles.keys().next().unwrap().clone()
                };
                profiles.get_mut(&target_name).unwrap().as_object_mut().unwrap()
                    .insert("dir".to_string(), Value::String(dir.to_string()));
            } else {
                output_mut["dir"] = Value::String(dir.to_string());
            }
        }
    }

    // Compute input_hash
    let canonical =
        serde_json::to_string(&result).expect("failed to serialize for hash");
    let mut hasher = Sha256::new();
    hasher.update(canonical.as_bytes());
    let hash = hasher.finalize();
    let input_hash = hex::encode(&hash[..8]);
    result["mrp"] = serde_json::json!({"version": "0.0.1", "input_hash": input_hash});

    result
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_value() {
        assert_eq!(parse_value("true"), Value::Bool(true));
        assert_eq!(parse_value("false"), Value::Bool(false));
        assert_eq!(parse_value("42"), Value::Number(42.into()));
        assert_eq!(parse_value("hello"), Value::String("hello".to_string()));
    }

    #[test]
    fn test_apply_overrides() {
        let config = serde_json::json!({"input": {"r0": 1.0}});
        let result = apply_overrides(&config, &["input.r0=2.5"]);
        assert_eq!(
            result.get("input").unwrap().get("r0").unwrap().as_f64().unwrap(),
            2.5
        );
    }

    #[test]
    fn test_build_run_json_strips_command() {
        let config = serde_json::json!({
            "runtime": {"spec": "process", "command": "my-model", "args": ["--flag"]},
            "input": {"r0": 2.0}
        });
        let result = build_run_json(&config);
        let runtime = result.get("runtime").unwrap();
        assert!(runtime.get("command").is_none());
        assert!(runtime.get("args").is_none());
        assert!(result.get("mrp").is_some());
    }

    #[test]
    fn test_build_run_json_default_output() {
        let config = serde_json::json!({"input": {"r0": 1.0}});
        let result = build_run_json(&config);
        assert_eq!(
            result.get("output").unwrap().get("spec").unwrap().as_str().unwrap(),
            "stdout"
        );
    }
}
