---
title: Search command enhancements for filtering and output
created: 2026-01-30T00:00:00Z
updated: 2026-01-30T00:00:00Z
status: open
type: feature
priority: p3
units: []
tags: [search, ux, filtering]
related: []
---

## Summary

When searching for units across training packages, several workflow improvements would make the tool more efficient for curriculum research tasks like finding units for skillset development.

## Current Limitations

1. **index-search lacks type filtering** - When searching by title/code, results include units, qualifications, skill sets, and training packages mixed together. Users often want just units.

2. **index-search lacks package filtering** - Cannot limit index-search to specific packages (e.g., `--include ICT,BSB`), forcing users to pipe through grep.

3. **Content search output verbose for discovery** - The `search` command shows matching content lines which is great for detailed analysis, but for initial discovery a list-only mode would be faster.

4. **No combined search capability** - Finding units that match both title keywords AND content keywords requires multiple commands.

## Steps / Repro

1. Run `uoc index-search "emerging"` - returns mixed types
2. Run `uoc index-search "emerging" | grep "^ICT"` - workaround needed
3. Run `uoc search "AI" -i ICT` - get verbose output when you just want unit codes

## Expected

More flexible search options for curriculum research workflows.

## Proposal / Acceptance Criteria

- [ ] Add `--type` or `-t` filter to `index-search` (values: `unit`, `qual`, `ss`, `package`, `all`)
- [ ] Add `--include` or `-i` filter to `index-search` for package prefix filtering
- [ ] Add `--list` or `-l` flag to `search` command for code-only output (no content snippets)
- [ ] Consider a `--json` output option for programmatic use

## Example Usage

```bash
# Filter index-search by type and package
uoc index-search "emerging" -t unit -i ICT,BSB

# List-only mode for content search
uoc search "AI" -i ICT --list
# Output: ICTICT426, ICTICT521, ...
```
