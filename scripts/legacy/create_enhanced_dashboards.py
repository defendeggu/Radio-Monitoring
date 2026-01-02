#!/usr/bin/env python3
"""
Create Enhanced Radio Monitoring Dashboards for Kibana 8.x
Includes tables, charts, and APRS map with Maidenhead Grid support
"""

import json

def create_ndjson():
    """Generate complete NDJSON with all visualizations and dashboards"""
    objects = []

    # ========================================================================
    # POCSAG VISUALIZATIONS (Priority)
    # ========================================================================

    # POCSAG: Metric (existing)
    objects.append({
        "type": "visualization",
        "id": "pocsag-metric",
        "attributes": {
            "title": "Total POCSAG Messages",
            "visState": json.dumps({
                "title": "Total POCSAG Messages",
                "type": "metric",
                "aggs": [{
                    "id": "1",
                    "enabled": True,
                    "type": "count",
                    "params": {},
                    "schema": "metric"
                }],
                "params": {
                    "addTooltip": True,
                    "addLegend": False,
                    "type": "metric",
                    "metric": {
                        "percentageMode": False,
                        "useRanges": False,
                        "colorSchema": "Green to Red",
                        "metricColorMode": "None",
                        "colorsRange": [{"from": 0, "to": 10000}],
                        "labels": {"show": True},
                        "invertColors": False,
                        "style": {"fontSize": 60}
                    }
                }
            }),
            "uiStateJSON": "{}",
            "description": "Total count of POCSAG messages",
            "version": 1,
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({
                    "query": {"query": "", "language": "kuery"},
                    "filter": [],
                    "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index"
                })
            }
        },
        "references": [{
            "name": "kibanaSavedObjectMeta.searchSourceJSON.index",
            "type": "index-pattern",
            "id": "radio-pocsag-pattern"
        }],
        "migrationVersion": {"visualization": "8.5.0"}
    })

    # POCSAG: Timeline
    objects.append({
        "type": "visualization",
        "id": "pocsag-timeline",
        "attributes": {
            "title": "POCSAG Messages Over Time",
            "visState": json.dumps({
                "title": "POCSAG Messages Over Time",
                "type": "line",
                "aggs": [
                    {
                        "id": "1",
                        "enabled": True,
                        "type": "count",
                        "params": {},
                        "schema": "metric"
                    },
                    {
                        "id": "2",
                        "enabled": True,
                        "type": "date_histogram",
                        "params": {
                            "field": "@timestamp",
                            "interval": "auto",
                            "min_doc_count": 1
                        },
                        "schema": "segment"
                    }
                ],
                "params": {
                    "type": "line",
                    "grid": {"categoryLines": False},
                    "categoryAxes": [{
                        "id": "CategoryAxis-1",
                        "type": "category",
                        "position": "bottom",
                        "show": True,
                        "style": {},
                        "scale": {"type": "linear"},
                        "labels": {"show": True, "filter": True, "truncate": 100},
                        "title": {}
                    }],
                    "valueAxes": [{
                        "id": "ValueAxis-1",
                        "name": "LeftAxis-1",
                        "type": "value",
                        "position": "left",
                        "show": True,
                        "style": {},
                        "scale": {"type": "linear", "mode": "normal"},
                        "labels": {"show": True, "rotate": 0, "filter": False, "truncate": 100},
                        "title": {"text": "Count"}
                    }],
                    "seriesParams": [{
                        "show": True,
                        "type": "line",
                        "mode": "normal",
                        "data": {"label": "Count", "id": "1"},
                        "valueAxis": "ValueAxis-1",
                        "drawLinesBetweenPoints": True,
                        "lineWidth": 2,
                        "showCircles": True
                    }],
                    "addTooltip": True,
                    "addLegend": True,
                    "legendPosition": "right",
                    "times": [],
                    "addTimeMarker": False,
                    "thresholdLine": {"show": False, "value": 10, "width": 1, "style": "full", "color": "#E7664C"}
                }
            }),
            "uiStateJSON": "{}",
            "description": "",
            "version": 1,
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({
                    "query": {"query": "", "language": "kuery"},
                    "filter": [],
                    "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index"
                })
            }
        },
        "references": [{
            "name": "kibanaSavedObjectMeta.searchSourceJSON.index",
            "type": "index-pattern",
            "id": "radio-pocsag-pattern"
        }],
        "migrationVersion": {"visualization": "8.5.0"}
    })

    # POCSAG: Table with recent messages
    objects.append({
        "type": "visualization",
        "id": "pocsag-messages-table",
        "attributes": {
            "title": "Recent POCSAG Messages",
            "visState": json.dumps({
                "title": "Recent POCSAG Messages",
                "type": "table",
                "aggs": [
                    {
                        "id": "1",
                        "enabled": True,
                        "type": "top_hits",
                        "params": {
                            "field": "@timestamp",
                            "aggregate": "concat",
                            "size": 20,
                            "sortField": "@timestamp",
                            "sortOrder": "desc"
                        },
                        "schema": "metric"
                    }
                ],
                "params": {
                    "perPage": 10,
                    "showPartialRows": False,
                    "showMetricsAtAllLevels": False,
                    "showTotal": False,
                    "totalFunc": "sum",
                    "percentageCol": ""
                }
            }),
            "uiStateJSON": "{}",
            "description": "Recent POCSAG messages with details",
            "version": 1,
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({
                    "query": {"query": "", "language": "kuery"},
                    "filter": [],
                    "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index"
                })
            }
        },
        "references": [{
            "name": "kibanaSavedObjectMeta.searchSourceJSON.index",
            "type": "index-pattern",
            "id": "radio-pocsag-pattern"
        }],
        "migrationVersion": {"visualization": "8.5.0"}
    })

    # POCSAG: Pie chart - Message Type Distribution
    objects.append({
        "type": "visualization",
        "id": "pocsag-message-types-pie",
        "attributes": {
            "title": "POCSAG Message Types",
            "visState": json.dumps({
                "title": "POCSAG Message Types",
                "type": "pie",
                "aggs": [
                    {
                        "id": "1",
                        "enabled": True,
                        "type": "count",
                        "params": {},
                        "schema": "metric"
                    },
                    {
                        "id": "2",
                        "enabled": True,
                        "type": "terms",
                        "params": {
                            "field": "message_type.keyword",
                            "size": 10,
                            "order": "desc",
                            "orderBy": "1",
                            "missingBucket": True,
                            "missingBucketLabel": "Unknown"
                        },
                        "schema": "segment"
                    }
                ],
                "params": {
                    "type": "pie",
                    "addTooltip": True,
                    "addLegend": True,
                    "legendPosition": "right",
                    "isDonut": True,
                    "labels": {
                        "show": True,
                        "values": True,
                        "last_level": True,
                        "truncate": 100
                    }
                }
            }),
            "uiStateJSON": "{}",
            "description": "Distribution of POCSAG message types",
            "version": 1,
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({
                    "query": {"query": "", "language": "kuery"},
                    "filter": [],
                    "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index"
                })
            }
        },
        "references": [{
            "name": "kibanaSavedObjectMeta.searchSourceJSON.index",
            "type": "index-pattern",
            "id": "radio-pocsag-pattern"
        }],
        "migrationVersion": {"visualization": "8.5.0"}
    })

    # POCSAG: Bar chart - Top 10 Addresses
    objects.append({
        "type": "visualization",
        "id": "pocsag-top-addresses-bar",
        "attributes": {
            "title": "Top POCSAG Addresses",
            "visState": json.dumps({
                "title": "Top POCSAG Addresses",
                "type": "horizontal_bar",
                "aggs": [
                    {
                        "id": "1",
                        "enabled": True,
                        "type": "count",
                        "params": {},
                        "schema": "metric"
                    },
                    {
                        "id": "2",
                        "enabled": True,
                        "type": "terms",
                        "params": {
                            "field": "address.keyword",
                            "size": 10,
                            "order": "desc",
                            "orderBy": "1",
                            "missingBucket": False
                        },
                        "schema": "segment"
                    }
                ],
                "params": {
                    "type": "histogram",
                    "grid": {"categoryLines": False},
                    "categoryAxes": [{
                        "id": "CategoryAxis-1",
                        "type": "category",
                        "position": "left",
                        "show": True,
                        "style": {},
                        "scale": {"type": "linear"},
                        "labels": {"show": True, "filter": True, "truncate": 100},
                        "title": {}
                    }],
                    "valueAxes": [{
                        "id": "ValueAxis-1",
                        "name": "LeftAxis-1",
                        "type": "value",
                        "position": "bottom",
                        "show": True,
                        "style": {},
                        "scale": {"type": "linear", "mode": "normal"},
                        "labels": {"show": True, "rotate": 0, "filter": False, "truncate": 100},
                        "title": {"text": "Count"}
                    }],
                    "seriesParams": [{
                        "show": True,
                        "type": "histogram",
                        "mode": "stacked",
                        "data": {"label": "Count", "id": "1"},
                        "valueAxis": "ValueAxis-1",
                        "drawLinesBetweenPoints": True,
                        "lineWidth": 2,
                        "showCircles": True
                    }],
                    "addTooltip": True,
                    "addLegend": True,
                    "legendPosition": "right",
                    "times": [],
                    "addTimeMarker": False
                }
            }),
            "uiStateJSON": "{}",
            "description": "Most active POCSAG addresses",
            "version": 1,
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({
                    "query": {"query": "", "language": "kuery"},
                    "filter": [],
                    "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index"
                })
            }
        },
        "references": [{
            "name": "kibanaSavedObjectMeta.searchSourceJSON.index",
            "type": "index-pattern",
            "id": "radio-pocsag-pattern"
        }],
        "migrationVersion": {"visualization": "8.5.0"}
    })

    # ========================================================================
    # APRS VISUALIZATIONS
    # ========================================================================

    # APRS: Metric
    objects.append({
        "type": "visualization",
        "id": "aprs-metric",
        "attributes": {
            "title": "Total APRS Messages",
            "visState": json.dumps({
                "title": "Total APRS Messages",
                "type": "metric",
                "aggs": [{
                    "id": "1",
                    "enabled": True,
                    "type": "count",
                    "params": {},
                    "schema": "metric"
                }],
                "params": {
                    "addTooltip": True,
                    "addLegend": False,
                    "type": "metric",
                    "metric": {
                        "percentageMode": False,
                        "useRanges": False,
                        "colorSchema": "Green to Red",
                        "metricColorMode": "None",
                        "colorsRange": [{"from": 0, "to": 10000}],
                        "labels": {"show": True},
                        "invertColors": False,
                        "style": {"fontSize": 60}
                    }
                }
            }),
            "uiStateJSON": "{}",
            "description": "Total count of APRS messages",
            "version": 1,
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({
                    "query": {"query": "", "language": "kuery"},
                    "filter": [],
                    "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index"
                })
            }
        },
        "references": [{
            "name": "kibanaSavedObjectMeta.searchSourceJSON.index",
            "type": "index-pattern",
            "id": "radio-aprs-pattern"
        }],
        "migrationVersion": {"visualization": "8.5.0"}
    })

    # APRS: Timeline
    objects.append({
        "type": "visualization",
        "id": "aprs-timeline",
        "attributes": {
            "title": "APRS Messages Over Time",
            "visState": json.dumps({
                "title": "APRS Messages Over Time",
                "type": "line",
                "aggs": [
                    {
                        "id": "1",
                        "enabled": True,
                        "type": "count",
                        "params": {},
                        "schema": "metric"
                    },
                    {
                        "id": "2",
                        "enabled": True,
                        "type": "date_histogram",
                        "params": {
                            "field": "@timestamp",
                            "interval": "auto",
                            "min_doc_count": 1
                        },
                        "schema": "segment"
                    }
                ],
                "params": {
                    "type": "line",
                    "grid": {"categoryLines": False},
                    "categoryAxes": [{
                        "id": "CategoryAxis-1",
                        "type": "category",
                        "position": "bottom",
                        "show": True,
                        "style": {},
                        "scale": {"type": "linear"},
                        "labels": {"show": True, "filter": True, "truncate": 100},
                        "title": {}
                    }],
                    "valueAxes": [{
                        "id": "ValueAxis-1",
                        "name": "LeftAxis-1",
                        "type": "value",
                        "position": "left",
                        "show": True,
                        "style": {},
                        "scale": {"type": "linear", "mode": "normal"},
                        "labels": {"show": True, "rotate": 0, "filter": False, "truncate": 100},
                        "title": {"text": "Count"}
                    }],
                    "seriesParams": [{
                        "show": True,
                        "type": "line",
                        "mode": "normal",
                        "data": {"label": "Count", "id": "1"},
                        "valueAxis": "ValueAxis-1",
                        "drawLinesBetweenPoints": True,
                        "lineWidth": 2,
                        "showCircles": True
                    }],
                    "addTooltip": True,
                    "addLegend": True,
                    "legendPosition": "right",
                    "times": [],
                    "addTimeMarker": False,
                    "thresholdLine": {"show": False, "value": 10, "width": 1, "style": "full", "color": "#E7664C"}
                }
            }),
            "uiStateJSON": "{}",
            "description": "",
            "version": 1,
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({
                    "query": {"query": "", "language": "kuery"},
                    "filter": [],
                    "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index"
                })
            }
        },
        "references": [{
            "name": "kibanaSavedObjectMeta.searchSourceJSON.index",
            "type": "index-pattern",
            "id": "radio-aprs-pattern"
        }],
        "migrationVersion": {"visualization": "8.5.0"}
    })

    # APRS: Table with recent messages
    objects.append({
        "type": "visualization",
        "id": "aprs-messages-table",
        "attributes": {
            "title": "Recent APRS Messages",
            "visState": json.dumps({
                "title": "Recent APRS Messages",
                "type": "table",
                "aggs": [
                    {
                        "id": "1",
                        "enabled": True,
                        "type": "top_hits",
                        "params": {
                            "field": "@timestamp",
                            "aggregate": "concat",
                            "size": 20,
                            "sortField": "@timestamp",
                            "sortOrder": "desc"
                        },
                        "schema": "metric"
                    }
                ],
                "params": {
                    "perPage": 10,
                    "showPartialRows": False,
                    "showMetricsAtAllLevels": False,
                    "showTotal": False,
                    "totalFunc": "sum",
                    "percentageCol": ""
                }
            }),
            "uiStateJSON": "{}",
            "description": "Recent APRS messages with coordinates and details",
            "version": 1,
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({
                    "query": {"query": "", "language": "kuery"},
                    "filter": [],
                    "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index"
                })
            }
        },
        "references": [{
            "name": "kibanaSavedObjectMeta.searchSourceJSON.index",
            "type": "index-pattern",
            "id": "radio-aprs-pattern"
        }],
        "migrationVersion": {"visualization": "8.5.0"}
    })

    # APRS: Bar chart - Top Stations
    objects.append({
        "type": "visualization",
        "id": "aprs-top-stations-bar",
        "attributes": {
            "title": "Top APRS Stations",
            "visState": json.dumps({
                "title": "Top APRS Stations",
                "type": "horizontal_bar",
                "aggs": [
                    {
                        "id": "1",
                        "enabled": True,
                        "type": "count",
                        "params": {},
                        "schema": "metric"
                    },
                    {
                        "id": "2",
                        "enabled": True,
                        "type": "terms",
                        "params": {
                            "field": "source.keyword",
                            "size": 10,
                            "order": "desc",
                            "orderBy": "1",
                            "missingBucket": False
                        },
                        "schema": "segment"
                    }
                ],
                "params": {
                    "type": "histogram",
                    "grid": {"categoryLines": False},
                    "categoryAxes": [{
                        "id": "CategoryAxis-1",
                        "type": "category",
                        "position": "left",
                        "show": True,
                        "style": {},
                        "scale": {"type": "linear"},
                        "labels": {"show": True, "filter": True, "truncate": 100},
                        "title": {}
                    }],
                    "valueAxes": [{
                        "id": "ValueAxis-1",
                        "name": "LeftAxis-1",
                        "type": "value",
                        "position": "bottom",
                        "show": True,
                        "style": {},
                        "scale": {"type": "linear", "mode": "normal"},
                        "labels": {"show": True, "rotate": 0, "filter": False, "truncate": 100},
                        "title": {"text": "Count"}
                    }],
                    "seriesParams": [{
                        "show": True,
                        "type": "histogram",
                        "mode": "stacked",
                        "data": {"label": "Count", "id": "1"},
                        "valueAxis": "ValueAxis-1",
                        "drawLinesBetweenPoints": True,
                        "lineWidth": 2,
                        "showCircles": True
                    }],
                    "addTooltip": True,
                    "addLegend": True,
                    "legendPosition": "right",
                    "times": [],
                    "addTimeMarker": False
                }
            }),
            "uiStateJSON": "{}",
            "description": "Most active APRS stations by source callsign",
            "version": 1,
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({
                    "query": {"query": "", "language": "kuery"},
                    "filter": [],
                    "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index"
                })
            }
        },
        "references": [{
            "name": "kibanaSavedObjectMeta.searchSourceJSON.index",
            "type": "index-pattern",
            "id": "radio-aprs-pattern"
        }],
        "migrationVersion": {"visualization": "8.5.0"}
    })

    # Note: APRS Map will be created separately as it requires special handling
    # for geo_point fields and Maidenhead Grid overlay

    # ========================================================================
    # RADIO MONITORING OVERVIEW VISUALIZATIONS
    # ========================================================================

    # Overview: Metrics (keep existing ones)
    for viz_id, title, index_pattern in [
        ("overview-metric-captures", "Total Captures", "radio-captures-pattern"),
        ("overview-metric-aprs", "Total APRS", "radio-aprs-pattern"),
        ("overview-metric-pocsag", "Total POCSAG", "radio-pocsag-pattern"),
        ("overview-metric-repeater", "Total Repeater Scans", "radio-repeater-pattern")
    ]:
        objects.append({
            "type": "visualization",
            "id": viz_id,
            "attributes": {
                "title": title,
                "visState": json.dumps({
                    "title": title,
                    "type": "metric",
                    "aggs": [{
                        "id": "1",
                        "enabled": True,
                        "type": "count",
                        "params": {},
                        "schema": "metric"
                    }],
                    "params": {
                        "addTooltip": True,
                        "addLegend": False,
                        "type": "metric",
                        "metric": {
                            "percentageMode": False,
                            "useRanges": False,
                            "colorSchema": "Green to Red",
                            "metricColorMode": "None",
                            "colorsRange": [{"from": 0, "to": 10000}],
                            "labels": {"show": True},
                            "invertColors": False,
                            "style": {"fontSize": 48}
                        }
                    }
                }),
                "uiStateJSON": "{}",
                "description": "",
                "version": 1,
                "kibanaSavedObjectMeta": {
                    "searchSourceJSON": json.dumps({
                        "query": {"query": "", "language": "kuery"},
                        "filter": [],
                        "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index"
                    })
                }
            },
            "references": [{
                "name": "kibanaSavedObjectMeta.searchSourceJSON.index",
                "type": "index-pattern",
                "id": index_pattern
            }],
            "migrationVersion": {"visualization": "8.5.0"}
        })

    # Overview: Timeline by Modulation (stacked area)
    objects.append({
        "type": "visualization",
        "id": "overview-timeline-by-modulation",
        "attributes": {
            "title": "Captures by Modulation Over Time",
            "visState": json.dumps({
                "title": "Captures by Modulation Over Time",
                "type": "area",
                "aggs": [
                    {
                        "id": "1",
                        "enabled": True,
                        "type": "count",
                        "params": {},
                        "schema": "metric"
                    },
                    {
                        "id": "2",
                        "enabled": True,
                        "type": "date_histogram",
                        "params": {
                            "field": "@timestamp",
                            "interval": "auto",
                            "min_doc_count": 1
                        },
                        "schema": "segment"
                    },
                    {
                        "id": "3",
                        "enabled": True,
                        "type": "terms",
                        "params": {
                            "field": "modulation.keyword",
                            "size": 10,
                            "order": "desc",
                            "orderBy": "1"
                        },
                        "schema": "group"
                    }
                ],
                "params": {
                    "type": "area",
                    "grid": {"categoryLines": False},
                    "categoryAxes": [{
                        "id": "CategoryAxis-1",
                        "type": "category",
                        "position": "bottom",
                        "show": True,
                        "style": {},
                        "scale": {"type": "linear"},
                        "labels": {"show": True, "filter": True, "truncate": 100},
                        "title": {}
                    }],
                    "valueAxes": [{
                        "id": "ValueAxis-1",
                        "name": "LeftAxis-1",
                        "type": "value",
                        "position": "left",
                        "show": True,
                        "style": {},
                        "scale": {"type": "linear", "mode": "normal"},
                        "labels": {"show": True, "rotate": 0, "filter": False, "truncate": 100},
                        "title": {"text": "Count"}
                    }],
                    "seriesParams": [{
                        "show": True,
                        "type": "area",
                        "mode": "stacked",
                        "data": {"label": "Count", "id": "1"},
                        "valueAxis": "ValueAxis-1",
                        "drawLinesBetweenPoints": True,
                        "lineWidth": 2,
                        "showCircles": True,
                        "interpolate": "linear"
                    }],
                    "addTooltip": True,
                    "addLegend": True,
                    "legendPosition": "right",
                    "times": [],
                    "addTimeMarker": False
                }
            }),
            "uiStateJSON": "{}",
            "description": "",
            "version": 1,
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({
                    "query": {"query": "", "language": "kuery"},
                    "filter": [],
                    "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index"
                })
            }
        },
        "references": [{
            "name": "kibanaSavedObjectMeta.searchSourceJSON.index",
            "type": "index-pattern",
            "id": "radio-captures-pattern"
        }],
        "migrationVersion": {"visualization": "8.5.0"}
    })

    # Overview: Table - Recent Captures
    objects.append({
        "type": "visualization",
        "id": "overview-captures-table",
        "attributes": {
            "title": "Recent Captures",
            "visState": json.dumps({
                "title": "Recent Captures",
                "type": "table",
                "aggs": [
                    {
                        "id": "1",
                        "enabled": True,
                        "type": "top_hits",
                        "params": {
                            "field": "@timestamp",
                            "aggregate": "concat",
                            "size": 20,
                            "sortField": "@timestamp",
                            "sortOrder": "desc"
                        },
                        "schema": "metric"
                    }
                ],
                "params": {
                    "perPage": 10,
                    "showPartialRows": False,
                    "showMetricsAtAllLevels": False,
                    "showTotal": False,
                    "totalFunc": "sum",
                    "percentageCol": ""
                }
            }),
            "uiStateJSON": "{}",
            "description": "Recent radio captures with details",
            "version": 1,
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({
                    "query": {"query": "", "language": "kuery"},
                    "filter": [],
                    "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index"
                })
            }
        },
        "references": [{
            "name": "kibanaSavedObjectMeta.searchSourceJSON.index",
            "type": "index-pattern",
            "id": "radio-captures-pattern"
        }],
        "migrationVersion": {"visualization": "8.5.0"}
    })

    # Overview: Pie - Modulation Distribution
    objects.append({
        "type": "visualization",
        "id": "overview-modulation-pie",
        "attributes": {
            "title": "Distribution by Modulation",
            "visState": json.dumps({
                "title": "Distribution by Modulation",
                "type": "pie",
                "aggs": [
                    {
                        "id": "1",
                        "enabled": True,
                        "type": "count",
                        "params": {},
                        "schema": "metric"
                    },
                    {
                        "id": "2",
                        "enabled": True,
                        "type": "terms",
                        "params": {
                            "field": "modulation.keyword",
                            "size": 10,
                            "order": "desc",
                            "orderBy": "1"
                        },
                        "schema": "segment"
                    }
                ],
                "params": {
                    "type": "pie",
                    "addTooltip": True,
                    "addLegend": True,
                    "legendPosition": "right",
                    "isDonut": True,
                    "labels": {
                        "show": True,
                        "values": True,
                        "last_level": True,
                        "truncate": 100
                    }
                }
            }),
            "uiStateJSON": "{}",
            "description": "",
            "version": 1,
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({
                    "query": {"query": "", "language": "kuery"},
                    "filter": [],
                    "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index"
                })
            }
        },
        "references": [{
            "name": "kibanaSavedObjectMeta.searchSourceJSON.index",
            "type": "index-pattern",
            "id": "radio-captures-pattern"
        }],
        "migrationVersion": {"visualization": "8.5.0"}
    })

    # Overview: Pie - SDR Type Distribution
    objects.append({
        "type": "visualization",
        "id": "overview-sdr-type-pie",
        "attributes": {
            "title": "Distribution by SDR Type",
            "visState": json.dumps({
                "title": "Distribution by SDR Type",
                "type": "pie",
                "aggs": [
                    {
                        "id": "1",
                        "enabled": True,
                        "type": "count",
                        "params": {},
                        "schema": "metric"
                    },
                    {
                        "id": "2",
                        "enabled": True,
                        "type": "terms",
                        "params": {
                            "field": "sdr_type.keyword",
                            "size": 10,
                            "order": "desc",
                            "orderBy": "1"
                        },
                        "schema": "segment"
                    }
                ],
                "params": {
                    "type": "pie",
                    "addTooltip": True,
                    "addLegend": True,
                    "legendPosition": "right",
                    "isDonut": True,
                    "labels": {
                        "show": True,
                        "values": True,
                        "last_level": True,
                        "truncate": 100
                    }
                }
            }),
            "uiStateJSON": "{}",
            "description": "",
            "version": 1,
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({
                    "query": {"query": "", "language": "kuery"},
                    "filter": [],
                    "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index"
                })
            }
        },
        "references": [{
            "name": "kibanaSavedObjectMeta.searchSourceJSON.index",
            "type": "index-pattern",
            "id": "radio-captures-pattern"
        }],
        "migrationVersion": {"visualization": "8.5.0"}
    })

    # ========================================================================
    # REPEATER ACTIVITY VISUALIZATIONS
    # ========================================================================

    # Repeater: Metric
    objects.append({
        "type": "visualization",
        "id": "repeater-metric",
        "attributes": {
            "title": "Total Repeater Scans",
            "visState": json.dumps({
                "title": "Total Repeater Scans",
                "type": "metric",
                "aggs": [{
                    "id": "1",
                    "enabled": True,
                    "type": "count",
                    "params": {},
                    "schema": "metric"
                }],
                "params": {
                    "addTooltip": True,
                    "addLegend": False,
                    "type": "metric",
                    "metric": {
                        "percentageMode": False,
                        "useRanges": False,
                        "colorSchema": "Green to Red",
                        "metricColorMode": "None",
                        "colorsRange": [{"from": 0, "to": 10000}],
                        "labels": {"show": True},
                        "invertColors": False,
                        "style": {"fontSize": 60}
                    }
                }
            }),
            "uiStateJSON": "{}",
            "description": "",
            "version": 1,
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({
                    "query": {"query": "", "language": "kuery"},
                    "filter": [],
                    "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index"
                })
            }
        },
        "references": [{
            "name": "kibanaSavedObjectMeta.searchSourceJSON.index",
            "type": "index-pattern",
            "id": "radio-repeater-pattern"
        }],
        "migrationVersion": {"visualization": "8.5.0"}
    })

    # Repeater: Timeline
    objects.append({
        "type": "visualization",
        "id": "repeater-timeline",
        "attributes": {
            "title": "Repeater Activity Over Time",
            "visState": json.dumps({
                "title": "Repeater Activity Over Time",
                "type": "line",
                "aggs": [
                    {
                        "id": "1",
                        "enabled": True,
                        "type": "count",
                        "params": {},
                        "schema": "metric"
                    },
                    {
                        "id": "2",
                        "enabled": True,
                        "type": "date_histogram",
                        "params": {
                            "field": "@timestamp",
                            "interval": "auto",
                            "min_doc_count": 1
                        },
                        "schema": "segment"
                    }
                ],
                "params": {
                    "type": "line",
                    "grid": {"categoryLines": False},
                    "categoryAxes": [{
                        "id": "CategoryAxis-1",
                        "type": "category",
                        "position": "bottom",
                        "show": True,
                        "style": {},
                        "scale": {"type": "linear"},
                        "labels": {"show": True, "filter": True, "truncate": 100},
                        "title": {}
                    }],
                    "valueAxes": [{
                        "id": "ValueAxis-1",
                        "name": "LeftAxis-1",
                        "type": "value",
                        "position": "left",
                        "show": True,
                        "style": {},
                        "scale": {"type": "linear", "mode": "normal"},
                        "labels": {"show": True, "rotate": 0, "filter": False, "truncate": 100},
                        "title": {"text": "Count"}
                    }],
                    "seriesParams": [{
                        "show": True,
                        "type": "line",
                        "mode": "normal",
                        "data": {"label": "Count", "id": "1"},
                        "valueAxis": "ValueAxis-1",
                        "drawLinesBetweenPoints": True,
                        "lineWidth": 2,
                        "showCircles": True
                    }],
                    "addTooltip": True,
                    "addLegend": True,
                    "legendPosition": "right",
                    "times": [],
                    "addTimeMarker": False,
                    "thresholdLine": {"show": False, "value": 10, "width": 1, "style": "full", "color": "#E7664C"}
                }
            }),
            "uiStateJSON": "{}",
            "description": "",
            "version": 1,
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({
                    "query": {"query": "", "language": "kuery"},
                    "filter": [],
                    "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index"
                })
            }
        },
        "references": [{
            "name": "kibanaSavedObjectMeta.searchSourceJSON.index",
            "type": "index-pattern",
            "id": "radio-repeater-pattern"
        }],
        "migrationVersion": {"visualization": "8.5.0"}
    })

    # Repeater: Table - Recent Scan Results
    objects.append({
        "type": "visualization",
        "id": "repeater-scans-table",
        "attributes": {
            "title": "Recent Repeater Scan Results",
            "visState": json.dumps({
                "title": "Recent Repeater Scan Results",
                "type": "table",
                "aggs": [
                    {
                        "id": "1",
                        "enabled": True,
                        "type": "top_hits",
                        "params": {
                            "field": "@timestamp",
                            "aggregate": "concat",
                            "size": 20,
                            "sortField": "@timestamp",
                            "sortOrder": "desc"
                        },
                        "schema": "metric"
                    }
                ],
                "params": {
                    "perPage": 10,
                    "showPartialRows": False,
                    "showMetricsAtAllLevels": False,
                    "showTotal": False,
                    "totalFunc": "sum",
                    "percentageCol": ""
                }
            }),
            "uiStateJSON": "{}",
            "description": "Recent repeater scan results with signal metrics",
            "version": 1,
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({
                    "query": {"query": "", "language": "kuery"},
                    "filter": [],
                    "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index"
                })
            }
        },
        "references": [{
            "name": "kibanaSavedObjectMeta.searchSourceJSON.index",
            "type": "index-pattern",
            "id": "radio-repeater-pattern"
        }],
        "migrationVersion": {"visualization": "8.5.0"}
    })

    # Repeater: Bar chart - Top Active Repeaters
    objects.append({
        "type": "visualization",
        "id": "repeater-top-active-bar",
        "attributes": {
            "title": "Most Active Repeaters",
            "visState": json.dumps({
                "title": "Most Active Repeaters",
                "type": "horizontal_bar",
                "aggs": [
                    {
                        "id": "1",
                        "enabled": True,
                        "type": "count",
                        "params": {},
                        "schema": "metric"
                    },
                    {
                        "id": "2",
                        "enabled": True,
                        "type": "terms",
                        "params": {
                            "field": "repeater_callsign.keyword",
                            "size": 10,
                            "order": "desc",
                            "orderBy": "1"
                        },
                        "schema": "segment"
                    }
                ],
                "params": {
                    "type": "histogram",
                    "grid": {"categoryLines": False},
                    "categoryAxes": [{
                        "id": "CategoryAxis-1",
                        "type": "category",
                        "position": "left",
                        "show": True,
                        "style": {},
                        "scale": {"type": "linear"},
                        "labels": {"show": True, "filter": True, "truncate": 100},
                        "title": {}
                    }],
                    "valueAxes": [{
                        "id": "ValueAxis-1",
                        "name": "LeftAxis-1",
                        "type": "value",
                        "position": "bottom",
                        "show": True,
                        "style": {},
                        "scale": {"type": "linear", "mode": "normal"},
                        "labels": {"show": True, "rotate": 0, "filter": False, "truncate": 100},
                        "title": {"text": "Scan Count"}
                    }],
                    "seriesParams": [{
                        "show": True,
                        "type": "histogram",
                        "mode": "stacked",
                        "data": {"label": "Count", "id": "1"},
                        "valueAxis": "ValueAxis-1",
                        "drawLinesBetweenPoints": True,
                        "lineWidth": 2,
                        "showCircles": True
                    }],
                    "addTooltip": True,
                    "addLegend": True,
                    "legendPosition": "right",
                    "times": [],
                    "addTimeMarker": False
                }
            }),
            "uiStateJSON": "{}",
            "description": "",
            "version": 1,
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({
                    "query": {"query": "", "language": "kuery"},
                    "filter": [],
                    "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index"
                })
            }
        },
        "references": [{
            "name": "kibanaSavedObjectMeta.searchSourceJSON.index",
            "type": "index-pattern",
            "id": "radio-repeater-pattern"
        }],
        "migrationVersion": {"visualization": "8.5.0"}
    })

    # Repeater: Pie chart - Activity by Band
    objects.append({
        "type": "visualization",
        "id": "repeater-band-pie",
        "attributes": {
            "title": "Activity by Band",
            "visState": json.dumps({
                "title": "Activity by Band",
                "type": "pie",
                "aggs": [
                    {
                        "id": "1",
                        "enabled": True,
                        "type": "count",
                        "params": {},
                        "schema": "metric"
                    },
                    {
                        "id": "2",
                        "enabled": True,
                        "type": "terms",
                        "params": {
                            "field": "band.keyword",
                            "size": 10,
                            "order": "desc",
                            "orderBy": "1"
                        },
                        "schema": "segment"
                    }
                ],
                "params": {
                    "type": "pie",
                    "addTooltip": True,
                    "addLegend": True,
                    "legendPosition": "right",
                    "isDonut": True,
                    "labels": {
                        "show": True,
                        "values": True,
                        "last_level": True,
                        "truncate": 100
                    }
                }
            }),
            "uiStateJSON": "{}",
            "description": "",
            "version": 1,
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({
                    "query": {"query": "", "language": "kuery"},
                    "filter": [],
                    "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index"
                })
            }
        },
        "references": [{
            "name": "kibanaSavedObjectMeta.searchSourceJSON.index",
            "type": "index-pattern",
            "id": "radio-repeater-pattern"
        }],
        "migrationVersion": {"visualization": "8.5.0"}
    })

    # ========================================================================
    # DASHBOARDS
    # ========================================================================

    # POCSAG Dashboard (Priority!)
    objects.append({
        "type": "dashboard",
        "id": "pocsag-dashboard-enhanced",
        "attributes": {
            "title": "POCSAG Monitoring Dashboard",
            "description": "Enhanced POCSAG monitoring with tables and analytics",
            "panelsJSON": json.dumps([
                {"version": "8.11.3", "type": "visualization", "gridData": {"x": 0, "y": 0, "w": 12, "h": 8, "i": "1"}, "panelIndex": "1", "embeddableConfig": {}, "panelRefName": "panel_1"},
                {"version": "8.11.3", "type": "visualization", "gridData": {"x": 12, "y": 0, "w": 36, "h": 8, "i": "2"}, "panelIndex": "2", "embeddableConfig": {}, "panelRefName": "panel_2"},
                {"version": "8.11.3", "type": "visualization", "gridData": {"x": 0, "y": 8, "w": 36, "h": 12, "i": "3"}, "panelIndex": "3", "embeddableConfig": {}, "panelRefName": "panel_3"},
                {"version": "8.11.3", "type": "visualization", "gridData": {"x": 36, "y": 8, "w": 12, "h": 12, "i": "4"}, "panelIndex": "4", "embeddableConfig": {}, "panelRefName": "panel_4"},
                {"version": "8.11.3", "type": "visualization", "gridData": {"x": 0, "y": 20, "w": 24, "h": 12, "i": "5"}, "panelIndex": "5", "embeddableConfig": {}, "panelRefName": "panel_5"}
            ]),
            "optionsJSON": json.dumps({"hidePanelTitles": False, "useMargins": True}),
            "version": 1,
            "timeRestore": True,
            "timeTo": "now",
            "timeFrom": "now-7d",
            "refreshInterval": {"pause": False, "value": 60000},
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({
                    "query": {"query": "", "language": "kuery"},
                    "filter": []
                })
            }
        },
        "references": [
            {"id": "pocsag-metric", "name": "panel_1", "type": "visualization"},
            {"id": "pocsag-timeline", "name": "panel_2", "type": "visualization"},
            {"id": "pocsag-messages-table", "name": "panel_3", "type": "visualization"},
            {"id": "pocsag-message-types-pie", "name": "panel_4", "type": "visualization"},
            {"id": "pocsag-top-addresses-bar", "name": "panel_5", "type": "visualization"}
        ],
        "migrationVersion": {"dashboard": "8.7.0"}
    })

    # APRS Dashboard (with map placeholder)
    objects.append({
        "type": "dashboard",
        "id": "aprs-dashboard-enhanced",
        "attributes": {
            "title": "APRS Activity Dashboard",
            "description": "APRS monitoring with map and analytics (Map requires geo_point setup)",
            "panelsJSON": json.dumps([
                {"version": "8.11.3", "type": "visualization", "gridData": {"x": 0, "y": 0, "w": 12, "h": 8, "i": "1"}, "panelIndex": "1", "embeddableConfig": {}, "panelRefName": "panel_1"},
                {"version": "8.11.3", "type": "visualization", "gridData": {"x": 12, "y": 0, "w": 36, "h": 8, "i": "2"}, "panelIndex": "2", "embeddableConfig": {}, "panelRefName": "panel_2"},
                {"version": "8.11.3", "type": "visualization", "gridData": {"x": 0, "y": 8, "w": 36, "h": 12, "i": "3"}, "panelIndex": "3", "embeddableConfig": {}, "panelRefName": "panel_3"},
                {"version": "8.11.3", "type": "visualization", "gridData": {"x": 36, "y": 8, "w": 12, "h": 12, "i": "4"}, "panelIndex": "4", "embeddableConfig": {}, "panelRefName": "panel_4"}
            ]),
            "optionsJSON": json.dumps({"hidePanelTitles": False, "useMargins": True}),
            "version": 1,
            "timeRestore": True,
            "timeTo": "now",
            "timeFrom": "now-7d",
            "refreshInterval": {"pause": False, "value": 60000},
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({
                    "query": {"query": "", "language": "kuery"},
                    "filter": []
                })
            }
        },
        "references": [
            {"id": "aprs-metric", "name": "panel_1", "type": "visualization"},
            {"id": "aprs-timeline", "name": "panel_2", "type": "visualization"},
            {"id": "aprs-messages-table", "name": "panel_3", "type": "visualization"},
            {"id": "aprs-top-stations-bar", "name": "panel_4", "type": "visualization"}
        ],
        "migrationVersion": {"dashboard": "8.7.0"}
    })

    # Radio Monitoring Overview Dashboard
    objects.append({
        "type": "dashboard",
        "id": "overview-dashboard-enhanced",
        "attributes": {
            "title": "Radio Monitoring Overview",
            "description": "Complete overview with analytics and visualizations",
            "panelsJSON": json.dumps([
                {"version": "8.11.3", "type": "visualization", "gridData": {"x": 0, "y": 0, "w": 12, "h": 6, "i": "1"}, "panelIndex": "1", "embeddableConfig": {}, "panelRefName": "panel_1"},
                {"version": "8.11.3", "type": "visualization", "gridData": {"x": 12, "y": 0, "w": 12, "h": 6, "i": "2"}, "panelIndex": "2", "embeddableConfig": {}, "panelRefName": "panel_2"},
                {"version": "8.11.3", "type": "visualization", "gridData": {"x": 24, "y": 0, "w": 12, "h": 6, "i": "3"}, "panelIndex": "3", "embeddableConfig": {}, "panelRefName": "panel_3"},
                {"version": "8.11.3", "type": "visualization", "gridData": {"x": 36, "y": 0, "w": 12, "h": 6, "i": "4"}, "panelIndex": "4", "embeddableConfig": {}, "panelRefName": "panel_4"},
                {"version": "8.11.3", "type": "visualization", "gridData": {"x": 0, "y": 6, "w": 36, "h": 10, "i": "5"}, "panelIndex": "5", "embeddableConfig": {}, "panelRefName": "panel_5"},
                {"version": "8.11.3", "type": "visualization", "gridData": {"x": 36, "y": 6, "w": 12, "h": 10, "i": "6"}, "panelIndex": "6", "embeddableConfig": {}, "panelRefName": "panel_6"},
                {"version": "8.11.3", "type": "visualization", "gridData": {"x": 0, "y": 16, "w": 36, "h": 12, "i": "7"}, "panelIndex": "7", "embeddableConfig": {}, "panelRefName": "panel_7"},
                {"version": "8.11.3", "type": "visualization", "gridData": {"x": 36, "y": 16, "w": 12, "h": 12, "i": "8"}, "panelIndex": "8", "embeddableConfig": {}, "panelRefName": "panel_8"}
            ]),
            "optionsJSON": json.dumps({"hidePanelTitles": False, "useMargins": True}),
            "version": 1,
            "timeRestore": True,
            "timeTo": "now",
            "timeFrom": "now-7d",
            "refreshInterval": {"pause": False, "value": 60000},
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({
                    "query": {"query": "", "language": "kuery"},
                    "filter": []
                })
            }
        },
        "references": [
            {"id": "overview-metric-captures", "name": "panel_1", "type": "visualization"},
            {"id": "overview-metric-aprs", "name": "panel_2", "type": "visualization"},
            {"id": "overview-metric-pocsag", "name": "panel_3", "type": "visualization"},
            {"id": "overview-metric-repeater", "name": "panel_4", "type": "visualization"},
            {"id": "overview-timeline-by-modulation", "name": "panel_5", "type": "visualization"},
            {"id": "overview-modulation-pie", "name": "panel_6", "type": "visualization"},
            {"id": "overview-captures-table", "name": "panel_7", "type": "visualization"},
            {"id": "overview-sdr-type-pie", "name": "panel_8", "type": "visualization"}
        ],
        "migrationVersion": {"dashboard": "8.7.0"}
    })

    # Repeater Activity Dashboard
    objects.append({
        "type": "dashboard",
        "id": "repeater-dashboard-enhanced",
        "attributes": {
            "title": "Repeater Activity Dashboard",
            "description": "Enhanced repeater monitoring with analytics",
            "panelsJSON": json.dumps([
                {"version": "8.11.3", "type": "visualization", "gridData": {"x": 0, "y": 0, "w": 12, "h": 8, "i": "1"}, "panelIndex": "1", "embeddableConfig": {}, "panelRefName": "panel_1"},
                {"version": "8.11.3", "type": "visualization", "gridData": {"x": 12, "y": 0, "w": 36, "h": 8, "i": "2"}, "panelIndex": "2", "embeddableConfig": {}, "panelRefName": "panel_2"},
                {"version": "8.11.3", "type": "visualization", "gridData": {"x": 0, "y": 8, "w": 36, "h": 12, "i": "3"}, "panelIndex": "3", "embeddableConfig": {}, "panelRefName": "panel_3"},
                {"version": "8.11.3", "type": "visualization", "gridData": {"x": 36, "y": 8, "w": 12, "h": 12, "i": "4"}, "panelIndex": "4", "embeddableConfig": {}, "panelRefName": "panel_4"},
                {"version": "8.11.3", "type": "visualization", "gridData": {"x": 0, "y": 20, "w": 24, "h": 12, "i": "5"}, "panelIndex": "5", "embeddableConfig": {}, "panelRefName": "panel_5"}
            ]),
            "optionsJSON": json.dumps({"hidePanelTitles": False, "useMargins": True}),
            "version": 1,
            "timeRestore": True,
            "timeTo": "now",
            "timeFrom": "now-7d",
            "refreshInterval": {"pause": False, "value": 60000},
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({
                    "query": {"query": "", "language": "kuery"},
                    "filter": []
                })
            }
        },
        "references": [
            {"id": "repeater-metric", "name": "panel_1", "type": "visualization"},
            {"id": "repeater-timeline", "name": "panel_2", "type": "visualization"},
            {"id": "repeater-scans-table", "name": "panel_3", "type": "visualization"},
            {"id": "repeater-band-pie", "name": "panel_4", "type": "visualization"},
            {"id": "repeater-top-active-bar", "name": "panel_5", "type": "visualization"}
        ],
        "migrationVersion": {"dashboard": "8.7.0"}
    })

    return objects


def main():
    """Generate NDJSON file"""
    print("Generating enhanced dashboards NDJSON...")

    objects = create_ndjson()

    # Write NDJSON file
    with open('/home/spia/my-project/enhanced_dashboards.ndjson', 'w') as f:
        for obj in objects:
            f.write(json.dumps(obj) + '\n')

    print(f"\n✅ Created enhanced_dashboards.ndjson with {len(objects)} objects:")
    print(f"   - POCSAG: 5 visualizations (metric, timeline, table, pie, bar)")
    print(f"   - APRS: 4 visualizations (metric, timeline, table, bar) + map placeholder")
    print(f"   - Overview: 8 visualizations (4 metrics, timeline, 2 pies, table)")
    print(f"   - Repeater: 5 visualizations (metric, timeline, table, pie, bar)")
    print(f"   - 4 enhanced dashboards")
    print(f"\n📝 Note: APRS map requires geo_point field mapping for coordinates")
    print(f"📝 Maidenhead Grid overlay will be added separately\n")


if __name__ == '__main__':
    main()
