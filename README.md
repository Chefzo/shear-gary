# Gary — local starter for Shear’s M1

Local-first maintenance intake for Galleria Workspace / The Creative Space. Gary runs on Shear’s Mac. Claude Code builds this repo. Shear is the face: no spending and no contacting anyone without his OK.

This is a starter a person can run and a coding agent can continue. It is not eight production apps, and it is not installed on Shear’s Mac by being in git.

Business facts in `docs/shear-galleria-ops-mindmap.md` and `docs/SETUP-GUIDE.md` are **user-supplied**. They were not independently verified here. The setup checklist is not an install log. Every box there is still open.

## Implemented and placeholder

| Piece | In this repo |
|---|---|
| Maintenance intake | Runs locally: channel label, request text, photo metadata, phrase triage |
| Emergency vs routine | Phrase list in `gary/triage.py`. Unknown wording becomes `needs_review` |
| Human escalation | Emergency and needs-review queue a **pending** draft to “Shear or property manager” |
| Audit log | Append-only SQLite log under `data/` |
| Approval gate | Separate `approve` and `execute` steps for every outbound and every spend label |
| Connectors | Mock dry-run by default. BlueBubbles adapter exists and does not connect |
| Eight modules | Defined in `config/modules.toml`. Only maintenance has a workflow |
| Website | Unpublished sitemap and copy in `docs/website/` |
| Barbershop, tours, marketing, lead gen, hiring, academy | Definitions and human gates. No workflow |
| Dedicated phone line, live iMessage, vendor dispatch, payments, publishing | Not built |

Emergency intake does not dispatch anyone. Triage is not a life-safety system and it does not contact emergency services.

## Roles

| Who | Job |
|---|---|
| Shear | Face. Final OK on spend, contact, and irreversible steps. |
| Gary | Local automation and messaging on the M1 at the space. |
| Claude Code | Writes and changes this code. Complementary to Gary. |
| Rhonda | Separate Inkbox relay. A working Rhonda group is not this install. |

Enzo’s Mac Messenger has a Contact Key Verification send block. That describes Enzo’s Mac, not Shear’s M1. BlueBubbles stays disabled until Shear configures it on the M1.

## M1 prerequisites

- Shear’s M1 Mac, only after Shear has approved work on it
- Python 3.11 or newer (`python3 --version`). The standard library is enough
- Git, to clone this repo
- No pip install, no virtualenv, no BlueBubbles install, no paid service

Confirm the interpreter before anything else. A system `python3` older than 3.11 will not run this package. Install a newer Python only if Shear wants that on the machine; this repo does not install it.

## Start, test, demo

From the repo root:

```sh
python3 --version
python3 -m unittest discover -s tests -v
python3 -m gary config-check
python3 -m gary modules
python3 -m gary demo
```

The same test and demo entry points:

```sh
make test
make check
make demo
```

`gary demo` resets `data/demo` only (the sqlite file and the `photos/` directory inside it), prints a routine request, an emergency, an unclassified request, a blocked send, a dry-run send, and a dry-run spend, and ends with:

```text
RESULT delivered=0 spent=0 dispatched=0 dry_run_records=2
```

The demo’s decision label `Shear (demo)` is a string in the local database. It is not Shear’s real approval.

Record one request with the stand-in file `samples/flicker.txt` (not a tenant photo):

```sh
python3 -m gary intake \
  --sender "studio 4 tenant" \
  --body "Flickering light in the office." \
  --photo samples/flicker.txt

python3 -m gary list
python3 -m gary show <request-id>
python3 -m gary approvals
python3 -m gary approve <approval-id> --by "Shear"
python3 -m gary execute <approval-id>
python3 -m gary audit
```

`approve` records the person. `execute` is the second step. With the sample config, execute writes a dry-run or a disabled result and delivers nothing. `data/` is gitignored.

`python3 -m gary --help` lists `draft`, `spend`, `deny`, and `poll` as well. `poll` asks the mock adapter and reports `contacted: no`.

## Config

`config/gary.example.toml` is the file the CLI loads. Adapter `mock`. BlueBubbles `enabled = false`. Human approval required. There is no URL and no secret.

`config/modules.toml` is the eight-module configuration. Editing a workflow name to `maintenance_intake` on another module fails the loader. `gary run` is not a command for those modules; `App.run_module()` raises for anything except maintenance.

A local file with a password, token, or `require_human = false` is rejected.

## Safety rules in the code

- Outbound messages and spend requests start `pending`.
- Execute on a pending or denied item is blocked and audited.
- Spend execute records: no spend connector, nothing purchased.
- Attempt rows cannot be stored with `delivered = 1`.
- Dispatch is refused.
- Photo filenames are stripped to a basename inside `data/photos`.
- The data directory must sit under the working directory or the system temp directory.

## Docs

- [Architecture](docs/architecture.md) — boundary, triage, gate, and what Claude Code should build next
- [Setup guide](docs/SETUP-GUIDE.md) — M1 checklist, still unchecked
- [Ops mind map](docs/shear-galleria-ops-mindmap.md) — user-supplied business requirements
- [Sitemap draft](docs/website/sitemap.md) and [copy draft](docs/website/copy.md) — do not publish

## Next step on the M1

Clone this repo on Shear’s M1, run the five commands in **Start, test, demo**, and read the demo with Shear. Leave BlueBubbles disabled. Do not approve a real tenant message from the demo database.

## Still blocked

- BlueBubbles is not verified on Shear’s M1. This repo will not connect even if the flag is turned on.
- Enzo’s Contact Key Verification setting is not Shear’s Mac.
- No dedicated maintenance number has been chosen.
- Office prices other than virtual office from $75/month were not supplied.
- The website draft is not a site.
- Booking, tours, marketing, lead gen, hiring, and the academy have no workflow and no external accounts.
- Rhonda’s Inkbox group is outside this process. This starter does not send through it.
