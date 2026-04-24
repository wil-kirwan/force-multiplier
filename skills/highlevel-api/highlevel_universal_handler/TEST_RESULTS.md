# Test Results

Command run inside the package folder:

```bash
PYTHONPATH=. python -S -m unittest -v tests/test_highlevel_handler.py
```

Result:

```text
test_ai_agent_studio_execute_renders_exact_path ... ok
test_contact_create_payload ... ok
test_dynamic_wrapper_renders_path_and_headers ... ok
test_from_env_allows_explicit_location_override ... ok
test_missing_path_parameter_raises_clear_error ... ok
test_recent_endpoint_paths_are_exact ... ok
test_registry_has_all_required_roots ... ok
test_social_planner_create_requires_account_intent ... ok
test_social_planner_resolves_account_ids_before_create ... ok

Ran 9 tests in 0.150s

OK
```

Live HighLevel API calls were not executed inside this container because external API access is not available here. The included `examples/smoke_test_location.py` performs the live call from any networked runtime after setting environment variables.
