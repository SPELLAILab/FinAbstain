# `scripts/html_to_txt.py`

## Overview
[`scripts/html_to_txt.py`](file:///Users/kartiksirohi/FinAbstain/scripts/html_to_txt.py) converts raw financial report HTML filings (such as SEC EDGAR 10-K filings) into clean, plain-text documents. It strips hidden iXBRL markup, removes CSS-hidden tags, converts HTML tables into clean pipe-delimited text representations, and normalizes financial numbers.

---

## How It Works

1. **iXBRL & Hidden Metadata Stripping**:
   - Uses `BeautifulSoup` (with the `lxml` parser).
   - Decomposes SEC inline XBRL metadata tags (`ix:header`, `ix:hidden`).
   - Decomposes tags with inline styles indicating `display:none`.
   - Removes `<script>`, `<style>`, `<head>`, `<noscript>`, `<meta>`, and `<link>` tags.
2. **Table Conversion**:
   - Financial tables in SEC filings frequently split currency symbols, values, and parentheses into separate adjacent cells (e.g. `<td>$</td><td>1,234</td>` or `<td>(</td><td>50</td><td>)</td>`).
   - `format_table` traverses rows and cells, merges these split elements into unified tokens (e.g. `$1,234`, `(50)`), and formats the rows into clean markdown-style pipe-delimited lines (`cell1 | cell2 | cell3`).
3. **Whitespace & Structure Normalization**:
   - Replaces non-breaking spaces (`\u00a0`) and zero-width spaces with standard spaces.
   - Preserves section breaks via double newlines (`\n\n`).
   - Collapses excessive blank lines ($>2$).

---

## Functions Reference

### `clean_cell_text(text: str) -> str`
- **Purpose**: Cleans unicode whitespace and trims cell contents.
- **Parameters**: `text` (`str`).
- **Returns**: `str`: Cleaned string.

### `format_table(table: Tag) -> str`
- **Purpose**: Formats a BeautifulSoup `<table>` tag into pipe-delimited text, merging separated currency and parenthesis cells.
- **Parameters**: `table` (`Tag`): BeautifulSoup table element.
- **Returns**: `str`: Formatted table string.

### `html_to_text(html_content: str) -> str`
- **Purpose**: Main parsing function converting raw HTML string into clean text.
- **Parameters**: `html_content` (`str`): Raw HTML file content.
- **Returns**: `str`: Clean plain-text representation.

### `main() -> None`
- **Purpose**: CLI entrypoint. Takes `sys.argv[1]` as input HTML path and `sys.argv[2]` as output text path.

---

## Usage Example

```bash
# Convert a raw filing HTML to text
python scripts/html_to_txt.py data/raw/cat/cat.html data/raw/cat/cat.txt
```
