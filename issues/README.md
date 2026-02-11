# Repository issues (filesystem-based)

This repository uses a lightweight, git-tracked, filesystem-based issue system under `issues/` to capture bugs, features, and tasks without relying on an external tracker.

## How it works

- Issues are plain text (Markdown) files committed to the repo.
- File names encode status and optional type for easy filtering.
- Contents use a small YAML frontmatter for machine-readability, followed by freeform Markdown.

## Directory layout

- `issues/` – root for all issue groups
- `issues/uoc/` – issues specific to the `uoc` tool

## Naming convention

Pattern:

```
<date>--<short-slug>.issue[.<type>].<status>
```

- `<date>`: `YYYY-MM-DD`
- `<short-slug>`: lowercase, hyphenated summary
- `<type>` (optional): one of `bug, feature, task, docs, question`
- `<status>`: `open` or `closed`

Examples:

- `2025-10-22--compare-crash-on-empty-ke.issue.bug.open`
- `2025-10-22--add-json-output-for-show.issue.feature.open`
- When resolved, rename to end with `.closed`.

## Creating an issue

1. Copy the template from `issues/uoc/TEMPLATE.issue.md` to the appropriate subfolder.
2. Rename the file to follow the convention above.
3. Fill out the YAML frontmatter and body sections.

## Closing an issue

- Rename the file suffix from `.open` to `.closed` and update the `status` field and `updated` timestamp in frontmatter.

## Suggested frontmatter keys

```
---
title: short human title
created: ISO timestamp
updated: ISO timestamp
status: open | closed
type: bug | feature | task | docs | question
priority: p0 | p1 | p2 | p3
units: [ICTAII401, ICTPRG302]
tags: [cli, compare, output]
related: [commit/PR links or filenames]
---
```

## Why do this?

- Keeps issues close to the code.
- Easy to review, diff, and search.
- Works offline and with any workflow (no external accounts needed).

