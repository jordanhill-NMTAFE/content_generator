# UOC issues

Issues for the `uoc` tool live in this folder. Use the filesystem-based convention for status and optional type in the filename.

## Naming

```
<date>--<short-slug>.issue[.<type>].<status>
```

- `<date>`: `YYYY-MM-DD` (e.g., 2025-10-22)
- `<short-slug>`: lowercase, hyphenated
- `<type>` (optional): `bug|feature|task|docs|question`
- `<status>`: `open|closed`

## Examples

- `2025-10-22--compare-crash-on-empty-ke.issue.bug.open`
- `2025-10-22--uoc-search-boolean-operators.issue.feature.open`
- `2025-10-22--expand-help-examples.issue.docs.open`

## Template

Copy `TEMPLATE.issue.md` and fill out the YAML frontmatter and sections. Rename the file to follow the naming convention.

