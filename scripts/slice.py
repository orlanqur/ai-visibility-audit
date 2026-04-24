#!/usr/bin/env python3
"""
slice.py — нарезает сырые ответы AI-моделей на по-вопросные файлы.

Читает: responses/{Model}-{Brand}.md
Пишет: sliced/{Model}/q{NNN}.md (с YAML-frontmatter)

Usage:
    python scripts/slice.py                         # defaults: ./responses -> ./sliced
    python scripts/slice.py --input R --output O    # кастомные пути
"""
import argparse
import json
import re
from pathlib import Path

# Маркеры секций. Допускаем уровни заголовков ## и ### (можно микс).
# Если в следующем аудите формат чуть другой — правь здесь (например, добавь #{2,4}).
QUESTION_RE = re.compile(r"^#{2,3}\s+Вопрос\s+(\d+)\s*$",  re.MULTILINE)
ANSWER_RE   = re.compile(r"^#{2,3}\s+Ответ\s+(\d+)\s*$",   re.MULTILINE)
SOURCES_RE  = re.compile(r"^#{2,3}\s+Источники\s+(\d+)\s*$", re.MULTILINE)

# Имя файла: {Model}-{Brand}.md
FILENAME_RE = re.compile(r"^(?P<model>[^-]+)-(?P<brand>.+)\.md$")

# Строка источника в списке: "1. https://..."
SOURCE_LINE_RE = re.compile(r"^\s*\d+\.\s+(\S+)\s*$")


def parse_file(path: Path):
    text = path.read_text(encoding="utf-8")
    m = FILENAME_RE.match(path.name)
    if not m:
        raise ValueError(f"Не могу извлечь model/brand из имени файла: {path.name}")
    model, brand = m.group("model"), m.group("brand")

    q_marks = list(QUESTION_RE.finditer(text))
    a_marks = {int(m.group(1)): m for m in ANSWER_RE.finditer(text)}
    s_marks = {int(m.group(1)): m for m in SOURCES_RE.finditer(text)}

    blocks = []
    for i, q in enumerate(q_marks):
        q_id = int(q.group(1))
        next_start = q_marks[i + 1].start() if i + 1 < len(q_marks) else len(text)

        a, s = a_marks.get(q_id), s_marks.get(q_id)
        if not a or not s:
            raise ValueError(f"{path.name}: q{q_id} без Ответ или Источники")
        if not (q.end() < a.start() < s.start() < next_start):
            raise ValueError(f"{path.name}: нарушен порядок маркеров для q{q_id}")

        question_text = text[q.end():a.start()].strip()
        answer_body   = text[a.end():s.start()].strip()
        sources_block = text[s.end():next_start].strip()
        # У всех кроме последнего блока в хвосте висит разделитель "---"
        sources_block = re.sub(r"\n*---\s*$", "", sources_block).strip()

        sources = [
            sm.group(1)
            for line in sources_block.splitlines()
            if (sm := SOURCE_LINE_RE.match(line))
        ]

        blocks.append({
            "q_id": q_id,
            "question_text": question_text,
            "answer_body": answer_body,
            "sources_block": sources_block,
            "sources_count": len(sources),
        })

    return model, brand, blocks


def write_slice(out_dir: Path, model: str, brand: str, block: dict):
    model_dir = out_dir / model
    model_dir.mkdir(parents=True, exist_ok=True)
    q_file = model_dir / f"q{block['q_id']:03d}.md"

    # JSON-строка = валидный YAML flow scalar для всех практических случаев
    q_text_yaml = json.dumps(block["question_text"], ensure_ascii=False)

    content = (
        "---\n"
        f"model: {model}\n"
        f"brand: {brand}\n"
        f"question_id: {block['q_id']}\n"
        f"question_text: {q_text_yaml}\n"
        f"sources_count: {block['sources_count']}\n"
        "---\n\n"
        f"## Вопрос\n\n{block['question_text']}\n\n"
        f"## Ответ\n\n{block['answer_body']}\n\n"
        f"## Источники\n\n{block['sources_block']}\n"
    )
    q_file.write_text(content, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", help="имя проекта в projects/ (например: alfa_bank). Если задан, входом становится projects/<NAME>/responses, выходом — projects/<NAME>/sliced")
    ap.add_argument("--input",   default="responses", help="папка с сырыми .md (игнорируется при --project)")
    ap.add_argument("--output",  default="sliced",    help="папка для нарезки (игнорируется при --project)")
    args = ap.parse_args()

    if args.project:
        base = Path("projects") / args.project
        in_dir  = (base / "responses").resolve()
        out_dir = (base / "sliced").resolve()
    else:
        in_dir  = Path(args.input).resolve()
        out_dir = Path(args.output).resolve()

    files = sorted(in_dir.glob("*.md"))
    if not files:
        print(f"В {in_dir} нет .md файлов")
        return

    total_q = 0
    for f in files:
        model, brand, blocks = parse_file(f)
        for b in blocks:
            write_slice(out_dir, model, brand, b)
        total_q += len(blocks)
        print(f"  {f.name}: {len(blocks)} вопросов  (model={model}, brand={brand})")

    print()
    print(f"Обработано файлов: {len(files)}")
    print(f"Найдено вопросов:  {total_q}")
    print(f"Выход:             {out_dir}")


if __name__ == "__main__":
    main()
