<!-- HIGHLEVEL-INTEGRATION-START: shopify-store-design -->
## HighLevel integration

Use the shared `highlevel-api` skill and bundled handler whenever this skill touches HighLevel-managed data or build steps.

### Skill-specific change
Keep Shopify-specific product, checkout, and collection guidance if the store stays on Shopify. Route landing pages, email capture, CRM follow-up, SMS/email recovery, and abandoned checkout workflows through HighLevel where appropriate. (GoHighLevel)

### Default implementation rule
- HighLevel becomes the default system only for the parts named above.
- Keep the skill's existing research, analysis, platform-native tooling, and non-HighLevel specialization intact.
- Do not hand-roll raw HTTP calls if the bundled HighLevel handler already supports the route.
- Resolve parent IDs and chained calls through the handler instead of asking the user for every ID.

### Shared handler entry point
```python
from highlevel_universal_handler import HighLevelHandler

handler = HighLevelHandler.from_env()

# Known route
# handler.<root>.<child>.<action>(...)

# Generic route
# handler.invoke(root, child, action, ...)
```

### Guidance for this skill
Typical HighLevel objects for this skill:
- Funnels, Forms, Contacts, Tags, Workflows, Email, SMS, Calendars, Social Planner
- Keep Shopify as the store and checkout system when the skill is Shopify-specific
- Use HighLevel as the campaign landing-page, CRM, follow-up, lead capture, and recovery layer where appropriate
<!-- HIGHLEVEL-INTEGRATION-END: shopify-store-design -->
