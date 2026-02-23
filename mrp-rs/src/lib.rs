pub mod api;
pub mod config;
pub mod csv;
pub mod environment;
pub mod manifest;
pub mod orchestrator;
pub mod runtime;
pub mod stager;

pub use api::{run, run_with_options};
pub use csv::CsvWriter;
pub use environment::Environment;
pub use orchestrator::{ConfigSource, DefaultOrchestrator, Orchestrator};
pub use manifest::{ModelSection, MrpMeta, MrpOutput, RunManifest, RuntimeSpec};
pub use runtime::{RunResult, Runtime, SubprocessRuntime};

#[derive(Debug)]
pub enum MrpError {
    Config(String),
    FileNotFound(String),
    Staging(String),
    Runtime(String),
    Serialization(String),
}

impl std::fmt::Display for MrpError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            MrpError::Config(msg) => write!(f, "config error: {msg}"),
            MrpError::FileNotFound(msg) => write!(f, "file not found: {msg}"),
            MrpError::Staging(msg) => write!(f, "staging error: {msg}"),
            MrpError::Runtime(msg) => write!(f, "runtime error: {msg}"),
            MrpError::Serialization(msg) => write!(f, "serialization error: {msg}"),
        }
    }
}

impl std::error::Error for MrpError {}
