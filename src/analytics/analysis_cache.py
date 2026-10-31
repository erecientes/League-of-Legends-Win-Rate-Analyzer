"""
Extracts and builds analytical Parquet DataFrames from raw match cache.

Usage:
    from analysis_cache import build_or_update_frames, best_items_per_slot, best_runes_per_slot
    matches_df, items_df, runes_df = build_or_update_frames(cache, my_puuid)
"""

from pathlib import Path
import pandas as pd
from config import DATA_DIR
from analytics.item_data import classify_item, load_item_data, patch_from_game_version

SCHEMA_VERSION = 1


def _find_my_participant(match_data: dict, my_puuid: str) -> dict:
    """Find the participant record matching my_puuid in match_data."""
    return next(p for p in match_data["info"]["participants"] if p["puuid"] == my_puuid)


def _extract_champions(match_data: dict) -> frozenset:
    """Extract set of all 10 champion names in the match."""
    return frozenset(p["championName"] for p in match_data["info"]["participants"])


def _extract_runes(participant: dict) -> list[tuple[str, int]]:
    """Extract list of (slot_label, rune_id) tuples from participant perks."""
    runes = []
    styles = participant.get("perks", {}).get("styles", [])
    for style in styles:
        is_primary = style.get("description") == "primary"
        prefix = "primary" if is_primary else "secondary"
        for i, selection in enumerate(style.get("selections", [])):
            label = "keystone" if (is_primary and i == 0) else f"{prefix}_{i}"
            runes.append((label, selection["perk"]))
    return runes


def _extract_build_order(
    match_data: dict, timeline_data: dict, my_puuid: str, item_data: dict
) -> list[tuple[str, int]]:
    """Extract chronological completed items [(category, item_id), ...], resolving ITEM_UNDO events."""
    my_participant_id = _find_my_participant(match_data, my_puuid)["participantId"]

    raw_purchases = []
    for frame in timeline_data["info"]["frames"]:
        for event in frame.get("events", []):
            if event.get("participantId") != my_participant_id:
                continue
            if event["type"] == "ITEM_PURCHASED":
                raw_purchases.append(event["itemId"])
            elif event["type"] == "ITEM_UNDO":
                before_id = event.get("beforeId")
                if before_id:
                    for i in range(len(raw_purchases) - 1, -1, -1):
                        if raw_purchases[i] == before_id:
                            raw_purchases.pop(i)
                            break

    completed = []
    for item_id in raw_purchases:
        category = classify_item(item_id, item_data)
        if category is not None:
            completed.append((category, item_id))
    return completed


def _process_match(match_id: str, match_data: dict, timeline_data: dict, my_puuid: str, item_data: dict):
    """Parse raw match and timeline JSON into flat tabular row dictionaries."""
    me = _find_my_participant(match_data, my_puuid)

    match_row = {
        "match_id": match_id,
        "champions": _extract_champions(match_data),
        "win": me["win"],
        "game_duration_sec": match_data["info"]["gameDuration"],
    }

    category_counts: dict[str, int] = {}
    item_rows = []
    for category, item_id in _extract_build_order(match_data, timeline_data, my_puuid, item_data):
        category_counts[category] = category_counts.get(category, 0) + 1
        item_rows.append({
            "match_id": match_id,
            "category": category,
            "purchase_index": category_counts[category],
            "item_id": item_id,
            "win": me["win"],
        })

    rune_rows = [
        {"match_id": match_id, "slot": slot, "rune_id": rune_id, "win": me["win"]}
        for slot, rune_id in _extract_runes(me)
    ]

    return match_row, item_rows, rune_rows


def build_or_update_frames(cache, my_puuid: str, cache_dir: str | None = None):
    """Load or incrementally build matches, items, and runes DataFrames."""
    if cache_dir is None:
        cache_dir_path = DATA_DIR / f"analysis_cache_{my_puuid}"
    else:
        cache_dir_path = Path(cache_dir)
    cache_dir_path.mkdir(exist_ok=True, parents=True)

    matches_path = cache_dir_path / "matches.parquet"
    items_path = cache_dir_path / "items.parquet"
    runes_path = cache_dir_path / "runes.parquet"
    version_path = cache_dir_path / "schema_version.txt"

    stored_version = int(version_path.read_text()) if version_path.exists() else None

    if matches_path.exists() and stored_version == SCHEMA_VERSION:
        matches_df = pd.read_parquet(matches_path)
        items_df = pd.read_parquet(items_path)
        runes_df = pd.read_parquet(runes_path)
        already_processed = set(matches_df["match_id"])
    else:
        matches_df = pd.DataFrame(columns=["match_id", "champions", "win", "game_duration_sec"])
        items_df = pd.DataFrame(columns=["match_id", "category", "purchase_index", "item_id", "win"])
        runes_df = pd.DataFrame(columns=["match_id", "slot", "rune_id", "win"])
        already_processed = set()

    new_match_ids = [mid for mid in cache.get_all_match_ids() if mid not in already_processed]

    if new_match_ids:
        item_data_cache: dict[str, dict] = {}
        new_match_rows, new_item_rows, new_rune_rows = [], [], []

        for match_id in new_match_ids:
            match_data = cache.get_match_data(match_id)
            timeline_data = cache.get_timeline_data(match_id)
            if timeline_data is None:
                continue

            patch = patch_from_game_version(match_data["info"]["gameVersion"])
            if patch not in item_data_cache:
                item_data_cache[patch] = load_item_data(patch)

            m_row, i_rows, r_rows = _process_match(
                match_id, match_data, timeline_data, my_puuid, item_data_cache[patch]
            )
            new_match_rows.append(m_row)
            new_item_rows.extend(i_rows)
            new_rune_rows.extend(r_rows)

        matches_df = pd.concat([matches_df, pd.DataFrame(new_match_rows)], ignore_index=True)
        items_df = pd.concat([items_df, pd.DataFrame(new_item_rows)], ignore_index=True)
        runes_df = pd.concat([runes_df, pd.DataFrame(new_rune_rows)], ignore_index=True)

        matches_df["champions"] = matches_df["champions"].apply(
            lambda c: tuple(sorted(c)) if isinstance(c, frozenset) else c
        )

        matches_df.to_parquet(matches_path)
        items_df.to_parquet(items_path)
        runes_df.to_parquet(runes_path)

    version_path.write_text(str(SCHEMA_VERSION))
    return matches_df, items_df, runes_df


def _wilson_lower_bound(wins: pd.Series, games: pd.Series, z: float = 1.96) -> pd.Series:
    """Calculate Wilson score lower bound for binomial confidence intervals."""
    phat = wins / games
    denom = 1 + z**2 / games
    center = phat + z**2 / (2 * games)
    margin = z * ((phat * (1 - phat) + z**2 / (4 * games)) / games).pow(0.5)
    return (center - margin) / denom


def item_win_rates(matches_df: pd.DataFrame, items_df: pd.DataFrame, mask: pd.Series) -> pd.DataFrame:
    """Calculate win rate and Wilson score per item slot under mask."""
    filtered_ids = set(matches_df.loc[mask, "match_id"])
    filtered_items = items_df[items_df["match_id"].isin(filtered_ids)]
    result = (
        filtered_items.groupby(["category", "purchase_index", "item_id"])["win"]
        .agg(wins="sum", games="count")
        .reset_index()
    )
    result["win_rate"] = result["wins"] / result["games"]
    result["wilson_score"] = _wilson_lower_bound(result["wins"], result["games"])
    return result.drop(columns="wins")


def rune_win_rates(matches_df: pd.DataFrame, runes_df: pd.DataFrame, mask: pd.Series) -> pd.DataFrame:
    """Calculate win rate and Wilson score per rune under mask."""
    filtered_ids = set(matches_df.loc[mask, "match_id"])
    filtered_runes = runes_df[runes_df["match_id"].isin(filtered_ids)]
    result = (
        filtered_runes.groupby(["slot", "rune_id"])["win"]
        .agg(wins="sum", games="count")
        .reset_index()
    )
    result["win_rate"] = result["wins"] / result["games"]
    result["wilson_score"] = _wilson_lower_bound(result["wins"], result["games"])
    return result.drop(columns="wins")


def win_rate_by_duration(matches_df: pd.DataFrame, mask: pd.Series, bucket_minutes: int = 5) -> pd.DataFrame:
    """Group match win rates into time duration buckets."""
    filtered = matches_df[mask].copy()
    bucket_seconds = bucket_minutes * 60
    filtered["duration_bucket_min"] = (
        (filtered["game_duration_sec"] // bucket_seconds) * bucket_minutes
    )
    return (
        filtered.groupby("duration_bucket_min")["win"]
        .agg(win_rate="mean", games="count")
        .reset_index()
        .sort_values("duration_bucket_min")
    )


def best_items_per_slot(matches_df: pd.DataFrame, items_df: pd.DataFrame, mask: pd.Series, top_n: int = 5) -> pd.DataFrame:
    """Rank top item choices per category and purchase index by Wilson score."""
    rates = item_win_rates(matches_df, items_df, mask)
    return (
        rates.sort_values("wilson_score", ascending=False)
        .groupby(["category", "purchase_index"])
        .head(top_n)
        .sort_values(["category", "purchase_index", "wilson_score"], ascending=[True, True, False])
        .reset_index(drop=True)
    )


def best_runes_per_slot(matches_df: pd.DataFrame, runes_df: pd.DataFrame, mask: pd.Series, top_n: int = 5) -> pd.DataFrame:
    """Rank top rune choices per slot by Wilson score."""
    rates = rune_win_rates(matches_df, runes_df, mask)
    return (
        rates.sort_values("wilson_score", ascending=False)
        .groupby("slot")
        .head(top_n)
        .sort_values(["slot", "wilson_score"], ascending=[True, False])
        .reset_index(drop=True)
    )
