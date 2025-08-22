import os
import pickle
import pandas as pd

from synthetic_forecast.validation import validate_and_plot_results

if __name__ == "__main__":
    print("--- Running Validation Only ---")
    
    base_debug_dir = os.path.join(os.path.dirname(__file__), "20250708_172032")
    if not os.path.exists(base_debug_dir):
        print(f"Error: Debug directory '{base_debug_dir}' not found.")
        exit()
        
    print(f"Loading data from: {base_debug_dir}\n")

    # Load the existing synthetic forecast results from parquet
    synthetic_results_path = os.path.join(base_debug_dir, "synthetic_forecast_output.parquet")
    if not os.path.exists(synthetic_results_path):
        print(f"Error: Synthetic forecast output file '{synthetic_results_path}' not found.")
        exit()
    
    results_df = pd.read_parquet(synthetic_results_path)
    print(f"Loaded synthetic forecast results: {len(results_df)} rows")

    # Load the required pickle files for validation
    def load_data(filename):
        path = os.path.join(base_debug_dir, filename)
        try:
            with open(path, "rb") as f:
                return pickle.load(f)
        except FileNotFoundError:
            print(f"Warning: Could not load {filename}")
            return []

    pre_2020_obs = load_data("pre_2020_observations.pkl")
    
    # Load validation DataFrames from parquet files
    validation_df_path = os.path.join(base_debug_dir, "validation_df.parquet")
    test_df_path = os.path.join(base_debug_dir, "test_df.parquet")
    
    validation_df = pd.DataFrame()
    test_df = pd.DataFrame()
    
    if os.path.exists(validation_df_path):
        validation_df = pd.read_parquet(validation_df_path)
        print(f"Loaded validation data: {len(validation_df)} rows")
    else:
        print("Warning: validation_df.parquet not found")
    
    if os.path.exists(test_df_path):
        test_df = pd.read_parquet(test_df_path)
        print(f"Loaded test data: {len(test_df)} rows")
    else:
        print("Warning: test_df.parquet not found")
    
    print("\n--- Running Validation and Plotting ---")
    
    # Run validation with the loaded data
    if not validation_df.empty:
        validate_and_plot_results(
            synthetic_df=results_df,
            pre_2020_obs_df=pd.DataFrame(pre_2020_obs),
            validation_year_df=validation_df,
            output_dir=base_debug_dir,
            validation_label="2020"
        )
    
    # Run test validation if test data is available
    if not test_df.empty:
        test_output_dir = os.path.join(base_debug_dir, "test_results")
        validate_and_plot_results(
            synthetic_df=results_df,
            pre_2020_obs_df=pd.DataFrame(pre_2020_obs),
            validation_year_df=test_df,
            output_dir=test_output_dir,
            validation_label="2020_Jul-Dec"
        )
    
    print("\n--- Validation Finished ---")
