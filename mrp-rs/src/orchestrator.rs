use std::path::Path;

use serde_json::Value;

use crate::config::{apply_overrides, build_run_json_with_options, load_toml, resolve_input};
use crate::runtime::{resolve_runtime as rt_resolve, resolve_runtime_with_profile, RunResult, Runtime};
use crate::stager::{cleanup, stage_files};
use crate::MrpError;

pub enum ConfigSource<'a> {
    Path(&'a Path),
    Dict(Value),
}

pub trait Orchestrator {
    fn load_config(&self, configs: &[ConfigSource]) -> Result<Value, MrpError> {
        self.load_config_with_overrides(configs, &[])
    }

    fn load_config_with_overrides(
        &self,
        configs: &[ConfigSource],
        overrides: &[&str],
    ) -> Result<Value, MrpError>;

    fn resolve_runtime(&self, config: &Value) -> Result<Option<Box<dyn Runtime>>, MrpError> {
        self.resolve_runtime_with_profile(config, None)
    }

    fn resolve_runtime_with_profile(
        &self,
        config: &Value,
        profile: Option<&str>,
    ) -> Result<Option<Box<dyn Runtime>>, MrpError>;

    fn execute(
        &self,
        config: &Value,
        runtime: Option<&dyn Runtime>,
    ) -> Result<RunResult, MrpError>;

    fn build_run(&self, config: &Value) -> Result<Value, MrpError> {
        self.build_run_with_options(config, None, None)
    }

    fn build_run_with_options(
        &self,
        config: &Value,
        output_dir: Option<&str>,
        output_profile: Option<&str>,
    ) -> Result<Value, MrpError>;

    fn run(&self, run_json: &Value, runtime: &dyn Runtime) -> Result<RunResult, MrpError>;
}

fn deep_merge(base: &mut Value, updates: &Value) {
    if let (Some(base_obj), Some(updates_obj)) = (base.as_object_mut(), updates.as_object()) {
        for (key, value) in updates_obj {
            if base_obj.get(key).is_some_and(|v| v.is_object()) && value.is_object() {
                deep_merge(base_obj.get_mut(key).unwrap(), value);
            } else {
                base_obj.insert(key.clone(), value.clone());
            }
        }
    }
}

fn load_single_config(source: &ConfigSource) -> Result<Value, MrpError> {
    match source {
        ConfigSource::Path(path) => {
            if !path.exists() {
                return Err(MrpError::FileNotFound(format!(
                    "config file not found: {}",
                    path.display()
                )));
            }
            Ok(load_toml(path))
        }
        ConfigSource::Dict(val) => Ok(val.clone()),
    }
}

pub struct DefaultOrchestrator {
    pub output_dir: Option<String>,
    pub output_profile: Option<String>,
}

impl DefaultOrchestrator {
    pub fn new() -> Self {
        DefaultOrchestrator {
            output_dir: None,
            output_profile: None,
        }
    }
}

impl Default for DefaultOrchestrator {
    fn default() -> Self {
        Self::new()
    }
}

impl Orchestrator for DefaultOrchestrator {
    fn load_config_with_overrides(
        &self,
        configs: &[ConfigSource],
        overrides: &[&str],
    ) -> Result<Value, MrpError> {
        if configs.is_empty() {
            return Err(MrpError::Config("at least one config is required".to_string()));
        }

        let base_dir = match &configs[0] {
            ConfigSource::Path(p) => p.parent().map(|p| p.to_path_buf()),
            _ => None,
        };

        let mut result = load_single_config(&configs[0])?;
        for source in &configs[1..] {
            let loaded = load_single_config(source)?;
            deep_merge(&mut result, &loaded);
        }

        if !overrides.is_empty() {
            result = apply_overrides(&result, overrides);
        }

        result = resolve_input(&result, base_dir.as_deref());

        Ok(result)
    }

    fn resolve_runtime_with_profile(
        &self,
        config: &Value,
        profile: Option<&str>,
    ) -> Result<Option<Box<dyn Runtime>>, MrpError> {
        if config.get("runtime").is_none() {
            return Ok(None);
        }
        match profile {
            Some(p) => resolve_runtime_with_profile(config, Some(p)).map(Some),
            None => rt_resolve(config).map(Some),
        }
    }

    fn execute(
        &self,
        config: &Value,
        runtime: Option<&dyn Runtime>,
    ) -> Result<RunResult, MrpError> {
        let runtime = runtime
            .ok_or_else(|| MrpError::Config("DefaultOrchestrator requires a runtime".to_string()))?;
        let run_json = self.build_run_with_options(
            config,
            self.output_dir.as_deref(),
            self.output_profile.as_deref(),
        )?;
        self.run(&run_json, runtime)
    }

    fn build_run_with_options(
        &self,
        config: &Value,
        output_dir: Option<&str>,
        output_profile: Option<&str>,
    ) -> Result<Value, MrpError> {
        let raw_files = config
            .get("model")
            .and_then(|m| m.get("files"))
            .and_then(|f| f.as_object());

        let staged = if let Some(files) = raw_files {
            let file_map = files
                .iter()
                .filter_map(|(k, v)| v.as_str().map(|s| (k.clone(), s.to_string())))
                .collect();
            let staged = stage_files(&file_map)?;
            let map: serde_json::Map<String, Value> = staged
                .into_iter()
                .map(|(k, v)| (k, Value::String(v)))
                .collect();
            Some(map)
        } else {
            None
        };

        Ok(build_run_json_with_options(
            config,
            staged.as_ref(),
            output_dir,
            output_profile,
        ))
    }

    fn run(&self, run_json: &Value, runtime: &dyn Runtime) -> Result<RunResult, MrpError> {
        let result = runtime.run(run_json);
        cleanup();
        result
    }
}
