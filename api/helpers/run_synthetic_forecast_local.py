import os
import pickle
import asyncio
import pandas as pd

from synthetic_forecast import create_synthetic_forecast
from synthetic_forecast.validation import validate_and_plot_results

if __name__ == "__main__":
    print("--- Running Local Test Harness ---")
    
    base_debug_dir = os.path.join(os.path.dirname(__file__), "20250708_172032")
    if not os.path.exists(base_debug_dir):
        print(f"Error: Debug directory '{base_debug_dir}' not found.")
        exit()
        
    print(f"Loading data from: {base_debug_dir}\n")

    params_path = os.path.join(base_debug_dir, "params.pkl")
    with open(params_path, "rb") as f:
        params = pickle.load(f)

    def load_data(filename):
        path = os.path.join(base_debug_dir, filename)
        try:
            with open(path, "rb") as f:
                return pickle.load(f)
        except FileNotFoundError:
            return []

    pre_2020_obs = load_data("pre_2020_observations.pkl")
    hist_obs = load_data("historical_observations.pkl")
    hist_fc = load_data("historical_forecasts.pkl")

    print("\n--- Calling create_synthetic_forecast ---")
    
    synthetic_results, validation_df, test_df = asyncio.run(create_synthetic_forecast(
        loc_id=params["loc_id"],
        start_time=params["start_time"],
        end_time=params["end_time"],
        pre_2020_obs_data=pre_2020_obs,
        all_historical_obs=hist_obs,
        all_historical_fc=hist_fc
    ))

    print("\n--- Test Harness Finished ---")
    if synthetic_results:
        results_df = pd.DataFrame(synthetic_results)
        output_path = os.path.join(base_debug_dir, "synthetic_forecast_output.parquet")
        results_df.to_parquet(output_path)
        print(f"Full results saved to: {output_path}")

        validate_and_plot_results(
            synthetic_df=results_df,
            pre_2020_obs_df=pd.DataFrame(pre_2020_obs),
            validation_year_df=validation_df,
            output_dir=base_debug_dir,
            validation_label="2020"
        )
        
        if not test_df.empty:
            test_output_dir = os.path.join(base_debug_dir, "test_results")
            validate_and_plot_results(
                synthetic_df=results_df,
                pre_2020_obs_df=pd.DataFrame(pre_2020_obs),
                validation_year_df=test_df,
                output_dir=test_output_dir,
                validation_label="2020_Jul-Dec"
            )
    else:
        print("The function returned no synthetic data.")