use serde::Deserialize;

#[derive(Debug, Clone, Deserialize)]
pub struct Parameters {
    pub population: Population,
    pub r0: f64,
    pub generation_interval_pmf: Vec<f64>,
    pub symptom_onset_pmf: Vec<f64>,
    pub initial_infections: Vec<u64>,
    pub sim_length: usize,
    pub seed: u64,
}

#[derive(Debug, Clone, Copy, Deserialize)]
pub enum Population {
    Finite(u64),
    Infinite,
}
