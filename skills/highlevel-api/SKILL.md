---
name: highlevel-api
description: Use the universal HighLevel Python handler to read, create, update, delete, and automate any HighLevel workflow. Handles PIT/OAuth auth, retries, pagination, and chained lookups like accountIds.
argument-hint: "list contacts" or "create a draft social post" or "create opportunity in pipeline" or "refresh the registry"
context: conversation
---

# HighLevel Universal API Handler

Use the shared HighLevel helper instead of hand-writing curl calls or raw `requests` code.

This skill is for any task that needs HighLevel in any way:
- Reading records
- Creating, updating, or deleting records
- Debugging HighLevel integrations
- Generating Python code against HighLevel
- Running chained workflows where one call depends on another
- Refreshing coverage when the public docs change

---

## Files This Skill Uses

Prefer these files, in this order:

1. `./highlevel_universal_handler/` package
2. `./highlevel_universal_handler.py` standalone script

If both exist, use the package.

Key entry points:
- `from highlevel_universal_handler import HighLevelHandler`
- `handler = HighLevelHandler.from_env()`
- `handler.invoke(root, child, action, ...)`
- `handler.<root>.<child>.<action>(...)`
- `handler.request_path(method, path, ...)`
- `handler.registry.list_roots()`
- `handler.registry.list_children(root)`
- `handler.registry.list_actions(root, child)`
- `handler.refresh_registry_from_docs(save_to=...)`

If the import fails because the repo root is not on `PYTHONPATH`, add the project root to `sys.path` before importing.

---

## Source of Truth

Use the helper as the default interface for HighLevel work.

Use the public HighLevel docs only to:
- Verify auth behavior
- Confirm a newly added route
- Refresh the registry when docs drift

Target the current V2 API surface. Do not generate new V1 API key flows.

---

## Environment and Auth

The helper supports both auth modes:
- Private Integration Token
- OAuth 2.0

Prefer environment variables. Never hardcode tokens into source files.

```bash
export HIGHLEVEL_BEARER_TOKEN="..."
export HIGHLEVEL_LOCATION_ID="..."
export GHL_COMPANY_ID="..."
export GHL_USER_ID="..."
```

OAuth environment variables when needed:

```bash
export HIGHLEVEL_CLIENT_ID="..."
export HIGHLEVEL_CLIENT_SECRET="..."
export HIGHLEVEL_REDIRECT_URI="https://yourapp.example.com/oauth/callback"
```

Rules:
- If the user gives a `locationId`, use it.
- If both explicit arguments and env vars exist, explicit arguments win.
- For write actions, keep tokens out of printed output and logs.

---

## Opening Behavior

When the user asks for a HighLevel task, determine these five things first:

1. **Mode**
   - `execute` — perform a live API call with the helper
   - `code` — generate Python that uses the helper
   - `debug` — diagnose a failing call or auth issue
   - `coverage` — inspect implemented roots, children, and actions
   - `refresh` — refresh the registry from the docs

2. **Target**
   - root family
   - child group
   - action

3. **Context**
   - `locationId`
   - `companyId`
   - `userId`
   - parent IDs such as `productId`, `pipelineId`, `conversationId`, `accountIds`

4. **Auth**
   - PIT for internal or single-account use
   - OAuth for public app or rotating tokens

5. **Write Risk**
   - If the action changes data, confirm the requested intent from the user’s message
   - Do not silently turn a draft workflow into a publish workflow

Do not ask for IDs that the helper can resolve on its own. Resolve them.

---

## Execution Rules

### Rule 1 — Prefer the helper over raw HTTP

Default to:

```python
handler.<root>.<child>.<action>(...)
```

Use:

```python
handler.invoke(root, child, action, ...)
```

when writing generic tooling, shared agent utilities, or dynamic wrappers.

Use:

```python
handler.request_path(method, path, ...)
```

only when:
- The user explicitly asks for a raw route
- A new route is not yet in the seed registry
- You already know the exact route and only need auth, retry, and transport handling

### Rule 2 — Prefer dynamic wrappers when the route is known

Good:

```python
handler.contacts.contacts.list_contacts(...)
handler.social_planner.post.create_post(...)
```

### Rule 3 — Prefer `invoke()` for skills that need one universal entry point

Good:

```python
handler.invoke("contacts", "contacts", "list_contacts", query={...})
```

### Rule 4 — Use registry inspection before guessing names

Before inventing a method name, inspect:

```python
handler.registry.list_roots()
handler.registry.list_children("contacts")
handler.registry.list_actions("contacts", "contacts")
```

### Rule 5 — Refresh the registry when docs drift

If a route appears to be missing or renamed:

```python
handler.refresh_registry_from_docs(save_to="highlevel_registry.generated.json")
```

---

## Dependency Resolution — REQUIRED

Many HighLevel calls depend on IDs from earlier calls. Use the helper’s resolver system before falling back to manual lookup.

### Social Planner account IDs

For social planner posts, `accountIds` come from Get Accounts.

Use:

```python
result = handler.social_planner.post.create_post(
    payload={
        "summary": "Draft post",
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

The helper should perform:
1. `GET /social-media-posting/:locationId/accounts`
2. `POST /social-media-posting/:locationId/posts`

For non-draft posts:
- Do not post to all accounts by accident
- Require either explicit `payload["accountIds"]`
- Or a specific resolver instruction

### Product price routes

If `productId` is missing but the user knows the product name:

```python
handler.products.prices.list_prices(
    resolve={"product": {"name": "Starter Plan"}}
)
```

### Opportunity creation

If `pipelineId` or `stageId` is missing:

```python
handler.opportunities.opportunities.create_opportunity(
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

### General resolver policy

Attempt resolver-based lookup for:
- `locationId`
- `companyId`
- `userId`
- `productId`
- `priceId`
- `pipelineId`
- `stageId`
- `accountIds`
- `conversationId`
- `calendarId`
- `recordId`
- Any other parent ID required by the selected action

Only ask the user for an ID when:
- The helper cannot resolve it
- There is real ambiguity
- Or the action is destructive and multiple matches exist

---

## Standard Workflows

### 1. Read data

Use the narrowest action that solves the request.
Prefer list or search first, then get-by-id if needed.

Example:

```python
from highlevel_universal_handler import HighLevelHandler

handler = HighLevelHandler.from_env()

contacts = handler.contacts.contacts.list_contacts(
    query={
        "locationId": "R3T13C7SpeS7cOozpIiw",
        "limit": 20,
    }
)
```

### 2. Create data

Pass write payloads under `payload=...`.

Example:

```python
contact = handler.contacts.contacts.create_contact(
    payload={
        "locationId": "R3T13C7SpeS7cOozpIiw",
        "firstName": "Ada",
        "lastName": "Lovelace",
        "email": "ada@example.com",
    }
)
```

### 3. Update data

Pass the identifying ID plus `payload=...`.

Example pattern:

```python
updated = handler.contacts.contacts.update_contact(
    contactId="CONTACT_ID",
    payload={
        "tags": ["VIP"],
    }
)
```

### 4. Delete data

Only run deletes when the user clearly asked for deletion.
Surface the exact target before deleting if there is any ambiguity.

### 5. Paginated reads

Use the helper’s pagination support instead of writing manual next-page code whenever possible.

### 6. OAuth setup

Use the helper’s OAuth classes when the user needs a public app flow.

Example:

```python
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
```

---

## Universal Adapter Pattern For Other Skills

When another skill just needs one reusable entry point, use this wrapper:

```python
from highlevel_universal_handler import HighLevelHandler

_handler = None

def get_handler():
    global _handler
    if _handler is None:
        _handler = HighLevelHandler.from_env()
    return _handler

def highlevel_call(root, child, action, **kwargs):
    return get_handler().invoke(root, child, action, **kwargs)
```

This is the preferred pattern for AI-agent skills that call many HighLevel endpoints through one shared interface.

---

## Live Execution Checklist

Before running a live mutation:
- Confirm auth exists in env or explicit config
- Confirm `locationId` or required parent context
- Confirm the requested action is the correct one
- Resolve missing parent IDs automatically where possible
- Use the helper, not handwritten requests
- Log or print the final result in structured JSON
- Redact tokens from any output

For read-only requests, run directly.
For write requests, run directly when the user clearly asked for the change.

---

## Debugging Checklist

When a HighLevel call fails:

1. Check auth mode
   - PIT present
   - OAuth token expired
   - Missing scopes

2. Check required context
   - Missing `locationId`
   - Missing `companyId`
   - Missing parent ID

3. Check action naming
   - Inspect the registry instead of guessing

4. Check docs drift
   - Refresh the registry if needed

5. Check route fallback
   - If the seed registry is stale, use `request_path()` temporarily

6. Check chained dependencies
   - Especially Social Planner accounts
   - Product parents
   - Pipelines and stages

---

## CLI Shortcuts

Use these when useful:

```bash
python highlevel_universal_handler.py --list-roots
python highlevel_universal_handler.py --coverage
python highlevel_universal_handler.py --refresh-registry highlevel_registry.generated.json
python highlevel_universal_handler.py --smoke-location
```

---

## Output Style

When the user asks for code:
- Return production-ready Python that imports the helper
- Do not use raw `requests` unless the user explicitly asks for it
- Keep the code focused on the requested workflow

When the user asks to perform the action:
- Use the helper live
- Show the result
- Call out any resolver step that was applied

When the user asks what is available:
- Inspect the registry and report roots, children, and actions

---

## What Not To Do

- Do not hardcode tokens into source files
- Do not bypass the helper for normal HighLevel tasks
- Do not guess endpoint names when the registry can tell you
- Do not ask the user for IDs the resolver can find
- Do not publish social posts to every connected account by accident
- Do not write new one-off HighLevel clients when this helper already covers the task

---

## Quick Recipes

### List contacts

```python
from highlevel_universal_handler import HighLevelHandler

handler = HighLevelHandler.from_env()
result = handler.contacts.contacts.list_contacts(
    query={"locationId": "R3T13C7SpeS7cOozpIiw", "limit": 20}
)
```

### Create a contact

```python
from highlevel_universal_handler import HighLevelHandler

handler = HighLevelHandler.from_env()
result = handler.contacts.contacts.create_contact(
    payload={
        "locationId": "R3T13C7SpeS7cOozpIiw",
        "firstName": "John",
        "lastName": "Doe",
        "email": "john@example.com",
    }
)
```

### Create a draft social post with resolved account IDs

```python
from highlevel_universal_handler import HighLevelHandler

handler = HighLevelHandler.from_env()
result = handler.social_planner.post.create_post(
    payload={
        "summary": "Draft post from the skill",
        "status": "draft",
    },
    resolve={"accountIds": {"platforms": ["facebook"], "first": True}},
)
```

### Create an opportunity with resolved pipeline and stage

```python
from highlevel_universal_handler import HighLevelHandler

handler = HighLevelHandler.from_env()
result = handler.opportunities.opportunities.create_opportunity(
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

### Raw route fallback with handler transport

```python
from highlevel_universal_handler import HighLevelHandler

handler = HighLevelHandler.from_env()
result = handler.request_path(
    "GET",
    "/locations/:locationId",
    locationId="R3T13C7SpeS7cOozpIiw",
)
```

---

## Definition of Done

A HighLevel task is only done when one of these is true:

1. The live call succeeded through the helper
2. The user has a working Python snippet that imports the helper correctly
3. The missing route was found via registry refresh or direct path fallback
4. The dependency chain was fully resolved, not left half-finished
