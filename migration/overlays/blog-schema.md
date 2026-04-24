<!-- HIGHLEVEL-INTEGRATION-START: blog-schema -->
## HighLevel schema placement guidance

Keep JSON-LD generation and validation rules unchanged. Add a HighLevel-specific placement note.

### Placement rules
- for HighLevel websites and funnels, prefer native HighLevel schema features or page-level schema placement when available
- for HighLevel blog posts, treat built-in blog SEO fields as the first metadata layer
- if a custom JSON-LD block cannot be placed directly on the blog post, document the limitation clearly and recommend the nearest supported HighLevel page or site-level placement
- separate the schema payload from the blog editor content so the user can place it where HighLevel actually supports it

Do not assume an MDX component or arbitrary custom-code insertion path exists on every HighLevel blog implementation.
<!-- HIGHLEVEL-INTEGRATION-END: blog-schema -->
