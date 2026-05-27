# Install on OpenCode

```bash
# After running `bash scripts/build.sh --platform opencode`:
cp -R dist/opencode/. /path/to/your/vault/
```

Then in your vault:

- `AGENTS.md` is the operating manual OpenCode reads at session start.
- `.opencode/commands/*.md` are the command bodies the AI follows.
- `.opencode/scripts/` holds the Python helpers.
