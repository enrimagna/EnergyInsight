# Energy Monitoring Project

This project monitors energy usage from a heat pump using MELCloud, retrieves temperature data from Home Assistant, and compares costs against a hypothetical diesel heater. Data is stored in SQLite, and custom web dashboards display key metrics via simple graphs.

## Goals
- Fetch energy usage data from MELCloud using the `pymelcloud` library.
- Receive temperature data from Home Assistant via a simple API endpoint.
- Store data in an SQLite database.
- Display dashboards with 2-3 graphs:
  - Energy consumption over time.
  - Cost comparison (heat pump vs. diesel).
  - Temperature trends.
- Enable manual entry of fuel and energy prices.

## Documentation Sections
- [Project Setup](setup.md): Install dependencies and set up the database.
- [Data Sources](data_sources.md): Configure energy usage and temperature data retrieval.
- [Database](database.md): SQLite schema and management.
- [Web Apps](web_apps.md): Build custom dashboards with Flask.
- [Deployment](deployment.md): Run the application and automate tasks.