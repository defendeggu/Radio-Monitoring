#!/usr/bin/env python3
"""
RadioMoni API entry point.

Production:   gunicorn --config config/gunicorn_config.py radiomoni.api_service:app
Development:  ALLOW_INSECURE=true python3 -m radiomoni.api_service

The application itself is assembled in app_factory.create_app().
"""

import os

from dotenv import load_dotenv

# .env is optional; real deployments pass variables through Docker Compose.
load_dotenv()

from radiomoni.app_factory import create_app  # noqa: E402  (env must be loaded first)

app = create_app()


if __name__ == '__main__':
    import logging
    logger = logging.getLogger(__name__)
    logger.warning("DEVELOPMENT MODE - Flask built-in server. Use Gunicorn in production.")
    app.run(host=os.getenv('API_HOST', '127.0.0.1'), port=int(os.getenv('API_PORT', '5000')),
            debug=os.getenv('FLASK_DEBUG', 'false').lower() == 'true', use_reloader=False, threaded=True)
