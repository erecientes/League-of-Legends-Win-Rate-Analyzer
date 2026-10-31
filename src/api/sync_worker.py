"""
Background worker for historical match backfill and catchup ingestion.

Usage:
    from api.sync_worker import start_sync_worker
    worker = start_sync_worker(puuid, client, cache, on_batch_complete, on_sync_finished)
"""

import threading
import time
from typing import Callable
from api.riot_client import RiotAPIClient, RiotAPIError, InvalidAPIKeyError
from storage.match_cache import MatchCache


class MatchSyncWorker(threading.Thread):
    """Background thread that crawls backwards from the latest match to backfill history."""

    def __init__(
        self,
        puuid: str,
        client: RiotAPIClient,
        cache: MatchCache,
        on_batch_complete: Callable[[int], None] | None = None,
        on_sync_finished: Callable[[], None] | None = None,
        batch_size: int = 20,
        request_delay: float = 1.2,
    ):
        super().__init__(daemon=True)
        self.puuid = puuid
        self.client = client
        self.cache = cache
        self.on_batch_complete = on_batch_complete
        self.on_sync_finished = on_sync_finished
        self.batch_size = batch_size
        self.request_delay = request_delay
        self._stop_event = threading.Event()

    def stop(self):
        """Signal the worker to gracefully stop syncing."""
        self._stop_event.set()

    def run(self):
        """Execute the continuous reverse-crawl until the account history is exhausted."""
        start_index = 0

        while not self._stop_event.is_set():
            try:
                # Fetch next batch of match IDs
                match_ids = self.client.get_match_ids(
                    self.puuid, start=start_index, count=self.batch_size
                )
            except (RiotAPIError, InvalidAPIKeyError) as e:
                print(f"[SyncWorker] API request failed at offset {start_index}: {e}")
                break
            except Exception as e:
                print(f"[SyncWorker] Unexpected network error at offset {start_index}: {e}")
                break

            # If empty, we reached the beginning of account history
            if not match_ids:
                print(f"[SyncWorker] Historical backfill complete for PUUID: {self.puuid}")
                if self.on_sync_finished:
                    self.on_sync_finished()
                break

            new_matches_in_batch = 0

            for match_id in match_ids:
                if self._stop_event.is_set():
                    return

                # If already cached, skip instantly
                if self.cache.has_match(match_id):
                    continue

                try:
                    # Fetch match + timeline payloads
                    match_data, timeline_data = self.client.get_match_details(match_id)
                    self.cache.save_match(match_id, match_data, timeline_data)
                    new_matches_in_batch += 1

                    # Polite sleep to respect Riot rate limits and leave bandwidth for UI
                    time.sleep(self.request_delay)
                except Exception as e:
                    print(f"[SyncWorker] Failed to fetch match {match_id}: {e}")

            # Notify UI only once per batch, and only if new matches were actually saved
            if new_matches_in_batch > 0 and self.on_batch_complete:
                self.on_batch_complete(new_matches_in_batch)

            start_index += len(match_ids)


def start_sync_worker(
    puuid: str,
    client: RiotAPIClient,
    cache: MatchCache,
    on_batch_complete: Callable[[int], None] | None = None,
    on_sync_finished: Callable[[], None] | None = None,
) -> MatchSyncWorker:
    """Instantiate and start a background sync worker thread."""
    worker = MatchSyncWorker(puuid, client, cache, on_batch_complete, on_sync_finished)
    worker.start()
    return worker
