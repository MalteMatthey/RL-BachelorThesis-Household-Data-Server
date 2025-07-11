import pandas as pd
import numpy as np
from datetime import timezone
from typing import List, Dict

from . import config

def preprocess_and_align_data(obs_data: List[Dict], fc_data: List[Dict]) -> pd.DataFrame:
    """
    Takes raw observation and forecast data, aligns them by time, and calculates errors.
    """
    print("  Preprocessing: Converting raw data to DataFrames.")
    obs_df = pd.DataFrame(obs_data)
    fc_df = pd.DataFrame(fc_data)

    if obs_df.empty or fc_df.empty:
        return pd.DataFrame()

    # --- FIX: Convert to UTC *before* any calculations ---
    # This is the critical step to prevent timezone-related miscalculations.
    obs_df['datetime'] = pd.to_datetime(obs_df['datetime']).dt.tz_convert(timezone.utc)
    fc_df['forecast_run'] = pd.to_datetime(fc_df['forecast_run']).dt.tz_convert(timezone.utc)
    fc_df['target_time'] = pd.to_datetime(fc_df['target_time']).dt.tz_convert(timezone.utc)
    
    # --- FIX: Ensure all feature columns are numeric ---
    # This prevents errors if a column contains None or non-numeric strings,
    # which can cause its dtype to be 'object'.
    for feature in config.WEATHER_FEATURES_TO_MODEL:
        if feature in obs_df.columns:
            # Coerce errors will turn non-numeric values into NaT/NaN
            obs_df[feature] = pd.to_numeric(obs_df[feature], errors='coerce')
            # Fill any resulting NaN values with 0 as a safe default
            obs_df[feature] = obs_df[feature].fillna(0)
        if feature in fc_df.columns:
            fc_df[feature] = pd.to_numeric(fc_df[feature], errors='coerce')
            fc_df[feature] = fc_df[feature].fillna(0)

    # Now, calculate lead_time on timezone-aware and standardized columns.
    fc_df['lead_time'] = (fc_df['target_time'] - fc_df['forecast_run']).dt.total_seconds() / 3600
    
    # Filter out any records where target_time is before forecast_run, which are invalid.
    fc_df = fc_df[fc_df['lead_time'] >= 0].copy()

    print("  Preprocessing: Aligning forecast and observation data...")
    
    # Set indices to ensure proper time-based alignment
    obs_df.set_index('datetime', inplace=True)
    fc_df.set_index('target_time', inplace=True)

    # Robustly find common features to avoid dropping data
    common_features = [f for f in config.WEATHER_FEATURES_TO_MODEL if f in obs_df.columns and f in fc_df.columns]
    print(f"    Identified {len(common_features)} common features for modeling.")

    obs_rename_map = {f: f"{f}_obs" for f in common_features}
    obs_df.rename(columns=obs_rename_map, inplace=True)

    fc_rename_map = {f: f"{f}_fc" for f in common_features}
    fc_df.rename(columns=fc_rename_map, inplace=True)

    # Merge based on the DatetimeIndex. This is more robust for time-series data.
    merged_df = pd.merge(
        fc_df, 
        obs_df, 
        left_index=True, 
        right_index=True,
        how='inner'
    )
    
    # The index is now the target_time/datetime, which we can rename.
    merged_df.index.name = 'target_time'
    merged_df.reset_index(inplace=True)

    if merged_df.empty:
        print("  Warning: Preprocessing resulted in an empty DataFrame. No matching obs/fc times found.")
        return pd.DataFrame()
        
    print(f"  Preprocessing: Aligned {len(merged_df)} forecast/observation pairs.")
    return merged_df

def create_feature_matrix(df: pd.DataFrame, feature: str) -> pd.DataFrame:
    """
    Creates the feature matrix (X) for a given weather feature.
    This includes time-based features and the observed value of the feature itself.
    """
    df_copy = df.copy()
    
    # Time-based features (from target_time or datetime index)
    time_col = df_copy.index
    if not isinstance(time_col, pd.DatetimeIndex):
        # Fallback for safety, though the index should be the primary source
        time_col = pd.to_datetime(df_copy.get('target_time'))

    # Use .dt accessor for pandas Series
    if isinstance(time_col, pd.Series):
        df_copy['time_of_day_sin'] = np.sin(2 * np.pi * time_col.dt.hour / 24)
        df_copy['time_of_day_cos'] = np.cos(2 * np.pi * time_col.dt.hour / 24)
        df_copy['day_of_year_sin'] = np.sin(2 * np.pi * time_col.dt.dayofyear / 365.25)
        df_copy['day_of_year_cos'] = np.cos(2 * np.pi * time_col.dt.dayofyear / 365.25)
    else:
        # For DatetimeIndex
        df_copy['time_of_day_sin'] = np.sin(2 * np.pi * time_col.hour / 24)
        df_copy['time_of_day_cos'] = np.cos(2 * np.pi * time_col.hour / 24)
        df_copy['day_of_year_sin'] = np.sin(2 * np.pi * time_col.dayofyear / 365.25)
        df_copy['day_of_year_cos'] = np.cos(2 * np.pi * time_col.dayofyear / 365.25)
    
    # Define the final feature set
    # The observed value is included as a feature as per the original logic
    final_feature_cols = config.MODEL_FEATURES + [f'{feature}_obs']

    return df_copy[final_feature_cols]