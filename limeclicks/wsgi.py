"""
WSGI config for limeclicks project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/wsgi/
"""

import os

# Import gevent configuration before Django initialization
from limeclicks import gevent_config

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')

application = get_wsgi_application()
