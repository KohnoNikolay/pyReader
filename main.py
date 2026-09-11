# а почему не подсвечивается красиво?
import tkinter as tk # подгружаем запрос к библиотеке "tkinter" и обзываем её "tk".
from tkinter import filedialog, scrolledtext
import json
import os

# === НАСТРОЙКИ ===
SETTINGS_FILE = "reader_settings.json"
current_font_size = 14  # Текущий размер шрифта


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
def load_book(file_path, scroll_position=0):
    """Загружает книгу и восстанавливает позицию прокрутки"""
    if not os.path.exists(file_path):
        return False
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        text_area.delete("1.0", tk.END)
        text_area.insert(tk.END, content)
        # Запоминаем путь к файлу прямо в текстовом поле
        text_area.last_file = file_path
        # Восстанавливаем позицию прокрутки
        if scroll_position > 0:
            text_area.yview_moveto(scroll_position)
        window.title(f"Моя читалка - {os.path.basename(file_path)}")
        return True
    except Exception as e:
        print(f"Ошибка загрузки файла: {e}")
        return False


# === ФУНКЦИЯ ОТКРЫТИЯ ФАЙЛА ===
def open_file():  # Открываем диалог выбора файла (только .txt)
    file_path = filedialog.askopenfilename(filetypes=[("Текстовые файлы", "*.txt")])
    if file_path:  # если пользователь выбрал файл
        if load_book(file_path):
            # Сохраняем настройки (позиция будет сохранена позже при скролле)
            save_settings(file_path, 0, current_font_size)


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

# Кнопка "Открыть файл" слева. Размещаем сначала кнопку над текстовой зоной,
# чтобы она прогружалась первой. Так мы избежим выдавливания кнопки при малом размере окна.
btn_open = tk.Button(bottom_frame, text="Открыть файл", command=open_file)
btn_open.pack(side=tk.LEFT, padx=10)

# Кнопки изменения шрифта справа
btn_font_minus = tk.Button(bottom_frame, text="A−", command=decrease_font, width=4)
btn_font_minus.pack(side=tk.RIGHT, padx=5)

btn_font_plus = tk.Button(bottom_frame, text="A+", command=increase_font, width=4)
btn_font_plus.pack(side=tk.RIGHT, padx=5)

# Создаём текстовое поле с прокруткой
text_area = scrolledtext.ScrolledText(window, wrap=tk.WORD, font=("Arial", current_font_size))
text_area.pack(fill=tk.BOTH, expand=True)
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

# === ЗАПУСК ===
# Запускаем главный цикл окна
window.mainloop()


