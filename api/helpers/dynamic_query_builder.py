from typing import List, Optional, Dict, Any, Set

# --- Constants and Configuration ---

# Table name constants
PRICE_TABLE = "electricity_prices"
PV_TABLE = "pv_generation"
LOAD_TABLE = "load_data"
OBS_TABLE = "weather_observations"
FC_TABLE = "weather_forecasts"

# Map CTE names to SQL aliases used in SELECT expressions
CTE_ALIASES = {
    "price_data": "pr",
    "pv_data": "pv",
    "load_data": "ld",
    "weather_observation_data": "wo",
    "forecast_data": "fc"
}

# Database column names for weather observations
OBS_DB_COLUMNS = [
    "temp", "tempmin", "tempmax", "feelslike", "feelslikemax", "feelslikemin",
    "humidity", "dew", "precip", "precipprob", "precipcover",
    "snow", "snowdepth", "windgust", "windspeed", "winddir", "pressure",
    "cloudcover", "visibility", "solarradiation", "solarenergy", "uvindex",
    "severerisk", "windspeedmax", "windspeedmean", "windspeedmin", "sunrise",
    "sunset", "moonphase", "conditions", "windspeed50", "winddir50",
    "windspeed80", "winddir80", "windspeed100", "winddir100", "ghiradiation",
    "dniradiation", "difradiation", "sunelevation"
]

# Pydantic field names for ForecastEntry
FORECAST_ENTRY_FIELDS = [
    "forecast_run", "target_time", "temp", "tempmin", "tempmax", "feelslikemax",
    "feelslikemin", "feelslike", "dew", "humidity", "precip", "precipprob",
    "precipcover", "snow", "snowdepth", "windgust", "windspeed",
    "winddir", "pressure", "cloudcover", "visibility", "solarradiation",
    "solarenergy", "uvindex", "severerisk", "windspeedmax", "windspeedmean",
    "windspeedmin", "sunrise", "sunset", "moonphase", "conditions",
    "windspeed50", "winddir50", "windspeed80", "winddir80", "windspeed100",
    "winddir100", "ghiradiation", "dniradiation", "difradiation", "sunelevation"
]

# Field Configuration
FIELD_CONFIG: Dict[str, Dict[str, Any]] = {
    "price_region_id": {
        "main_select_expr": f"{CTE_ALIASES['price_data']}.\"price_region_id\"",
        "cte_dependency": "price_data", "cte_source_column": "price_region_id", "cte_alias": "price_region_id",
        "cte_table": PRICE_TABLE, "cte_time_column": "time", "cte_filter_column_name": "price_region_id",
    },
    "raw_price_eur_mwh": {
        "main_select_expr": f"{CTE_ALIASES['price_data']}.\"price_eur_mwh\"",
        "cte_dependency": "price_data", "cte_source_column": "price_eur_mwh", "cte_alias": "price_eur_mwh",
        "cte_table": PRICE_TABLE, "cte_time_column": "time", "cte_filter_column_name": "price_region_id",
    },
    "pv_generation_kwh": {
        "main_select_expr": f"{CTE_ALIASES['pv_data']}.\"generation_kwh\"",
        "cte_dependency": "pv_data", "cte_source_column": "generation_kwh", "cte_alias": "generation_kwh",
        "cte_table": PV_TABLE, "cte_time_column": "time", "cte_filter_column_name": "household_id",
    },
    "load_consumption_kwh": {
        "main_select_expr": f"{CTE_ALIASES['load_data']}.\"consumption_kwh\"",
        "cte_dependency": "load_data", "cte_source_column": "consumption_kwh", "cte_alias": "consumption_kwh",
        "cte_table": LOAD_TABLE, "cte_time_column": "time", "cte_filter_column_name": "household_id",
    },
    "forecasts": {
        "main_select_expr": f"{CTE_ALIASES['forecast_data']}.\"forecasts\"",
        "requires_forecast_join": True,
        "cte_dependency": None,
    }
}

obs_cte_name_key = "weather_observation_data"
obs_cte_alias_in_main_query = CTE_ALIASES.get(obs_cte_name_key, obs_cte_name_key)
for db_col_name in OBS_DB_COLUMNS:
    api_field_key = f"obs_{db_col_name}"
    FIELD_CONFIG[api_field_key] = {
        "main_select_expr": f"{obs_cte_alias_in_main_query}.\"{api_field_key}\"",
        "cte_dependency": obs_cte_name_key,
        "cte_source_column": db_col_name,
        "cte_alias": api_field_key,
        "cte_table": OBS_TABLE,
        "cte_time_column": "datetime",
        "cte_filter_column_name": "location_id",
    }

REQUESTABLE_DB_FIELDS: List[str] = list(FIELD_CONFIG.keys())

# --- SQL Generation Helper Functions ---

def _quote_sql_identifier(name: str) -> str:
    """Quotes a SQL identifier (table or column name)."""
    if not isinstance(name, str):
        raise TypeError("Identifier must be a string")
    return f'"{name.replace("\"", "\"\"")}"' # Basic quoting, replace " with ""

def _format_sql_value(value: Any) -> str:
    """Formats a Python value into a SQL literal string."""
    if value is None:
        return "NULL"
    if isinstance(value, (int, float)):
        return str(value)
    # Basic SQL injection protection for strings
    return f"'{str(value).replace('\'', '\'\'')}'"


def _determine_selected_fields(requested_fields_input: Optional[List[str]]) -> Set[str]:
    """Determines the set of fields to include in the query."""
    if not requested_fields_input:
        return set(REQUESTABLE_DB_FIELDS)
    return set(requested_fields_input)


def _prepare_query_components(
    selected_fields: Set[str],
    household_id: int,
    location_id: int,
    price_region_id: int
) -> tuple[Set[str], Dict[str, Dict[str, Any]]]:
    """
    Initializes main SELECT expressions and gathers information for CTEs.
    """
    main_select_expressions: Set[str] = {f"ms.ts AS {_quote_sql_identifier('timestamp')}"}
    ctes_to_build_info: Dict[str, Dict[str, Any]] = {}

    for field_name in selected_fields:
        if field_name not in FIELD_CONFIG:
            continue

        config = FIELD_CONFIG[field_name]
        main_select_expressions.add(config["main_select_expr"])

        if config.get("cte_dependency"):
            cte_name = config["cte_dependency"]
            if cte_name not in ctes_to_build_info:
                filter_value: Any = None
                filter_col_name = config.get("cte_filter_column_name")

                if filter_col_name == "price_region_id":
                    filter_value = price_region_id
                elif filter_col_name == "household_id":
                    filter_value = household_id
                elif filter_col_name == "location_id":
                    filter_value = location_id
                
                if filter_value is None and filter_col_name is not None:
                    raise ValueError(
                        f"Filter value not determined for CTE {cte_name} "
                        f"with filter column {filter_col_name}"
                    )

                ctes_to_build_info[cte_name] = {
                    "table": config["cte_table"],
                    "time_col": config["cte_time_column"],
                    "filter_col_name": filter_col_name,
                    "filter_val": filter_value,
                    "locf_expressions": set(),  # Stores (source_db_col, alias_in_cte)
                }
            ctes_to_build_info[cte_name]["locf_expressions"].add(
                (config["cte_source_column"], config["cte_alias"])
            )
    return main_select_expressions, ctes_to_build_info


def _build_minute_series_cte_sql(start_str: str, end_str: str) -> str:
    """Builds the SQL for the minute_series CTE."""
    return f"minute_series AS (SELECT generate_series('{start_str}'::timestamptz, '{end_str}'::timestamptz, '1 minute') AS ts)"


def _build_locf_cte_sql(cte_name: str, info: Dict[str, Any]) -> str:
    """Builds SQL for a single LOCF CTE using LATERAL JOIN."""
    internal_source_table_alias = _quote_sql_identifier("_source_tbl")
    lateral_join_block_alias = _quote_sql_identifier("_lj")

    lateral_subquery_select_parts = []
    cte_select_list_parts = ["ms.ts"] # ms.ts is from the outer scope for this CTE

    sorted_locf_expressions = sorted(list(info.get("locf_expressions", set())))

    if not sorted_locf_expressions: # Should not happen if config is correct
        return "" 

    for db_col, cte_col_alias in sorted_locf_expressions:
        q_db_col = _quote_sql_identifier(db_col)
        q_cte_col_alias = _quote_sql_identifier(cte_col_alias)
        lateral_subquery_select_parts.append(f"{internal_source_table_alias}.{q_db_col} AS {q_cte_col_alias}")
        cte_select_list_parts.append(f"{lateral_join_block_alias}.{q_cte_col_alias}")
    
    lateral_subquery_select_expr_str = ", ".join(lateral_subquery_select_parts)
    cte_select_expr_str = ", ".join(cte_select_list_parts)
    
    q_table = _quote_sql_identifier(info['table'])
    q_filter_col_name = _quote_sql_identifier(info['filter_col_name'])
    q_time_col = _quote_sql_identifier(info['time_col'])
    filter_val_sql = _format_sql_value(info['filter_val'])

    return f"""
    {_quote_sql_identifier(cte_name)} AS (
      SELECT
        {cte_select_expr_str}
      FROM minute_series ms
      LEFT JOIN LATERAL (
        SELECT
          {lateral_subquery_select_expr_str}
        FROM {q_table} AS {internal_source_table_alias}
        WHERE {internal_source_table_alias}.{q_filter_col_name} = {filter_val_sql}
          AND {internal_source_table_alias}.{q_time_col} <= ms.ts
        ORDER BY {internal_source_table_alias}.{q_time_col} DESC
        LIMIT 1
      ) {lateral_join_block_alias} ON true
    )"""


def _build_forecast_join_sql(
    location_id: int,
    forecast_fields_input: Optional[List[str]],
    fc_table_name: str,
    fc_cte_alias: str # This is the alias for the LATERAL subquery block, e.g., "fc"
) -> str:
    """Builds the SQL for the forecast LATERAL JOIN clause."""
    ff_to_select = set(FORECAST_ENTRY_FIELDS)
    if forecast_fields_input:
        ff_to_select = set(forecast_fields_input)
    ff_to_select.add("forecast_run") # Essential for logic and data models
    ff_to_select.add("target_time")  # Essential for ordering and data models

    json_build_object_args = [
        f"'{field}', wf.{_quote_sql_identifier(field)}" 
        for field in sorted(list(ff_to_select))
    ]
    
    q_fc_table_name = _quote_sql_identifier(fc_table_name)
    q_fc_cte_alias = _quote_sql_identifier(fc_cte_alias)
    
    # wf_alias and fr2_alias are internal to this SQL block
    wf_alias = _quote_sql_identifier("wf") 
    fr2_alias = _quote_sql_identifier("fr2")

    return f"""
    LEFT JOIN LATERAL (
      SELECT
        COALESCE(
          jsonb_agg(
            jsonb_build_object({', '.join(json_build_object_args)})
            ORDER BY {wf_alias}."target_time" ASC
          ),
          '[]'::jsonb
        ) AS "forecasts" -- This is the column name selected, must match FIELD_CONFIG
      FROM {q_fc_table_name} AS {wf_alias}
      WHERE {wf_alias}."location_id" = {_format_sql_value(location_id)}
        AND {wf_alias}."forecast_run" = (
          SELECT MAX({fr2_alias}."forecast_run")
          FROM {q_fc_table_name} AS {fr2_alias}
          WHERE {fr2_alias}."location_id" = {_format_sql_value(location_id)}
            AND {fr2_alias}."forecast_run" <= ms.ts -- ms.ts is from the outer query context
        )
        AND {wf_alias}."target_time" > ms.ts
        AND {wf_alias}."target_time" <= ms.ts + interval '7 days'
    ) {q_fc_cte_alias} ON true"""


# --- Main Query Builder Function ---

def build_rl_agent_state_query(
    requested_fields_input: Optional[List[str]],
    forecast_fields_input: Optional[List[str]],
    household_id: int,
    location_id: int,
    price_region_id: int,
    start_str: str,
    end_str: str
) -> str:
    """
    Builds the SQL query for RL Agent State dynamically based on requested fields.
    """
    selected_fields = _determine_selected_fields(requested_fields_input)
    
    main_select_expressions, ctes_to_build_info = _prepare_query_components(
        selected_fields, household_id, location_id, price_region_id
    )

    cte_definitions: Dict[str, str] = {}
    main_join_clauses: List[str] = []

    # 1. Minute Series CTE
    cte_definitions["minute_series"] = _build_minute_series_cte_sql(start_str, end_str)

    # 2. LOCF CTEs
    for cte_name, info in ctes_to_build_info.items():
        cte_sql = _build_locf_cte_sql(cte_name, info)
        if cte_sql: # Only add if CTE sql was generated
            cte_definitions[cte_name] = cte_sql.strip()
            
            # Add JOIN clause for this CTE to the main query
            # The alias for the CTE in the main query's FROM clause
            main_query_cte_alias = CTE_ALIASES.get(cte_name, cte_name) 
            q_cte_name = _quote_sql_identifier(cte_name)
            q_main_query_cte_alias = _quote_sql_identifier(main_query_cte_alias)
            main_join_clauses.append(
                f"LEFT JOIN {q_cte_name} AS {q_main_query_cte_alias} "
                f"ON ms.ts = {q_main_query_cte_alias}.ts"
            )
            
    # 3. Forecasts LATERAL JOIN (if requested)
    if "forecasts" in selected_fields:
        fc_cte_alias = CTE_ALIASES['forecast_data'] # Alias for the forecast lateral join block, e.g., "fc"
        forecast_join_sql_clause = _build_forecast_join_sql(
            location_id,
            forecast_fields_input,
            FC_TABLE,
            fc_cte_alias
        )
        main_join_clauses.append(forecast_join_sql_clause.strip())

    # Assemble the final query
    ordered_cte_names = ["minute_series"] + sorted(
        [name for name in cte_definitions if name != "minute_series"]
    )
    with_clause_str = "WITH " + ",\n".join(
        cte_definitions[name] for name in ordered_cte_names if name in cte_definitions
    )

    select_clause_str = "SELECT\n  " + ",\n  ".join(sorted(list(main_select_expressions)))
    from_clause_str = "FROM minute_series ms"
    join_clauses_str = "\n".join(main_join_clauses)

    final_sql = f"""
{with_clause_str}
{select_clause_str}
{from_clause_str}
{join_clauses_str}
ORDER BY ms.ts ASC
"""
    return final_sql.strip()