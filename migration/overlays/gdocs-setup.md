<!-- HIGHLEVEL-INTEGRATION-START: gdocs-setup -->
## Legacy optional path

This skill is now a compatibility shim. The default stack is Notion for content storage and HighLevel for capture, delivery, and CRM activity.

### Default recommendation
- run `/notion-setup` for the Script Library
- configure the shared `highlevel-api` skill with the required HighLevel auth and location context
- use HighLevel funnels, forms, calendars, workflows, blogs, and resources instead of requiring Google Docs or Drive

### Legacy fallback
Only walk through Google Docs setup if the user explicitly asks to keep a parallel Docs workflow.
<!-- HIGHLEVEL-INTEGRATION-END: gdocs-setup -->
