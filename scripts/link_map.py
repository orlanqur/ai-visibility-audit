#!/usr/bin/env python3
"""
link_map.py — карта ссылок и консенсус источников.

Читает: sliced/{Model}/q{NNN}.md
Пишет:
  metrics/link_map.json      — полный инвентарь (домен -> модели, вопросы, URL-ы)
  metrics/link_consensus.csv — плоская таблица: домен, число моделей, число вопросов, частота

Консенсус = домен, упомянутый в источниках у ≥ --min-models моделей.

Usage:
    python scripts/link_map.py --min-models 3 --top 30
"""
import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
SOURCES_SECTION_RE = re.compile(r"^## Источники\s*$(.*)", re.MULTILINE | re.DOTALL)
SOURCE_LINE_RE = re.compile(r"^\s*\d+\.\s+(\S+)\s*$")
# Грубый паттерн URL для извлечения из тела ответа (не только из секции источников)
BODY_URL_RE = re.compile(r"https?://[^\s\)\]\>\"']+")


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


def extract_section_urls(text: str) -> list[str]:
    m = SOURCES_SECTION_RE.search(text)
    if not m:
        return []
    return [
        sm.group(1)
        for line in m.group(1).splitlines()
        if (sm := SOURCE_LINE_RE.match(line))
    ]


def extract_body_urls(text: str) -> list[str]:
    # Берём всё до секции Источники, чтобы не дублировать их
    end = SOURCES_SECTION_RE.search(text)
    body = text[:end.start()] if end else text
    # Вычищаем хвостовые пунктуации Markdown-ссылок
    return [u.rstrip(".,;:") for u in BODY_URL_RE.findall(body)]


def domain_of(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return ""


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", help="имя проекта в projects/ (например: alfa_bank)")
    ap.add_argument("--input",   default="sliced", help="папка с нарезкой (игнорируется при --project)")
    ap.add_argument("--out-json", default="metrics/link_map.json")
    ap.add_argument("--out-csv",  default="metrics/link_consensus.csv")
    ap.add_argument("--min-models", type=int, default=2, help="минимум моделей для консенсуса (default: 2)")
    ap.add_argument("--top", type=int, default=30, help="сколько топ-доменов показать в stdout (default: 30)")
    args = ap.parse_args()

    if args.project:
        base = Path("projects") / args.project
        in_dir   = (base / "sliced").resolve()
        out_json = (base / "metrics" / "link_map.json").resolve()
        out_csv  = (base / "metrics" / "link_consensus.csv").resolve()
    else:
        in_dir   = Path(args.input).resolve()
        out_json = Path(args.out_json).resolve()
        out_csv  = Path(args.out_csv).resolve()
    out_json.parent.mkdir(parents=True, exist_ok=True)

    files = sorted(in_dir.rglob("q*.md"))
    if not files:
        print(f"В {in_dir} нет файлов qNNN.md")
        return

    # domain -> {models: set, questions: set((model, qid)), urls: set, mentions: int}
    inventory = defaultdict(lambda: {
        "models": set(),
        "questions": set(),
        "urls": set(),
        "sources_mentions": 0,
        "body_mentions": 0,
    })

    for f in files:
        text = f.read_text(encoding="utf-8")
        meta = parse_frontmatter(text)
        model = meta["model"]
        qid = int(meta["question_id"])

        for url in extract_section_urls(text):
            d = domain_of(url)
            if not d:
                continue
            rec = inventory[d]
            rec["models"].add(model)
            rec["questions"].add((model, qid))
            rec["urls"].add(url)
            rec["sources_mentions"] += 1

        for url in extract_body_urls(text):
            d = domain_of(url)
            if not d:
                continue
            inventory[d]["body_mentions"] += 1

    # JSON: сортируем по (число моделей, число упоминаний) убыванию
    flat = []
    for d, rec in inventory.items():
        flat.append({
            "domain": d,
            "models_count": len(rec["models"]),
            "models": sorted(rec["models"]),
            "questions_count": len(rec["questions"]),
            "unique_urls": len(rec["urls"]),
            "sources_mentions": rec["sources_mentions"],
            "body_mentions": rec["body_mentions"],
            "urls": sorted(rec["urls"]),
        })
    flat.sort(key=lambda r: (-r["models_count"], -r["sources_mentions"], r["domain"]))

    out_json.write_text(json.dumps(flat, ensure_ascii=False, indent=2), encoding="utf-8")

    # CSV: консенсус (≥ min-models), плоско
    consensus = [r for r in flat if r["models_count"] >= args.min_models]
    with out_csv.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["domain", "models_count", "models", "questions_count",
                    "unique_urls", "sources_mentions", "body_mentions"])
        for r in consensus:
            w.writerow([r["domain"], r["models_count"], "|".join(r["models"]),
                        r["questions_count"], r["unique_urls"],
                        r["sources_mentions"], r["body_mentions"]])

    # Сводка в stdout
    total_domains = len(flat)
    total_urls = sum(r["unique_urls"] for r in flat)
    print(f"Обработано файлов: {len(files)}")
    print(f"Уникальных доменов: {total_domains}")
    print(f"Уникальных URL: {total_urls}")
    print(f"Консенсус (≥{args.min_models} моделей): {len(consensus)} доменов")
    print()
    print(f"Топ-{args.top} доменов по числу моделей, затем по упоминаниям в источниках:")
    print(f"{'домен':<40} {'моделей':>8} {'вопр':>6} {'src':>5} {'body':>5}")
    for r in flat[:args.top]:
        print(f"{r['domain']:<40} {r['models_count']:>8} "
              f"{r['questions_count']:>6} {r['sources_mentions']:>5} {r['body_mentions']:>5}")
    print()
    print(f"JSON: {out_json}")
    print(f"CSV:  {out_csv}")


if __name__ == "__main__":
    main()
