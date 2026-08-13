"""Static files storage."""

from django.contrib.staticfiles.storage import ManifestStaticFilesStorage


class ForgivingManifestStaticFilesStorage(ManifestStaticFilesStorage):
    """
    Hashed static filenames, but a missing manifest entry is not fatal.

    nginx serves /static/ with ``immutable``, so filenames have to change when
    contents do. The strict default turns any unreferenced file into a hard
    500 for the whole page, and it also breaks any code path that renders a
    template before ``collectstatic`` has run — the test suite, most notably.
    Falling back to the unhashed name degrades caching for that one file
    instead of taking the page down.
    """

    manifest_strict = False
