# Web Applications and Dashboard Interfaces

The application provides multiple web-based dashboards built with Flask, using Plotly for data visualization and Bootstrap for the user interface.

## Core Web Framework

- **Flask**: A lightweight Python web framework that handles routing, templates, and HTTP requests
- **Jinja2**: The templating engine used by Flask to render HTML templates
- **Blueprints**: The application is organized into separate blueprint modules for better code organization

## Dashboard Interfaces

### Main Dashboard (`/dashboard`)
The main dashboard provides an overview of energy usage and costs:
- Energy consumption over time
- Cost comparison between heat pump electricity and hypothetical diesel heating
- Historical trends and patterns

### Temperature Dashboard (`/temperature`)
The temperature dashboard focuses on temperature data:
- Indoor and outdoor temperature trends
- Temperature correlation with energy usage
- Heat pump efficiency at different outdoor temperatures

### Settings Interface (`/settings`)
The settings interface allows users to:
- Update price information (electricity price, diesel price, diesel efficiency)
- Configure data collection settings
- Manage application preferences

### Data Management (`/data`)
The data management interface provides:
- Options to export or download data
- Manual data entry capabilities
- Data filtering and range selection

## Visualization Technology

All graphs and charts are created using **Plotly**, which provides:
- Interactive and responsive visualizations
- Zoom, pan, and hover functionality
- Export options (PNG, SVG)
- Modern and appealing visual design

## Template Structure

Templates are organized hierarchically:
- `base.html`: Main layout template with common elements
- Section-specific templates (e.g., `dashboard/index.html`, `temperature/index.html`)
- Reusable components and fragments

## Dynamic Updates

Data is updated through:
- Scheduled background jobs using APScheduler
- Manual refresh options in the UI
- Automatic page refreshes where appropriate