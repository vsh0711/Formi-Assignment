"""The ONE cohort object (C2). Detection, experiments, schedule and the supervisor view all go through here.

A *cell* is the full feature tuple of a lead (lang, city_tier, age_band, value_band) - the finest grain we keep
statistics at. A *Cohort* is a predicate over cells with a canonical, content-derived id, so "seniors in Tamil"
has one id everywhere. `assign` reproduces the simulator's documented rule exactly: cohorts are evaluated in
order, a lead belongs to the first one it matches, otherwise to 'default'.
"""
from __future__ import annotations

from dataclasses import dataclass

FEATURES: list[str] = ["age_band", "city_tier", "lang", "value_band"]  # canonical (sorted) order of cell tuples


def set_features(names: list[str]) -> None:
    global FEATURES
    FEATURES = sorted(names)


def cell_of(features: dict) -> str:
    return "|".join(str(features.get(f, "?")) for f in FEATURES)


_cell_cache: dict[str, tuple] = {}


def cell_tuple(cell: str) -> tuple:
    t = _cell_cache.get(cell)
    if t is None:
        t = _cell_cache[cell] = tuple(cell.split("|"))
    return t


@dataclass(frozen=True)
class Cohort:
    where: tuple  # ((feature, (values...)), ...) sorted by feature

    @staticmethod
    def make(where: dict) -> "Cohort":
        return Cohort(tuple(sorted((f, tuple(sorted(v))) for f, v in where.items())))

    @property
    def id(self) -> str:
        return "&".join(f"{f}={'+'.join(v)}" for f, v in self.where)

    def as_where(self) -> dict:
        return {f: list(v) for f, v in self.where}

    def to_config(self) -> dict:
        return {"id": self.id, "where": self.as_where()}

    def matches(self, cell: str) -> bool:
        t = cell_tuple(cell)
        for f, vals in self.where:
            if t[FEATURES.index(f)] not in vals:
                return False
        return True

    @property
    def label(self) -> str:
        return self.id


def assign(cohorts: list[dict], cell: str) -> str:
    """Simulator semantics: first matching cohort in order, else 'default'."""
    t = cell_tuple(cell)
    for c in cohorts:
        ok = True
        for f, vals in c["where"].items():
            if t[FEATURES.index(f)] not in vals:
                ok = False
                break
        if ok:
            return c["id"]
    return "default"


def segment_cohorts(levels: dict[str, list[str]]) -> list[Cohort]:
    """Single-feature, single-level candidate segments (the pre-registered family for heterogeneity tests)."""
    return [Cohort.make({f: [v]}) for f in sorted(levels) for v in sorted(levels[f])]
