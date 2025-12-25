# Monitoring Setup

## Overview

This monitoring stack provides comprehensive observability for the Radio Transcription System using Prometheus and Grafana.

## Components

- **Prometheus** (Port 9090): Metrics collection and storage
- **Grafana** (Port 3000): Visualization and dashboards
- **cAdvisor** (Port 8081): Container resource metrics

## Access

- **Grafana**: http://localhost:3000
  - Username: `admin`
  - Password: `admin`

- **Prometheus**: http://localhost:9090

- **cAdvisor**: http://localhost:8081

## Metrics Collected

### API Performance
- `http_requests_total`: Total HTTP requests by endpoint and status
- `http_request_duration_seconds`: Request latency
- `http_request_size_bytes`: Request payload sizes
- `http_response_size_bytes`: Response payload sizes

### Radio Operations
- `radio_captures_total{modulation, status}`: Total captures by modulation type
- `radio_capture_duration_seconds`: Capture duration distribution
- `radio_simulation_mode`: Whether using real hardware or simulation

### Transcription Operations
- `transcription_requests_total{status}`: Total transcription requests
- `transcription_duration_seconds`: Transcription time distribution

### Container Metrics (via cAdvisor)
- CPU usage
- Memory usage
- Network I/O
- Disk I/O

## Alerts

Configured alerts (view in Prometheus):
- API Down
- High Error Rate (>10% for 5 minutes)
- High Capture Failure Rate (>20%)
- Slow Captures (p95 > 2 minutes)
- High Transcription Failure Rate (>20%)
- Slow Transcriptions (p95 > 1 minute)
- High Memory Usage (>90%)
- High CPU Usage (>80%)

## Data Retention

- Prometheus retains metrics for 30 days
- Data stored in Docker volume: `prometheus-data`

## Starting the Monitoring Stack

```bash
# Start all services including monitoring
docker-compose up -d

# View logs
docker-compose logs -f prometheus grafana

# Stop services
docker-compose down
```

## Custom Dashboards

Dashboards are provisioned automatically in Grafana:
- Import custom dashboards by adding JSON files to `monitoring/grafana/dashboards/`
- Dashboards reload automatically every 10 seconds

## Querying Metrics

Example PromQL queries:

```promql
# Request rate per second
rate(http_requests_total[5m])

# 95th percentile latency
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# Capture success rate
rate(radio_captures_total{status="success"}[5m]) / rate(radio_captures_total[5m])

# Container memory usage
container_memory_usage_bytes{name="radio-api"}
```
