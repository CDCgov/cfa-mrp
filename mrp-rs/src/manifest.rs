use std::collections::HashMap;

use serde::de::DeserializeOwned;
use serde::{Deserialize, Deserializer, Serialize, Serializer};
use serde_json::Value as JsonValue;

pub const MRP_VERSION: &str = "0.0.1";

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(bound(
    deserialize = "I: Deserialize<'de>, X: Deserialize<'de>",
    serialize = "I: Serialize, X: Serialize"
))]
pub struct RunManifest<I = JsonValue, X = JsonValue> {
    pub mrp: MrpMeta,
    #[serde(default)]
    pub model: ModelSection,
    #[serde(default)]
    pub runtime: RuntimeSpec,
    pub input: I,
    #[serde(default)]
    pub output: MrpOutput,
    #[serde(default)]
    #[serde(flatten)]
    pub ext: Option<X>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(tag = "spec")]
pub enum RuntimeSpec {
    #[serde(rename = "process")]
    Process {
        command: String,
        #[serde(default, skip_serializing_if = "Vec::is_empty")]
        args: Vec<String>,
    },
    #[serde(rename = "wasm")]
    Wasm,
    #[serde(rename = "inline")]
    Inline,
}

impl Default for RuntimeSpec {
    fn default() -> Self {
        RuntimeSpec::Process {
            command: String::new(),
            args: Vec::new(),
        }
    }
}

impl<'de> Deserialize<'de> for RuntimeSpec {
    fn deserialize<D: Deserializer<'de>>(deserializer: D) -> Result<Self, D::Error> {
        let mut map = serde_json::Map::deserialize(deserializer)?;
        let spec = map
            .remove("spec")
            .and_then(|v| v.as_str().map(String::from))
            .unwrap_or_else(|| "process".to_string());
        map.insert("spec".to_string(), JsonValue::String(spec));

        #[derive(Deserialize)]
        #[serde(tag = "spec")]
        enum Helper {
            #[serde(rename = "process")]
            Process {
                command: String,
                #[serde(default)]
                args: Vec<String>,
            },
            #[serde(rename = "wasm")]
            Wasm,
            #[serde(rename = "inline")]
            Inline,
        }

        let helper: Helper =
            serde_json::from_value(JsonValue::Object(map)).map_err(serde::de::Error::custom)?;

        Ok(match helper {
            Helper::Process { command, args } => RuntimeSpec::Process { command, args },
            Helper::Wasm => RuntimeSpec::Wasm,
            Helper::Inline => RuntimeSpec::Inline,
        })
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub enum OutputSpec {
    #[default]
    #[serde(rename = "filesystem")]
    Filesystem,
    #[serde(rename = "buffer")]
    Buffer,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct MrpOutput {
    #[serde(default)]
    pub spec: OutputSpec,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub dir: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub format: Option<String>,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct MrpMeta {
    #[serde(serialize_with = "serialize_mrp_version")]
    pub version: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub input_hash: Option<String>,
}

fn serialize_mrp_version<S: Serializer>(_: &str, s: S) -> Result<S::Ok, S::Error> {
    s.serialize_str(MRP_VERSION)
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct ModelSection {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub spec: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub version: Option<String>,
    #[serde(default, skip_serializing_if = "HashMap::is_empty")]
    pub files: HashMap<String, String>,
}

impl<I: DeserializeOwned + Serialize, X: DeserializeOwned + Serialize> RunManifest<I, X> {
    pub fn from_json(value: JsonValue) -> Result<Self, serde_json::Error> {
        serde_json::from_value(value)
    }

    pub fn to_json(&self) -> Result<JsonValue, serde_json::Error> {
        serde_json::to_value(self)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_roundtrip() {
        let json = serde_json::json!({
            "mrp": {"version": "0.0.1", "input_hash": "abc123"},
            "model": {"spec": "renewal", "files": {"data": "/tmp/data.csv"}},
            "runtime": {"command": "my-model", "args": ["--flag"]},
            "output": {"spec": "filesystem", "dir": "/tmp/out"},
            "input": {"r0": 2.0, "seed": 42}
        });
        let manifest: RunManifest = RunManifest::from_json(json).unwrap();
        assert_eq!(manifest.mrp.version, "0.0.1");
        assert_eq!(manifest.mrp.input_hash.as_deref(), Some("abc123"));
        assert_eq!(manifest.model.spec.as_deref(), Some("renewal"));
        assert_eq!(manifest.model.files.get("data").unwrap(), "/tmp/data.csv");
        assert!(matches!(manifest.runtime, RuntimeSpec::Process { .. }));

        let back = manifest.to_json().unwrap();
        assert_eq!(back["input"]["r0"], 2.0);
        assert_eq!(back["runtime"]["spec"], "process");
        assert_eq!(back["runtime"]["command"], "my-model");
    }

    #[test]
    fn test_runtime_defaults_to_process() {
        let json = serde_json::json!({
            "mrp": {"version": "0.0.1"},
            "input": {},
            "runtime": {"command": "foo"}
        });
        let manifest: RunManifest = RunManifest::from_json(json).unwrap();
        match &manifest.runtime {
            RuntimeSpec::Process { command, args } => {
                assert_eq!(command, "foo");
                assert!(args.is_empty());
            }
            _ => panic!("expected Process"),
        }
    }

    #[test]
    fn test_runtime_explicit_spec() {
        let json = serde_json::json!({
            "mrp": {"version": "0.0.1"},
            "input": {},
            "runtime": {"spec": "process", "command": "bar", "args": ["--verbose"]}
        });
        let manifest: RunManifest = RunManifest::from_json(json).unwrap();
        match &manifest.runtime {
            RuntimeSpec::Process { command, args } => {
                assert_eq!(command, "bar");
                assert_eq!(args, &vec!["--verbose".to_string()]);
            }
            _ => panic!("expected Process"),
        }
    }

    #[test]
    fn test_runtime_wasm() {
        let json = serde_json::json!({
            "mrp": {"version": "0.0.1"},
            "input": {},
            "runtime": {"spec": "wasm"}
        });
        let manifest: RunManifest = RunManifest::from_json(json).unwrap();
        assert!(matches!(manifest.runtime, RuntimeSpec::Wasm));
    }

    #[test]
    fn test_defaults() {
        let manifest: RunManifest = RunManifest::from_json(serde_json::json!({
            "mrp": {"version": "0.0.1"},
            "input": {}
        })).unwrap();
        assert_eq!(manifest.mrp.version, "0.0.1");
        assert!(manifest.model.files.is_empty());
        assert!(manifest.model.spec.is_none());
    }

    #[test]
    fn test_typed_input() {
        #[derive(Debug, Deserialize, Serialize)]
        struct MyInput {
            r0: f64,
        }
        let json = serde_json::json!({
            "mrp": {"version": "0.0.1"},
            "input": {"r0": 2.5}
        });
        let manifest: RunManifest<MyInput> = RunManifest::from_json(json).unwrap();
        assert!((manifest.input.r0 - 2.5).abs() < f64::EPSILON);
    }

    #[test]
    fn test_extension() {
        #[derive(Debug, Deserialize, Serialize)]
        struct MyExt {
            custom: String,
        }
        let json = serde_json::json!({
            "mrp": {"version": "0.0.1"},
            "input": {},
            "custom": "hello"
        });
        let manifest: RunManifest<JsonValue, MyExt> = RunManifest::from_json(json).unwrap();
        assert_eq!(manifest.ext.unwrap().custom, "hello");
    }
}
