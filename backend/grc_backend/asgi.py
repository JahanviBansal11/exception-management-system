import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'grc_backend.settings')

django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from exceptions.ws_auth import JwtAuthMiddleware
import exceptions.routing

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': AllowedHostsOriginValidator(
        JwtAuthMiddleware(
            URLRouter(exceptions.routing.websocket_urlpatterns)
        )
    ),
})
