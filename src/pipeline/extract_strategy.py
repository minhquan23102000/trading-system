"""Aggregate transcripts into extraction context for AI-assisted strategy extraction.

Combines all transcript .txt files into a single _extraction_context.md with
instructions your AI assistant can follow to produce strategy.md and
philosophy_draft.md — no API key needed.

Usage:
    uv run python -m pipeline.extract_strategy <transcripts_dir> <output_dir>

Writes:
    <output_dir>/_extraction_context.md  — the aggregated context for AI
"""

from __future__ import annotations

from pathlib import Path
import sys


EXTRACTION_INSTRUCTIONS = """# Strategy Extraction Instructions

You are analyzing a trader's content to extract their complete trading
strategy. Read all transcripts below, then produce TWO documents:

## 1. strategy.md

A structured strategy breakdown. Follow the extraction workflow in
`.omc/skills/trade-setup-scanner/SKILL.md` Phase 1. Must include:
- Core Identity, Ranked Priorities
- The Setup(s) with trigger/timeframes/entry/stop/target/exclusions
- Key Concepts (defined with THEIR definitions, not textbook)
- Gates (draft pipeline) — pass/fail conditions
- Anti-Patterns, Risk Management, Voice & Vocabulary

Extraction rules:
- Quote directly when the trader says something characteristic
- Note contradictions — flag them openly
- Don't invent gates the trader didn't actually use
- Be specific about timeframes ("HTF" alone is useless — is it 1h? 4h? daily?)
- Prefer what they DO over what they SAY

## 2. philosophy_draft.md

A first-person document in the trader's voice, 2,000-4,000 words.
Structure: Who I am, Core philosophy, The setup(s) I trade, Entry mechanics,
Stop loss, Take profit, "Am I actually taking this?" checklist, Anti-patterns,
Psychology/mindset, My voice.
Strip generic platitudes. Be specific about what the trader actually does.

---

Write both files to this directory. Use the templates from the skill file.
"""


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: uv run python -m pipeline.extract_strategy <transcripts_dir> <output_dir>")
        sys.exit(1)

    transcripts_dir = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])
    output_dir.mkdir(parents=True, exist_ok=True)

    txt_files = sorted(transcripts_dir.glob("*.txt"))
    if not txt_files:
        print(f"No .txt files found in {transcripts_dir}")
        sys.exit(1)

    print(f"Loading {len(txt_files)} transcripts...")
    parts: list[str] = [EXTRACTION_INSTRUCTIONS, "---\n"]
    for f in txt_files:
        parts.append(f"## {f.stem}\n\n{f.read_text(encoding='utf-8')}\n")
    corpus = "\n".join(parts)

    out_path = output_dir / "_extraction_context.md"
    out_path.write_text(corpus, encoding="utf-8")
    print(f"  -> {out_path} ({len(corpus):,} chars)")
    print()
    print("Next: ask your AI assistant to process this file:")
    print(f'  "Read {out_path} and follow the extraction instructions inside.')
    print(f'   Produce strategy.md and philosophy_draft.md in {output_dir}."')


if __name__ == "__main__":
    main()
