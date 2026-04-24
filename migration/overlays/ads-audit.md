<!-- HIGHLEVEL-INTEGRATION-START: ads-audit -->
## HighLevel audit data pack

Keep ad platform exports as the primary source for spend and delivery. Add a HighLevel data path before you score conversion quality or recommend workflow changes.

### Pull these HighLevel records
- Contacts with lead-source fields, UTMs, click IDs, and owner assignments
- Opportunities with pipeline, stage, status, value, and closed revenue
- Forms and form submissions for opt-in quality and hidden-field capture
- Calendars and appointment events for booked, rescheduled, cancelled, no-show, and completed outcomes
- Conversations or call logs when the business qualifies leads by phone
- Workflows that fire after form submits, calendar bookings, or missed calls

### Reconciliation logic
For every platform, compare:
1. platform-reported conversions
2. HighLevel-created contacts
3. HighLevel opportunities and stage progression
4. booked appointments, show rate, and closed revenue

Use this to identify:
- tracking inflation or double counting
- CRM drop-off between lead and opportunity
- broken follow-up after a form or call
- weak routing between source, owner, and pipeline stage

### Default implementation rule
If the user needs fixes, route the default build through the shared `highlevel-api` skill and handler instead of generic CRM or form guidance.
<!-- HIGHLEVEL-INTEGRATION-END: ads-audit -->
