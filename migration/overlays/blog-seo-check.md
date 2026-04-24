<!-- HIGHLEVEL-INTEGRATION-START: blog-seo-check -->
## HighLevel blog SEO field checks

Keep the normal SEO validation flow. Add HighLevel blog metadata checks whenever the content is destined for or already hosted in HighLevel.

### Extra checks
- slug quality and final published URL
- SEO title
- post description
- canonical URL
- cover image URL
- cover image alt text
- author
- category
- keyword field usage when available

### Input rule
If the user provides a published HighLevel blog URL or a HighLevel metadata packet instead of a local file, treat that as a valid input and run the same pass-fail reporting with the added metadata checks above.
<!-- HIGHLEVEL-INTEGRATION-END: blog-seo-check -->
