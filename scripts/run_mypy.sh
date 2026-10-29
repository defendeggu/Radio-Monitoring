#!/bin/bash
# Static type checking of the API code (strict mode, see [tool.mypy] in pyproject.toml)
set -e
cd "$(dirname "$0")/.."
mypy radiomoni/
