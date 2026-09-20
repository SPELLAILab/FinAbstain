#!/usr/bin/env python3
"""Convert financial report HTML files (e.g. SEC 10-K filings) to clean plain text.

- Removes XML / iXBRL headers and hidden tags (ix:header, ix:hidden, display:none).
- Formats financial tables into clean pipe-delimited text, merging split currency symbols and parenthesized negatives.
- Preserves document headings, paragraphs, and sections.
- Cleans non-breaking spaces and unicode artifacts.
"""

import sys
import re
from pathlib import Path
from bs4 import BeautifulSoup, Tag

def clean_cell_text(text: str) -> str:
    # Normalize unicode whitespace and non-breaking spaces
    text = re.sub(r'[\u00a0\u200b\u200e\u200f\s]+', ' ', text)
    return text.strip()

def format_table(table: Tag) -> str:
    rows = []
    for tr in table.find_all('tr'):
        cells = [clean_cell_text(cell.get_text()) for cell in tr.find_all(['td', 'th'])]
        # Merge split currency symbols and parenthesis commonly found in SEC XBRL HTML
        merged = []
        idx = 0
        while idx < len(cells):
            c = cells[idx]
            if c == "$" and idx + 1 < len(cells) and cells[idx + 1]:
                merged.append("$" + cells[idx + 1])
                idx += 2
            elif c == "(" and idx + 1 < len(cells) and cells[idx + 1]:
                val = cells[idx + 1]
                idx += 2
                if idx < len(cells) and cells[idx] == ")":
                    idx += 1
                merged.append(f"({val})")
            elif c:
                merged.append(c)
                idx += 1
            else:
                idx += 1

        if merged:
            rows.append(" | ".join(merged))

    if not rows:
        return ""
    return "\n".join(rows)

def html_to_text(html_content: str) -> str:
    soup = BeautifulSoup(html_content, 'lxml')

    # Remove hidden iXBRL metadata and tags
    for tag in soup.find_all(['ix:header', 'ix:hidden']):
        tag.decompose()

    # Remove tags explicitly hidden via CSS
    for tag in soup.find_all(lambda t: t.has_attr('style') and 'display:none' in t['style'].replace(' ', '').lower()):
        tag.decompose()

    # Remove script, style, head, noscript, etc.
    for tag in soup(['script', 'style', 'head', 'noscript', 'meta', 'link']):
        tag.decompose()

    # Format tables
    for table in soup.find_all('table'):
        t_text = format_table(table)
        if t_text:
            table.replace_with(f"\n\n{t_text}\n\n")
        else:
            table.decompose()

    # Extract text with double newlines between blocks
    text = soup.get_text(separator='\n\n')

    # Clean up lines
    lines = []
    for line in text.splitlines():
        line = re.sub(r'[\u00a0\u200b\u200e\u200f \t]+', ' ', line).strip()
        # Drop standalone navigational links
        if line.lower() == "table of contents":
            continue
        if line:
            lines.append(line)
        elif lines and lines[-1] != "":
            lines.append("")

    # Join lines and collapse excessive blank lines
    result = '\n'.join(lines)
    result = re.sub(r'\n{3,}', '\n\n', result)
    return result.strip()

def main():
    if len(sys.argv) > 1:
        input_path = Path(sys.argv[1])
    else:
        input_path = Path("data/raw/report.html")

    if len(sys.argv) > 2:
        output_path = Path(sys.argv[2])
    else:
        output_path = input_path.with_suffix(".txt")

    if not input_path.exists():
        print(f"Error: {input_path} does not exist.")
        sys.exit(1)

    print(f"Converting {input_path} to {output_path}...")
    try:
        html_content = input_path.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        html_content = input_path.read_text(encoding='latin-1')

    text = html_to_text(html_content)
    output_path.write_text(text, encoding='utf-8')
    print(f"Successfully converted {input_path} -> {output_path} ({len(text)} characters, {len(text.split())} words).")

if __name__ == '__main__':
    main()
