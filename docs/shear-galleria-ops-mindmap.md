# Shear / Galleria Workspace — Ops Mind Map

**Business requirements, included in this repo.**
Recreated 2026-11-06 America/Louisville from Enzo’s project brief.

This is not a published site and not an install log. **Business facts in the table are user-supplied and were not independently verified when this starter was written.**

The code in this repo is a local starter that follows the map. It does not prove the facts. Module definitions live in `config/modules.toml`.

## Who / where (user-supplied)

| Fact | Value | Source |
|---|---|---|
| Owner | Shear (face of the business) | Enzo brief |
| Instagram | @shearfades | Enzo brief |
| Phone (confirmed) | +1 502-341-4647 | Enzo correction 2026-11-06 |
| Space | Galleria Workspace / The Creative Space | Enzo brief |
| Address | 1734 S 4th Street, Louisville KY 40202 (~two blocks from One Fourteen) | Enzo brief |
| Website | galleriaworkspace.com (currently a bare placeholder) | Enzo brief |
| Offices | 17 private offices (Studio through Crown tiers) | Enzo brief — **business fact user supplied; not independently verified here** |
| Conference | ~700 sq ft conference room, bookable by the hour | Enzo brief — user-supplied |
| Virtual office | Plans from **$75/month** (only price Enzo supplied; do not invent other rates) | Enzo brief |
| Access | 24/7 key fob | Enzo brief — user-supplied |
| Site gaps | No office prices on site, no contact info, no footer, tour button has no real link | Enzo brief |

## Principle

**Shear is the face. Agents do the grunt work.**

Hard rules for every agent/branch:

1. Never spend money without Shear’s OK.
2. Never contact anyone (tenant, prospect, vendor, hire, DM reply that reaches a stranger) without Shear’s OK — unless Shear has already approved that exact action or a standing rule for that lane.
3. Everything reversible except what Shear explicitly approves.
4. Short, one-next-step communication with Shear (group text is low-pressure; these docs are the deep reference).

The starter enforces (1) and (2) locally: spend and outbound stay pending until a person records approval, and execute still does not transmit or charge. It cannot enforce them on a system this repo does not call.

## Codebase / roles

| Piece | Role |
|---|---|
| Repo | https://github.com/Chefzo/shear-gary |
| **Gary** | Local automation + messaging on Shear’s **M1 Mac** at the space (Mac Messenger pattern: local BlueBubbles-style bridge). Reports through Rhonda. |
| **Claude Code** | Coding / building on the same machine. **Complementary to Gary, not competing.** |
| Rhonda | Relay / ops coordinator; Inkbox group-text fallback when Mac Messenger cannot send. Rhonda’s working group is not Gary installed. |

## Eight branches (build target)

### Core five

1. **Maintenance agent**
   Own phone line / chat for tenants. Triage **emergency** (burst pipe, HVAC down) vs **routine** (flickering light, filter, bulb). Log with photo if sent. Ping Shear or property manager only when a human is needed. Help schedule routine work.

   Starter status: local intake, photo metadata, phrase triage, audit, and a pending human draft. No dedicated number, no live ping, no dispatch.

2. **Barbershop booking agent**
   Answer DMs, check calendar, lock slots, send confirmations, waitlist texts when slammed. (All outbound contact still needs Shear OK until he sets standing rules.)

   Starter status: definition only.

3. **Tour scheduling**
   Self-serve link for prospects, auto-reminder, follow-up asking if they want to move in.

   Starter status: definition only. Website draft explains the missing link. No scheduler.

4. **Tenant marketing**
   Auto-generate Instagram and Google Business posts from a content calendar using Shear’s existing photos; lean on his “opportunity for growth” angle. Publish only with Shear OK.

   Starter status: definition only. Nothing publishes.

5. **Website rebuild**
   Hero with real photo, live availability grid, embedded tour scheduler, actual pricing, maintenance/tenant portal link in footer. **Draft sitemap and copy first** before any deploy.

   Starter status: `docs/website/sitemap.md` and `docs/website/copy.md`. Not published. No deploy.

### Growth branches

6. **Lead gen**
   Warm barber prospects from Instagram, Booksy, barber schools, Mizutani network. Track, cadence follow-ups, flag best fits for Shear to close personally. No cold outreach without Shear OK.

   Starter status: definition only. No prospect list and no scraping.

7. **Hiring agent**
   Post openings, screen portfolios, structured interviews against a Shear-set rubric, surface top 2–3 for face-to-face. Shear never writes a rejection email (agent drafts; Shear decides).

   Starter status: definition only. No rubric and no applicants.

8. **Online academy**
   Courses, tools/skills install guidance, live + online classes, tutorials/content, editing software setup. Shear already has a school with courses — extend, don’t invent a fake catalog.

   Starter status: definition only. No catalog was supplied, so none is invented.

## Mind-map sketch (text)

```
Shear (face) ── OK gates: spend / contact / irreversible
    │
    ├── Gary (M1 Mac) ── local automation + messaging
    │     └── Claude Code ── coding / building (complementary)
    │
    ├── 1 Maintenance (dedicated line)     starter: local intake
    ├── 2 Barbershop booking               starter: defined
    ├── 3 Tour scheduling                  starter: defined
    ├── 4 Tenant marketing                 starter: defined
    ├── 5 Website (sitemap/copy first)     starter: draft docs
    ├── 6 Lead gen                         starter: defined
    ├── 7 Hiring                           starter: defined
    └── 8 Online academy                   starter: defined
```

## Group-text note (reference)

Keep live iMessage short: one intro, then one next step at a time. Point Shear at this file or `docs/SETUP-GUIDE.md` only if he asks for depth. Do not paste this whole mind map into the group. This repo does not send that message.

## Open / blocked (honest)

- BlueBubbles on Shear’s M1 is not verified. The adapter in this repo does not connect.
- Enzo’s separate Mac has a Contact Key Verification send block. That is not evidence of Shear’s Mac.
- The dedicated maintenance number is not chosen.
- Office tier prices beyond virtual office from $75/month were not supplied.
- Seven modules have no workflow. The website module is an unpublished draft.
- On-site checklist boxes in `docs/SETUP-GUIDE.md` stay open.
