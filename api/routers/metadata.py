from typing import List

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select, insert

import api.db as db
from api.db import database
from api.schemas import PriceRegionIn, LocationIn, HouseholdIn
from api.helpers.formula_calculator import verify_formula

router = APIRouter(prefix="/metadata", tags=["metadata"])


# --- Regions ---

@router.post("/price_regions", response_model=PriceRegionIn)
async def create_region(region: PriceRegionIn):
    # Insert price region and return the created record in one operation
    query = (
        insert(db.price_regions_tbl)
        .values(
            name=region.name,
            bidding_zone_eic_code=region.bidding_zone_eic_code
        )
        .returning(
            db.price_regions_tbl.c.price_region_id,
            db.price_regions_tbl.c.name,
            db.price_regions_tbl.c.bidding_zone_eic_code
        )
    )
    created_region = await database.fetch_one(query)

    if not created_region:
        raise HTTPException(status_code=500, detail="Failed to create region")

    # Convert database row to response model
    return PriceRegionIn(price_region_id=created_region['price_region_id'], name=created_region['name'],
                         bidding_zone_eic_code=created_region['bidding_zone_eic_code'])


@router.get("/price_regions", response_model=List[PriceRegionIn])
async def get_regions(name: str | None = Query(None)):
    # Filter price regions by name if provided
    query = select(db.price_regions_tbl)
    if name:
        query = query.where(db.price_regions_tbl.c.name == name)

    regions = await database.fetch_all(query)

    # Convert database rows to response models
    return [PriceRegionIn(price_region_id=r['price_region_id'], name=r['name'],
                          bidding_zone_eic_code=r['bidding_zone_eic_code']) for r in regions]


@router.get("/price_regions/{price_region_id}", response_model=PriceRegionIn)
async def get_region(price_region_id: int):
    query = select(db.price_regions_tbl).where(db.price_regions_tbl.c.price_region_id == price_region_id)
    region = await database.fetch_one(query)

    if not region:
        raise HTTPException(status_code=404, detail="Region not found")

    return PriceRegionIn(price_region_id=region['price_region_id'], name=region['name'],
                         bidding_zone_eic_code=region['bidding_zone_eic_code'])


# --- Locations ---

@router.post("/locations", response_model=LocationIn)
async def create_location(location: LocationIn):
    # Validate that the referenced region exists before creating the location
    region_query = select(db.price_regions_tbl).where(
        db.price_regions_tbl.c.price_region_id == location.price_region_id)
    region = await database.fetch_one(region_query)

    if not region:
        raise HTTPException(
            status_code=404,
            detail=f"Price region with id {location.price_region_id} not found"
        )

    # Insert location with geographic coordinates and return the created record
    location_data = {
        "price_region_id": location.price_region_id,
        "name": location.name,
        "latitude": location.latitude,
        "longitude": location.longitude
    }

    query = (
        insert(db.locations_tbl)
        .values(**location_data)
        .returning(
            db.locations_tbl.c.location_id,
            db.locations_tbl.c.price_region_id,
            db.locations_tbl.c.name,
            db.locations_tbl.c.latitude,
            db.locations_tbl.c.longitude
        )
    )

    created_location = await database.fetch_one(query)

    if not created_location:
        raise HTTPException(status_code=500, detail="Failed to create location")

    # Use _mapping to convert row proxy to dict for response model
    return LocationIn(**created_location._mapping)


@router.get("/locations", response_model=List[LocationIn])
async def get_locations(price_region_id: int | None = Query(None)):
    # Filter locations by price_region_id if provided
    query = select(db.locations_tbl)
    if price_region_id:
        query = query.where(db.locations_tbl.c.price_region_id == price_region_id)

    locations = await database.fetch_all(query)

    # Convert database rows to response models using the _mapping attribute
    return [LocationIn(**loc._mapping) for loc in locations]


@router.get("/locations/{location_id}", response_model=LocationIn)
async def get_location(location_id: int):
    query = select(db.locations_tbl).where(db.locations_tbl.c.location_id == location_id)
    location = await database.fetch_one(query)

    if not location:
        raise HTTPException(status_code=404, detail="Location not found")

    return LocationIn(**location._mapping)


# --- Households ---

@router.post("/households", response_model=HouseholdIn)
async def create_household(household: HouseholdIn):
    # Validate that the referenced location exists before creating the household
    location_query = select(db.locations_tbl).where(db.locations_tbl.c.location_id == household.location_id)
    location = await database.fetch_one(location_query)

    if not location:
        raise HTTPException(
            status_code=404,
            detail=f"Location with id {household.location_id} not found"
        )

    # Verify the enduser_price_formula
    if household.enduser_price_formula and not verify_formula(household.enduser_price_formula):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid formula: {household.enduser_price_formula}"
        )

    # Insert household and return the created record
    query = (
        insert(db.households_tbl)
        .values(
            location_id=household.location_id,
            name=household.name,
            enduser_price_formula=household.enduser_price_formula,
            pv_tilt=household.pv_tilt,
            pv_azimuth=household.pv_azimuth,
            pv_capacity_kw=household.pv_capacity_kw,
            pv_performance_ratio=household.pv_performance_ratio,
            pv_temp_model_key=household.pv_temp_model_key,
            pv_module_temp_coeff_power=household.pv_module_temp_coeff_power,
            battery_capacity_kwh=household.battery_capacity_kwh,
            battery_efficiency=household.battery_efficiency,
            battery_max_charge_power=household.battery_max_charge_power,
            battery_max_discharge_power=household.battery_max_discharge_power
        )
        .returning(
            db.households_tbl.c.household_id,
            db.households_tbl.c.location_id,
            db.households_tbl.c.name,
            db.households_tbl.c.enduser_price_formula,
            db.households_tbl.c.pv_tilt,
            db.households_tbl.c.pv_azimuth,
            db.households_tbl.c.pv_capacity_kw,
            db.households_tbl.c.pv_performance_ratio,
            db.households_tbl.c.pv_temp_model_key,
            db.households_tbl.c.pv_module_temp_coeff_power,
            db.households_tbl.c.battery_capacity_kwh,
            db.households_tbl.c.battery_efficiency,
            db.households_tbl.c.battery_max_charge_power,
            db.households_tbl.c.battery_max_discharge_power
        )
    )

    created_household = await database.fetch_one(query)

    if not created_household:
        raise HTTPException(status_code=500, detail="Failed to create household")

    return HouseholdIn(**created_household._mapping)


@router.get("/households", response_model=List[HouseholdIn])
async def get_households(location_id: int | None = Query(None)):
    # Filter households by location_id if provided
    query = select(db.households_tbl)
    if location_id:
        query = query.where(db.households_tbl.c.location_id == location_id)

    households = await database.fetch_all(query)

    # Convert database rows to response models
    return [HouseholdIn(**hh._mapping) for hh in households]


@router.get("/households/{household_id}", response_model=HouseholdIn)
async def get_household(household_id: int):
    query = select(db.households_tbl).where(db.households_tbl.c.household_id == household_id)
    household = await database.fetch_one(query)

    if not household:
        raise HTTPException(status_code=404, detail="Household not found")

    return HouseholdIn(**household._mapping)
