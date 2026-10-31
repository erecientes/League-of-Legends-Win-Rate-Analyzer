"""
Composable filter mask builder for matches DataFrame.

Usage:
    from match_filter import MatchFilter, build_mask
    mask = build_mask(matches_df, MatchFilter(champions={"Udyr", "Zed"}, min_champions_required=1))
"""

from dataclasses import dataclass, field
import pandas as pd


@dataclass
class MatchFilter:
    """Filter specifications for selecting matches."""
    champions: set[str] = field(default_factory=set)
    min_champions_required: int = 1


def _champion_stage(matches_df: pd.DataFrame, spec: MatchFilter) -> pd.Series:
    """Filter rows containing at least min_champions_required in spec.champions."""
    if not spec.champions:
        return pd.Series(True, index=matches_df.index)
    return matches_df["champions"].apply(
        lambda champs: len(spec.champions & set(champs)) >= spec.min_champions_required
    )


_FILTER_STAGES = [_champion_stage]


def build_mask(matches_df: pd.DataFrame, spec: MatchFilter) -> pd.Series:
    """Evaluate composed boolean mask across registered filter stages."""
    mask = pd.Series(True, index=matches_df.index)
    for stage in _FILTER_STAGES:
        mask &= stage(matches_df, spec)
    return mask
