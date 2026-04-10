# Duster Codex Plugin

`duster` is a self-contained Codex plugin for scoring Go codebase hygiene with OpenAI embeddings.

## What it provides

- `snapshot`: parse a Go repo, embed code units, score hygiene, save a snapshot
- `report`: format the latest snapshot as markdown or json, optionally inject into `AGENTS.md`
- `diff`: compare the latest two snapshots

## Plugin layout

- `.codex-plugin/plugin.json`: Codex plugin manifest
- `.mcp.json`: MCP server config
- `scripts/mcp_server.py`: stdio MCP entrypoint
- `src/duster_plugin/`: bundled implementation

## Requirements

- Python 3.11+
- `OPENAI_API_KEY` set in the environment that launches Codex

Bootstrap the plugin-local virtualenv:

```bash
./plugins/duster/scripts/setup.sh
```

## Installation

Repo-local:

1. Ensure the plugin is present at `./plugins/duster`
2. Ensure the marketplace entry exists in `./.agents/plugins/marketplace.json`
3. Run `./plugins/duster/scripts/setup.sh`
4. Restart Codex

## Publishing

Recommended repository name: `duster`

Suggested GitHub repository:

```text
https://github.com/injaneity/duster
```

Suggested release workflow:

1. Keep this plugin as its own git repository rooted at `plugins/duster`
2. Tag releases with the plugin version from `.codex-plugin/plugin.json`
3. Ask users to clone the repo into `~/plugins/duster`
4. Ask users to run `~/plugins/duster/scripts/setup.sh`
5. Ask users to register the plugin in `~/.agents/plugins/marketplace.json`

Marketplace entry:

```json
{
  "name": "duster",
  "source": {
    "source": "local",
    "path": "./plugins/duster"
  },
  "policy": {
    "installation": "AVAILABLE",
    "authentication": "ON_INSTALL"
  },
  "category": "Productivity"
}
```

Home-local:

1. Copy `plugins/duster` to `~/plugins/duster`
2. Add or update `~/.agents/plugins/marketplace.json` to point to `./plugins/duster`
3. Bootstrap the plugin-local environment:

```bash
~/plugins/duster/scripts/setup.sh
```

4. Restart Codex

## Verification

Run:

```bash
./plugins/duster/scripts/check.sh
```

This verifies:
- the plugin-local virtualenv exists
- dependencies import cleanly
- the MCP server responds to `initialize`
- the tool list contains `snapshot`, `report`, and `diff`

## Notes

- Snapshots and embedding cache are written to `<target-root>/.duster/`
- The first cold run can take time on larger repos because every unit must be embedded
- Subsequent runs are much faster because vectors are cached in sqlite
