# Documentation Overview

This directory contains all project documentation organized by status and relevance.

## 📁 Directory Structure

```
docs/
├── current/         # Active documentation and recent reports
├── archive/         # Historical documentation and outdated plans
└── README.md        # This file
```

## 📚 Root Documentation (Always Current)

Main documentation files are kept in the project root for easy access:

- **`README.md`** - Complete project documentation, API reference, and quick start guide
- **`USER_MANUAL.md`** - German language user manual for end users
- **`CLAUDE.md`** - Instructions for Claude Code when working with this codebase

## 📄 Current Documentation (`docs/current/`)

Active documentation that is still relevant:

### Session Reports (2026)
- **`FINAL_SUMMARY_20260120.md`** - Comprehensive session summary from Jan 20, 2026
  - Documents duration bug fix (commit d1f40c4)
  - RTL-SDR Unicode detection fix
  - Docker Secrets implementation
- **`TEST_REPORT_20260120.md`** - Live streaming test results and analysis

### Planning & Roadmap
- **`OPTIMIZATION_ROADMAP.md`** - Future improvements and optimization plans
  - Signal quality metrics
  - Auto-gain control
  - Frequency management
  - Hardware upgrades

### Technical Guides
- **`QUICKSTART.md`** - Quick start guide for developers
- **`STREAMING_MODE.md`** - Streaming decoder documentation (APRS/POCSAG)
- **`TESTING_GUIDE.md`** - Testing framework and test writing guide
- **`MULTI_DEVICE.md`** - Multi-device RTL-SDR setup guide

### Security Documentation
- **`CONTAINER_SECURITY.md`** - Docker container security practices
- **`ELK_SECURITY.md`** - Elasticsearch/Kibana security configuration

## 🗄️ Archived Documentation (`docs/archive/`)

Historical documentation preserved for reference:

### Historical Implementation Plans
- **`Forkplan.md`** - Original fork planning document
- **`IMPLEMENTATION_PLAN.md`** - Phase 1 implementation plan
- **`IMPLEMENTATION_PLAN_new.md`** - Revised implementation plan
- **`IMPROVEMENT_PLAN.md`** - System improvement proposals
- **`IMPROVEMENT_SUMMARY.md`** - Summary of improvements made
- **`MIGRATION_GUIDE_PHASE2.md`** - Phase 2 migration guide

### Historical Test Reports
- **`PHASE2_TEST_RESULTS.md`** - Phase 2 testing results
- **`TEST_REPORT.md`** - Early test report (superseded by TEST_REPORT_20260120.md)
- **`VERIFICATION_REPORT.md`** - Implementation verification report
- **`HARDWARE_TEST_REPORT.md`** - Hardware testing results
- **`CREDENTIALS_UPDATE.md`** - Credential update procedures (superseded by Docker Secrets)

## 🔍 Finding Documentation

### By Topic

**Getting Started**
- Root: `README.md` - Quick Start with Docker
- Current: `QUICKSTART.md` - Developer quick start

**User Documentation**
- Root: `USER_MANUAL.md` - Complete user guide (German)

**Development**
- Root: `CLAUDE.md` - Development guidelines for AI assistants
- Current: `TESTING_GUIDE.md` - Test framework documentation

**Security**
- Current: `CONTAINER_SECURITY.md`, `ELK_SECURITY.md`
- Archive: `CREDENTIALS_UPDATE.md` (historical)

**Hardware**
- Current: `MULTI_DEVICE.md` - Multi-device setup
- Archive: `HARDWARE_TEST_REPORT.md` - Historical test results

**Recent Changes**
- Current: `FINAL_SUMMARY_20260120.md` - Latest session summary
- Current: `TEST_REPORT_20260120.md` - Recent test results

### By Date

**January 2026**
- `FINAL_SUMMARY_20260120.md` - Jan 20, 2026 session
- `TEST_REPORT_20260120.md` - Jan 20, 2026 tests
- `OPTIMIZATION_ROADMAP.md` - Jan 20, 2026 planning

**Earlier (Archived)**
- `PHASE2_TEST_RESULTS.md` - Jan 4, 2026
- `IMPROVEMENT_SUMMARY.md` - Jan 4, 2026
- Various planning documents from December 2025 - January 2026

## 📝 Maintenance

### Adding New Documentation

- **Session summaries, test reports**: Place in `docs/current/`
- **Outdated plans, historical reports**: Move to `docs/archive/`
- **User guides, API docs**: Update root `README.md` or `USER_MANUAL.md`

### Archiving Guidelines

Move documentation to `docs/archive/` when:
- It describes features that have been replaced
- It contains outdated procedures or instructions
- It's superseded by newer documentation
- It's historical but worth keeping for reference

Keep in `docs/current/` when:
- It's actively referenced by developers or users
- It describes current system features
- It contains troubleshooting guides still in use
- It's less than 90 days old and describes recent changes

## 🔄 Recent Reorganization

**Date**: January 20, 2026

Reorganized documentation from root directory:
- Moved 8 documents to `docs/current/`
- Moved 11 documents to `docs/archive/`
- Removed 3 obsolete files (Dockerfile.old, Dockerfile.test, enhanced_dashboards.ndjson)
- Created structured documentation hierarchy
- Kept only essential files in root (README.md, USER_MANUAL.md, CLAUDE.md)

**Result**: Clean root directory with well-organized documentation structure.

---

**Last Updated**: January 20, 2026
