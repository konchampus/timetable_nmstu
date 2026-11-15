"""Telegram-native timetable documents; no source text is parsed as markup."""
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
import re
from urllib.parse import urlsplit

from .timetable import TZ, date_week

DAYS = ("Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье")
MONTHS = ("января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря")


@dataclass(frozen=True)
class Span:
    text: str
    kind: str | None = None
    url: str | None = None


def units(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def label(value, maximum: int = 600) -> str:
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\u202a-\u202e\u2066-\u2069]", "", str(value or "")).strip()
    if units(text) <= maximum:
        return text
    result, size = [], 0
    for character in text:
        length = units(character)
        if size + length > maximum - 1:
            break
        result.append(character)
        size += length
    return "".join(result) + "…"


def bold(text) -> dict:
    return {"type": "bold", "text": text}


def paragraph(text) -> dict:
    return {"type": "paragraph", "text": text}


def heading(text, size: int = 3) -> dict:
    return {"type": "heading", "text": text, "size": size}


def day_label(day: date) -> str:
    return f"{DAYS[day.weekday()]}, {day.day} {MONTHS[day.month - 1]}"


def lesson_count(count: int) -> str:
    tail = count % 100
    noun = "занятий" if 11 <= tail <= 14 else "занятие" if count % 10 == 1 else "занятия" if count % 10 in (2, 3, 4) else "занятий"
    return f"{count} {noun}"


def lessons_on(schedule: dict, day: date) -> list[dict]:
    return sorted((item for item in schedule["lessons"] if item["week"] == date_week(day) and item["weekday"] == day.weekday()), key=lambda item: (item["start"], item["number"], item["title"]))


def source_link(schedule: dict) -> str | None:
    value = str(schedule["entity"].get("url", ""))
    parsed = urlsplit(value)
    return value if parsed.scheme == "https" and parsed.netloc == "timetable.magtu.ru" and not parsed.username and not parsed.query and not parsed.fragment else None


def serialized_text(spans: list[Span]) -> dict:
    text, entities, position = [], [], 0
    for span in spans:
        length = units(span.text)
        text.append(span.text)
        if span.kind and length:
            entity = {"type": span.kind, "offset": position, "length": length}
            if span.url:
                entity["url"] = span.url
            entities.append(entity)
        position += length
    return {"text": "".join(text), "entities": entities}


@dataclass
class LessonView:
    cells: list[dict]
    spans: list[Span]
    shortened: bool = False


@dataclass
class Section:
    title: str
    day: date
    rows: list[LessonView] = field(default_factory=list)
    introduction: str | dict | list | None = None


def names(items: list[dict], maximum: int) -> tuple[str, bool]:
    raw = ", ".join(dict.fromkeys(str(item.get("name", "")) for item in items if item.get("name")))
    result = label(raw, maximum)
    return result, result != raw.strip()


def lesson_view(item: dict, day: date, schedule: dict, moment: datetime) -> LessonView:
    raw_title, raw_room, raw_kind = str(item["title"]), str(item.get("room") or "Не указана"), str(item.get("kind") or "")
    title, room, kind = label(raw_title, 600), label(raw_room, 120), label(raw_kind, 100)
    teachers, shortened_teachers = names(item.get("teachers", []), 500)
    groups, shortened_groups = names(item.get("groups", []), 650)
    local = moment.astimezone(TZ)
    current = day == local.date() and item["start"] <= local.strftime("%H:%M") < item["end"]
    timing = f'{item["start"]}–{item["end"]}'
    clock = [bold(f'{item["number"]} пара'), "\n", timing]
    if current:
        clock += ["\n", {"type": "marked", "text": "Сейчас"}]
    subject = [bold(title)]
    if kind:
        subject += ["\n", {"type": "italic", "text": kind}]
    if teachers:
        subject += ["\n", teachers]
    if schedule["entity"]["kind"] == "teacher" and groups:
        subject += ["\nГруппы: ", groups]
    cells = [{"text": text, "align": "left", "valign": "top"} for text in (clock, subject, bold(room))]
    spans = [Span(f'{item["number"]} пара · {timing}' + (" · СЕЙЧАС" if current else "") + "\n", "bold"), Span(title + "\n", "bold"), Span("Аудитория: "), Span(room, "code")]
    if kind:
        spans += [Span(" · "), Span(kind, "italic")]
    if teachers:
        spans += [Span("\nПреподаватель: " + teachers)]
    if schedule["entity"]["kind"] == "teacher" and groups:
        spans += [Span("\nГруппы: " + groups)]
    spans += [Span("\n\n")]
    shortened = title != raw_title.strip() or room != raw_room.strip() or kind != raw_kind.strip() or shortened_teachers or (shortened_groups and schedule["entity"]["kind"] == "teacher")
    return LessonView(cells=cells, spans=spans, shortened=shortened)


def make_sections(schedule: dict, mode: str, day: date, moment: datetime) -> tuple[str, list[Section]]:
    local = moment.astimezone(TZ)
    if mode == "next":
        current = [item for item in lessons_on(schedule, local.date()) if item["start"] <= local.strftime("%H:%M") < item["end"]]
        sections = []
        if current:
            sections.append(Section("Сейчас · " + day_label(local.date()), local.date(), [lesson_view(item, local.date(), schedule, moment) for item in current]))
        for offset in range(15):
            target = local.date() + timedelta(days=offset)
            candidates = [item for item in lessons_on(schedule, target) if offset or item["start"] > local.strftime("%H:%M")]
            if candidates:
                nearest = [item for item in candidates if item["start"] == candidates[0]["start"]]
                start = datetime.combine(target, time.fromisoformat(nearest[0]["start"]), TZ)
                relative = {"type": "date_time", "text": f'в {nearest[0]["start"]}', "unix_time": int(start.timestamp()), "date_time_format": "r"}
                sections.append(Section("Следующая · " + day_label(target), target, [lesson_view(item, target, schedule, moment) for item in nearest], ["Начало ", relative]))
                break
        else:
            sections.append(Section("Ближайшие занятия", local.date(), introduction="В ближайшие 14 дней по опубликованному шаблону занятий нет."))
        return "Сейчас и дальше", sections
    if mode == "week":
        monday = day - timedelta(days=day.weekday())
        title = f'Неделя · {monday:%d.%m}–{monday + timedelta(days=6):%d.%m}'
        days = [monday + timedelta(days=offset) for offset in range(7)]
    else:
        title = "Сегодня" if day == local.date() else "Завтра" if day == local.date() + timedelta(days=1) else "Расписание"
        days = [day]
    return title, [Section(day_label(target), target, [lesson_view(item, target, schedule, moment) for item in lessons_on(schedule, target)]) for target in days]


def documents(schedule: dict, mode: str, day: date, moment: datetime, *, title_override: str | None = None, sections_override: list[Section] | None = None) -> list[dict]:
    """Each document has one complete rich page and one <=3600 UTF-16 fallback.

    Outbox delivery therefore remains one external send per job, not a partial
    multi-message send that could duplicate earlier pages on Telegram retry_after.
    """
    title, source_sections = make_sections(schedule, mode, day, moment)
    title = title_override or title
    if sections_override is not None:
        source_sections = sections_override
    entity = label(schedule["entity"]["name"], 200)
    parity = "Нечётная" if date_week(day) == 1 else "Чётная"
    week_note = f"{parity} неделя" if mode in ("day", "week") else "По расписанию"
    meta = f"{week_note} · Магнитогорск, UTC+5 · на {moment.astimezone(TZ):%H:%M}"
    header_spans = [Span(title + "\n", "bold"), Span(entity + "\n", "bold"), Span(meta + "\n\n", "italic")]
    header_blocks = [heading(title, 2), paragraph(bold(entity)), paragraph(meta)]
    if schedule.get("stale"):
        warning = "⚠ Сохранённая копия: источник давно не обновлялся. Сведения могут быть неточными."
        header_spans += [Span(warning + "\n\n", "bold")]
        header_blocks += [paragraph(bold(warning))]
    try:
        fetched = datetime.fromisoformat(str(schedule["fetched_at"]).replace("Z", "+00:00")).astimezone(TZ).strftime("%d.%m %H:%M")
    except (ValueError, KeyError):
        fetched = "время неизвестно"
    footer = f"Двухнедельный шаблон, не подтверждение замен. Обновлено {fetched}."
    url = source_link(schedule)
    footer_spans = [Span(footer + "\n", "italic")]
    footer_text = [footer]
    if url:
        footer_spans += [Span("Открыть источник", "text_link", url)]
        footer_text += [" · ", {"type": "url", "text": "Источник", "url": url}]
    limit = 3400 - units("".join(span.text for span in header_spans + footer_spans)) - 120
    batches, batch, size = [], [], 0
    for section in source_sections:
        heading_size = units(section.title) + 40
        if not section.rows:
            if batch and size + heading_size + 120 > limit:
                batches.append(batch)
                batch, size = [], 0
            batch.append(Section(section.title, section.day, introduction=section.introduction))
            size += heading_size + 120
            continue
        for row in section.rows:
            row_size = units("".join(span.text for span in row.spans))
            needs_heading = not batch or batch[-1].title != section.title
            if batch and size + row_size + (heading_size if needs_heading else 0) > limit:
                batches.append(batch)
                batch, size, needs_heading = [], 0, True
            if needs_heading:
                batch.append(Section(section.title, section.day, introduction=section.introduction))
                size += heading_size
            batch[-1].rows.append(row)
            size += row_size
    if batch:
        batches.append(batch)
    result = []
    for page_number, sections in enumerate(batches, 1):
        blocks, spans = list(header_blocks), list(header_spans)
        if len(batches) > 1:
            caption = f"Часть {page_number} из {len(batches)}"
            blocks += [paragraph(caption)]
            spans += [Span(caption + "\n\n", "italic")]
        shortened = False
        for section in sections:
            body = []
            if section.introduction:
                body += [paragraph(section.introduction)]
            spans += [Span(section.title + "\n", "bold")]
            if section.rows:
                headers = [{"text": text, "is_header": True, "align": "left", "valign": "middle"} for text in ("Пара · время", "Занятие", "Аудитория")]
                body += [{"type": "table", "cells": [headers, *[row.cells for row in section.rows]], "is_striped": True, "is_compact": True, "is_bordered": True}]
                for row in section.rows:
                    spans += row.spans
                    shortened = shortened or row.shortened
            else:
                note = section.introduction if isinstance(section.introduction, str) else "По опубликованному шаблону занятий нет."
                if not section.introduction:
                    body += [paragraph(note)]
                spans += [Span(note + "\n\n")]
            if mode == "week":
                detail = {"type": "details", "summary": section.title + " · " + lesson_count(len(section.rows)), "blocks": body}
                if section.day == moment.astimezone(TZ).date():
                    detail["is_open"] = True
                blocks.append(detail)
            else:
                blocks += [heading(section.title, 4), *body]
        if shortened:
            note = "Очень длинные поля сокращены; полный текст — в источнике."
            blocks += [paragraph(note)]
            spans += [Span(note + "\n", "italic")]
        blocks += [{"type": "footer", "text": footer_text}]
        spans += footer_spans
        fallback = serialized_text(spans)
        if units(fallback["text"]) > 3900:
            raise ValueError("Telegram schedule page exceeds the safe text limit")
        result.append({"version": 1, "rich_message": {"blocks": blocks, "skip_entity_detection": True}, "fallback": fallback})
    return result
