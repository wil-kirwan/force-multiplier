<!-- HIGHLEVEL-INTEGRATION-START: ads-meta -->
## HighLevel mapping for Meta lead and pipeline outcomes

Keep Meta Pixel, CAPI, AEM, event deduplication, EMQ, and domain verification requirements unchanged.

Use HighLevel as the default system for:
- lead records and `external_id` alignment
- contact fields and custom fields that store campaign metadata
- opportunity creation and pipeline-stage tracking
- appointment, show, close, and revenue outcomes after the click

### Field mapping rule
Map Meta customer parameters and identifiers into HighLevel wherever possible:
- `external_id` -> stable CRM/contact ID
- campaign, ad set, and ad identifiers -> custom fields
- `fbclid` and UTM values -> capture fields used for attribution and reporting

### Audit rule
When Meta claims good top-line conversion performance, verify real lead quality in HighLevel before recommending more budget.
<!-- HIGHLEVEL-INTEGRATION-END: ads-meta -->
