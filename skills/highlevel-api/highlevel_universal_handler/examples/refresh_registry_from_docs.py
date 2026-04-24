"""Refresh the registry from HighLevel's public docs.

Run this in CI to catch new endpoints:
  python examples/refresh_registry_from_docs.py
"""

from highlevel_universal_handler import HighLevelHandler

handler = HighLevelHandler.from_env()
registry = handler.refresh_registry_from_docs(save_to="highlevel_registry.generated.json")
print(f"Registry refreshed. Actions: {len(registry)}")
print(registry.coverage_report())
