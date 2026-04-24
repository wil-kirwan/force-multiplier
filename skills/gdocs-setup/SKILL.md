---
name: gdocs-setup
description: Legacy optional Google Docs integration setup. The default stack is Notion for content storage and HighLevel for lead capture, delivery workflows, and CRM activity.
argument-hint: (no arguments needed)
context: conversation
---

# Google Docs Setup — Legacy Optional

This skill remains available for backwards compatibility, but Google Docs is no longer the required content-pipeline path.

The default operating stack is:
- Notion for script storage and content operations
- HighLevel for funnels, forms, surveys, calendars, workflows, email, SMS, CRM activity, and delivery

---

## Default path

### Step 1: Set up Notion first

Run `/notion-setup` and confirm that `~/.config/notion-content/config.json` exists.

The Script Library should be the default long-form record for scripts, approvals, status, and reporting.

### Step 2: Configure HighLevel access

Install and configure the shared `highlevel-api` skill.

Confirm these are available before using downstream content skills:
- HighLevel auth, either Private Integration or OAuth
- the target location or sub-account context
- any default pipeline, form, calendar, or workflow destinations the user wants to use

### Step 3: Verify the live stack

Use the shared `highlevel-api` skill to confirm the stack can reach the assets your content system needs, such as:
- contacts and opportunities
- forms or surveys
- calendars
- blogs or website pages
- Social Planner assets when relevant

### Step 4: Explain the current default

Tell the user:

> The default stack is now ready.
>
> - Notion stores scripts, approvals, and pipeline state.
> - HighLevel handles capture, delivery, workflows, email, SMS, calendars, and CRM activity.
> - Google Docs is optional only if you still want a parallel document layer.

---

## Optional legacy Google Docs path

Only run this if the user explicitly asks to keep Google Docs.

1. Create or use a Google Cloud project
2. Enable Google Docs API and Google Drive API
3. Create Desktop OAuth credentials
4. Save them to `~/.config/gdocs/credentials.json`
5. Run the legacy setup flow through `gdocs_push.py --setup`

If the user does not ask for Google Docs specifically, do not guide them into this path.
