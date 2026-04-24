"""Minimal OAuth 2.0 setup.

Set:
  HIGHLEVEL_CLIENT_ID=...
  HIGHLEVEL_CLIENT_SECRET=...
  HIGHLEVEL_REDIRECT_URI=https://yourapp.example.com/oauth/callback

Then use authorization_url() to send the installer to HighLevel.
After callback, call exchange_code(code).
"""

import os
from highlevel_universal_handler import HighLevelHandler, OAuthConfig, JsonTokenStore

config = OAuthConfig(
    client_id=os.environ["HIGHLEVEL_CLIENT_ID"],
    client_secret=os.environ["HIGHLEVEL_CLIENT_SECRET"],
    redirect_uri=os.environ["HIGHLEVEL_REDIRECT_URI"],
    scopes=("contacts.readonly", "contacts.write", "locations.readonly"),
)

handler = HighLevelHandler(
    oauth_config=config,
    token_store=JsonTokenStore(".highlevel_tokens.json"),
)

print(handler.transport.authorization_url(state="replace-with-csrf-state"))
# token_set = handler.transport.exchange_code(code_from_callback)
