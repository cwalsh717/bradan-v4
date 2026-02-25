# Bradán v4 — Claude Code Setup Guide

You have 7 files to put in place. Here's exactly where each one goes and what to do.

---

## Step 1: Make Sure You Have The Tools

Open your terminal and run these one at a time:

```bash
# Check Claude Code is installed
claude --version

# Check Node.js is installed (needed for MCP servers)
node --version

# Install ruff (Python linter/formatter) if you don't have it
pip install ruff
```

If any of those fail, stop and install the missing one first.

---

## Step 2: Go To Your Project

```bash
cd ~/path/to/bradan-v4
```

Replace with wherever your actual repo lives.

---

## Step 3: Drop In The Files

You have 7 files. Here's exactly where each one goes:

### File 1: CLAUDE.md (goes in repo root)
```bash
# This replaces your existing CLAUDE.md if you have one
cp CLAUDE.md ./CLAUDE.md
```
This is what Claude Code reads at the start of every session. It's the system prompt.

### File 2: backend.md (sub-agent)
```bash
mkdir -p .claude/agents
cp backend.md .claude/agents/backend.md
```

### File 3: frontend.md (sub-agent)
```bash
cp frontend.md .claude/agents/frontend.md
```

### File 4: phase-plan.md (slash command)
```bash
mkdir -p .claude/commands
cp phase-plan.md .claude/commands/phase-plan.md
```

### File 5: check.md (slash command)
```bash
cp check.md .claude/commands/check.md
```

### File 6: settings.json (hooks)
```bash
# This goes in .claude/ NOT in .claude/agents/
cp settings.json .claude/settings.json
```

### File 7: .mcp.json (MCP server config)
```bash
# This goes in the repo root
cp .mcp.json ./.mcp.json
```

---

## Step 4: Set Up The PostgreSQL MCP

You need your Railway database connection details. Go to Railway dashboard → your Postgres service → Variables tab.

You need these 4 things:
- Host (something like `xxx.railway.app`)
- Port (usually `5432` or a custom one)
- Username
- Password
- Database name

Now edit `.mcp.json` and replace the placeholder:

```bash
# Open it in whatever editor you have
nano .mcp.json
```

Replace this part:
```
postgresql://YOUR_USER:YOUR_PASSWORD@YOUR_RAILWAY_HOST:YOUR_PORT/railway
```

With your actual connection string like:
```
postgresql://postgres:abc123@monorail.proxy.rlwy.net:12345/railway
```

Save and close.

---

## Step 5: Verify It All Works

Start Claude Code:
```bash
claude
```

Once it's running, check each piece:

### Check MCP is connected:
```
/mcp
```
You should see `postgres` listed and showing green/active.

### Check hooks are loaded:
```
/hooks
```
You should see the PostToolUse (ruff) and PreToolUse (pytest) hooks.

### Check slash commands work:
Type `/` and you should see `phase-plan` and `check` in the autocomplete.

### Check sub-agents exist:
```
/agents
```
You should see `backend` and `frontend` listed.

---

## Step 6: Test Drive It

Try this to make sure everything is wired up:

```
/phase-plan 2
```

This should read the spec, decompose Phase 2 (Data Layer) into tasks, and present a plan without building anything.

If that works, you're set up.

---

## How The Workflow Works Now

### Starting a new phase:
1. Come to claude.ai project → discuss the phase with me at a high level
2. Go to Claude Code → run `/phase-plan N` where N is the phase number
3. Review the plan it presents → approve or adjust
4. Tell it to execute → it spawns sub-agents for independent tasks
5. When done → run `/check` to gate everything
6. If check passes → commit and push
7. Come back to claude.ai → debrief, update spec if needed

### During implementation:
- Ruff auto-formats every Python file on edit (hook, no tokens)
- pytest auto-runs before every commit (hook, blocks if fails)
- Run `/check` anytime you want a full quality gate
- Sub-agents keep the main context window clean

---

## Adding More MCPs Later

### Phase 5+ (when frontend exists): Add GitHub MCP
```bash
claude mcp add --transport http github https://api.github.com/mcp
```
(Follow the OAuth flow it prompts)

### Phase 5+ (when frontend exists): Add Browser MCP
Look into Puppeteer MCP or Playwright MCP at that point. The setup depends on which one has better Claude Code support when you get there. We'll figure it out at Phase 5.

---

## If Something Breaks

### MCP not connecting:
```bash
# Check if npx works
npx -y @bytebase/dbhub --help

# Check your connection string works
psql "postgresql://YOUR_USER:YOUR_PASSWORD@YOUR_HOST:PORT/railway"
```

### Hooks not firing:
```
/hooks
```
If they're not listed, check `.claude/settings.json` syntax. JSON is picky about commas and quotes.

### Slash commands not showing:
Make sure the files are in `.claude/commands/` (not `.claude/agents/` or anywhere else).
The `---` frontmatter at the top of each file must be valid YAML.

---

## That's It

You have:
- CLAUDE.md → system prompt (short, strict)
- 2 sub-agents → backend and frontend specialists
- 2 slash commands → /phase-plan and /check
- 2 hooks → auto-format and pre-commit test gate
- 1 MCP → PostgreSQL for database validation

Go build Phase 2.
