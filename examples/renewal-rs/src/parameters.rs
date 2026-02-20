use serde::Deserialize;

#[derive(Debug, Clone, Deserialize)]
pub struct Input {
    #[serde(default = "default_r0")]
    pub r0: f64,
    pub generation_interval_pmf: Vec<f64>,
    #[serde(default = "default_symptom_onset_pmf")]
    pub symptom_onset_pmf: Vec<f64>,
    #[serde(default = "default_initial_infections")]
    pub initial_infections: Vec<u64>,
    #[serde(default = "default_sim_length")]
    pub sim_length: usize,
    pub population_size: Option<u64>,
}

fn default_r0() -> f64 {
    2.0
}

fn default_symptom_onset_pmf() -> Vec<f64> {
    vec![1.0]
}

fn default_initial_infections() -> Vec<u64> {
    vec![1]
}

fn default_sim_length() -> usize {
    200
}

#[derive(Debug, Clone)]
pub struct Parameters {
    pub population: Population,
    pub r0: f64,
    pub generation_interval_pmf: Vec<f64>,
    pub symptom_onset_pmf: Vec<f64>,
    pub initial_infections: Vec<u64>,
    pub sim_length: usize,
    pub seed: u64,
}

impl Parameters {
    pub fn new(input: &Input, seed: u64) -> Self {
        let population = match input.population_size {
            Some(n) => Population::Finite(n),
            None => Population::Infinite,
        };
        Self {
            population,
            r0: input.r0,
            generation_interval_pmf: input.generation_interval_pmf.clone(),
            symptom_onset_pmf: input.symptom_onset_pmf.clone(),
            initial_infections: input.initial_infections.clone(),
            sim_length: input.sim_length,
            seed,
        }
    }
}

#[derive(Debug, Clone, Copy)]
pub enum Population {
    Finite(u64),
    Infinite,
}
