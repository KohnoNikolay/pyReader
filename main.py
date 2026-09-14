import tkinter as tk # подгружаем запрос к библиотеке "tkinter" и обзываем её "tk".
from tkinter import filedialog, scrolledtext
from tkinter import ttk        # <-- НОВОЕ: "тематизированные" виджеты (Treeview, Scrollbar и др.)
import json
import os
import xml.etree.ElementTree as ET
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import pymupdf

# === НАСТРОЙКИ ===
SETTINGS_FILE = "reader_settings.json"
current_font_size = 14  # Текущий размер шрифта
toc_visible = False        # видна ли сейчас панель оглавления


def read_pdf(file_path):
    """Читает PDF и возвращает текст"""
    try:
        doc = pymupdf.open(file_path)
        full_text = []

        for page in doc:
            text = page.get_text()
            if text:
                full_text.append(text)

        doc.close()
        return "\n".join(full_text)
    except Exception as e:
        return f"Ошибка чтения PDF: {e}"


def read_epub(file_path):
    """Читает EPUB. Возвращает (текст, оглавление)."""
    try:
        book = epub.read_epub(file_path)
        lines = []
        # Словарь: имя файла внутри EPUB -> номер строки, с которой он начинается
        file_start_lines = {}

        # 1) Идём по всем документам и собираем текст, запоминая стартовые строки
        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            file_name = item.get_name()
            file_start_lines[file_name] = len(lines)

            html_content = item.get_content()
            soup = BeautifulSoup(html_content, 'html.parser')

            for tag in soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                text = tag.get_text(separator=' ', strip=True)
                if text:
                    lines.append(text)
                    lines.append("")

        # 2) Из book.toc строим плоский список с уровнями
        toc = []

        def walk(items, level):
            """Рекурсивно обходит структуру оглавления EPUB."""
            for item in items:
                # Элемент вида (Section, [дети])
                if isinstance(item, tuple):
                    section, children = item
                    # Section — это не ссылка, а просто «папка». Показываем её как заголовок.
                    if getattr(section, 'title', None):
                        toc.append((section.title, -1, level))  # -1 = некуда переходить
                        walk(children, level + 1)
                    else:
                        walk(children, level)
                # Элемент-ссылка на файл
                elif isinstance(item, epub.Link):
                    href = item.href.split('#')[0]  # убираем якорь после #
                    line = file_start_lines.get(href, 0)
                    title = item.title or "Без названия"
                    toc.append((title, line, level))

        walk(book.toc, 0)
        return "\n".join(lines), toc

    except Exception as e:
        return f"Ошибка чтения EPUB: {e}", []


def read_fb2(file_path):
    """Читает FB2. Возвращает (текст, оглавление).
    Оглавление — список кортежей (название, номер_строки, уровень).
    """
    try:
        # --- 1) Читаем файл с автоопределением кодировки ---
        raw = open(file_path, "rb").read()
        # Пробуем популярные кодировки FB2 по очереди
        text_data = None
        for enc in ("utf-8", "windows-1251", "cp1251"):
            try:
                text_data = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if text_data is None:
            return "Не удалось определить кодировку FB2", []

        # --- 2) Парсим XML из строки (а не из файла — так надёжнее с кодировками) ---
        root = ET.fromstring(text_data)

        NS = '{http://www.gribuser.ru/xml/fictionbook/2.0}'
        lines = []   # сюда собираем строки текста
        toc = []     # сюда собираем главы

        def title_to_string(title_elem):
            """Собирает текст из <title> (может состоять из нескольких <p>)."""
            parts = []
            for p in title_elem.iter(f'{NS}p'):
                # itertext() — весь текст внутри тега, включая вложенные <emphasis>, <strong> и т.п.
                t = "".join(p.itertext()).strip()
                if t:
                    parts.append(t)
            return " ".join(parts)

        def process_section(section, level):
            """Обходит одну секцию (главу) и её вложенные секции."""
            # --- Заголовок секции ---
            title_elem = section.find(f'{NS}title')
            if title_elem is not None:
                title = title_to_string(title_elem)
                if title:
                    toc.append((title, len(lines), level))   # номер строки ДО добавления
                    lines.append(f"*** {title} ***")
                    lines.append("")

            # --- Дочерние элементы секции ---
            for child in section:
                tag = child.tag
                if tag == f'{NS}section':
                    process_section(child, level + 1)        # рекурсия во вложенную секцию
                elif tag == f'{NS}title':
                    continue                                 # уже обработали выше
                elif tag in (f'{NS}p', f'{NS}subtitle'):
                    # get_text через itertext склеит текст даже из сложных параграфов
                    t = "".join(child.itertext()).strip()
                    if t:
                        lines.append(t)
                        lines.append("")
                elif tag == f'{NS}empty-line':
                    lines.append("")
                elif tag == f'{NS}epigraph':
                    # эпиграфы тоже читаем как обычный текст
                    for p in child.iter(f'{NS}p'):
                        t = "".join(p.itertext()).strip()
                        if t:
                            lines.append(t)
                            lines.append("")

        # --- 3) Идём ТОЛЬКО по <body>, игнорируя <description> ---
        for body in root.findall(f'{NS}body'):
            # type="notes" — сноски, обычно их в основном тексте не нужно показывать рядом
            # Если хотите — можно оставить. Здесь пропускаем сноски:
            if body.get('type') == 'notes':
                continue

            for child in body:
                if child.tag == f'{NS}section':
                    process_section(child, 0)
                elif child.tag == f'{NS}title':
                    title = title_to_string(child)
                    if title:
                        lines.append(f"*** {title} ***")
                        lines.append("")
                elif child.tag == f'{NS}p':
                    t = "".join(child.itertext()).strip()
                    if t:
                        lines.append(t)
                        lines.append("")
                elif child.tag == f'{NS}epigraph':
                    for p in child.iter(f'{NS}p'):
                        t = "".join(p.itertext()).strip()
                        if t:
                            lines.append(t)
                            lines.append("")

        return "\n".join(lines), toc

    except Exception as e:
        return f"Ошибка чтения FB2: {e}", []


def save_settings(file_path, scroll_position=0.0, font_size=14):
    """Сохраняет настройки: путь к файлу, позицию, размер шрифта"""
    settings = {
        "last_file": file_path,
        "scroll_position": scroll_position,
        "font_size": font_size
    }
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


def load_settings():
    """Загружает сохранённые настройки"""
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            settings = json.load(f)
            return {
                "last_file": settings.get("last_file", ""),
                "scroll_position": settings.get("scroll_position", 0),
                "font_size": settings.get("font_size", 14)
            }
    return {     # Если файла нет — возвращаем значения по умолчанию
        "last_file": "",
        "scroll_position": 0,
        "font_size": 14
    }


# === ФУНКЦИЯ ЗАГРУЗКИ КНИГИ ===
def load_book(file_path, scroll_position=0.0):
    """Загружает книгу и восстанавливает позицию прокрутки"""
    if not os.path.exists(file_path):
        return False
    try:
        # Определяем формат по расширению
        ext = os.path.splitext(file_path)[1].lower()
        toc = []  # по умолчанию пусто (для TXT, PDF)

        if ext == '.txt':
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        elif ext == '.fb2':
            content, toc = read_fb2(file_path)  # ← распаковываем кортеж
        elif ext == '.epub':
            content, toc = read_epub(file_path)  # ← и здесь тоже
        elif ext == '.pdf':
            content = read_pdf(file_path)
        else:
            content = f"Формат {ext} не поддерживается."

        # Отображаем текст
        text_area.delete("1.0", tk.END)
        text_area.insert(tk.END, content)
        # Запоминаем путь к файлу прямо в текстовом поле
        text_area.last_file = file_path

        # Восстанавливаем позицию прокрутки
        if scroll_position > 0:
            text_area.yview_moveto(scroll_position)

        window.title(f"Моя читалка - {os.path.basename(file_path)}")

        # === НОВОЕ: заполняем оглавление ===
        populate_toc(toc)

        return True
    except Exception as e:
        print(f"Ошибка загрузки файла: {e}")
        return False


# === ФУНКЦИЯ ОТКРЫТИЯ ФАЙЛА ===
def open_file():  # Открываем диалог выбора файла (только .txt)
    print("open_file вызвана")  # ← временно
    file_path = filedialog.askopenfilename(
        filetypes=[
            ("Все поддерживаемые", "*.txt *.fb2 *.epub *.pdf"),
            ("Текстовые файлы", "*.txt"),
            ("Книги FB2", "*.fb2"),
            ("Книги EPUB", "*.epub"),
            ("Документы PDF", "*.pdf"),
        ]
    )
    if file_path:  # если пользователь выбрал файл
        if load_book(file_path):
            # Сохраняем настройки (позиция будет сохранена позже при скролле)
            save_settings(file_path, 0.0, current_font_size)


# === СОХРАНЕНИЕ ПОЗИЦИИ ===
def save_scroll_position(event=None):
    """Сохраняет позицию прокрутки и размер шрифта"""
    if hasattr(text_area, 'last_file') and text_area.last_file:
        scroll_pos = text_area.yview()[0]
        save_settings(text_area.last_file, scroll_pos, current_font_size)


def on_closing():
    """Сохраняет настройки при закрытии"""
    if hasattr(text_area, 'last_file') and text_area.last_file:
        scroll_pos = text_area.yview()[0]
        save_settings(text_area.last_file, scroll_pos, current_font_size)
    window.destroy()


def increase_font():
    """Увеличивает размер шрифта на 2 пункта"""
    global current_font_size
    current_font_size = min(current_font_size + 2, 40)  # Максимум 40
    apply_font()
    save_current_settings()


def decrease_font():
    """Уменьшает размер шрифта на 2 пункта"""
    global current_font_size
    current_font_size = max(current_font_size - 2, 8)  # Минимум 8
    apply_font()
    save_current_settings()


def apply_font():
    """Применяет текущий размер шрифта к текстовому полю"""
    text_area.configure(font=("Arial", current_font_size))


def save_current_settings():
    """Сохраняет текущие настройки (вызывается при изменении шрифта)"""
    file_path = getattr(text_area, 'last_file', '')
    scroll_pos = text_area.yview()[0] if file_path else 0
    save_settings(file_path, scroll_pos, current_font_size)


def find_text(event=None):
    """Ищет все совпадения и подсвечивает их"""
    # Убираем старую подсветку
    text_area.tag_remove("highlight", "1.0", tk.END)
    text_area.tag_remove("current", "1.0", tk.END)

    # Получаем текст для поиска
    query = search_entry.get()
    if not query:
        return

    # Начинаем поиск с начала текста
    start_pos = "1.0"
    count = 0

    while True:
        # Ищем следующее совпадение
        pos = text_area.search(query, start_pos, stopindex=tk.END, nocase=True)
        if not pos:
            break  # Совпадений больше нет

        # Определяем конец совпадения
        end_pos = f"{pos}+{len(query)}c"

        # Подсвечиваем
        text_area.tag_add("highlight", pos, end_pos)
        count += 1

        # Продолжаем поиск с конца текущего совпадения
        start_pos = end_pos

    # Если что-то нашли — переходим к первому совпадению
    if count > 0:
        first_pos = text_area.search(query, "1.0", stopindex=tk.END, nocase=True)
        if first_pos:
            end_pos = f"{first_pos}+{len(query)}c"
            text_area.tag_remove("current", "1.0", tk.END)
            text_area.tag_add("current", first_pos, end_pos)
            text_area.see(first_pos)
            text_area.mark_set("found_pos", first_pos)

        # Показываем количество найденных совпадений
        window.title(f"Моя читалка - Найдено: {count}")
    else:
        window.title("Моя читалка - Ничего не найдено")


def find_next(event=None):
    """Переходит к следующему совпадению"""
    query = search_entry.get()
    if not query:
        return

    # Получаем позицию последнего найденного совпадения
    if not text_area.mark_names() or "found_pos" not in text_area.mark_names():
        # Если поиск не запускался — запускаем
        find_text()
        return

    current_pos = text_area.index("found_pos")
    # Ищем следующее совпадение после текущего
    end_pos = f"{current_pos}+{len(query)}c"
    next_pos = text_area.search(query, end_pos, stopindex=tk.END, nocase=True)

    if not next_pos:
        # Если дошли до конца — начинаем сначала
        next_pos = text_area.search(query, "1.0", stopindex=tk.END, nocase=True)
        if not next_pos:
            return

    # Снимаем выделение с предыдущего и выделяем новое
    end_pos = f"{next_pos}+{len(query)}c"
    text_area.tag_remove("current", "1.0", tk.END)
    text_area.tag_add("current", next_pos, end_pos)
    text_area.see(next_pos)
    text_area.mark_set("found_pos", next_pos)


def clear_highlight():
    """Убирает всю подсветку"""
    text_area.tag_remove("highlight", "1.0", tk.END)
    text_area.tag_remove("current", "1.0", tk.END)
    search_entry.delete(0, tk.END)  # Очищаем поле поиска

    # Возвращаем обычный заголовок
    if hasattr(text_area, 'last_file') and text_area.last_file:
        window.title(f"Моя читалка - {os.path.basename(text_area.last_file)}")
    else:
        window.title("Моя читалка")


# === НОВОЕ: ОГЛАВЛЕНИЕ ===

def populate_toc(toc_entries):
    """Заполняет дерево оглавления.
    toc_entries — список кортежей (название, номер_строки, уровень)."""
    # 1) Очищаем дерево
    for item in toc_tree.get_children():
        toc_tree.delete(item)

    # 2) Строим иерархию.
    # parents[level] = id родителя для элементов этого уровня.
    # parents[0] = "" (корень дерева — пустая строка).
    parents = [""]

    for title, line, level in toc_entries:
        # Если вернулись на более высокий уровень — подрезаем лишних «родителей»
        if len(parents) > level + 1:
            del parents[level + 1:]
        # Добираем недостающие уровни (бывает в кривых FB2/EPUB)
        while len(parents) <= level:
            parents.append("")

        parent = parents[level]
        # values=(line,) — кладём номер строки внутрь элемента дерева
        item_id = toc_tree.insert(parent, 'end', text=title, values=(line,))

        # Этот элемент становится родителем для следующего уровня
        if len(parents) > level + 1:
            parents[level + 1] = item_id
        else:
            parents.append(item_id)


def on_toc_select(event=None):
    """Вызывается при выборе элемента в оглавлении — переходим к главе."""
    selected = toc_tree.selection()
    if not selected:
        return
    values = toc_tree.item(selected[0], 'values')
    if not values:
        return

    try:
        line_number = int(values[0])
    except (ValueError, IndexError):
        return

    # -1 означает «это просто заголовок-папка, переходить некуда»
    if line_number < 0:
        return

    # Прокручиваем так, чтобы глава оказалась вверху окна
    total_lines = int(text_area.index('end-1c').split('.')[0])
    if total_lines > 0:
        fraction = line_number / total_lines
        text_area.yview_moveto(fraction)
    text_area.see(f"{line_number + 1}.0")
    text_area.mark_set(tk.INSERT, f"{line_number + 1}.0")


def toggle_toc():
    """Показывает/скрывает панель оглавления."""
    global toc_visible
    if toc_visible:
        toc_frame.pack_forget()
        toc_visible = False
        btn_toc.config(text="☰ Оглавление")
    else:
        # before=text_area — вставляем панель ЛЕВЕЕ текстового поля
        toc_frame.pack(side=tk.LEFT, fill=tk.Y, before=text_area)
        toc_visible = True
        btn_toc.config(text="✕ Скрыть")


# === ГЛАВНОЕ ОКНО ===
# Создаём главное окно
window = tk.Tk()
window.title("Моя читалка")
window.geometry("600x400")  # ширина x высота

# === ВЕРХНЯЯ ПАНЕЛЬ ПОИСКА ===
search_frame = tk.Frame(window)
search_frame.pack(side=tk.TOP, fill=tk.X, pady=5)

# Метка "Поиск:"
label_search = tk.Label(search_frame, text="Поиск:")
label_search.pack(side=tk.LEFT, padx=5)

# Поле ввода для поиска
search_entry = tk.Entry(search_frame, width=30)
search_entry.pack(side=tk.LEFT, padx=5)

# Кнопка "Найти"
btn_find = tk.Button(search_frame, text="Найти", command=find_text, width=8)
btn_find.pack(side=tk.LEFT, padx=5)

# Кнопка "Найти далее"
btn_find_next = tk.Button(search_frame, text="Далее", command=find_next, width=8)
btn_find_next.pack(side=tk.LEFT, padx=5)

# Кнопка "Очистить"
btn_clear = tk.Button(search_frame, text="Очистить", command=clear_highlight, width=8)
btn_clear.pack(side=tk.LEFT, padx=5)

# Нижняя панель с кнопками
bottom_frame = tk.Frame(window)
bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=10)

# Кнопка "Открыть файл" слева
btn_open = tk.Button(bottom_frame, text="Открыть файл", command=open_file)
btn_open.pack(side=tk.LEFT, padx=10)

# === НОВОЕ: кнопка переключения оглавления ===
btn_toc = tk.Button(bottom_frame, text="☰ Оглавление", command=toggle_toc, width=14)
btn_toc.pack(side=tk.LEFT, padx=10)

# Кнопки изменения шрифта справа
btn_font_minus = tk.Button(bottom_frame, text="A−", command=decrease_font, width=4)
btn_font_minus.pack(side=tk.RIGHT, padx=5)

btn_font_plus = tk.Button(bottom_frame, text="A+", command=increase_font, width=4)
btn_font_plus.pack(side=tk.RIGHT, padx=5)

# === НОВОЕ: контейнер, внутри которого будут оглавление (слева) и текст ===
content_frame = tk.Frame(window)
content_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

# --- Панель оглавления (сначала скрыта) ---
toc_frame = tk.Frame(content_frame, bg="#f0f0f0")

toc_label = tk.Label(toc_frame, text="Оглавление",
                     font=("Arial", 11, "bold"), bg="#f0f0f0")
toc_label.pack(side=tk.TOP, fill=tk.X, pady=5)

# Вертикальная прокрутка для дерева
toc_scroll = tk.Scrollbar(toc_frame, orient="vertical")
toc_scroll.pack(side=tk.RIGHT, fill=tk.Y)

# Само дерево оглавления
toc_tree = ttk.Treeview(toc_frame, show='tree', selectmode='browse',
                        yscrollcommand=toc_scroll.set, height=30)
toc_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
toc_scroll.config(command=toc_tree.yview)

# Клик по элементу дерева — переход к главе
toc_tree.bind('<<TreeviewSelect>>', on_toc_select)

# --- Текстовое поле ---
text_area = scrolledtext.ScrolledText(content_frame, wrap=tk.WORD, font=("Arial", current_font_size))
text_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

# Привязываем событие прокрутки к текстовому полю
text_area.bind("<Configure>", save_scroll_position)

# Привязываем событие прокрутки к текстовому полю
text_area.bind("<Configure>", save_scroll_position)

# Настраиваем тег для подсветки найденных слов
text_area.tag_config("highlight", background="yellow", foreground="black")
text_area.tag_config("current", background="orange", foreground="black")

# Привязываем обработчик к крестику окна
window.protocol("WM_DELETE_WINDOW", on_closing)

# === АВТОМАТИЧЕСКАЯ ЗАГРУЗКА ПОСЛЕДНЕГО ФАЙЛА ===
settings = load_settings()
last_file = settings["last_file"]
scroll_position = settings["scroll_position"]
saved_font_size = settings["font_size"]

current_font_size = saved_font_size  # Применяем сохранённый размер
apply_font()

if last_file and os.path.exists(last_file):
    load_book(last_file, scroll_position)

# Горячие клавиши
window.bind("<Control-f>", lambda e: search_entry.focus_set())  # Ctrl+F — фокус на поиск
window.bind("<Return>", find_next)                              # Enter — найти далее
window.bind("<Escape>", lambda e: clear_highlight())            # Escape — очистить
window.bind("<Control-o>", lambda e: open_file())               # Ctrl+O — открыть новый файл

# === ЗАПУСК ===
# Запускаем главный цикл окна
window.mainloop()


