<!-- HIGHLEVEL-INTEGRATION-START: blog-write -->
## HighLevel Blog publishing mode

When the destination is HighLevel Blogs, do not default to frontmatter, MDX-only output, or custom component assumptions.

### HighLevel output package
Return a clean editor-ready package with:
- title
- clean body content for the HighLevel editor
- slug
- author
- category
- keywords or tags
- canonical link
- SEO title
- post description
- cover image URL
- cover image alt text
- publish status or schedule note

### HighLevel-specific execution
- if location access exists, use the shared `highlevel-api` skill to list blogs, authors, and categories, validate the slug, and create or update the post
- if the CTA needs a form, survey, calendar, funnel, or workflow, prefer HighLevel assets over external embed assumptions
- when distribution is requested, prefer HighLevel Social Planner and HighLevel email assets where supported
<!-- HIGHLEVEL-INTEGRATION-END: blog-write -->
