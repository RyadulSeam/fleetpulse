# Step 01 – Raw data profile

## Orders  (27,979 rows, source encoding `utf-16`)

| column | dtype | nulls | distinct | sample |
|---|---|---|---|---|
| Order ID | int64 | 0 | 27,979 | 1, 2, 3 |
| Actual Delivery Date | str | 252 | 735 | 25-10-2024, 16-06-2024, 05-07-2024 |
| Delay Reason | str | 22,071 | 10 | Severe Weather, Customer Not Home, Incorrect Address |
| Driver ID | int64 | 0 | 55 | 43, 29, 25 |
| Driver Name | str | 0 | 53 | Karen Rodriguez, Matthew Williams, Nancy Harris |
| Hub Name | str | 0 | 6 | San Antonio Hub, Houston Hub, Austin Hub |
| Is Delayed | bool | 0 | 2 | False, True |
| Is On Time | bool | 0 | 2 | True, False |
| Order Date | str | 0 | 731 | 25-10-2024, 16-06-2024, 05-07-2024 |
| Order Status | str | 0 | 2 | Delivered, Cancelled |
| Vehicle Name | str | 0 | 41 | FT-036, FT-016, FT-040 |
| Vehicle Type | str | 0 | 4 | Truck, Van, Pickup |
| Customer Satisfaction Score | int64 | 0 | 5 | 4, 5, 3 |
| Delivery Time Hours | float64 | 252 | 7,989 | 6.81, 5.74, 12.91 |
| Hub Processing Time Hours | float64 | 0 | 376 | 0.89, 3.6, 2.07 |

Duplicate full rows: **0**

## Drivers  (55 rows, source encoding `utf-16`)

| column | dtype | nulls | distinct | sample |
|---|---|---|---|---|
| DriverID | int64 | 0 | 55 | 1, 2, 3 |
| DriverName | str | 0 | 53 | Sarah Lopez, Lisa Davis, Steven Anderson |
| Employment Type | str | 0 | 3 | Contract, Full-time, Part-time |
| Hire Date | str | 0 | 54 | 23-11-2021, 19-06-2019, 18-08-2022 |
| Experience Years | int64 | 0 | 8 | 6, 3, 1 |
| Performance Rating | int64 | 0 | 5 | 4, 5, 3 |

Duplicate full rows: **0**

## Hubs  (6 rows, source encoding `utf-16`)

| column | dtype | nulls | distinct | sample |
|---|---|---|---|---|
| Hub ID | int64 | 0 | 6 | 1, 2, 3 |
| HubName | str | 0 | 6 | Dallas Main Hub, Houston Hub, Austin Hub |
| Hub Capacity | int64 | 0 | 6 | 250, 380, 220 |

Duplicate full rows: **0**

## Vehicles  (45 rows, source encoding `utf-16`)

| column | dtype | nulls | distinct | sample |
|---|---|---|---|---|
| Purchase Date | str | 0 | 43 | 22-07-2022, 05-10-2019, 13-10-2022 |
| Vehicle ID | int64 | 0 | 45 | 1, 2, 3 |
| Vehicle Model | str | 0 | 9 | Mercedes Sprinter, Freightliner M2, Chevrolet Express |
| Vehicle Status | str | 0 | 2 | Active, Maintenance |
| Breakdown | int64 | 0 | 20 | 5, 25, 11 |
| Maintenance count Alert | int64 | 0 | 2 | 0, 1 |
| Vehicle Code | str | 0 | 45 | FT-001, FT-002, FT-003 |

Duplicate full rows: **0**
