# -*- coding: utf-8 -*-
"""
╔═══════════════════════════════════════════════════════════════════════╗
║  МОЯ ЧИТАЛКА — приложение для чтения электронных книг                 ║
║                                                                       ║
║  Форматы:  TXT, FB2, EPUB, PDF                                        ║
║  Режимы:   скроллинг (непрерывный)  /  листание (постраничный)        ║
║  Функции:  оглавление, поиск с подсветкой, размер шрифта,             ║
║            сохранение позиции чтения, удобные горячие клавиши         ║
║                                                                       ║
║  Установка зависимостей:                                              ║
║     pip install ebooklib beautifulsoup4 pymupdf                       ║
╚═══════════════════════════════════════════════════════════════════════╝
"""

import json
import os
import tkinter as tk
import tkinter.font as tkfont
import xml.etree.ElementTree as ET
from tkinter import ttk, filedialog, messagebox

# --- Необязательные библиотеки (для EPUB и PDF) ---
try:
    import ebooklib
    from ebooklib import epub
    from bs4 import BeautifulSoup
    EPUB_OK = True
except ImportError:
    EPUB_OK = False

try:
    import pymupdf
    PDF_OK = True
except ImportError:
    PDF_OK = False


# ══════════════════════════════════════════════════════════════════════
#  НАСТРОЙКИ ВНЕШНЕГО ВИДА
# ══════════════════════════════════════════════════════════════════════

SETTINGS_FILE = "reader_settings.json"

# Тёплая бежевая палитра — приятна для чтения, не утомляет глаза
COLORS = {
    "bg":         "#f4f1ea",   # фон окна
    "panel":      "#ffffff",   # панели (тулбар, статус-бар, оглавление)
    "text_bg":    "#fdfaf3",   # фон страницы с текстом книги
    "text_fg":    "#2b2b2b",   # цвет текста книги
    "accent":     "#8b6f47",   # акцентный (коричневый)
    "accent_hov": "#a68656",   # акцентный при наведении
    "muted":      "#7a7a7a",   # приглушённый серый
    "border":     "#d8d2c4",   # разделительные линии
}

# Базовые шрифты (могут быть переопределены ниже, если их нет в системе)
READ_FONT = "Georgia"     # для текста книги — serif читать легче
UI_FONT   = "Segoe UI"    # для интерфейса


# ══════════════════════════════════════════════════════════════════════
#  ГЛОБАЛЬНОЕ СОСТОЯНИЕ
# ══════════════════════════════════════════════════════════════════════

current_font_size = 16     # текущий размер шрифта книги
reading_mode      = "scroll"   # "scroll" | "page"
toc_visible       = False  # видна ли панель оглавления


# ══════════════════════════════════════════════════════════════════════
#  ЧТЕНИЕ ФАЙЛОВ РАЗНЫХ ФОРМАТОВ
#  Каждая функция возвращает кортеж: (текст, оглавление, заголовки)
#     оглавление = [(название, номер_строки, уровень), ...]
#     заголовки  = [(номер_строки, уровень), ...]   — для стилизации
# ══════════════════════════════════════════════════════════════════════

def read_txt(path):
    """Читает TXT с автоопределением кодировки."""
    raw = open(path, "rb").read()
    for enc in ("utf-8", "windows-1251", "cp1251", "koi8-r", "latin-1"):
        try:
            return raw.decode(enc), [], []
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace"), [], []


def read_fb2(path):
    """Читает FB2. Разбирает только <body>, пропуская <description>."""
    try:
        # сами определяем кодировку — так надёжнее, чем ET.parse(file)
        raw = open(path, "rb").read()
        text_data = None
        for enc in ("utf-8", "windows-1251", "cp1251"):
            try:
                text_data = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if text_data is None:
            return "Не удалось определить кодировку FB2", [], []

        root = ET.fromstring(text_data)
        NS = "{http://www.gribuser.ru/xml/fictionbook/2.0}"

        lines, toc, headings = [], [], []

        def title_to_string(el):
            """Собирает текст заголовка из всех <p> внутри <title>."""
            parts = []
            for p in el.iter(f"{NS}p"):
                t = "".join(p.itertext()).strip()
                if t:
                    parts.append(t)
            return " ".join(parts)

        def walk_section(section, level):
            """Рекурсивный обход секции (главы)."""
            title_el = section.find(f"{NS}title")
            if title_el is not None:
                title = title_to_string(title_el)
                if title:
                    toc.append((title, len(lines), level))
                    headings.append((len(lines), level))
                    lines.append(title)
                    lines.append("")

            for child in section:
                tag = child.tag
                if tag == f"{NS}section":
                    walk_section(child, level + 1)
                elif tag == f"{NS}title":
                    continue
                elif tag in (f"{NS}p", f"{NS}subtitle"):
                    t = "".join(child.itertext()).strip()
                    if t:
                        lines.append(t)
                        lines.append("")
                elif tag == f"{NS}empty-line":
                    lines.append("")
                elif tag == f"{NS}epigraph":
                    for p in child.iter(f"{NS}p"):
                        t = "".join(p.itertext()).strip()
                        if t:
                            lines.append(t)
                            lines.append("")

        # обходим <body> — но пропускаем <body type="notes"> (сноски)
        for body in root.findall(f"{NS}body"):
            if body.get("type") == "notes":
                continue
            for child in body:
                if child.tag == f"{NS}section":
                    walk_section(child, 0)
                elif child.tag == f"{NS}title":
                    title = title_to_string(child)
                    if title:
                        headings.append((len(lines), 0))
                        lines.append(title)
                        lines.append("")
                elif child.tag == f"{NS}p":
                    t = "".join(child.itertext()).strip()
                    if t:
                        lines.append(t)
                        lines.append("")

        return "\n".join(lines), toc, headings
    except Exception as e:
        return f"Ошибка чтения FB2: {e}", [], []


def read_epub(path):
    """Читает EPUB: собирает текст из HTML-файлов и оглавление из book.toc."""
    if not EPUB_OK:
        return ("Для EPUB нужно установить:\npip install ebooklib beautifulsoup4",
                [], [])
    try:
        book = epub.read_epub(path)
        lines, headings = [], []
        file_start = {}  # имя_файла_в_epub → номер строки

        # 1) собираем текст из всех документов, запоминая стартовые строки
        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            file_start[item.get_name()] = len(lines)
            soup = BeautifulSoup(item.get_content(), "html.parser")
            for tag in soup.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6"]):
                text = tag.get_text(separator=" ", strip=True)
                if not text:
                    continue
                if tag.name.startswith("h"):
                    headings.append((len(lines), int(tag.name[1]) - 1))
                lines.append(text)
                lines.append("")

        # 2) строим плоское оглавление из book.toc (может быть вложенным)
        toc = []

        def walk(items, level):
            for item in items:
                if isinstance(item, tuple):
                    sec, children = item
                    if getattr(sec, "title", None):
                        toc.append((sec.title, -1, level))
                        walk(children, level + 1)
                    else:
                        walk(children, level)
                elif isinstance(item, epub.Link):
                    href = item.href.split("#")[0]
                    toc.append((item.title or "Без названия",
                                file_start.get(href, 0), level))

        walk(book.toc, 0)
        return "\n".join(lines), toc, headings
    except Exception as e:
        return f"Ошибка чтения EPUB: {e}", [], []


def read_pdf(path):
    """Читает PDF, возвращает сплошной текст."""
    if not PDF_OK:
        return ("Для PDF нужно установить:\npip install pymupdf", [], [])
    try:
        doc = pymupdf.open(path)
        parts = [page.get_text() for page in doc if page.get_text()]
        doc.close()
        return "\n".join(parts), [], []
    except Exception as e:
        return f"Ошибка чтения PDF: {e}", [], []


# ══════════════════════════════════════════════════════════════════════
#  СОХРАНЕНИЕ И ЗАГРУЗКА НАСТРОЕК
# ══════════════════════════════════════════════════════════════════════

def load_settings():
    """Возвращает словарь настроек (из файла или по умолчанию)."""
    defaults = {
        "last_file": "",
        "scroll_position": 0.0,
        "font_size": 16,
        "reading_mode": "scroll",
        "toc_visible": False,
        "geometry": "1000x700",
    }
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                defaults.update(json.load(f))
        except Exception:
            pass
    return defaults


def save_settings(**kwargs):
    """Обновляет и сохраняет настройки."""
    data = load_settings()
    data.update(kwargs)
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Не удалось сохранить настройки: {e}")


# ══════════════════════════════════════════════════════════════════════
#  ГЛАВНОЕ ОКНО
# ══════════════════════════════════════════════════════════════════════

root = tk.Tk()
root.title("Моя читалка")
root.configure(bg=COLORS["bg"])
root.minsize(760, 500)

# --- проверяем доступность красивых шрифтов ---
_families = set(tkfont.families())
if READ_FONT not in _families:
    for candidate in ("Times New Roman", "DejaVu Serif", "Liberation Serif"):
        if candidate in _families:
            READ_FONT = candidate
            break
if UI_FONT not in _families:
    for candidate in ("DejaVu Sans", "Arial", "Helvetica"):
        if candidate in _families:
            UI_FONT = candidate
            break

# --- стили ttk ---
style = ttk.Style()
try:
    style.theme_use("clam")
except tk.TclError:
    pass

style.configure("TButton",
                font=(UI_FONT, 10),
                padding=(10, 5),
                borderwidth=0,
                background=COLORS["panel"],
                foreground=COLORS["text_fg"])
style.map("TButton",
          background=[("active", COLORS["accent_hov"])],
          foreground=[("active", "white")])

style.configure("TEntry",
                font=(UI_FONT, 10),
                padding=4,
                fieldbackground=COLORS["panel"])

style.configure("Treeview",
                font=(UI_FONT, 10),
                background=COLORS["panel"],
                fieldbackground=COLORS["panel"],
                rowheight=28,
                borderwidth=0)
style.map("Treeview",
          background=[("selected", COLORS["accent_hov"])],
          foreground=[("selected", "white")])


# ══════════════════════════════════════════════════════════════════════
#  ВЕРХНЯЯ ПАНЕЛЬ (TOOLBAR)
# ══════════════════════════════════════════════════════════════════════

toolbar = tk.Frame(root, bg=COLORS["panel"], height=52)
toolbar.pack(side=tk.TOP, fill=tk.X)
toolbar.pack_propagate(False)
tk.Frame(root, bg=COLORS["border"], height=1).pack(side=tk.TOP, fill=tk.X)

# логотип
tk.Label(toolbar, text="📖  Читалка",
         font=(UI_FONT, 12, "bold"),
         bg=COLORS["panel"], fg=COLORS["accent"]
         ).pack(side=tk.LEFT, padx=(14, 20))

# кнопки открытия / оглавления
btn_open = ttk.Button(toolbar, text="📂  Открыть", command=lambda: open_file())
btn_open.pack(side=tk.LEFT, padx=3, pady=8)

btn_toc = ttk.Button(toolbar, text="☰  Оглавление", command=lambda: toggle_toc())
btn_toc.pack(side=tk.LEFT, padx=3, pady=8)

# разделитель
ttk.Separator(toolbar, orient="vertical").pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=12)

# поиск
tk.Label(toolbar, text="Поиск:", bg=COLORS["panel"], fg=COLORS["text_fg"],
         font=(UI_FONT, 10)).pack(side=tk.LEFT, padx=(0, 4))

search_var = tk.StringVar()
search_entry = ttk.Entry(toolbar, textvariable=search_var, width=22)
search_entry.pack(side=tk.LEFT, padx=(0, 4), pady=8)
search_entry.bind("<Return>", lambda e: find_text())

ttk.Button(toolbar, text="🔍", width=3,
           command=lambda: find_text()).pack(side=tk.LEFT, padx=2)
ttk.Button(toolbar, text="→", width=3,
           command=lambda: find_next()).pack(side=tk.LEFT, padx=2)
ttk.Button(toolbar, text="✕", width=3,
           command=lambda: clear_highlight()).pack(side=tk.LEFT, padx=2)

# правая группа: переключатель режима и размер шрифта
right_group = tk.Frame(toolbar, bg=COLORS["panel"])
right_group.pack(side=tk.RIGHT, padx=10)

ttk.Button(right_group, text="A+", width=4,
           command=lambda: change_font(2)).pack(side=tk.RIGHT, padx=2)
ttk.Button(right_group, text="A−", width=4,
           command=lambda: change_font(-2)).pack(side=tk.RIGHT, padx=2)

btn_mode = ttk.Button(right_group, text="📜  Скролл", width=12,
                      command=lambda: toggle_mode())
btn_mode.pack(side=tk.RIGHT, padx=6)


# ══════════════════════════════════════════════════════════════════════
#  ЦЕНТРАЛЬНАЯ ЧАСТЬ: ОГЛАВЛЕНИЕ + ТЕКСТ
# ══════════════════════════════════════════════════════════════════════

main_area = tk.Frame(root, bg=COLORS["bg"])
main_area.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

# --- панель оглавления (по умолчанию НЕ упакована) ---
toc_frame = tk.Frame(main_area, bg=COLORS["panel"], width=270)
toc_frame.pack_propagate(False)

toc_header = tk.Frame(toc_frame, bg=COLORS["panel"])
toc_header.pack(side=tk.TOP, fill=tk.X, pady=(10, 4))
tk.Label(toc_header, text="Оглавление",
         font=(UI_FONT, 11, "bold"),
         bg=COLORS["panel"], fg=COLORS["text_fg"]
         ).pack(side=tk.LEFT, padx=12)

toc_scroll = ttk.Scrollbar(toc_frame, orient="vertical")
toc_scroll.pack(side=tk.RIGHT, fill=tk.Y)

toc_tree = ttk.Treeview(toc_frame, show="tree",
                        selectmode="browse",
                        yscrollcommand=toc_scroll.set)
toc_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(4, 0), pady=6)
toc_scroll.config(command=toc_tree.yview)
toc_tree.bind("<<TreeviewSelect>>", lambda e: on_toc_select())

# разделительная линия между оглавлением и текстом (тоже не упакована)
toc_sep = tk.Frame(main_area, bg=COLORS["border"], width=1)

# --- текстовое поле (всегда упаковано) ---
text_container = tk.Frame(main_area, bg=COLORS["bg"])
text_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

# «поля» вокруг текста — чтобы страница «дышала»
text_inner = tk.Frame(text_container, bg=COLORS["text_bg"])
text_inner.pack(fill=tk.BOTH, expand=True, padx=20, pady=16)

text_area = tk.Text(
    text_inner,
    wrap="word",
    font=(READ_FONT, current_font_size),
    bg=COLORS["text_bg"],
    fg=COLORS["text_fg"],
    insertbackground=COLORS["accent"],
    selectbackground="#f0e0c0",
    selectforeground=COLORS["text_fg"],
    relief="flat", borderwidth=0,
    padx=28, pady=20,
    spacing1=2, spacing2=2, spacing3=6,
    cursor="arrow",
    state="disabled",       # текст книги недоступен для правки
)
text_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

text_scrollbar = ttk.Scrollbar(text_inner, orient="vertical",
                               command=text_area.yview)
text_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
text_area.configure(yscrollcommand=text_scrollbar.set)


# ══════════════════════════════════════════════════════════════════════
#  НИЖНЯЯ ПАНЕЛЬ (СТАТУС-БАР + навигация по страницам)
# ══════════════════════════════════════════════════════════════════════

tk.Frame(root, bg=COLORS["border"], height=1).pack(side=tk.BOTTOM, fill=tk.X)

status_bar = tk.Frame(root, bg=COLORS["panel"], height=44)
status_bar.pack(side=tk.BOTTOM, fill=tk.X)
status_bar.pack_propagate(False)

# три «колонки»: слева статус, по центру — листание, справа — прогресс
status_bar.grid_columnconfigure(0, weight=1)
status_bar.grid_columnconfigure(2, weight=1)

status_label = tk.Label(status_bar, text="Готово",
                        bg=COLORS["panel"], fg=COLORS["muted"],
                        font=(UI_FONT, 9), anchor="w")
status_label.grid(row=0, column=0, sticky="w", padx=14, pady=10)

# контейнер с кнопками листания (по умолчанию НЕ упакован — только для page-режима)
page_controls = tk.Frame(status_bar, bg=COLORS["panel"])

btn_prev_page = ttk.Button(page_controls, text="◀  Назад", width=12,
                           command=lambda: turn_page(-1))
btn_prev_page.pack(side=tk.LEFT, padx=4)

page_indicator = tk.Label(page_controls, text="— / —",
                          bg=COLORS["panel"], fg=COLORS["text_fg"],
                          font=(UI_FONT, 10, "bold"), width=12)
page_indicator.pack(side=tk.LEFT, padx=6)

btn_next_page = ttk.Button(page_controls, text="Вперёд  ▶", width=12,
                           command=lambda: turn_page(1))
btn_next_page.pack(side=tk.LEFT, padx=4)

progress_label = tk.Label(status_bar, text="0%",
                          bg=COLORS["panel"], fg=COLORS["muted"],
                          font=(UI_FONT, 9), anchor="e")
progress_label.grid(row=0, column=2, sticky="e", padx=14, pady=10)


# ══════════════════════════════════════════════════════════════════════
#  ТЕГИ (СТИЛИ) ДЛЯ ТЕКСТА КНИГИ
# ══════════════════════════════════════════════════════════════════════

def config_text_tags():
    """Перенастраивает теги под текущий размер шрифта."""
    fs = current_font_size
    text_area.tag_config("h1",
        font=(READ_FONT, fs + 8, "bold"),
        foreground="#3b2d1a",
        spacing1=22, spacing3=12, justify="center")
    text_area.tag_config("h2",
        font=(READ_FONT, fs + 5, "bold"),
        foreground="#3b2d1a",
        spacing1=18, spacing3=8)
    text_area.tag_config("h3",
        font=(READ_FONT, fs + 3, "bold"),
        foreground="#4a3a22",
        spacing1=14, spacing3=6)
    text_area.tag_config("h4",
        font=(READ_FONT, fs + 1, "bold"),
        foreground="#4a3a22",
        spacing1=10, spacing3=5)

    text_area.tag_config("highlight", background="#fff3a0", foreground="#000000")
    text_area.tag_config("current",   background="#ffb84d", foreground="#000000")


# ══════════════════════════════════════════════════════════════════════
#  ОТКРЫТИЕ И ЗАГРУЗКА КНИГИ
# ══════════════════════════════════════════════════════════════════════

def set_text_content(content):
    """Заменяет содержимое текстового поля (учитывает state=disabled)."""
    text_area.configure(state="normal")
    text_area.delete("1.0", tk.END)
    text_area.insert("1.0", content)
    text_area.configure(state="disabled")


def open_file():
    """Диалог выбора файла и загрузка книги."""
    path = filedialog.askopenfilename(
        title="Открыть книгу",
        filetypes=[
            ("Все поддерживаемые", "*.txt *.fb2 *.epub *.pdf"),
            ("Текстовые файлы", "*.txt"),
            ("Книги FB2",  "*.fb2"),
            ("Книги EPUB", "*.epub"),
            ("Документы PDF", "*.pdf"),
            ("Все файлы", "*.*"),
        ],
    )
    if not path:
        return
    if load_book(path):
        save_settings(last_file=path, scroll_position=0.0)
        status_label.config(text=f"Открыто: {os.path.basename(path)}")


def load_book(path, scroll_position=0.0):
    """Загружает книгу в текстовое поле и заполняет оглавление."""
    if not os.path.exists(path):
        return False

    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == ".txt":
            content, toc, headings = read_txt(path)
        elif ext == ".fb2":
            content, toc, headings = read_fb2(path)
        elif ext == ".epub":
            content, toc, headings = read_epub(path)
        elif ext == ".pdf":
            content, toc, headings = read_pdf(path)
        else:
            messagebox.showwarning("Формат не поддерживается",
                                   f"Файлы {ext} не поддерживаются.")
            return False
    except Exception as e:
        messagebox.showerror("Ошибка загрузки", str(e))
        return False

    set_text_content(content)          # вставляем текст
    apply_headings(headings)           # накладываем стили заголовков
    text_area.last_file = path         # запоминаем путь

    populate_toc(toc)                  # заполняем оглавление

    if scroll_position > 0:
        text_area.yview_moveto(scroll_position)

    root.title(f"Моя читалка — {os.path.basename(path)}")
    update_progress()
    return True


def apply_headings(headings):
    """Накладывает теги h1..h4 на строки-заголовки."""
    for tag in ("h1", "h2", "h3", "h4"):
        text_area.tag_remove(tag, "1.0", tk.END)
    for line_index, level in headings:
        lvl = min(level, 3)
        text_area.tag_add(f"h{lvl + 1}",
                          f"{line_index + 1}.0",
                          f"{line_index + 1}.end")


# ══════════════════════════════════════════════════════════════════════
#  ОГЛАВЛЕНИЕ
# ══════════════════════════════════════════════════════════════════════

def populate_toc(toc):
    """Заполняет дерево оглавления из плоского списка."""
    for item in toc_tree.get_children():
        toc_tree.delete(item)

    parents = [""]  # parents[level] — id родителя для этого уровня
    for title, line, level in toc:
        # подрезаем лишних «родителей», если уровень понизился
        if len(parents) > level + 1:
            del parents[level + 1:]
        # добираем недостающие уровни
        while len(parents) <= level:
            parents.append("")

        parent = parents[level]
        item_id = toc_tree.insert(parent, "end", text=title, values=(line,))

        if len(parents) > level + 1:
            parents[level + 1] = item_id
        else:
            parents.append(item_id)


def on_toc_select():
    """Переход к выбранной главе."""
    sel = toc_tree.selection()
    if not sel:
        return
    values = toc_tree.item(sel[0], "values")
    if not values:
        return
    try:
        line = int(values[0])
    except (ValueError, IndexError):
        return
    if line < 0:   # это «папка» без своей позиции в тексте
        return

    total = int(text_area.index("end-1c").split(".")[0])
    if total > 0:
        text_area.yview_moveto(line / total)
    text_area.see(f"{line + 1}.0")
    update_progress()


def toggle_toc():
    """Скрывает/показывает панель оглавления."""
    global toc_visible
    if toc_visible:
        toc_frame.pack_forget()
        toc_sep.pack_forget()
        toc_visible = False
        btn_toc.configure(text="☰  Оглавление")
    else:
        # вставляем панель и разделитель ПЕРЕД text_container
        toc_frame.pack(side=tk.LEFT, fill=tk.Y, before=text_container)
        toc_sep.pack(side=tk.LEFT, fill=tk.Y, before=text_container)
        toc_visible = True
        btn_toc.configure(text="✕  Скрыть")
    save_settings(toc_visible=toc_visible)


# ══════════════════════════════════════════════════════════════════════
#  РЕЖИМ ЧТЕНИЯ: СКРОЛЛ / ПОСТРАНИЧНО
# ══════════════════════════════════════════════════════════════════════

def toggle_mode():
    """Переключает между скроллом и постраничным листанием."""
    global reading_mode
    if reading_mode == "scroll":
        reading_mode = "page"
        text_scrollbar.pack_forget()              # прячем полосу прокрутки
        page_controls.grid(row=0, column=1)       # показываем кнопки листания
        btn_mode.configure(text="📖  Страницы")
    else:
        reading_mode = "scroll"
        text_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        page_controls.grid_remove()
        btn_mode.configure(text="📜  Скролл")

    save_settings(reading_mode=reading_mode)
    update_progress()


def turn_page(direction):
    """Перелистывает на одну страницу (1 — вперёд, -1 — назад)."""
    text_area.yview_scroll(direction, "page")
    update_progress()


# ══════════════════════════════════════════════════════════════════════
#  ПОИСК С ПОДСВЕТКОЙ
# ══════════════════════════════════════════════════════════════════════

def find_text():
    """Ищет все совпадения и подсвечивает их жёлтым, первое — оранжевым."""
    text_area.tag_remove("highlight", "1.0", tk.END)
    text_area.tag_remove("current", "1.0", tk.END)

    query = search_var.get().strip()
    if not query:
        status_label.config(text="Введите текст для поиска")
        return

    start, count, first = "1.0", 0, None
    while True:
        pos = text_area.search(query, start, stopindex=tk.END, nocase=True)
        if not pos:
            break
        end = f"{pos}+{len(query)}c"
        text_area.tag_add("highlight", pos, end)
        if first is None:
            first = (pos, end)
        count += 1
        start = end

    if count:
        text_area.tag_add("current", *first)
        text_area.see(first[0])
        text_area.mark_set("found_pos", first[0])
        status_label.config(text=f"Найдено: {count}")
    else:
        status_label.config(text="Ничего не найдено")


def find_next():
    """Переходит к следующему совпадению (циклически)."""
    query = search_var.get().strip()
    if not query:
        return
    if "found_pos" not in text_area.mark_names():
        find_text()
        return

    current = text_area.index("found_pos")
    end_current = f"{current}+{len(query)}c"
    nxt = text_area.search(query, end_current, stopindex=tk.END, nocase=True)
    if not nxt:   # дошли до конца — начинаем с начала
        nxt = text_area.search(query, "1.0", stopindex=tk.END, nocase=True)
    if not nxt:
        return

    end = f"{nxt}+{len(query)}c"
    text_area.tag_remove("current", "1.0", tk.END)
    text_area.tag_add("current", nxt, end)
    text_area.see(nxt)
    text_area.mark_set("found_pos", nxt)


def clear_highlight():
    """Снимает всю подсветку и очищает поле поиска."""
    text_area.tag_remove("highlight", "1.0", tk.END)
    text_area.tag_remove("current", "1.0", tk.END)
    search_var.set("")
    status_label.config(text="Готово")


# ══════════════════════════════════════════════════════════════════════
#  РАЗМЕР ШРИФТА
# ══════════════════════════════════════════════════════════════════════

def change_font(delta):
    """Меняет размер шрифта в пределах 8..40."""
    global current_font_size
    current_font_size = max(8, min(40, current_font_size + delta))
    apply_font()
    save_current_settings()


def apply_font():
    """Применяет текущий размер шрифта и обновляет теги."""
    text_area.configure(font=(READ_FONT, current_font_size))
    config_text_tags()
    update_progress()


# ══════════════════════════════════════════════════════════════════════
#  ПРОГРЕСС И СОХРАНЕНИЕ ПОЗИЦИИ
# ══════════════════════════════════════════════════════════════════════

def update_progress(event=None):
    """Обновляет индикатор прогресса и (в page-режиме) номер страницы."""
    try:
        top, bottom = text_area.yview()
    except tk.TclError:
        return

    percent = int(bottom * 100) if bottom >= 1.0 else int(top * 100)
    progress_label.config(text=f"{percent}%")

    if reading_mode == "page":
        total_lines = int(text_area.index("end-1c").split(".")[0])
        visible = max(1, int((bottom - top) * total_lines))
        total_pages = max(1, round(total_lines / visible))
        current_page = min(total_pages,
                           int(top * total_lines / visible) + 1)
        page_indicator.config(text=f"{current_page} / {total_pages}")


def save_current_settings():
    """Сохраняет текущее состояние (файл, позиция, шрифт, режим)."""
    path = getattr(text_area, "last_file", "")
    pos = text_area.yview()[0] if path else 0
    save_settings(
        last_file=path,
        scroll_position=pos,
        font_size=current_font_size,
        reading_mode=reading_mode,
        toc_visible=toc_visible,
    )


def on_closing():
    """Сохранение при закрытии окна."""
    save_settings(geometry=root.geometry())
    save_current_settings()
    root.destroy()


# ══════════════════════════════════════════════════════════════════════
#  КОПИРОВАНИЕ ВЫДЕЛЕННОГО (disabled-Text сам не копирует)
# ══════════════════════════════════════════════════════════════════════

def copy_selection(event=None):
    try:
        sel = text_area.get(tk.SEL_FIRST, tk.SEL_LAST)
        root.clipboard_clear()
        root.clipboard_append(sel)
    except tk.TclError:
        pass


# ══════════════════════════════════════════════════════════════════════
#  ГОРЯЧИЕ КЛАВИШИ
# ══════════════════════════════════════════════════════════════════════

root.bind("<Control-o>",     lambda e: open_file())
root.bind("<Control-f>",     lambda e: search_entry.focus_set())
root.bind("<Control-t>",     lambda e: toggle_toc())
root.bind("<Control-plus>",  lambda e: change_font(2))
root.bind("<Control-equal>", lambda e: change_font(2))   # та же клавиша без Shift
root.bind("<Control-minus>", lambda e: change_font(-2))
root.bind("<Control-c>",     copy_selection)
root.bind("<F3>",            lambda e: find_next())
root.bind("<Escape>",        lambda e: (clear_highlight(), text_area.focus_set()))

# листание стрелками/PageUp/PageDown — только в page-режиме
root.bind("<Next>",  lambda e: turn_page(1)  if reading_mode == "page" else None)
root.bind("<Prior>", lambda e: turn_page(-1) if reading_mode == "page" else None)
root.bind("<Right>", lambda e: turn_page(1)  if reading_mode == "page" else None)
root.bind("<Left>",  lambda e: turn_page(-1) if reading_mode == "page" else None)

# обновляем прогресс при скролле / изменении размера
for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>",
            "<KeyRelease>", "<Configure>"):
    text_area.bind(seq, lambda e: root.after(30, update_progress))

root.protocol("WM_DELETE_WINDOW", on_closing)


# ══════════════════════════════════════════════════════════════════════
#  ЗАПУСК ПРИЛОЖЕНИЯ
# ══════════════════════════════════════════════════════════════════════

# применяем базовые теги и шрифт
config_text_tags()

# загружаем сохранённые настройки
_s = load_settings()
current_font_size = _s.get("font_size", 16)
reading_mode      = "scroll"                 # сначала выставим значение по умолчанию
root.geometry(_s.get("geometry", "1000x700"))

apply_font()

# включаем нужный режим (если был сохранён page — переключаемся)
if _s.get("reading_mode") == "page":
    toggle_mode()

# показываем оглавление, если было открыто
if _s.get("toc_visible"):
    toggle_toc()

# автозагрузка последней книги
_last = _s.get("last_file", "")
if _last and os.path.exists(_last):
    if load_book(_last, _s.get("scroll_position", 0.0)):
        status_label.config(text=f"Продолжаем: {os.path.basename(_last)}")
else:
    # приветственное сообщение
    welcome = (
        "\n\n"
        "        📖   Добро пожаловать в читалку!\n\n"
        "        Ctrl+O — открыть книгу\n"
        "        Ctrl+F — поиск\n"
        "        Ctrl+T — оглавление\n"
        "        Ctrl + / Ctrl − — размер шрифта\n"
        "        Стрелки / PageUp / PageDown — листание в режиме страниц\n\n"
        "        Поддерживаются форматы: TXT, FB2, EPUB, PDF"
    )
    set_text_content(welcome)
    text_area.tag_add("h1", "3.0", "3.end")

root.mainloop()