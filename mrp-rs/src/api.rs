use serde_json::Value;

use crate::orchestrator::{ConfigSource, DefaultOrchestrator, Orchestrator};
use crate::runtime::RunResult;
use crate::MrpError;

pub fn run(configs: &[ConfigSource]) -> Result<RunResult, MrpError> {
    run_with_options(configs, None, None, None, None)
}

pub fn run_with_options(
    configs: &[ConfigSource],
    output_dir: Option<&str>,
    orchestrator: Option<&dyn Orchestrator>,
    runtime_profile: Option<&str>,
    output_profile: Option<&str>,
) -> Result<RunResult, MrpError> {
    let default_orch;
    let orch: &dyn Orchestrator = match orchestrator {
        Some(o) => o,
        None => {
            default_orch = DefaultOrchestrator {
                output_dir: output_dir.map(|s| s.to_string()),
                output_profile: output_profile.map(|s| s.to_string()),
            };
            &default_orch
        }
    };

    let config: Value = orch.load_config(configs)?;
    let runtime = orch.resolve_runtime_with_profile(&config, runtime_profile)?;
    orch.execute(&config, runtime.as_deref())
}
