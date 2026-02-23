use serde::Deserialize;

#[derive(Debug, Clone, Deserialize)]
pub struct Parameters {
    pub r0: f64,
    pub generation_interval_pmf: Vec<f64>,
    pub symptom_onset_pmf: Vec<f64>,
    pub initial_infections: Vec<u64>,
    pub sim_length: usize,
    pub population: Option<u64>,
    pub seed: u64,
}
