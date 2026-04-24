<!-- HIGHLEVEL-INTEGRATION-START: blog-rewrite -->
## HighLevel Blogs output mode

Keep MDX, markdown, and HTML exports available. Add a HighLevel-first output mode for users publishing inside HighLevel.

### HighLevel rewrite deliverable
Return:
- clean editor-ready body content
- title
- slug
- author
- category
- keywords
- canonical link
- SEO title
- post description
- cover image URL
- cover image alt text
- publish or schedule recommendation

### Execution rules
- use the shared `highlevel-api` skill when the user wants to check slug availability or create or update the HighLevel post
- do not assume frontmatter fields will be used directly by the publishing system
- if the CTA requires a form, survey, calendar, or lead magnet, prefer linking the blog post to a HighLevel funnel or website page rather than assuming those blocks live inside the blog post editor
<!-- HIGHLEVEL-INTEGRATION-END: blog-rewrite -->
