use std::collections::HashMap;
use std::fs;
use std::io::{self, Read, Write};
use std::path::PathBuf;

use serde::de::DeserializeOwned;
use serde_json::Value;

pub struct Environment<I = ()> {
    input_json: serde_json::Map<String, Value>,
    pub input: Option<I>,
    pub seed: u64,
    pub replicate: u64,
    pub files: HashMap<String, PathBuf>,
    output: Value,
}

impl Environment {
    pub fn from_json(data: Value) -> Self {
        let mut input_json = data
            .get("input")
            .and_then(|v| v.as_object())
            .cloned()
            .unwrap_or_default();

        let seed = input_json
            .remove("seed")
            .and_then(|v| v.as_u64())
            .unwrap_or(0);

        let replicate = input_json
            .remove("replicate")
            .and_then(|v| v.as_u64())
            .unwrap_or(0);

        let files = data
            .get("model")
            .and_then(|m| m.get("files"))
            .and_then(|f| f.as_object())
            .map(|obj| {
                obj.iter()
                    .filter_map(|(k, v)| v.as_str().map(|s| (k.clone(), PathBuf::from(s))))
                    .collect()
            })
            .unwrap_or_default();

        let output = data.get("output").cloned().unwrap_or(Value::Null);

        Self {
            input_json,
            input: None,
            seed,
            replicate,
            files,
            output,
        }
    }

    pub fn from_stdin() -> Self {
        let mut raw = String::new();
        io::stdin()
            .read_to_string(&mut raw)
            .expect("failed to read stdin");
        if raw.trim().is_empty() {
            eprintln!("Error: no input on stdin");
            std::process::exit(1);
        }
        let data: Value = serde_json::from_str(&raw).expect("failed to parse JSON from stdin");
        Self::from_json(data)
    }

    pub fn with_input_type<I: DeserializeOwned>(self) -> Environment<I> {
        let input_value = Value::Object(self.input_json.clone());
        let input = serde_json::from_value(input_value).expect("failed to deserialize input");
        Environment {
            input_json: self.input_json,
            input: Some(input),
            seed: self.seed,
            replicate: self.replicate,
            files: self.files,
            output: self.output,
        }
    }
}

impl<I: DeserializeOwned> Environment<I> {
    pub fn load() -> Self {
        Environment::from_stdin().with_input_type::<I>()
    }
}

impl<I> Environment<I> {
    pub fn input_json(&self) -> &serde_json::Map<String, Value> {
        &self.input_json
    }

    pub fn output_dir(&self) -> Option<PathBuf> {
        let output = &self.output;

        // Check flat output
        if output.get("spec").and_then(|v| v.as_str()) == Some("filesystem") {
            if let Some(dir) = output.get("dir").and_then(|v| v.as_str()) {
                return Some(PathBuf::from(dir));
            }
            return None;
        }

        // Check profiled output — resolve default profile
        if let Some(profiles) = output.get("profile").and_then(|v| v.as_object()) {
            let selected = profiles
                .get("default")
                .or_else(|| profiles.values().next());
            if let Some(profile) = selected {
                if profile.get("spec").and_then(|v| v.as_str()) == Some("filesystem") {
                    if let Some(dir) = profile.get("dir").and_then(|v| v.as_str()) {
                        return Some(PathBuf::from(dir));
                    }
                }
            }
        }

        None
    }

    pub fn write(&self, filename: &str, data: &[u8]) {
        if let Some(dir) = self.output_dir() {
            fs::create_dir_all(&dir).expect("failed to create output directory");
            fs::write(dir.join(filename), data).expect("failed to write output file");
        } else {
            io::stdout()
                .write_all(data)
                .expect("failed to write to stdout");
        }
    }

    pub fn write_csv(&self, filename: &str, headers: &[&str], rows: &[Vec<String>]) {
        if let Some(dir) = self.output_dir() {
            fs::create_dir_all(&dir).expect("failed to create output directory");
            let file =
                fs::File::create(dir.join(filename)).expect("failed to create output file");
            let mut wtr = csv::Writer::from_writer(file);
            wtr.write_record(headers).unwrap();
            for row in rows {
                wtr.write_record(row).unwrap();
            }
            wtr.flush().unwrap();
        } else {
            let mut wtr = csv::Writer::from_writer(io::stdout());
            wtr.write_record(headers).unwrap();
            for row in rows {
                wtr.write_record(row).unwrap();
            }
            wtr.flush().unwrap();
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde::Deserialize;
    use serde_json::json;

    #[test]
    fn test_from_json_basic() {
        let data = json!({
            "input": {
                "seed": 42,
                "replicate": 1,
                "r0": 2.0
            },
            "model": {
                "files": {
                    "data": "/tmp/data.csv"
                }
            },
            "output": {
                "spec": "filesystem",
                "dir": "/tmp/output"
            }
        });
        let ctx = Environment::from_json(data);
        assert_eq!(ctx.seed, 42);
        assert_eq!(ctx.replicate, 1);
        assert_eq!(ctx.input_json().get("r0").unwrap().as_f64().unwrap(), 2.0);
        assert!(!ctx.input_json().contains_key("seed"));
        assert!(!ctx.input_json().contains_key("replicate"));
        assert_eq!(ctx.files.get("data").unwrap(), &PathBuf::from("/tmp/data.csv"));
        assert_eq!(ctx.output_dir(), Some(PathBuf::from("/tmp/output")));
    }

    #[test]
    fn test_with_input_type() {
        #[derive(Deserialize, Debug, PartialEq)]
        struct Params {
            r0: f64,
        }
        let data = json!({
            "input": {
                "seed": 42,
                "r0": 2.5
            }
        });
        let ctx = Environment::from_json(data).with_input_type::<Params>();
        assert_eq!(ctx.input, Some(Params { r0: 2.5 }));
        assert_eq!(ctx.seed, 42);
    }

    #[test]
    fn test_output_dir_profiled() {
        let data = json!({
            "input": {},
            "output": {
                "profile": {
                    "default": {
                        "spec": "filesystem",
                        "dir": "/tmp/profiled"
                    }
                }
            }
        });
        let ctx = Environment::from_json(data);
        assert_eq!(ctx.output_dir(), Some(PathBuf::from("/tmp/profiled")));
    }

    #[test]
    fn test_output_dir_none() {
        let data = json!({
            "input": {},
            "output": {
                "spec": "stdout"
            }
        });
        let ctx = Environment::from_json(data);
        assert_eq!(ctx.output_dir(), None);
    }

    #[test]
    fn test_defaults() {
        let data = json!({});
        let ctx = Environment::from_json(data);
        assert_eq!(ctx.seed, 0);
        assert_eq!(ctx.replicate, 0);
        assert!(ctx.input_json().is_empty());
        assert!(ctx.files.is_empty());
        assert_eq!(ctx.output_dir(), None);
    }
}
