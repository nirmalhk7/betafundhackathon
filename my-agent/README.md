# LiveKit Agent

## Active Matt deployment

The active LiveKit target is **Matt**, project `p_59z2r1lar8z`, URL
`wss://matt-zwtabyku.livekit.cloud`, agent `CA_37DgPSCwJnaM`, dispatch
`assistant-0c8`, production version `QBKnavmzaKqW`.

Voice now uses Deepgram Nova 3 speech recognition, OpenAI GPT-5.6 Luna reasoning,
and Cartesia Sonic 3 with Ariana voice `ec1e269e-9ca0-402f-8a18-58e0e022355a`.
Silero provides voice activity detection. Keenable tools, Chert readiness greeting,
and computer video remain enabled. LiveKit credentials stay in ignored `.env.local`.

Verified: Ariana synthesis (3.59 seconds, PCM peak 12400); synthetic spoken greeting
and remembered caller name across turns; Keenable search/fetch with spoken answer;
cloud Chert-style greeting (PCM peak 22269) and 480x480 computer video. Six Python
tests, thirteen wrapper tests, and Ruff passed. Temporary test rooms were deleted.
The RTC SDK emitted a destructor assertion during local probe cleanup after room
deletion; the probe completed with exit status zero.

An existing terminal Chert connector owns the line and has connected a real call
in Matt. Do not start a competing connector. Real FaceTime conversation remains
unverified: observed caller audio still contained digital silence after migration.
The older Chris quota diagnostics below are historical; they do not describe
Matt's current inference access.


## Chert integration in this project

This is the exported source of your existing Builder agent, not a generic new
persona. It retains dispatch name `assistant-0c8`, model `openai/gpt-live-1`,
Marin voice, original instructions, and AI-coustics audio enhancement.
`livekit.toml` targets code deployment `CA_GzE9RWgmRVwF` in LiveKit project Chris.
The original Builder deployment was deleted with owner approval to free the one-agent quota.

Changes added here:

- A computer picture is prepared as a continuously published video track from
  the voice participant. Verified in a temporary LiveKit room; deployed with owner approval; a production agent delivered the picture
  to a LiveKit subscriber. A fresh FaceTime call still needs owner verification.
  It needs a fresh inbound FaceTime Video call after approved deployment.
  The current line API reports video disabled even though this active call
  record requested video; Chert must confirm line support.

- Chert rooms join promptly and wait for a caller before creating the paid model session.
- Greeting waits for room metadata `chert_bridge_ready: true`; participant join
  alone cannot trigger it. Duplicate signals and caller disconnects are handled.
- Audio input is bound to the caller; room deletion stays with Chert.
- Keenable MCP provides `search_web_pages` and `fetch_page_content`. Voice
  instructions delegate uncertain/current facts; backend instructions require
  source verification and honest failure reporting.

Browser verification update: Brave's Billing page says **"Credit balances are temporarily unavailable."** Sonic 3 shows a concurrency limit of 5 and peak usage of 1. A fresh gateway request still returns HTTP 429 with `MaxGatewayCredits`, `max_allowed: "0"`, and `remaining_limit: "0"`. This establishes inference denial, but does not establish that the user consumed all credits or must upgrade. Treat prior upgrade guidance as the gateway's generic hint, not a verified remedy. Screenshots and sanitized response are in `output/livekit-inference-evidence.json` at the repository root.

Current voice blocker (2026-10-23): a direct LiveKit Inference GPT-Live
WebSocket request returned HTTP 429, `inference_quota_exceeded`, category
`MaxGatewayCredits`, quota type `sts`. The project reported `max_allowed: "0"`,
`remaining_limit: "0"`, and `free_tier: true`. The provider's hint says realtime
credits are exhausted and to wait for the next billing cycle or upgrade the plan.
Restore realtime inference quota in **Chris** (`p_3gx7ofwhqg6`) before further
voice tests. An RTC agent and its computer video can connect while inference is
unavailable; neither proves the voice model is running.

Three recent real calls had worker `bridge_ready` and `agent_connected` events.
Earlier samples of caller audio were digital silence, and an isolated production
greeting logged `the model did not start speaking when asked`. After quota is
restored, verify greeting audio, caller audio, and a two-way conversation before
marking this resolved. No production code or billing settings changed during
this investigation. The existing connector remains responsible for the line.

Model usage is billed through LiveKit Inference using LiveKit credentials;
this configuration does not require a separate `OPENAI_API_KEY`. GPT-Live is
audio-only: use `lk agent debugger start --audio` and audio scenarios, not a
text-only debugger. Synthetic audio tests do not establish real FaceTime media.

### Credentials and checks

For local work, `.env.local` links to the parent project's private file. It must
contain `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, and
`KEENABLE_API_KEY`. Keep its mode `0600` and never commit it. The separately
ignored `.env.keenable` contains only the secret needed for the deployment update.
Cloud automatically supplies the deployed agent's LiveKit project credentials.

```sh
uv sync --frozen
PYTHONPATH=src uv run pytest -q
uv run ruff check src tests
```

### Deployment and calling

The owner approved replacing the Builder deployment with this code deployment.
Future production updates still require approval. Update this deployment:

```sh
lk agent deploy --id CA_GzE9RWgmRVwF --secrets-file .env.keenable
```

Maintain this exported project as the source of truth; avoid creating a competing
Builder agent with the same dispatch name.

The Chert connector separately uses pinned `@trychert/facetime@0.1.0-beta.10`,
approved CLI login, project `f023544a-0950-4373-862c-b044b3a34dec`, and the same
LiveKit URL and dispatch name. Coordinate with the existing connector holder;
do not use `--takeover` without explicit authorization. Enable calls only after
deployment readiness and the intended handoff, then wait for `agent_warm`.

Chert's CLI login, FaceTime project API keys, LiveKit credentials, and Keenable
credentials are separate. No extra project API key or custom webhook is needed
for the `chert dev` route. Hosting, inference, and searches can incur charges.
Before any real call, confirm its recipient/purpose and get owner approval.
Verify two conversations, interruption, hangup, and room cleanup; only the owner
can confirm real call audio/video.

A voice AI project built with [LiveKit Agents for Python](https://github.com/livekit/agents) and [LiveKit Cloud](https://cloud.livekit.io/). This project is designed to work with coding agents like [Claude Code](https://claude.com/product/claude-code), [Cursor](https://www.cursor.com/), and [Codex](https://openai.com/codex/) — see [Coding agent support](https://docs.livekit.io/intro/coding-agents/) for setup tips.

> [!IMPORTANT]
> This project was converted to code from the LiveKit Agent Builder. The code is identical to production deployments from the builder. Follow the steps below to make it your own and deploy it to LiveKit Cloud. Once you do so, you can delete the version in the builder.

## Next steps

### Run and deploy your agent

**Get your agent running locally and in production:**

1. **Run locally**: Follow the [Quickstart](#quickstart) section below to set up your environment and test the agent
2. **Deploy to production**: See the [Deploy to production](#deploy-to-production) section for deployment options and best practices

### Quickstart

**Get up and running** so you can start customizing:

1. **Install dependencies:**
   ```console
   uv sync
   ```

2. **Set up your LiveKit credentials:**

   Sign up for [LiveKit Cloud](https://cloud.livekit.io/), then configure your environment. You can either:

   - **Manual setup**: Copy `.env.example` to `.env.local` and fill in:
     - `LIVEKIT_URL`
     - `LIVEKIT_API_KEY`
     - `LIVEKIT_API_SECRET`

   - **Automatic setup** (recommended): Use the [LiveKit CLI](https://docs.livekit.io/intro/basics/cli/):
     ```bash
     lk cloud auth
     lk app env -w -d .env.local
     ```

3. **Download required models:**
   ```console
   uv run python src/agent.py download-files
   ```
   This downloads the model files used by the audio enhancement and noise cancellation plugins. [VAD](https://docs.livekit.io/agents/logic/turns/vad/) and [turn detection](https://docs.livekit.io/agents/logic/turns/turn-detector/) run in LiveKit Inference, so they need no local models.

4. **Test your agent:**
   ```console
   uv run python src/agent.py console
   ```
   This lets you speak to your agent directly in your terminal.

5. **Run for development:**
   ```console
   uv run python src/agent.py dev
   ```
   Use this when connecting to a frontend or telephony. This puts your agent into your LiveKit Cloud project, so use a different project if you don't want to affect production traffic.


## Customize your agent

Once your agent is running, enhance it for your use case:

- **Customize AI models**: Your agent uses a voice AI pipeline built on [LiveKit Inference](https://docs.livekit.io/agents/models/inference). More than 50 model providers are supported, including [Realtime models](https://docs.livekit.io/agents/models/realtime).

- **Add tests**: You can add a full test suite to your agent. See the [testing documentation](https://docs.livekit.io/testing/overview/) for more information.

- **Build reliable workflows**: For complex agents, use [tasks and handoffs](https://docs.livekit.io/agents/logic/workflows/) instead of long instruction prompts. This minimizes latency and improves reliability by structuring your agent into focused, reusable components.

### Get help from AI coding assistants

**Supercharge your development** with AI coding assistants that understand LiveKit. This project works seamlessly with [Claude Code](https://claude.com/product/claude-code), [Cursor](https://www.cursor.com/), [Codex](https://openai.com/codex/), and other AI coding tools.

For your convenience, LiveKit offers both a CLI and an [MCP server](https://docs.livekit.io/reference/developer-tools/docs-mcp/) that can be used to browse and search its documentation. The [LiveKit CLI](https://docs.livekit.io/intro/basics/cli/) (`lk docs`) works with any coding agent that can run shell commands. Install it for your platform:

**macOS:**

```console
brew install livekit-cli
```

**Linux:**

```console
curl -sSL https://get.livekit.io/cli | bash
```

**Windows:**

```console
winget install LiveKit.LiveKitCLI
```

Check your version with `lk --version` and update if needed. Once installed, your coding agent can search and browse LiveKit documentation directly from the terminal:

```console
lk docs search "voice agents"
lk docs get-page /agents/start/voice-ai-quickstart
```

**Install LiveKit's agent skills**: [Agent skills](https://docs.livekit.io/intro/coding-agents/#agent-skills) teach your coding agent how to build, debug, test, and deploy LiveKit agents, and point it to the latest documentation for API details. From this project's directory, install them for the coding agents on your machine:

```console
lk skills install
```

This also adds the LiveKit Docs MCP server to each coding agent's config. Run `lk skills update` to get the latest skills, and commit `skills-lock.json` along with them.

See the [Using coding agents](https://docs.livekit.io/intro/coding-agents/) guide for more details, including MCP server setup.

**Customize the AI assistant context**: The project includes an [AGENTS.md](AGENTS.md) file that guides AI assistants on how to work with this codebase. **Edit this file** to add your own project-specific context, patterns, and preferences. Learn more at [https://agents.md](https://agents.md).

## Frontend development

If you don't already have a frontend, use the following templates and guides to get started on one:

| Platform | Starter Template | What to customize |
|----------|----------|-------------|
| **Web** | [`livekit-examples/agent-starter-react`](https://github.com/livekit-examples/agent-starter-react) | React & Next.js—customize UI, add features, integrate with your backend |
| **iOS/macOS** | [`livekit-examples/agent-starter-swift`](https://github.com/livekit-examples/agent-starter-swift) | Native apps for iOS, macOS, visionOS—add platform-specific features |
| **Flutter** | [`livekit-examples/agent-starter-flutter`](https://github.com/livekit-examples/agent-starter-flutter) | Cross-platform—customize for Android, iOS, web, desktop |
| **React Native** | [`livekit-examples/voice-assistant-react-native`](https://github.com/livekit-examples/voice-assistant-react-native) | Mobile with Expo—add native modules, customize navigation |
| **Android** | [`livekit-examples/agent-starter-android`](https://github.com/livekit-examples/agent-starter-android) | Kotlin & Jetpack Compose—build Material Design UI |
| **Web Embed** | [`livekit-examples/agent-starter-embed`](https://github.com/livekit-examples/agent-starter-embed) | Widget for any website—customize styling, add to your site |
| **Telephony** | [Documentation](https://docs.livekit.io/telephony/) | Add phone calling—configure SIP, add call routing, customize prompts |

## Observability

LiveKit provides deep session insights for your agents through [Agent Observability](https://docs.livekit.io/testing/observability/). Monitor conversation quality, track latency metrics, and debug agent behavior in production.

## Deploy to production

To deploy your agent to production, you can use the LiveKit CLI:

```console
lk agent create
```

See the [deploying to production](https://docs.livekit.io/deploy/agents/) guide for detailed instructions and optimization tips.

## Join the LiveKit community

Join the [LiveKit Slack Community](https://livekit.io/join-slack) to get help from the LiveKit team and other developers.
