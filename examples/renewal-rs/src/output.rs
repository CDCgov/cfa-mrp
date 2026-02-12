#[derive(Default)]
pub struct RenewalOutput {
    pub infection_incidence: Vec<u64>,
    pub symptomatic_incidence: Vec<u64>,
}

impl RenewalOutput {
    pub fn new(len: usize) -> RenewalOutput {
        RenewalOutput {
            infection_incidence: vec![0; len],
            symptomatic_incidence: vec![0; len],
        }
    }
}
