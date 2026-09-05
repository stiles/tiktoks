"""Fetchers that turn a public dataset into a frame keyed by ISO 3166-1 alpha-3.

Most of `docs/guess-the-map-ideas.md` is one query each. These modules exist so a
map post is a catalog entry rather than a hand-built CSV.
"""

from tiktoks.sources.wikidata import members, query
from tiktoks.sources.worldbank import indicator

__all__ = ["indicator", "members", "query"]
