<!-- HIGHLEVEL-INTEGRATION-START: seo-sitemap -->
## HighLevel integration

Use the shared `highlevel-api` skill and bundled handler whenever this skill touches HighLevel-managed data or build steps.

### Skill-specific change
Add notes for validating HighLevel-generated or HighLevel-hosted sitemaps, canonical URLs, and included pages. Core sitemap analysis does not need to change.

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
- Sites, Funnels, Website pages, Blogs, Forms, Calendars, Contacts, Opportunities, Workflows
- Keep the core SEO framework unchanged and only adjust implementation guidance when the site stack is HighLevel
- Use the shared handler when you need live HighLevel lookups instead of generic CMS assumptions
<!-- HIGHLEVEL-INTEGRATION-END: seo-sitemap -->
