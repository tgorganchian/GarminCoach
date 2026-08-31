import unittest
from unittest.mock import patch

from garminconnect import GarminConnectTooManyRequestsError

from sync import GARMIN_RATE_LIMIT_RETRY_WAIT_SECONDS, fetch_activity_laps


class _RateLimitedLapClient:
    def __init__(self):
        self.calls = 0

    def get_activity_splits(self, activity_id):
        self.calls += 1
        if self.calls == 1:
            raise GarminConnectTooManyRequestsError()
        return {"lapDTOs": [{"distance": 1000, "duration": 300}]}


class SyncRateLimitTests(unittest.TestCase):
    def test_retries_lap_request_after_a_rate_limit(self):
        client = _RateLimitedLapClient()

        with patch("sync.time.sleep") as sleep:
            laps = fetch_activity_laps(client, "123")

        self.assertEqual(2, client.calls)
        self.assertEqual(1, len(laps))
        sleep.assert_called_once_with(GARMIN_RATE_LIMIT_RETRY_WAIT_SECONDS)
