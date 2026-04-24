"""Smoke test a HighLevel Private Integration Token.

Environment variables:
  HIGHLEVEL_BEARER_TOKEN=<your PIT or OAuth access token>
  HIGHLEVEL_LOCATION_ID=R3T13C7SpeS7cOozpIiw

Run:
  python examples/smoke_test_location.py
"""

import json
import os
from highlevel_universal_handler import HighLevelHandler

handler = HighLevelHandler.from_env()
location_id = os.getenv("HIGHLEVEL_LOCATION_ID") or "R3T13C7SpeS7cOozpIiw"

result = handler.sub_account.sub_account.get_location(location_id=location_id)
print(json.dumps(result, indent=2))
