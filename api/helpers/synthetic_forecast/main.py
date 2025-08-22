import pandas as pd
import time
import gc
from datetime import timezone, timedelta
import datetime
from typing import List, Dict, Any
from joblib import Parallel, delayed
import numpy as np

from . import config
from .data_processing import preprocess_and_align_data
from .model_trainer import train_model_for_feature
from .forecast_generator import generate_forecasts_for_run_date
from .utils import get_forecast_template_columns, calculate_max_lead_time

# Memory optimization constants
MAX_PARALLEL_JOBS = 4  # Limit parallel jobs to reduce memory usage
CHUNK_SIZE = 100  # Process forecast runs in chunks

async def create_synthetic_forecast(
    loc_id: int,
    start_time: datetime,
    end_time: datetime,
    pre_2020_obs_data: List[Dict],
    all_historical_obs: List[Dict],
    all_historical_fc: List[Dict]
) -> tuple[List[Dict[str, Any]], pd.DataFrame, pd.DataFrame]:
    """
    Generates synthetic weather forecasts by orchestrating the data processing,
    model training, and generation steps. This function is designed to be called
    by an API.
    
    Returns:
        tuple: (synthetic_results, validation_df, test_df)
    """
    print("Starting synthetic forecast generation process...")
    if not all_historical_obs or not all_historical_fc or not pre_2020_obs_data:
        print("Warning: Missing required historical or pre-2020 observation data. Aborting.")
        return [], pd.DataFrame(), pd.DataFrame()

    learning_df = preprocess_and_align_data(all_historical_obs, all_historical_fc)
    if learning_df.empty:
        print("Error: Data preprocessing failed. Aborting.")
        return [], pd.DataFrame(), pd.DataFrame()

    # Memory optimization: Create smaller DataFrames and clean up immediately

    ### PRODUCTION API ###
    #train_df = learning_df[learning_df['target_time'].dt.year >= 2020].copy()
    #validation_df = pd.DataFrame()
    #test_df = pd.DataFrame()

    ### TESTING ###
    train_df = learning_df[learning_df['target_time'].dt.year >= 2021].copy()
    validation_df = learning_df[learning_df['target_time'].dt.year == 2020].copy()
    test_df = pd.DataFrame()
    
    # Clear the large learning_df from memory
    del learning_df
    gc.collect()
    
    for feature in config.WEATHER_FEATURES_TO_MODEL:
        for df in [validation_df, test_df]:
            if not df.empty:
                df[f'{feature}_error'] = df[f'{feature}_fc'] - df[f'{feature}_obs']

    print(f"\nTraining error models for {len(config.WEATHER_FEATURES_TO_MODEL)} features...")
    # Use a thread-based backend for parallelism. This is efficient because
    # LightGBM releases the GIL during training, allowing threads to run on multiple cores.
    trained_models_list = Parallel(n_jobs=MAX_PARALLEL_JOBS, backend="threading")(
        delayed(train_model_for_feature)(feature, train_df, config.QUANTILES)
        for feature in config.WEATHER_FEATURES_TO_MODEL
    )
    feature_models = {feat: model for feat, model in zip(config.WEATHER_FEATURES_TO_MODEL, trained_models_list) if model}
    
    # Clear training data from memory
    del train_df
    gc.collect()
    
    if not feature_models:
        print("Error: No models were trained successfully. Aborting generation.")
        return [], pd.DataFrame(), pd.DataFrame()
    print(f"\nSuccessfully trained {len(feature_models)} models.")

    print("\nPreparing for generation phase...")
    generation_obs_df = pd.DataFrame(pre_2020_obs_data)
    generation_obs_df['datetime'] = pd.to_datetime(generation_obs_df['datetime']).dt.tz_convert(timezone.utc)
    
    # Clean all weather feature columns to ensure they are numeric
    for feature in config.WEATHER_FEATURES_TO_MODEL:
        if feature in generation_obs_df.columns:
            generation_obs_df[feature] = pd.to_numeric(generation_obs_df[feature], errors='coerce')
            generation_obs_df[feature] = generation_obs_df[feature].fillna(0)
    
    generation_obs_df.set_index('datetime', inplace=True)
    generation_obs_df.sort_index(inplace=True)

    # Forward-fill missing values to ensure continuity
    generation_obs_df.ffill(inplace=True)
    print("  Forward-filled missing values in generation observation data.")

    start_time_utc = start_time.astimezone(timezone.utc)
    end_time_utc = end_time.astimezone(timezone.utc)

    template_columns = get_forecast_template_columns(all_historical_fc)
    max_lead_time = calculate_max_lead_time(all_historical_fc)

    run_dates = pd.to_datetime(generation_obs_df.index.date).unique()
    
    # Final Fix: Correctly determine the range of run dates needed.
    # To get a forecast FOR `start_time_utc`, we need a run from `start_time_utc - max_lead_time`.
    min_run_date_needed = (start_time_utc - timedelta(hours=max_lead_time)).date()
    
    # To get a forecast FOR `end_time_utc`, the latest run we need is on `end_time_utc` itself.
    # Any run after this date is not needed.
    max_run_date_needed = end_time_utc.date()

    # Filter the available run_dates to only those within our needed window.
    run_dates = run_dates[
        (run_dates >= pd.to_datetime(min_run_date_needed)) & 
        (run_dates <= pd.to_datetime(max_run_date_needed))
    ]

    print(f"Generating synthetic data for {len(run_dates)} forecast runs...")
    print(f"Processing in chunks of {CHUNK_SIZE} to conserve memory...")
    
    start_gen_time = time.time()
    synthetic_results = []
    
    # Memory optimization: Process in chunks instead of all at once
    for i in range(0, len(run_dates), CHUNK_SIZE):
        chunk_end = min(i + CHUNK_SIZE, len(run_dates))
        chunk_dates = run_dates[i:chunk_end]
        
        print(f"Processing chunk {i//CHUNK_SIZE + 1}/{(len(run_dates)-1)//CHUNK_SIZE + 1} ({len(chunk_dates)} runs)")
        
        # Use a thread-based backend for generation to avoid data serialization overhead
        chunk_results = Parallel(n_jobs=min(MAX_PARALLEL_JOBS, len(chunk_dates)), backend="threading")(
            delayed(generate_forecasts_for_run_date)(
                run_date, max_lead_time, start_time_utc, end_time_utc, loc_id,
                generation_obs_df, feature_models, template_columns
            ) for run_date in chunk_dates
        )
        
        # Flatten and add to results
        chunk_flattened = [item for sublist in chunk_results for item in sublist]
        synthetic_results.extend(chunk_flattened)
        
        # Clean up memory after each chunk
        del chunk_results, chunk_flattened
        gc.collect()
    
    end_gen_time = time.time()
    print(f"Chunked generation completed in {end_gen_time - start_gen_time:.2f} seconds.")
    
    # Deduplicate results before returning
    if synthetic_results:
        print(f"Deduplicating {len(synthetic_results)} generated forecast points...")
        # Convert list of dicts to a set of tuples to remove duplicates, then back to a list of dicts
        unique_results_set = {tuple(sorted(d.items())) for d in synthetic_results}
        synthetic_results = [dict(t) for t in unique_results_set]
        print(f"Successfully generated {len(synthetic_results)} unique synthetic forecast points.")

        # Convert to DataFrame for easy NaN handling
        results_df = pd.DataFrame(synthetic_results)
        # Replace numpy.nan with None for JSON/DB compatibility
        results_df.replace({np.nan: None}, inplace=True)
        # Convert back to list of dictionaries
        synthetic_results = results_df.to_dict('records')
        print("Cleaned NaN values from synthetic forecast results.")
    else:
        print("No synthetic forecast points were generated.")

    return synthetic_results, validation_df, test_df