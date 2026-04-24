<!-- HIGHLEVEL-INTEGRATION-START: blog-analyze -->
## HighLevel blog URL mode

Add a dedicated HighLevel-hosted analysis path.

### Input rules
Accept any of these as valid sources:
- local markdown, MDX, or HTML
- any published URL
- a HighLevel-hosted blog post URL
- a HighLevel blog export or metadata packet

### Extra checks for HighLevel blog posts
In addition to the normal scorecard, check:
- slug quality
- author and category presence
- canonical URL
- SEO title
- post description
- cover image and alt text
- whether the page reads cleanly as a published HighLevel post, not just an editor draft

Keep the current local-file and generic URL audit logic unchanged.
<!-- HIGHLEVEL-INTEGRATION-END: blog-analyze -->
