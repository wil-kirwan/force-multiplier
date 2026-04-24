<!-- HIGHLEVEL-INTEGRATION-START: ads -->
## HighLevel-first CRM and conversion layer

Use the shared `highlevel-api` skill and bundled HighLevel handler whenever this skill touches CRM capture, landing pages, calendars, call tracking, pipeline reporting, workflows, or offline conversion measurement.

HighLevel is the default system for:
- CRM records, lead status, tags, custom fields, and pipeline stages
- landing pages, funnels, forms, surveys, chat widgets, calendars, and follow-up workflows
- UTM and click-ID storage that later powers lead quality and revenue analysis

Keep these unchanged:
- platform-native audits and exports
- pixels, CAPI, consent, enhanced conversions, and benchmark logic
- auction, search term, creative, and bidding analysis done inside the ad platforms

### Default HighLevel data pull for ads work
When the user runs an audit or asks for implementation help, enrich platform exports with HighLevel data in this order:
1. Contacts and custom fields for UTMs, click IDs, lead source, and lifecycle status
2. Opportunities and pipelines for MQL, SQL, booked call, show, close, and revenue outcomes
3. Forms, surveys, calendars, conversations, and call outcomes to verify post-click conversion flow
4. Workflows and follow-up messages to verify nurture, reminders, and handoff

Prefer the shared handler over raw HTTP:
- `contacts.contacts.*`
- `opportunities.opportunities.*`
- `opportunities.pipelines.*`
- `forms.forms.*`
- `calendars.calendars.*`
- `calendars.calendar_events.*`

### Audit and planning rule
For audit scoring, platform data remains the source of truth for spend, impressions, clicks, CTR, CPC, CPM, placement, and creative delivery.

For lead quality and revenue, HighLevel becomes the source of truth unless the user provides a more authoritative downstream sales system.
<!-- HIGHLEVEL-INTEGRATION-END: ads -->
