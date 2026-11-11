"""Errors shared by the source adapters."""


class BlockedError(RuntimeError):
    """A source answered HTTP 403 or 429. Stop requesting from it; a rerun resumes from the cache."""
