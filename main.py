# а почему не подсвечивается красиво?
import tkinter as tk # подгружаем запрос к библиотеке "tkinter" и обзываем её "tk".
from tkinter import filedialog, scrolledtext
import json
import os

# === НАСТРОЙКИ ===
SETTINGS_FILE = "reader_settings.json"


def save_settings(file_path, scroll_position):
    """Сохраняет путь к последнему открытому файлу и позицию прокрутки"""
    settings = {
        "last_file": file_path,
        "scroll_position": scroll_position
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
                "scroll_position": settings.get("scroll_position", 0)
            }
    return {"last_file": "", "scroll_position": 0} # зачем второй реторн? Как будто условия для false
    # но я не уверен.


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
            save_settings(file_path, 0)


# === СОХРАНЕНИЕ ПОЗИЦИИ ===
def save_scroll_position(event=None):
    """Сохраняет текущую позицию прокрутки"""
    if hasattr(text_area, 'last_file') and text_area.last_file:
        scroll_pos = text_area.yview()[0]  # Получаем позицию в процентах (0.0 - 1.0)
        save_settings(text_area.last_file, scroll_pos)


def on_closing():
    """Сохраняет настройки при закрытии программы"""
    if hasattr(text_area, 'last_file') and text_area.last_file:
        scroll_pos = text_area.yview()[0]
        save_settings(text_area.last_file, scroll_pos)
    window.destroy()

# === ГЛАВНОЕ ОКНО ===
# Создаём главное окно
window = tk.Tk()
window.title("Моя читалка")
window.geometry("600x400")  # ширина x высота

# Создаём кнопку "Открыть файл". Размещаем сначала кнопку над текстовой зоной,
# чтобы она прогружалась первой. Так мы избежим выдавливания кнопки при малом размере окна.
btn_open = tk.Button(window, text="Открыть файл", command=open_file)
btn_open.pack(pady=10, side=tk.BOTTOM)

# Создаём текстовое поле с прокруткой
text_area = scrolledtext.ScrolledText(window, wrap=tk.WORD, font=("Arial", 14))
text_area.pack(fill=tk.BOTH, expand=True)

# Привязываем событие прокрутки к текстовому полю
text_area.bind("<Configure>", save_scroll_position)


# Привязываем обработчик к крестику окна
window.protocol("WM_DELETE_WINDOW", on_closing)

# === АВТОМАТИЧЕСКАЯ ЗАГРУЗКА ПОСЛЕДНЕГО ФАЙЛА ===
settings = load_settings()
last_file = settings.get("last_file", "")
scroll_position = settings.get("scroll_position", 0)

if last_file and os.path.exists(last_file):
    load_book(last_file, scroll_position)

# === ЗАПУСК ===
# Запускаем главный цикл окна
window.mainloop()


