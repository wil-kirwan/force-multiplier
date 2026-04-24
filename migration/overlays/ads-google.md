<!-- HIGHLEVEL-INTEGRATION-START: ads-google -->
## HighLevel outcome mapping for Google Ads

Keep Google tag, Enhanced Conversions, Consent Mode, GTM, offline conversion import, and Google Ads attribution requirements unchanged.

Use HighLevel as the default system for:
- lead status after the click
- call outcomes and booked appointments
- pipeline stages, qualified opportunities, and closed revenue
- UTM fields, `gclid`, campaign, ad group, and keyword metadata stored on the contact or opportunity

### What to verify in HighLevel
- `gclid` is captured into a dedicated contact or opportunity field
- forms, calendars, and call flows create or update the correct contact
- opportunities are created in the correct pipeline and stage
- sales outcomes can be mapped back to offline conversion imports

### Reporting rule
When Google reports a conversion but HighLevel shows poor downstream quality, treat HighLevel as the truth source for lead quality, booked calls, pipeline movement, and revenue. Use that gap to diagnose false positives in Google conversion actions.
<!-- HIGHLEVEL-INTEGRATION-END: ads-google -->
