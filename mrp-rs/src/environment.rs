use std::collections::HashMap;
use std::fs;
use std::io::{self, Read};
use std::path::{Path, PathBuf};

use serde::de::DeserializeOwned;
use serde_json::Value;

use crate::csv::CsvWriter;

pub struct Environment<I = ()> {
    pub input: Option<I>,
    pub seed: u64,
    pub replicate: u64,
    pub files: HashMap<String, PathBuf>,
    input_json: Value,
    output: Value,
    csv_writers: HashMap<String, CsvWriter>,
}

impl Environment<()> {
    /// Create an empty environment.
    pub fn new() -> Self {
        Environment {
            input: None,
            seed: 0,
            replicate: 0,
            files: HashMap::new(),
            input_json: Value::Null,
            output: Value::Object(Default::default()),
            csv_writers: HashMap::new(),
        }
    }

    /// Create from a parsed JSON value.
    pub fn from_json(data: Value) -> Self {
        Self::build(data)
    }

    /// Read JSON from stdin.
    pub fn from_stdin() -> Self {
        let data = read_stdin();
        Self::build(data)
    }

    /// Read JSON or TOML from a file.
    pub fn from_file(path: &Path) -> Self {
        let data = read_file(path);
        Self::build(data)
    }

    fn build(data: Value) -> Self {
        let (seed, replicate, files, input_json, output) = extract_common(&data);
        Environment {
            input: None,
            seed,
            replicate,
            files,
            input_json,
            output,
            csv_writers: HashMap::new(),
        }
    }
}

impl<I: DeserializeOwned> Environment<I> {
    /// Read JSON from stdin and deserialize input into a typed struct.
    pub fn from_stdin_typed() -> Self {
        let data = read_stdin();
        Self::build_typed(data)
    }

    /// Read JSON or TOML from a file and deserialize input.
    pub fn from_file_typed(path: &Path) -> Self {
        let data = read_file(path);
        Self::build_typed(data)
    }

    /// Create from parsed JSON and deserialize input.
    pub fn from_json_typed(data: Value) -> Self {
        Self::build_typed(data)
    }

    fn build_typed(data: Value) -> Self {
        let (seed, replicate, files, input_json, output) = extract_common(&data);
        let input = if input_json.is_null() || input_json.as_object().is_some_and(|m| m.is_empty())
        {
            None
        } else {
            Some(serde_json::from_value::<I>(input_json.clone()).expect("failed to parse input"))
        };
        Environment {
            input,
            seed,
            replicate,
            files,
            input_json,
            output,
            csv_writers: HashMap::new(),
        }
    }
}

impl Environment<()> {
    /// Convert an untyped environment into a typed one by deserializing input.
    pub fn with_input_type<I: DeserializeOwned>(self) -> Environment<I> {
        let input = if self.input_json.is_null()
            || self.input_json.as_object().is_some_and(|m| m.is_empty())
        {
            None
        } else {
            Some(
                serde_json::from_value::<I>(self.input_json.clone())
                    .expect("failed to parse input"),
            )
        };
        Environment {
            input,
            seed: self.seed,
            replicate: self.replicate,
            files: self.files,
            input_json: self.input_json,
            output: self.output,
            csv_writers: self.csv_writers,
        }
    }
}

impl<I> Environment<I> {
    /// Get the output directory, if configured as filesystem output.
    pub fn output_dir(&self) -> Option<PathBuf> {
        let output = &self.output;
        // Flat output
        if output.get("spec").and_then(|v| v.as_str()) == Some("filesystem") {
            return output
                .get("dir")
                .and_then(|v| v.as_str())
                .map(PathBuf::from);
        }
        // Profiled output
        if let Some(profiles) = output.get("profile").and_then(|v| v.as_object()) {
            let selected = profiles.get("default").or_else(|| profiles.values().next());
            if let Some(prof) = selected {
                if prof.get("spec").and_then(|v| v.as_str()) == Some("filesystem") {
                    return prof.get("dir").and_then(|v| v.as_str()).map(PathBuf::from);
                }
            }
        }
        None
    }

    /// Write bytes to a file in the output directory, or to stdout.
    pub fn write(&self, filename: &str, data: &[u8]) {
        if let Some(dir) = self.output_dir() {
            fs::create_dir_all(&dir).expect("failed to create output dir");
            fs::write(dir.join(filename), data).expect("failed to write file");
        } else {
            use std::io::Write;
            io::stdout()
                .write_all(data)
                .expect("failed to write to stdout");
        }
    }

    /// Write a string to a file in the output directory, or to stdout.
    pub fn write_str(&self, filename: &str, data: &str) {
        self.write(filename, data.as_bytes());
    }

    /// Create a managed CSV writer with an ID for later row writes.
    pub fn create_csv(&mut self, id: &str, filename: &str, headers: &[&str]) {
        let writer = self.csv_writer(filename, headers);
        self.csv_writers.insert(id.to_string(), writer);
    }

    /// Write a row to a managed CSV writer by ID.
    pub fn write_csv_row(&mut self, id: &str, row: &[&str]) {
        self.csv_writers
            .get_mut(id)
            .expect("no CSV writer with that id")
            .write_row(row);
    }

    /// Close and remove a managed CSV writer by ID.
    pub fn close_csv(&mut self, id: &str) {
        if let Some(mut w) = self.csv_writers.remove(id) {
            w.flush();
        }
    }

    /// Close all managed CSV writers.
    pub fn close_all_csv(&mut self) {
        for (_, mut w) in self.csv_writers.drain() {
            w.flush();
        }
    }

    /// Create a standalone CSV writer for the given filename and headers.
    pub fn csv_writer(&self, filename: &str, headers: &[&str]) -> CsvWriter {
        let dest: Box<dyn std::io::Write> = if let Some(dir) = self.output_dir() {
            fs::create_dir_all(&dir).expect("failed to create output dir");
            Box::new(fs::File::create(dir.join(filename)).expect("failed to create CSV file"))
        } else {
            Box::new(io::stdout())
        };
        CsvWriter::new(dest, headers)
    }

    /// Write all rows to a CSV file at once.
    pub fn write_csv(&self, filename: &str, headers: &[&str], rows: &[Vec<String>]) {
        let mut writer = self.csv_writer(filename, headers);
        for row in rows {
            let refs: Vec<&str> = row.iter().map(|s| s.as_str()).collect();
            writer.write_row(&refs);
        }
        writer.flush();
    }
}

impl Default for Environment<()> {
    fn default() -> Self {
        Self::new()
    }
}

fn extract_common(data: &Value) -> (u64, u64, HashMap<String, PathBuf>, Value, Value) {
    let input_section = data
        .get("input")
        .cloned()
        .unwrap_or(Value::Object(Default::default()));

    let mut input_map = match input_section {
        Value::Object(m) => m,
        _ => Default::default(),
    };

    let seed = input_map
        .remove("seed")
        .and_then(|v| v.as_u64())
        .unwrap_or(0);
    let replicate = input_map
        .remove("replicate")
        .and_then(|v| v.as_u64())
        .unwrap_or(0);

    let input_json = Value::Object(input_map);

    let model = data.get("model").unwrap_or(&Value::Null);
    let files = model
        .get("files")
        .and_then(|f| f.as_object())
        .map(|m| {
            m.iter()
                .filter_map(|(k, v)| v.as_str().map(|s| (k.clone(), PathBuf::from(s))))
                .collect()
        })
        .unwrap_or_default();

    let output = data
        .get("output")
        .cloned()
        .unwrap_or(Value::Object(Default::default()));

    (seed, replicate, files, input_json, output)
}

fn read_stdin() -> Value {
    let mut buf = String::new();
    io::stdin()
        .read_to_string(&mut buf)
        .expect("failed to read stdin");
    if buf.trim().is_empty() {
        return Value::Object(Default::default());
    }
    serde_json::from_str(&buf).expect("failed to parse JSON from stdin")
}

fn read_file(path: &Path) -> Value {
    let contents = fs::read_to_string(path).expect("failed to read file");
    match path.extension().and_then(|e| e.to_str()) {
        Some("toml") => {
            let table: toml::Value = contents.parse().expect("failed to parse TOML");
            toml_to_json(table)
        }
        _ => serde_json::from_str(&contents).expect("failed to parse JSON file"),
    }
}

pub fn toml_to_json(val: toml::Value) -> Value {
    match val {
        toml::Value::String(s) => Value::String(s),
        toml::Value::Integer(i) => Value::Number(serde_json::Number::from(i)),
        toml::Value::Float(f) => serde_json::Number::from_f64(f).map_or(Value::Null, Value::Number),
        toml::Value::Boolean(b) => Value::Bool(b),
        toml::Value::Datetime(d) => Value::String(d.to_string()),
        toml::Value::Array(arr) => Value::Array(arr.into_iter().map(toml_to_json).collect()),
        toml::Value::Table(table) => {
            let map = table
                .into_iter()
                .map(|(k, v)| (k, toml_to_json(v)))
                .collect();
            Value::Object(map)
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_from_json_empty() {
        let env = Environment::from_json(Value::Object(Default::default()));
        assert_eq!(env.seed, 0);
        assert_eq!(env.replicate, 0);
        assert!(env.files.is_empty());
        assert!(env.output_dir().is_none());
    }

    #[test]
    fn test_from_json_with_input() {
        let data = serde_json::json!({
            "input": { "seed": 42, "replicate": 3, "r0": 2.0 },
            "output": { "spec": "filesystem", "dir": "/tmp/out" },
            "model": { "files": { "data": "/tmp/data.csv" } }
        });
        let env = Environment::from_json(data);
        assert_eq!(env.seed, 42);
        assert_eq!(env.replicate, 3);
        assert_eq!(
            env.files.get("data").unwrap(),
            &PathBuf::from("/tmp/data.csv")
        );
        assert_eq!(env.output_dir(), Some(PathBuf::from("/tmp/out")));
    }

    #[test]
    fn test_typed_input() {
        #[derive(serde::Deserialize, Debug)]
        struct MyInput {
            r0: f64,
        }
        let data = serde_json::json!({
            "input": { "seed": 1, "r0": 2.5 }
        });
        let env = Environment::<MyInput>::from_json_typed(data);
        assert_eq!(env.seed, 1);
        let input = env.input.unwrap();
        assert!((input.r0 - 2.5).abs() < f64::EPSILON);
    }

    #[test]
    fn test_with_input_type() {
        #[derive(serde::Deserialize, Debug)]
        struct MyInput {
            r0: f64,
        }
        let data = serde_json::json!({
            "input": { "seed": 5, "r0": 1.5 }
        });
        let env = Environment::from_json(data);
        assert_eq!(env.seed, 5);
        let typed: Environment<MyInput> = env.with_input_type();
        assert_eq!(typed.seed, 5);
        assert!((typed.input.unwrap().r0 - 1.5).abs() < f64::EPSILON);
    }

    #[test]
    fn test_profiled_output_dir() {
        let data = serde_json::json!({
            "output": {
                "profile": {
                    "default": { "spec": "filesystem", "dir": "/tmp/profiled" }
                }
            }
        });
        let env = Environment::from_json(data);
        assert_eq!(env.output_dir(), Some(PathBuf::from("/tmp/profiled")));
    }

    #[test]
    fn test_write_csv() {
        let dir = tempfile::tempdir().unwrap();
        let data = serde_json::json!({
            "output": { "spec": "filesystem", "dir": dir.path().to_str().unwrap() }
        });
        let env = Environment::from_json(data);
        env.write_csv(
            "test.csv",
            &["a", "b"],
            &[
                vec!["1".to_string(), "2".to_string()],
                vec!["3".to_string(), "4".to_string()],
            ],
        );
        let content = fs::read_to_string(dir.path().join("test.csv")).unwrap();
        assert!(content.contains("a,b"));
        assert!(content.contains("1,2"));
        assert!(content.contains("3,4"));
    }
}
