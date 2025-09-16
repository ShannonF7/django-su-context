"""
WSGI config for feedback_project project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/wsgi/
"""

import os
import sys
import pysqlite3

# 强制使用 pysqlite3 代替 sqlite3
sys.modules['sqlite3'] = pysqlite3


from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'feedback_project.settings')

application = get_wsgi_application()
