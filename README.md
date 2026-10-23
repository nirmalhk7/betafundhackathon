# Local Chert integration

Installed packages: `@trychert/facetime@0.1.0-beta.10` and `@trychert/sdk@0.1.0`.
Requires Node.js 22.12+ (22.x), 24.x, or 26.x. Dependencies are pinned in `package-lock.json`.
Restore with `npm ci --ignore-scripts`.

This integration targets the existing LiveKit Cloud agent in project **Chris**:

- Project: `p_3gx7ofwhqg6`
- Agent: `CA_HJ6N6GNSyzsp`; builder: `ab_qrffng10k9f`
- Dispatch name: `assistant-0c8`
- URL: `wss://chris-1zd6fz6o.livekit.cloud`
- [Agent Builder](https://cloud.livekit.io/projects/p_3gx7ofwhqg6/agents/builder/ab_qrffng10k9f?tab=conversation&dashboardAgentId=CA_HJ6N6GNSyzsp)

Existing Cloud agent status is `Running`. Its exported source, revised for
Chert greeting timing and Keenable search, is in [my-agent](my-agent/README.md).
The revised source has not yet replaced production. It preserves model
`openai/gpt-live-1`, Marin voice, original instructions, and audio enhancement.
Model access uses LiveKit Inference; no separate OpenAI API key is required.

Incoming FaceTime calls are bridged by Chert into LiveKit rooms, where Chert
dispatches the named Cloud agent. The agent's dashboard ID and builder ID are
reference metadata; dispatch uses its name, not either ID. The pinned CLI targets
the production deployment. Project selection, CLI login, line assignment, and
LiveKit credentials have been verified. Real call media remains unverified.

## Finish configuration

1. Open `.env.local` in your local editor. Enter your **Chert** project UUID as
   `CHERT_PROJECT_ID` (selected: `f023544a-0950-4373-862c-b044b3a34dec`), plus `LIVEKIT_API_KEY` and `LIVEKIT_API_SECRET` for the
   **Chris** LiveKit project above. Chert's project ID is separate from LiveKit's
   `p_3gx7ofwhqg6`; do not substitute one for the other. `LIVEKIT_URL` and
   `AGENT_NAME` default to the pinned Cloud target, so they can remain blank.
   Conflicting values fail closed. Add service-specific SDK credentials only for
   SDK iMessage or FaceTime identity reads. Keep credentials out of chat and commands.
   The file is ignored by Git and must retain mode `0600`.
2. For an existing Chert project, run `npx --no-install chert login` in your own
   terminal and approve that project in the browser. Do not paste its tokens or
   verification codes into chat. Login, SDK API keys, FaceTime tokens, and LiveKit
   credentials are separate.
3. Wait for the hosted agent's production deployment to become ready. Keep
   `mode: "livekit-cloud"` in `chert-agent.config.json`; no local runtime command
   is needed. Existing agent behavior and contact policies stay with that agent.
4. Run `npm run chert-agent -- setup`, then `npm run chert-agent -- health`.
5. Run `npm run chert-agent -- start` in your terminal. Review the prompt and type
   `YES` only when you approve connecting the selected project line to incoming
   callers using hosted agent `assistant-0c8`. This starts a foreground connector;
   keep the terminal open. LiveKit continues hosting and managing the voice agent.
   Chert may prewarm a LiveKit room and dispatch an agent after this approval;
   provider usage charges may apply.

The requested native CLI setup command for the selected existing project is:

```sh
./node_modules/.bin/chert setup --env-file .env.local --project f023544a-0950-4373-862c-b044b3a34dec
./node_modules/.bin/chert doctor --env-file .env.local --project f023544a-0950-4373-862c-b044b3a34dec --json
```

Chert setup and approved CLI login select project
`f023544a-0950-4373-862c-b044b3a34dec`. LiveKit credentials passed doctor. Austin
Parker is assigned. The latest read-only check now reports calls enabled, a
recent Mac heartbeat, and no session holding the line. Our earlier connector
stopped cleanly after another session took over. Check again before connecting;
do not start duplicate connectors or reset onboarding.

## Required Chert greeting behavior

Before starting this existing agent on the line, verify the implementation:

- Join Chert's waiting room immediately using the registered agent name.
- Wait for the caller before opening a paid model session.
- Watch room metadata for `chert_bridge_ready: true` and greet exactly once on
  that signal, within 10 seconds. Do not greet on participant join alone.
- Publish exactly one unmuted audio track. If video is enabled, its camera
  track must come from the same participant that publishes audio.

`my-agent/src/chert_bridge.py` implements the bridge-ready hook. Five local tests
cover greeting timing, repeated signals, early signals, disconnects, and
cancellation. Existing Builder production code has not yet received this hook.
Ask before deploying changes or placing a call, and keep audio/video unverified
until the owner confirms an actual call. Hosting, inference/model sessions,
and connected providers can incur usage charges.

For a **new** Chert project, first approve account creation and the browser/phone
verification exchange. Then inspect `npx --no-install chert onboard --help` and run
`npx --no-install chert onboard --skip-demo --no-browser --json --wait 0` locally.
Complete verification yourself. Preserve `~/.chert` and resume the same request;
do not use `--restart` after uncertain outcomes. No onboarding has been started.

## Local wrapper commands

Use `npm run chert-agent -- COMMAND`. These are generated local commands.

| Command | Behavior |
| --- | --- |
| `setup` | Reports variable presence, execution mode, and selected agent; no secrets or writes. |
| `health` | Read-only `doctor --json`, SDK context/status/lines/workers. Reports check exit codes; inspect native CLI privately for detailed identity records. Never dispatches `doctor --agent`. |
| `status` | Local connector state plus the same read-only checks. |
| `start` | Requires configured credentials and project, healthy doctor, fresh interactive approval. Starts foreground `chert dev` targeting the hosted agent; local mode can optionally own a runtime. |
| `watch` | Streams redacted event summaries from this wrapper's own running connector over a private local socket. Raw private caller payloads are omitted. |
| `watch imessage` | Returns `capability_pending`; no inbox API is available. |
| `message` | Interactively requests exact E.164 recipient and body, discloses possible charges, then requires fresh `YES`. Saves stable request ID before a single SDK send; never retries. |
| `call` | Returns `capability_pending`; outbound FaceTime is unsupported. |
| `stop` | Sends one SIGINT to wrapper-owned connector and waits for terminal record. Hosted Cloud deployment keeps running; only local mode stops an owned runtime. |

Wrapper output uses JSON Lines with `wrapper_schema_version: 1`, separate from
Chert's `schema_version: 1`. Native event codes and retained-cleanup counts are
preserved in redacted summaries. No raw provider responses, message bodies,
phone numbers, or runtime logs are written to disk.

## Recovery and limitations

- `.chert-agent/pending-message.json` stores only request ID and outcome. Even a
  `queued` receipt means acceptance, not delivery. Reconcile the request with the
  service/operator before removing this guard file for another message. An
  uncertain response must not be retried automatically.
- `stop` waits for `dev_stopped` with `retained: 0` before reporting binding
  release. `cleanup_pending`, retained calls, and `release_failed` require owner/admin
  reconciliation. A durable connector receipt blocks another start after an
  unconfirmed exit. Preserve Chert state and the local receipt during recovery.
- If a crashed process leaves `control.sock`, inspect local processes and reconcile
  server-side cleanup before removing it. Do not use takeover/force as recovery.
- Ctrl+C sends one graceful interrupt. Further interrupts do not force termination.
  There is no automatic restart, service manager, or reboot recovery.
- Stopping a connector does not unassign its phone number or shared allocation.
- Login, identity checks, a healthy doctor, and `call_bridge_ready` do not verify
  audio/video. Owner must verify a real-world call before calling media operational.
- Cloud agent behavior, readiness, handlers, and contact policy depend on its
  existing deployed configuration. This integration does not clone or redeploy it.

To use a local runtime instead, explicitly change `mode` to `local` and set
`runtime` to its executable/argument array. Commands run from this directory
without a shell; use absolute paths as needed and keep secrets out of arguments.

Run local tests with `npm test`. Tests do not send messages, claim lines, or call contacts.

## Keenable web search

The Keenable endpoint authenticated successfully and exposed `search_web_pages`
and `fetch_page_content`. The mistakenly created Claude MCP registration was
removed; this agent must use LiveKit's own MCP tools.

`livekit-keenable.json` contains the prepared Builder settings and exact search
policy to append to the hosted agent's existing instructions. It contains only
a secret reference, never the API key. This is a configuration checklist; the
local wrapper does not load it into the hosted agent automatically.

Actual MCP integration is in `my-agent/src/agent.py`, using secret
`KEENABLE_API_KEY`. The agent's own SDK authenticated and discovered both tools.
A synthetic-audio debugger conversation called search and fetch, then spoke an
answer grounded in Keenable's official site. Audio regression scenarios are in
`my-agent/scenarios.yaml`; GPT-Live does not support text-only response testing.
Production deployment and real FaceTime testing remain pending. The root wrapper
does not automatically upload this code or modify the hosted agent.

`my-agent/verification.json` records the local checks and synthetic-audio evidence.
The audio scenario grader reported one of two failed for answer ordering; review
of the exported timestamps shows search and fetch results preceded the factual
answer in both scenarios. That evaluator discrepancy is retained, not hidden.

Root `health` marks unconfigured SDK FaceTime credentials as optional. CLI login
already authorizes the inbound `chert dev` route; missing SDK tokens do not mean
that CLI login failed. Direct FaceTime API calls use a separate project key.

Source: [Chert setup guide](https://trychert.com/setup).
LiveKit references: [Agent Builder](https://docs.livekit.io/agents/start/builder/),
[dispatch names and production deployment](https://docs.livekit.io/agents/server/agent-dispatch/).
