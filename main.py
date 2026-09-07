# а почему не подсвечивается красиво?
import tkinter as tk # подгружаем запрос к библиотеке "tkinter" и обзываем её "tk".
from tkinter import filedialog, scrolledtext
import json
import os

SETTINGS_FILE = "reader_settings.json"


def save_settings(file_path):
    """Сохраняет путь к последнему открытому файлу"""
    settings = {"last_file": file_path}
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


def load_settings():
    """Загружает сохранённые настройки"""
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            settings = json.load(f)
            return settings.get("last_file", "")
    return "" # зачем второй реторн со скобками?

def open_file():
    # Открываем диалог выбора файла (только .txt)
    file_path = filedialog.askopenfilename(filetypes=[("Текстовые файлы", "*.txt")])
    if file_path:  # если пользователь выбрал файл
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()   # читаем весь текст
        text_area.delete("1.0", tk.END)  # очищаем поле
        text_area.insert(tk.END, content) # вставляем текст

        # СОХРАНЯЕМ ПУТЬ К ФАЙЛУ
        save_settings(file_path)
        # Меняем заголовок окна на имя файла
        window.title(f"Моя читалка - {os.path.basename(file_path)}")

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

# ПРОВЕРЯЕМ, ЕСТЬ ЛИ СОХРАНЁННЫЙ ФАЙЛ
last_file = load_settings()
if last_file and os.path.exists(last_file):
    try:
        with open(last_file, "r", encoding="utf-8") as f:
            content = f.read()
        text_area.delete("1.0", tk.END)
        text_area.insert(tk.END, content)
        window.title(f"Моя читалка - {os.path.basename(last_file)}")
    except Exception as e:
        print(f"Ошибка загрузки файла: {e}")
        # Если файл не загрузился, очищаем сохранённый путь
        save_settings("")

# Запускаем главный цикл окна
window.mainloop()