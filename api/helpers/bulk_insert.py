from typing import List, Dict, Any

from sqlalchemy.dialects.postgresql import insert as pg_insert
from math import floor

from api.db import database


def chunkify(records: list, chunk_size: int):
    """Generator that yields chunks of records."""
    for i in range(0, len(records), chunk_size):
        yield records[i: i + chunk_size]


async def insert_records(
        records: List[Dict[str, Any]],
        table,
        label: str,
        *,
        unique_keys: List[str]
):
    """
    Insert or update in chunks so we don't exceed Postgres' parameter limit.
    """
    if not records:
        return

    # how many columns per row
    # Ensure there's at least one record to get keys from, and all records have same keys.
    if not records[0]:
        print(f"Warning: First record for {label} is empty, cannot determine columns per row.")
        return

    cols_per_row = len(records[0].keys())
    if cols_per_row == 0:
        print(f"Warning: No columns found in records for {label}, skipping insertion.")
        return

    max_args = 32767  # PostgreSQL default limit for bind parameters
    # floor so we never exceed the limit
    rows_per_batch = floor(max_args / cols_per_row) or 1

    print(f"Preparing to insert/update {len(records)} {label} records in batches of up to {rows_per_batch}...")

    processed_total = 0
    for batch_idx, batch in enumerate(chunkify(records, rows_per_batch)):
        if not batch:
            continue

        insert_stmt = pg_insert(table).values(batch)

        update_values = {
            col.name: insert_stmt.excluded[col.name]
            for col in table.columns
            if col.name not in unique_keys
        }

        if not update_values:
            upsert_query = insert_stmt.on_conflict_do_nothing(
                index_elements=unique_keys
            )
        else:
            upsert_query = insert_stmt.on_conflict_do_update(
                index_elements=unique_keys,
                set_=update_values
            )

        try:
            await database.execute(upsert_query)
            processed_total += len(batch)
        except Exception as e:
            print(f"Error during batch insert/update for {label} (batch {batch_idx + 1}, {len(batch)} records): {e}")
            raise  # Re-raise the exception to be handled by the caller

    print(f"Successfully processed {processed_total} {label} records.")
