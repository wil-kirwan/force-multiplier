<!-- HIGHLEVEL-INTEGRATION-START: blog-geo -->
## HighLevel-specific GEO checks

Keep the AI citation scoring model unchanged. Add platform-specific checks when the page is a HighLevel blog post or a blog post embedded on a HighLevel site or funnel.

### Additional checks
- published URL is public and crawlable
- canonical URL is set correctly
- SEO title and post description are present
- author and category are set
- cover image metadata is present
- page content is visible without depending on gated editor state
- blog-to-funnel or blog-to-site embedding does not block normal crawler access
- AI-crawler accessibility is evaluated on the final published HighLevel URL, not just on local source files
<!-- HIGHLEVEL-INTEGRATION-END: blog-geo -->
