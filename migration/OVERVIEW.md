# HighLevel skill migration overview

This repo packages the shared `highlevel-api` skill together with the HighLevel handler files and a migration kit for your existing skill library.

## Counts from the supplied matrix

- Total skills reviewed: 59
- Required updates (`Yes`): 9
- Optional HighLevel-aware updates (`Optional`): 32
- No update needed (`No`): 18

## What is included

- `skills/highlevel-api/` — the packaged HighLevel skill plus the bundled handler
- `skills/` — concrete updated SKILL files for provided source skills
- `migration/skills-highlevel-manifest.csv` — the exact update matrix
- `migration/overlays/` — merge-ready overlay blocks for every skill marked `Yes` or `Optional`
- `migration/generated-updated-skills/` — concrete updated SKILL files for uploaded source skills
- `scripts/install_highlevel_skill_pack.py` — installer that copies the shared skill and applies overlays to an existing skill library
- `docs/UPDATED_SKILLS.md` — summary of the concrete skill files that were updated in this repo

## Concrete updated skills included

### Existing concrete skills
- seo-programmatic
- seo-sitemap
- shopify-store-design
- topic-researcher
- transcript

### Batch 1 concrete skills
- ads
- ads-audit
- ads-google
- ads-landing
- ads-linkedin
- ads-meta
- ads-microsoft
- ads-plan
- ads-tiktok
- ads-youtube
- blog
- blog-analyze
- blog-audit
- blog-brief
- blog-calendar
- blog-geo
- blog-repurpose
- blog-rewrite
- blog-schema
- blog-seo-check

### Batch 2 concrete skills
- blog-strategy
- blog-write
- carousel-gen
- client-brief
- content-master
- content-scripting
- ecommerce-cro
- gdocs-setup
- hand-raiser
- hooks
- notion-setup
- seo
- seo-audit
- seo-competitor-pages
- seo-geo
- seo-page
- seo-plan
- seo-schema
- seo-technical

Skills that have not yet been provided as full files remain covered by generated overlays and the installer script.
