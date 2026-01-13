import os
import sys
from pathlib import Path
from django.core.asgi import get_asgi_application

ROOT_DIR = Path(__file__).resolve(strict=True).parent.parent
sys.path.append(
    str(ROOT_DIR / "root")
)  # this line adds the 'root' directory to the Python path for module resolution

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "root.settings")

# This application object is used by any ASGI server configured to use this file.
django_application = get_asgi_application()
from channels.routing import ProtocolTypeRouter, URLRouter
from chat.middleware import TokenAuthMiddleware
from chat.routing import websocket_urlpatterns


application = ProtocolTypeRouter(
    {
        "http": django_application,
        "websocket": TokenAuthMiddleware(URLRouter(websocket_urlpatterns)),
    }
)
