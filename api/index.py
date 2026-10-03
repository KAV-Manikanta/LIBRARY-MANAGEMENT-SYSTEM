import os
import sys

# Ensure project root is in the Python search path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.app import app

class VercelPathFixMiddleware:
    """Restores the original request URL from Vercel's x-matched-path header."""
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        matched = environ.get('HTTP_X_MATCHED_PATH') or environ.get('x-matched-path')
        if matched:
            environ['PATH_INFO'] = matched.split('?')[0]
        return self.wsgi_app(environ, start_response)

app.wsgi_app = VercelPathFixMiddleware(app.wsgi_app)
handler = app
