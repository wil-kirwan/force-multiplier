---
name: hand-raiser
description: Generate a hand raiser PDF lead magnet (1-5 pages) for any script or standalone topic. Renders a professional guide, cheatsheet, or checklist, then routes delivery through HighLevel and writes the asset back to Notion.
argument-hint: "SF #3" or "Claude Code setup guide" or "AI scheduling cheatsheet"
context: conversation
---

# Hand Raiser PDF Generator

Create professional 1-5 page PDF lead magnets — guides, cheatsheets, checklists, quick-references, or how-to guides. Every script produced gets a matching hand raiser. This is part of the production pipeline, not optional.

---

## Step 1: Parse Input

Extract from `$ARGUMENTS`:

1. **SCRIPT_REF** — A script reference like "SF #3", "#3", "script 3" → fetch from Notion
2. **STANDALONE_TOPIC** — A freeform topic like "Claude Code setup guide" → no Notion fetch needed
3. **PDF_TYPE** (optional) — One of: `setup-guide`, `cheatsheet`, `quick-reference`, `how-to-guide`, `checklist`. If not specified, auto-detect in Step 3.

If input is ambiguous, default to treating it as a script reference if it contains a number.

---

## Step 2: Fetch Script Context (if script ref)

If SCRIPT_REF is provided, query the Script Library:

1. Read `~/.config/notion-content/config.json` to get `script_library_db_id`
2. Use `notion-search` with `data_source_url` set to `collection://{script_library_db_id}` to find the script by number or title
3. Extract:
   - **Title** — Script title
   - **Topic** — Content topic
   - **CTA** — The "Comment [WORD]" CTA from the script caption
   - **Pain Point** — The core problem the script solves
   - **Script source** — Use the Notion page body, stored script preview, local file path, or any linked script asset for reference
4. If the script record includes page content, a local file path, or a legacy external doc URL, read that content for context before generating the PDF

If STANDALONE_TOPIC, skip this step — use the topic directly.

---

## Step 3: Auto-Detect PDF Type

Based on the content, select the best PDF type:

| Content Signal | PDF Type | When |
|---|---|---|
| Setup/install/config steps | `setup-guide` | Script shows how to set up or install something |
| Quick tips, shortcuts, commands | `cheatsheet` | Script covers multiple quick tips or a tool's commands |
| Reference data, benchmarks, specs | `quick-reference` | Script references data the viewer would want to save |
| Step-by-step tutorial | `how-to-guide` | Script walks through a process |
| Audit, evaluation, requirements | `checklist` | Script involves checking/evaluating things |

**Default:** `how-to-guide` if unclear.

Tell the user what type was selected and why (one line).

---

## Step 4: Generate Content JSON

Create structured JSON content for the PDF. The JSON format is documented in `~/ai-content-system/scripts/pdf_generator.py`.

### Content Guidelines by Type

**setup-guide** (1-5 pages):
- Cover page with title + "What You'll Learn" bullets
- Prerequisites section
- Numbered steps with code blocks where relevant
- Tip boxes for common gotchas
- Resources section at the end

**cheatsheet** (1-3 pages):
- Cover page with title + quick summary
- Tables for commands/shortcuts/formulas
- Two-column layouts for quick scanning
- Tip boxes for pro tips
- Keep dense — max info per page

**quick-reference** (1-3 pages):
- Cover page with title
- Tables with benchmarks/data/specs
- Callout boxes for key thresholds
- Organized by category

**how-to-guide** (2-5 pages):
- Cover page with "What You'll Learn" bullets
- Numbered steps with descriptions
- Code blocks or screen instructions where relevant
- Tip boxes between sections
- Resources at the end

**checklist** (1-3 pages):
- Cover page with title + context
- Checklist items grouped by category
- Tip boxes for important notes
- Keep actionable — each item is a clear yes/no

### Content Rules
- **Ground in the script's content.** The PDF should deliver the value promised by the script's CTA.
- **No fluff.** Every section earns its space. If a page doesn't add value, cut it.
- **Actionable over informational.** The reader should be able to DO something with every page.
- **Include the script's CTA context.** If the script says "Comment GUIDE", the PDF should feel like the guide that was promised.
- **5 pages MAX.** Enforced by the PDF generator, but aim for the right length — a cheatsheet should be 1-2 pages, not 5.

### JSON Structure

Write the content as a JSON object and save to a temp file:

```json
{
    "type": "{pdf_type}",
    "title": "{Title}",
    "subtitle": "{Subtitle}",
    "subtitle_bullets": ["Bullet 1", "Bullet 2", "Bullet 3"],
    "footer_text": "Your Footer Text | 2026",
    "sections": [
        {"type": "section_title", "number": "01", "title": "Section Name"},
        {"type": "body", "text": "Paragraph text."},
        {"type": "bullets", "items": ["Item 1", "Item 2"]},
        {"type": "tip_box", "title": "Pro Tip", "text": "Tip text."},
        ...
    ]
}
```

Save to: `~/ai-content-system/output/hand-raisers/content-sf{N}.json`

For standalone topics: `~/ai-content-system/output/hand-raisers/content-{kebab-title}.json`

---

## Step 5: Render PDF

Run the PDF generator:

```bash
cd ~/ai-content-system/scripts && python3 pdf_generator.py --content-file "{CONTENT_JSON_PATH}" --output "{OUTPUT_PATH}"
```

**Output path:** `~/ai-content-system/output/hand-raisers/SF{N}-{kebab-title}.pdf`
- If script ref: `SF{N}-{kebab-title}.pdf` (e.g., `SF3-ai-scheduling-setup-guide.pdf`)
- If standalone: `{kebab-title}.pdf` (e.g., `claude-code-setup-guide.pdf`)

Verify the PDF was created and report page count.

---

## Step 6: Create HighLevel delivery asset

HighLevel is the default delivery path. Google Drive is optional only if the user explicitly wants an external file host.

If the shared `highlevel-api` skill and location context are available:
1. Upload or register the PDF as a HighLevel asset, media item, or resource where supported
2. Capture the returned delivery URL

If HighLevel upload is not available, keep the local PDF path and continue with the landing and workflow steps.

---

## Step 7: Create HighLevel funnel or site page

Create the lead-capture and delivery page in HighLevel by default.

### Default build
- create or update a HighLevel funnel step or website page for the offer
- attach a HighLevel form, survey, or calendar based on the CTA
- route submissions into tags, custom fields, and the correct pipeline logic
- trigger HighLevel email, SMS, reminder, and nurture workflows for delivery
- if the offer is driven by Instagram comments, connect the keyword to HighLevel comment automation and DM workflows

If the user explicitly asks for a non-HighLevel landing page, that becomes an export path, not the default.

---

## Step 8: Update Notion (if script ref)

If this hand raiser is for a Script Library entry:

1. Use `notion-update-page` to set the local PDF path plus any available HighLevel URLs such as Hand Raiser URL, Hand Raiser Page, HighLevel Funnel URL, HighLevel Form URL, HighLevel Calendar URL, or HighLevel Resource URL on the script's Notion page
2. If some properties do not exist, skip them gracefully and still deliver the asset

If standalone, skip this step.

---

## Step 9: Report

Output a summary:

```
Hand Raiser Generated:
- Type: {pdf_type}
- Pages: {page_count}
- Local: {local_path}
- HighLevel Asset: {highlevel_asset_url or "not created"}
- HighLevel Landing Page: {highlevel_page_url or "not created"}
- Notion: {Updated / Skipped (standalone) / Property missing}
- CTA: "Comment {WORD} and I'll send you this {pdf_type}!"
```

The CTA line gives the user ready-to-use caption text for their video.

---

## Batch Mode

When called in a loop, accept multiple scripts efficiently:

1. Generate all content JSONs first
2. Render all PDFs locally
3. Create all required HighLevel delivery assets and pages
4. Update all Notion entries with local paths and HighLevel URLs
5. Report all links in a single summary table

This avoids repeated setup and keeps delivery in the same stack.

---

## Error Handling

- **fpdf2 not installed:** `pip3 install fpdf2` and retry
- **HighLevel auth expired or missing:** refresh auth or reconnect the shared `highlevel-api` skill
- **Notion property missing:** report gracefully, still deliver the PDF and any local or HighLevel URLs
- **Content too long:** PDF generator enforces 5-page max; warn if content was truncated
- **Missing script in Notion:** tell the user the script wasn't found, offer to create as standalone

---

## HighLevel delivery path

HighLevel is the default delivery and follow-up layer for hand raisers. Google Drive and Vercel are no longer the required path.

### Default execution
- render the PDF locally first
- if HighLevel access exists, upload or register the asset through the shared `highlevel-api` skill where supported
- create a HighLevel funnel or site page for opt-in and delivery
- use HighLevel forms, surveys, calendars, workflows, email, SMS, tags, and opportunities for capture and nurture
- write the resulting HighLevel URLs back to Notion when a script record exists

### Instagram delivery
For comment-keyword offers, pair the PDF with HighLevel Instagram comment automation and DM workflows instead of external DM tools.
