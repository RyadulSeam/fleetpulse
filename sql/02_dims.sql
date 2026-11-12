-- GOLD dimensions (loaded from data/processed/*.csv by pipeline/06_build_warehouse.py; reload is idempotent)
CREATE TABLE IF NOT EXISTS gold.dim_hub (
    hub_id int PRIMARY KEY, hub_name text NOT NULL, hub_capacity_orders_per_month int NOT NULL,
    lat double precision, lon double precision, timezone text NOT NULL);
CREATE TABLE IF NOT EXISTS gold.dim_driver (
    driver_id int PRIMARY KEY, driver_name text NOT NULL, employment_type text, hire_date date,
    experience_years int, performance_rating int, home_hub_id int);
CREATE TABLE IF NOT EXISTS gold.dim_vehicle (
    vehicle_id int PRIMARY KEY, purchase_date date, vehicle_model text, vehicle_status text,
    breakdown_count_total int, maintenance_alert boolean, vehicle_code text, vehicle_type text, home_hub_id int);
CREATE TABLE IF NOT EXISTS gold.dim_date (
    date date PRIMARY KEY, year int, quarter int, month int, month_name text, iso_week int,
    day_of_week int, day_name text, is_weekend boolean, is_holiday boolean, holiday_name text);
CREATE TABLE IF NOT EXISTS gold.weather_daily (
    hub_id int, date date, temp_c double precision, precip_mm double precision, wind_kmh double precision,
    weather_code int, weather_source text, is_severe_weather boolean, PRIMARY KEY (hub_id, date));
