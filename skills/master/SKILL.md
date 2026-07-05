---
name: master
description: End-to-end campaign orchestrator — research outlier topics, write scripts, track recording, then fan every script batch out into blog posts, hand raisers, newsletters, social posts, and ads on a fixed publishing timeline through HighLevel. Persists campaign state so the multi-week workflow survives across sessions.
argument-hint: "AI scheduling for service businesses" or "status" or "resume" or "publish" or "social" or "ads"
context: conversation
---

# Master Campaign Orchestrator

Runs the full content flywheel as one campaign, chaining the other skills in this repo in a fixed order with a fixed publishing timeline. The user talks naturally; you track where the campaign is and drive it to the next gate.

**The pipeline:**

```
Stage 1  RESEARCH   → outlier topics found and approved
Stage 2  SCRIPTS    → scripts written and CONFIRMED by the user
Stage 3  RECORD     → user films; pipeline statuses tracked
Stage 4  DERIVE     → blog post, hand raisers, newsletter generated from scripts
Stage 5  PUBLISH    → Day 0: blog live on HighLevel; hand raisers in Media Storage
                      + manifest JSON updated; newsletter scheduled for Day +2
Stage 6  SOCIAL     → posts designed in Hyperframes, uploaded to Social Planner,
                      scheduled to ALL connected platforms for Day +1
Stage 7  ADS        → Day +7: rank social posts from the last 14 days, turn the
                      best performer(s) into an ad
```

**Timeline anchor:** everything is dated relative to the blog publish date (Day 0):
- Day +1 — social posts go out on all platforms
- Day +2 — newsletter sends
- Day +7 — ads review: best social posts from the previous two weeks become ads

---

## Campaign State — REQUIRED

This workflow spans weeks. Never rely on conversation memory alone. Persist state to:

```
~/ai-content-system/campaigns/{slug}/campaign.json
```

Structure:

```json
{
  "slug": "ai-scheduling-service-businesses",
  "topic": "AI scheduling for service businesses",
  "audience": "service business owners",
  "stage": "SOCIAL",
  "created": "2026-07-05",
  "research": { "status": "complete", "file": "~/ai-content-system/output/{slug}-research.md", "approved_topics": 8 },
  "scripts": { "status": "confirmed", "file": "~/ai-content-system/output/{slug}-scripts.md", "count": 10, "sf_numbers": [12, 13, 14] },
  "recording": { "status": "complete", "filmed": [12, 13, 14] },
  "blog": { "status": "published", "highlevel_post_id": "...", "url": "...", "publish_date": "2026-07-10" },
  "hand_raisers": { "status": "uploaded", "manifest": "~/ai-content-system/output/hand-raisers/manifest.json", "media_ids": ["..."] },
  "newsletter": { "status": "scheduled", "send_date": "2026-07-12", "campaign_ref": "..." },
  "social": { "status": "scheduled", "post_date": "2026-07-11", "post_ids": ["..."], "platforms": ["facebook", "instagram", "linkedin", "tiktok"] },
  "ads": { "status": "pending", "review_date": "2026-07-17", "source_post_ids": [], "ad_refs": [] }
}
```

Rules:
- **Read state first** on every invocation. If `~/ai-content-system/campaigns/` has campaigns, list any that are mid-flight before starting a new one.
- **Write state after every stage transition** and after capturing any external ID (HighLevel post ID, media ID, social post IDs).
- All dates are computed from `blog.publish_date` (Day 0) the moment the blog is published or scheduled: social = Day +1, newsletter = Day +2, ads review = Day +7.

---

## Invocation Routing

Parse `$ARGUMENTS`:

| Input | Action |
|---|---|
| A topic (e.g. "AI scheduling for plumbers") | Start a new campaign at Stage 1 |
| `status` | Show the dashboard for all campaigns (see Status Dashboard) |
| `resume` or `resume {slug}` | Load state, announce current stage, continue from the next incomplete step |
| `research`, `scripts`, `record`, `derive`, `publish`, `social`, `ads` | Jump to that stage of the active campaign (validate prerequisites first) |
| Empty | If exactly one campaign is mid-flight, resume it. Otherwise show the dashboard and ask which campaign or topic to work on. |

**Prerequisite validation when jumping stages:** each stage requires the prior stage's status to be complete/confirmed. If it isn't, say what's missing and offer to run the missing stage first. Never publish derivatives from unconfirmed scripts.

**Date-aware resume:** when resuming, compare today's date against the scheduled dates in state. If `ads.review_date` has passed and `ads.status` is `pending`, lead with that: "Ads review was due {date} — want me to pull the stats now?"

---

## Stage 1 — RESEARCH (topics + outliers)

1. Read `~/.claude/skills/topic-researcher/SKILL.md` and follow it to produce scored, deduplicated outlier topic cards for the campaign topic.
2. Supplement with the pain-point research pipeline:
   ```bash
   python3 ~/.claude/skills/last30days/scripts/last30days.py "{TOPIC}" --emit=compact 2>&1
   ```
   plus WebSearch queries ({TOPIC} frustration / biggest challenges / pain points, excluding reddit.com, x.com, twitter.com).
3. If `~/.config/notion-content/config.json` has `inspiration_data_source_id`, query the Inspiration Library for validated findings on this topic and weight them above fresh research.
4. Save to `~/ai-content-system/output/{slug}-research.md`. Present the topic cards and get the user's approval on which topics move forward.
5. **Gate:** user approves topics → set `research.status = complete`, advance to Stage 2.

## Stage 2 — SCRIPTS

1. Read `~/.claude/skills/content-scripting/SKILL.md`. Feed the approved topics and pain points in directly (start at its outlier-checklist step — do not re-research).
2. Write the scripts with hook variations and series groupings. Save to `~/ai-content-system/output/{slug}-scripts.md`.
3. Push scripts to the Notion Script Library if configured (per content-scripting's own push step). Record the SF numbers in campaign state.
4. **Gate — explicit confirmation required.** Show the scripts and ask the user to confirm them. Iterate (rewrites, hook swaps via `~/.claude/skills/hooks/SKILL.md`) until they confirm. Only then set `scripts.status = confirmed`. Nothing downstream may run from unconfirmed scripts.

## Stage 3 — RECORD

Recording happens off-screen — the user films the confirmed scripts. Your job is tracking, not filming:

1. Tell the user which scripts are ready to film (titles + SF numbers).
2. As they report progress ("filmed 12 and 13"), read `~/.claude/skills/content-pipeline/SKILL.md` and update statuses in the Notion Script Library.
3. If the user shares recordings or wants captions/transcripts, use `~/.claude/skills/transcript/SKILL.md`.
4. **Gate:** user says recording is done (or explicitly wants to proceed while filming continues) → set `recording.status = complete`, advance.

The user does not have to sit in this stage: Stage 4 derivatives are generated from the *scripts*, so they can be drafted while filming is still underway. Publishing (Stage 5) should wait for the user's go-ahead.

## Stage 4 — DERIVE (blog, hand raisers, newsletter)

Generate all three derivative formats from the confirmed scripts. Draft everything first; nothing is pushed to HighLevel until Stage 5.

1. **Blog post** — Read `~/.claude/skills/blog/SKILL.md` and run its write flow using the scripts and research as source material (answer-first formatting, sourced stats, schema). Save the draft to `~/ai-content-system/campaigns/{slug}/blog.md`. If a richer repurpose is useful, `~/.claude/skills/blog-repurpose/SKILL.md` handles per-platform variants later — the blog itself comes from the blog skill.
2. **Hand raisers** — Read `~/.claude/skills/hand-raiser/SKILL.md`. Generate one hand raiser PDF per script (or per series if the user prefers) via `pdf_generator.py`. Keep the content JSONs and PDFs in `~/ai-content-system/output/hand-raisers/`.
3. **Newsletter** — Read `~/.claude/skills/newsletter/SKILL.md` for its template selection and writing rules (subject variants, preview text, body rules). Generate the email HTML + metadata JSON. The *send platform* for this pipeline is HighLevel, not Beehiiv — generation follows the newsletter skill, delivery happens in Stage 5.
4. Show the user the blog draft, hand raiser list, and newsletter draft. **Gate:** user approves the derivative set → advance to Stage 5.

## Stage 5 — PUBLISH to HighLevel (Day 0)

Everything in this stage goes through the shared HighLevel handler. Read `~/.claude/skills/highlevel-api/SKILL.md` and use `HighLevelHandler.from_env()` — never raw requests. Confirm `HIGHLEVEL_BEARER_TOKEN` and `HIGHLEVEL_LOCATION_ID` (or OAuth) are configured before starting; if not, stop and tell the user what's missing.

Ask the user for the blog publish date if they haven't given one (default: today). That date becomes **Day 0** — write it to state and compute social (+1), newsletter (+2), and ads review (+7) dates immediately.

1. **Publish the blog:**
   - `handler.blogs.posts.create_post(...)` (inspect the registry for exact action names — `handler.registry.list_actions("blogs", "posts")`). Resolve the blog site/author/category IDs via the registry's list actions rather than asking the user.
   - Set it live on Day 0 (publish now, or scheduled if the date is in the future and the API supports it — otherwise publish on the day).
   - Capture the post ID and public URL into state.
2. **Hand raisers → Media Storage:**
   - Upload each PDF: `handler.media_storage.medias.upload_file(...)`.
   - Capture every returned media ID + URL.
   - **Update the manifest JSON** at `~/ai-content-system/output/hand-raisers/manifest.json`: one entry per hand raiser with `{ "sf": N, "title", "pdf_path", "highlevel_media_id", "url", "campaign": "{slug}", "uploaded": "{date}" }`. Merge with existing entries — never clobber other campaigns' records. This manifest is what funnels, workflows, and CTAs reference, so it must be updated in the same step as the upload.
   - Write the delivery URLs back to the Notion Script Library pages if configured.
3. **Newsletter → scheduled for Day +2:**
   - Build the email in HighLevel from the Stage 4 draft: inspect `handler.registry.list_actions("email", "campaigns")` / `("email", "templates")` and create the template + campaign/schedule. Use HighLevel's merge-tag syntax (e.g. `{{contact.first_name}}`) — swap any Beehiiv-style tags from the draft.
   - Schedule the send for **Day +2**. If the API surface doesn't expose scheduling for the user's plan, create the draft, tell the user exactly what to click and when, and record `newsletter.status = "draft-needs-manual-schedule"` with the target date.
   - Include the blog URL and the hand raiser delivery URL(s) from the manifest as the CTAs.
4. Update state: `blog.status = published`, `hand_raisers.status = uploaded`, `newsletter.status = scheduled`, and report all URLs/IDs.

## Stage 6 — SOCIAL (Day +1)

1. **Draft the posts.** From the scripts and blog, write per-platform post copy (captions, hooks, hashtags, CTA keywords). Save to `~/ai-content-system/campaigns/{slug}/social-posts.md`.
2. **Create the visuals in Hyperframes.** Hyperframes is an external design tool — you cannot drive it directly. Produce a creative brief per post (headline, supporting text, visual direction, format/dimensions per platform) and hand it to the user to build the frames in Hyperframes. Ask them to export the finished images/videos into `~/ai-content-system/campaigns/{slug}/assets/`. If the user doesn't use Hyperframes for a given post, offer `~/.claude/skills/carousel-gen/SKILL.md` (carousels) or `~/.claude/skills/nano-banana/SKILL.md` (AI images) as in-repo fallbacks.
3. **Upload to Social Planner** once assets exist in the folder:
   - Upload each asset via `handler.media_storage.medias.upload_file(...)`.
   - Get connected accounts: the social_planner `account` child (`handler.registry.list_actions("social_planner", "account")`). "All available platforms" means every connected account — list them back to the user before scheduling so nothing posts somewhere unexpected.
   - Create one post per platform with `handler.social_planner.post.create_post(...)`, attaching the media URLs and platform-specific copy, **scheduled for Day +1**.
   - This is a non-draft, multi-account publish: per the highlevel-api skill's rules, pass explicit `accountIds` (from the accounts you just listed and the user acknowledged) — never let a resolver blanket-post by accident.
4. Record post IDs, platforms, and the post date in state. Set `social.status = scheduled`.
5. Remind the user: "Ads review is {Day +7 date} — run `/master ads` then, and I'll pull the last two weeks of stats."

## Stage 7 — ADS (Day +7)

Runs a week after the blog post (state has the date; surface it on any resume after it passes).

1. **Pull performance.** Via the highlevel-api handler: `handler.social_planner.statistics.get_statistics(...)` for the connected accounts over the **previous two weeks**. If statistics are thin for some platform, supplement with whatever the user can export/paste from that platform's native analytics.
2. **Rank the posts** from the last two weeks (this campaign's and any others in the window — the user asked for best performers overall). Rank on engagement rate first (interactions ÷ reach), tie-break on reach. Present a short table: post, platform, reach, engagement, and your pick(s).
3. **Turn the winner(s) into ads:**
   - Read `~/.claude/skills/ads-creative/SKILL.md` for creative quality rules, then the platform sub-skill matching where the winning post lives (`~/.claude/skills/ads-meta/SKILL.md`, `ads-tiktok`, `ads-linkedin`, `ads-google`/`ads-youtube`).
   - Build the ad package: recommended objective, audience, placement, budget guidance (read `~/.claude/skills/ads-budget/SKILL.md` if the user wants budget help), plus ad copy variants derived from the winning post's hook and the campaign's hand raiser/blog CTAs.
   - Winning organic post → ad mapping: keep the proven hook verbatim, tighten copy to platform limits, swap the organic CTA for the lead-capture CTA (hand raiser landing page or blog URL from the manifest).
4. **Gate — explicit confirmation required before anything spends money.** Present the ad package and get sign-off. Ad platforms are managed outside HighLevel, so deliver the package as ready-to-paste campaign specs (and set up the HighLevel side — landing page, tags, workflows — via the hand-raiser/highlevel-api flows if the ad drives to a HighLevel funnel).
5. Set `ads.status = delivered` with the source post IDs, and mark the campaign `stage = COMPLETE`.

---

## Status Dashboard

For `status` (or ambiguous resume), read every `campaign.json` under `~/ai-content-system/campaigns/` and render:

```
CAMPAIGNS

ai-scheduling-service-businesses      Stage 6/7 — SOCIAL
  Blog: published Jul 10 → https://...
  Newsletter: sends Jul 12
  Social: 4 platforms scheduled Jul 11
  Ads review due: Jul 17

restaurant-ai-tools                   Stage 2/7 — SCRIPTS (awaiting confirmation)
  10 scripts drafted — waiting on your review
```

Flag anything overdue (past-date pending items) at the top.

---

## Sub-Skill Map

Load only what the current stage needs, via `Read` on the skill file. Follow the loaded skill's own output formats — they are authoritative for their step.

| Stage | Skill files |
|---|---|
| 1 Research | `topic-researcher`, `last30days` (script), `inspiration-library` |
| 2 Scripts | `content-scripting`, `hooks` |
| 3 Record | `content-pipeline`, `transcript` |
| 4 Derive | `blog` (+ `blog-repurpose` if needed), `hand-raiser`, `newsletter` |
| 5 Publish | `highlevel-api` |
| 6 Social | `highlevel-api`, `carousel-gen` / `nano-banana` (Hyperframes fallbacks) |
| 7 Ads | `highlevel-api` (stats), `ads-creative`, `ads-meta`/`ads-tiktok`/`ads-linkedin`/`ads-google`/`ads-youtube`, `ads-budget` |

All paths are `~/.claude/skills/{name}/SKILL.md` (or `~/.codex/skills/` under Codex — check which exists).

---

## Hard Rules

1. **Never skip the script confirmation gate.** Derivatives, publishing, and social all trace back to confirmed scripts.
2. **Never publish or schedule to HighLevel without the highlevel-api handler** and confirmed auth. No raw HTTP.
3. **Never blanket-post to social accounts implicitly.** List connected accounts, get acknowledgment, pass explicit accountIds.
4. **Never launch ad spend without explicit sign-off** on the final package.
5. **Always write state after each step that creates an external artifact.** A crashed session must be resumable from `campaign.json` alone.
6. **Dates come from Day 0.** If the blog date moves, recompute and re-schedule the newsletter (+2), social (+1), and ads review (+7) — and say so.

## Conversation Style

Same voice as content-master: casual, direct, proactive. Announce stage transitions in one line ("Scripts confirmed — drafting the blog, hand raisers, and newsletter now."). Compress transitions the user already implied. Max one clarifying question before acting; state your assumptions instead of asking when you can reasonably infer.
