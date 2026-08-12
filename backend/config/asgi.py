import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

# Must be built before importing anything that touches models.
django_asgi_app = get_asgi_application()

from apps.ticketing.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        # OriginValidator rejects sockets opened from other sites, which is the
        # WebSocket equivalent of CSRF protection; AuthMiddlewareStack resolves
        # the session cookie so consumers can authorise the user.
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
        ),
    }
)
