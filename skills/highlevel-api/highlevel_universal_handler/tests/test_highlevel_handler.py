import json
import unittest

from highlevel_universal_handler import (
    ActionRegistry,
    HighLevelHandler,
    MissingParameterError,
    ResolverError,
)


class FakeResponse:
    def __init__(self, status_code=200, data=None, headers=None):
        self.status_code = status_code
        self._data = data if data is not None else {}
        self.headers = headers or {"Content-Type": "application/json"}
        self.text = json.dumps(self._data)

    def json(self):
        return self._data


class FakeSession:
    def __init__(self):
        self.calls = []
        self.routes = []

    def add(self, method, url_suffix, response):
        self.routes.append((method.upper(), url_suffix, response))
        return self

    def request(self, method, url, **kwargs):
        self.calls.append({"method": method.upper(), "url": url, **kwargs})
        for route_method, suffix, response in self.routes:
            if route_method == method.upper() and url.endswith(suffix):
                return response
        return FakeResponse(404, {"message": f"No fake route for {method} {url}"})

    def post(self, url, data=None, timeout=None):
        self.calls.append({"method": "POST", "url": url, "data": data, "timeout": timeout})
        return FakeResponse(200, {"access_token": "test", "refresh_token": "refresh", "expires_in": 86399})


class HighLevelHandlerTests(unittest.TestCase):
    def test_registry_has_all_required_roots(self):
        registry = ActionRegistry.seeded()
        report = registry.coverage_report()
        self.assertEqual(report["missing_required_roots"], [])
        self.assertGreaterEqual(report["total_actions"], 300)
        self.assertIn("social_planner", report["roots_present"])
        self.assertIn("brand_boards", report["roots_present"])

    def test_dynamic_wrapper_renders_path_and_headers(self):
        session = FakeSession().add(
            "GET",
            "/brand-boards/R3T13C7SpeS7cOozpIiw",
            FakeResponse(200, {"brandBoards": []}),
        )
        handler = HighLevelHandler(
            bearer_token="pit-test-token",
            location_id="R3T13C7SpeS7cOozpIiw",
            session=session,
        )
        result = handler.brand_boards.brand_boards.get_brand_boards()
        self.assertEqual(result, {"brandBoards": []})
        call = session.calls[-1]
        self.assertEqual(call["method"], "GET")
        self.assertTrue(call["url"].endswith("/brand-boards/R3T13C7SpeS7cOozpIiw"))
        self.assertEqual(call["headers"]["Authorization"], "Bearer pit-test-token")
        self.assertEqual(call["headers"]["Version"], "2021-07-28")

    def test_missing_path_parameter_raises_clear_error(self):
        handler = HighLevelHandler(session=FakeSession())
        with self.assertRaises(MissingParameterError):
            handler.brand_boards.brand_boards.get_brand_boards()

    def test_contact_create_payload(self):
        session = FakeSession().add(
            "POST",
            "/contacts/",
            FakeResponse(201, {"contact": {"id": "c1"}}),
        )
        handler = HighLevelHandler(
            bearer_token="pit-test-token",
            location_id="loc1",
            session=session,
        )
        payload = {"firstName": "Ada", "locationId": "loc1"}
        result = handler.contacts.contacts.create_contact(payload=payload)
        self.assertEqual(result["contact"]["id"], "c1")
        self.assertEqual(session.calls[-1]["json"], payload)

    def test_social_planner_resolves_account_ids_before_create(self):
        session = FakeSession()
        session.add(
            "GET",
            "/social-media-posting/loc1/accounts",
            FakeResponse(200, {"accounts": [{"id": "fb1", "platform": "facebook", "name": "Main Page"}]}),
        )
        session.add(
            "POST",
            "/social-media-posting/loc1/posts",
            FakeResponse(201, {"id": "post1"}),
        )
        handler = HighLevelHandler(
            bearer_token="pit-test-token",
            location_id="loc1",
            session=session,
        )
        result = handler.social_planner.post.create_post(
            payload={"summary": "hello", "status": "published"},
            resolve={"accountIds": {"platforms": ["facebook"]}},
        )
        self.assertEqual(result["id"], "post1")
        create_call = session.calls[-1]
        self.assertEqual(create_call["json"]["accountIds"], ["fb1"])

    def test_social_planner_create_requires_account_intent(self):
        handler = HighLevelHandler(location_id="loc1", session=FakeSession())
        with self.assertRaises(ResolverError):
            handler.social_planner.post.create_post(payload={"summary": "hello", "status": "published"})

    def test_from_env_allows_explicit_location_override(self):
        import os
        old = os.environ.get("HIGHLEVEL_LOCATION_ID")
        os.environ["HIGHLEVEL_LOCATION_ID"] = "env-location"
        try:
            handler = HighLevelHandler.from_env(location_id="explicit-location", session=FakeSession())
            self.assertEqual(handler.context.location_id, "explicit-location")
        finally:
            if old is None:
                os.environ.pop("HIGHLEVEL_LOCATION_ID", None)
            else:
                os.environ["HIGHLEVEL_LOCATION_ID"] = old

    def test_recent_endpoint_paths_are_exact(self):
        registry = ActionRegistry.seeded()
        self.assertEqual(
            registry.get("knowledge_base", "faqs", "delete_faq").path,
            "/knowledge-bases/faqs/:id",
        )
        self.assertEqual(
            registry.get("conversation_ai", "actions", "list_actions_for_agent").path,
            "/conversation-ai/agents/:agentId/actions/list",
        )
        self.assertEqual(
            registry.get("store", "shipping_zone_rates", "get_shipping_rate").path,
            "/store/shipping-zone/:shippingZoneId/shipping-rate/:shippingRateId",
        )
        self.assertEqual(
            registry.get("ai_agent_studio", "agents", "execute_agent").path,
            "/agent-studio/agent/:agentId/execute",
        )

    def test_ai_agent_studio_execute_renders_exact_path(self):
        session = FakeSession().add(
            "POST",
            "/agent-studio/agent/agent-1/execute",
            FakeResponse(200, {"answer": "ok"}),
        )
        handler = HighLevelHandler(bearer_token="pit-test-token", session=session)
        result = handler.ai_agent_studio.agents.execute_agent(
            agent_id="agent-1",
            payload={"locationId": "loc1", "message": "hello"},
        )
        self.assertEqual(result["answer"], "ok")
        self.assertTrue(session.calls[-1]["url"].endswith("/agent-studio/agent/agent-1/execute"))


if __name__ == "__main__":
    unittest.main()
