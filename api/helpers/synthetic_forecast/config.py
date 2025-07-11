# Define the weather features you want to model the error for.
# These column names must be present in both observation and forecast data.
WEATHER_FEATURES_TO_MODEL = [
    'temp', 'tempmax', 'tempmin',
    'feelslike', 'feelslikemax', 'feelslikemin',
    'dew', 'humidity',
    'precip', 'precipprob', 'precipcover',
    'snow', 'snowdepth',
    'windgust', 'windspeed', 'winddir',
    'windspeed50',
    'windspeed80',
    'windspeed100',
    'windspeedmax', 'windspeedmean', 'windspeedmin',
    'pressure', 'cloudcover', 'visibility',
    'solarradiation', 'solarenergy', 'uvindex'
]

# Features that must be non-negative
NON_NEGATIVE_FEATURES = [
    'precip', 'precipcover', 'snow', 'snowdepth', 'windgust', 'windspeed', 
    'windspeedmax', 'windspeedmean', 'windspeedmin', 'windspeed50', 
    'windspeed80', 'windspeed100', 'visibility', 'solarradiation', 
    'solarenergy', 'uvindex', 'ghiradiation', 'dniradiation', 'difradiation'
]

# Features that are percentages and should be clamped between 0 and 100
PERCENTAGE_FEATURES = ['humidity', 'precipprob', 'cloudcover']

# Dummy features (forecast only)
DUMMY_FORECAST_FEATURES = ['severerisk']

# Quantiles to be used for the quantile regression model.
# This list is used for both training and prediction.
QUANTILES = [0.1, 0.25, 0.5, 0.75, 0.9]

# LightGBM model parameters for the quantile regression.
LGBM_PARAMS = {
    'objective': 'quantile',
    'metric': 'quantile',
    'n_estimators': 500,
    'num_leaves': 61,
    'learning_rate': 0.05,
    'feature_fraction': 0.8,
    'bagging_fraction': 0.8,
    'bagging_freq': 1,
    'n_jobs': 1,  # Set to 1 because we parallelize training over features
    'verbose': -1,
    'seed': 42
}

# Features to be engineered from timestamps and used by the model.
MODEL_FEATURES = [
    'lead_time',
    'time_of_day_sin', 'time_of_day_cos',
    'day_of_year_sin', 'day_of_year_cos'
]