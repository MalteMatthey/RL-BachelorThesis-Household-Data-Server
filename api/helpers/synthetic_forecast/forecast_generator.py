import pandas as pd
import numpy as np
import gc
from datetime import datetime, timedelta
from typing import List, Dict, Any

from . import config
from .utils import sample_from_quantiles
from .data_processing import create_feature_matrix

def generate_forecasts_for_run_date(
    run_date: pd.Timestamp,
    max_lead_time: int,
    start_time: datetime,
    end_time: datetime,
    loc_id: int,
    generation_obs_df: pd.DataFrame,
    feature_models: Dict[str, Dict[str, Any]],
    template_columns: List[str],
) -> List[Dict[str, Any]]:
    """
    Generates synthetic forecasts for a single forecast run date using a memory-optimized approach.
    """
    # Ensure all times are timezone-aware (UTC)
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=pd.Timestamp.utcnow().tzinfo or pd.Timestamp('UTC').tzinfo)
    if end_time.tzinfo is None:
        end_time = end_time.replace(tzinfo=pd.Timestamp.utcnow().tzinfo or pd.Timestamp('UTC').tzinfo)
    
    # Ensure run_date is UTC-aware
    if hasattr(run_date, 'tzinfo') and run_date.tzinfo is None:
        run_date = run_date.tz_localize('UTC')
    elif hasattr(run_date, 'tz_convert'):
        run_date = run_date.tz_convert('UTC')
    
    # Memory optimization: Calculate only needed lead times
    # Generate lead times from 0 up to the dynamically calculated max_lead_time
    lead_times = np.arange(0, max_lead_time + 1)
    target_times = [run_date + timedelta(hours=int(lt)) for lt in lead_times]
    
    # Make all target_times UTC-aware
    target_times = [t if t.tzinfo is not None else t.replace(tzinfo=start_time.tzinfo) for t in target_times]
    
    # Include target_times that are >= start_time
    valid_indices = [i for i, t in enumerate(target_times) if start_time <= t < end_time]
    if not valid_indices:
        return []
        
    target_times = [target_times[i] for i in valid_indices]
    lead_times = np.array([lead_times[i] for i in valid_indices])

    try:
        obs_rows = generation_obs_df.loc[target_times]
    except KeyError:
        return []

    # Memory optimization: Process features one by one instead of creating large matrices
    all_feature_errors = {}
    for feature, model_data in feature_models.items():
        try:
            quantile_model_dict = model_data['models']
            feature_max_lead = model_data['max_lead']

            # Create smaller batch DataFrame for just this feature
            batch_df = pd.DataFrame({
                'lead_time': lead_times,
                f'{feature}_obs': obs_rows[feature].values
            }, index=obs_rows.index)
            
            # Use more memory-efficient feature matrix creation
            X_batch = create_feature_matrix(batch_df, feature)
            known_lead_mask = X_batch['lead_time'] <= feature_max_lead
            X_batch_feature = X_batch[known_lead_mask]

            if X_batch_feature.empty:
                all_feature_errors[feature] = np.full(len(lead_times), np.nan)
                continue
            
            # Memory optimization: Process quantiles sequentially to reduce peak memory
            sampled_errors = np.zeros(len(X_batch_feature))
            quantile_predictions = {}
            
            for q, model in quantile_model_dict.items():
                quantile_predictions[q] = model.predict(X_batch_feature)
                
            # Convert to array format for sampling
            quantile_values = list(config.QUANTILES)
            quantile_preds_array = np.array([quantile_predictions[q] for q in quantile_values]).T
            
            # Generate random samples
            random_uniforms = np.random.uniform(0, 1, size=len(X_batch_feature))
            
            # Sample errors more efficiently
            for i, (row, u) in enumerate(zip(quantile_preds_array, random_uniforms)):
                sampled_errors[i] = sample_from_quantiles(quantile_values, row, u)
            
            # Store results
            full_length_errors = np.full(len(lead_times), np.nan)
            full_length_errors[known_lead_mask] = sampled_errors
            all_feature_errors[feature] = full_length_errors
            
            # Clean up intermediate variables
            del X_batch, X_batch_feature, quantile_predictions, quantile_preds_array
            
        except Exception as e:
            print(f"Warning: Error processing feature {feature}: {e}")
            all_feature_errors[feature] = np.full(len(lead_times), np.nan)

    # --- 3. Assemble Final Results ---
    synthetic_results = []
    for i in range(len(lead_times)):
        synthetic_row = {
            'location_id': loc_id,
            'forecast_run': run_date.to_pydatetime(),
            'target_time': target_times[i].to_pydatetime(),
        }
        obs_row = obs_rows.iloc[i]
        # Add modeled features by applying the simulated error
        for feature in feature_models.keys():
            if feature in all_feature_errors and not np.isnan(all_feature_errors[feature][i]):
                forecast_value = obs_row[feature] + all_feature_errors[feature][i]
                # Clamp non-negative and percentage features
                if feature in config.NON_NEGATIVE_FEATURES:
                    forecast_value = max(0, forecast_value)
                if feature in config.PERCENTAGE_FEATURES:
                    forecast_value = max(0, min(100, forecast_value))
                synthetic_row[feature] = round(forecast_value, 1)
            else:
                # If error is NaN (e.g., beyond max lead), the forecast is also NaN
                synthetic_row[feature] = float('nan')
        # Ensure all configured weather features are included; missing ones as NaN
        for feature in config.WEATHER_FEATURES_TO_MODEL:
            if feature not in feature_models.keys():
                synthetic_row[feature] = float('nan')
        # Add dummy forecast features with zero values
        for feature in config.DUMMY_FORECAST_FEATURES:
            synthetic_row[feature] = 0
        # Pass through non-modeled columns from the template to ensure exact format
        for col in template_columns:
            if col not in feature_models.keys() and col not in config.DUMMY_FORECAST_FEATURES and col in obs_row:
                synthetic_row[col] = obs_row[col]
        synthetic_results.append(synthetic_row)
    return synthetic_results