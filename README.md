# Founders Force Multiplier

A complete AI-powered content creation system built for use by Claude Code or Codex and HighLevel. 60 skills across 7 categories — from topic research to script production, SEO audits, ad optimization, blog writing, image generation, and e-commerce CRO.

## What's Included

| Category | Skills | What It Does |
|---|---|---|
| Content Creation | 7 | Topic research, script writing, hook frameworks, inspiration library, pipeline management |
| Transcript & Lead Magnets | 2 | Video transcript extraction (any platform), PDF lead magnet generator |
| SEO | 13 | Full site audits, technical SEO, schema, content quality, GEO, programmatic SEO |
| Ads | 13 | Multi-platform audits (Google, Meta, LinkedIn, TikTok, Microsoft, YouTube) |
| Blog | 13 | Blog writing, rewriting, analysis, strategy, calendars, schema, repurposing |
| Image Gen & Design | 2 | AI image generation, frontend design |
| E-commerce | 2 | CRO expertise, Shopify store design |

## Quick Start

### 1A. Install Claude Code

```bash
npm install -g @anthropic-ai/claude-code
```
### 1B. Install codex

```bash
npm install -g @openai/codex
```

### 2. Clone This Repo

```bash
git clone https://github.com/wil-kirwan/force-multiplier.git ~/force-multiplier
```

### 3. Install Skills
For Claude:
```bash
cp -r ~/force-multiplier/skills/* ~/.claude/skills/
```
For Codex:
```bash
cp -r ~/force-multiplier/skills/* ~/.codex/skills/
```

### 4. Verify

Open Claude Code and type `/hooks` — you should see the skill activate.

## Updating

Claude:
```bash
cd ~/force-multiplier && git pull && cp -r skills/* ~/.claude/skills/
```

Codex:
```bash
cd ~/force-multiplier && git pull && cp -r skills/* ~/.codex/skills/
```

One command. Instant updates.

## Configuration

Most skills work out of the box. For full functionality, connect these integrations:

| Integration | Required For | Setup |
|---|---|---|
| Notion MCP | Content pipeline, inspiration library |  |
| Google Docs/Drive | Script export, PDF hosting |  |
| Supadata API | Video transcript extraction |  |
| Gemini API | Image generation | |
|Highlevel MCP | CRM integration, Blog posting, Social Media Posting | |

Config templates are in `config-templates/`.

## Repo Structure

```
force-multiplier/
├── skills/              # 60 Claude Code/Codex skills (and counting!)
├── scripts/             # Shared Python scripts (PDF gen, Google Docs, Drive)
├── config-templates/    # Example config files with placeholders
├── lead-pages-starter/  # Vercel landing page template for lead capture
├── newsletter/          # Helper Scripts for newsletter, including scripts to run newsletter through beehiiv and HighLevel
└── output/              # Default output directory
```

## Getting Help

Full setup guides, video walkthroughs, and community support are available through the [Founders Force Multiplier Community](https://community.x20.io).

## License

For use by active community members only. Do not redistribute.
