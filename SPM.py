
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import sqlite3
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import json
import os
from PIL import Image, ImageTk, ImageOps
import io
import threading
import time
import re
import sys
import csv
import webbrowser
from urllib.parse import urlparse
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple
import logging
import urllib3
from urllib3.exceptions import InsecureRequestWarning

# Отключаем предупреждения о SSL
urllib3.disable_warnings(InsecureRequestWarning)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('price_monitor.log'),
        logging.StreamHandler()
    ]
)

@dataclass
class Product:
    """Класс для хранения данных о товаре"""
    id: int
    name: str
    url: str
    current_price: Optional[float]
    previous_price: Optional[float]
    currency: str
    last_updated: str
    selector_type: str
    selector_path: str
    image_data: Optional[bytes] = None
    category: str = "Без категории"

class PriceMonitorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("💰 Smart Price Monitor Pro")
        self.root.geometry("1400x800")
        
        # Установка стиля
        self.setup_styles()
        
        # Центрирование окна
        self.center_window()
        
        # Иконка приложения
        self.set_icon()
        
        # Подключение к базе данных
        self.conn = None
        self.create_database()
        
        # Кэш изображений
        self.image_cache = {}
        self.current_product_id = None
        self.update_thread = None
        self.stop_update = False
        self.products = []
        
        # Конфигурация
        self.config = self.load_config()
        
        # Создание интерфейса
        self.create_widgets()
        
        # Загрузка данных
        self.load_products()
        
        # Запуск автообновления, если включено
        if self.config.get('auto_update', False):
            self.start_auto_update()
    
    def setup_styles(self):
        """Настройка стилей интерфейса"""
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # Цветовая схема
        self.colors = {
            'primary': '#2c3e50',
            'secondary': '#3498db',
            'success': '#2ecc71',
            'danger': '#e74c3c',
            'warning': '#f39c12',
            'light': '#ecf0f1',
            'dark': '#34495e',
            'background': '#f5f6fa',
            'card': '#ffffff'
        }
        
        # Настройка стилей виджетов
        self.style.configure('Title.TLabel', 
                           font=('Segoe UI', 24, 'bold'),
                           foreground=self.colors['primary'])
        
        self.style.configure('Subtitle.TLabel',
                           font=('Segoe UI', 14),
                           foreground=self.colors['dark'])
        
        self.style.configure('Card.TFrame',
                           background=self.colors['card'],
                           relief='raised',
                           borderwidth=1)
        
        self.style.configure('Primary.TButton',
                           font=('Segoe UI', 10, 'bold'),
                           background=self.colors['secondary'],
                           foreground='white',
                           borderwidth=0)
        
        self.style.map('Primary.TButton',
                      background=[('active', '#2980b9')])
        
        self.style.configure('Success.TButton',
                           font=('Segoe UI', 10, 'bold'),
                           background=self.colors['success'],
                           foreground='white',
                           borderwidth=0)
        
        self.style.configure('Danger.TButton',
                           font=('Segoe UI', 10, 'bold'),
                           background=self.colors['danger'],
                           foreground='white',
                           borderwidth=0)
        
        self.style.configure('Warning.TButton',
                           font=('Segoe UI', 10, 'bold'),
                           background=self.colors['warning'],
                           foreground='white',
                           borderwidth=0)
        
        # Настройка Treeview
        self.style.configure('Treeview',
                           font=('Segoe UI', 10),
                           rowheight=30,
                           background=self.colors['light'],
                           fieldbackground=self.colors['light'])
        
        self.style.configure('Treeview.Heading',
                           font=('Segoe UI', 11, 'bold'),
                           background=self.colors['primary'],
                           foreground='white',
                           relief='flat')
        
        self.style.map('Treeview.Heading',
                      background=[('active', self.colors['dark'])])
    
    def center_window(self):
        """Центрирование окна на экране"""
        self.root.update_idletasks()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        window_width = 1400
        window_height = 800
        
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        
        self.root.geometry(f'{window_width}x{window_height}+{x}+{y}')
    
    def set_icon(self):
        """Установка иконки приложения"""
        try:
            # Создаем простую иконку из данных
            icon_data = """
                R0lGODlhIAAgAIAAAAAAAP///yH5BAAAAAAALAAAAAAgACAAAAMLjI+py+0Po5y0
                ugUAOw==
            """
            self.root.iconbitmap(default='')
        except:
            pass
    
    def create_database(self):
        """Создание и подключение к базе данных"""
        try:
            self.conn = sqlite3.connect('price_monitor.db', check_same_thread=False)
            self.conn.execute("PRAGMA foreign_keys = ON")
            cursor = self.conn.cursor()
            
            # Таблица товаров с дополнительными полями
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    url TEXT NOT NULL,
                    category TEXT DEFAULT 'Без категории',
                    image_url TEXT,
                    image_data BLOB,
                    current_price REAL,
                    previous_price REAL,
                    currency TEXT DEFAULT 'RUB',
                    last_updated TEXT,
                    selector_type TEXT DEFAULT 'CSS',
                    selector_path TEXT,
                    min_price REAL,
                    max_price REAL,
                    target_price REAL,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица истории цен
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER,
                    price REAL NOT NULL,
                    date TEXT NOT NULL,
                    FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE,
                    UNIQUE(product_id, date)
                )
            ''')
            
            # Таблица настроек
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')
            
            # Индексы для улучшения производительности
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_products_category ON products(category)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_products_active ON products(is_active)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_price_history_product_date ON price_history(product_id, date)')
            
            self.conn.commit()
            
        except sqlite3.Error as e:
            logging.error(f"Ошибка создания базы данных: {e}")
            messagebox.showerror("Ошибка базы данных", f"Не удалось создать базу данных:\n{e}")
            sys.exit(1)
    
    def load_config(self):
        """Загрузка конфигурации из базы данных"""
        config = {
            'update_interval': 300,
            'auto_update': False,
            'notifications': True,
            'currency': 'RUB',
            'theme': 'light'
        }
        
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT key, value FROM settings")
            rows = cursor.fetchall()
            
            for key, value in rows:
                if key in config:
                    # Преобразование типов
                    if key in ['update_interval']:
                        config[key] = int(value)
                    elif key in ['auto_update', 'notifications']:
                        config[key] = bool(int(value))
                    else:
                        config[key] = value
                        
        except Exception as e:
            logging.error(f"Ошибка загрузки конфигурации: {e}")
        
        return config
    
    def save_config(self):
        """Сохранение конфигурации в базу данных"""
        try:
            cursor = self.conn.cursor()
            for key, value in self.config.items():
                # Преобразование boolean в int для SQLite
                if isinstance(value, bool):
                    value = int(value)
                cursor.execute(
                    "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                    (key, str(value))
                )
            self.conn.commit()
        except Exception as e:
            logging.error(f"Ошибка сохранения конфигурации: {e}")
    
    def create_widgets(self):
        """Создание виджетов интерфейса"""
        # Основной контейнер
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Верхняя панель с заголовком
        self.create_header(main_container)
        
        # Основное содержание
        content_frame = ttk.Frame(main_container)
        content_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        
        # Левая панель - управление
        left_panel = ttk.Frame(content_frame, width=350)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 10))
        left_panel.pack_propagate(False)
        
        self.create_control_panel(left_panel)
        
        # Правая панель - данные и графики
        right_panel = ttk.Frame(content_frame)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        self.create_data_panel(right_panel)
        
        # Статус бар
        self.create_status_bar(main_container)
    
    def create_header(self, parent):
        """Создание верхней панели"""
        header_frame = ttk.Frame(parent, style='Card.TFrame')
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Заголовок и логотип
        title_frame = ttk.Frame(header_frame)
        title_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=20, pady=10)
        
        ttk.Label(title_frame, text="💰", font=('Segoe UI', 36)).pack(side=tk.LEFT, padx=(0, 10))
        
        title_text = ttk.Label(title_frame, 
                              text="Smart Price Monitor Pro",
                              style='Title.TLabel')
        title_text.pack(side=tk.LEFT)
        
        # Кнопки управления
        button_frame = ttk.Frame(header_frame)
        button_frame.pack(side=tk.RIGHT, padx=20, pady=10)
        
        ttk.Button(button_frame, text="📊 Статистика", 
                  command=self.show_statistics, style='Primary.TButton').pack(side=tk.LEFT, padx=5)
        
        ttk.Button(button_frame, text="⚙ Настройки", 
                  command=self.show_settings, style='Primary.TButton').pack(side=tk.LEFT, padx=5)
        
        ttk.Button(button_frame, text="📤 Экспорт", 
                  command=self.export_data, style='Success.TButton').pack(side=tk.LEFT, padx=5)
    
    def create_control_panel(self, parent):
        """Создание панели управления"""
        # Категории товаров
        categories_frame = ttk.LabelFrame(parent, text="📁 Категории", padding=15)
        categories_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.category_var = tk.StringVar(value="Все товары")
        self.category_combo = ttk.Combobox(categories_frame, 
                                          textvariable=self.category_var,
                                          state="readonly",
                                          font=('Segoe UI', 10))
        self.category_combo.pack(fill=tk.X)
        self.category_combo.bind('<<ComboboxSelected>>', self.filter_by_category)
        
        # Форма добавления/редактирования товара
        form_frame = ttk.LabelFrame(parent, text="➕ Добавить товар", padding=15)
        form_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Поля формы
        fields = [
            ("Название товара:", "name"),
            ("URL страницы:", "url"),
            ("Категория:", "category"),
            ("CSS-селектор цены:", "selector"),
            ("Целевая цена:", "target_price")
        ]
        
        self.form_vars = {}
        for i, (label, key) in enumerate(fields):
            ttk.Label(form_frame, text=label).grid(row=i, column=0, sticky=tk.W, pady=5)
            
            if key == 'category':
                var = tk.StringVar()
                entry = ttk.Combobox(form_frame, textvariable=var, state="normal")
                entry['values'] = self.get_categories()
            elif key == 'selector':
                var = tk.StringVar(value=".price, .product-price, [itemprop='price']")
                entry = ttk.Entry(form_frame, textvariable=var, font=('Segoe UI', 10))
            else:
                var = tk.StringVar()
                entry = ttk.Entry(form_frame, textvariable=var, font=('Segoe UI', 10))
            
            entry.grid(row=i, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
            self.form_vars[key] = var
        
        form_frame.columnconfigure(1, weight=1)
        
        # Кнопки управления формой
        button_frame = ttk.Frame(form_frame)
        button_frame.grid(row=len(fields), column=0, columnspan=2, pady=15)
        
        ttk.Button(button_frame, text="Добавить", 
                  command=self.add_product, style='Success.TButton',
                  width=12).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(button_frame, text="Обновить", 
                  command=self.update_product, style='Primary.TButton',
                  width=12).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(button_frame, text="Очистить", 
                  command=self.clear_form, width=12).pack(side=tk.LEFT, padx=5)
        
        # Управление мониторингом
        monitor_frame = ttk.LabelFrame(parent, text="📈 Мониторинг", padding=15)
        monitor_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(monitor_frame, text="🔄 Обновить все цены", 
                  command=self.update_all_prices, style='Primary.TButton').pack(fill=tk.X, pady=5)
        
        ttk.Button(monitor_frame, text="🚀 Обновить выбранное", 
                  command=self.update_selected_price).pack(fill=tk.X, pady=5)
        
        self.auto_update_var = tk.BooleanVar(value=self.config.get('auto_update', False))
        ttk.Checkbutton(monitor_frame, text="Автообновление", 
                       variable=self.auto_update_var,
                       command=self.toggle_auto_update).pack(anchor=tk.W, pady=5)
        
        # Интервал обновления
        interval_frame = ttk.Frame(monitor_frame)
        interval_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(interval_frame, text="Интервал (мин):").pack(side=tk.LEFT)
        self.interval_var = tk.StringVar(value=str(self.config.get('update_interval', 300) // 60))
        ttk.Entry(interval_frame, textvariable=self.interval_var, width=8).pack(side=tk.LEFT, padx=5)
        
        # Информация о товаре
        info_frame = ttk.LabelFrame(parent, text="ℹ Информация", padding=15)
        info_frame.pack(fill=tk.BOTH, expand=True)
        
        self.info_text = scrolledtext.ScrolledText(info_frame, 
                                                  height=10,
                                                  font=('Segoe UI', 10),
                                                  wrap=tk.WORD)
        self.info_text.pack(fill=tk.BOTH, expand=True)
        self.info_text.config(state=tk.DISABLED)
    
    def create_data_panel(self, parent):
        """Создание панели данных"""
        notebook = ttk.Notebook(parent)
        notebook.pack(fill=tk.BOTH, expand=True)
        
        # Вкладка со списком товаров
        products_tab = ttk.Frame(notebook)
        notebook.add(products_tab, text="📋 Товары")
        
        self.create_products_table(products_tab)
        
        # Вкладка с графиками
        charts_tab = ttk.Frame(notebook)
        notebook.add(charts_tab, text="📊 Графики")
        
        self.create_charts_panel(charts_tab)
        
        # Вкладка с деталями товара
        details_tab = ttk.Frame(notebook)
        notebook.add(details_tab, text="👁 Детали")
        
        self.create_details_panel(details_tab)
    
    def create_products_table(self, parent):
        """Создание таблицы товаров"""
        # Панель поиска и фильтров
        filter_frame = ttk.Frame(parent)
        filter_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(filter_frame, text="Поиск:").pack(side=tk.LEFT, padx=(0, 5))
        
        self.search_var = tk.StringVar()
        self.search_var.trace('w', lambda *args: self.search_products())
        search_entry = ttk.Entry(filter_frame, textvariable=self.search_var, width=30)
        search_entry.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(filter_frame, text="Сброс", 
                  command=self.reset_filters, width=10).pack(side=tk.LEFT, padx=5)
        
        # Таблица товаров
        table_frame = ttk.Frame(parent)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        columns = ("ID", "Название", "Категория", "Текущая цена", "Изменение", "Статус", "Обновлено")
        
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=15)
        
        # Настройка колонок
        col_widths = {
            "ID": 50, "Название": 250, "Категория": 120,
            "Текущая цена": 100, "Изменение": 100, "Статус": 100, "Обновлено": 150
        }
        
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=col_widths.get(col, 100), anchor=tk.CENTER)
        
        # Вертикальная прокрутка
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        
        # Горизонтальная прокрутка
        hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(xscrollcommand=hsb.set)
        
        # Размещение
        self.tree.grid(row=0, column=0, sticky=tk.NSEW)
        vsb.grid(row=0, column=1, sticky=tk.NS)
        hsb.grid(row=1, column=0, sticky=tk.EW)
        
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)
        
        # Привязка событий
        self.tree.bind('<<TreeviewSelect>>', self.on_product_select)
        self.tree.bind('<Double-1>', self.on_product_double_click)
        
        # Контекстное меню
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Копировать URL", command=self.copy_url)
        self.context_menu.add_command(label="Открыть в браузере", command=self.open_in_browser)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Обновить цену", command=self.update_selected_price)
        self.context_menu.add_command(label="Показать историю", command=self.show_price_history)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Удалить товар", command=self.delete_product)
        
        self.tree.bind('<Button-3>', self.show_context_menu)
    
    def create_charts_panel(self, parent):
        """Создание панели с графиками"""
        # Контейнер для графиков
        self.charts_container = ttk.Frame(parent)
        self.charts_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Кнопка обновления графиков
        ttk.Button(parent, text="Обновить графики", 
                  command=self.update_charts, style='Primary.TButton').pack(pady=10)
    
    def create_details_panel(self, parent):
        """Создание панели деталей товара"""
        # Основной контейнер
        details_container = ttk.Frame(parent)
        details_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Левая часть - изображение
        image_frame = ttk.LabelFrame(details_container, text="🖼 Изображение", padding=10)
        image_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        self.image_label = ttk.Label(image_frame, 
                                    text="Изображение не загружено\n\nПеретащите файл сюда",
                                    font=('Segoe UI', 11),
                                    relief='sunken',
                                    anchor=tk.CENTER)
        self.image_label.pack(fill=tk.BOTH, expand=True)
        
        # Кнопки для изображения
        image_buttons = ttk.Frame(image_frame)
        image_buttons.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(image_buttons, text="Загрузить файл", 
                  command=self.load_image_from_file, width=15).pack(side=tk.LEFT, padx=2)
        
        ttk.Button(image_buttons, text="Загрузить URL", 
                  command=self.load_image_from_url, width=15).pack(side=tk.LEFT, padx=2)
        
        ttk.Button(image_buttons, text="Удалить", 
                  command=self.delete_image, width=15).pack(side=tk.LEFT, padx=2)
        
        # Правая часть - детальная информация
        info_frame = ttk.LabelFrame(details_container, text="📋 Информация", padding=10)
        info_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        self.details_text = scrolledtext.ScrolledText(info_frame,
                                                     height=20,
                                                     font=('Segoe UI', 10),
                                                     wrap=tk.WORD)
        self.details_text.pack(fill=tk.BOTH, expand=True)
        self.details_text.config(state=tk.DISABLED)
        
        # Кнопки действий
        action_frame = ttk.Frame(details_container)
        action_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(action_frame, text="Сохранить изменения", 
                  command=self.save_product_changes, style='Success.TButton').pack(side=tk.LEFT, padx=5)
        
        ttk.Button(action_frame, text="Сброс", 
                  command=self.reset_details).pack(side=tk.LEFT, padx=5)
    
    def create_status_bar(self, parent):
        """Создание статус бара"""
        self.status_bar = ttk.Frame(parent, relief=tk.SUNKEN)
        self.status_bar.pack(fill=tk.X, pady=(10, 0))
        
        self.status_label = ttk.Label(self.status_bar, text="Готов к работе", relief=tk.SUNKEN)
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2, pady=2)
        
        self.update_time_label = ttk.Label(self.status_bar, text="", width=20)
        self.update_time_label.pack(side=tk.RIGHT, padx=2, pady=2)
        
        # Таймер обновления времени
        self.update_clock()
    
    def update_clock(self):
        """Обновление времени в статус баре"""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.update_time_label.config(text=f"🕐 {current_time}")
        self.root.after(1000, self.update_clock)
    
    def get_categories(self):
        """Получение списка категорий из базы данных"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT DISTINCT category FROM products WHERE category != '' ORDER BY category")
            categories = ["Все товары"] + [row[0] for row in cursor.fetchall()]
            return categories
        except Exception as e:
            logging.error(f"Ошибка получения категорий: {e}")
            return ["Все товары"]
    
    def filter_by_category(self, event=None):
        """Фильтрация товаров по категории"""
        category = self.category_var.get()
        self.load_products(category=category if category != "Все товары" else None)
    
    def load_products(self, category=None, search_text=None):
        """Загрузка товаров из базы данных"""
        try:
            # Очистка таблицы
            for item in self.tree.get_children():
                self.tree.delete(item)
            
            # Построение запроса
            query = "SELECT id, name, category, current_price, previous_price, last_updated FROM products WHERE is_active = 1"
            params = []
            
            if category:
                query += " AND category = ?"
                params.append(category)
            
            if search_text:
                query += " AND (name LIKE ? OR category LIKE ?)"
                params.extend([f"%{search_text}%", f"%{search_text}%"])
            
            query += " ORDER BY last_updated DESC"
            
            cursor = self.conn.cursor()
            cursor.execute(query, params)
            products = cursor.fetchall()
            
            self.products = []
            for product in products:
                product_id, name, category, current_price, previous_price, last_updated = product
                
                # Расчет изменения цены
                change_text = "—"
                change_percent = 0
                tags = ()
                
                if current_price is not None and previous_price is not None and previous_price > 0:
                    change = current_price - previous_price
                    change_percent = (change / previous_price) * 100
                    
                    if change > 0:
                        change_text = f"▲ {change:.2f} ({change_percent:.1f}%)"
                        tags = ('price_up',)
                    elif change < 0:
                        change_text = f"▼ {abs(change):.2f} ({abs(change_percent):.1f}%)"
                        tags = ('price_down',)
                    else:
                        change_text = "—"
                        tags = ('price_same',)
                
                # Определение статуса
                status = "✅ В наличии" if current_price is not None else "❓ Не проверен"
                if current_price is not None:
                    cursor.execute("SELECT target_price FROM products WHERE id = ?", (product_id,))
                    target_price_row = cursor.fetchone()
                    if target_price_row and target_price_row[0] and current_price <= target_price_row[0]:
                        status = "🎯 Цель достигнута"
                        tags = ('target_reached',)
                
                # Форматирование цены
                price_text = f"{current_price:.2f} ₽" if current_price is not None else "—"
                
                # Добавление в таблицу
                item_id = self.tree.insert("", tk.END, values=(
                    product_id, name, category, price_text, change_text, status, last_updated
                ), tags=tags)
                
                # Сохранение в списке
                self.products.append(Product(
                    id=product_id,
                    name=name,
                    url="",
                    current_price=current_price,
                    previous_price=previous_price,
                    currency="RUB",
                    last_updated=last_updated,
                    selector_type="CSS",
                    selector_path=""
                ))
            
            # Настройка тегов для цветового выделения
            self.tree.tag_configure('price_up', foreground='#e74c3c')  # Красный для роста
            self.tree.tag_configure('price_down', foreground='#2ecc71')  # Зеленый для снижения
            self.tree.tag_configure('price_same', foreground='#95a5a6')  # Серый для без изменений
            self.tree.tag_configure('target_reached', background='#d4edda')  # Зеленый фон для достижения цели
            
            # Обновление комбобокса категорий
            self.category_combo['values'] = self.get_categories()
            
            # Обновление статуса
            self.status_label.config(text=f"Загружено товаров: {len(products)}")
            
        except Exception as e:
            logging.error(f"Ошибка загрузки товаров: {e}")
            self.status_label.config(text=f"Ошибка загрузки: {e}")
    
    def search_products(self):
        """Поиск товаров"""
        search_text = self.search_var.get()
        category = self.category_var.get() if self.category_var.get() != "Все товары" else None
        self.load_products(category=category, search_text=search_text)
    
    def reset_filters(self):
        """Сброс фильтров"""
        self.search_var.set("")
        self.category_var.set("Все товары")
        self.load_products()
    
    def on_product_select(self, event):
        """Обработка выбора товара в таблице"""
        selection = self.tree.selection()
        if not selection:
            return
        
        item = self.tree.item(selection[0])
        product_id = item['values'][0]
        self.current_product_id = product_id
        
        self.load_product_details(product_id)
    
    def on_product_double_click(self, event):
        """Обработка двойного клика по товару"""
        self.open_in_browser()
    
    def show_context_menu(self, event):
        """Показ контекстного меню"""
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)
    
    def load_product_details(self, product_id):
        """Загрузка деталей товара"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT name, url, category, current_price, previous_price, 
                       currency, last_updated, selector_type, selector_path,
                       target_price, image_data, image_url
                FROM products 
                WHERE id = ?
            """, (product_id,))
            
            product = cursor.fetchone()
            if product:
                name, url, category, current_price, previous_price, currency, \
                last_updated, selector_type, selector_path, target_price, \
                image_data, image_url = product
                
                # Заполнение формы
                self.form_vars['name'].set(name)
                self.form_vars['url'].set(url)
                self.form_vars['category'].set(category)
                self.form_vars['selector'].set(selector_path)
                self.form_vars['target_price'].set(str(target_price) if target_price else "")
                
                # Отображение изображения
                self.display_product_image(image_data)
                
                # Отображение деталей
                details = f"""📦 **Информация о товаре**

**Название:** {name}
**Категория:** {category}
**URL:** {url}

💰 **Цены**
Текущая цена: {current_price:.2f} {currency if currency else '₽'}
Предыдущая цена: {previous_price:.2f} {currency if currency else '₽'}
Целевая цена: {target_price:.2f if target_price else 'Не установлена'} {currency if currency else '₽'}

📅 **Мониторинг**
Последнее обновление: {last_updated}
Селектор: {selector_path}
Тип селектора: {selector_type}

🔗 **Ссылки**
Изображение: {image_url if image_url else 'Не загружено'}"""
                
                self.details_text.config(state=tk.NORMAL)
                self.details_text.delete(1.0, tk.END)
                self.details_text.insert(1.0, details)
                self.details_text.config(state=tk.DISABLED)
                
                # Обновление информационной панели
                info_text = f"""Выбран товар: {name}
Категория: {category}
Последняя цена: {current_price:.2f} {currency if currency else '₽'}
Обновлено: {last_updated}"""
                
                self.info_text.config(state=tk.NORMAL)
                self.info_text.delete(1.0, tk.END)
                self.info_text.insert(1.0, info_text)
                self.info_text.config(state=tk.DISABLED)
                
        except Exception as e:
            logging.error(f"Ошибка загрузки деталей товара: {e}")
    
    def display_product_image(self, image_data):
        """Отображение изображения товара"""
        if image_data:
            try:
                image = Image.open(io.BytesIO(image_data))
                # Создаем thumbnail с сохранением пропорций
                image.thumbnail((300, 300), Image.Resampling.LANCZOS)
                
                # Создаем красивый frame для изображения
                bg = Image.new('RGB', (320, 320), color=self.colors['card'])
                bg.paste(image, ((320 - image.width) // 2, (320 - image.height) // 2))
                
                photo = ImageTk.PhotoImage(bg)
                self.image_label.config(image=photo, text="")
                self.image_label.image = photo
                
            except Exception as e:
                logging.error(f"Ошибка отображения изображения: {e}")
                self.image_label.config(
                    image="",
                    text="Ошибка загрузки\nизображения"
                )
        else:
            self.image_label.config(
                image="",
                text="Изображение не загружено\n\nПеретащите файл сюда"
            )
    
    def load_image_from_file(self):
        """Загрузка изображения из файла"""
        if not self.current_product_id:
            messagebox.showwarning("Внимание", "Сначала выберите товар")
            return
        
        file_path = filedialog.askopenfilename(
            title="Выберите изображение товара",
            filetypes=[
                ("Изображения", "*.jpg *.jpeg *.png *.gif *.bmp *.webp"),
                ("Все файлы", "*.*")
            ]
        )
        
        if file_path:
            try:
                # Чтение и оптимизация изображения
                with Image.open(file_path) as img:
                    # Конвертируем в RGB если нужно
                    if img.mode in ('RGBA', 'LA'):
                        background = Image.new('RGB', img.size, self.colors['card'])
                        background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                        img = background
                    
                    # Сохраняем в буфер
                    buffer = io.BytesIO()
                    img.save(buffer, format='JPEG', quality=85, optimize=True)
                    image_data = buffer.getvalue()
                
                # Сохранение в БД
                cursor = self.conn.cursor()
                cursor.execute(
                    "UPDATE products SET image_data = ?, image_url = ? WHERE id = ?",
                    (image_data, f"file://{file_path}", self.current_product_id)
                )
                self.conn.commit()
                
                # Отображение
                self.display_product_image(image_data)
                self.status_label.config(text="Изображение загружено")
                
            except Exception as e:
                logging.error(f"Ошибка загрузки изображения: {e}")
                messagebox.showerror("Ошибка", f"Не удалось загрузить изображение:\n{e}")
    
    def load_image_from_url(self):
        """Загрузка изображения по URL"""
        if not self.current_product_id:
            messagebox.showwarning("Внимание", "Сначала выберите товар")
            return
        
        # Диалог для ввода URL
        dialog = tk.Toplevel(self.root)
        dialog.title("Загрузка изображения по URL")
        dialog.geometry("500x200")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Введите URL изображения:", font=('Segoe UI', 11)).pack(pady=10)
        
        url_var = tk.StringVar()
        url_entry = ttk.Entry(dialog, textvariable=url_var, width=50, font=('Segoe UI', 10))
        url_entry.pack(pady=10, padx=20, fill=tk.X)
        url_entry.focus()
        
        def download():
            url = url_var.get().strip()
            if not url:
                messagebox.showwarning("Внимание", "Введите URL")
                return
            
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'image/webp,image/*,*/*;q=0.8',
                    'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
                }
                
                response = requests.get(url, headers=headers, timeout=15, stream=True)
                response.raise_for_status()
                
                # Проверка типа контента
                content_type = response.headers.get('content-type', '')
                if not content_type.startswith('image/'):
                    messagebox.showwarning("Внимание", "URL не ведет к изображению")
                    return
                
                # Загрузка изображения
                image_data = response.content
                
                if len(image_data) > 10 * 1024 * 1024:  # 10MB limit
                    messagebox.showwarning("Внимание", "Изображение слишком большое (макс. 10MB)")
                    return
                
                # Оптимизация изображения
                image = Image.open(io.BytesIO(image_data))
                if image.mode in ('RGBA', 'LA'):
                    background = Image.new('RGB', image.size, self.colors['card'])
                    background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
                    image = background
                
                buffer = io.BytesIO()
                image.save(buffer, format='JPEG', quality=85, optimize=True)
                image_data = buffer.getvalue()
                
                # Сохранение в БД
                cursor = self.conn.cursor()
                cursor.execute(
                    "UPDATE products SET image_data = ?, image_url = ? WHERE id = ?",
                    (image_data, url, self.current_product_id)
                )
                self.conn.commit()
                
                # Отображение
                self.display_product_image(image_data)
                self.status_label.config(text="Изображение загружено по URL")
                dialog.destroy()
                
            except Exception as e:
                logging.error(f"Ошибка загрузки изображения по URL: {e}")
                messagebox.showerror("Ошибка", f"Не удалось загрузить изображение:\n{e}")
        
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)
        
        ttk.Button(button_frame, text="Загрузить", 
                  command=download, style='Success.TButton').pack(side=tk.LEFT, padx=10)
        
        ttk.Button(button_frame, text="Отмена", 
                  command=dialog.destroy).pack(side=tk.LEFT, padx=10)
    
    def delete_image(self):
        """Удаление изображения товара"""
        if not self.current_product_id:
            return
        
        if messagebox.askyesno("Подтверждение", "Удалить изображение товара?"):
            try:
                cursor = self.conn.cursor()
                cursor.execute(
                    "UPDATE products SET image_data = NULL, image_url = NULL WHERE id = ?",
                    (self.current_product_id,)
                )
                self.conn.commit()
                
                self.display_product_image(None)
                self.status_label.config(text="Изображение удалено")
                
            except Exception as e:
                logging.error(f"Ошибка удаления изображения: {e}")
                messagebox.showerror("Ошибка", f"Не удалось удалить изображение:\n{e}")
    
    def add_product(self):
        """Добавление нового товара"""
        name = self.form_vars['name'].get().strip()
        url = self.form_vars['url'].get().strip()
        category = self.form_vars['category'].get().strip()
        selector = self.form_vars['selector'].get().strip()
        target_price_str = self.form_vars['target_price'].get().strip()
        
        # Валидация
        if not name:
            messagebox.showwarning("Внимание", "Введите название товара")
            self.form_vars['name'].focus_set()
            return
        
        if not url:
            messagebox.showwarning("Внимание", "Введите URL товара")
            self.form_vars['url'].focus_set()
            return
        
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        if not selector:
            selector = ".price, .product-price, [itemprop='price']"
        
        try:
            target_price = float(target_price_str) if target_price_str else None
        except ValueError:
            messagebox.showwarning("Внимание", "Некорректная целевая цена")
            self.form_vars['target_price'].focus_set()
            return
        
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO products 
                (name, url, category, selector_path, target_price, last_updated) 
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                name, 
                url, 
                category if category else "Без категории",
                selector,
                target_price,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ))
            
            self.conn.commit()
            
            # Автоматическое обновление цены
            product_id = cursor.lastrowid
            self.current_product_id = product_id
            self.update_product_price(product_id)
            
            # Обновление интерфейса
            self.load_products()
            self.clear_form()
            
            self.status_label.config(text=f"Товар '{name}' добавлен и обновлен")
            
        except Exception as e:
            logging.error(f"Ошибка добавления товара: {e}")
            messagebox.showerror("Ошибка", f"Не удалось добавить товар:\n{e}")
    
    def update_product(self):
        """Обновление информации о товаре"""
        if not self.current_product_id:
            messagebox.showwarning("Внимание", "Сначала выберите товар")
            return
        
        name = self.form_vars['name'].get().strip()
        url = self.form_vars['url'].get().strip()
        category = self.form_vars['category'].get().strip()
        selector = self.form_vars['selector'].get().strip()
        target_price_str = self.form_vars['target_price'].get().strip()
        
        # Валидация
        if not name:
            messagebox.showwarning("Внимание", "Введите название товара")
            self.form_vars['name'].focus_set()
            return
        
        if not url:
            messagebox.showwarning("Внимание", "Введите URL товара")
            self.form_vars['url'].focus_set()
            return
        
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        try:
            target_price = float(target_price_str) if target_price_str else None
        except ValueError:
            messagebox.showwarning("Внимание", "Некорректная целевая цена")
            self.form_vars['target_price'].focus_set()
            return
        
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                UPDATE products 
                SET name = ?, url = ?, category = ?, selector_path = ?, target_price = ?
                WHERE id = ?
            """, (
                name,
                url,
                category if category else "Без категории",
                selector,
                target_price,
                self.current_product_id
            ))
            
            self.conn.commit()
            self.load_products()
            self.load_product_details(self.current_product_id)
            
            self.status_label.config(text=f"Товар '{name}' обновлен")
            
        except Exception as e:
            logging.error(f"Ошибка обновления товара: {e}")
            messagebox.showerror("Ошибка", f"Не удалось обновить товар:\n{e}")
    
    def save_product_changes(self):
        """Сохранение изменений в деталях товара"""
        # Реализация сохранения изменений из детальной панели
        messagebox.showinfo("Информация", "Функция сохранения изменений будет реализована в следующей версии")
    
    def reset_details(self):
        """Сброс деталей товара"""
        self.details_text.config(state=tk.NORMAL)
        self.details_text.delete(1.0, tk.END)
        self.details_text.config(state=tk.DISABLED)
        self.image_label.config(image="", text="Изображение не загружено")
    
    def clear_form(self):
        """Очистка формы добавления товара"""
        for var in self.form_vars.values():
            var.set("")
        
        self.form_vars['selector'].set(".price, .product-price, [itemprop='price']")
        self.current_product_id = None
    
    def delete_product(self):
        """Удаление выбранного товара"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("Внимание", "Выберите товар для удаления")
            return
        
        item = self.tree.item(selection[0])
        product_id = item['values'][0]
        product_name = item['values'][1]
        
        if messagebox.askyesno("Подтверждение", 
                              f"Удалить товар '{product_name}'?\nВся история цен будет также удалена."):
            try:
                cursor = self.conn.cursor()
                cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
                self.conn.commit()
                
                self.load_products()
                self.clear_form()
                self.status_label.config(text=f"Товар '{product_name}' удален")
                
            except Exception as e:
                logging.error(f"Ошибка удаления товара: {e}")
                messagebox.showerror("Ошибка", f"Не удалось удалить товар:\n{e}")
    
    def copy_url(self):
        """Копирование URL товара в буфер обмена"""
        selection = self.tree.selection()
        if not selection:
            return
        
        item = self.tree.item(selection[0])
        product_id = item['values'][0]
        
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT url FROM products WHERE id = ?", (product_id,))
            result = cursor.fetchone()
            if result:
                url = result[0]
                
                self.root.clipboard_clear()
                self.root.clipboard_append(url)
                
                self.status_label.config(text="URL скопирован в буфер обмена")
            
        except Exception as e:
            logging.error(f"Ошибка копирования URL: {e}")
    
    def open_in_browser(self):
        """Открытие URL товара в браузере"""
        selection = self.tree.selection()
        if not selection:
            return
        
        item = self.tree.item(selection[0])
        product_id = item['values'][0]
        
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT url FROM products WHERE id = ?", (product_id,))
            result = cursor.fetchone()
            if result:
                url = result[0]
                
                webbrowser.open(url)
                self.status_label.config(text="Открываю в браузере...")
            
        except Exception as e:
            logging.error(f"Ошибка открытия в браузере: {e}")
            messagebox.showerror("Ошибка", f"Не удалось открыть в браузере:\n{e}")
    
    def extract_price(self, html_content, selector):
        """Извлечение цены из HTML с использованием нескольких методов"""
        if not html_content or not selector:
            return None
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Метод 1: CSS селекторы
            selectors_to_try = selector.split(',')
            selectors_to_try.extend([
                '[data-price]',
                '[itemprop="price"]',
                '.price',
                '.product-price',
                '.price-value',
                '.current-price',
                '.js-price',
                '.c-price',
                '.product-price__value'
            ])
            
            for sel in selectors_to_try:
                sel = sel.strip()
                if not sel:
                    continue
                
                try:
                    elements = soup.select(sel)
                    if elements:
                        price_text = elements[0].get_text().strip()
                        price = self.parse_price_text(price_text)
                        if price:
                            return price
                except Exception:
                    continue
            
            # Метод 2: Поиск по регулярным выражениям
            price_patterns = [
                r'(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)',  # 1,234.56 или 1.234,56
                r'(\d+(?:[.,]\d+)?)',  # 1234.56 или 1234,56
                r'price["\']?\s*[:=]\s*["\']?([\d.,]+)',  # price: "1234.56"
                r'data-price=["\']?([\d.,]+)'  # data-price="1234.56"
            ]
            
            for pattern in price_patterns:
                matches = re.findall(pattern, html_content, re.IGNORECASE)
                for match in matches:
                    price = self.parse_price_text(match)
                    if price:
                        return price
            
            # Метод 3: Поиск по структурированным данным
            script_tags = soup.find_all('script', type='application/ld+json')
            for script in script_tags:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, dict):
                        price = self.extract_from_structured_data(data)
                        if price:
                            return price
                except:
                    continue
            
            return None
            
        except Exception as e:
            logging.error(f"Ошибка извлечения цены: {e}")
            return None
    
    def parse_price_text(self, text):
        """Парсинг текста с ценой"""
        try:
            # Удаляем все символы кроме цифр, точек и запятых
            cleaned = re.sub(r'[^\d.,]', '', text)
            
            if not cleaned:
                return None
            
            # Определяем разделитель тысяч и десятичных
            last_comma = cleaned.rfind(',')
            last_dot = cleaned.rfind('.')
            
            if last_comma > last_dot:
                # Запятая - десятичный разделитель (1.234,56)
                cleaned = cleaned.replace('.', '').replace(',', '.')
            else:
                # Точка - десятичный разделитель (1,234.56)
                cleaned = cleaned.replace(',', '')
            
            return float(cleaned)
            
        except Exception as e:
            logging.error(f"Ошибка парсинга цены '{text}': {e}")
            return None
    
    def extract_from_structured_data(self, data):
        """Извлечение цены из структурированных данных"""
        try:
            # Проверяем разные форматы структурированных данных
            if 'price' in data:
                price = data['price']
                if isinstance(price, (int, float)):
                    return float(price)
                elif isinstance(price, str):
                    return self.parse_price_text(price)
            
            if 'offers' in data:
                offers = data['offers']
                if isinstance(offers, dict) and 'price' in offers:
                    price = offers['price']
                    if isinstance(price, (int, float)):
                        return float(price)
                    elif isinstance(price, str):
                        return self.parse_price_text(price)
                elif isinstance(offers, list) and offers:
                    offer = offers[0]
                    if 'price' in offer:
                        price = offer['price']
                        if isinstance(price, (int, float)):
                            return float(price)
                        elif isinstance(price, str):
                            return self.parse_price_text(price)
            
            return None
            
        except Exception as e:
            logging.error(f"Ошибка извлечения из структурированных данных: {e}")
            return None
    
    def update_product_price(self, product_id, force=False):
        """Обновление цены для конкретного товара"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT url, selector_path, current_price, name 
                FROM products 
                WHERE id = ? AND is_active = 1
            """, (product_id,))
            
            product = cursor.fetchone()
            if not product:
                return False
            
            url, selector, current_price, name = product
            
            # Проверяем, не обновляли ли мы недавно
            if not force:
                cursor.execute("SELECT last_updated FROM products WHERE id = ?", (product_id,))
                last_updated_result = cursor.fetchone()
                if last_updated_result and last_updated_result[0]:
                    last_updated_str = last_updated_result[0]
                    try:
                        last_updated = datetime.strptime(last_updated_str, "%Y-%m-%d %H:%M:%S")
                        if datetime.now() - last_updated < timedelta(minutes=5):
                            logging.info(f"Пропускаем {name} - недавно обновляли")
                            return True
                    except ValueError:
                        pass  # Если формат даты некорректный, продолжаем обновление
            
            logging.info(f"Обновляю цену для: {name}")
            self.status_label.config(text=f"Обновляю: {name}")
            
            try:
                # Настраиваем заголовки для обхода защиты
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Sec-Fetch-User': '?1',
                    'Cache-Control': 'max-age=0',
                }
                
                # Настраиваем сессию
                session = requests.Session()
                session.headers.update(headers)
                
                # Добавляем задержку между запросами
                time.sleep(1)
                
                response = session.get(url, timeout=20, verify=False)
                response.raise_for_status()
                
                # Проверяем кодировку
                if response.encoding is None:
                    response.encoding = 'utf-8'
                
                new_price = self.extract_price(response.text, selector)
                
                if new_price:
                    logging.info(f"Найдена цена для {name}: {new_price}")
                    
                    # Обновляем цены в БД
                    cursor.execute("""
                        UPDATE products 
                        SET previous_price = ?, 
                            current_price = ?, 
                            last_updated = ?,
                            min_price = CASE 
                                WHEN min_price IS NULL OR ? < min_price THEN ? 
                                ELSE min_price 
                            END,
                            max_price = CASE 
                                WHEN max_price IS NULL OR ? > max_price THEN ? 
                                ELSE max_price 
                            END
                        WHERE id = ?
                    """, (
                        current_price,
                        new_price,
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        new_price, new_price,
                        new_price, new_price,
                        product_id
                    ))
                    
                    # Сохраняем в историю
                    cursor.execute("""
                        INSERT OR REPLACE INTO price_history (product_id, price, date)
                        VALUES (?, ?, ?)
                    """, (
                        product_id,
                        new_price,
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    ))
                    
                    self.conn.commit()
                    
                    # Проверяем достижение целевой цены
                    cursor.execute("SELECT target_price FROM products WHERE id = ?", (product_id,))
                    target_price_row = cursor.fetchone()
                    
                    if (target_price_row and target_price_row[0] and 
                        new_price <= target_price_row[0] and 
                        (not current_price or new_price < current_price)):
                        self.show_notification(
                            f"🎯 Целевая цена достигнута!",
                            f"{name}\nНовая цена: {new_price:.2f} ₽\nЦелевая цена: {target_price_row[0]:.2f} ₽"
                        )
                    
                    return True
                else:
                    logging.warning(f"Не удалось найти цену для {name}")
                    return False
                
            except requests.exceptions.RequestException as e:
                logging.error(f"Ошибка сети для {name}: {e}")
                return False
            except Exception as e:
                logging.error(f"Ошибка обновления цены для {name}: {e}")
                return False
                
        except Exception as e:
            logging.error(f"Критическая ошибка при обновлении товара {product_id}: {e}")
            return False
    
    def update_selected_price(self):
        """Обновление цены выбранного товара"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("Внимание", "Выберите товар для обновления")
            return
        
        item = self.tree.item(selection[0])
        product_id = item['values'][0]
        product_name = item['values'][1]
        
        self.status_label.config(text=f"Обновляю {product_name}...")
        self.root.update()
        
        if self.update_product_price(product_id, force=True):
            self.load_products()
            self.load_product_details(product_id)
            self.status_label.config(text=f"Цена для {product_name} обновлена")
        else:
            self.status_label.config(text=f"Не удалось обновить {product_name}")
    
    def update_all_prices(self):
        """Обновление цен для всех активных товаров"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT id, name FROM products WHERE is_active = 1")
            products = cursor.fetchall()
            
            if not products:
                messagebox.showinfo("Информация", "Нет активных товаров для обновления")
                return
            
            total = len(products)
            
            # Окно прогресса
            progress_window = tk.Toplevel(self.root)
            progress_window.title("Обновление цен")
            progress_window.geometry("400x150")
            progress_window.transient(self.root)
            progress_window.grab_set()
            
            # Центрирование
            progress_window.update_idletasks()
            width = progress_window.winfo_width()
            height = progress_window.winfo_height()
            x = (progress_window.winfo_screenwidth() // 2) - (width // 2)
            y = (progress_window.winfo_screenheight() // 2) - (height // 2)
            progress_window.geometry(f'{width}x{height}+{x}+{y}')
            
            ttk.Label(progress_window, 
                     text=f"Обновление {total} товаров...",
                     font=('Segoe UI', 12)).pack(pady=20)
            
            progress_var = tk.DoubleVar()
            progress_bar = ttk.Progressbar(progress_window, 
                                          variable=progress_var,
                                          maximum=total,
                                          length=300)
            progress_bar.pack(pady=10)
            
            status_label = ttk.Label(progress_window, text="Подготовка...")
            status_label.pack()
            
            def update_process():
                success_count = 0
                
                for i, (product_id, name) in enumerate(products, 1):
                    if self.stop_update:
                        break
                    
                    status_label.config(text=f"Обновление: {name}")
                    progress_var.set(i)
                    progress_window.update()
                    
                    if self.update_product_price(product_id):
                        success_count += 1
                    
                    # Задержка между запросами
                    time.sleep(2)
                
                progress_window.destroy()
                
                # Обновляем интерфейс
                self.load_products()
                self.status_label.config(text=f"Обновлено {success_count} из {total} товаров")
                
                # Показываем статистику
                if success_count < total:
                    messagebox.showinfo("Результат", 
                                       f"✅ Успешно обновлено: {success_count}\n"
                                       f"❌ Не удалось обновить: {total - success_count}")
                else:
                    messagebox.showinfo("Успех", f"Все {total} товаров успешно обновлены!")
                
                # Обновляем графики
                self.update_charts()
            
            # Запуск в отдельном потоке
            thread = threading.Thread(target=update_process, daemon=True)
            thread.start()
            
        except Exception as e:
            logging.error(f"Ошибка массового обновления: {e}")
            messagebox.showerror("Ошибка", f"Не удалось обновить цены:\n{e}")
    
    def toggle_auto_update(self):
        """Включение/выключение автоматического обновления"""
        self.config['auto_update'] = self.auto_update_var.get()
        self.save_config()
        
        if self.config['auto_update']:
            self.start_auto_update()
        else:
            self.stop_auto_update()
    
    def start_auto_update(self):
        """Запуск автоматического обновления"""
        if self.update_thread and self.update_thread.is_alive():
            return
        
        self.stop_update = False
        
        def auto_update_loop():
            while self.config.get('auto_update', False) and not self.stop_update:
                try:
                    interval = self.config.get('update_interval', 300)
                    logging.info(f"Автообновление через {interval} секунд")
                    
                    # Ждем указанный интервал
                    for _ in range(interval):
                        if not self.config.get('auto_update', False) or self.stop_update:
                            return
                        time.sleep(1)
                    
                    # Обновляем все цены
                    if self.config.get('auto_update', False) and not self.stop_update:
                        logging.info("Запуск автообновления цен")
                        self.root.after(0, self.update_all_prices)
                        
                except Exception as e:
                    logging.error(f"Ошибка в автообновлении: {e}")
                    time.sleep(60)
        
        self.update_thread = threading.Thread(target=auto_update_loop, daemon=True)
        self.update_thread.start()
        
        self.status_label.config(text="Автообновление запущено")
    
    def stop_auto_update(self):
        """Остановка автоматического обновления"""
        self.stop_update = True
        if self.update_thread and self.update_thread.is_alive():
            self.update_thread.join(timeout=5)
        self.stop_update = False
        self.status_label.config(text="Автообновление остановлено")
    
    def show_price_history(self):
        """Показать историю цен для выбранного товара"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("Внимание", "Выберите товар")
            return
        
        item = self.tree.item(selection[0])
        product_id = item['values'][0]
        product_name = item['values'][1]
        
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT date, price 
                FROM price_history 
                WHERE product_id = ? 
                ORDER BY date DESC
                LIMIT 100
            """, (product_id,))
            
            history = cursor.fetchall()
            
            if not history:
                messagebox.showinfo("История", f"Для товара '{product_name}' нет истории цен")
                return
            
            # Создаем окно с графиком
            history_window = tk.Toplevel(self.root)
            history_window.title(f"История цен: {product_name}")
            history_window.geometry("800x600")
            
            # Центрирование
            history_window.update_idletasks()
            width = history_window.winfo_width()
            height = history_window.winfo_height()
            x = (history_window.winfo_screenwidth() // 2) - (width // 2)
            y = (history_window.winfo_screenheight() // 2) - (height // 2)
            history_window.geometry(f'{width}x{height}+{x}+{y}')
            
            # Подготавливаем данные
            dates = []
            prices = []
            
            for date_str, price in reversed(history):  # Разворачиваем для правильного порядка
                dates.append(datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S"))
                prices.append(price)
            
            # Создаем график
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))
            
            # График цен
            ax1.plot(dates, prices, marker='o', linestyle='-', color=self.colors['secondary'], linewidth=2)
            ax1.set_title(f'История цен: {product_name}', fontsize=14, fontweight='bold')
            ax1.set_xlabel('Дата', fontsize=12)
            ax1.set_ylabel('Цена (₽)', fontsize=12)
            ax1.grid(True, alpha=0.3)
            ax1.tick_params(axis='x', rotation=45)
            
            # Гистограмма изменений
            if len(prices) > 1:
                changes = [prices[i] - prices[i-1] for i in range(1, len(prices))]
                colors = ['green' if c < 0 else 'red' for c in changes]
                ax2.bar(range(len(changes)), changes, color=colors, alpha=0.7)
                ax2.set_title('Изменения цен', fontsize=14, fontweight='bold')
                ax2.set_xlabel('Период', fontsize=12)
                ax2.set_ylabel('Изменение (₽)', fontsize=12)
                ax2.grid(True, alpha=0.3)
            
            plt.tight_layout()
            
            # Встраиваем график в Tkinter
            canvas = FigureCanvasTkAgg(fig, master=history_window)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            # Таблица с данными
            table_frame = ttk.Frame(history_window)
            table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
            
            columns = ("Дата", "Цена (₽)", "Изменение")
            history_tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=8)
            
            for col in columns:
                history_tree.heading(col, text=col)
                history_tree.column(col, width=200)
            
            # Заполняем таблицу
            prev_price = None
            for date_str, price in history:
                change = ""
                if prev_price is not None:
                    diff = price - prev_price
                    if diff > 0:
                        change = f"▲ {diff:.2f}"
                    elif diff < 0:
                        change = f"▼ {abs(diff):.2f}"
                    else:
                        change = "—"
                prev_price = price
                
                history_tree.insert("", tk.END, values=(date_str, f"{price:.2f}", change))
            
            scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=history_tree.yview)
            history_tree.configure(yscrollcommand=scrollbar.set)
            
            history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            # Кнопка экспорта
            ttk.Button(history_window, text="📥 Экспорт в CSV", 
                      command=lambda: self.export_history_to_csv(product_id, product_name),
                      style='Success.TButton').pack(pady=10)
            
        except Exception as e:
            logging.error(f"Ошибка показа истории: {e}")
            messagebox.showerror("Ошибка", f"Не удалось загрузить историю:\n{e}")
    
    def export_history_to_csv(self, product_id, product_name):
        """Экспорт истории цен в CSV"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT date, price 
                FROM price_history 
                WHERE product_id = ? 
                ORDER BY date
            """, (product_id,))
            
            history = cursor.fetchall()
            
            if not history:
                messagebox.showwarning("Экспорт", "Нет данных для экспорта")
                return
            
            # Запрос имени файла
            default_name = f"history_{product_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            file_path = filedialog.asksaveasfilename(
                title="Экспорт истории в CSV",
                defaultextension=".csv",
                initialfile=default_name,
                filetypes=[("CSV файлы", "*.csv"), ("Все файлы", "*.*")]
            )
            
            if file_path:
                with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['Дата', 'Цена (₽)', 'Изменение'])
                    
                    prev_price = None
                    for date_str, price in history:
                        change = ""
                        if prev_price is not None:
                            diff = price - prev_price
                            if diff > 0:
                                change = f"+{diff:.2f}"
                            elif diff < 0:
                                change = f"{diff:.2f}"
                        prev_price = price
                        
                        writer.writerow([date_str, f"{price:.2f}", change])
                
                self.status_label.config(text=f"История экспортирована в {os.path.basename(file_path)}")
                messagebox.showinfo("Успех", f"История успешно экспортирована в:\n{file_path}")
                
        except Exception as e:
            logging.error(f"Ошибка экспорта истории: {e}")
            messagebox.showerror("Ошибка", f"Не удалось экспортировать историю:\n{e}")
    
    def update_charts(self):
        """Обновление графиков"""
        try:
            # Очищаем контейнер
            for widget in self.charts_container.winfo_children():
                widget.destroy()
            
            # Создаем графики
            self.create_price_distribution_chart()
            self.create_price_changes_chart()
            self.create_category_stats_chart()
            
        except Exception as e:
            logging.error(f"Ошибка обновления графиков: {e}")
    
    def create_price_distribution_chart(self):
        """Создание графика распределения цен"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT current_price 
                FROM products 
                WHERE current_price IS NOT NULL AND is_active = 1
            """)
            
            prices = [row[0] for row in cursor.fetchall()]
            
            if not prices:
                ttk.Label(self.charts_container, 
                         text="Нет данных для построения графиков",
                         font=('Segoe UI', 12)).pack(pady=50)
                return
            
            fig, axes = plt.subplots(1, 3, figsize=(15, 5))
            
            # Гистограмма распределения цен
            axes[0].hist(prices, bins=20, edgecolor='black', alpha=0.7, color=self.colors['secondary'])
            axes[0].set_title('Распределение цен', fontsize=12, fontweight='bold')
            axes[0].set_xlabel('Цена (₽)', fontsize=10)
            axes[0].set_ylabel('Количество товаров', fontsize=10)
            axes[0].grid(True, alpha=0.3)
            
            # Box plot
            axes[1].boxplot(prices, vert=True, patch_artist=True,
                           boxprops=dict(facecolor=self.colors['warning']))
            axes[1].set_title('Статистика цен', fontsize=12, fontweight='bold')
            axes[1].set_ylabel('Цена (₽)', fontsize=10)
            axes[1].grid(True, alpha=0.3)
            
            # Топ 10 самых дорогих товаров
            cursor.execute("""
                SELECT name, current_price 
                FROM products 
                WHERE current_price IS NOT NULL AND is_active = 1
                ORDER BY current_price DESC 
                LIMIT 10
            """)
            
            top_products = cursor.fetchall()
            names = [p[0][:20] + '...' if len(p[0]) > 20 else p[0] for p in top_products]
            top_prices = [p[1] for p in top_products]
            
            y_pos = range(len(names))
            axes[2].barh(y_pos, top_prices, color=self.colors['success'], alpha=0.7)
            axes[2].set_yticks(y_pos)
            axes[2].set_yticklabels(names)
            axes[2].set_title('Топ 10 самых дорогих товаров', fontsize=12, fontweight='bold')
            axes[2].set_xlabel('Цена (₽)', fontsize=10)
            axes[2].grid(True, alpha=0.3)
            
            plt.tight_layout()
            
            # Встраиваем график
            canvas = FigureCanvasTkAgg(fig, master=self.charts_container)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
        except Exception as e:
            logging.error(f"Ошибка создания графиков: {e}")
    
    def create_price_changes_chart(self):
        """Создание графика изменений цен"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT p.name, p.current_price, p.previous_price
                FROM products p
                WHERE p.current_price IS NOT NULL 
                  AND p.previous_price IS NOT NULL
                  AND p.is_active = 1
                LIMIT 20
            """)
            
            products = cursor.fetchall()
            
            if not products:
                return
            
            fig, ax = plt.subplots(figsize=(12, 6))
            
            names = [p[0][:15] + '...' if len(p[0]) > 15 else p[0] for p in products]
            current_prices = [p[1] for p in products]
            previous_prices = [p[2] for p in products]
            
            x = range(len(names))
            width = 0.35
            
            ax.bar([i - width/2 for i in x], previous_prices, width, 
                  label='Предыдущая цена', color=self.colors['warning'], alpha=0.7)
            ax.bar([i + width/2 for i in x], current_prices, width, 
                  label='Текущая цена', color=self.colors['success'], alpha=0.7)
            
            ax.set_xlabel('Товары', fontsize=12)
            ax.set_ylabel('Цена (₽)', fontsize=12)
            ax.set_title('Сравнение текущих и предыдущих цен', fontsize=14, fontweight='bold')
            ax.set_xticks(x)
            ax.set_xticklabels(names, rotation=45, ha='right')
            ax.legend()
            ax.grid(True, alpha=0.3)
            
            plt.tight_layout()
            
            # Встраиваем график
            canvas = FigureCanvasTkAgg(fig, master=self.charts_container)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
        except Exception as e:
            logging.error(f"Ошибка создания графика изменений: {e}")
    
    def create_category_stats_chart(self):
        """Создание статистики по категориям"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT category, 
                       COUNT(*) as count,
                       AVG(current_price) as avg_price,
                       MIN(current_price) as min_price,
                       MAX(current_price) as max_price
                FROM products 
                WHERE category IS NOT NULL 
                  AND category != '' 
                  AND current_price IS NOT NULL
                  AND is_active = 1
                GROUP BY category
                ORDER BY count DESC
                LIMIT 10
            """)
            
            stats = cursor.fetchall()
            
            if not stats:
                return
            
            categories = [s[0][:15] + '...' if len(s[0]) > 15 else s[0] for s in stats]
            counts = [s[1] for s in stats]
            avg_prices = [s[2] for s in stats]
            
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
            
            # Количество товаров по категориям
            colors = plt.cm.Set3(np.linspace(0, 1, len(categories)))
            wedges, texts, autotexts = ax1.pie(counts, labels=categories, colors=colors,
                                              autopct='%1.1f%%', startangle=90)
            ax1.set_title('Распределение товаров по категориям', fontsize=14, fontweight='bold')
            
            # Средние цены по категориям
            y_pos = range(len(categories))
            ax2.barh(y_pos, avg_prices, color=self.colors['secondary'], alpha=0.7)
            ax2.set_yticks(y_pos)
            ax2.set_yticklabels(categories)
            ax2.set_xlabel('Средняя цена (₽)', fontsize=12)
            ax2.set_title('Средние цены по категориям', fontsize=14, fontweight='bold')
            ax2.grid(True, alpha=0.3)
            
            plt.tight_layout()
            
            # Встраиваем график
            canvas = FigureCanvasTkAgg(fig, master=self.charts_container)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
        except Exception as e:
            logging.error(f"Ошибка создания статистики категорий: {e}")
    
    def show_statistics(self):
        """Показать статистику"""
        try:
            cursor = self.conn.cursor()
            
            # Общая статистика
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN current_price IS NOT NULL THEN 1 END) as with_price,
                    COUNT(CASE WHEN current_price IS NULL THEN 1 END) as without_price,
                    AVG(current_price) as avg_price,
                    MIN(current_price) as min_price,
                    MAX(current_price) as max_price
                FROM products 
                WHERE is_active = 1
            """)
            
            stats = cursor.fetchone()
            
            # Статистика изменений
            cursor.execute("""
                SELECT 
                    COUNT(CASE WHEN current_price > previous_price THEN 1 END) as increased,
                    COUNT(CASE WHEN current_price < previous_price THEN 1 END) as decreased,
                    COUNT(CASE WHEN current_price = previous_price THEN 1 END) as unchanged
                FROM products 
                WHERE current_price IS NOT NULL 
                  AND previous_price IS NOT NULL
                  AND is_active = 1
            """)
            
            changes = cursor.fetchone()
            
            # Создаем окно статистики
            stats_window = tk.Toplevel(self.root)
            stats_window.title("📊 Статистика")
            stats_window.geometry("600x500")
            
            # Центрирование
            stats_window.update_idletasks()
            width = stats_window.winfo_width()
            height = stats_window.winfo_height()
            x = (stats_window.winfo_screenwidth() // 2) - (width // 2)
            y = (stats_window.winfo_screenheight() // 2) - (height // 2)
            stats_window.geometry(f'{width}x{height}+{x}+{y}')
            
            # Заголовок
            ttk.Label(stats_window, 
                     text="📊 Статистика мониторинга",
                     font=('Segoe UI', 16, 'bold')).pack(pady=20)
            
            # Статистика в виде карточек
            stats_frame = ttk.Frame(stats_window)
            stats_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
            
            # Создаем карточки
            cards_data = [
                ("Всего товаров", f"{stats[0] if stats else 0}", "📦"),
                ("С ценами", f"{stats[1] if stats else 0}", "💰"),
                ("Без цен", f"{stats[2] if stats else 0}", "❓"),
                ("Средняя цена", f"{stats[3]:.2f} ₽" if stats and stats[3] else "—", "📊"),
                ("Минимальная", f"{stats[4]:.2f} ₽" if stats and stats[4] else "—", "📉"),
                ("Максимальная", f"{stats[5]:.2f} ₽" if stats and stats[5] else "—", "📈"),
            ]
            
            if changes:
                cards_data.extend([
                    ("Цены выросли", f"{changes[0]}", "📈"),
                    ("Цены упали", f"{changes[1]}", "📉"),
                    ("Без изменений", f"{changes[2]}", "➡"),
                ])
            
            # Создаем карточки в сетке 3x3
            for i, (title, value, icon) in enumerate(cards_data):
                row = i // 3
                col = i % 3
                
                card = ttk.Frame(stats_frame, style='Card.TFrame', padding=15)
                card.grid(row=row, column=col, padx=10, pady=10, sticky=tk.NSEW)
                
                ttk.Label(card, text=icon, font=('Segoe UI', 24)).pack()
                ttk.Label(card, text=title, font=('Segoe UI', 10)).pack()
                ttk.Label(card, text=value, font=('Segoe UI', 14, 'bold')).pack()
            
            # Настройка сетки
            for i in range(3):
                stats_frame.grid_columnconfigure(i, weight=1)
            
            # Кнопка закрытия
            ttk.Button(stats_window, text="Закрыть", 
                      command=stats_window.destroy,
                      style='Primary.TButton').pack(pady=20)
            
        except Exception as e:
            logging.error(f"Ошибка показа статистики: {e}")
            messagebox.showerror("Ошибка", f"Не удалось загрузить статистику:\n{e}")
    
    def show_settings(self):
        """Показать настройки"""
        settings_window = tk.Toplevel(self.root)
        settings_window.title("⚙ Настройки")
        settings_window.geometry("500x600")
        
        # Центрирование
        settings_window.update_idletasks()
        width = settings_window.winfo_width()
        height = settings_window.winfo_height()
        x = (settings_window.winfo_screenwidth() // 2) - (width // 2)
        y = (settings_window.winfo_screenheight() // 2) - (height // 2)
        settings_window.geometry(f'{width}x{height}+{x}+{y}')
        
        ttk.Label(settings_window, 
                 text="⚙ Настройки приложения",
                 font=('Segoe UI', 16, 'bold')).pack(pady=20)
        
        # Форма настроек
        form_frame = ttk.Frame(settings_window)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=10)
        
        settings_vars = {}
        
        # Интервал обновления
        ttk.Label(form_frame, text="Интервал автообновления (минут):").grid(row=0, column=0, sticky=tk.W, pady=10)
        interval_var = tk.StringVar(value=str(self.config.get('update_interval', 300) // 60))
        ttk.Entry(form_frame, textvariable=interval_var, width=10).grid(row=0, column=1, sticky=tk.W, pady=10)
        settings_vars['update_interval'] = interval_var
        
        # Валюта
        ttk.Label(form_frame, text="Валюта:").grid(row=1, column=0, sticky=tk.W, pady=10)
        currency_var = tk.StringVar(value=self.config.get('currency', 'RUB'))
        ttk.Combobox(form_frame, textvariable=currency_var, 
                    values=['RUB', 'USD', 'EUR', 'UAH', 'KZT'], 
                    width=10).grid(row=1, column=1, sticky=tk.W, pady=10)
        settings_vars['currency'] = currency_var
        
        # Уведомления
        notifications_var = tk.BooleanVar(value=self.config.get('notifications', True))
        ttk.Checkbutton(form_frame, text="Показывать уведомления", 
                       variable=notifications_var).grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=10)
        settings_vars['notifications'] = notifications_var
        
        # Тема
        ttk.Label(form_frame, text="Тема интерфейса:").grid(row=3, column=0, sticky=tk.W, pady=10)
        theme_var = tk.StringVar(value=self.config.get('theme', 'light'))
        ttk.Combobox(form_frame, textvariable=theme_var, 
                    values=['light', 'dark'], 
                    width=10).grid(row=3, column=1, sticky=tk.W, pady=10)
        settings_vars['theme'] = theme_var
        
        form_frame.columnconfigure(1, weight=1)
        
        def save_settings():
            """Сохранение настроек"""
            try:
                # Преобразуем интервал в секунды
                try:
                    minutes = int(interval_var.get())
                    self.config['update_interval'] = minutes * 60
                except ValueError:
                    messagebox.showwarning("Ошибка", "Некорректный интервал")
                    return
                
                self.config['currency'] = currency_var.get()
                self.config['notifications'] = notifications_var.get()
                self.config['theme'] = theme_var.get()
                
                self.save_config()
                settings_window.destroy()
                
                messagebox.showinfo("Сохранено", "Настройки успешно сохранены")
                
            except Exception as e:
                logging.error(f"Ошибка сохранения настроек: {e}")
                messagebox.showerror("Ошибка", f"Не удалось сохранить настройки:\n{e}")
        
        # Кнопки
        button_frame = ttk.Frame(settings_window)
        button_frame.pack(pady=20)
        
        ttk.Button(button_frame, text="Сохранить", 
                  command=save_settings, style='Success.TButton').pack(side=tk.LEFT, padx=10)
        
        ttk.Button(button_frame, text="Отмена", 
                  command=settings_window.destroy).pack(side=tk.LEFT, padx=10)
    
    def export_data(self):
        """Экспорт данных"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT name, category, url, current_price, previous_price, 
                       currency, last_updated, target_price
                FROM products 
                WHERE is_active = 1
                ORDER BY category, name
            """)
            
            products = cursor.fetchall()
            
            if not products:
                messagebox.showinfo("Экспорт", "Нет данных для экспорта")
                return
            
            # Запрос имени файла
            default_name = f"price_monitor_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            file_path = filedialog.asksaveasfilename(
                title="Экспорт данных",
                defaultextension=".csv",
                initialfile=default_name,
                filetypes=[
                    ("CSV файлы", "*.csv"),
                    ("Excel файлы", "*.xlsx"),
                    ("JSON файлы", "*.json"),
                    ("Все файлы", "*.*")
                ]
            )
            
            if not file_path:
                return
            
            ext = os.path.splitext(file_path)[1].lower()
            
            if ext == '.csv':
                # Экспорт в CSV
                with open(file_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['Название', 'Категория', 'URL', 'Текущая цена', 
                                   'Предыдущая цена', 'Валюта', 'Обновлено', 'Целевая цена'])
                    
                    for product in products:
                        writer.writerow(product)
                
                self.status_label.config(text=f"Данные экспортированы в CSV")
                
            elif ext == '.xlsx':
                # Экспорт в Excel (требуется pandas)
                try:
                    import pandas as pd
                    
                    df = pd.DataFrame(products, columns=['Название', 'Категория', 'URL', 'Текущая цена', 
                                                        'Предыдущая цена', 'Валюта', 'Обновлено', 'Целевая цена'])
                    df.to_excel(file_path, index=False)
                    
                    self.status_label.config(text=f"Данные экспортированы в Excel")
                    
                except ImportError:
                    messagebox.showerror("Ошибка", "Для экспорта в Excel установите pandas:\npip install pandas")
                    return
                    
            elif ext == '.json':
                # Экспорт в JSON
                data = []
                for product in products:
                    data.append({
                        'name': product[0],
                        'category': product[1],
                        'url': product[2],
                        'current_price': product[3],
                        'previous_price': product[4],
                        'currency': product[5],
                        'last_updated': product[6],
                        'target_price': product[7]
                    })
                
                with open(file_path, 'w', encoding='utf-8') as jsonfile:
                    json.dump(data, jsonfile, ensure_ascii=False, indent=2)
                
                self.status_label.config(text=f"Данные экспортированы в JSON")
            
            else:
                # По умолчанию CSV
                file_path += '.csv'
                with open(file_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['Название', 'Категория', 'URL', 'Текущая цена', 
                                   'Предыдущая цена', 'Валюта', 'Обновлено', 'Целевая цена'])
                    
                    for product in products:
                        writer.writerow(product)
                
                self.status_label.config(text=f"Данные экспортированы в {os.path.basename(file_path)}")
            
            messagebox.showinfo("Успех", f"Данные успешно экспортированы в:\n{file_path}")
            
        except Exception as e:
            logging.error(f"Ошибка экспорта данных: {e}")
            messagebox.showerror("Ошибка", f"Не удалось экспортировать данные:\n{e}")
    
    def show_notification(self, title, message):
        """Показ уведомления"""
        if not self.config.get('notifications', True):
            return
        
        try:
            # Создаем окно уведомления
            notification = tk.Toplevel(self.root)
            notification.title(title)
            notification.geometry("400x200")
            
            # Делаем окно поверх других
            notification.attributes('-topmost', True)
            
            # Центрирование
            notification.update_idletasks()
            width = notification.winfo_width()
            height = notification.winfo_height()
            x = (notification.winfo_screenwidth() // 2) - (width // 2)
            y = (notification.winfo_screenheight() // 2) - (height // 2)
            notification.geometry(f'{width}x{height}+{x}+{y}')
            
            # Содержимое уведомления
            ttk.Label(notification, text="🔔", font=('Segoe UI', 36)).pack(pady=10)
            ttk.Label(notification, text=title, font=('Segoe UI', 14, 'bold')).pack()
            
            message_label = ttk.Label(notification, text=message, font=('Segoe UI', 11))
            message_label.pack(pady=10, padx=20)
            
            # Кнопка закрытия
            ttk.Button(notification, text="OK", 
                      command=notification.destroy,
                      style='Success.TButton').pack(pady=10)
            
            # Автоматическое закрытие через 10 секунд
            self.root.after(10000, notification.destroy)
            
        except Exception as e:
            logging.error(f"Ошибка показа уведомления: {e}")
    
    def on_closing(self):
        """Действия при закрытии приложения"""
        # Останавливаем автообновление
        self.stop_auto_update()
        
        # Закрываем базу данных
        if self.conn:
            self.conn.close()
        
        # Закрываем приложение
        self.root.destroy()

def main():
    """Основная функция"""
    # Создаем главное окно
    root = tk.Tk()
    
    # Создаем приложение
    app = PriceMonitorApp(root)
    
    # Обработка закрытия окна
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    
    # Запуск главного цикла
    root.mainloop()

if __name__ == "__main__":
    main()