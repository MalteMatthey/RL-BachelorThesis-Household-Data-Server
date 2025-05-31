from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional


def build_continuous_ranges(
    times: List[datetime],
    requested_start: datetime,
    requested_end: datetime
) -> List[Tuple[datetime, datetime]]:
    """
    Build continuous hourly ranges from sorted timestamps, splitting on gaps >1 hour.
    """
    if not times:
        return []
    ranges: List[Tuple[datetime, datetime]] = []
    # Initialize current range start at first timestamp bounded by request
    cur_start = max(times[0], requested_start)
    prev = times[0]
    for t in times[1:]:
        if (t - prev) > timedelta(hours=1):
            ranges.append((cur_start, prev))
            cur_start = t
        prev = t
    # Close last range bounded by request
    ranges.append((cur_start, min(prev, requested_end)))
    return ranges


def calculate_missing_time_ranges(
        requested_start: datetime,
        requested_end: datetime,
        existing_ranges: List[Tuple[datetime, datetime]]
) -> List[Tuple[datetime, datetime]]:
    """
    Calculate missing time ranges that need to be fetched.
    Returns a list of (start, end) tuples representing gaps in the existing data.
    """
    if not existing_ranges:
        return [(requested_start, requested_end)]
    
    # Sort existing ranges by start time
    sorted_ranges = sorted(existing_ranges, key=lambda x: x[0])
    missing_ranges = []
    
    # Check if we need data before the first existing range
    first_start = sorted_ranges[0][0]
    if requested_start < first_start:
        missing_ranges.append((requested_start, min(first_start, requested_end)))
    
    # Check for gaps between existing ranges
    for i in range(len(sorted_ranges) - 1):
        current_end = sorted_ranges[i][1]
        next_start = sorted_ranges[i + 1][0]
        
        if current_end < next_start:
            gap_start = max(current_end, requested_start)
            gap_end = min(next_start, requested_end)
            if gap_start < gap_end:
                missing_ranges.append((gap_start, gap_end))
    
    # Check if we need data after the last existing range
    last_end = sorted_ranges[-1][1]
    if requested_end > last_end:
        missing_ranges.append((max(last_end, requested_start), requested_end))
    
    return missing_ranges


def calculate_overlap(
        min1: Optional[datetime], max1: Optional[datetime],
        min2: Optional[datetime], max2: Optional[datetime]
) -> Tuple[Optional[datetime], Optional[datetime]]:
    """Calculates the overlapping time range between two intervals."""
    if not all([min1, max1, min2, max2]):
        return None, None  # No overlap if one range is missing

    overlap_start = max(min1, min2)
    overlap_end = min(max1, max2)

    if overlap_start < overlap_end:
        return overlap_start, overlap_end
    else:
        return None, None  # No overlap


def calculate_household_time_ranges(records: List[Dict]) -> Dict[int, Tuple[datetime, datetime]]:
    """
    Calculate individual time ranges for each household from the records.
    Returns a dictionary mapping household_id to (min_time, max_time) for that household.
    """
    household_time_ranges = {}
    
    for record in records:
        household_id = record['household_id']
        time = record['time']
        
        if household_id not in household_time_ranges:
            household_time_ranges[household_id] = [time, time]
        else:
            current_min, current_max = household_time_ranges[household_id]
            household_time_ranges[household_id] = [
                min(current_min, time),
                max(current_max, time)
            ]
    
    # Convert lists to tuples
    return {hid: (min_time, max_time) for hid, (min_time, max_time) in household_time_ranges.items()}


def calculate_location_time_ranges(
    household_time_ranges: Dict[int, Tuple[datetime, datetime]],
    household_to_location: Dict[int, int]
) -> Dict[int, Tuple[datetime, datetime]]:
    """
    Calculate time ranges for each location based on households at that location.
    Returns a dictionary mapping location_id to (min_time, max_time) for that location.
    """
    location_time_ranges = {}
    
    for household_id, (start_time, end_time) in household_time_ranges.items():
        location_id = household_to_location[household_id]
        
        if location_id not in location_time_ranges:
            location_time_ranges[location_id] = [start_time, end_time]
        else:
            current_min, current_max = location_time_ranges[location_id]
            location_time_ranges[location_id] = [
                min(current_min, start_time),
                max(current_max, end_time)
            ]
    
    # Convert lists to tuples
    return {loc_id: (min_time, max_time) for loc_id, (min_time, max_time) in location_time_ranges.items()}
