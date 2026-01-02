# Legacy Grafana/Prometheus Scripts

⚠️ **DEPRECATED** - These scripts are for the old Prometheus/Grafana monitoring stack.

## Status

This directory contains scripts from **Phase 1** of the project (Prometheus/Grafana stack). The project has since migrated to the **ELK Stack** (Elasticsearch, Logstash, Kibana) in Phase 2.

These scripts are **no longer actively maintained** and are kept for reference only.

## Migration Path

If you need similar functionality with the current ELK stack:

- **Dashboard creation**: Use Kibana's UI or import via `scripts/import_kibana_dashboards.py`
- **Metrics visualization**: See `monitoring/kibana/` for current dashboards
- **Health monitoring**: Metricbeat now handles system/container metrics

## Scripts in this Directory

### Dashboard Creation Scripts
- `create_enhanced_dashboards.py` - Created comprehensive Grafana dashboards
- `create_stack_dashboard.py` - Generated stack overview dashboard
- `create_stack_health_dashboard.py` - Health monitoring dashboard

### Dashboard Maintenance
- `cleanup_old_dashboards.py` - Removed old/duplicate Grafana dashboards
- `update_aprs_dashboard_with_map.py` - Added geo-mapping to APRS dashboard
- `update_aprs_template.py` - Updated APRS dashboard templates

## Legacy Stack Reference

The old stack used:
- **PostgreSQL** for data storage (now: Elasticsearch)
- **Prometheus** for metrics collection (now: Metricbeat)
- **Grafana** for visualization (now: Kibana)

See `docker-compose.legacy.yml` (if it exists) for the old stack configuration.

## Current Stack

For the active monitoring stack, see:
- `docker-compose.yml` - ELK Stack configuration
- `monitoring/` - Current ELK stack configs
- `STREAMING_MODE.md` - New streaming decode documentation

---

Last updated: 2026-01-02
Migration: Phase 1 (Prometheus/Grafana) → Phase 2 (ELK Stack)
