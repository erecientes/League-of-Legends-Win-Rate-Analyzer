"""
analysis_cache.py

Derives fast, pre-parsed pandas DataFrames from the raw JSON blobs stored
in MatchCache, for interactive filtering. Each match is parsed once and
the result persisted to parquet, so repeated queries run against
already-parsed data instead of re-parsing JSON. Only new matches are
(re)processed on a given call.

Produces three DataFrames:
  matches_df -- one row per match: champions (both teams), win/loss, duration.
  items_df   -- one row per completed item purchased (legendaries, boots),
                labeled by category, with purchase_index counted per category.
  runes_df   -- one row per rune selected, labeled by slot.

Usage:
    from match_filter import MatchFilter, build_mask
    from analysis_cache import build_or_update_frames, best_items_per_slot

    matches_df, items_df, runes_df = build_or_update_frames(cache, my_puuid)
    mask = build_mask(matches_df, MatchFilter(champions={"Yuumi", "Zed"}, min_champions_required=1))
    print(best_items_per_slot(matches_df, items_df, mask))
"""

from pathlib import Path

import pandas as pd

from config import DATA_DIR
from item_data import classify_item, load_item_data, patch_from_game_version

# Incremented whenever _process_match's extraction logic changes (a field
# added, a column changed, a new table added). On mismatch,
# build_or_update_frames discards the cached frames and reprocesses every
# match from scratch, rather than silently returning frames from an
# outdated schema.
SCHEMA_VERSION = 1


# ---- Parsing raw match_data / timeline_data into flat rows -----------------

def _find_my_participant(match_data: dict, my_puuid: str) -> dict:
    participants = match_data["info"]["participants"]
    return next(p for p in participants if p["puuid"] == my_puuid)


def _extract_champions(match_data: dict) -> frozenset:
    """All 10 champions in the match, both teams combined."""
    return frozenset(p["championName"] for p in match_data["info"]["participants"])


def _extract_runes(participant: dict) -> list[tuple[str, int]]:
    """Returns [(slot_label, rune_id), ...], e.g. [("keystone", 8214), ("primary_1", 8226), ...].

    Unverified against a current match-v5 response; Riot's perks/styles
    schema has changed in past patches and may change again."""
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
    """Returns [(category, item_id), ...] in chronological purchase order,
    restricted to completed items (legendaries, boots) via classify_item.
    ITEM_UNDO is resolved against the raw purchase list before filtering,
    so beforeId always matches something actually purchased.

    Approximate: not verified against production data, particularly item
    upgrades/combines and ITEM_UNDO's beforeId/afterId behavior."""
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
    """Returns (match_row: dict, item_rows: list[dict], rune_rows: list[dict])."""
    me = _find_my_participant(match_data, my_puuid)

    match_row = {
        "match_id": match_id,
        "champions": _extract_champions(match_data),
        "win": me["win"],
        "game_duration_sec": match_data["info"]["gameDuration"],
    }

    # Counted per category, so boots (max 1 per game) never share slot
    # numbers with legendaries.
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


# ---- Building / incrementally updating the cached frames -------------------

def build_or_update_frames(cache, my_puuid: str, cache_dir: str | None = None):
    """Loads cached parquet frames if present and schema-current, processes
    any matches not yet in them, and appends the result. A schema mismatch
    or missing cache reprocesses every match from scratch.

    cache_dir defaults to a directory scoped to my_puuid under DATA_DIR
    (mirrors the matches_<puuid>.db naming convention); override mainly
    useful for pointing tests at a scratch directory."""
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
        # Either no cache yet, or the schema changed since it was written --
        # either way, everything gets reprocessed from the raw JSON in `cache`.
        matches_df = pd.DataFrame(columns=["match_id", "champions", "win", "game_duration_sec"])
        items_df = pd.DataFrame(columns=["match_id", "category", "purchase_index", "item_id", "win"])
        runes_df = pd.DataFrame(columns=["match_id", "slot", "rune_id", "win"])
        already_processed = set()

    new_match_ids = [mid for mid in cache.get_all_match_ids() if mid not in already_processed]

    if new_match_ids:
        # Populated lazily; matches sharing a patch reuse the same
        # item_data instead of each re-fetching it.
        item_data_cache: dict[str, dict] = {}

        new_match_rows, new_item_rows, new_rune_rows = [], [], []
        for match_id in new_match_ids:
            match_data = cache.get_match_data(match_id)
            timeline_data = cache.get_timeline_data(match_id)
            if timeline_data is None:
                continue  # not yet backfilled; picked up on a subsequent call

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

        # Parquet does not support storing a frozenset directly; stored as
        # a sorted tuple instead, which remains hashable and filterable.
        matches_df["champions"] = matches_df["champions"].apply(
            lambda c: tuple(sorted(c)) if isinstance(c, frozenset) else c
        )

        matches_df.to_parquet(matches_path)
        items_df.to_parquet(items_path)
        runes_df.to_parquet(runes_path)

    version_path.write_text(str(SCHEMA_VERSION))

    return matches_df, items_df, runes_df


# ---- The actual interactive queries -----------------------------------------

def _wilson_lower_bound(wins: pd.Series, games: pd.Series, z: float = 1.96) -> pd.Series:
    """Lower bound of the Wilson score confidence interval for a binomial
    win rate. Ranking by this instead of raw win_rate means a 100% win
    rate over 1 game scores far lower than 65% over 200 games -- the
    bound tightens toward the true win rate as games grows."""
    phat = wins / games
    denom = 1 + z**2 / games
    center = phat + z**2 / (2 * games)
    margin = z * ((phat * (1 - phat) + z**2 / (4 * games)) / games).pow(0.5)
    return (center - margin) / denom


def item_win_rates(matches_df: pd.DataFrame, items_df: pd.DataFrame, mask: pd.Series) -> pd.DataFrame:
    """Win rate + game count per (category, purchase_index, item_id),
    restricted to matches passing the filter."""
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
    """Win rate + game count per (slot, rune_id), restricted to matches
    passing the filter."""
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
    """Win rate + game count, bucketed by game duration rounded down to
    the nearest bucket_minutes."""
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


def best_items_per_slot(matches_df, items_df, mask, top_n: int = 5) -> pd.DataFrame:
    """Top top_n item(s) per (category, purchase_index), ranked by Wilson
    score (not raw win_rate), restricted to matches passing the filter."""
    rates = item_win_rates(matches_df, items_df, mask)
    return (
        rates.sort_values("wilson_score", ascending=False)
        .groupby(["category", "purchase_index"])
        .head(top_n)
        .sort_values(["category", "purchase_index", "wilson_score"], ascending=[True, True, False])
        .reset_index(drop=True)
    )


def best_runes_per_slot(matches_df, runes_df, mask, top_n: int = 5) -> pd.DataFrame:
    """Top top_n rune(s) per slot, ranked by Wilson score, restricted to
    matches passing the filter."""
    rates = rune_win_rates(matches_df, runes_df, mask)
    return (
        rates.sort_values("wilson_score", ascending=False)
        .groupby("slot")
        .head(top_n)
        .sort_values(["slot", "wilson_score"], ascending=[True, False])
        .reset_index(drop=True)
    )