# Gary on Shear’s M1 Mac — Setup Guide (honest checklist)

**Included in this repo as a business-requirements checklist.**
Recreated 2026-11-06 America/Louisville from Enzo’s notes.

This is a checklist and architecture note. It is **not** a claim that BlueBubbles, Mac Messenger, or Gary are installed and working on Shear’s machine. Every box below stays open until someone checks it **on that Mac**.

The product starter that belongs with this checklist is the rest of this repository: local maintenance intake, a dry-run adapter boundary, an approval gate, and eight module definitions. Running the starter on a development machine does not tick these boxes.

## Goal

Get **Gary** running on Shear’s **M1 Mac desktop** at Galleria Workspace so it can:

- Handle **local automation + messaging** (Mac Messenger pattern).
- Work **alongside Claude Code** (coding/building), not against it.
- Stay under Shear’s face / agents-handle-the-rest principle (see `docs/shear-galleria-ops-mindmap.md`).

## Roles (do not blur)

| Agent / tool | Owns | Does not own |
|---|---|---|
| **Gary** | Local automation, digests, drafts, messaging bridge on the M1 | Writing the product codebase as the primary builder |
| **Claude Code** | Coding, scaffolding, refactors, installs Shear approves | Competing with Gary for “who is the agent” |
| **Rhonda (Inkbox)** | Relay group with Enzo + Shear when Mac send path is blocked | Replacing Gary on Shear’s desktop |
| **Shear** | Face, final OK on spend/contact/irreversible | Grunt work agents should absorb |

Rhonda’s Inkbox group can send on its own identity. That working group is **not** Gary installed on Shear’s M1.

## Messaging paths (researched — be honest)

### A. Mac Messenger / BlueBubbles (intended local pattern)

- Pattern target: same idea as Enzo’s **Mac Messenger** bot on the MacBook Air — local BlueBubbles-style API, read threads, **draft** replies, send only on explicit yes.
- **Current research status (Enzo’s Air bridge, 2026-11-06):** Contact Key Verification (**CKV**) left **on** by owner choice. That **blocks sending** even when read may work. Treat CKV as a **current send block on Enzo’s Air**, not as the state of Shear’s M1, and not as a solved install.
- **Do not invent:** “BlueBubbles is installed and verified on Shear’s M1.” Until Shear (or Enzo with Shear’s OK) confirms install, port, and a successful send test, mark those steps **unchecked**.
- In this repo the BlueBubbles adapter is optional code with **no client**. `config/gary.example.toml` sets `enabled = false`. Turning the flag on still does not open a connection.

### B. Inkbox Rhonda group (fallback that actually sends — separate from Gary)

- Supported create/send route from Rhonda’s Inkbox identity (`@zpmadmin`, dedicated iMessage **+1 623-206-3101**): Inkbox iMessage with Enzo + Shear as recipients → new group.
- Confirmed Shear number for routing: **+1 502-341-4647** (Enzo correction; ignore earlier 502-384-0440).
- SMS to Shear is **not** ready (`recipient_not_opted_in`); use **iMessage**, not SMS.
- Saved auto-send rules cover Enzo/Sienna work — **not** Shear. Any first (or next) message still needs Enzo’s send approval before it goes out.
- This starter does not call Inkbox. Keep group texts **short**: one next step. Point here for depth.

## Checklist — Shear’s M1 (all unverified until checked off on-site)

Copy this and tick only what is actually done.

### Machine / access

- [ ] Shear’s M1 Mac is on, signed in, and Shear has approved agent work on it
- [ ] Gary bot identity exists and is the one Shear expects (local agent id for Gary is separate from this file)
- [ ] Claude Code available for build work; Shear understands Gary ≠ Claude Code

### Local messaging bridge (optional until working)

- [ ] BlueBubbles (or equivalent) installed on **this** Mac — **not verified in research**
- [ ] Local API reachable (host/port recorded by Shear/Enzo — do not store secrets in this file)
- [ ] Read path tested (list conversations / latest message)
- [ ] CKV / security settings reviewed with Shear **on this Mac**
- [ ] Send path tested with Shear’s OK on exact text

### Repo / code

- [ ] Remote https://github.com/Chefzo/shear-gary accessible to Shear from the M1
- [ ] Shear can pull this repo on the M1
- [ ] Local clone path decided by Shear + Claude Code

### Ops readiness

- [ ] Shear OK’d principle: face vs agents; no spend/contact without his OK
- [ ] Maintenance “own line” number strategy decided (not invented here)
- [ ] Content for website starts as **sitemap + copy draft** only (`docs/website/`)
- [ ] Pricing: only user-supplied figure so far is virtual office **from $75/month** — do not invent office tier prices

## Commands once the repo is on the M1

Prerequisites: Python 3.11+ and git. No pip packages. Do not install BlueBubbles as part of these commands.

```sh
git clone https://github.com/Chefzo/shear-gary.git
cd shear-gary
python3 --version
python3 -m unittest discover -s tests -v
python3 -m gary config-check
python3 -m gary demo
```

`python3 -m gary demo` writes only under `data/demo` and does not send or spend. The next human step is to read that output with Shear before any messaging bridge is configured.

## First week build order (suggestion, not a promise that it is done)

1. Confirm group channel (Inkbox Rhonda fallback if Mac send is blocked). This repo does not send that message.
2. Sitemap + website copy draft. A draft is in `docs/website/`. It is not published.
3. Maintenance triage rules + log shape (photos optional). The starter implements this locally.
4. Tour self-serve flow sketch. Module definition only.
5. Booking / lead / hiring / academy — only after Shear prioritizes. Definitions only.

## What this guide does not claim

- That BlueBubbles works on Shear’s M1 today.
- That Mac Messenger can send while CKV is on, on any machine.
- That Enzo’s Air and Shear’s M1 are in the same state.
- That Rhonda’s Inkbox group means Gary is installed.
- Any passwords, API keys, tokens, or private BlueBubbles credentials. Keep those out of this file and out of the repo.

## Related files

- Ops mind map: `docs/shear-galleria-ops-mindmap.md`
- Architecture: `docs/architecture.md`
- Sample config: `config/gary.example.toml`
- Module definitions: `config/modules.toml`
- Website draft: `docs/website/sitemap.md`, `docs/website/copy.md`
