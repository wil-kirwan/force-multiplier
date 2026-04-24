# HighLevel Universal Python Handler

This package gives your AI-agent skills one shared HighLevel API handler.

It supports:

- Private Integration Tokens and OAuth 2.0
- All 40 documented HighLevel root families
- 386 static seed actions across documented child groups
- Dynamic `handler.root.child.action()` wrappers
- Generic `handler.invoke(root, child, action, ...)`
- Direct `handler.request_path(method, path, ...)` for emergency passthrough calls
- Automatic `Version: 2021-07-28` header
- Rate-limit aware transport
- Retries for 429 and transient 5xx errors
- OAuth token refresh
- Pagination helper
- Registry refresh from HighLevel public docs
- Resolver hooks for chained calls, including Social Planner `accountIds`
- Unit tests with mocked transport

## Install

```bash
cd highlevel_universal_handler
python -m pip install -r requirements.txt
```

## Configure

Do not hardcode a PIT into your agent code. Use environment variables.

```bash
export HIGHLEVEL_BEARER_TOKEN="<your-private-integration-token-or-oauth-access-token>"
export HIGHLEVEL_LOCATION_ID="R3T13C7SpeS7cOozpIiw"
```

The handler also reads these aliases:

```bash
GHL_BEARER_TOKEN
GHL_LOCATION_ID
GHL_COMPANY_ID
GHL_USER_ID
GHL_APP_ID
```

## First smoke test

```bash
python examples/smoke_test_location.py
```

This performs a live authenticated call. Run it from your machine or server after setting `HIGHLEVEL_BEARER_TOKEN`.

That calls:

```http
GET https://services.leadconnectorhq.com/locations/R3T13C7SpeS7cOozpIiw
```

with:

```http
Authorization: Bearer $HIGHLEVEL_BEARER_TOKEN
Version: 2021-07-28
Accept: application/json
```

## Basic usage

```python
from highlevel_universal_handler import HighLevelHandler

handler = HighLevelHandler.from_env()

contacts = handler.contacts.contacts.list_contacts(
    query={"locationId": "R3T13C7SpeS7cOozpIiw", "limit": 20}
)

contact = handler.contacts.contacts.create_contact(
    payload={
        "locationId": "R3T13C7SpeS7cOozpIiw",
        "firstName": "Ada",
        "lastName": "Lovelace",
        "email": "ada@example.com",
    }
)
```

The same call through the generic dispatcher:

```python
contact = handler.invoke(
    "contacts",
    "contacts",
    "create_contact",
    payload={
        "locationId": "R3T13C7SpeS7cOozpIiw",
        "firstName": "Ada",
        "email": "ada@example.com",
    },
)
```

## Social Planner chained dependency resolver

HighLevel Social Planner post calls require `accountIds`. The handler can resolve those IDs by calling Get Accounts first.

```python
result = handler.social_planner.post.create_post(
    payload={
        "summary": "Post from my AI workflow",
        "status": "draft",
    },
    resolve={
        "accountIds": {
            "platforms": ["facebook"],
            "first": True,
        }
    },
)
```

What happens internally:

```http
GET /social-media-posting/:locationId/accounts
POST /social-media-posting/:locationId/posts
```

The second request receives `payload["accountIds"]` from the first response.

For safety, the handler will not silently publish to every account. For non-draft posts, pass one of these:

```python
payload={"accountIds": ["account-id-here"], ...}
```

or:

```python
resolve={"accountIds": {"platforms": ["instagram"], "first": True}}
```

## Product price parent resolver

Product price routes require `productId`.

```python
prices = handler.products.prices.list_prices(
    resolve={"product": {"name": "Starter Plan"}}
)
```

The handler lists products, finds the product by name, then calls:

```http
GET /products/:productId/price/
```

## Opportunity pipeline resolver

```python
opportunity = handler.opportunities.opportunities.create_opportunity(
    payload={
        "locationId": "R3T13C7SpeS7cOozpIiw",
        "name": "New deal",
        "monetaryValue": 2500,
    },
    resolve={
        "pipeline": {"name": "Sales Pipeline"},
        "stage": {"name": "Qualified"},
    },
)
```

The handler calls `GET /opportunities/pipelines`, resolves `pipelineId` and `stageId`, then creates the opportunity.

## Registry inspection

```python
handler = HighLevelHandler.from_env()

print(handler.registry.list_roots())
print(handler.registry.list_children("social_planner"))
print(handler.registry.list_actions("social_planner", "post"))
print(handler.registry.coverage_report())
```

CLI version:

```bash
python highlevel_universal_handler.py --coverage
python highlevel_universal_handler.py --list-roots
```

## Registry refresh from docs

The static registry ships with 386 actions. HighLevel changes docs over time, so the package includes a crawler.

```bash
python examples/refresh_registry_from_docs.py
```

or:

```python
handler.refresh_registry_from_docs(save_to="highlevel_registry.generated.json")
```

Use this in CI. If HighLevel adds an action, your build can detect it before an agent fails in production.

## Direct path fallback

When you know the route and want to bypass root-child-action lookup:

```python
result = handler.request_path(
    "GET",
    "/locations/:locationId",
    locationId="R3T13C7SpeS7cOozpIiw",
)
```

This still uses auth, version headers, retry, rate limiting, and response parsing.

## OAuth 2.0

```python
from highlevel_universal_handler import HighLevelHandler, OAuthConfig, JsonTokenStore

config = OAuthConfig(
    client_id="...",
    client_secret="...",
    redirect_uri="https://yourapp.example.com/oauth/callback",
    scopes=("contacts.readonly", "contacts.write", "locations.readonly"),
)

handler = HighLevelHandler(
    oauth_config=config,
    token_store=JsonTokenStore(".highlevel_tokens.json"),
)

url = handler.transport.authorization_url(state="csrf-state")

# After callback:
# token_set = handler.transport.exchange_code(code)
```

Refresh tokens rotate automatically when the access token expires, as long as `oauth_config` and `token_store` are set.

## File uploads

Use `files=` and `data=`.

```python
with open("image.png", "rb") as f:
    result = handler.media_storage.medias.upload_file(
        data={"locationId": "R3T13C7SpeS7cOozpIiw"},
        files={"file": f},
    )
```

## Tests

```bash
PYTHONPATH=. python -m unittest -v tests/test_highlevel_handler.py
```

Tested locally in this artifact with mocked transport:

- Registry includes every required root family
- Dynamic wrapper path rendering
- Header injection
- Missing parameter errors
- Contact creation payload forwarding
- Social Planner account ID resolver
- Social Planner non-draft safety guard
- Environment override handling
- Recent endpoint route validation for Knowledge Base, Conversation AI, Store, and AI Agent Studio

## Definition of done used here

The delivered package contains:

```text
highlevel_universal_handler.py       Main self-contained handler
__init__.py                          Package exports
highlevel_registry.seed.json         Static registry JSON, 386 actions
coverage_report.json                 Coverage by root and child
examples/                            Smoke, OAuth, Social Planner, registry refresh examples
tests/                               Unit tests with mocked transport
requirements.txt                     Runtime dependency
pyproject.toml                       Package metadata
```

## Notes for AI-agent integration

Use one handler instance per HighLevel account context.

Recommended pattern:

```python
class MyAgentSkill:
    def __init__(self):
        self.ghl = HighLevelHandler.from_env()

    def run(self, input):
        return self.ghl.contacts.contacts.create_contact(payload=input)
```

For multi-location agents, pass `location_id` per call:

```python
handler.contacts.contacts.list_contacts(query={"locationId": location_id})
```

For routes with `:locationId` in the path, the handler uses the context value by default:

```python
handler = HighLevelHandler.from_env(location_id="R3T13C7SpeS7cOozpIiw")
handler.brand_boards.brand_boards.get_brand_boards()
```

## Security

- Do not commit PITs or OAuth refresh tokens.
- Use environment variables or a secrets manager.
- `JsonTokenStore` is a local example, replace it with your database token store in production.
- Request logs redact bearer tokens, OAuth tokens, and client secrets.
