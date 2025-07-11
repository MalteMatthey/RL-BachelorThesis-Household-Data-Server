import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats

from . import config

def validate_and_plot_results(
    synthetic_df: pd.DataFrame, 
    pre_2020_obs_df: pd.DataFrame,
    validation_year_df: pd.DataFrame, 
    output_dir: str,
    validation_label: str = "Validation"
):
    """
    Performs validation by comparing error characteristics of synthetic data against a hold-out set.
    """
    print(f"\n--- Running Validation and Plotting (Comparing Synthetic vs. {validation_label}) ---")
    
    plot_dir = os.path.join(output_dir, "validation_plots")
    os.makedirs(plot_dir, exist_ok=True)
    print(f"Saving validation plots to: {plot_dir}")

    for col in config.WEATHER_FEATURES_TO_MODEL:
        synthetic_df[col] = pd.to_numeric(synthetic_df[col], errors='coerce')
        pre_2020_obs_df[col] = pd.to_numeric(pre_2020_obs_df[col], errors='coerce')

    synthetic_df['target_time_utc'] = pd.to_datetime(synthetic_df['target_time'], utc=True)
    pre_2020_obs_df['datetime_utc'] = pd.to_datetime(pre_2020_obs_df['datetime'], utc=True)
    
    merged_synthetic = pd.merge(
        synthetic_df,
        pre_2020_obs_df,
        left_on='target_time_utc',
        right_on='datetime_utc',
        suffixes=('_synth', '_obs')
    )

    if validation_year_df.empty or merged_synthetic.empty:
        print("Warning: Cannot perform validation due to empty data.")
        return

    for feature in config.WEATHER_FEATURES_TO_MODEL:
        merged_synthetic[f'{feature}_error'] = merged_synthetic[f'{feature}_synth'] - merged_synthetic[f'{feature}_obs']
    
    merged_synthetic['lead_time'] = (merged_synthetic['target_time_utc'] - pd.to_datetime(merged_synthetic['forecast_run'], utc=True)).dt.total_seconds() / 3600

    for feature in config.WEATHER_FEATURES_TO_MODEL:
        print(f"\nValidating feature: {feature}")
        
        real_errors = validation_year_df[f'{feature}_error'].dropna()
        synthetic_errors = merged_synthetic[f'{feature}_error'].dropna()

        if real_errors.empty or synthetic_errors.empty:
            print(f"  Skipping '{feature}' due to missing error data.")
            continue

        # Plot 1: Error Distribution
        plt.figure(figsize=(12, 6))
        sns.histplot(real_errors, color='skyblue', label=f'Real {validation_label} Error', kde=True, stat='density', bins=50)
        sns.histplot(synthetic_errors, color='red', label='Synthetic Error', kde=True, stat='density', bins=50)
        plt.title(f'Error Distribution for {feature.capitalize()}: Synthetic vs. Real {validation_label}')
        plt.legend()
        plt.savefig(os.path.join(plot_dir, f'{feature}_error_dist_{validation_label}.png'))
        plt.close()

        # Plot 2: Error vs. Lead Time
        plt.figure(figsize=(12, 6))
        sns.lineplot(data=validation_year_df, x='lead_time', y=f'{feature}_error', label=f'Real {validation_label} Error', errorbar='sd', color='blue')
        sns.lineplot(data=merged_synthetic, x='lead_time', y=f'{feature}_error', label='Synthetic Error', errorbar='sd', color='orange')
        plt.title(f'Error vs. Lead Time for {feature.capitalize()}: Synthetic vs. Real {validation_label}')
        plt.legend()
        plt.savefig(os.path.join(plot_dir, f'{feature}_error_vs_lead_{validation_label}.png'))
        plt.close()

        # Test: Kolmogorov-Smirnov
        ks_stat, p_val = stats.ks_2samp(real_errors, synthetic_errors)
        print(f"  Kolmogorov-Smirnov Test (vs. {validation_label}): KS Stat={ks_stat:.4f}, p-value={p_val:.4f}")