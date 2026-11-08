"""The QueryService's spatial and statistical tools (REQ-35).

Specification: contracts/query_service_contract.py, CONTRACT_QUERY_TOOLS (SLICE-4 batch 3):
POST-TOOL-1, POST-TOOL-2, ERRORS-TOOL-1. Every read goes through the engine's execute_sql, so the
same read-only checks and limits apply, and every row is read page by page. Runtime declarations
are independent of the contract module; tests bridge the two (CL11-F).
"""

import math
import re
import statistics
from collections.abc import Mapping
from typing import Final

from .ask import SourceCitation, SqlQueryResult
from .engine import MAX_ROW_LIMIT, WarehouseQueryEngine

SITES_SOURCE_FILE: Final = (
    "repo:data/external/second-harvest-food-finder/second_harvest_food_finder_locations.csv"
)
BLOCKS_SOURCE_FILE: Final = "repo:data/external/census-2020-blocks/central-fl-blocks-2020.csv"
TRACTS_SOURCE_FILE: Final = (
    "repo:data/external/second-harvest-food-finder/central_fl_tract_pantry_coverage.csv"
)
EARTH_RADIUS_MILES: Final = 3958.8
MAX_NEAR_MILES: Final = 20.0
SITES_NEAR_COLUMNS: Final[tuple[str, ...]] = ("storeid", "name", "address", "county", "miles")
CORRELATION_COLUMNS: Final[tuple[str, ...]] = ("n", "coefficient", "method", "excluded")
CORRELATION_CAVEATS: Final[tuple[str, ...]] = (
    "Correlation does not show cause.",
    "Rows with a missing or non-numeric value are left out.",
)
PAGE_TEMPLATE: Final = (
    "SELECT * FROM ({sql}) AS page_source ORDER BY ALL LIMIT {limit} OFFSET {offset}"
)
_GEOID: Final = re.compile(r"^\d{11}$")
MAX_LAT: Final = 90.0
MAX_LON: Final = 180.0
CORRELATION_COLUMN_COUNT: Final = 2
CORRELATION_MIN_N: Final = 3


class ToolArgumentError(ValueError):
    """ERRORS-TOOL-1: a tool was called with arguments outside its contract."""


def miles_between(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Straight-line miles on the Build's sphere (the Build's haversine)."""
    p = math.pi / 180.0
    a = (
        math.sin((lat2 - lat1) * p / 2.0) ** 2
        + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2.0) ** 2
    )
    return 2.0 * EARTH_RADIUS_MILES * math.asin(math.sqrt(a))


def _number(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(str(value))
    except ValueError:
        return None
    return number if math.isfinite(number) else None


class _Read:
    """Every row of one query, read page by page, with the query's tables and citations."""

    def __init__(self, engine: WarehouseQueryEngine, sql: str) -> None:
        self.columns: tuple[str, ...] = ()
        self.rows: list[Mapping[str, object]] = []
        self.referenced: tuple[str, ...] = ()
        self.citations: tuple[SourceCitation, ...] = ()
        offset = 0
        while True:
            page = engine.execute_sql(
                PAGE_TEMPLATE.format(sql=sql, limit=MAX_ROW_LIMIT, offset=offset),
                row_limit=MAX_ROW_LIMIT,
            )
            self.columns = page.columns
            self.referenced = page.referenced_tables
            self.citations = page.citations
            self.rows.extend(page.rows)
            if len(page.rows) < MAX_ROW_LIMIT:
                break
            offset += MAX_ROW_LIMIT


class WarehouseTools:
    """sites_near and stats_correlate over an open engine."""

    def __init__(self, engine: WarehouseQueryEngine) -> None:
        self._engine = engine
        self._sites = engine.table_for_source(SITES_SOURCE_FILE)
        self._blocks = engine.table_for_source(BLOCKS_SOURCE_FILE)
        tracts = engine.table_for_source(TRACTS_SOURCE_FILE)
        # table names come from the catalog and match the adapter's table-name pattern
        read = _Read(engine, f'SELECT geoid FROM "{tracts}"')  # noqa: S608
        self._known = frozenset(str(r["geoid"]) for r in read.rows)

    @property
    def known_geoids(self) -> frozenset[str]:
        """Every tract GEOID in the tract table."""
        return self._known

    def sites_near(
        self,
        geoid: str | None = None,
        lat: float | None = None,
        lon: float | None = None,
        *,
        miles: float,
    ) -> SqlQueryResult:
        """Second Harvest sites within miles of a point or of a tract's populated blocks.

        Raises:
            ToolArgumentError: ERRORS-TOOL-1, the arguments are outside the contract.
        """
        by_point = lat is not None or lon is not None
        if (geoid is None) == (not by_point) or (by_point and (lat is None or lon is None)):
            raise ToolArgumentError(
                "ERRORS-TOOL-1 violation: give exactly one of geoid or lat and lon"
            )
        if (
            not isinstance(miles, int | float)
            or isinstance(miles, bool)
            or not 0 < miles <= MAX_NEAR_MILES
        ):
            raise ToolArgumentError(
                f"ERRORS-TOOL-1 violation: miles {miles!r} is outside (0, {MAX_NEAR_MILES}]"
            )
        referenced = [self._sites]
        citations: dict[str, SourceCitation] = {}
        if lat is not None and lon is not None:
            if not -MAX_LAT <= lat <= MAX_LAT or not -MAX_LON <= lon <= MAX_LON:
                raise ToolArgumentError(
                    f"ERRORS-TOOL-1 violation: point ({lat}, {lon}) is not a latitude and longitude"
                )
            origins = [(float(lat), float(lon))]
        else:
            if geoid is None or not _GEOID.match(geoid) or geoid not in self._known:
                raise ToolArgumentError(f"ERRORS-TOOL-1 violation: {geoid!r} is not a known tract")
            blocks = _Read(
                self._engine,
                # geoid is eleven digits from the tract table; the table name is the catalog's
                f"SELECT geoid20, pop20, lat, lon FROM \"{self._blocks}\" WHERE geoid20 LIKE '{geoid}%'",  # noqa: S608, E501
            )
            origins = [
                (float(str(b["lat"])), float(str(b["lon"])))
                for b in blocks.rows
                if int(str(b["pop20"])) > 0
            ]
            referenced.append(self._blocks)
            citations.update({c.table_name: c for c in blocks.citations})
        sites = _Read(
            self._engine,
            f'SELECT storeid, name, address, county, lat, lng FROM "{self._sites}"',  # noqa: S608
        )
        citations.update({c.table_name: c for c in sites.citations})
        rows: list[tuple[str, str, str, str, float]] = []
        if origins:
            for s in sites.rows:
                slat, slon = float(str(s["lat"])), float(str(s["lng"]))
                d = min(miles_between(olat, olon, slat, slon) for olat, olon in origins)
                if d <= miles:
                    rows.append(
                        (str(s["storeid"]), str(s["name"]), str(s["address"]), str(s["county"]), d)
                    )
        rows.sort(key=lambda r: (r[4], r[0]))
        return SqlQueryResult(
            columns=SITES_NEAR_COLUMNS,
            rows=tuple(dict(zip(SITES_NEAR_COLUMNS, r, strict=True)) for r in rows),
            row_count=len(rows),
            truncated=False,
            referenced_tables=tuple(referenced),
            citations=tuple(citations[t] for t in referenced if t in citations),
        )

    def stats_correlate(self, sql: str) -> SqlQueryResult:
        """Pearson correlation over every row of a two-column SELECT (POST-TOOL-2).

        Raises:
            ToolArgumentError: ERRORS-TOOL-1, the query does not return exactly two columns.
            RejectedSqlError, QueryTimeoutError: from the engine, for a refused or slow query.
        """
        probe = self._engine.execute_sql(sql, row_limit=1)
        if len(probe.columns) != CORRELATION_COLUMN_COUNT:
            raise ToolArgumentError(
                f"ERRORS-TOOL-1 violation: the query returns {len(probe.columns)} columns, not 2"
            )
        read = _Read(self._engine, sql)
        a, b = read.columns
        pairs = [(_number(r[a]), _number(r[b])) for r in read.rows]
        good = [(x, y) for x, y in pairs if x is not None and y is not None]
        coefficient: float | None = None
        if len(good) >= CORRELATION_MIN_N:
            try:
                coefficient = statistics.correlation([x for x, _ in good], [y for _, y in good])
            except statistics.StatisticsError:
                coefficient = None
        row = {
            "n": len(good),
            "coefficient": coefficient,
            "method": "pearson",
            "excluded": len(pairs) - len(good),
        }
        return SqlQueryResult(
            columns=CORRELATION_COLUMNS,
            rows=(row,),
            row_count=1,
            truncated=False,
            referenced_tables=probe.referenced_tables,
            citations=probe.citations,
        )
