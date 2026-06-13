"""
Thread-local current-user tracking.

Signal handlers run outside the request/response cycle and have no access to
``request.user``. This middleware stashes the acting user for the duration of
each request so ``record()`` can attribute automatic audit entries. Outside a
request (Celery sync, management commands) the user is ``None`` → logged as
"System".
"""

import threading

_state = threading.local()


def get_current_user():
    return getattr(_state, "user", None)


def set_current_user(user):
    _state.user = user


class CurrentUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        set_current_user(getattr(request, "user", None))
        try:
            return self.get_response(request)
        finally:
            set_current_user(None)
