"""Universal Python handler for the HighLevel / LeadConnector API V2.

This file is intentionally self-contained. You can drop it into any AI-agent
project, set HIGHLEVEL_BEARER_TOKEN and HIGHLEVEL_LOCATION_ID, then call either:

    handler.invoke("contacts", "contacts", "create_contact", payload={...})

or the generated dynamic wrapper:

    handler.contacts.contacts.create_contact(payload={...})

Design goals:
- Registry-driven endpoint coverage.
- Static seed registry from the official HighLevel public docs and Scopes page.
- Optional docs crawler to refresh the registry from action pages.
- Private Integration Token and OAuth 2.0 support.
- Automatic retries, rate-limit awareness, pagination, and OAuth refresh.
- Resolver hooks for chained calls, such as Social Planner accountIds.

Generated: 2026-04-23
"""

from __future__ import annotations

import dataclasses
import json
import logging
import os
import re
import threading
import time
import typing as t
import urllib.parse
from html.parser import HTMLParser

try:  # pragma: no cover, import availability depends on runtime image.
    import requests  # type: ignore
except Exception:  # pragma: no cover
    requests = None  # type: ignore

HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}
DEFAULT_BASE_URL = "https://services.leadconnectorhq.com"
DEFAULT_DOCS_URL = "https://marketplace.gohighlevel.com/docs"
DEFAULT_VERSION = "2021-07-28"

LOGGER = logging.getLogger("highlevel_universal_handler")


# ---------------------------------------------------------------------------
# Naming helpers
# ---------------------------------------------------------------------------


def slugify(value: str) -> str:
    value = str(value or "").strip()
    value = re.sub(r"&", " and ", value)
    value = re.sub(r"[^A-Za-z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_").lower()
    return value or "unnamed"


def camel_to_snake(value: str) -> str:
    value = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", value)
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value)
    return slugify(value)


def normalize_param_name(name: str) -> str:
    """Normalize user input names while preserving HighLevel path param case."""
    return slugify(name).replace("_id", "id")


def redact(value: t.Any) -> t.Any:
    if isinstance(value, str):
        if value.startswith("pit-") or value.count(".") >= 2 or len(value) > 32:
            return value[:6] + "..." + value[-4:]
        return value
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if slugify(key) in {"authorization", "access_token", "refresh_token", "token", "bearer_token", "client_secret"}:
                out[key] = "<redacted>"
            else:
                out[key] = redact(item)
        return out
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


PARAM_ALIASES: dict[str, tuple[str, ...]] = {
    "locationId": ("location_id", "locationId", "sub_account_id", "subAccountId"),
    "companyId": ("company_id", "companyId", "agency_id", "agencyId"),
    "userId": ("user_id", "userId"),
    "appId": ("app_id", "appId"),
    "businessId": ("business_id", "businessId"),
    "calendarId": ("calendar_id", "calendarId"),
    "groupId": ("group_id", "groupId"),
    "eventId": ("event_id", "eventId"),
    "contactId": ("contact_id", "contactId"),
    "conversationId": ("conversation_id", "conversationId", "conversations_id", "conversationsId"),
    "conversationsId": ("conversation_id", "conversationId", "conversations_id", "conversationsId"),
    "messageId": ("message_id", "messageId"),
    "emailMessageId": ("email_message_id", "emailMessageId"),
    "invoiceId": ("invoice_id", "invoiceId"),
    "scheduleId": ("schedule_id", "scheduleId"),
    "templateId": ("template_id", "templateId"),
    "estimateId": ("estimate_id", "estimateId"),
    "linkId": ("link_id", "linkId"),
    "tagId": ("tag_id", "tagId"),
    "fileId": ("file_id", "fileId"),
    "pipelineId": ("pipeline_id", "pipelineId"),
    "stageId": ("stage_id", "stageId"),
    "opportunityId": ("opportunity_id", "opportunityId", "id"),
    "orderId": ("order_id", "orderId"),
    "transactionId": ("transaction_id", "transactionId"),
    "subscriptionId": ("subscription_id", "subscriptionId"),
    "productId": ("product_id", "productId"),
    "priceId": ("price_id", "priceId"),
    "collectionId": ("collection_id", "collectionId"),
    "reviewId": ("review_id", "reviewId"),
    "snapshotId": ("snapshot_id", "snapshotId"),
    "accountId": ("account_id", "accountId"),
    "csvId": ("csv_id", "csvId"),
    "postId": ("post_id", "postId", "id"),
    "associationId": ("association_id", "associationId"),
    "recordId": ("record_id", "recordId"),
    "schemaKey": ("schema_key", "schemaKey"),
    "objectKey": ("object_key", "objectKey"),
    "resourceType": ("resource_type", "resourceType"),
    "brandVoiceId": ("brand_voice_id", "brandVoiceId"),
    "customMenuId": ("custom_menu_id", "customMenuId"),
    "chargeId": ("charge_id", "chargeId"),
    "callId": ("call_id", "callId"),
    "agentId": ("agent_id", "agentId"),
    "actionId": ("action_id", "actionId"),
    "knowledgeBaseId": ("knowledge_base_id", "knowledgeBaseId"),
    "faqId": ("faq_id", "faqId"),
    "shippingZoneId": ("shipping_zone_id", "shippingZoneId", "zone_id", "zoneId"),
    "shippingRateId": ("shipping_rate_id", "shippingRateId", "rate_id", "rateId"),
    "shippingCarrierId": ("shipping_carrier_id", "shippingCarrierId", "carrier_id", "carrierId"),
    "versionId": ("version_id", "versionId"),
    "id": ("id",),
}

ROOT_ALIASES: dict[str, str] = {
    "oauth": "oauth_2_0",
    "oauth_2": "oauth_2_0",
    "oauth_2_0": "oauth_2_0",
    "brand_board": "brand_boards",
    "brand_boards": "brand_boards",
    "business": "business",
    "businesses": "business",
    "calendar": "calendars",
    "calendars": "calendars",
    "campaign": "campaigns",
    "campaigns": "campaigns",
    "companies": "companies",
    "company": "companies",
    "contacts": "contacts",
    "contact": "contacts",
    "objects": "objects",
    "custom_objects": "objects",
    "associations": "associations",
    "custom_fields": "custom_fields_v2",
    "custom_fields_v2": "custom_fields_v2",
    "conversations": "conversations",
    "conversation": "conversations",
    "courses": "courses",
    "memberships": "courses",
    "email": "email",
    "emails": "email",
    "forms": "forms",
    "invoice": "invoice",
    "invoices": "invoice",
    "trigger_links": "trigger_links",
    "links": "trigger_links",
    "location": "sub_account",
    "locations": "sub_account",
    "sub_account": "sub_account",
    "sub_account_formerly_location": "sub_account",
    "media": "media_storage",
    "medias": "media_storage",
    "media_storage": "media_storage",
    "developer_marketplace": "developer_marketplace",
    "marketplace": "developer_marketplace",
    "blogs": "blogs",
    "funnels": "funnels",
    "opportunities": "opportunities",
    "payments": "payments",
    "products": "products",
    "saas": "saas",
    "snapshots": "snapshots",
    "social_planner": "social_planner",
    "socialplanner": "social_planner",
    "surveys": "surveys",
    "users": "users",
    "workflows": "workflows",
    "lc_email": "lc_email",
    "email_isv": "lc_email",
    "custom_menus": "custom_menus",
    "custom_menu": "custom_menus",
    "voice_ai": "voice_ai",
    "proposals": "proposals",
    "documents_contracts": "proposals",
    "knowledge_base": "knowledge_base",
    "conversation_ai": "conversation_ai",
    "phone_system": "phone_system",
    "phone_numbers": "phone_system",
    "store": "store",
    "ai_agent_studio": "ai_agent_studio",
    "agent_studio": "ai_agent_studio",
    "affiliate_manager": "affiliate_manager",
}

URL_ROOT_ALIASES: dict[str, str] = {
    "oauth": "oauth_2_0",
    "brand-boards": "brand_boards",
    "businesses": "business",
    "calendars": "calendars",
    "campaigns": "campaigns",
    "companies": "companies",
    "contacts": "contacts",
    "objects": "objects",
    "associations": "associations",
    "custom-fields": "custom_fields_v2",
    "conversations": "conversations",
    "courses": "courses",
    "emails": "email",
    "forms": "forms",
    "invoices": "invoice",
    "links": "trigger_links",
    "locations": "sub_account",
    "medias": "media_storage",
    "marketplace": "developer_marketplace",
    "blogs": "blogs",
    "funnels": "funnels",
    "opportunities": "opportunities",
    "payments": "payments",
    "products": "products",
    "saas": "saas",
    "snapshots": "snapshots",
    "social-planner": "social_planner",
    "surveys": "surveys",
    "users": "users",
    "workflows": "workflows",
    "email-isv": "lc_email",
    "custom-menus": "custom_menus",
    "voice-ai": "voice_ai",
    "proposals": "proposals",
    "knowledge-base": "knowledge_base",
    "conversation-ai": "conversation_ai",
    "phone-system": "phone_system",
    "store": "store",
    "agent-studio": "ai_agent_studio",
    "affiliate-manager": "affiliate_manager",
}

DEFAULT_ROOTS: tuple[str, ...] = (
    "oauth_2_0", "brand_boards", "business", "calendars", "campaigns", "companies",
    "contacts", "objects", "associations", "custom_fields_v2", "conversations", "courses",
    "email", "forms", "invoice", "trigger_links", "sub_account", "media_storage",
    "developer_marketplace", "blogs", "funnels", "opportunities", "payments", "products",
    "saas", "snapshots", "social_planner", "surveys", "users", "workflows", "lc_email",
    "custom_menus", "voice_ai", "proposals", "knowledge_base", "conversation_ai", "phone_system",
    "store", "ai_agent_studio", "affiliate_manager",
)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class ActionSpec:
    root: str
    child: str
    action: str
    method: str
    path: str
    scope: str = ""
    access: str = ""
    description: str = ""
    doc_url: str = ""
    aliases: tuple[str, ...] = dataclasses.field(default_factory=tuple)
    resolver_hints: tuple[str, ...] = dataclasses.field(default_factory=tuple)
    paginated: bool = False
    multipart: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "root", canonical_root(self.root))
        object.__setattr__(self, "child", slugify(self.child))
        object.__setattr__(self, "action", slugify(self.action))
        method = str(self.method).upper().strip()
        if method not in HTTP_METHODS:
            raise ValueError(f"Invalid HTTP method {method!r} for {self.root}.{self.child}.{self.action}")
        object.__setattr__(self, "method", method)
        path = self.path.strip()
        if not path.startswith("/"):
            path = "/" + path
        path = re.sub(r"\s+", "", path)
        object.__setattr__(self, "path", path)

    @property
    def key(self) -> tuple[str, str, str]:
        return self.root, self.child, self.action

    @property
    def path_params(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(re.findall(r":([A-Za-z_][A-Za-z0-9_]*)", self.path)))

    @property
    def canonical_name(self) -> str:
        return ".".join(self.key)

    def to_dict(self) -> dict[str, t.Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, t.Any]) -> "ActionSpec":
        copied = dict(data)
        for tuple_key in ("aliases", "resolver_hints"):
            if isinstance(copied.get(tuple_key), list):
                copied[tuple_key] = tuple(copied[tuple_key])
        return cls(**copied)


@dataclasses.dataclass
class SessionContext:
    location_id: str | None = None
    company_id: str | None = None
    user_id: str | None = None
    app_id: str | None = None
    extra: dict[str, t.Any] = dataclasses.field(default_factory=dict)

    def get_for_param(self, param: str) -> str | None:
        mapping = {
            "locationId": self.location_id,
            "companyId": self.company_id,
            "userId": self.user_id,
            "appId": self.app_id,
        }
        if param in mapping and mapping[param]:
            return mapping[param]
        snake = camel_to_snake(param)
        return self.extra.get(param) or self.extra.get(snake)


@dataclasses.dataclass
class TokenSet:
    access_token: str
    refresh_token: str | None = None
    token_type: str = "Bearer"
    expires_at: float | None = None
    scope: str | None = None
    location_id: str | None = None
    company_id: str | None = None
    user_type: str | None = None

    @classmethod
    def from_oauth_response(cls, data: dict[str, t.Any], now: float | None = None) -> "TokenSet":
        now = time.time() if now is None else now
        expires_in = data.get("expires_in") or data.get("expiresIn")
        expires_at = None
        if expires_in is not None:
            try:
                expires_at = now + float(expires_in) - 60.0
            except Exception:
                expires_at = None
        return cls(
            access_token=data.get("access_token") or data.get("accessToken") or "",
            refresh_token=data.get("refresh_token") or data.get("refreshToken"),
            token_type=data.get("token_type") or data.get("tokenType") or "Bearer",
            expires_at=expires_at,
            scope=data.get("scope"),
            location_id=data.get("locationId") or data.get("location_id"),
            company_id=data.get("companyId") or data.get("company_id"),
            user_type=data.get("userType") or data.get("user_type"),
        )

    def is_expiring(self, skew_seconds: int = 120) -> bool:
        return bool(self.expires_at and time.time() >= self.expires_at - skew_seconds)

    def to_dict(self) -> dict[str, t.Any]:
        return dataclasses.asdict(self)


@dataclasses.dataclass
class OAuthConfig:
    client_id: str
    client_secret: str
    redirect_uri: str | None = None
    token_url: str = DEFAULT_BASE_URL + "/oauth/token"
    scopes: tuple[str, ...] = dataclasses.field(default_factory=tuple)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class HighLevelError(Exception):
    pass


class ActionNotFoundError(HighLevelError):
    pass


class MissingParameterError(HighLevelError):
    pass


class ResolverError(HighLevelError):
    pass


class HighLevelAPIError(HighLevelError):
    def __init__(self, message: str, *, status_code: int | None = None, response: t.Any = None, request: dict[str, t.Any] | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response
        self.request = request or {}


class HighLevelAuthError(HighLevelAPIError):
    pass


class HighLevelRateLimitError(HighLevelAPIError):
    pass


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def canonical_root(value: str) -> str:
    key = slugify(value)
    return ROOT_ALIASES.get(key, key)


def infer_root_child_from_scope(scope: str, path: str = "") -> tuple[str, str]:
    base = scope.split(".", 1)[0].strip()
    if "/" in base:
        parts = base.split("/")
        root = canonical_root(parts[0])
        child = slugify(parts[1] if len(parts) > 1 else parts[0])
        return root, child
    root = canonical_root(base)
    child = slugify(base)
    if root == "social_planner" and base.startswith("socialplanner"):
        child = "social_planner"
    if scope.startswith("socialplanner/"):
        child = slugify(scope.split("/", 1)[1].split(".", 1)[0])
    if scope.startswith("locations/"):
        root = "sub_account"
        child = slugify(scope.split("/", 1)[1].split(".", 1)[0])
    if scope.startswith("invoices/"):
        root = "invoice"
        child = slugify(scope.split("/", 1)[1].split(".", 1)[0])
    if scope.startswith("payments/"):
        root = "payments"
        child = slugify(scope.split("/", 1)[1].split(".", 1)[0])
    if scope.startswith("products/"):
        root = "products"
        child = slugify(scope.split("/", 1)[1].split(".", 1)[0])
    if scope.startswith("calendars/"):
        root = "calendars"
        child = slugify(scope.split("/", 1)[1].split(".", 1)[0])
    if scope.startswith("conversations/"):
        root = "conversations"
        child = slugify(scope.split("/", 1)[1].split(".", 1)[0])
    if scope.startswith("blogs/"):
        root = "blogs"
        child = slugify(scope.split("/", 1)[1].split(".", 1)[0])
    if scope.startswith("funnels/"):
        root = "funnels"
        child = slugify(scope.split("/", 1)[1].split(".", 1)[0])
    if scope.startswith("associations/"):
        root = "associations"
        child = slugify(scope.split("/", 1)[1].split(".", 1)[0])
    if scope.startswith("emails/"):
        root = "email"
        child = slugify(scope.split("/", 1)[1].split(".", 1)[0])
    if scope.startswith("documents_contracts_templates"):
        return "proposals", "templates"
    if scope.startswith("documents_contracts"):
        return "proposals", "documents"
    if scope.startswith("custom-menu-link"):
        return "custom_menus", "custom_menu_links"
    if scope.startswith("voice-ai-dashboard"):
        return "voice_ai", "dashboard"
    if scope.startswith("voice-ai-agents"):
        return "voice_ai", "agents"
    if scope.startswith("voice-ai-agent-goals"):
        return "voice_ai", "actions"
    if scope.startswith("phonenumbers"):
        return "phone_system", "phone_numbers"
    if scope.startswith("numberpools"):
        return "phone_system", "number_pools"
    if scope.startswith("marketplace-installer-details"):
        return "developer_marketplace", "app_management"
    if scope.startswith("charges"):
        return "developer_marketplace", "wallet_charges"
    if path.startswith("/brand-boards/public"):
        return "brand_boards", "brand_voices"
    if path.startswith("/brand-boards"):
        return "brand_boards", "brand_boards"
    return root, child


def action_name_from_method_path(method: str, path: str) -> str:
    method = method.lower()
    clean = path.strip("/")
    if not clean:
        return slugify(method)
    parts = [p for p in clean.split("/") if p]
    constants = [p for p in parts if not p.startswith(":")]
    params = [camel_to_snake(p[1:]) for p in parts if p.startswith(":")]
    noun = "_".join(slugify(p) for p in constants[-3:]) or "resource"
    if method == "get":
        if params and parts[-1].startswith(":"):
            return f"get_{noun.rstrip('s')}_by_{params[-1]}"
        return f"list_{noun}"
    if method == "post":
        tail = constants[-1] if constants else "resource"
        verb_map = {
            "search": "search", "send": "send", "void": "void", "record-payment": "record_payment",
            "text2pay": "create_text2pay", "validate-slug": "validate_slug", "bulk-update": "bulk_update",
            "share": "share", "link": "create_link", "import": "import", "upload-file": "upload_file",
            "upload-custom-files": "upload_custom_files", "block-slots": "create_block_slot",
            "appointments": "create_appointment", "fulfillments": "create_fulfillment", "details": "get_details",
            "statistics": "get_statistics", "schedule": "schedule", "auto-payment": "auto_payment", "cancel": "cancel",
        }
        if tail in verb_map:
            return slugify(verb_map[tail] + "_" + noun if verb_map[tail] in {"search", "list"} else verb_map[tail])
        return f"create_{slugify(constants[-1]).rstrip('s') if constants else 'resource'}"
    if method in {"put", "patch"}:
        verb = "patch" if method == "patch" else "update"
        if constants and constants[-1] in {"status", "completed", "capabilities", "default", "stats"}:
            return f"{verb}_{slugify(constants[-1])}"
        return f"{verb}_{slugify(constants[-1]).rstrip('s') if constants else 'resource'}"
    if method == "delete":
        return f"delete_{slugify(constants[-1]).rstrip('s') if constants else 'resource'}"
    return slugify(f"{method}_{noun}")


class ActionRegistry:
    def __init__(self, actions: t.Iterable[ActionSpec] | None = None):
        self._actions: dict[tuple[str, str, str], ActionSpec] = {}
        self._alias_index: dict[tuple[str, str, str], tuple[str, str, str]] = {}
        if actions:
            for action in actions:
                self.add(action)

    def __len__(self) -> int:
        return len(self._actions)

    def __iter__(self) -> t.Iterator[ActionSpec]:
        yield from sorted(self._actions.values(), key=lambda s: s.canonical_name)

    def add(self, spec: ActionSpec, *, replace: bool = True) -> None:
        key = spec.key
        if replace or key not in self._actions:
            self._actions[key] = spec
        for alias in spec.aliases:
            self._alias_index[(spec.root, spec.child, slugify(alias))] = key
        # Common CRUD aliases when unambiguous by method/path shape.
        self._index_crud_aliases(spec)

    def merge(self, other: "ActionRegistry", *, replace: bool = True) -> None:
        for spec in other:
            self.add(spec, replace=replace)

    def _index_crud_aliases(self, spec: ActionSpec) -> None:
        params = spec.path_params
        action = spec.action
        aliases: list[str] = []
        if spec.method == "GET" and not params:
            aliases.extend(["list", "get_all"])
        elif spec.method == "GET" and spec.path.rstrip("/").endswith(tuple(":" + p for p in params)):
            aliases.extend(["get", "retrieve"])
        elif spec.method == "POST":
            aliases.extend(["create"])
        elif spec.method in {"PUT", "PATCH"}:
            aliases.extend(["update"])
        elif spec.method == "DELETE":
            aliases.extend(["delete", "remove"])
        # Also infer direct action names that humans expect.
        if action.startswith("list_"):
            aliases.append("list")
        if action.startswith("get_"):
            aliases.append("get")
        if action.startswith("create_"):
            aliases.append("create")
        if action.startswith("update_") or action.startswith("patch_"):
            aliases.append("update")
        if action.startswith("delete_"):
            aliases.append("delete")
        for alias in aliases:
            alias_key = (spec.root, spec.child, slugify(alias))
            self._alias_index.setdefault(alias_key, spec.key)

    def get(self, root: str, child: str, action: str) -> ActionSpec:
        root_key = canonical_root(root)
        child_key = slugify(child)
        action_key = slugify(action)
        key = (root_key, child_key, action_key)
        if key in self._actions:
            return self._actions[key]
        alias_key = self._alias_index.get(key)
        if alias_key and alias_key in self._actions:
            return self._actions[alias_key]
        # Last attempt: if root has one child matching action name style.
        matches = [s for s in self._actions.values() if s.root == root_key and s.action == action_key]
        if len(matches) == 1:
            return matches[0]
        raise ActionNotFoundError(
            f"Action not found: {root}.{child}.{action}. "
            f"Use handler.registry.list_actions({root_key!r}, {child_key!r}) to inspect valid actions."
        )

    def find_by_path(self, method: str, path: str) -> ActionSpec | None:
        method = method.upper()
        normalized = re.sub(r"/+$", "", path if path.startswith("/") else "/" + path)
        for spec in self._actions.values():
            if spec.method == method and re.sub(r"/+$", "", spec.path) == normalized:
                return spec
        return None

    def list_roots(self) -> list[str]:
        return sorted({spec.root for spec in self._actions.values()})

    def list_children(self, root: str) -> list[str]:
        root_key = canonical_root(root)
        return sorted({spec.child for spec in self._actions.values() if spec.root == root_key})

    def list_actions(self, root: str | None = None, child: str | None = None) -> list[str]:
        root_key = canonical_root(root) if root else None
        child_key = slugify(child) if child else None
        specs = self._actions.values()
        if root_key:
            specs = [s for s in specs if s.root == root_key]
        if child_key:
            specs = [s for s in specs if s.child == child_key]
        return sorted(s.action for s in specs)

    def coverage_report(self, required_roots: t.Iterable[str] = DEFAULT_ROOTS) -> dict[str, t.Any]:
        roots = set(self.list_roots())
        required = {canonical_root(root) for root in required_roots}
        by_root: dict[str, dict[str, t.Any]] = {}
        for root in sorted(roots | required):
            specs = [s for s in self._actions.values() if s.root == root]
            children = sorted({s.child for s in specs})
            by_root[root] = {
                "implemented_actions": len(specs),
                "children": {child: len([s for s in specs if s.child == child]) for child in children},
            }
        return {
            "total_actions": len(self._actions),
            "roots_present": sorted(roots),
            "missing_required_roots": sorted(required - roots),
            "by_root": by_root,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps([spec.to_dict() for spec in self], indent=indent, sort_keys=True)

    @classmethod
    def from_json(cls, value: str | bytes) -> "ActionRegistry":
        data = json.loads(value)
        return cls(ActionSpec.from_dict(item) for item in data)

    @classmethod
    def from_file(cls, path: str) -> "ActionRegistry":
        with open(path, "r", encoding="utf-8") as f:
            return cls.from_json(f.read())

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_json())

    @classmethod
    def seeded(cls) -> "ActionRegistry":
        registry = cls()
        for line in SEED_ENDPOINTS.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 5:
                continue
            root, child, action, method, path = parts[:5]
            scope = parts[5] if len(parts) > 5 else ""
            access = parts[6] if len(parts) > 6 else ""
            description = parts[7] if len(parts) > 7 else ""
            aliases = tuple(slugify(a) for a in parts[8].split(",") if a.strip()) if len(parts) > 8 else ()
            registry.add(ActionSpec(root, child, action, method, path, scope, access, description, aliases=aliases))
        return registry


# ---------------------------------------------------------------------------
# Docs crawler, optional but production-useful for drift and new endpoints.
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class Link:
    href: str
    text: str


class _LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links: list[Link] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a":
            attrs_dict = dict(attrs)
            href = attrs_dict.get("href")
            if href:
                self._href = href
                self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href is not None:
            text = re.sub(r"\s+", " ", "".join(self._text)).strip()
            self.links.append(Link(self._href, text))
            self._href = None
            self._text = []


class DocsCrawler:
    """Crawl HighLevel docs action pages and compile an ActionRegistry.

    This does not execute API calls. It only reads public documentation pages.
    It is safe to run in CI to detect docs drift.
    """

    def __init__(self, docs_url: str = DEFAULT_DOCS_URL, session: t.Any = None, timeout: int = 20):
        if requests is None and session is None:
            raise RuntimeError("requests is required for DocsCrawler unless a compatible session is supplied")
        self.docs_url = docs_url.rstrip("/")
        self.session = session or (requests.Session() if requests is not None else None)
        self.timeout = timeout

    def fetch(self, url: str) -> str:
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response.text

    def crawl(self, max_pages: int = 2000) -> ActionRegistry:
        start = self.docs_url + "/ghl/brand-boards/brand-boards/index.html"
        queue = [start]
        seen: set[str] = set()
        registry = ActionRegistry.seeded()
        while queue and len(seen) < max_pages:
            url = queue.pop(0)
            if url in seen:
                continue
            seen.add(url)
            try:
                html = self.fetch(url)
            except Exception as exc:  # pragma: no cover, network dependent
                LOGGER.debug("Skipping docs URL %s: %s", url, exc)
                continue
            for link in self._extract_doc_links(html, url):
                if link not in seen and link not in queue:
                    queue.append(link)
            spec = self._parse_action_page(html, url)
            if spec:
                registry.add(spec)
        return registry

    def _extract_doc_links(self, html: str, base_url: str) -> list[str]:
        parser = _LinkParser()
        parser.feed(html)
        out: list[str] = []
        for link in parser.links:
            href = urllib.parse.urljoin(base_url, link.href)
            if "/docs/ghl/" not in href:
                continue
            href = href.split("#", 1)[0]
            if not href.endswith("/") and not href.endswith(".html"):
                href = href.rstrip("/") + "/index.html"
            out.append(href)
        return out

    def _parse_action_page(self, html: str, url: str) -> ActionSpec | None:
        text = re.sub(r"<[^>]+>", "\n", html)
        text = re.sub(r"&nbsp;", " ", text)
        text = re.sub(r"\s+", " ", text)
        method_path = re.search(r"\b(GET|POST|PUT|PATCH|DELETE)\b\s*#+\s*([^\s<]+)", text)
        if not method_path:
            # Some rendered pages have method and route separated by whitespace only.
            method_path = re.search(r"\b(GET|POST|PUT|PATCH|DELETE)\b\s+(/[^\s<]+)", text)
        if not method_path:
            return None
        method, path = method_path.group(1), method_path.group(2)
        if not path.startswith("/"):
            path = "/" + path
        title_match = re.search(r"<h1[^>]*>(.*?)</h1>", html, flags=re.I | re.S)
        title = re.sub(r"<[^>]+>", " ", title_match.group(1)).strip() if title_match else ""
        action = slugify(title or action_name_from_method_path(method, path))
        root = self._infer_root_from_url(url)
        child = self._infer_child_from_path(root, path, url)
        doc_url = url
        return ActionSpec(root, child, action, method, path, doc_url=doc_url, aliases=(action_name_from_method_path(method, path),))

    def _infer_root_from_url(self, url: str) -> str:
        match = re.search(r"/docs/ghl/([^/]+)/", url)
        if not match:
            return "unknown"
        return URL_ROOT_ALIASES.get(match.group(1), slugify(match.group(1)))

    def _infer_child_from_path(self, root: str, path: str, url: str) -> str:
        if root == "brand_boards":
            return "brand_voices" if "/voices" in path else "brand_boards"
        if root == "social_planner":
            if "/accounts" in path: return "account"
            if "/posts" in path: return "post"
            if "/csv" in path: return "csv"
            if "/categories" in path: return "category"
            if "/tags" in path: return "tag"
            if "/statistics" in path: return "statistics"
            if "/oauth" in path: return "oauth"
        if root == "payments":
            for child in ["integrations", "orders", "transactions", "subscriptions", "coupon", "custom_provider"]:
                if child.replace("_", "-") in path or child in path:
                    return "coupons" if child == "coupon" else child
        if root == "products":
            if "/price" in path: return "prices"
            if "/collections" in path: return "collections"
            if "/reviews" in path: return "reviews"
            if "/store" in path: return "store"
            return "products"
        if root == "invoice":
            if "/schedule" in path: return "schedule"
            if "/template" in path: return "template"
            if "/estimate" in path: return "estimate"
            return "invoice"
        if root == "sub_account":
            if "/customValues" in path: return "custom_value"
            if "/customFields" in path or "/custom-fields" in path or "/custom-field" in path: return "custom_field"
            if "/tags" in path: return "tags"
            if "/templates" in path: return "template"
            if "/tasks" in path: return "tasks_search"
            if "/timeZones" in path: return "timezone"
            if "/search" in path: return "search"
            return "sub_account"
        # URL segment after root often names the child index.
        parts = urllib.parse.urlparse(url).path.split("/")
        try:
            root_idx = parts.index("ghl") + 2
            if len(parts) > root_idx:
                maybe = parts[root_idx]
                if maybe and maybe not in {"index.html"}:
                    return slugify(maybe)
        except Exception:
            pass
        return slugify(root)


# ---------------------------------------------------------------------------
# Token storage and OAuth
# ---------------------------------------------------------------------------


class JsonTokenStore:
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()

    def load(self, key: str = "default") -> TokenSet | None:
        with self._lock:
            if not os.path.exists(self.path):
                return None
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            item = data.get(key)
            return TokenSet(**item) if item else None

    def save(self, token_set: TokenSet, key: str = "default") -> None:
        with self._lock:
            data: dict[str, t.Any] = {}
            if os.path.exists(self.path):
                try:
                    with open(self.path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception:
                    data = {}
            data[key] = token_set.to_dict()
            os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, sort_keys=True)


class RateLimiter:
    def __init__(self, max_requests: int = 90, interval_seconds: float = 10.0):
        self.max_requests = max_requests
        self.interval_seconds = interval_seconds
        self._lock = threading.Lock()
        self._hits: list[float] = []
        self.last_headers: dict[str, str] = {}

    def acquire(self) -> None:
        with self._lock:
            now = time.time()
            self._hits = [hit for hit in self._hits if now - hit < self.interval_seconds]
            if len(self._hits) >= self.max_requests:
                sleep_for = self.interval_seconds - (now - self._hits[0]) + 0.05
                if sleep_for > 0:
                    time.sleep(sleep_for)
            self._hits.append(time.time())

    def update_from_headers(self, headers: t.Mapping[str, t.Any]) -> None:
        wanted = {
            "x-ratelimit-limit-daily",
            "x-ratelimit-daily-remaining",
            "x-ratelimit-interval-milliseconds",
            "x-ratelimit-max",
            "x-ratelimit-remaining",
        }
        self.last_headers = {k: str(v) for k, v in headers.items() if k.lower() in wanted}
        interval = self.last_headers.get("X-RateLimit-Interval-Milliseconds") or self.last_headers.get("x-ratelimit-interval-milliseconds")
        maximum = self.last_headers.get("X-RateLimit-Max") or self.last_headers.get("x-ratelimit-max")
        try:
            if interval:
                self.interval_seconds = max(1.0, float(interval) / 1000.0)
            if maximum:
                self.max_requests = max(1, int(float(maximum)) - 1)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# HTTP transport
# ---------------------------------------------------------------------------


class HighLevelTransport:
    def __init__(
        self,
        *,
        bearer_token: str | None = None,
        token_set: TokenSet | None = None,
        oauth_config: OAuthConfig | None = None,
        token_store: JsonTokenStore | None = None,
        token_store_key: str = "default",
        base_url: str = DEFAULT_BASE_URL,
        version: str = DEFAULT_VERSION,
        session: t.Any = None,
        timeout: int = 30,
        max_retries: int = 4,
        rate_limiter: RateLimiter | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.version = version
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = session or (requests.Session() if requests is not None else None)
        self.oauth_config = oauth_config
        self.token_store = token_store
        self.token_store_key = token_store_key
        self.rate_limiter = rate_limiter or RateLimiter()
        self._token_set = token_set
        if bearer_token and not token_set:
            self._token_set = TokenSet(access_token=bearer_token)
        if not self._token_set and token_store:
            self._token_set = token_store.load(token_store_key)

    @property
    def token_set(self) -> TokenSet | None:
        return self._token_set

    @token_set.setter
    def token_set(self, value: TokenSet | None) -> None:
        self._token_set = value
        if value and self.token_store:
            self.token_store.save(value, self.token_store_key)

    @property
    def access_token(self) -> str | None:
        return self._token_set.access_token if self._token_set else None

    def authorization_url(self, *, state: str, scopes: t.Iterable[str] | None = None, redirect_uri: str | None = None) -> str:
        if not self.oauth_config:
            raise HighLevelAuthError("OAuthConfig is required to build an authorization URL")
        params = {
            "response_type": "code",
            "client_id": self.oauth_config.client_id,
            "redirect_uri": redirect_uri or self.oauth_config.redirect_uri or "",
            "scope": " ".join(scopes or self.oauth_config.scopes),
            "state": state,
        }
        return "https://marketplace.gohighlevel.com/oauth/chooselocation?" + urllib.parse.urlencode(params)

    def exchange_code(self, code: str, *, redirect_uri: str | None = None) -> TokenSet:
        if not self.oauth_config:
            raise HighLevelAuthError("OAuthConfig is required to exchange an authorization code")
        payload = {
            "grant_type": "authorization_code",
            "client_id": self.oauth_config.client_id,
            "client_secret": self.oauth_config.client_secret,
            "code": code,
        }
        if redirect_uri or self.oauth_config.redirect_uri:
            payload["redirect_uri"] = redirect_uri or self.oauth_config.redirect_uri
        data = self._token_request(payload)
        token_set = TokenSet.from_oauth_response(data)
        self.token_set = token_set
        return token_set

    def refresh(self) -> TokenSet:
        if not self.oauth_config or not self._token_set or not self._token_set.refresh_token:
            raise HighLevelAuthError("OAuth refresh requires OAuthConfig and a refresh_token")
        payload = {
            "grant_type": "refresh_token",
            "client_id": self.oauth_config.client_id,
            "client_secret": self.oauth_config.client_secret,
            "refresh_token": self._token_set.refresh_token,
        }
        data = self._token_request(payload)
        token_set = TokenSet.from_oauth_response(data)
        self.token_set = token_set
        return token_set

    def _token_request(self, payload: dict[str, t.Any]) -> dict[str, t.Any]:
        if requests is None and not self.session:
            raise RuntimeError("requests is required for token requests")
        url = self.oauth_config.token_url if self.oauth_config else DEFAULT_BASE_URL + "/oauth/token"
        if self.session is None:
            raise RuntimeError("requests is required for token requests unless a compatible session is supplied")
        response = self.session.post(url, data=payload, timeout=self.timeout)
        if response.status_code >= 400:
            raise HighLevelAuthError("OAuth token request failed", status_code=response.status_code, response=_safe_response_body(response))
        return response.json()

    def request(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, t.Any] | None = None,
        payload: t.Any = None,
        data: t.Any = None,
        files: t.Any = None,
        headers: dict[str, str] | None = None,
        raw: bool = False,
        timeout: int | None = None,
    ) -> t.Any:
        method = method.upper().strip()
        if method not in HTTP_METHODS:
            raise ValueError(f"Invalid HTTP method {method!r}")
        if not path.startswith("/"):
            path = "/" + path
        url = self.base_url + path
        request_headers = self._headers(headers, json_body=payload is not None and files is None)

        if self._token_set and self._token_set.is_expiring() and self.oauth_config and self._token_set.refresh_token:
            self.refresh()
            request_headers = self._headers(headers, json_body=payload is not None and files is None)

        last_response = None
        for attempt in range(self.max_retries + 1):
            self.rate_limiter.acquire()
            LOGGER.debug("HighLevel request %s", redact({"method": method, "url": url, "query": query, "payload": payload}))
            if self.session is None:
                raise RuntimeError("requests is required for API requests unless a compatible session is supplied")
            response = self.session.request(
                method,
                url,
                params=_clean_params(query),
                json=payload if files is None else None,
                data=data,
                files=files,
                headers=request_headers,
                timeout=timeout or self.timeout,
            )
            last_response = response
            self.rate_limiter.update_from_headers(getattr(response, "headers", {}))
            if response.status_code == 401 and self.oauth_config and self._token_set and self._token_set.refresh_token and attempt == 0:
                self.refresh()
                request_headers = self._headers(headers, json_body=payload is not None and files is None)
                continue
            if response.status_code in {429, 500, 502, 503, 504} and attempt < self.max_retries:
                retry_after = _retry_after_seconds(response)
                if retry_after is None:
                    retry_after = min(30.0, 0.5 * (2 ** attempt))
                time.sleep(retry_after)
                continue
            return self._handle_response(response, raw=raw, request={"method": method, "url": url, "query": query})
        assert last_response is not None
        return self._handle_response(last_response, raw=raw, request={"method": method, "url": url, "query": query})

    def _headers(self, extra: dict[str, str] | None = None, *, json_body: bool = True) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Version": self.version,
        }
        if json_body:
            headers["Content-Type"] = "application/json"
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        if extra:
            headers.update(extra)
        return headers

    def _handle_response(self, response: t.Any, *, raw: bool, request: dict[str, t.Any]) -> t.Any:
        status = int(response.status_code)
        if status == 429:
            raise HighLevelRateLimitError("HighLevel API rate limit exceeded", status_code=status, response=_safe_response_body(response), request=request)
        if status == 401:
            raise HighLevelAuthError("HighLevel API authorization failed", status_code=status, response=_safe_response_body(response), request=request)
        if status >= 400:
            raise HighLevelAPIError(f"HighLevel API request failed with status {status}", status_code=status, response=_safe_response_body(response), request=request)
        if raw:
            return response
        if status == 204:
            return None
        content_type = str(getattr(response, "headers", {}).get("Content-Type", ""))
        if "application/json" in content_type.lower():
            return response.json()
        try:
            return response.json()
        except Exception:
            return getattr(response, "text", None)


# ---------------------------------------------------------------------------
# Handler and resolvers
# ---------------------------------------------------------------------------


class HighLevelHandler:
    def __init__(
        self,
        *,
        bearer_token: str | None = None,
        token_set: TokenSet | None = None,
        oauth_config: OAuthConfig | None = None,
        token_store: JsonTokenStore | None = None,
        location_id: str | None = None,
        company_id: str | None = None,
        user_id: str | None = None,
        app_id: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        version: str = DEFAULT_VERSION,
        registry: ActionRegistry | None = None,
        session: t.Any = None,
        timeout: int = 30,
        max_retries: int = 4,
        safe_social_posting: bool = True,
    ):
        self.context = SessionContext(location_id=location_id, company_id=company_id, user_id=user_id, app_id=app_id)
        self.registry = registry or ActionRegistry.seeded()
        self.transport = HighLevelTransport(
            bearer_token=bearer_token or os.getenv("HIGHLEVEL_BEARER_TOKEN") or os.getenv("GHL_BEARER_TOKEN"),
            token_set=token_set,
            oauth_config=oauth_config,
            token_store=token_store,
            base_url=base_url,
            version=version,
            session=session,
            timeout=timeout,
            max_retries=max_retries,
        )
        self.safe_social_posting = safe_social_posting

    @classmethod
    def from_env(cls, **kwargs: t.Any) -> "HighLevelHandler":
        kwargs.setdefault("bearer_token", os.getenv("HIGHLEVEL_BEARER_TOKEN") or os.getenv("GHL_BEARER_TOKEN"))
        kwargs.setdefault("location_id", os.getenv("HIGHLEVEL_LOCATION_ID") or os.getenv("GHL_LOCATION_ID"))
        kwargs.setdefault("company_id", os.getenv("HIGHLEVEL_COMPANY_ID") or os.getenv("GHL_COMPANY_ID"))
        kwargs.setdefault("user_id", os.getenv("HIGHLEVEL_USER_ID") or os.getenv("GHL_USER_ID"))
        kwargs.setdefault("app_id", os.getenv("HIGHLEVEL_APP_ID") or os.getenv("GHL_APP_ID"))
        return cls(**kwargs)

    def __getattr__(self, name: str) -> "ResourceProxy":
        root = canonical_root(name)
        if root in DEFAULT_ROOTS or root in self.registry.list_roots():
            return ResourceProxy(self, [root])
        raise AttributeError(name)

    def refresh_registry_from_docs(self, *, docs_url: str = DEFAULT_DOCS_URL, save_to: str | None = None, max_pages: int = 2000) -> ActionRegistry:
        crawler = DocsCrawler(docs_url=docs_url)
        fresh = crawler.crawl(max_pages=max_pages)
        self.registry.merge(fresh, replace=True)
        if save_to:
            self.registry.save(save_to)
        return self.registry

    def load_registry(self, path: str, *, merge: bool = True) -> None:
        registry = ActionRegistry.from_file(path)
        if merge:
            self.registry.merge(registry)
        else:
            self.registry = registry

    def request_path(
        self,
        method: str,
        path: str,
        *,
        path_params: dict[str, t.Any] | None = None,
        query: dict[str, t.Any] | None = None,
        payload: t.Any = None,
        data: t.Any = None,
        files: t.Any = None,
        headers: dict[str, str] | None = None,
        raw: bool = False,
        **kwargs: t.Any,
    ) -> t.Any:
        path_params = dict(path_params or {})
        path_params.update({k: v for k, v in kwargs.items() if k in re.findall(r":([A-Za-z_][A-Za-z0-9_]*)", path)})
        path = self._render_path(path, path_params)
        return self.transport.request(method, path, query=query, payload=payload, data=data, files=files, headers=headers, raw=raw)

    def invoke(
        self,
        root: str,
        child: str,
        action: str,
        *,
        path_params: dict[str, t.Any] | None = None,
        query: dict[str, t.Any] | None = None,
        payload: t.Any = None,
        data: t.Any = None,
        files: t.Any = None,
        headers: dict[str, str] | None = None,
        resolve: dict[str, t.Any] | bool | None = None,
        raw: bool = False,
        skip_resolve: bool = False,
        **kwargs: t.Any,
    ) -> t.Any:
        spec = self.registry.get(root, child, action)
        path_params, query, payload = self._prepare_call(spec, path_params=path_params, query=query, payload=payload, kwargs=kwargs)
        if not skip_resolve:
            path_params, query, payload = self._resolve_dependencies(spec, path_params, query, payload, resolve)
        path = self._render_path(spec.path, path_params)
        return self.transport.request(spec.method, path, query=query, payload=payload, data=data, files=files, headers=headers, raw=raw)

    def paginate(
        self,
        root: str,
        child: str,
        action: str,
        *,
        item_path: str | None = None,
        cursor_param: str = "page",
        next_cursor_path: str | None = None,
        limit_param: str = "limit",
        limit: int | None = None,
        max_pages: int | None = None,
        **kwargs: t.Any,
    ) -> t.Iterator[t.Any]:
        page = 1
        cursor: t.Any = kwargs.pop(cursor_param, None) or page
        query = dict(kwargs.pop("query", {}) or {})
        if limit is not None:
            query[limit_param] = limit
        yielded_pages = 0
        while True:
            query[cursor_param] = cursor
            response = self.invoke(root, child, action, query=query, **kwargs)
            yielded_pages += 1
            items = _get_path(response, item_path) if item_path else _extract_items(response)
            if items is None:
                yield response
            else:
                for item in items:
                    yield item
            if max_pages and yielded_pages >= max_pages:
                break
            next_cursor = _get_path(response, next_cursor_path) if next_cursor_path else _infer_next_cursor(response, cursor)
            if not next_cursor:
                break
            cursor = next_cursor

    def _prepare_call(
        self,
        spec: ActionSpec,
        *,
        path_params: dict[str, t.Any] | None,
        query: dict[str, t.Any] | None,
        payload: t.Any,
        kwargs: dict[str, t.Any],
    ) -> tuple[dict[str, t.Any], dict[str, t.Any], t.Any]:
        path_params = dict(path_params or {})
        query = dict(query or {})
        kwargs = dict(kwargs)
        for param in spec.path_params:
            if param not in path_params:
                value = self._pop_param_value(param, kwargs)
                if value is None:
                    value = self.context.get_for_param(param)
                if value is not None:
                    path_params[param] = value
        if payload is None and "json" in kwargs:
            payload = kwargs.pop("json")
        if payload is None and "body" in kwargs:
            payload = kwargs.pop("body")
        if spec.method in {"GET", "DELETE"}:
            query.update(kwargs)
        else:
            # For write methods, explicit query wins. Remaining kwargs become payload fields.
            if payload is None and kwargs:
                payload = kwargs
            elif isinstance(payload, dict) and kwargs:
                payload = {**payload, **kwargs}
        return path_params, query, payload

    def _pop_param_value(self, param: str, values: dict[str, t.Any]) -> t.Any:
        candidates = [param, camel_to_snake(param), slugify(param)] + list(PARAM_ALIASES.get(param, ()))
        for candidate in candidates:
            if candidate in values:
                return values.pop(candidate)
        return None

    def _render_path(self, path_template: str, path_params: dict[str, t.Any]) -> str:
        missing = []
        path = path_template
        for param in re.findall(r":([A-Za-z_][A-Za-z0-9_]*)", path_template):
            if param not in path_params or path_params[param] is None:
                value = self.context.get_for_param(param)
                if value is not None:
                    path_params[param] = value
                else:
                    missing.append(param)
                    continue
            encoded = urllib.parse.quote(str(path_params[param]), safe="")
            path = path.replace(":" + param, encoded)
        if missing:
            raise MissingParameterError(f"Missing path parameter(s) for {path_template}: {', '.join(missing)}")
        return path

    def _resolve_dependencies(
        self,
        spec: ActionSpec,
        path_params: dict[str, t.Any],
        query: dict[str, t.Any],
        payload: t.Any,
        resolve: dict[str, t.Any] | bool | None,
    ) -> tuple[dict[str, t.Any], dict[str, t.Any], t.Any]:
        resolve_spec: dict[str, t.Any]
        if resolve is True:
            resolve_spec = {"auto": True}
        elif isinstance(resolve, dict):
            resolve_spec = dict(resolve)
        else:
            resolve_spec = {}

        # Social Planner post dependencies. Create and list use accountIds in the request body.
        if spec.root == "social_planner" and spec.child == "post" and spec.action in {"create_post", "get_posts", "list_social_media_posting_posts", "list_posts"}:
            payload_dict = payload if isinstance(payload, dict) else {}
            account_key = "accountIds" if "accountIds" in payload_dict else "account_ids"
            has_accounts = bool(payload_dict.get("accountIds") or payload_dict.get("account_ids") or query.get("accountIds") or query.get("account_ids"))
            wants_resolution = any(k in resolve_spec for k in ("accountIds", "account_ids", "social_accounts", "accounts")) or resolve_spec.get("auto")
            if not has_accounts and wants_resolution:
                selector = resolve_spec.get("accountIds") or resolve_spec.get("account_ids") or resolve_spec.get("social_accounts") or resolve_spec.get("accounts") or {}
                account_ids = self.resolve_social_account_ids(selector, location_id=path_params.get("locationId"))
                if not account_ids:
                    raise ResolverError("Social Planner accountIds could not be resolved from Get Accounts")
                payload_dict = dict(payload_dict)
                payload_dict["accountIds"] = account_ids
                payload = payload_dict
            elif spec.action == "create_post" and not has_accounts and not self.safe_social_posting:
                account_ids = self.resolve_social_account_ids({"all": True}, location_id=path_params.get("locationId"))
                payload_dict = dict(payload_dict)
                payload_dict["accountIds"] = account_ids
                payload = payload_dict
            elif spec.action == "create_post" and not has_accounts and not _is_draft_payload(payload_dict):
                # Do not silently post to all channels. The resolver exists, but writes require intent.
                raise ResolverError(
                    "Create post requires accountIds for non-draft posts. Pass payload['accountIds'] or "
                    "resolve={'accountIds': {'platforms': ['facebook']}}."
                )

        # Product price endpoints require productId. Resolve by product name when asked.
        if "productId" in spec.path_params and "productId" not in path_params:
            selector = resolve_spec.get("productId") or resolve_spec.get("product") or resolve_spec.get("product_id")
            if selector:
                path_params["productId"] = self.resolve_product_id(selector)

        # Opportunity operations often require pipelineId and sometimes stageId in payload.
        if spec.root == "opportunities" and isinstance(payload, dict):
            if not payload.get("pipelineId") and (resolve_spec.get("pipeline") or resolve_spec.get("pipelineId")):
                payload = dict(payload)
                payload["pipelineId"] = self.resolve_pipeline_id(resolve_spec.get("pipeline") or resolve_spec.get("pipelineId"))
            if not payload.get("stageId") and resolve_spec.get("stage"):
                payload = dict(payload)
                payload["stageId"] = self.resolve_stage_id(resolve_spec.get("stage"), pipeline_id=payload.get("pipelineId"))
        return path_params, query, payload

    def resolve_social_account_ids(self, selector: t.Any = None, *, location_id: str | None = None) -> list[str]:
        location_id = location_id or self.context.location_id
        if not location_id:
            raise MissingParameterError("locationId is required to resolve Social Planner account IDs")
        if selector is True or selector is None:
            selector = {"all": True}
        if isinstance(selector, str):
            selector = {"platforms": [selector]}
        if isinstance(selector, list):
            selector = {"ids": selector}
        selector = dict(selector or {})
        if selector.get("ids"):
            return list(selector["ids"])
        response = self.invoke("social_planner", "account", "get_accounts", path_params={"locationId": location_id}, skip_resolve=True)
        accounts = _flatten_social_accounts(response)
        if not accounts:
            return []
        platforms = {slugify(p) for p in selector.get("platforms", selector.get("channels", []))}
        names = {slugify(n) for n in selector.get("names", [])}
        groups = {slugify(g) for g in selector.get("groups", [])}
        out: list[str] = []
        for account in accounts:
            account_id = account.get("id") or account.get("accountId") or account.get("_id")
            if not account_id:
                continue
            platform = slugify(account.get("platform") or account.get("type") or account.get("provider") or account.get("channel") or "")
            name = slugify(account.get("name") or account.get("username") or account.get("displayName") or account.get("pageName") or "")
            group = slugify(account.get("groupName") or account.get("group") or "")
            if platforms and platform not in platforms:
                continue
            if names and name not in names:
                continue
            if groups and group not in groups:
                continue
            out.append(str(account_id))
        if selector.get("first") and out:
            return [out[0]]
        if selector.get("all") or platforms or names or groups:
            return out
        return []

    def resolve_product_id(self, selector: t.Any) -> str:
        if isinstance(selector, str) and re.match(r"^[A-Za-z0-9_-]{8,}$", selector):
            return selector
        name = selector.get("name") if isinstance(selector, dict) else str(selector)
        response = self.invoke("products", "products", "list_products", skip_resolve=True)
        return _find_id_by_name(response, name, id_keys=("productId", "id", "_id"), name_keys=("name", "title"))

    def resolve_pipeline_id(self, selector: t.Any) -> str:
        if isinstance(selector, str) and re.match(r"^[A-Za-z0-9_-]{8,}$", selector):
            return selector
        name = selector.get("name") if isinstance(selector, dict) else str(selector)
        response = self.invoke("opportunities", "pipelines", "get_pipelines", skip_resolve=True)
        return _find_id_by_name(response, name, id_keys=("pipelineId", "id", "_id"), name_keys=("name", "title"))

    def resolve_stage_id(self, selector: t.Any, *, pipeline_id: str | None = None) -> str:
        if isinstance(selector, str) and re.match(r"^[A-Za-z0-9_-]{8,}$", selector):
            return selector
        name = selector.get("name") if isinstance(selector, dict) else str(selector)
        response = self.invoke("opportunities", "pipelines", "get_pipelines", skip_resolve=True)
        pipelines = _extract_items(response)
        for pipeline in pipelines:
            if pipeline_id and str(pipeline.get("id") or pipeline.get("pipelineId")) != str(pipeline_id):
                continue
            for stage in pipeline.get("stages", []) or []:
                stage_name = stage.get("name") or stage.get("title")
                if slugify(stage_name) == slugify(name):
                    return str(stage.get("id") or stage.get("stageId"))
        raise ResolverError(f"Could not resolve stage id for {name!r}")


class ResourceProxy:
    def __init__(self, handler: HighLevelHandler, parts: list[str]):
        self._handler = handler
        self._parts = parts

    def __getattr__(self, name: str) -> "ResourceProxy":
        return ResourceProxy(self._handler, self._parts + [slugify(name)])

    def __call__(self, *args: t.Any, **kwargs: t.Any) -> t.Any:
        if len(self._parts) < 3:
            raise AttributeError("Call requires root.child.action, for example handler.contacts.contacts.create_contact(...)")
        root, child, action = self._parts[:3]
        if args:
            if len(args) == 1 and "payload" not in kwargs and isinstance(args[0], dict):
                kwargs["payload"] = args[0]
            else:
                raise TypeError("Positional arguments are only supported as a single payload dict")
        return self._handler.invoke(root, child, action, **kwargs)

    def actions(self) -> list[str]:
        if len(self._parts) == 1:
            return self._handler.registry.list_actions(self._parts[0])
        if len(self._parts) >= 2:
            return self._handler.registry.list_actions(self._parts[0], self._parts[1])
        return []

    def children(self) -> list[str]:
        if not self._parts:
            return []
        return self._handler.registry.list_children(self._parts[0])


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------


def _clean_params(params: dict[str, t.Any] | None) -> dict[str, t.Any] | None:
    if not params:
        return None
    return {k: v for k, v in params.items() if v is not None}


def _safe_response_body(response: t.Any) -> t.Any:
    try:
        return response.json()
    except Exception:
        return getattr(response, "text", None)


def _retry_after_seconds(response: t.Any) -> float | None:
    headers = getattr(response, "headers", {}) or {}
    value = headers.get("Retry-After") or headers.get("retry-after")
    if value:
        try:
            return float(value)
        except Exception:
            return None
    return None


def _extract_items(response: t.Any) -> list[t.Any]:
    if response is None:
        return []
    if isinstance(response, list):
        return response
    if not isinstance(response, dict):
        return []
    for key in ("items", "data", "results", "contacts", "opportunities", "products", "records", "accounts", "posts", "pipelines", "users", "forms", "surveys", "invoices", "orders", "transactions", "subscriptions", "affiliates", "payouts", "commissions"):
        value = response.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            nested = _extract_items(value)
            if nested:
                return nested
    # Some GHL responses are {resource: {...}}; return dict values that look like records.
    values = [v for v in response.values() if isinstance(v, dict) and ("id" in v or "_id" in v)]
    return values


def _get_path(data: t.Any, path: str | None) -> t.Any:
    if not path:
        return data
    current = data
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list) and part.isdigit():
            idx = int(part)
            current = current[idx] if idx < len(current) else None
        else:
            return None
    return current


def _infer_next_cursor(response: t.Any, current: t.Any) -> t.Any:
    if not isinstance(response, dict):
        return None
    for key in ("nextPageToken", "next_page_token", "next", "nextCursor", "next_cursor", "startAfter"):
        if response.get(key):
            return response[key]
    meta = response.get("meta") or response.get("pagination") or {}
    if isinstance(meta, dict):
        for key in ("nextPage", "next_page", "nextPageToken", "nextCursor"):
            if meta.get(key):
                return meta[key]
        if meta.get("currentPage") and meta.get("totalPages") and meta["currentPage"] < meta["totalPages"]:
            return int(meta["currentPage"]) + 1
    if isinstance(current, int):
        items = _extract_items(response)
        if items:
            return current + 1
    return None


def _flatten_social_accounts(response: t.Any) -> list[dict[str, t.Any]]:
    items = _extract_items(response)
    flattened: list[dict[str, t.Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if item.get("accounts") and isinstance(item["accounts"], list):
            for account in item["accounts"]:
                if isinstance(account, dict):
                    merged = {**account}
                    merged.setdefault("groupName", item.get("name") or item.get("groupName"))
                    flattened.append(merged)
        else:
            flattened.append(item)
    return flattened


def _find_id_by_name(response: t.Any, name: str, *, id_keys: tuple[str, ...], name_keys: tuple[str, ...]) -> str:
    target = slugify(name)
    for item in _extract_items(response):
        if not isinstance(item, dict):
            continue
        for name_key in name_keys:
            if slugify(item.get(name_key, "")) == target:
                for id_key in id_keys:
                    if item.get(id_key):
                        return str(item[id_key])
    raise ResolverError(f"Could not resolve id by name {name!r}")


def _is_draft_payload(payload: dict[str, t.Any]) -> bool:
    status = slugify(payload.get("status") or payload.get("postStatus") or payload.get("type") or "")
    return status == "draft" or bool(payload.get("isDraft"))


# ---------------------------------------------------------------------------
# Seed registry
# Format: root|child|action|method|path|scope|access|description|aliases
# ---------------------------------------------------------------------------

SEED_ENDPOINTS = r'''
# OAuth 2.0
oauth_2_0|oauth_2_0|get_access_token|POST|/oauth/token|oauth.write|Agency|Exchange an OAuth code or refresh token for an access token|token,exchange_token
oauth_2_0|oauth_2_0|get_location_access_token|POST|/oauth/locationToken|oauth.write|Agency|Get Location Access Token from Agency Token|location_token
oauth_2_0|oauth_2_0|get_installed_locations|GET|/oauth/installedLocations|oauth.readonly|Agency|Get locations where the app is installed|installed_locations

# Brand Boards
brand_boards|brand_boards|get_brand_boards|GET|/brand-boards/:locationId|brand-boards.readonly|Sub-Account|Retrieves all Brand Boards for a location|list
brand_boards|brand_boards|get_brand_board|GET|/brand-boards/:locationId/:id|brand-boards.readonly|Sub-Account|Retrieves a specific Brand Board by ID|get
brand_boards|brand_boards|update_brand_board|PATCH|/brand-boards/:locationId/:id|brand-boards.write|Sub-Account|Updates an existing Brand Board|update
brand_boards|brand_boards|delete_brand_board|DELETE|/brand-boards/:locationId/:id|brand-boards.write|Sub-Account|Deletes a Brand Board|delete
brand_boards|brand_boards|create_brand_board|POST|/brand-boards/|brand-boards.write|Sub-Account|Creates a new brand board|create
brand_boards|brand_voices|list_brand_voices|GET|/brand-boards/public/v1/locations/:locationId/voices|brand-boards.readonly|Sub-Account|Get list of brand voices for a location|list
brand_boards|brand_voices|create_brand_voice|POST|/brand-boards/public/v1/locations/:locationId/voices|brand-boards.write|Sub-Account|Create a brand voice for a location|create
brand_boards|brand_voices|get_brand_voice|GET|/brand-boards/public/v1/locations/:locationId/voices/:brandVoiceId|brand-boards.readonly|Sub-Account|Get a brand voice by ID|get
brand_boards|brand_voices|update_brand_voice|PATCH|/brand-boards/public/v1/locations/:locationId/voices/:brandVoiceId|brand-boards.write|Sub-Account|Update a brand voice by ID|update
brand_boards|brand_voices|delete_brand_voice|DELETE|/brand-boards/public/v1/locations/:locationId/voices/:brandVoiceId|brand-boards.write|Sub-Account|Delete a brand voice by ID|delete
brand_boards|brand_voices|set_default_brand_voice|POST|/brand-boards/public/v1/locations/:locationId/voices/:brandVoiceId/default|brand-boards.write|Sub-Account|Set a brand voice as default|set_default

# Business
business|businesses|list_businesses|GET|/businesses|businesses.readonly|Sub-Account|List businesses|list
business|businesses|get_business|GET|/businesses/:businessId|businesses.readonly|Sub-Account|Get business|get
business|businesses|create_business|POST|/businesses|businesses.write|Sub-Account|Create business|create
business|businesses|update_business|PUT|/businesses/:businessId|businesses.write|Sub-Account|Update business|update
business|businesses|delete_business|DELETE|/businesses/:businessId|businesses.write|Sub-Account|Delete business|delete

# Calendars
calendars|calendars|create_calendar|POST|/calendars/|calendars.write|Sub-Account|Create calendar|create
calendars|calendars|list_calendars|GET|/calendars/|calendars.readonly|Sub-Account|List calendars|list
calendars|calendars|get_calendar|GET|/calendars/:calendarId|calendars.readonly|Sub-Account|Get calendar|get
calendars|calendars|update_calendar|PUT|/calendars/:calendarId|calendars.write|Sub-Account|Update calendar|update
calendars|calendars|delete_calendar|DELETE|/calendars/:calendarId|calendars.write|Sub-Account|Delete calendar|delete
calendars|availability|get_free_slots|GET|/calendars/:calendarId/free-slots|calendars.readonly|Sub-Account|Get calendar free slots|free_slots
calendars|calendar_groups|list_groups|GET|/calendars/groups|calendars/groups.readonly|Sub-Account|List calendar groups|list
calendars|calendar_groups|create_group|POST|/calendars/groups|calendars/groups.write|Sub-Account|Create calendar group|create
calendars|calendar_groups|validate_group_slug|POST|/calendars/groups/validate-slug|calendars/groups.write|Sub-Account|Validate calendar group slug|validate_slug
calendars|calendar_groups|delete_group|DELETE|/calendars/groups/:groupId|calendars/groups.write|Sub-Account|Delete calendar group|delete
calendars|calendar_groups|update_group|PUT|/calendars/groups/:groupId|calendars/groups.write|Sub-Account|Update calendar group|update
calendars|calendar_groups|update_group_status|PUT|/calendars/groups/:groupId/status|calendars/groups.write|Sub-Account|Update group status|update_status
calendars|calendar_resources|get_resources|GET|/calendars/resources/:resourceType|calendars/resources.readonly|Sub-Account|Get calendar resources|list
calendars|calendar_resources|get_resource|GET|/calendars/resources/:resourceType/:id|calendars/resources.readonly|Sub-Account|Get calendar resource|get
calendars|calendar_resources|create_resource|POST|/calendars/resources|calendars/resources.write|Sub-Account|Create calendar resource|create
calendars|calendar_resources|update_resource|PUT|/calendars/resources/:resourceType/:id|calendars/resources.write|Sub-Account|Update calendar resource|update
calendars|calendar_resources|delete_resource|DELETE|/calendars/resources/:resourceType/:id|calendars/resources.write|Sub-Account|Delete calendar resource|delete
calendars|calendar_events|get_appointment|GET|/calendars/events/appointments/:eventId|calendars/events.readonly|Sub-Account|Get appointment|get_appointment
calendars|calendar_events|list_events|GET|/calendars/events|calendars/events.readonly|Sub-Account|List calendar events|list
calendars|calendar_events|get_blocked_slots|GET|/calendars/blocked-slots|calendars/events.readonly|Sub-Account|Get blocked slots|blocked_slots
calendars|calendar_events|delete_event|DELETE|/calendars/events/:eventId|calendars/events.write|Sub-Account|Delete event|delete
calendars|calendar_events|create_block_slot|POST|/calendars/events/block-slots|calendars/events.write|Sub-Account|Create block slot|create_block_slot
calendars|calendar_events|update_block_slot|PUT|/calendars/events/block-slots/:eventId|calendars/events.write|Sub-Account|Update block slot|update_block_slot
calendars|calendar_events|create_appointment|POST|/calendars/events/appointments|calendars/events.write|Sub-Account|Create appointment|create_appointment
calendars|calendar_events|update_appointment|PUT|/calendars/events/appointments/:eventId|calendars/events.write|Sub-Account|Update appointment|update_appointment

# Campaigns
campaigns|campaigns|get_campaigns|GET|/campaigns/|campaigns.readonly|Sub-Account|Get campaigns|list

# Companies
companies|companies|get_company|GET|/companies/:companyId|companies.readonly|Agency|Get company|get

# Contacts
contacts|contacts|list_contacts|GET|/contacts/|contacts.readonly|Sub-Account|List contacts|list,search
contacts|contacts|get_contact|GET|/contacts/:contactId|contacts.readonly|Sub-Account|Get contact|get
contacts|contacts|get_contacts_by_business|GET|/contacts/business/:businessId|contacts.readonly|Sub-Account|Get contacts by business|by_business
contacts|contacts|create_contact|POST|/contacts/|contacts.write|Sub-Account|Create contact|create
contacts|contacts|update_contact|PUT|/contacts/:contactId|contacts.write|Sub-Account|Update contact|update
contacts|contacts|delete_contact|DELETE|/contacts/:contactId|contacts.write|Sub-Account|Delete contact|delete
contacts|tasks|list_tasks|GET|/contacts/:contactId/tasks|contacts.readonly|Sub-Account|List contact tasks|list
contacts|tasks|get_task|GET|/contacts/:contactId/tasks/:taskId|contacts.readonly|Sub-Account|Get contact task|get
contacts|tasks|create_task|POST|/contacts/:contactId/tasks|contacts.write|Sub-Account|Create contact task|create
contacts|tasks|update_task|PUT|/contacts/:contactId/tasks/:taskId|contacts.write|Sub-Account|Update contact task|update
contacts|tasks|mark_task_completed|PUT|/contacts/:contactId/tasks/:taskId/completed|contacts.write|Sub-Account|Mark contact task completed|complete
contacts|tasks|delete_task|DELETE|/contacts/:contactId/tasks/:taskId|contacts.write|Sub-Account|Delete contact task|delete
contacts|tags|add_tags|POST|/contacts/:contactId/tags|contacts.write|Sub-Account|Add tags to contact|add
contacts|tags|remove_tags|DELETE|/contacts/:contactId/tags|contacts.write|Sub-Account|Remove tags from contact|remove
contacts|notes|list_notes|GET|/contacts/:contactId/notes|contacts.readonly|Sub-Account|List contact notes|list
contacts|notes|get_note|GET|/contacts/:contactId/notes/:id|contacts.readonly|Sub-Account|Get contact note|get
contacts|notes|create_note|POST|/contacts/:contactId/notes|contacts.write|Sub-Account|Create contact note|create
contacts|notes|update_note|PUT|/contacts/:contactId/notes/:id|contacts.write|Sub-Account|Update contact note|update
contacts|notes|delete_note|DELETE|/contacts/:contactId/notes/:id|contacts.write|Sub-Account|Delete contact note|delete
contacts|appointments|list_appointments|GET|/contacts/:contactId/appointments|contacts.readonly|Sub-Account|List contact appointments|list
contacts|campaigns|add_to_campaign|POST|/contacts/:contactId/campaigns/:campaignId|contacts.write|Sub-Account|Add contact to campaign|add
contacts|campaigns|remove_all_campaigns|DELETE|/contacts/:contactId/campaigns/removeAll|contacts.write|Sub-Account|Remove contact from all campaigns|remove_all
contacts|campaigns|remove_from_campaign|DELETE|/contacts/:contactId/campaigns/:campaignId|contacts.write|Sub-Account|Remove contact from campaign|remove
contacts|workflow|add_to_workflow|POST|/contacts/:contactId/workflow/:workflowId|contacts.write|Sub-Account|Add contact to workflow|add
contacts|workflow|remove_from_workflow|DELETE|/contacts/:contactId/workflow/:workflowId|contacts.write|Sub-Account|Remove contact from workflow|remove

# Objects
objects|object_schema|list_object_schemas|GET|/objects|objects/schema.readonly|Sub-Account|List object schemas|list
objects|object_schema|get_object_schema|GET|/objects/:key|objects/schema.readonly|Sub-Account|Get object schema|get
objects|records|get_record_by_id|GET|/objects/:schemaKey/records/:id|objects/record.readonly|Sub-Account|Get object record|get
objects|records|create_record|POST|/objects/:schemaKey/records|objects/record.write|Sub-Account|Create object record|create
objects|records|update_record|PUT|/objects/:schemaKey/records/:id|objects/record.write|Sub-Account|Update object record|update
objects|records|delete_record|DELETE|/objects/:schemaKey/records/:id|objects/record.write|Sub-Account|Delete object record|delete
objects|search_object_records|search_object_records|POST|/objects/:schemaKey/records/search|objects/record.readonly|Sub-Account|Search object records|search

# Associations
associations|associations|get_association_by_key|GET|/associations/key/:key_name|associations.readonly|Sub-Account|Get association by key|get_by_key
associations|associations|get_association_by_object_key|GET|/associations/objectKey/:objectKey|associations.readonly|Sub-Account|Get association by object key|get_by_object_key
associations|associations|get_association|GET|/associations/:associationId|associations.readonly|Sub-Account|Get association|get
associations|associations|list_associations|GET|/associations/|associations.readonly|Sub-Account|List associations|list
associations|associations|create_association|POST|/associations/|associations.write|Sub-Account|Create association|create
associations|associations|update_association|PUT|/associations/:associationId|associations.write|Sub-Account|Update association|update
associations|associations|delete_association|DELETE|/associations/:associationId|associations.write|Sub-Account|Delete association|delete
associations|relations|get_relations|GET|/associations/relations/:recordId|associations/relation.readonly|Sub-Account|Get relations|list
associations|relations|create_relation|POST|/associations/relations|associations/relation.write|Sub-Account|Create relation|create

# Custom Fields V2
custom_fields_v2|custom_fields_v2|get_custom_field_by_id|GET|/custom-fields/:id|locations/customFields.readonly|Sub-Account|Get custom field by ID|get
custom_fields_v2|custom_fields_v2|get_custom_field_by_object_key|GET|/custom-field/object-key/:key|locations/customFields.readonly|Sub-Account|Get custom field by object key|get_by_object_key

# Conversations
conversations|conversations|get_conversation|GET|/conversations/:conversationsId|conversations.readonly|Sub-Account|Get conversation|get
conversations|conversations|create_conversation|POST|/conversations/|conversations.write|Sub-Account|Create conversation|create
conversations|conversations|update_conversation|PUT|/conversations/:conversationsId|conversations.write|Sub-Account|Update conversation|update
conversations|conversations|delete_conversation|DELETE|/conversations/:conversationsId|conversations.write|Sub-Account|Delete conversation|delete
conversations|search|search_conversations|GET|/conversations/search|conversations.readonly|Sub-Account|Search conversations|search
conversations|messages|get_recording|GET|/conversations/messages/:messageId/locations/:locationId/recording|conversations/message.readonly|Sub-Account|Get message recording|recording
conversations|messages|get_transcription|GET|/conversations/locations/:locationId/messages/:messageId/transcription|conversations/message.readonly|Sub-Account|Get message transcription|transcription
conversations|messages|download_transcription|GET|/conversations/locations/:locationId/messages/:messageId/transcription/download|conversations/message.readonly|Sub-Account|Download message transcription|download_transcription
conversations|messages|send_message|POST|/conversations/messages|conversations/message.write|Sub-Account|Send conversation message|send,create
conversations|messages|create_inbound_message|POST|/conversations/messages/inbound|conversations/message.write|Sub-Account|Create inbound message|inbound
conversations|messages|upload_message_attachment|POST|/conversations/messages/upload|conversations/message.write|Sub-Account|Upload message attachment|upload
conversations|messages|update_message_status|PUT|/conversations/messages/:messageId/status|conversations/message.write|Sub-Account|Update message status|update_status
conversations|messages|cancel_scheduled_message|DELETE|/conversations/messages/:messageId/schedule|conversations/message.write|Sub-Account|Cancel scheduled message|cancel_schedule
conversations|messages|cancel_scheduled_email|DELETE|/conversations/messages/email/:emailMessageId/schedule|conversations/message.write|Sub-Account|Cancel scheduled email|cancel_email_schedule

# Courses
courses|untagged|import_courses|POST|/courses/courses-exporter/public/import|courses.write|Sub-Account|Import courses|import

# Email
email|templates|list_email_templates|GET|/emails/builder|emails/builder.readonly|Sub-Account|List email builder templates|list
email|templates|create_email_template|POST|/emails/builder|emails/builder.write|Sub-Account|Create email builder template|create
email|templates|create_email_template_data|POST|/emails/builder/data|emails/builder.write|Sub-Account|Create email template data|create_data
email|templates|delete_email_template|DELETE|/emails/builder/:locationId/:templateId|emails/builder.write|Sub-Account|Delete email template|delete
email|campaigns|list_scheduled_email_campaigns|GET|/emails/schedule|emails/schedule.readonly|Sub-Account|List scheduled emails|list

# Forms
forms|forms|list_forms|GET|/forms/|forms.readonly|Sub-Account|List forms|list
forms|forms|list_form_submissions|GET|/forms/submissions|forms.readonly|Sub-Account|List form submissions|submissions
forms|forms|upload_custom_files|POST|/forms/upload-custom-files|forms.write|Sub-Account|Upload custom files|upload

# Invoice
invoice|invoice|list_invoices|GET|/invoices/|invoices.readonly|Sub-Account|List invoices|list
invoice|invoice|get_invoice|GET|/invoices/:invoiceId|invoices.readonly|Sub-Account|Get invoice|get
invoice|invoice|generate_invoice_number|GET|/invoices/generate-invoice-number|invoices.readonly|Sub-Account|Generate invoice number|generate_number
invoice|invoice|create_invoice|POST|/invoices|invoices.write|Sub-Account|Create invoice|create
invoice|invoice|update_invoice|PUT|/invoices/:invoiceId|invoices.write|Sub-Account|Update invoice|update
invoice|invoice|delete_invoice|DELETE|/invoices/:invoiceId|invoices.write|Sub-Account|Delete invoice|delete
invoice|invoice|send_invoice|POST|/invoices/:invoiceId/send|invoices.write|Sub-Account|Send invoice|send
invoice|invoice|void_invoice|POST|/invoices/:invoiceId/void|invoices.write|Sub-Account|Void invoice|void
invoice|invoice|record_payment|POST|/invoices/:invoiceId/record-payment|invoices.write|Sub-Account|Record invoice payment|record_payment
invoice|invoice|text2pay|POST|/invoices/text2pay|invoices.write|Sub-Account|Create text to pay invoice|text2pay
invoice|schedule|list_schedules|GET|/invoices/schedule/|invoices/schedule.readonly|Sub-Account|List invoice schedules|list
invoice|schedule|get_schedule|GET|/invoices/schedule/:scheduleId|invoices/schedule.readonly|Sub-Account|Get invoice schedule|get
invoice|schedule|create_schedule|POST|/invoices/schedule|invoices/schedule.write|Sub-Account|Create invoice schedule|create
invoice|schedule|update_schedule|PUT|/invoices/schedule/:scheduleId|invoices/schedule.write|Sub-Account|Update invoice schedule|update
invoice|schedule|delete_schedule|DELETE|/invoices/schedule/:scheduleId|invoices/schedule.write|Sub-Account|Delete invoice schedule|delete
invoice|schedule|schedule_invoice|POST|/invoices/schedule/:scheduleId/schedule|invoices/schedule.write|Sub-Account|Schedule invoice|schedule
invoice|schedule|auto_payment|POST|/invoices/schedule/:scheduleId/auto-payment|invoices/schedule.write|Sub-Account|Invoice schedule auto payment|auto_payment
invoice|schedule|cancel_schedule|POST|/invoices/schedule/:scheduleId/cancel|invoices/schedule.write|Sub-Account|Cancel invoice schedule|cancel
invoice|template|list_templates|GET|/invoices/template/|invoices/template.readonly|Sub-Account|List invoice templates|list
invoice|template|get_template|GET|/invoices/template/:templateId|invoices/template.readonly|Sub-Account|Get invoice template|get
invoice|template|create_template|POST|/invoices/template/|invoices/template.write|Sub-Account|Create invoice template|create
invoice|template|update_template|PUT|/invoices/template/:templateId|invoices/template.write|Sub-Account|Update invoice template|update
invoice|template|delete_template|DELETE|/invoices/template/:templateId|invoices/template.write|Sub-Account|Delete invoice template|delete
invoice|estimate|generate_estimate_number|GET|/invoices/estimate/number/generate|invoices/estimate.readonly|Sub-Account|Generate estimate number|generate_number
invoice|estimate|list_estimates|GET|/invoices/estimate/list|invoices/estimate.readonly|Sub-Account|List estimates|list
invoice|estimate|get_estimate_template|GET|/invoices/estimate/template|invoices/estimate.readonly|Sub-Account|Get estimate template|get_template
invoice|estimate|preview_estimate_template|GET|/invoices/estimate/template/preview|invoices/estimate.readonly|Sub-Account|Preview estimate template|preview_template
invoice|estimate|create_estimate|POST|/invoices/estimate|invoices/estimate.write|Sub-Account|Create estimate|create
invoice|estimate|send_estimate|POST|/invoices/estimate/:estimateId/send|invoices/estimate.write|Sub-Account|Send estimate|send
invoice|estimate|convert_estimate_to_invoice|POST|/invoices/estimate/:estimateId/invoice|invoices/estimate.write|Sub-Account|Convert estimate to invoice|convert_to_invoice
invoice|estimate|create_estimate_template|POST|/invoices/estimate/template|invoices/estimate.write|Sub-Account|Create estimate template|create_template
invoice|estimate|update_estimate|PUT|/invoices/estimate/:estimateId|invoices/estimate.write|Sub-Account|Update estimate|update
invoice|estimate|update_estimate_template|PUT|/invoices/estimate/template/:templateId|invoices/estimate.write|Sub-Account|Update estimate template|update_template
invoice|estimate|patch_last_visited_at|PATCH|/invoices/estimate/stats/last-visited-at|invoices/estimate.write|Sub-Account|Patch last visited at|patch_last_visited_at
invoice|estimate|delete_estimate|DELETE|/invoices/estimate/:estimateId|invoices/estimate.write|Sub-Account|Delete estimate|delete
invoice|estimate|delete_estimate_template|DELETE|/invoices/estimate/template/:templateId|invoices/estimate.write|Sub-Account|Delete estimate template|delete_template

# Trigger Links
trigger_links|trigger_links|list_trigger_links|GET|/links/|links.readonly|Sub-Account|List trigger links|list
trigger_links|trigger_links|create_trigger_link|POST|/links/|links.write|Sub-Account|Create trigger link|create
trigger_links|trigger_links|update_trigger_link|PUT|/links/:linkId|links.write|Sub-Account|Update trigger link|update
trigger_links|trigger_links|delete_trigger_link|DELETE|/links/:linkId|links.write|Sub-Account|Delete trigger link|delete

# Sub-Account formerly Location
sub_account|sub_account|get_location|GET|/locations/:locationId|locations.readonly|Sub-Account,Agency|Get location|get
sub_account|search|search_locations|GET|/locations/search|locations.readonly|Sub-Account,Agency|Search locations|search
sub_account|timezone|list_timezones|GET|/locations/timeZones|locations.readonly|Sub-Account|List timezones|timezones
sub_account|sub_account|create_location|POST|/locations/|locations.write|Agency|Create location|create
sub_account|sub_account|update_location|PUT|/locations/:locationId|locations.write|Agency|Update location|update
sub_account|sub_account|delete_location|DELETE|/locations/:locationId|locations.write|Agency|Delete location|delete
sub_account|custom_value|list_custom_values|GET|/locations/:locationId/customValues|locations/customValues.readonly|Sub-Account|List custom values|list
sub_account|custom_value|get_custom_value|GET|/locations/:locationId/customValues/:id|locations/customValues.readonly|Sub-Account|Get custom value|get
sub_account|custom_value|create_custom_value|POST|/locations/:locationId/customValues|locations/customValues.write|Sub-Account|Create custom value|create
sub_account|custom_value|update_custom_value|PUT|/locations/:locationId/customValues/:id|locations/customValues.write|Sub-Account|Update custom value|update
sub_account|custom_value|delete_custom_value|DELETE|/locations/:locationId/customValues/:id|locations/customValues.write|Sub-Account|Delete custom value|delete
sub_account|custom_field|list_custom_fields|GET|/locations/:locationId/customFields|locations/customFields.readonly|Sub-Account|List custom fields|list
sub_account|custom_field|get_custom_field|GET|/locations/:locationId/customFields/:id|locations/customFields.readonly|Sub-Account|Get custom field|get
sub_account|custom_field|create_custom_field|POST|/locations/:locationId/customFields|locations/customFields.write|Sub-Account|Create custom field|create
sub_account|custom_field|update_custom_field|PUT|/locations/:locationId/customFields/:id|locations/customFields.write|Sub-Account|Update custom field|update
sub_account|custom_field|delete_custom_field|DELETE|/locations/:locationId/customFields/:id|locations/customFields.write|Sub-Account|Delete custom field|delete
sub_account|tags|list_tags|GET|/locations/:locationId/tags|locations/tags.readonly|Sub-Account|List location tags|list
sub_account|tags|get_tag|GET|/locations/:locationId/tags/:tagId|locations/tags.readonly|Sub-Account|Get location tag|get
sub_account|tags|create_tag|POST|/locations/:locationId/tags/|locations/tags.write|Sub-Account|Create location tag|create
sub_account|tags|update_tag|PUT|/locations/:locationId/tags/:tagId|locations/tags.write|Sub-Account|Update location tag|update
sub_account|tags|delete_tag|DELETE|/locations/:locationId/tags/:tagId|locations/tags.write|Sub-Account|Delete location tag|delete
sub_account|template|list_templates|GET|/locations/:locationId/templates|locations/templates.readonly|Sub-Account|List location templates|list
sub_account|tasks_search|search_tasks|POST|/locations/:locationId/tasks/search|locations/tasks.readonly|Sub-Account|Search tasks|search

# Media Storage
media_storage|medias|list_files|GET|/medias/files|medias.readonly|Sub-Account|List media files|list
media_storage|medias|upload_file|POST|/medias/upload-file|medias.write|Sub-Account|Upload media file|upload
media_storage|medias|delete_file|DELETE|/medias/:fileId|medias.write|Sub-Account|Delete media file|delete

# Developer marketplace
developer_marketplace|app_management|get_app_installations|GET|/marketplace/app/:appId/installations|marketplace-installer-details.readonly|Sub-Account,Agency|Get app installation details|installations
developer_marketplace|app_management|delete_app_installation|DELETE|/marketplace/app/:appId/installations|oauth.write|Sub-Account,Agency|Delete app installation|delete_installation
developer_marketplace|wallet_charges|list_charges|GET|/marketplace/billing/charges|charges.readonly|Sub-Account|List wallet charges|list
developer_marketplace|wallet_charges|get_charge|GET|/marketplace/billing/charges/:chargeId|charges.readonly|Sub-Account|Get wallet charge|get
developer_marketplace|wallet_charges|has_funds|GET|/marketplace/billing/charges/has-funds|charges.readonly|Sub-Account|Check wallet funds|has_funds
developer_marketplace|wallet_charges|create_charge|POST|/marketplace/billing/charges|charges.write|Sub-Account|Create wallet charge|create
developer_marketplace|wallet_charges|delete_charge|DELETE|/marketplace/billing/charges/:chargeId|charges.write|Sub-Account|Delete wallet charge|delete

# Blogs
blogs|posts|create_post|POST|/blogs/posts|blogs/post.write|Sub-Account|Create blog post|create
blogs|posts|update_post|PUT|/blogs/posts/:postId|blogs/post-update.write|Sub-Account|Update blog post|update
blogs|posts|check_slug|GET|/blogs/posts/url-slug-exists|blogs/check-slug.readonly|Sub-Account|Check blog post slug|check_slug
blogs|categories|list_categories|GET|/blogs/categories|blogs/category.readonly|Sub-Account|List blog categories|list
blogs|authors|list_authors|GET|/blogs/authors|blogs/author.readonly|Sub-Account|List blog authors|list

# Funnels
funnels|redirect|list_redirects|GET|/funnels/lookup/redirect/list|funnels/redirect.readonly|Sub-Account|List funnel redirects|list
funnels|redirect|create_redirect|POST|/funnels/lookup/redirect|funnels/redirect.write|Sub-Account|Create funnel redirect|create
funnels|redirect|delete_redirect|DELETE|/funnels/lookup/redirect/:id|funnels/redirect.write|Sub-Account|Delete funnel redirect|delete
funnels|redirect|update_redirect|PATCH|/funnels/lookup/redirect/:id|funnels/redirect.write|Sub-Account|Update funnel redirect|update
funnels|funnel|get_pages|GET|/funnels/page|funnels/page.readonly|Sub-Account|Get funnel pages|pages
funnels|funnel|list_funnels|GET|/funnels/funnel/list|funnels/funnel.readonly|Sub-Account|List funnels|list
funnels|funnel|get_page_count|GET|/funnels/page/count|funnels/pagecount.readonly|Sub-Account|Get funnel page count|page_count

# Opportunities
opportunities|search|search_opportunities|GET|/opportunities/search|opportunities.readonly|Sub-Account|Search opportunities|search,list
opportunities|opportunities|get_opportunity|GET|/opportunities/:id|opportunities.readonly|Sub-Account|Get opportunity|get
opportunities|opportunities|delete_opportunity|DELETE|/opportunities/:id|opportunities.write|Sub-Account|Delete opportunity|delete
opportunities|opportunities|update_status|PUT|/opportunities/:id/status|opportunities.write|Sub-Account|Update opportunity status|update_status
opportunities|opportunities|create_opportunity|POST|/opportunities|opportunities.write|Sub-Account|Create opportunity|create
opportunities|opportunities|update_opportunity|PUT|/opportunities/:id|opportunities.write|Sub-Account|Update opportunity|update
opportunities|pipelines|get_pipelines|GET|/opportunities/pipelines|opportunities.readonly|Sub-Account|Get pipelines|list

# Payments
payments|integrations|get_whitelabel_provider|GET|/payments/integrations/provider/whitelabel|payments/integration.readonly|Sub-Account|Get whitelabel payment provider|get
payments|integrations|create_whitelabel_provider|POST|/payments/integrations/provider/whitelabel|payments/integration.write|Sub-Account|Create whitelabel payment provider|create
payments|orders|list_orders|GET|/payments/orders/|payments/orders.readonly|Sub-Account|List orders|list
payments|orders|get_order|GET|/payments/orders/:orderId|payments/orders.readonly|Sub-Account|Get order|get
payments|order_fulfillments|list_fulfillments|GET|/payments/orders/:orderId/fulfillments|payments/orders.readonly|Sub-Account|List order fulfillments|list
payments|order_fulfillments|create_fulfillment|POST|/payments/orders/:orderId/fulfillments|payments/orders.write|Sub-Account|Create order fulfillment|create
payments|transactions|list_transactions|GET|/payments/transactions/|payments/transactions.readonly|Sub-Account|List transactions|list
payments|transactions|get_transaction|GET|/payments/transactions/:transactionId|payments/transactions.readonly|Sub-Account|Get transaction|get
payments|subscriptions|list_subscriptions|GET|/payments/subscriptions/|payments/subscriptions.readonly|Sub-Account|List subscriptions|list
payments|subscriptions|get_subscription|GET|/payments/subscriptions/:subscriptionId|payments/subscriptions.readonly|Sub-Account|Get subscription|get
payments|coupons|list_coupons|GET|/payments/coupon/list|payments/coupons.readonly|Sub-Account|List coupons|list
payments|coupons|get_coupon|GET|/payments/coupon|payments/coupons.readonly|Sub-Account|Get coupon|get
payments|coupons|create_coupon|POST|/payments/coupon|payments/coupons.write|Sub-Account|Create coupon|create
payments|coupons|update_coupon|PUT|/payments/coupon|payments/coupons.write|Sub-Account|Update coupon|update
payments|coupons|delete_coupon|DELETE|/payments/coupon|payments/coupons.write|Sub-Account|Delete coupon|delete
payments|custom_provider|get_connect_url|GET|/payments/custom-provider/connect|payments/custom-provider.readonly|Sub-Account|Get custom provider connect URL|connect_url
payments|custom_provider|create_provider|POST|/payments/custom-provider/provider|payments/custom-provider.write|Sub-Account|Create custom payment provider|create
payments|custom_provider|connect|POST|/payments/custom-provider/connect|payments/custom-provider.write|Sub-Account|Connect custom provider|connect
payments|custom_provider|disconnect|POST|/payments/custom-provider/disconnect|payments/custom-provider.write|Sub-Account|Disconnect custom provider|disconnect
payments|custom_provider|update_capabilities|PUT|/payments/custom-provider/capabilities|payments/custom-provider.write|Sub-Account|Update provider capabilities|capabilities
payments|custom_provider|delete_provider|DELETE|/payments/custom-provider/provider|payments/custom-provider.write|Sub-Account|Delete custom provider|delete

# Products
products|products|list_products|GET|/products/|products.readonly|Sub-Account|List products|list
products|products|get_product|GET|/products/:productId|products.readonly|Sub-Account|Get product|get
products|products|create_product|POST|/products/|products.write|Sub-Account|Create product|create
products|products|update_product|PUT|/products/:productId|products.write|Sub-Account|Update product|update
products|products|delete_product|DELETE|/products/:productId|products.write|Sub-Account|Delete product|delete
products|products|bulk_update_products|POST|/products/bulk-update|products.write|Sub-Account|Bulk update products|bulk_update
products|store|get_store_stats|GET|/products/store/:storeId/stats|products.readonly|Sub-Account|Get product store stats|stats
products|store|create_store_product|POST|/products/store/:storeId|products.write|Sub-Account|Create store product|create
products|reviews|list_reviews|GET|/products/reviews|products.readonly|Sub-Account|List reviews|list
products|reviews|count_reviews|GET|/products/reviews/count|products.readonly|Sub-Account|Count reviews|count
products|reviews|bulk_update_reviews|POST|/products/reviews/bulk-update|products.write|Sub-Account|Bulk update reviews|bulk_update
products|reviews|update_review|PUT|/products/reviews/:reviewId|products.write|Sub-Account|Update review|update
products|reviews|delete_review|DELETE|/products/reviews/:reviewId|products.write|Sub-Account|Delete review|delete
products|prices|list_prices|GET|/products/:productId/price/|products/prices.readonly|Sub-Account|List product prices|list
products|prices|get_price|GET|/products/:productId/price/:priceId|products/prices.readonly|Sub-Account|Get product price|get
products|prices|create_price|POST|/products/:productId/price/|products/prices.write|Sub-Account|Create product price|create
products|prices|update_price|PUT|/products/:productId/price/:priceId|products/prices.write|Sub-Account|Update product price|update
products|prices|delete_price|DELETE|/products/:productId/price/:priceId|products/prices.write|Sub-Account|Delete product price|delete
products|collections|list_collections|GET|/products/collections|products/collection.readonly|Sub-Account|List collections|list
products|collections|get_collection|GET|/products/collections/:collectionId|products/collection.readonly|Sub-Account|Get collection|get
products|collections|create_collection|POST|/products/collections|products/collection.write|Sub-Account|Create collection|create
products|collections|update_collection|PUT|/products/collections/:collectionId|products/collection.write|Sub-Account|Update collection|update
products|collections|delete_collection|DELETE|/products/collections/:collectionId|products/collection.write|Sub-Account|Delete collection|delete

# SaaS
saas|saas|update_saas_subscription|PUT|/update-saas-subscription/:locationId|saas/location.write|Agency|Update SaaS subscription|update_subscription
saas|saas|enable_saas|POST|/enable-saas/:locationId|saas/location.write|Sub-Account,Agency|Enable SaaS|enable
saas|saas|list_locations|GET|/locations|saas/location.read|Sub-Account,Agency|List SaaS locations|locations
saas|saas|bulk_disable_saas|POST|/bulk-disable-saas/:companyId|saas/company.write|Sub-Account,Agency|Bulk disable SaaS|bulk_disable

# Snapshots
snapshots|snapshots|list_snapshots|GET|/snapshots|snapshots.readonly|Agency|List snapshots|list
snapshots|snapshots|get_snapshot_status|GET|/snapshots/snapshot-status/:snapshotId|snapshots.readonly|Agency|Get snapshot status|status
snapshots|snapshots|get_location_snapshot_status|GET|/snapshots/snapshot-status/:snapshotId/location/:locationId|snapshots.readonly|Agency|Get location snapshot status|location_status
snapshots|snapshots|create_share_link|POST|/snapshots/share/link|snapshots.write|Agency|Create snapshot share link|share_link

# Social Planner
social_planner|account|get_accounts|GET|/social-media-posting/:locationId/accounts|socialplanner/account.readonly|Sub-Account|Get list of accounts and groups|list
social_planner|account|delete_account|DELETE|/social-media-posting/:locationId/accounts/:id|socialplanner/account.write|Sub-Account|Delete account|delete
social_planner|csv|list_csv|GET|/social-media-posting/:locationId/csv|socialplanner/csv.readonly|Sub-Account|List CSVs|list
social_planner|csv|get_csv|GET|/social-media-posting/:locationId/csv/:id|socialplanner/csv.readonly|Sub-Account|Get CSV|get
social_planner|csv|create_csv|POST|/social-media-posting/:locationId/csv|socialplanner/csv.write|Sub-Account|Create CSV|create
social_planner|csv|set_accounts|POST|/social-media-posting/:locationId/set-accounts|socialplanner/csv.write|Sub-Account|Set accounts|set_accounts
social_planner|csv|delete_csv|DELETE|/social-media-posting/:locationId/csv/:id|socialplanner/csv.write|Sub-Account|Delete CSV|delete
social_planner|csv|update_csv|PATCH|/social-media-posting/:locationId/csv/:id|socialplanner/csv.write|Sub-Account|Update CSV|update
social_planner|csv|delete_csv_post|DELETE|/social-media-posting/:locationId/csv/:csvId/post/:postId|socialplanner/csv.write|Sub-Account|Delete CSV post|delete_post
social_planner|category|list_categories|GET|/social-media-posting/:locationId/categories|socialplanner/category.readonly|Sub-Account|List categories|list
social_planner|category|get_category|GET|/social-media-posting/:locationId/categories/:id|socialplanner/category.readonly|Sub-Account|Get category|get
social_planner|oauth_google|start_google_oauth|GET|/social-media-posting/oauth/google/start|socialplanner/oauth.readonly|Sub-Account|Start Google OAuth|start
social_planner|oauth_google|get_google_locations|GET|/social-media-posting/oauth/:locationId/google/locations/:accountId|socialplanner/oauth.readonly|Sub-Account|Get Google locations|get_locations
social_planner|oauth_google|set_google_locations|POST|/social-media-posting/oauth/:locationId/google/locations/:accountId|socialplanner/oauth.write|Sub-Account|Set Google business locations|set_locations
social_planner|oauth_facebook|start_facebook_oauth|GET|/social-media-posting/oauth/facebook/start|socialplanner/oauth.readonly|Sub-Account|Start Facebook OAuth|start
social_planner|oauth_facebook|get_facebook_accounts|GET|/social-media-posting/oauth/:locationId/facebook/accounts/:accountId|socialplanner/oauth.readonly|Sub-Account|Get Facebook accounts|get_accounts
social_planner|oauth_facebook|set_facebook_accounts|POST|/social-media-posting/oauth/:locationId/facebook/accounts/:accountId|socialplanner/oauth.write|Sub-Account|Set Facebook accounts|set_accounts
social_planner|oauth_instagram|start_instagram_oauth|GET|/social-media-posting/oauth/instagram/start|socialplanner/oauth.readonly|Sub-Account|Start Instagram OAuth|start
social_planner|oauth_instagram|get_instagram_accounts|GET|/social-media-posting/oauth/:locationId/instagram/accounts/:accountId|socialplanner/oauth.readonly|Sub-Account|Get Instagram accounts|get_accounts
social_planner|oauth_instagram|set_instagram_accounts|POST|/social-media-posting/oauth/:locationId/instagram/accounts/:accountId|socialplanner/oauth.write|Sub-Account|Set Instagram accounts|set_accounts
social_planner|oauth_linkedin|start_linkedin_oauth|GET|/social-media-posting/oauth/linkedin/start|socialplanner/oauth.readonly|Sub-Account|Start LinkedIn OAuth|start
social_planner|oauth_linkedin|get_linkedin_accounts|GET|/social-media-posting/oauth/:locationId/linkedin/accounts/:accountId|socialplanner/oauth.readonly|Sub-Account|Get LinkedIn accounts|get_accounts
social_planner|oauth_linkedin|set_linkedin_accounts|POST|/social-media-posting/oauth/:locationId/linkedin/accounts/:accountId|socialplanner/oauth.write|Sub-Account|Set LinkedIn accounts|set_accounts
social_planner|oauth_tiktok|start_tiktok_oauth|GET|/social-media-posting/oauth/tiktok/start|socialplanner/oauth.readonly|Sub-Account|Start TikTok OAuth|start
social_planner|oauth_tiktok|get_tiktok_accounts|GET|/social-media-posting/oauth/:locationId/tiktok/accounts/:accountId|socialplanner/oauth.readonly|Sub-Account|Get TikTok accounts|get_accounts
social_planner|oauth_tiktok|set_tiktok_accounts|POST|/social-media-posting/oauth/:locationId/tiktok/accounts/:accountId|socialplanner/oauth.write|Sub-Account|Set TikTok accounts|set_accounts
social_planner|oauth_tiktok|start_tiktok_business_oauth|GET|/social-media-posting/oauth/tiktok-business/start|socialplanner/oauth.readonly|Sub-Account|Start TikTok Business OAuth|start_business
social_planner|oauth_tiktok|get_tiktok_business_accounts|GET|/social-media-posting/oauth/:locationId/tiktok-business/accounts/:accountId|socialplanner/oauth.readonly|Sub-Account|Get TikTok Business accounts|get_business_accounts
social_planner|oauth_twitter|start_twitter_oauth|GET|/social-media-posting/oauth/twitter/start|socialplanner/oauth.readonly|Sub-Account|Start Twitter OAuth|start
social_planner|oauth_twitter|get_twitter_accounts|GET|/social-media-posting/oauth/:locationId/twitter/accounts/:accountId|socialplanner/oauth.readonly|Sub-Account|Get Twitter accounts|get_accounts
social_planner|oauth_twitter|set_twitter_accounts|POST|/social-media-posting/oauth/:locationId/twitter/accounts/:accountId|socialplanner/oauth.write|Sub-Account|Set Twitter accounts|set_accounts
social_planner|post|get_post|GET|/social-media-posting/:locationId/posts/:id|socialplanner/post.readonly|Sub-Account|Get post|get
social_planner|post|get_posts|POST|/social-media-posting/:locationId/posts/list|socialplanner/post.readonly|Sub-Account|Get posts|list
social_planner|post|create_post|POST|/social-media-posting/:locationId/posts|socialplanner/post.write|Sub-Account|Create post|create
social_planner|post|edit_post|PUT|/social-media-posting/:locationId/posts/:id|socialplanner/post.write|Sub-Account|Edit post|update,edit
social_planner|post|delete_post|DELETE|/social-media-posting/:locationId/posts/:id|socialplanner/post.write|Sub-Account|Delete post|delete
social_planner|post|bulk_delete_posts|PATCH|/social-media-posting/:locationId/posts/:id|socialplanner/post.write|Sub-Account|Bulk delete social planner posts|bulk_delete
social_planner|tag|list_tags|GET|/social-media-posting/:locationId/tags|socialplanner/tag.readonly|Sub-Account|List tags|list
social_planner|tag|get_tag_details|POST|/social-media-posting/:locationId/tags/details|socialplanner/tag.readonly|Sub-Account|Get tag details|details
social_planner|statistics|get_statistics|POST|/social-media-posting/statistics|socialplanner/statistics.readonly|Sub-Account|Get social planner statistics|statistics

# Surveys
surveys|surveys|list_surveys|GET|/surveys/|surveys.readonly|Sub-Account|List surveys|list
surveys|surveys|list_survey_submissions|GET|/surveys/submissions|surveys.readonly|Sub-Account|List survey submissions|submissions

# Users
users|users|list_users|GET|/users/|users.readonly|Sub-Account,Agency|List users|list
users|users|get_user|GET|/users/:userId|users.readonly|Sub-Account,Agency|Get user|get
users|users|create_user|POST|/users/|users.write|Sub-Account,Agency|Create user|create
users|users|delete_user|DELETE|/users/:userId|users.write|Sub-Account,Agency|Delete user|delete
users|users|update_user|PUT|/users/:userId|users.write|Sub-Account,Agency|Update user|update

# Workflows
workflows|workflows|list_workflows|GET|/workflows/|workflows.readonly|Sub-Account|List workflows|list

# LC Email
lc_email|email_verification|verify_email|POST|/email-isv/verify|email-isv.write|Sub-Account|Verify LC email|verify

# Custom menus
custom_menus|custom_menu_links|get_custom_menu|GET|/custom-menus/:customMenuId|custom-menu-link.readonly|Agency|Get custom menu|get
custom_menus|custom_menu_links|list_custom_menus|GET|/custom-menus/|custom-menu-link.readonly|Agency|List custom menus|list
custom_menus|custom_menu_links|create_custom_menu|POST|/custom-menus/|custom-menu-link.write|Agency|Create custom menu|create
custom_menus|custom_menu_links|update_custom_menu|PUT|/custom-menus/:customMenuId|custom-menu-link.write|Agency|Update custom menu|update
custom_menus|custom_menu_links|delete_custom_menu|DELETE|/custom-menus/:customMenuId|custom-menu-link.write|Agency|Delete custom menu|delete

# Voice AI
voice_ai|dashboard|list_call_logs|GET|/voice-ai/dashboard/call-logs|voice-ai-dashboard.readonly|Sub-Account|List Voice AI call logs|list
voice_ai|dashboard|get_call_log|GET|/voice-ai/dashboard/call-logs/:callId|voice-ai-dashboard.readonly|Sub-Account|Get Voice AI call log|get
voice_ai|agents|list_agents|GET|/voice-ai/agents|voice-ai-agents.readonly|Sub-Account|List Voice AI agents|list
voice_ai|agents|get_agent|GET|/voice-ai/agents/:agentId|voice-ai-agents.readonly|Sub-Account|Get Voice AI agent|get
voice_ai|agents|create_agent|POST|/voice-ai/agents|voice-ai-agents.write|Sub-Account|Create Voice AI agent|create
voice_ai|agents|update_agent|PATCH|/voice-ai/agents/:agentId|voice-ai-agents.write|Sub-Account|Update Voice AI agent|update
voice_ai|agents|delete_agent|DELETE|/voice-ai/agents/:agentId|voice-ai-agents.write|Sub-Account|Delete Voice AI agent|delete
voice_ai|actions|get_action|GET|/voice-ai/actions/:actionId|voice-ai-agent-goals.readonly|Sub-Account|Get Voice AI action|get
voice_ai|actions|create_action|POST|/voice-ai/actions|voice-ai-agent-goals.write|Sub-Account|Create Voice AI action|create
voice_ai|actions|update_action|PUT|/voice-ai/actions/:actionId|voice-ai-agent-goals.write|Sub-Account|Update Voice AI action|update
voice_ai|actions|delete_action|DELETE|/voice-ai/actions/:actionId/agent/:agentId|voice-ai-agent-goals.write|Sub-Account|Delete Voice AI action|delete

# Proposals
proposals|documents|list_documents|GET|/proposals/document|documents_contracts/list.readonly|Sub-Account,Agency|List proposal documents|list
proposals|documents|send_document_link|POST|/proposals/document/send|documents_contracts/sendlink.write|Sub-Account,Agency|Send proposal document link|send
proposals|templates|list_templates|GET|/proposals/templates|documents_contracts_templates/list.readonly|Sub-Account,Agency|List proposal templates|list
proposals|templates|send_template_link|POST|/proposals/templates/send|documents_contracts_templates/sendlink.write|Sub-Account,Agency|Send proposal template link|send

# Knowledge Base
knowledge_base|knowledge_base|list_knowledge_bases|GET|/knowledge-bases/|knowledge-base.readonly|Sub-Account|List knowledge bases|list
knowledge_base|knowledge_base|get_knowledge_base|GET|/knowledge-bases/:knowledgeBaseId|knowledge-base.readonly|Sub-Account|Get knowledge base|get
knowledge_base|knowledge_base|create_knowledge_base|POST|/knowledge-bases/|knowledge-base.write|Sub-Account|Create knowledge base|create
knowledge_base|knowledge_base|update_knowledge_base|PUT|/knowledge-bases/:knowledgeBaseId|knowledge-base.write|Sub-Account|Update knowledge base|update
knowledge_base|knowledge_base|delete_knowledge_base|DELETE|/knowledge-bases/:knowledgeBaseId|knowledge-base.write|Sub-Account|Delete knowledge base|delete
knowledge_base|web_crawler|list_trained_page_links|GET|/knowledge-bases/crawler|knowledge-base.readonly|Sub-Account|List trained page links|list
knowledge_base|web_crawler|start_crawl|POST|/knowledge-bases/crawler|knowledge-base.write|Sub-Account|Start website crawl|crawl
knowledge_base|web_crawler|delete_trained_pages|DELETE|/knowledge-bases/crawler|knowledge-base.write|Sub-Account|Delete trained pages|delete
knowledge_base|web_crawler|get_crawling_status|GET|/knowledge-bases/crawler/status|knowledge-base.readonly|Sub-Account|Get crawler status|status
knowledge_base|web_crawler|train_discovered_pages|POST|/knowledge-bases/crawler/train|knowledge-base.write|Sub-Account|Train discovered pages|train
knowledge_base|faqs|list_faqs|GET|/knowledge-bases/faqs|knowledge-base.readonly|Sub-Account|List FAQs|list
knowledge_base|faqs|create_faq|POST|/knowledge-bases/faqs|knowledge-base.write|Sub-Account|Create FAQ|create
knowledge_base|faqs|update_faq|PUT|/knowledge-bases/faqs/:id|knowledge-base.write|Sub-Account|Update FAQ|update
knowledge_base|faqs|delete_faq|DELETE|/knowledge-bases/faqs/:id|knowledge-base.write|Sub-Account|Delete FAQ|delete

# Conversation AI
conversation_ai|actions|attach_action_to_agent|POST|/conversation-ai/agents/:agentId/actions|conversation-ai/actions.write|Sub-Account|Attach action to agent|create,attach
conversation_ai|actions|list_actions_for_agent|GET|/conversation-ai/agents/:agentId/actions/list|conversation-ai/actions.readonly|Sub-Account|List actions for an agent|list
conversation_ai|actions|get_action_by_id|GET|/conversation-ai/agents/:agentId/actions/:actionId|conversation-ai/actions.readonly|Sub-Account|Get action by id|get
conversation_ai|actions|update_action|PUT|/conversation-ai/agents/:agentId/actions/:actionId|conversation-ai/actions.write|Sub-Account|Update action|update
conversation_ai|actions|remove_action_from_agent|DELETE|/conversation-ai/agents/:agentId/actions/:actionId|conversation-ai/actions.write|Sub-Account|Remove action from agent|delete,remove
conversation_ai|actions|update_followup_settings|PATCH|/conversation-ai/agents/:agentId/followup-settings|conversation-ai/actions.write|Sub-Account|Update followup settings|followup
conversation_ai|agents|create_agent|POST|/conversation-ai/agents|conversation-ai/agents.write|Sub-Account|Create Conversation AI agent|create
conversation_ai|agents|search_agents|GET|/conversation-ai/agents/search|conversation-ai/agents.readonly|Sub-Account|Search Conversation AI agents|search,list
conversation_ai|agents|update_agent|PUT|/conversation-ai/agents/:agentId|conversation-ai/agents.write|Sub-Account|Update Conversation AI agent|update
conversation_ai|agents|get_agent|GET|/conversation-ai/agents/:agentId|conversation-ai/agents.readonly|Sub-Account|Get Conversation AI agent|get
conversation_ai|agents|delete_agent|DELETE|/conversation-ai/agents/:agentId|conversation-ai/agents.write|Sub-Account|Delete Conversation AI agent|delete
conversation_ai|generations|get_generation_details|GET|/conversation-ai/generations|conversation-ai/generations.readonly|Sub-Account|Get generation details|get

# Phone System
phone_system|phone_numbers|list_phone_numbers|GET|/phone-system/numbers/location/:locationId|phonenumbers.read|Sub-Account|List phone numbers|list
phone_system|number_pools|list_number_pools|GET|/phone-system/number-pools|numberpools.read|Sub-Account|List number pools|list

# Store
store|shipping_zone|create_shipping_zone|POST|/store/shipping-zone|store/shipping.write|Sub-Account|Create shipping zone|create
store|shipping_zone|list_shipping_zones|GET|/store/shipping-zone|store/shipping.readonly|Sub-Account|List shipping zones|list
store|shipping_zone|get_shipping_zone|GET|/store/shipping-zone/:shippingZoneId|store/shipping.readonly|Sub-Account|Get shipping zone|get
store|shipping_zone|update_shipping_zone|PUT|/store/shipping-zone/:shippingZoneId|store/shipping.write|Sub-Account|Update shipping zone|update
store|shipping_zone|delete_shipping_zone|DELETE|/store/shipping-zone/:shippingZoneId|store/shipping.write|Sub-Account|Delete shipping zone|delete
store|shipping_zone|get_available_shipping_rates|POST|/store/shipping-zone/shipping-rates|store/shipping.readonly|Sub-Account|Get available shipping rates|available_rates
store|shipping_zone_rates|create_shipping_rate|POST|/store/shipping-zone/:shippingZoneId/shipping-rate|store/shipping.write|Sub-Account|Create shipping rate|create
store|shipping_zone_rates|list_shipping_rates|GET|/store/shipping-zone/:shippingZoneId/shipping-rate|store/shipping.readonly|Sub-Account|List shipping rates|list
store|shipping_zone_rates|get_shipping_rate|GET|/store/shipping-zone/:shippingZoneId/shipping-rate/:shippingRateId|store/shipping.readonly|Sub-Account|Get shipping rate|get
store|shipping_zone_rates|update_shipping_rate|PUT|/store/shipping-zone/:shippingZoneId/shipping-rate/:shippingRateId|store/shipping.write|Sub-Account|Update shipping rate|update
store|shipping_zone_rates|delete_shipping_rate|DELETE|/store/shipping-zone/:shippingZoneId/shipping-rate/:shippingRateId|store/shipping.write|Sub-Account|Delete shipping rate|delete
store|shipping_carrier|create_shipping_carrier|POST|/store/shipping-carrier|store/shipping.write|Sub-Account|Create shipping carrier|create
store|shipping_carrier|list_shipping_carriers|GET|/store/shipping-carrier|store/shipping.readonly|Sub-Account|List shipping carriers|list
store|shipping_carrier|get_shipping_carrier|GET|/store/shipping-carrier/:shippingCarrierId|store/shipping.readonly|Sub-Account|Get shipping carrier|get
store|shipping_carrier|update_shipping_carrier|PUT|/store/shipping-carrier/:shippingCarrierId|store/shipping.write|Sub-Account|Update shipping carrier|update
store|shipping_carrier|delete_shipping_carrier|DELETE|/store/shipping-carrier/:shippingCarrierId|store/shipping.write|Sub-Account|Delete shipping carrier|delete
store|store_setting|create_or_update_store_settings|POST|/store/store-setting|store/settings.write|Sub-Account|Create or update store settings|create,update,upsert
store|store_setting|get_store_settings|GET|/store/store-setting|store/settings.readonly|Sub-Account|Get store settings|get

# AI Agent Studio
ai_agent_studio|agents|create_agent|POST|/agent-studio/agent|agent-studio/agents.write|Sub-Account|Create agent|create
ai_agent_studio|agents|list_agents|GET|/agent-studio/agent|agent-studio/agents.readonly|Sub-Account|List agents|list
ai_agent_studio|agents|update_agent_version|PATCH|/agent-studio/agent/versions/:versionId|agent-studio/agents.write|Sub-Account|Update agent version|update_version,update
ai_agent_studio|agents|update_agent_metadata|PATCH|/agent-studio/agent/:agentId|agent-studio/agents.write|Sub-Account|Update agent metadata|update_metadata
ai_agent_studio|agents|delete_agent|DELETE|/agent-studio/agent/:agentId|agent-studio/agents.write|Sub-Account|Delete agent|delete
ai_agent_studio|agents|get_agent|GET|/agent-studio/agent/:agentId|agent-studio/agents.readonly|Sub-Account|Get agent|get
ai_agent_studio|agents|promote_to_production|POST|/agent-studio/agent/versions/:versionId/publish|agent-studio/agents.write|Sub-Account|Promote to production|publish,promote
ai_agent_studio|agents|execute_agent|POST|/agent-studio/agent/:agentId/execute|agent-studio/agents.write|Sub-Account|Execute agent|execute
ai_agent_studio|agents|list_agents_deprecated|GET|/agent-studio/public-api/agents|agent-studio/agents.readonly|Sub-Account|Deprecated list agents|deprecated_list
ai_agent_studio|agents|get_agent_deprecated|GET|/agent-studio/public-api/agents/:agentId|agent-studio/agents.readonly|Sub-Account|Deprecated get agent|deprecated_get
ai_agent_studio|agents|execute_agent_deprecated|POST|/agent-studio/public-api/agents/:agentId/execute|agent-studio/agents.write|Sub-Account|Deprecated execute agent|deprecated_execute

# Affiliate Manager
affiliate_manager|affiliates|list_affiliates|GET|/affiliate-manager/:locationId/affiliates|affiliate-manager/affiliates.readonly|Sub-Account|List affiliates|list
affiliate_manager|affiliates|get_affiliate|GET|/affiliate-manager/:locationId/affiliates/:id|affiliate-manager/affiliates.readonly|Sub-Account|Get affiliate|get
affiliate_manager|payouts|list_payouts|GET|/affiliate-manager/:locationId/payouts|affiliate-manager/payouts.readonly|Sub-Account|List payouts|list
affiliate_manager|commissions|list_commissions|GET|/affiliate-manager/:locationId/commissions|affiliate-manager/commissions.readonly|Sub-Account|List commissions|list
'''


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="HighLevel universal API handler utility")
    parser.add_argument("--list-roots", action="store_true")
    parser.add_argument("--coverage", action="store_true")
    parser.add_argument("--refresh-registry", metavar="PATH", help="Crawl public docs and save refreshed registry JSON")
    parser.add_argument("--smoke-location", action="store_true", help="Call GET /locations/:locationId using env token")
    args = parser.parse_args()

    handler = HighLevelHandler.from_env()
    if args.refresh_registry:
        handler.refresh_registry_from_docs(save_to=args.refresh_registry)
        print(f"Saved registry with {len(handler.registry)} actions to {args.refresh_registry}")
    if args.list_roots:
        print(json.dumps(handler.registry.list_roots(), indent=2))
    if args.coverage:
        print(json.dumps(handler.registry.coverage_report(), indent=2))
    if args.smoke_location:
        print(json.dumps(handler.sub_account.sub_account.get_location(), indent=2))
