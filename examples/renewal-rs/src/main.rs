pub mod output;
pub mod parameters;
pub mod renewal;

use parameters::{Input, Parameters};
use renewal::RenewalModel;

fn main() {
    let ctx = mrp::Environment::<Input>::load();
    let input = ctx.input.as_ref().expect("missing input");
    let parameters = Parameters::new(input, ctx.seed);

    let result = RenewalModel::simulate(&parameters);

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
