#!/usr/bin/env python3
"""
metrics.py — считает базовые метрики по нарезанным ответам.

Читает: sliced/{Model}/q{NNN}.md (с YAML-frontmatter от slice.py)
Пишет: metrics/metrics.csv

Колонки:
  model, question_id, question_text,
  answer_length_chars, answer_length_words, sources_count,
  brand_in_body (bool), brand_in_sources (bool),
  brand_position_in_sources (номер первого источника с бренд-доменом или пусто)

Бренд задаётся флагами --brand (основное имя) и --alias (повторяемый).
Поиск бренд-упоминания — case-insensitive, по любому из имён/алиасов.

Usage:
    python scripts/metrics.py --brand "Альфа-Банк" --alias "Alfa Bank" --alias "alfabank.ru"
"""
import argparse
import csv
import re
from pathlib import Path

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
SECTION_RE     = re.compile(r"^## (Вопрос|Ответ|Источники)\s*$", re.MULTILINE)
SOURCE_LINE_RE = re.compile(r"^\s*\d+\.\s+(\S+)\s*$")


def parse_frontmatter(text: str) -> dict:
    m = FRONTMATTER_RE.match(text)
    if not m:
        raise ValueError("Нет YAML-frontmatter")
    meta = {}
    for line in m.group(1).splitlines():
        if ": " not in line:
            continue
        k, v = line.split(": ", 1)
        meta[k.strip()] = v.strip().strip('"')
    return meta


def split_sections(text: str) -> dict:
    """Возвращает {'Вопрос': ..., 'Ответ': ..., 'Источники': ...}."""
    marks = list(SECTION_RE.finditer(text))
    sections = {}
    for i, m in enumerate(marks):
        name = m.group(1)
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        sections[name] = text[m.end():end].strip()
    return sections


def extract_source_urls(sources_block: str) -> list[str]:
    return [
        m.group(1)
        for line in sources_block.splitlines()
        if (m := SOURCE_LINE_RE.match(line))
    ]


def brand_match(text: str, terms: list[str]) -> bool:
    low = text.lower()
    return any(t.lower() in low for t in terms)


def brand_position_in_sources(urls: list[str], terms: list[str]) -> int | None:
    low_terms = [t.lower() for t in terms]
    for i, url in enumerate(urls, start=1):
        low = url.lower()
        if any(t in low for t in low_terms):
            return i
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", help="имя проекта в projects/ (например: alfa_bank)")
    ap.add_argument("--input",   default="sliced", help="папка с нарезкой (игнорируется при --project)")
    ap.add_argument("--output",  default="metrics/metrics.csv", help="выходной csv (игнорируется при --project)")
    ap.add_argument("--brand",   required=True, help="основное имя бренда (например, \"Альфа-Банк\")")
    ap.add_argument("--alias",   action="append", default=[], help="синоним бренда (можно повторять)")
    args = ap.parse_args()

    terms = [args.brand] + args.alias
    if args.project:
        base = Path("projects") / args.project
        in_dir   = (base / "sliced").resolve()
        out_path = (base / "metrics" / "metrics.csv").resolve()
    else:
        in_dir   = Path(args.input).resolve()
        out_path = Path(args.output).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    files = sorted(in_dir.rglob("q*.md"))
    if not files:
        print(f"В {in_dir} нет файлов qNNN.md")
        return

    rows = []
    for f in files:
        text = f.read_text(encoding="utf-8")
        meta = parse_frontmatter(text)
        sections = split_sections(text)

        answer = sections.get("Ответ", "")
        sources_block = sections.get("Источники", "")
        urls = extract_source_urls(sources_block)

        rows.append({
            "model": meta["model"],
            "question_id": int(meta["question_id"]),
            "question_text": meta.get("question_text", ""),
            "answer_length_chars": len(answer),
            "answer_length_words": len(answer.split()),
            "sources_count": len(urls),
            "brand_in_body": brand_match(answer, terms),
            "brand_in_sources": brand_match(sources_block, terms),
            "brand_position_in_sources": brand_position_in_sources(urls, terms) or "",
        })

    rows.sort(key=lambda r: (r["model"], r["question_id"]))

    with out_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    # Короткая сводка в stdout
    by_model = {}
    for r in rows:
        by_model.setdefault(r["model"], []).append(r)
    print(f"Бренд: {args.brand}  (+{len(args.alias)} алиасов)")
    print(f"Всего строк: {len(rows)}")
    print()
    print(f"{'Модель':<14} {'вопросов':>8} {'brand_body%':>12} {'brand_src%':>11}")
    for model, rs in sorted(by_model.items()):
        n = len(rs)
        body_pct = sum(1 for r in rs if r["brand_in_body"]) / n * 100
        src_pct  = sum(1 for r in rs if r["brand_in_sources"]) / n * 100
        print(f"{model:<14} {n:>8} {body_pct:>11.1f}% {src_pct:>10.1f}%")
    print()
    print(f"Выход: {out_path}")


if __name__ == "__main__":
    main()
