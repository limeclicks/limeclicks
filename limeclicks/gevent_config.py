"""
Gevent configuration for Django
This module handles gevent monkey patching and PostgreSQL async support
"""

import os
import sys

def patch_for_gevent():
    """
    Apply gevent monkey patching if running under gevent worker class
    This should be called at the very beginning of the application
    """
    # Check if we're running under gunicorn with gevent
    if 'gunicorn' in sys.modules or os.environ.get('SERVER_SOFTWARE') == 'gevent':
        try:
            from gevent import monkey
            monkey.patch_all()
            
            # Enable PostgreSQL async support with psycogreen
            try:
                from psycogreen.gevent import patch_psycopg
                patch_psycopg()
                print("Gevent monkey patching and psycogreen applied successfully")
            except ImportError:
                print("psycogreen not installed, PostgreSQL will run in sync mode")
                
        except ImportError:
            print("Gevent not installed, running in standard mode")

# Apply patches when module is imported
patch_for_gevent()