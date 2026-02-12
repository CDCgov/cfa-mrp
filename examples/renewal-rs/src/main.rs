pub mod output;
pub mod parameters;
pub mod renewal;

use parameters::{Parameters, Population};
use renewal::RenewalModel;

fn main() {
    let ctx = mrp::RunnerContext::from_stdin();

    // Parse parameters from the input section
    let population_size = ctx.input.get("population_size").and_then(|v| v.as_u64());
    let population = match population_size {
        Some(n) => Population::Finite(n),
        None => Population::Infinite,
    };

    let r0 = ctx
        .input
        .get("r0")
        .and_then(|v| v.as_f64())
        .unwrap_or(2.0);

    let generation_interval_pmf: Vec<f64> = ctx
        .input
        .get("generation_interval_pmf")
        .and_then(|v| v.as_array())
        .expect("missing generation_interval_pmf")
        .iter()
        .map(|v| v.as_f64().unwrap())
        .collect();

    let symptom_onset_pmf: Vec<f64> = ctx
        .input
        .get("symptom_onset_pmf")
        .and_then(|v| v.as_array())
        .map(|a| a.iter().map(|v| v.as_f64().unwrap()).collect())
        .unwrap_or_else(|| vec![1.0]);

    let initial_infections: Vec<u64> = ctx
        .input
        .get("initial_infections")
        .and_then(|v| v.as_array())
        .map(|a| a.iter().map(|v| v.as_u64().unwrap()).collect())
        .unwrap_or_else(|| vec![1]);

    let sim_length = ctx
        .input
        .get("sim_length")
        .and_then(|v| v.as_u64())
        .unwrap_or(200) as usize;

    let parameters = Parameters {
        population,
        r0,
        generation_interval_pmf,
        symptom_onset_pmf,
        initial_infections,
        sim_length,
        seed: ctx.seed,
    };

    // Run simulation
    let result = RenewalModel::simulate(&parameters);

    // Build CSV rows
    let rows: Vec<Vec<String>> = (0..parameters.sim_length)
        .map(|i| {
            vec![
                i.to_string(),
                result.infection_incidence[i].to_string(),
                result.symptomatic_incidence[i].to_string(),
            ]
        })
        .collect();

    ctx.write_csv(
        "renewal_output.csv",
        &["step", "infections", "symptom_onsets"],
        &rows,
    );
}
