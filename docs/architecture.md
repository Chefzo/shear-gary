# Gary local architecture

This is the map of the starter in this repo. It is the thing Claude Code can keep building. It is not a claim that BlueBubbles, a dedicated phone line, or any of the eight branches are live on Shear's M1.

Business facts in `docs/shear-galleria-ops-mindmap.md` and `docs/SETUP-GUIDE.md` are **user-supplied**. They were not independently verified when this starter was written.

## Roles

| Who | Owns |
|---|---|
| Shear | Face of the business. OK on spend, contact, and irreversible steps. |
| Gary | Local automation and messaging on Shear's M1 Mac at Galleria Workspace / The Creative Space. |
| Claude Code | The codebase. Complementary to Gary. |
| Rhonda | Separate Inkbox relay. Not this install. |

## What runs

```
local CLI  or  ChannelAdapter.poll()
        |
        v
MaintenanceIntake.accept()
        |
        +-- Store request row
        +-- Store photo metadata (optional file copy under data/photos)
        +-- triage.classify()     emergency | routine | needs_review
        +-- audit log
        +-- if a human is required: pending outbound draft
        |
        v
person: gary approve --by "<name>"     (records a decision, does not send)
        |
        v
person: gary execute <approval>
        |
        +-- outbound_message -> adapter.send() -> dry_run or disabled, delivered false
        +-- spend            -> local record, no payment connector, delivered false
        |
        v
audit log (append-only through this API)
```

Automatic dispatch is not a function. Asking for any action other than `outbound_message` or `spend` is refused and audited.

## Layout

| Path | Role |
|---|---|
| `gary/cli.py` | Local interface |
| `gary/intake.py` | Maintenance workflow |
| `gary/triage.py` | Editable phrase lists |
| `gary/adapters.py` | Channel boundary. Mock and a disabled BlueBubbles shell |
| `gary/gate.py` | Human approval gate |
| `gary/store.py` | SQLite: requests, photo metadata, approvals, attempts, audit |
| `gary/demo.py` | Scripted demo |
| `config/gary.example.toml` | Sample config, no secrets |
| `config/modules.toml` | Eight business modules |
| `docs/website/` | Unpublished sitemap and copy |
| `data/` | Created at runtime. Gitignored |

The database enforces `delivered = 0` on attempts, and attempt mode is limited to `dry_run`, `disabled`, or `blocked`.

## Channel boundary

`ChannelAdapter` is `poll()` plus `send()`.

- `mock` is the sample default. `poll()` returns an in-memory inbox (empty in the CLI). `send()` returns a dry-run and does not transmit.
- `bluebubbles` is optional. `enabled = false` in the sample. `enabled = true` still has no client: `poll()` returns nothing and `send()` returns `disabled`. The package does not import an HTTP or socket client.
- Inkbox is Rhonda's path. Setting it as `adapter.name` is a config error.

Enzo's Mac Messenger Contact Key Verification send block is about Enzo's machine. It is not evidence about Shear's M1. The setup checklist stays unchecked until someone ticks it on that Mac.

## Triage

`gary/triage.py` is the list Shear and Claude Code edit.

- Emergency phrases, including the user-supplied examples "burst pipe" and "HVAC down", classify as `emergency`, escalate, and queue a local draft.
- Routine phrases, including "flickering light", "filter", and "bulb", classify as `routine` and do not queue a draft.
- Anything else, including paraphrases such as "HVAC isn't working" or a bare "leak", classifies as `needs_review` and escalates.
- Emergency wins when both kinds of phrase are present.

The limitation stored on every request: phrase-list triage is not a life-safety system, not emergency services, and not a promise that danger will be detected. Gary does not dispatch help.

## Approval gate

Every outbound message and every spend request is stored as `pending`.

1. `approve` or `deny` records a person. `--by` is a label, not a login.
2. `execute` is a second command.
3. Pending or denied items are blocked. The audit records `execute_blocked`. No attempt row is written.
4. An approved message calls the adapter. The sample adapter's result is `dry_run` and `delivered: false`.
5. An approved spend writes the same kind of non-delivery. The detail says no spend connector is installed.
6. A result with `delivered: true`, or a mode outside the allowlist, is refused and not stored.

There is no config key that turns this off. `approvals.require_human` must be `true`. Unknown config keys, including passwords and tokens, fail closed.

## Modules

`config/modules.toml` is the definition list. Order is fixed:

1. `maintenance` — workflow `maintenance_intake` (runs)
2. `barbershop_booking` — `none`
3. `tour_scheduling` — `none`
4. `tenant_marketing` — `none`
5. `website_rebuild` — `docs_only` (markdown only, not a site)
6. `lead_gen` — `none`
7. `hiring` — `none`
8. `online_academy` — `none`

`App.run_module()` raises `ModuleNotRunnable` for every id except `maintenance`.

## M1 prerequisites and commands

On Shear's M1, from a clone of this repo:

- macOS on that Mac, with Shear's OK to use it
- Python 3.11 or newer (`python3 --version`)
- Git
- No pip packages, no virtualenv, no BlueBubbles install, no paid account

Run from the repo root:

```sh
python3 --version
python3 -m unittest discover -s tests -v
python3 -m gary config-check
python3 -m gary modules
python3 -m gary demo
```

`make test`, `make check`, and `make demo` call those same commands.

Useful follow-ups, still local:

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

`samples/flicker.txt` is a stand-in file, not a tenant photo. `gary demo` resets only `data/demo` (or the `--data-dir` you pass): its sqlite file and its `photos/` folder.

## For Claude Code

Build the next real slice only after Shear picks it. Keep the adapter boundary. Do not mark a module runnable by flipping a word in TOML: the loader only allows `maintenance_intake` on `maintenance`.

A sensible order when Shear asks:

1. Walk the demo with Shear and edit `gary/triage.py` in his words.
2. Decide the dedicated maintenance number. Do not invent one.
3. A read-only BlueBubbles poll can be a later adapter method. Ship it disabled by default, with tests that the default config still does not open a socket.
4. Sending stays a separate, explicit change after Shear tests his own Mac, including Contact Key Verification. Enzo's Air is a different machine.
5. Pick one of the defined modules and implement one dry-run workflow. Do not scaffold eight apps.

## Intentionally absent

- Network clients (`urllib`, `requests`, sockets, subprocess)
- Credentials, server URLs, and `.env` loading
- Payments, ads, social posting, scraping, SMS, email, job boards
- A public website, a deploy, DNS, or a launchd service
- A course catalog, office tier prices, or a hiring rubric
- Any promise that emergencies are detected or that help is on the way
