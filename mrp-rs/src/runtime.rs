use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::Command;

use serde_json::Value;

use crate::MrpError;

#[derive(Debug, Clone)]
pub struct RunResult {
    pub exit_code: i32,
    pub stdout: Vec<u8>,
    pub stderr: Vec<u8>,
}

impl RunResult {
    pub fn ok(&self) -> bool {
        self.exit_code == 0
    }
}

pub trait Runtime {
    fn run(&self, run_json: &Value) -> Result<RunResult, MrpError>;
}

pub struct SubprocessRuntime {
    pub command: Vec<String>,
    pub cwd: Option<PathBuf>,
    pub timeout: Option<u64>,
}

impl SubprocessRuntime {
    pub fn new(command: Vec<String>) -> Self {
        SubprocessRuntime {
            command,
            cwd: None,
            timeout: None,
        }
    }
}

impl Runtime for SubprocessRuntime {
    fn run(&self, run_json: &Value) -> Result<RunResult, MrpError> {
        prepare_output(run_json);

        let input_bytes =
            serde_json::to_vec(run_json).map_err(|e| MrpError::Serialization(e.to_string()))?;

        let (program, args) = self
            .command
            .split_first()
            .ok_or_else(|| MrpError::Config("empty command".to_string()))?;

        let mut cmd = Command::new(program);
        cmd.args(args).stdin(std::process::Stdio::piped());
        cmd.stdout(std::process::Stdio::piped());
        cmd.stderr(std::process::Stdio::piped());

        if let Some(ref cwd) = self.cwd {
            cmd.current_dir(cwd);
        }

        let mut child = cmd.spawn().map_err(|e| MrpError::Runtime(e.to_string()))?;

        if let Some(ref mut stdin) = child.stdin.take() {
            stdin
                .write_all(&input_bytes)
                .map_err(|e| MrpError::Runtime(e.to_string()))?;
        }

        let output = child
            .wait_with_output()
            .map_err(|e| MrpError::Runtime(e.to_string()))?;

        Ok(RunResult {
            exit_code: output.status.code().unwrap_or(-1),
            stdout: output.stdout,
            stderr: output.stderr,
        })
    }
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

fn prepare_output(run_json: &Value) {
    let output = match run_json.get("output") {
        Some(o) => o,
        None => return,
    };
    if output.get("spec").and_then(|v| v.as_str()) == Some("filesystem") {
        if let Some(dir) = output.get("dir").and_then(|v| v.as_str()) {
            let _ = std::fs::create_dir_all(Path::new(dir));
        }
        return;
    }
    let selected = select_profile(output, None);
    if selected.get("spec").and_then(|v| v.as_str()) == Some("filesystem") {
        if let Some(dir) = selected.get("dir").and_then(|v| v.as_str()) {
            let _ = std::fs::create_dir_all(Path::new(dir));
        }
    }
}

pub fn resolve_runtime(config: &Value) -> Result<Box<dyn Runtime>, MrpError> {
    resolve_runtime_with_profile(config, None)
}

pub fn resolve_runtime_with_profile(
    config: &Value,
    profile: Option<&str>,
) -> Result<Box<dyn Runtime>, MrpError> {
    let runtime = config
        .get("runtime")
        .ok_or_else(|| MrpError::Config("missing [runtime] section".to_string()))?;

    let selected = select_profile(runtime, profile);
    let spec = selected
        .get("spec")
        .and_then(|v| v.as_str())
        .unwrap_or("process");

    match spec {
        "process" => {
            let command = selected
                .get("command")
                .and_then(|v| v.as_str())
                .ok_or_else(|| {
                    MrpError::Config("runtime.command is required for process runtime".to_string())
                })?;

            let mut full_command = vec![command.to_string()];
            if let Some(args) = selected.get("args").and_then(|v| v.as_array()) {
                for arg in args {
                    if let Some(s) = arg.as_str() {
                        full_command.push(s.to_string());
                    }
                }
            }

            if selected.get("env").and_then(|v| v.as_str()) == Some("uv") {
                full_command = [vec!["uv".to_string(), "run".to_string()], full_command].concat();
            }

            let mut rt = SubprocessRuntime::new(full_command);
            rt.cwd = selected
                .get("cwd")
                .and_then(|v| v.as_str())
                .map(PathBuf::from);
            rt.timeout = selected.get("timeout").and_then(|v| v.as_u64());
            Ok(Box::new(rt))
        }
        _ => Err(MrpError::Config(format!("unknown runtime spec: {spec}"))),
    }
}
