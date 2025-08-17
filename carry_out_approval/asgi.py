"""
ASGI config for carry_out_approval project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'carry_out_approval.settings')

# Djangoの初期化（staticfiles設定を含む）
django_asgi_app = get_asgi_application()

# Long Polling 移行に伴い WebSocket / Channels 依存を撤去。
# 標準 runserver / ASGI サーバはいずれもこのシンプルな application を利用。
application = django_asgi_app
