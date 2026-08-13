"""
Shared pagination helpers.

Page size lives in the URL (`?per_page=`) so a paginated view stays
bookmarkable, matching how the reports app carries column state.
Render the controls with ``{% include "partials/pagination.html" %}``.
"""

import urllib.parse

PAGE_SIZES = (25, 50, 100)
DEFAULT_PAGE_SIZE = 50


def parse_per_page(request, default: int = DEFAULT_PAGE_SIZE) -> int:
    """Read `?per_page=`, falling back to the default for anything unexpected."""
    try:
        per_page = int(request.GET.get("per_page", default))
    except (ValueError, TypeError):
        return default
    return per_page if per_page in PAGE_SIZES else default


def strip_params(request, *exclude_keys: str) -> str:
    """Rebuild the current query string without the given keys."""
    params = [(k, v) for k, v in request.GET.items() if k not in exclude_keys]
    return urllib.parse.urlencode(params)
