# Browser Commands

> **🤖 Coding Agents**: Run `act browser --help` for complete command usage, flags, and examples directly in your terminal.

Interactive browser automation commands for Nova Act CLI. Execute browser actions using natural language prompts or specific commands.

## Architecture

```
browser/
├── __init__.py              # Browser group (registers all commands)
├── types.py                 # CommandParams dataclass
├── config_schema.json       # JSON schema for browser config (reference only)
├── commands/                # CLI command definitions (Click interface)
│   ├── browsing/            # Browsing commands (19)
│   │   ├── ask.py           # Read-only page questions
│   │   ├── back.py          # Browser back navigation
│   │   ├── click_target.py  # Click an element by description
│   │   ├── console_log.py   # Capture browser console output
│   │   ├── execute.py       # Multi-step browser plan delegation
│   │   ├── fill_form.py     # Form filling via natural language
│   │   ├── forward.py       # Browser forward navigation
│   │   ├── goto.py          # Raw Playwright URL navigation
│   │   ├── network_log.py   # Capture network requests/responses
│   │   ├── page.py          # Page info (URL, title)
│   │   ├── refresh.py       # Page refresh
│   │   ├── scroll_to.py     # Scroll to element or position
│   │   ├── tab_close.py     # Close a browser tab
│   │   ├── tab_list.py      # List browser tabs
│   │   ├── tab_new.py       # Open a new browser tab
│   │   ├── tab_select.py    # Select/switch browser tab
│   │   ├── type_text.py     # Type text into focused element
│   │   ├── verify.py        # Visually assert a condition on the page
│   │   └── wait_for.py      # Condition polling
│   ├── extraction/          # Extraction commands (10)
│   │   ├── diff.py          # Before/after page state observation
│   │   ├── evaluate.py      # JavaScript expression evaluation
│   │   ├── extract.py       # Structured data extraction
│   │   ├── get_content.py   # Page content (text/HTML/markdown)
│   │   ├── pdf.py           # Save page as PDF
│   │   ├── perf.py          # Page performance metrics
│   │   ├── query.py         # CSS selector element queries
│   │   ├── screenshot.py    # Page screenshot capture
│   │   ├── snapshot.py      # Accessibility tree snapshot
│   │   └── style.py         # Computed CSS style inspection
│   ├── session/             # Session management subcommands (8)
│   │   ├── close.py         # close + close-all commands
│   │   ├── create.py        # Session creation with validation
│   │   ├── export.py        # Export session history and artifacts
│   │   ├── list.py          # List active sessions
│   │   ├── prune.py         # Remove stale sessions
│   │   ├── record_show.py   # Show session recording
│   │   ├── trace_start.py   # Start CDP tracing
│   │   └── trace_stop.py    # Stop CDP tracing and save
│   └── setup/               # Setup commands (4)
│       ├── cli_doctor.py    # CLIDoctor diagnostic check runner
│       ├── doctor.py        # Doctor command entry point
│       ├── qa_plan.py       # Generate QA test plan from Gherkin
│       └── setup.py         # API key storage command
├── services/                # Business logic and state management
│   ├── action_results.py    # Typed result dataclasses
│   ├── browser_config.py    # DefaultBrowserConfig class
│   ├── console_capture.py   # Browser console log capture
│   ├── gherkin_compiler.py  # Gherkin feature file compiler
│   ├── network_capture.py   # Network request/response capture
│   ├── performance_collector.py  # Page performance metrics collection
│   ├── screenshot_annotator.py   # Screenshot annotation with overlays
│   ├── session_recorder.py  # Session history recording
│   ├── step_tracking.py     # Command step/trajectory tracking
│   ├── browser_actions/     # BrowserActions mixin package
│   │   ├── __init__.py      # BrowserActions class (mixin aggregator)
│   │   ├── exploration.py   # Ask logic
│   │   ├── inspection.py    # Query/style/evaluate/diff logic
│   │   ├── interaction.py   # Execute/fill-form/wait-for logic
│   │   ├── navigation.py    # Goto logic
│   │   └── utils.py         # Shared action utilities
│   ├── intent_resolution/   # Natural language command routing
│   │   ├── __init__.py      # Re-exports
│   │   ├── matching.py      # Fuzzy matching logic
│   │   ├── resolver.py      # Intent resolver
│   │   └── snapshot.py      # Page state snapshot for context
│   └── session/             # Session lifecycle management
│       ├── __init__.py      # Re-exports SessionManager, models
│       ├── cdp_endpoint_manager.py  # CDP endpoint discovery
│       ├── chrome_launcher.py       # Chrome process launching
│       ├── chrome_terminator.py     # Chrome process termination
│       ├── closer.py               # Session close logic
│       ├── connector.py            # CDP connection management
│       ├── locking.py              # File-based session locking
│       ├── manager.py              # SessionManager (main entry point)
│       ├── models.py               # SessionInfo, BrowserOptions, SessionState
│       ├── persistence.py          # Session metadata file I/O
│       └── pruner.py               # Stale session cleanup
└── utils/                   # Shared utilities
    ├── auth.py              # Authentication resolution
    ├── browser_config_cli.py # Headless mode resolution + screenshot config
    ├── decorators.py        # Shared Click decorators + CommandParams packing
    ├── disk_usage.py        # Disk usage warnings for session data
    ├── error_handlers.py    # Common error handling decorator
    ├── file_output.py       # File output formatting
    ├── log_capture.py       # Command log capture (TeeWriter)
    ├── nova_args.py         # --nova-arg parsing and validation
    ├── orientation.py       # Auto-orientation context for commands
    ├── parsing.py           # CLI argument parsing utilities
    ├── session.py           # Session preparation (command_session() CM)
    ├── timeout.py           # Timeout handling
    └── validation_utils.py  # Input validation helpers
```

The browser CLI also depends on shared modules in `nova_act.cli.core/`:
- `config.py` — CLI path management and browser config I/O
- `output.py` — Formatted terminal output helpers
- `json_output.py` — Structured JSON output mode
- `cli_stdout.py` — Stdout capture utilities
- `locking.py` — File-based locking
- `nova_args.py` — NovaAct argument parsing and validation
- `exceptions.py` — CLI exception types
- `constants.py` — Shared constants (paths, defaults)
- `process.py` — Process utilities

## Supported Browsers / OS

- **Browsers**: Chromium-based only — Chrome, Chromium, Edge
- **Operating Systems**:
  - macOS ✅
  - Linux ✅
  - Windows ❌ (not supported)

## Design Principles

- **Commands**: Thin CLI wiring layer using Click decorators. Delegates to services via `command_session()` context manager and `BrowserActions` methods. Uses `CommandParams` (from `types.py`) to bundle common parameters.
- **Services**: Business logic independent of CLI framework. `BrowserActions` is a mixin-based class decomposed into 5 files by domain (exploration, inspection, interaction, navigation, utils). `SessionManager` orchestrates the session lifecycle through dedicated submodules.
- **Utils**: Shared utilities across commands. `command_session()` is the unified context manager that handles session preparation, NovaAct instantiation, and cleanup. `decorators.py` provides composite Click decorators that pack parameters into `CommandParams`.
- **Separation**: Commands never directly manage browser state or NovaAct instances.

## Import Patterns

```python
# In command files
from nova_act.cli.browser.services import SessionManager
from nova_act.cli.browser.services.browser_actions import BrowserActions
from nova_act.cli.browser.utils.session import command_session
from nova_act.cli.browser.types import CommandParams

# commands/__init__.py re-exports from subpackages:
from nova_act.cli.browser.commands.browsing import ask, execute, ...
from nova_act.cli.browser.commands.extraction import diff, evaluate, extract, ...
from nova_act.cli.browser.commands.session import session
from nova_act.cli.browser.commands.setup import doctor, setup
```

## Commands

### Browsing (19 commands)

| Command | Description |
|---------|-------------|
| `ask` | Ask a read-only question about the current page (observation only) |
| `back` | Go back in browser history |
| `click` | Click an element described in natural language |
| `console-log` | Capture and display browser console output |
| `execute` | Delegate a multi-step browser plan using natural language (primary agent command) |
| `fill-form` | Fill out a form using natural language field descriptions |
| `forward` | Go forward in browser history |
| `goto` | Navigate to a URL via raw Playwright `go_to_url` |
| `network-log` | Capture and display network requests/responses |
| `page` | Get current page info (URL, title) |
| `refresh` | Refresh the current page |
| `scroll-to` | Scroll to an element or position on the page |
| `tab-close` | Close a browser tab |
| `tab-list` | List all open browser tabs |
| `tab-new` | Open a new browser tab |
| `tab-select` | Switch to a specific browser tab |
| `type` | Type text into the currently focused element |
| `verify` | Visually assert a condition is true on the current page |
| `wait-for` | Poll until a condition is met (each poll = 1 inference call) |

### Extraction (10 commands)

| Command | Description |
|---------|-------------|
| `diff` | Observe page state before and after an action (3 inference calls) |
| `evaluate` | Evaluate a JavaScript expression in the page context |
| `extract` | Extract structured data with optional `--schema` JSON schema |
| `get-content` | Get page content in text, HTML, or markdown format |
| `pdf` | Save the current page as a PDF file |
| `perf` | Collect page performance metrics (timing, resources, vitals) |
| `query` | Query elements matching a CSS selector with `--properties` filter |
| `screenshot` | Capture screenshot with `--full-page`, `--format`, `--quality` options |
| `snapshot` | Capture accessibility tree snapshot of the page |
| `style` | Get computed CSS styles for elements matching a selector |

Extraction commands that return structured data (`extract`, `get-content`, `query`, `style`, `evaluate`, `screenshot`) support `--output`/`-o` for writing results to a file.

### Session (8 subcommands under `act browser session`)

| Subcommand | Description |
|------------|-------------|
| `list` | List all active browser sessions |
| `close` | Close a specific session (`--session-id`, `--force`) |
| `close-all` | Close all active browser sessions |
| `create` | Create a new session with `--starting-page` and `--headed` options |
| `prune` | Remove stale sessions (24h+ inactive by default, `--all` for all non-active) |
| `export` | Export session history, screenshots, and command logs |
| `record-show` | Show session recording |
| `trace-start` | Start CDP tracing for performance analysis |
| `trace-stop` | Stop CDP tracing and save trace file |

### Setup (4 commands)

| Command | Description |
|---------|-------------|
| `doctor` | Run diagnostic checks (Chrome, API key, sessions, Playwright) |
| `setup` | Store API key in `~/.act_cli/browser/config.yaml` for persistent auth |
| `qa-plan` | Generate a QA test plan from Gherkin feature files |

## Common Flags

All browsing and extraction commands share these flags via composite decorators:

| Flag | Description |
|------|-------------|
| `--session-id` | Session ID (default: `default`) |
| `--nova-arg KEY=VALUE` | Pass additional NovaAct parameters (repeatable) |
| `--headless` | Launch browser in headless mode (no visible UI) |
| `--headed` | Launch browser in headed mode (visible UI) |
| `--executable-path` | Path to custom Chromium-based browser executable |
| `--profile-path` | Path to browser profile directory |
| `--use-default-chrome` | Use default Chrome with extensions (quits running Chrome, rsyncs profile; macOS only) |
| `--user-data-dir` | Working directory for Chrome profile (auto-created if omitted with `--use-default-chrome`) |
| `--launch-arg` | Additional Chrome launch argument (repeatable) |
| `--cdp` | Connect to existing browser via CDP WebSocket endpoint |
| `--ignore-https-errors/--no-ignore-https-errors` | Ignore HTTPS certificate errors (enabled by default) |
| `--auth-mode` | Authentication mode: `api-key` or `aws` (auto-detected if omitted) |
| `--profile` | AWS profile name for AWS auth |
| `--region` | AWS region for AWS auth |
| `--workflow-name` | Workflow definition name for AWS auth |
| `--json` | Output results as structured JSON |
| `--quiet` / `-q` | Suppress SDK output for token efficiency |
| `--verbose` / `-v` | Show decorated output with full SDK trace |
| `--no-screenshot-on-failure` | Disable automatic screenshot capture on act() failure |

Setup commands (`doctor`, `setup`) support only `--json` and `--verbose`.

## Session Management

Sessions persist across CLI invocations using Chrome DevTools Protocol (CDP). The `session/` service package handles the full lifecycle:

- **manager.py**: `SessionManager` — main entry point for create/connect/close/list
- **persistence.py**: File-based session metadata storage (`~/.act_cli/browser/sessions/`)
- **chrome_launcher.py**: Chrome process launching with profile and config support
- **chrome_terminator.py**: Chrome process termination (graceful SIGTERM → force SIGKILL)
- **connector.py**: CDP WebSocket connection management
- **cdp_endpoint_manager.py**: CDP endpoint validation and polling
- **closer.py**: Graceful session teardown with Chrome process termination
- **locking.py**: File-based session locking to prevent concurrent access
- **pruner.py**: Stale session cleanup with configurable TTL
- **models.py**: `SessionInfo`, `BrowserOptions`, `SessionState` dataclasses

## Configuration

### Headless Mode Resolution

Headless mode follows this precedence (highest to lowest):

1. CLI flags (`--headless` or `--headed`)
2. `NOVA_ACT_HEADLESS` environment variable (`true`/`false`/`1`/`0`/`yes`/`no`)
3. Default: headless (for agent workflows)

### Browser CLI Config

API key and browser preferences are stored in `~/.act_cli/browser/config.yaml` (YAML format, `0o600` permissions). Managed via `act browser setup`.

### Workflow CLI Config

Workflow user preferences are stored separately in `~/.act_cli/config.yml`.

## Security Considerations

> **⚠️ This tool controls a real browser with real credentials.** Any page you navigate to, any form you fill, and any JavaScript you execute operates in a real browser session with full access to your authenticated state (cookies, local storage, session tokens). Treat browser CLI sessions with the same caution as manual browsing.

### API Key Handling

- **Never commit API keys to source control.** Use `act browser setup` to store your key in `~/.act_cli/browser/config.yaml` (created with `0o600` permissions — owner-read/write only).
- The API key is held in the `NOVA_ACT_API_KEY` environment variable during process execution. This is standard for SDK credential passing but means the key is accessible to any code running in the same process.
- Prefer environment variables (`export NOVA_ACT_API_KEY=...`) over CLI arguments to avoid shell history exposure.

### Session Data Sensitivity

- Session metadata is stored in `~/.act_cli/browser/sessions/` with `0o700` directory permissions.
- Session files contain CDP endpoints, browser PIDs, and connection metadata. They do **not** contain API keys.
- Use `act browser session prune` to clean up stale session data.

### Network and Console Log Contents

- **Network capture** stores full HTTP request/response headers in memory during a session, including `Authorization`, `Cookie`, and `Set-Cookie` headers. These headers are **not** displayed in `network-log` output (only URL, method, status, resource type, duration, and size are shown), but they remain in process memory until the session ends.
- **Console capture** stores page console output (`console.log`, `console.error`, etc.) in memory. Web pages may log sensitive data (tokens, user info, API responses) to the console.
- Neither network nor console data is persisted to disk unless you explicitly use `export`.

### Evaluate Command

- `evaluate` executes **arbitrary JavaScript** in the page context. This has the same power as the browser DevTools console — it can read cookies, access local storage, modify the DOM, and make network requests as the authenticated user.
- Never run untrusted JavaScript expressions. Validate any dynamically-generated JS before execution.

### Export Command

- `export` bundles session history, screenshots, and command logs into a single file. This file may contain sensitive page content, URLs visited, and visual captures of authenticated pages.
- Export files are created with default umask permissions. Store exports in secure locations and delete them when no longer needed.

### Chrome Launch Arguments (`--launch-arg`)

- `--launch-arg` passes arguments directly to the Chrome process without validation. This is a power-user feature.
- **Dangerous flags to avoid** unless you understand the implications:
  - `--disable-web-security` — disables same-origin policy
  - `--no-sandbox` — disables Chrome's sandbox (auto-added only in CI/Docker environments)
  - `--disable-site-isolation-trials` — weakens process isolation
  - `--allow-running-insecure-content` — allows HTTP content on HTTPS pages

### HTTPS Error Handling

- `--ignore-https-errors` is **enabled by default** for convenience in development and automation workflows. This means the browser will accept invalid, expired, and self-signed TLS certificates.
- For security-sensitive workflows, use `--no-ignore-https-errors` to enforce strict certificate validation.

### CDP Connection Security

- Local Chrome sessions use `ws://localhost` for CDP connections, which is safe for local use.
- If connecting to a remote CDP endpoint via `--cdp`, prefer `wss://` (encrypted WebSocket) over `ws://` to protect the connection from eavesdropping.

### Log Files

- Command log files (when `--verbose` logging is enabled) may contain SDK trace output including page content and URLs visited. These files are created with default system umask permissions.
- Review and delete log files after debugging sessions.
