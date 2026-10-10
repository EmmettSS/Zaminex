import os

from django.core.wsgi import get_wsgi_application

from apps.common.staticfiles import static_files_handler

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

application = static_files_handler(get_wsgi_application())
