# Obsidian Second Brain — OpenCode Operating Manual

This vault runs the **obsidian-second-brain** skill. The skill ships a set of
*commands*: each one is a multi-step instruction file that you (the OpenCode
agent) should follow when the user's request matches its trigger phrase.

## How to operate

1. Read `_CLAUDE.md` in the vault root, if it exists, to learn the user's
   vault conventions.
2. When the user's request matches a trigger in the tables below, read the
   matching file under `.opencode/commands/<name>.md` and follow its
   instructions step by step.
3. Treat the AI-first vault rule (`references/ai-first-rules.md`) as
   non-negotiable for every note you write: `## For future Claude` preamble,
   rich frontmatter (`type`, `date`, `tags`, `ai-first: true`), `[[wikilinks]]`
   for every person/project/concept, recency markers per external claim,
   sources verbatim, confidence levels where applicable.

## Command routing tables (grouped by category)

### Vault — daily writing, capture, find

| Command | What it does | Read this file |
|---|---|---|
| `/obsidian-board` | Show or update a kanban board — flags overdue items, updates from conversation | `.opencode/commands/obsidian-board.md` |
| `/obsidian-capture` | Quick idea capture — zero friction, saves to Ideas/ and mentions in daily note | `.opencode/commands/obsidian-capture.md` |
| `/obsidian-daily` | Create or update today's daily note — pulls calendar events, overdue tasks, and conversation context | `.opencode/commands/obsidian-daily.md` |
| `/obsidian-find` | Smart vault search — returns results with context, not just filenames | `.opencode/commands/obsidian-find.md` |
| `/obsidian-log` | Log this work or dev session to the vault — infers project from context | `.opencode/commands/obsidian-log.md` |
| `/obsidian-person` | Create or update a person note from conversation context | `.opencode/commands/obsidian-person.md` |
| `/obsidian-project` | Create or update a project note — adds to board and daily note automatically | `.opencode/commands/obsidian-project.md` |
| `/obsidian-recap` | Summarize a time period from the vault — today, week, or month | `.opencode/commands/obsidian-recap.md` |
| `/obsidian-save` | Save everything worth keeping from this conversation to the vault | `.opencode/commands/obsidian-save.md` |
| `/obsidian-task` | Add a task to the right kanban board with inferred priority and due date | `.opencode/commands/obsidian-task.md` |
| `/obsidian-world` | Load your identity, values, priorities, and current state in one shot — with progressive context levels to avoid burning tokens | `.opencode/commands/obsidian-world.md` |

### Thinking — synthesis, decisions, learning, reviews

| Command | What it does | Read this file |
|---|---|---|
| `/obsidian-adr` | Generate a decision record when the vault structure changes — the vault knows why it knows what it does | `.opencode/commands/obsidian-adr.md` |
| `/obsidian-challenge` | Red-team your current idea against your own vault history — finds contradictions, past failures, and flawed assumptions | `.opencode/commands/obsidian-challenge.md` |
| `/obsidian-connect` | Bridge two unrelated domains using your vault's link graph — forces creative friction to spark new ideas | `.opencode/commands/obsidian-connect.md` |
| `/obsidian-decide` | Extract decisions from this conversation and log them to the right project notes | `.opencode/commands/obsidian-decide.md` |
| `/obsidian-emerge` | Surface unnamed patterns from your recent notes — recurring themes, hidden connections, and conclusions you haven't explicitly stated | `.opencode/commands/obsidian-emerge.md` |
| `/obsidian-graduate` | Promote an idea fragment into a full project spec with tasks, board entries, and structure | `.opencode/commands/obsidian-graduate.md` |
| `/obsidian-learn` | Review vault learnings, prune stale ones, surface active patterns — the vault's lessons compound or expire | `.opencode/commands/obsidian-learn.md` |
| `/obsidian-reconcile` | Find and resolve contradictions in the vault — the vault maintains its own truth | `.opencode/commands/obsidian-reconcile.md` |
| `/obsidian-review` | Generate a structured weekly or monthly review note from vault history | `.opencode/commands/obsidian-review.md` |
| `/obsidian-synthesize` | Automatic synthesis — scans the vault for unnamed patterns and writes synthesis pages without being asked | `.opencode/commands/obsidian-synthesize.md` |

### Research — bring external sources into the vault

| Command | What it does | Read this file |
|---|---|---|
| `/notebooklm` | Vault-first source-grounded research via Gemini File Search. One command, no browser. The grounded parallel to /research-deep (which is open-web via Perplexity). | `.opencode/commands/notebooklm.md` |
| `/obsidian-ingest` | Ingest a source into the vault — the vault rewrites itself around new knowledge. Every ingest updates entities, rewrites stale claims, synthesizes new concepts, and resolves contradictions. | `.opencode/commands/obsidian-ingest.md` |
| `/research` | Web research with citations via Perplexity Sonar — deep dossier with summary, facts, timeline, players, contrarian views, open questions | `.opencode/commands/research.md` |
| `/research-deep` | Vault-first deep research — scans vault, identifies gaps, fills via Perplexity + Grok, synthesizes a delta, then propagates updates across people/projects/ideas via /obsidian-save | `.opencode/commands/research-deep.md` |
| `/x-pulse` | Scan X for what's trending in a topic — themes, voices, hooks, and post ideas powered by Grok + Live Search | `.opencode/commands/x-pulse.md` |
| `/x-read` | Deep-read an X (Twitter) post via Grok + Live Search — verbatim post, thread, TL;DR, claims, reply sentiment, voices to watch | `.opencode/commands/x-read.md` |
| `/youtube` | Extract transcript, metadata, and top comments from a YouTube video — summarized via Grok and saved to vault | `.opencode/commands/youtube.md` |

### Meta — vault setup, health, structure

| Command | What it does | Read this file |
|---|---|---|
| `/create-command` | Create a new obsidian-second-brain command via interview — zero markdown editing required | `.opencode/commands/create-command.md` |
| `/obsidian-export` | Export a clean structured snapshot of the vault that any agent or tool can consume — flat JSON or markdown index | `.opencode/commands/obsidian-export.md` |
| `/obsidian-health` | Run a vault health check — grouped by severity, detects contradictions, concept gaps, stale claims, and structural issues | `.opencode/commands/obsidian-health.md` |
| `/obsidian-init` | Scan your vault and generate a _CLAUDE.md operating manual, index.md catalog, and log.md pointer | `.opencode/commands/obsidian-init.md` |
| `/obsidian-visualize` | Generate a visual canvas map of your vault — see the shape of your second brain and how knowledge connects | `.opencode/commands/obsidian-visualize.md` |

## Trigger phrases

When the user says any of the phrases below (or a close paraphrase), follow the matching command file.

### English (`en`)


**Vault — daily writing, capture, find**

- `/obsidian-board` — "show board", "kanban", "what is on my board", "update board"
- `/obsidian-capture` — "capture this idea", "save this idea", "quick note", "drop a thought"
- `/obsidian-daily` — "todays note", "create todays daily", "open daily", "today daily note"
- `/obsidian-find` — "find in vault", "search my notes", "where is", "what did I write about"
- `/obsidian-log` — "log this work", "log this session", "log this dev session", "obsidian log"
- `/obsidian-person` — "save this person", "add person", "new contact note", "create person note"
- `/obsidian-project` — "new project", "create project note", "project setup", "start a project"
- `/obsidian-recap` — "recap today", "recap the week", "summarize the week", "month recap"
- `/obsidian-save` — "save this", "save the conversation", "save to vault", "obsidian save"
- `/obsidian-task` — "add task", "new todo", "track this", "remind me"
- `/obsidian-world` — "load context", "what is going on", "where am I", "load my world"

**Thinking — synthesis, decisions, learning, reviews**

- `/obsidian-adr` — "log this decision", "ADR", "record decision", "decision record"
- `/obsidian-challenge` — "challenge this", "grill me on this", "red team my idea", "stress test this"
- `/obsidian-connect` — "connect domains", "cross-pollinate", "bridge ideas", "find an unexpected link"
- `/obsidian-decide` — "extract decisions", "log decisions", "what did we decide"
- `/obsidian-emerge` — "find patterns", "what is emerging", "surface themes", "unnamed patterns"
- `/obsidian-graduate` — "promote idea", "graduate this to project", "make a project from this", "elevate idea"
- `/obsidian-learn` — "review learnings", "what have I learned", "show lessons", "prune learnings"
- `/obsidian-reconcile` — "find contradictions", "reconcile vault", "fix conflicts", "vault contradictions"
- `/obsidian-review` — "weekly review", "monthly review", "review my week", "review my month"
- `/obsidian-synthesize` — "synthesize", "auto-synthesis", "make synthesis notes", "find unnamed patterns"

**Research — bring external sources into the vault**

- `/notebooklm` — "notebooklm", "research grounded", "ground research in vault", "ask my notebook", "source-grounded research"
- `/obsidian-ingest` — "ingest this source", "add this article", "import this", "absorb this"
- `/research` — "research this", "look up", "find information about", "perplexity research"
- `/research-deep` — "deep research", "thorough research", "vault-first research", "research gaps"
- `/x-pulse` — "x pulse", "what is trending on twitter", "scan x for", "twitter pulse"
- `/x-read` — "read this x post", "deep read this tweet", "analyze this tweet", "read this thread"
- `/youtube` — "summarize youtube", "youtube transcript", "extract video", "youtube to vault"

**Meta — vault setup, health, structure**

- `/create-command` — "create command", "new command", "add a command", "scaffold a command"
- `/obsidian-export` — "export vault", "snapshot vault", "dump vault", "vault export"
- `/obsidian-health` — "vault health", "check vault", "audit vault", "vault diagnostics"
- `/obsidian-init` — "init vault", "bootstrap vault", "setup vault", "scan vault"
- `/obsidian-visualize` — "visualize vault", "vault map", "canvas of vault", "show me the vault shape"

---

*Generated by adapters/opencode/adapter.sh — do not edit manually.*
