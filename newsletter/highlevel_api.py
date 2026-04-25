#!/usr/bin/env python3
"""
HighLevel-backed drop-in replacement for a Beehiiv newsletter wrapper.

This module preserves the original BeehiivClient method signatures so existing
call-sites can keep importing and calling the same methods, while the backing
implementation talks to HighLevel instead of Beehiiv.

Behavior mapping:
- Beehiiv "posts" -> HighLevel Email Campaigns V2
- Beehiiv subscribers -> HighLevel Contacts
- Beehiiv automations -> HighLevel Workflows (contact enrollment)

Why the local cache exists:
HighLevel's public Email Campaigns V2 docs expose create, list, update, delete,
schedule, and stats endpoints, but the public docs reviewed for this adapter do
not expose a dedicated "get campaign by id" page. To preserve one-for-one
compatibility, this adapter keeps a tiny local cache for campaigns it creates,
then merges cache data with live list results when you call get_post() or
list_posts().

Environment variables:
- HIGHLEVEL_BEARER_TOKEN / HIGHLEVEL_ACCESS_TOKEN / GHL_PIT
- HIGHLEVEL_LOCATION_ID / GHL_LOCATION_ID
- HIGHLEVEL_BASE_URL (optional, defaults to https://services.leadconnectorhq.com)
- HIGHLEVEL_API_VERSION (optional, defaults to 2021-07-28)
- HIGHLEVEL_FROM_NAME / HIGHLEVEL_FROM_EMAIL / HIGHLEVEL_REPLY_TO_EMAIL (optional)

Compatibility aliases:
- BEEHIIV_API_KEY -> HighLevel token fallback
- BEEHIIV_PUBLICATION_ID -> HighLevel locationId fallback
"""

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None


_env_path = Path(__file__).parent / ".env"
if load_dotenv:
    load_dotenv(_env_path)

BASE_URL = os.environ.get("HIGHLEVEL_BASE_URL", "https://services.leadconnectorhq.com").rstrip("/")
API_VERSION = os.environ.get("HIGHLEVEL_API_VERSION", "2021-07-28")
_NO_BODY = object()


class HighLevelApiError(RuntimeError):
    """Raised when HighLevel returns a non-success response."""

    def __init__(self, status: int, method: str, path: str, message: str, response_body: str = ""):
        self.status = status
        self.method = method
        self.path = path
        self.message = message
        self.response_body = response_body
        super().__init__(f"HighLevel API error {status} on {method} {path}: {message}")


class BeehiivClient:
    """
    Drop-in replacement for the original BeehiivClient.

    Preserved public method signatures:
        - create_draft
        - publish_post
        - schedule_post
        - create_scheduled_post
        - delete_post
        - get_post
        - list_posts
        - subscribe
        - enroll_in_automation
        - update_subscriber
        - get_subscriber
        - test_connection
    """

    def __init__(self):
        self.api_key = (
            os.environ.get("HIGHLEVEL_BEARER_TOKEN")
            or os.environ.get("HIGHLEVEL_ACCESS_TOKEN")
            or os.environ.get("HIGHLEVEL_PRIVATE_INTEGRATION_TOKEN")
            or os.environ.get("GHL_PIT")
            or os.environ.get("BEEHIIV_API_KEY")  # compatibility fallback
        )
        self.pub_id = (
            os.environ.get("HIGHLEVEL_LOCATION_ID")
            or os.environ.get("GHL_LOCATION_ID")
            or os.environ.get("BEEHIIV_PUBLICATION_ID")  # compatibility fallback
        )
        self.base_url = BASE_URL
        self.api_version = API_VERSION
        self.from_name = os.environ.get("HIGHLEVEL_FROM_NAME", "").strip()
        self.from_email = os.environ.get("HIGHLEVEL_FROM_EMAIL", "").strip()
        self.reply_to_email = os.environ.get("HIGHLEVEL_REPLY_TO_EMAIL", "").strip()
        self.cache_path = Path(
            os.environ.get(
                "HIGHLEVEL_NEWSLETTER_CACHE_PATH",
                str(Path(__file__).with_name(".highlevel_newsletter_cache.json")),
            )
        )

        if not self.api_key or not self.pub_id:
            raise RuntimeError(
                f"Missing HighLevel credentials. Ensure .env exists at {_env_path} "
                "with HIGHLEVEL_BEARER_TOKEN (or HIGHLEVEL_ACCESS_TOKEN / GHL_PIT) "
                "and HIGHLEVEL_LOCATION_ID. For easy drop-in migration, "
                "BEEHIIV_API_KEY and BEEHIIV_PUBLICATION_ID are also accepted as fallbacks."
            )

        self._custom_field_cache: Optional[Dict[str, str]] = None
        self._cache = self._load_cache()

    # -------------------------------------------------------------------------
    # Core HTTP helpers
    # -------------------------------------------------------------------------

    def _auth_header_value(self) -> str:
        token = self.api_key.strip()
        return token if token.lower().startswith("bearer ") else f"Bearer {token}"

    def _build_url(self, path: str, query: Optional[Dict[str, Any]] = None) -> str:
        path = path if path.startswith("/") else f"/{path}"
        url = f"{self.base_url}{path}"
        if query:
            clean_query = {k: v for k, v in query.items() if v is not None}
            if clean_query:
                url = f"{url}?{urllib.parse.urlencode(clean_query, doseq=True)}"
        return url

    def _request(
        self,
        method: str,
        path: str,
        body: Any = _NO_BODY,
        query: Optional[Dict[str, Any]] = None,
        extra_headers: Optional[Dict[str, str]] = None,
        retries: int = 3,
    ) -> Any:
        url = self._build_url(path, query=query)
        headers = {
            "Authorization": self._auth_header_value(),
            "Accept": "application/json",
            "Version": self.api_version,
        }
        if extra_headers:
            headers.update(extra_headers)

        data: Optional[bytes] = None
        if body is not _NO_BODY:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body if body is not None else {}).encode("utf-8")

        last_error: Optional[HighLevelApiError] = None
        for attempt in range(retries):
            req = urllib.request.Request(url, data=data, method=method.upper())
            for key, value in headers.items():
                req.add_header(key, value)

            try:
                with urllib.request.urlopen(req) as resp:
                    raw = resp.read().decode("utf-8")
                    if not raw.strip():
                        return {}
                    try:
                        return json.loads(raw)
                    except json.JSONDecodeError:
                        return {"raw": raw}
            except urllib.error.HTTPError as exc:
                error_body = exc.read().decode("utf-8") if exc.fp else ""
                message = error_body or exc.reason or "HTTP error"
                current = HighLevelApiError(exc.code, method.upper(), path, message, response_body=error_body)
                last_error = current

                if exc.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                    time.sleep((2 ** attempt) * 0.75)
                    continue
                raise current
            except urllib.error.URLError as exc:
                current = HighLevelApiError(0, method.upper(), path, str(exc.reason))
                last_error = current
                if attempt < retries - 1:
                    time.sleep((2 ** attempt) * 0.75)
                    continue
                raise current

        if last_error:
            raise last_error
        raise RuntimeError("Request failed unexpectedly")

    def _request_variants(
        self,
        method: str,
        path: str,
        bodies: Iterable[Any],
        query: Optional[Dict[str, Any]] = None,
        tolerate_statuses: Tuple[int, ...] = (400, 404, 405, 409, 422),
    ) -> Any:
        last_error: Optional[HighLevelApiError] = None
        for body in bodies:
            try:
                return self._request(method, path, body=body, query=query)
            except HighLevelApiError as exc:
                last_error = exc
                if exc.status not in tolerate_statuses:
                    raise
                continue

        if last_error:
            raise last_error
        raise RuntimeError("No request variants were provided")

    # -------------------------------------------------------------------------
    # Cache helpers
    # -------------------------------------------------------------------------

    def _load_cache(self) -> Dict[str, Any]:
        if self.cache_path.exists():
            try:
                return json.loads(self.cache_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"campaigns": {}}

    def _save_cache(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(self._cache, indent=2, sort_keys=True), encoding="utf-8")

    def _campaign_cache(self, campaign_id: str) -> Dict[str, Any]:
        return deepcopy(self._cache.get("campaigns", {}).get(campaign_id, {}))

    def _upsert_campaign_cache(self, campaign_id: str, values: Dict[str, Any]) -> None:
        campaigns = self._cache.setdefault("campaigns", {})
        current = campaigns.get(campaign_id, {})
        current.update(values)
        current["id"] = campaign_id
        current["updated_at"] = self._utcnow_iso()
        campaigns[campaign_id] = current
        self._save_cache()

    def _delete_campaign_cache(self, campaign_id: str) -> None:
        campaigns = self._cache.setdefault("campaigns", {})
        if campaign_id in campaigns:
            del campaigns[campaign_id]
            self._save_cache()

    # -------------------------------------------------------------------------
    # Generic response parsing helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _utcnow_iso() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _slugify(value: str) -> str:
        value = value.lower().strip()
        value = re.sub(r"[^a-z0-9]+", "-", value)
        value = re.sub(r"-{2,}", "-", value)
        return value.strip("-") or "untitled"

    @staticmethod
    def _first_non_empty(*values: Any) -> Any:
        for value in values:
            if value not in (None, "", [], {}, ()):
                return value
        return None

    def _extract_items(self, payload: Any) -> List[Dict[str, Any]]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]

        if not isinstance(payload, dict):
            return []

        candidate_lists = []
        for key in ("data", "items", "campaigns", "emails", "contacts", "results", "records"):
            value = payload.get(key)
            if isinstance(value, list):
                candidate_lists.append(value)
            elif isinstance(value, dict):
                for nested_key in ("data", "items", "campaigns", "emails", "contacts", "results", "records"):
                    nested = value.get(nested_key)
                    if isinstance(nested, list):
                        candidate_lists.append(nested)

        if candidate_lists:
            for items in candidate_lists:
                dict_items = [item for item in items if isinstance(item, dict)]
                if dict_items:
                    return dict_items

        if isinstance(payload, dict) and self._first_non_empty(payload.get("id"), payload.get("campaignId"), payload.get("contactId")):
            return [payload]

        return []

    def _extract_campaign_id(self, payload: Any) -> str:
        for item in self._extract_items(payload):
            campaign_id = self._first_non_empty(item.get("id"), item.get("campaignId"), item.get("_id"))
            if campaign_id:
                return str(campaign_id)

        if isinstance(payload, dict):
            for key in ("id", "campaignId", "_id"):
                if payload.get(key):
                    return str(payload[key])
            data = payload.get("data")
            if isinstance(data, dict):
                for key in ("id", "campaignId", "_id"):
                    if data.get(key):
                        return str(data[key])
        return ""

    def _extract_first_contact(self, payload: Any) -> Optional[Dict[str, Any]]:
        for item in self._extract_items(payload):
            if self._first_non_empty(item.get("id"), item.get("contactId"), item.get("_id")):
                return item

        if isinstance(payload, dict):
            for key in ("contact", "data", "result"):
                maybe = payload.get(key)
                if isinstance(maybe, dict) and self._first_non_empty(maybe.get("id"), maybe.get("contactId"), maybe.get("_id")):
                    return maybe
        return None

    def _extract_contact_id(self, payload: Any) -> str:
        contact = self._extract_first_contact(payload)
        if contact:
            return str(self._first_non_empty(contact.get("id"), contact.get("contactId"), contact.get("_id")))
        return ""

    def _normalize_campaign(self, raw: Optional[Dict[str, Any]], cached: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        raw = raw or {}
        cached = cached or {}

        campaign_id = str(self._first_non_empty(
            raw.get("id"),
            raw.get("campaignId"),
            raw.get("_id"),
            cached.get("id"),
        ) or "")

        title = self._first_non_empty(
            raw.get("name"),
            raw.get("title"),
            raw.get("campaignName"),
            cached.get("title"),
        )
        subject = self._first_non_empty(
            raw.get("subject"),
            raw.get("subjectLine"),
            cached.get("subject"),
        )
        preview = self._first_non_empty(
            raw.get("previewText"),
            raw.get("preview"),
            cached.get("preview"),
        )
        status = str(self._first_non_empty(
            raw.get("status"),
            raw.get("state"),
            cached.get("status"),
            "unknown",
        ))
        scheduled_at = self._first_non_empty(
            raw.get("scheduledAt"),
            raw.get("scheduleAt"),
            raw.get("sendAt"),
            raw.get("startAt"),
            cached.get("scheduled_at"),
        )

        return {
            "id": campaign_id,
            "post_id": campaign_id,
            "title": title,
            "subject": subject,
            "preview": preview,
            "html_body": self._first_non_empty(
                raw.get("html"),
                raw.get("htmlContent"),
                raw.get("body"),
                raw.get("content"),
                cached.get("html_body"),
            ),
            "content_tags": cached.get("content_tags", []),
            "subtitle": cached.get("subtitle", ""),
            "status": status,
            "scheduled_at": scheduled_at,
            "url": self._campaign_api_url(campaign_id) if campaign_id else "",
            "web_url": cached.get("web_url", ""),
            "raw": raw if raw else {},
        }

    def _campaign_api_url(self, campaign_id: str) -> str:
        return self._build_url(f"/emails/public/v2/locations/{self.pub_id}/campaigns/{campaign_id}")

    def _merge_live_and_cache_campaign(self, campaign_id: str, live: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        cached = self._campaign_cache(campaign_id)
        campaign = self._normalize_campaign(live, cached=cached)
        if campaign_id:
            self._upsert_campaign_cache(
                campaign_id,
                {
                    "title": campaign.get("title"),
                    "subject": campaign.get("subject"),
                    "preview": campaign.get("preview"),
                    "html_body": campaign.get("html_body"),
                    "status": campaign.get("status"),
                    "scheduled_at": campaign.get("scheduled_at"),
                    "url": campaign.get("url"),
                    "web_url": campaign.get("web_url"),
                    "content_tags": campaign.get("content_tags", []),
                    "subtitle": campaign.get("subtitle", ""),
                    "raw_last_seen": live or cached.get("raw_last_seen", {}),
                },
            )
        return campaign

    # -------------------------------------------------------------------------
    # Custom field helpers
    # -------------------------------------------------------------------------

    def _load_custom_field_name_map(self) -> Dict[str, str]:
        if self._custom_field_cache is not None:
            return self._custom_field_cache

        mapping: Dict[str, str] = {}
        try:
            resp = self._request("GET", f"/locations/{self.pub_id}/customFields")
            for item in self._extract_items(resp):
                field_id = self._first_non_empty(item.get("id"), item.get("_id"))
                names = [
                    item.get("name"),
                    item.get("fieldName"),
                    item.get("key"),
                    item.get("slug"),
                ]
                if field_id:
                    for name in names:
                        if name:
                            mapping[str(name).strip().lower()] = str(field_id)
        except Exception:
            pass

        self._custom_field_cache = mapping
        return mapping

    def _resolve_custom_field_id(self, name_or_id: str) -> Optional[str]:
        if not name_or_id:
            return None
        lower = name_or_id.strip().lower()
        mapping = self._load_custom_field_name_map()
        if lower in mapping:
            return mapping[lower]

        # If the caller already supplied an id, keep it.
        if re.fullmatch(r"[A-Za-z0-9_-]{8,}", name_or_id):
            return name_or_id
        return None

    def _translate_custom_fields(self, custom_fields: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        translated: List[Dict[str, Any]] = []
        for item in custom_fields or []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or item.get("id") or "").strip()
            value = item.get("value")
            field_id = self._resolve_custom_field_id(name)
            if field_id and value is not None:
                translated.append({"id": field_id, "value": value})
        return translated

    # -------------------------------------------------------------------------
    # Contact helpers
    # -------------------------------------------------------------------------

    def _find_contact_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        email = email.strip()

        # First try the dedicated duplicate-search endpoint using common query
        # parameters seen in similar HighLevel patterns.
        duplicate_queries = [
            {"locationId": self.pub_id, "email": email},
            {"email": email},
            {"locationId": self.pub_id, "query": email},
        ]
        for query in duplicate_queries:
            try:
                resp = self._request("GET", "/contacts/search/duplicate", query=query)
                contact = self._extract_first_contact(resp)
                if contact:
                    return contact
            except HighLevelApiError as exc:
                if exc.status not in (400, 404, 422):
                    raise

        # Then try advanced search with a few body variants because the public
        # docs expose the endpoint but not the full body shape in the static text.
        search_bodies = [
            {
                "locationId": self.pub_id,
                "pageLimit": 1,
                "page": 1,
                "filters": [{"field": "email", "operator": "eq", "value": email}],
            },
            {
                "locationId": self.pub_id,
                "pageLimit": 1,
                "searchTerm": email,
            },
            {
                "locationId": self.pub_id,
                "pageLimit": 1,
                "query": email,
            },
        ]
        for body in search_bodies:
            try:
                resp = self._request("POST", "/contacts/search", body=body)
                contact = self._extract_first_contact(resp)
                if contact:
                    return contact
            except HighLevelApiError as exc:
                if exc.status not in (400, 404, 422):
                    raise

        # Final deprecated fallback.
        try:
            resp = self._request("GET", "/contacts/", query={"locationId": self.pub_id, "limit": 1, "query": email})
            contact = self._extract_first_contact(resp)
            if contact:
                return contact
        except HighLevelApiError:
            pass

        return None

    def _upsert_contact(
        self,
        email: str,
        first_name: Optional[str] = None,
        utm_source: Optional[str] = None,
        utm_campaign: Optional[str] = None,
        reactivate: bool = True,
        custom_fields: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        translated_custom_fields = self._translate_custom_fields(custom_fields)

        # Try to map Beehiiv-ish UTM fields into HighLevel custom fields if the
        # location has matching field names already defined.
        for field_name, field_value in (("utm_source", utm_source), ("utm_campaign", utm_campaign)):
            if field_value:
                field_id = self._resolve_custom_field_id(field_name)
                if field_id:
                    translated_custom_fields.append({"id": field_id, "value": field_value})

        body: Dict[str, Any] = {
            "locationId": self.pub_id,
            "email": email,
        }
        if first_name:
            body["firstName"] = first_name
        if translated_custom_fields:
            body["customFields"] = translated_custom_fields

        # HighLevel does not expose Beehiiv's exact reactivate / double opt
        # semantics on contact upsert in the public docs. The method signature is
        # preserved, but those behaviors are treated as compatibility inputs.
        response = self._request("POST", "/contacts/upsert", body=body)
        contact = self._extract_first_contact(response) or response
        contact_id = self._extract_contact_id(contact) or self._extract_contact_id(response)
        if contact_id:
            contact["id"] = contact_id
        return contact

    def _resolve_contact_id(self, subscription_id_or_email: str) -> str:
        value = str(subscription_id_or_email).strip()
        if "@" in value:
            contact = self._find_contact_by_email(value)
            if not contact:
                raise RuntimeError(f"Could not find HighLevel contact for email: {value}")
            return str(self._first_non_empty(contact.get("id"), contact.get("contactId"), contact.get("_id")))
        return value

    # -------------------------------------------------------------------------
    # Campaign helpers
    # -------------------------------------------------------------------------

    def _create_email_campaign_shell(self, title: str, subject: str) -> str:
        sender_fragment = {}
        if self.from_name:
            sender_fragment["fromName"] = self.from_name
        if self.from_email:
            sender_fragment["fromEmail"] = self.from_email
        if self.reply_to_email:
            sender_fragment["replyToEmail"] = self.reply_to_email

        create_variants = [
            {"name": title},
            {"title": title},
            {"campaignName": title},
            {"name": title, "subject": subject},
            {"title": title, "subject": subject},
            {**({"name": title} if title else {}), **sender_fragment},
            {**({"title": title} if title else {}), **sender_fragment},
        ]
        resp = self._request_variants(
            "POST",
            f"/emails/public/v2/locations/{self.pub_id}/campaigns/email-campaign",
            create_variants,
        )
        campaign_id = self._extract_campaign_id(resp)
        if not campaign_id:
            raise RuntimeError(f"HighLevel created a campaign but no campaign id was returned: {resp}")
        return campaign_id

    def _update_email_campaign_body(
        self,
        campaign_id: str,
        title: str,
        subject: str,
        preview: str,
        html_body: str,
    ) -> Any:
        sender_fragment = {}
        if self.from_name:
            sender_fragment["fromName"] = self.from_name
        if self.from_email:
            sender_fragment["fromEmail"] = self.from_email
        if self.reply_to_email:
            sender_fragment["replyToEmail"] = self.reply_to_email

        variants = [
            {"name": title, "subject": subject, "previewText": preview, "html": html_body, "status": "draft"},
            {"title": title, "subject": subject, "previewText": preview, "html": html_body, "status": "draft"},
            {"name": title, "subject": subject, "previewText": preview, "htmlContent": html_body, "status": "draft"},
            {"title": title, "subject": subject, "previewText": preview, "htmlContent": html_body, "status": "draft"},
            {"name": title, "subject": subject, "previewText": preview, "body": html_body, "status": "draft"},
            {"title": title, "subject": subject, "previewText": preview, "body": html_body, "status": "draft"},
            {"name": title, "subject": subject, "preview": preview, "content": html_body, "status": "draft"},
            {"title": title, "subject": subject, "preview": preview, "content": html_body, "status": "draft"},
        ]
        if sender_fragment:
            sender_variants = []
            for payload in variants:
                merged = dict(payload)
                merged.update(sender_fragment)
                sender_variants.append(merged)
            variants = sender_variants + variants

        return self._request_variants(
            "PATCH",
            f"/emails/public/v2/locations/{self.pub_id}/campaigns/{campaign_id}",
            variants,
        )

    def _schedule_campaign(self, campaign_id: str, send_at_utc: Optional[str]) -> Any:
        now_iso = self._utcnow_iso()
        is_immediate = not send_at_utc or send_at_utc <= now_iso

        variants: List[Any] = []
        if is_immediate:
            variants.extend([_NO_BODY, {}, {"sendAt": now_iso}, {"scheduledAt": now_iso}, {"startAt": now_iso}, {"mode": "now"}])
        else:
            variants.extend([
                {"scheduledAt": send_at_utc},
                {"scheduleAt": send_at_utc},
                {"sendAt": send_at_utc},
                {"startAt": send_at_utc},
                {"scheduledTime": send_at_utc},
                {"date": send_at_utc},
                {"scheduledAt": send_at_utc, "timezone": os.environ.get("HIGHLEVEL_DEFAULT_TIMEZONE", "")},
            ])

        return self._request_variants(
            "POST",
            f"/emails/public/v2/locations/{self.pub_id}/campaigns/{campaign_id}/schedule",
            variants,
            tolerate_statuses=(400, 404, 405, 409, 422),
        )

    def _list_live_campaigns(self, limit: int = 10, status: Optional[str] = None) -> List[Dict[str, Any]]:
        queries = [
            {"limit": limit, "status": status},
            {"pageLimit": limit, "status": status},
            {"limit": limit},
            {"pageLimit": limit},
        ]
        last_error: Optional[Exception] = None
        for query in queries:
            try:
                resp = self._request(
                    "GET",
                    f"/emails/public/v2/locations/{self.pub_id}/campaigns/emails",
                    query=query,
                )
                items = self._extract_items(resp)
                if items:
                    return items
                if isinstance(resp, dict) and resp:
                    # Accept empty-yet-valid responses too.
                    return []
            except Exception as exc:
                last_error = exc
                continue
        if last_error:
            raise last_error
        return []

    # -------------------------------------------------------------------------
    # Public API: same method signatures as the original Beehiiv wrapper
    # -------------------------------------------------------------------------

    def create_draft(self, title, subject, preview, html_body, content_tags=None):
        """
        Create a draft newsletter in HighLevel.

        Backing object: HighLevel Email Campaign V2 draft.
        """
        campaign_id = self._create_email_campaign_shell(title=title, subject=subject)
        self._update_email_campaign_body(
            campaign_id=campaign_id,
            title=title,
            subject=subject,
            preview=preview,
            html_body=html_body,
        )

        self._upsert_campaign_cache(
            campaign_id,
            {
                "title": title,
                "subject": subject,
                "preview": preview,
                "html_body": html_body,
                "content_tags": list(content_tags or []),
                "status": "draft",
                "created_at": self._utcnow_iso(),
                "url": self._campaign_api_url(campaign_id),
                "web_url": "",
            },
        )

        return {
            "post_id": campaign_id,
            "url": self._campaign_api_url(campaign_id),
            "web_url": "",
        }

    def publish_post(self, post_id):
        """Publish a draft immediately by scheduling it to send now."""
        try:
            self._schedule_campaign(post_id, None)
            self._upsert_campaign_cache(
                str(post_id),
                {
                    "status": "scheduled",
                    "scheduled_at": self._utcnow_iso(),
                },
            )
            return {"success": True, "message": "Campaign scheduled to send immediately via HighLevel"}
        except Exception as exc:
            return {
                "success": False,
                "message": "HighLevel publish failed",
                "url": self._campaign_api_url(str(post_id)),
                "error": str(exc),
            }

    def schedule_post(self, post_id, send_at_utc):
        """
        Schedule an existing draft for future delivery.

        Unlike Beehiiv, HighLevel Email Campaigns V2 schedules the same campaign
        object instead of deleting/recreating it, so the post_id is preserved.
        """
        self._schedule_campaign(str(post_id), send_at_utc)
        self._upsert_campaign_cache(
            str(post_id),
            {
                "status": "scheduled",
                "scheduled_at": send_at_utc,
            },
        )
        return {
            "post_id": str(post_id),
            "url": self._campaign_api_url(str(post_id)),
            "web_url": self._campaign_cache(str(post_id)).get("web_url", ""),
        }

    def create_scheduled_post(self, title, subject, preview, html_body, send_at_utc,
                               subtitle="", content_tags=None):
        """Create a draft and immediately schedule it for future delivery."""
        draft = self.create_draft(
            title=title,
            subject=subject,
            preview=preview,
            html_body=html_body,
            content_tags=content_tags,
        )
        post_id = draft["post_id"]
        self._upsert_campaign_cache(
            post_id,
            {
                "subtitle": subtitle or "",
            },
        )
        return self.schedule_post(post_id, send_at_utc)

    def delete_post(self, post_id):
        """Delete an email campaign draft/campaign in HighLevel."""
        response = self._request(
            "DELETE",
            f"/emails/public/v2/locations/{self.pub_id}/campaigns/{post_id}",
        )
        self._delete_campaign_cache(str(post_id))
        return response

    def get_post(self, post_id):
        """
        Get details for a specific campaign.

        HighLevel's public Email Campaigns V2 docs reviewed for this adapter do
        not expose a dedicated get-by-id campaign endpoint, so this method uses
        list+filter and then merges any local cached metadata.
        """
        post_id = str(post_id)
        live_campaign: Optional[Dict[str, Any]] = None
        try:
            live_campaigns = self._list_live_campaigns(limit=200)
            for item in live_campaigns:
                item_id = str(self._first_non_empty(item.get("id"), item.get("campaignId"), item.get("_id")) or "")
                if item_id == post_id:
                    live_campaign = item
                    break
        except Exception:
            live_campaign = None

        if live_campaign or self._campaign_cache(post_id):
            return self._merge_live_and_cache_campaign(post_id, live=live_campaign)

        raise RuntimeError(f"HighLevel campaign not found: {post_id}")

    def list_posts(self, status="draft", limit=10):
        """List campaigns, filtered by status when possible."""
        normalized_requested_status = (status or "").strip().lower()
        live_items: List[Dict[str, Any]] = []
        try:
            live_items = self._list_live_campaigns(limit=limit, status=status)
        except Exception:
            live_items = []

        merged: List[Dict[str, Any]] = []
        seen_ids = set()

        for raw in live_items:
            campaign_id = str(self._first_non_empty(raw.get("id"), raw.get("campaignId"), raw.get("_id")) or "")
            if not campaign_id:
                continue
            normalized = self._merge_live_and_cache_campaign(campaign_id, live=raw)
            seen_ids.add(campaign_id)
            merged.append(normalized)

        # Include cached items if live listing did not return them.
        for campaign_id, cached in self._cache.get("campaigns", {}).items():
            if campaign_id in seen_ids:
                continue
            merged.append(self._normalize_campaign(None, cached=cached))

        if normalized_requested_status:
            merged = [item for item in merged if str(item.get("status", "")).lower() == normalized_requested_status]

        # Most recent first, using cache timestamps when available.
        merged.sort(
            key=lambda item: self._first_non_empty(
                self._campaign_cache(str(item.get("id", ""))).get("updated_at"),
                self._campaign_cache(str(item.get("id", ""))).get("created_at"),
                "",
            ),
            reverse=True,
        )
        return merged[:limit]

    def subscribe(self, email, first_name=None, utm_source=None, utm_campaign=None,
                  automation_ids=None, double_opt="off", reactivate=True, custom_fields=None):
        """
        Add or update a subscriber in HighLevel.

        Mapping:
        - Beehiiv subscriber -> HighLevel contact
        - Beehiiv automation_ids -> HighLevel workflow ids

        Notes:
        - double_opt is preserved in the signature for compatibility, but
          HighLevel contact upsert does not expose Beehiiv's exact opt-in
          override behavior in the public docs reviewed for this adapter.
        - reactivate is preserved in the signature for compatibility.
        """
        contact = self._upsert_contact(
            email=email,
            first_name=first_name,
            utm_source=utm_source,
            utm_campaign=utm_campaign,
            reactivate=reactivate,
            custom_fields=custom_fields,
        )

        workflow_results = []
        for workflow_id in automation_ids or []:
            try:
                result = self.enroll_in_automation(workflow_id, email)
                workflow_results.append({"workflow_id": workflow_id, "success": True, "result": result})
            except Exception as exc:
                workflow_results.append({"workflow_id": workflow_id, "success": False, "error": str(exc)})

        if workflow_results:
            contact["workflow_results"] = workflow_results
        contact["_compat"] = {
            "double_opt": double_opt,
            "reactivate": reactivate,
        }
        return contact

    def enroll_in_automation(self, automation_id, email):
        """
        Enroll an existing subscriber in a HighLevel workflow.

        Beehiiv automation_id -> HighLevel workflowId
        """
        contact = self._find_contact_by_email(email)
        if not contact:
            contact = self._upsert_contact(email=email)
        contact_id = str(self._first_non_empty(contact.get("id"), contact.get("contactId"), contact.get("_id")) or "")
        if not contact_id:
            raise RuntimeError(f"Could not resolve HighLevel contact id for {email}")

        response = self._request(
            "POST",
            f"/contacts/{contact_id}/workflow/{automation_id}",
            body=_NO_BODY,
        )
        return {
            "success": True,
            "contact_id": contact_id,
            "workflow_id": automation_id,
            "result": response,
        }

    def update_subscriber(self, subscription_id, custom_fields=None, **kwargs):
        """
        Update a subscriber's contact fields in HighLevel.

        Beehiiv subscription_id maps to HighLevel contact id in this adapter.
        For convenience, passing an email address also works.
        """
        contact_id = self._resolve_contact_id(subscription_id)
        body = {}

        # Preserve common alias ergonomics.
        field_aliases = {
            "first_name": "firstName",
            "last_name": "lastName",
            "company_name": "companyName",
        }
        for key, value in kwargs.items():
            body[field_aliases.get(key, key)] = value

        translated_custom_fields = self._translate_custom_fields(custom_fields)
        if translated_custom_fields:
            body["customFields"] = translated_custom_fields

        response = self._request("PUT", f"/contacts/{contact_id}", body=body)
        contact = self._extract_first_contact(response) or response
        if isinstance(contact, dict):
            contact["id"] = contact_id
        return contact

    def get_subscriber(self, email):
        """Look up a subscriber by email in HighLevel."""
        try:
            contact = self._find_contact_by_email(email)
            return contact
        except RuntimeError:
            return None

    def test_connection(self):
        """Verify token and location id are valid."""
        try:
            self._request("GET", f"/locations/{self.pub_id}")
            return {"success": True, "message": "HighLevel API connection OK"}
        except Exception as exc:
            return {"success": False, "message": str(exc)}


if __name__ == "__main__":
    client = BeehiivClient()
    result = client.test_connection()
    print(json.dumps(result, indent=2))
