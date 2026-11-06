#!/bin/sh
# Start the SDRplay API service when the image has it (WITH_SDRPLAY=1), then the command.
# The service talks to the RSP over USB; sdrplay_rx (through SoapySDRPlay3) talks to the service.
set -e
if [ -x /opt/sdrplay_api/sdrplay_apiService ]; then
  /opt/sdrplay_api/sdrplay_apiService >/tmp/sdrplay_apiService.log 2>&1 &
fi
exec "$@"
