#!/bin/bash
# Static type checking of the API code (strict mode, see mypy.ini)
set -e
cd "$(dirname "$0")/.."
mypy --config-file mypy.ini *.py blueprints/
