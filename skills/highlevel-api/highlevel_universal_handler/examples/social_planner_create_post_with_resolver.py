"""Create a Social Planner post while resolving accountIds from Get Accounts.

This example performs the chained call the docs require:
1. GET /social-media-posting/:locationId/accounts
2. POST /social-media-posting/:locationId/posts with payload.accountIds filled in

It will not silently post to every connected account. Pick the platform/channel.
"""

import json
from highlevel_universal_handler import HighLevelHandler

handler = HighLevelHandler.from_env()

payload = {
    "summary": "Scheduled from the HighLevel universal Python handler.",
    "status": "draft",
}

result = handler.social_planner.post.create_post(
    payload=payload,
    resolve={"accountIds": {"platforms": ["facebook"], "first": True}},
)

print(json.dumps(result, indent=2))
