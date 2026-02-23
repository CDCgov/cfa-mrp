pub mod output;
pub mod parameters;
pub mod renewal;

use parameters::Parameters;
use renewal::RenewalModel;

fn main() {
    let ctx = cfa_mrp::Environment::<Parameters>::from_stdin_typed();
    let params = ctx.input.as_ref().expect("missing input");

    let result = RenewalModel::simulate(&params);

    let rows: Vec<Vec<String>> = (0..params.sim_length)
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
