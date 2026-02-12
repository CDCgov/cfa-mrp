use rand::{SeedableRng, distr::Distribution, rngs::StdRng};
use rand_distr::{Binomial, Poisson};

use crate::{
    output::RenewalOutput,
    parameters::{Parameters, Population},
};

pub struct RenewalModel {}

impl RenewalModel {
    pub fn simulate(parameters: &Parameters) -> RenewalOutput {
        let mut output = RenewalOutput::new(parameters.sim_length);
        let mut rt = vec![parameters.r0; parameters.sim_length];
        let mut cum_infected = 0;
        let mut rng = StdRng::seed_from_u64(parameters.seed);
        for step in 0..parameters.sim_length {
            // Set infections
            // Determine infections
            let infections: u64;
            if step < parameters.initial_infections.len() {
                // Use initial infections at first
                infections = parameters.initial_infections[step];
            } else {
                // Use renewal equation calculation
                let mut current_infectious = 0.0;
                for lag in 0..usize::min(step, parameters.generation_interval_pmf.len()) {
                    current_infectious += output.infection_incidence[step - lag - 1] as f64
                        * parameters.generation_interval_pmf[lag];
                }
                let transmission_rate = rt[step] * current_infectious;

                match parameters.population {
                    Population::Finite(population) => {
                        let susceptible = population - cum_infected;
                        infections = if susceptible > 0 {
                            Binomial::new(
                                susceptible,
                                f64::min(transmission_rate / susceptible as f64, 1.0),
                            )
                            .unwrap()
                            .sample(&mut rng)
                        } else {
                            0
                        };
                    }
                    Population::Infinite => {
                        infections = if transmission_rate > 0. {
                            // Poisson requires non-zero rate
                            Poisson::new(transmission_rate).unwrap().sample(&mut rng) as u64
                        } else {
                            0
                        }
                    }
                }
            }
            output.infection_incidence[step] = infections;
            cum_infected += infections;
            // Update rt if needed
            if let Population::Finite(population) = parameters.population
                && step < parameters.sim_length - 1
            {
                rt[step + 1] =
                    parameters.r0 * (population - cum_infected) as f64 / population as f64
            }

            // Distribute symptom onset times
            if infections > 0 {
                let mut residual_mass = 1.;
                let mut cum_onsets = 0;
                for (mass, output_onsets) in parameters
                    .symptom_onset_pmf
                    .iter()
                    .zip(output.symptomatic_incidence.iter_mut().skip(step + 1))
                {
                    let onsets = Binomial::new(infections - cum_onsets, *mass / residual_mass)
                        .unwrap()
                        .sample(&mut rng);
                    *output_onsets += onsets;
                    cum_onsets += onsets;
                    residual_mass -= *mass;
                }
            }
        }
        output
    }
}

#[cfg(test)]
mod test {
    use crate::{
        parameters::{Parameters, Population},
        renewal::RenewalModel,
    };

    #[test]
    fn test_final_size() {
        let population = 100_000;
        let parameters = Parameters {
            population: Population::Finite(population),
            r0: 2.0,
            generation_interval_pmf: vec![0., 0., 0.25, 0.5, 0.25],
            symptom_onset_pmf: vec![1.],
            initial_infections: vec![1],
            sim_length: 200,
            seed: 8675308,
        };
        let output = RenewalModel::simulate(&parameters);
        let cum_infected: u64 = output.infection_incidence.iter().sum();
        let fraction_infected = cum_infected as f64 / population as f64;
        // Final size for r0: 2. is ~0.796811
        assert!(f64::abs(fraction_infected - 0.796811) < 0.1);
    }

    #[test]
    fn test_generation_interval() {
        let n_samples = 10000;
        let initial_infections = 100;
        let generation_interval_pmf = vec![0., 0., 0.25, 0.5, 0.25];

        let mut cumulative_output = vec![0 as u64; generation_interval_pmf.len() + 1];
        let mut total = 0;
        for seed in 0..n_samples {
            let parameters = Parameters {
                population: Population::Infinite,
                r0: 1.,
                generation_interval_pmf: generation_interval_pmf.clone(),
                symptom_onset_pmf: vec![1.],
                initial_infections: vec![initial_infections],
                sim_length: generation_interval_pmf.len() + 1,
                seed,
            };
            let output = RenewalModel::simulate(&parameters);
            for (i, entry) in cumulative_output.iter_mut().enumerate() {
                let incidence = output.infection_incidence[i];
                *entry += incidence;
                if i > 0 {
                    // Accumulate secondary infections
                    total += incidence;
                }
            }
        }
        for (step, mass) in generation_interval_pmf.iter().enumerate() {
            let fraction = cumulative_output[step + 1] as f64 / total as f64;
            assert!(f64::abs(fraction - mass) < 1e-3);
        }
    }

    #[test]
    fn test_symptom_onset() {
        let initial_infections = 1000000;
        let symptom_onset_pmf = vec![0., 0., 0.25, 0.5, 0.25];
        let parameters = Parameters {
            population: Population::Infinite,
            r0: 0.,
            generation_interval_pmf: vec![1.],
            symptom_onset_pmf: symptom_onset_pmf.clone(),
            initial_infections: vec![initial_infections],
            sim_length: symptom_onset_pmf.len() + 1,
            seed: 8675309,
        };
        let output = RenewalModel::simulate(&parameters);
        let total: u64 = output.symptomatic_incidence.iter().skip(1).sum();
        for (step, mass) in symptom_onset_pmf.iter().enumerate() {
            let fraction = output.symptomatic_incidence[step + 1] as f64 / total as f64;
            assert!(f64::abs(fraction - mass) < 1e-3);
        }
    }
}
