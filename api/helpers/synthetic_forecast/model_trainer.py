import time
import gc
import pandas as pd
import lightgbm as lgb
from typing import Dict, Any, List

from . import config
from .data_processing import create_feature_matrix

def train_model_for_feature(feature: str, df: pd.DataFrame, quantiles: List[float]) -> Dict[str, Any]:
    """
    Trains a SET of quantile regression models for a single weather feature.
    Memory-optimized version that cleans up intermediate data.
    """
    start_time = time.time()
    print(f"    Training models for feature: {feature}")

    # Memory optimization: Work with a smaller subset of data if needed
    feature_df = df[[col for col in df.columns if feature in col or col in ['target_time', 'forecast_run', 'lead_time']]].copy()
    
    # Calculate error and remove NaN values
    if f'{feature}_fc' in feature_df.columns and f'{feature}_obs' in feature_df.columns:
        feature_df['error'] = feature_df[f'{feature}_fc'] - feature_df[f'{feature}_obs']
    else:
        print(f"      Warning: Missing forecast or observation columns for {feature}")
        return {"models": {}, "max_lead": 0}
    
    feature_df.dropna(subset=['error'], inplace=True)
    
    if feature_df.empty:
        print(f"      Warning: No valid data for feature {feature}")
        return {"models": {}, "max_lead": 0}
    
    # Create feature matrix
    X_train = create_feature_matrix(feature_df, feature)
    y_train = feature_df['error']

    if X_train.empty:
        return {"models": {}, "max_lead": 0}

    max_feature_lead = X_train['lead_time'].max()
    quantile_models = {}
    
    # Memory optimization: Train models sequentially and clean up
    for i, q in enumerate(quantiles):
        print(f"      - Training for quantile: {q} ({i+1}/{len(quantiles)})")
        
        # Create model parameters
        params = config.LGBM_PARAMS.copy()
        params['alpha'] = q
        params['n_jobs'] = 1 # Explicitly set to 1 to avoid conflicts with joblib
        
        # Train model
        model = lgb.LGBMRegressor(**params)
        model.fit(X_train, y_train)  # Reduce verbosity
        quantile_models[q] = model
        
        # Clean up after training each model
        if i < len(quantiles) - 1:  # Don't collect on the last iteration
            gc.collect()
    
    # Clean up training data
    del feature_df, X_train, y_train
    gc.collect()
    
    end_time = time.time()
    print(f"    All models for '{feature}' trained in {end_time - start_time:.2f} seconds.")
    return {"models": quantile_models, "max_lead": max_feature_lead}