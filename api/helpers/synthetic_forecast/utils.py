import pandas as pd
from typing import List, Dict

def sample_from_quantiles(quantiles: List[float], quantile_predictions: List[float], u: float) -> float:
    """
    Linearly interpolates to sample a value from a predicted quantile distribution.
    Handles u in the range [0, 1].
    """
    if u < quantiles[0]:
        return quantile_predictions[0]
    if u > quantiles[-1]:
        return quantile_predictions[-1]

    for i in range(len(quantiles) - 1):
        if quantiles[i] <= u <= quantiles[i + 1]:
            q_low, q_high = quantiles[i], quantiles[i + 1]
            pred_low, pred_high = quantile_predictions[i], quantile_predictions[i + 1]
            if q_high == q_low:
                return pred_low
            weight = (u - q_low) / (q_high - q_low)
            return pred_low + weight * (pred_high - pred_low)
            
    return quantile_predictions[-1]

def get_forecast_template_columns(historical_fc_data: List[Dict]) -> List[str]:
    """
    Extract all column names from historical forecast data to ensure exact format match.
    """
    if not historical_fc_data:
        return []
    
    sample_record = historical_fc_data[0]
    exclude_cols = {'forecast_run', 'target_time'}
    return [col for col in sample_record.keys() if col not in exclude_cols]

def calculate_max_lead_time(historical_fc_data: List[Dict]) -> int:
    """
    Dynamically calculate the maximum lead time from historical forecast data.
    """
    if not historical_fc_data:
        return 168  # Default to 7 days
    
    fc_df = pd.DataFrame(historical_fc_data)
    fc_df['forecast_run'] = pd.to_datetime(fc_df['forecast_run'])
    fc_df['target_time'] = pd.to_datetime(fc_df['target_time'])
    fc_df['lead_time'] = (fc_df['target_time'] - fc_df['forecast_run']).dt.total_seconds() / 3600
    
    max_lead_time = int(fc_df['lead_time'].max())
    print(f"  Dynamically calculated max lead time: {max_lead_time} hours")
    return max_lead_time