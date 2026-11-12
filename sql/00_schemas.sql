-- Medallion layout: bronze = raw immutable events, silver = cleaned/modelled entities, gold = business-ready marts
CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;
