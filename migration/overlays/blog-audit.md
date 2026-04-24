<!-- HIGHLEVEL-INTEGRATION-START: blog-audit -->
## HighLevel-hosted audit mode

The current file-directory scan is not enough for HighLevel-hosted blogs. Add a second audit path for published HighLevel content.

### Accepted audit sources
- blog sitemap URL
- list of published blog post URLs
- exported post list from HighLevel
- location-backed API access through the shared `highlevel-api` skill

### HighLevel audit additions
For each post, audit:
- published URL accessibility
- slug, author, category, canonical, and SEO metadata
- internal linking between HighLevel-hosted posts and related funnel or website pages
- stale content based on published URLs even when no local markdown exists
- whether CTAs route into HighLevel forms, calendars, funnels, or workflows when required

Keep the existing local directory audit flow. Add this as a parallel hosted-content path, not a replacement.
<!-- HIGHLEVEL-INTEGRATION-END: blog-audit -->
