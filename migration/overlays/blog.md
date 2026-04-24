<!-- HIGHLEVEL-INTEGRATION-START: blog -->
## HighLevel Blogs publishing mode

Add HighLevel Blogs as a first-class publishing path. Keep local markdown, MDX, HTML, and other CMS outputs available, but do not assume them by default when the user is working inside HighLevel.

### When the destination is HighLevel
Produce an editor-ready output package with:
- title
- clean body content for the HighLevel blog editor
- slug
- author
- category
- keywords
- canonical link
- SEO title
- post description
- cover image URL
- cover image alt text
- publish status or schedule note

### HighLevel-specific workflow
- treat published HighLevel blog URLs as first-class inputs for analysis and rewrites
- if location access exists, use the shared `highlevel-api` skill to list blog authors, categories, and posts, check slug availability, and create or update the post
- if the CTA needs a form, survey, or calendar, prefer routing from the blog post into a HighLevel funnel or website page rather than assuming embedded form blocks inside the post
- when distribution is requested, prefer HighLevel Social Planner and HighLevel email assets where supported
<!-- HIGHLEVEL-INTEGRATION-END: blog -->
