#!/usr/bin/env python3
"""
Instagram Post Planner - Windows GUI Application (Version 2)

Comprehensive GUI with all configuration parameters as user inputs.
NO hard-coded numeric thresholds - everything comes from GUI.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import queue
import os
import sys
from datetime import datetime
from config import PlanConfig, create_default_config
from planner import run_planner, run_planner_with_best_effort


class ScrollableFrame(ttk.Frame):
    """A scrollable frame for long forms"""
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        
        canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)


class PlannerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Instagram Post Planner - Comprehensive Configuration")
        self.root.geometry("900x700")
        self.root.resizable(True, True)
        
        self.config = create_default_config()
        
        self.excel_path = tk.StringVar()
        self.start_day = tk.StringVar(value="Pazartesi")
        self.num_days = tk.IntVar(value=7)
        
        self.use_yazlik_front = tk.BooleanVar(value=False)
        self.use_kislik_front = tk.BooleanVar(value=False)
        self.cekim_front_evet = tk.BooleanVar(value=False)
        self.cekim_front_na = tk.BooleanVar(value=False)
        self.one_atilma_allow_na = tk.BooleanVar(value=False)
        self.one_atilma_date = tk.StringVar(value="")
        self.one_atilma_days = tk.IntVar(value=0)
        self.min_stock_front = tk.IntVar(value=0)
        self.min_nos_front = tk.IntVar(value=0)
        self.min_dvm_front = tk.IntVar(value=0)
        
        self.front_size_y = {}
        self.front_size_z = {}
        for i in range(1, 9):
            self.front_size_y[i] = tk.IntVar(value=0)
            self.front_size_z[i] = tk.IntVar(value=0)
        
        self.use_yazlik_back = tk.BooleanVar(value=False)
        self.use_kislik_back = tk.BooleanVar(value=False)
        self.cekim_back_evet = tk.BooleanVar(value=False)
        self.cekim_back_na = tk.BooleanVar(value=False)
        self.min_stock_back = tk.IntVar(value=0)
        
        self.back_size_y = {}
        self.back_size_z = {}
        for i in range(1, 9):
            self.back_size_y[i] = tk.IntVar(value=0)
            self.back_size_z[i] = tk.IntVar(value=0)
        
        self.max_same_uruncinsi = tk.IntVar(value=0)
        self.min_distinct_uruncinsi = tk.IntVar(value=0)
        self.max_same_color = tk.IntVar(value=0)
        self.min_distinct_color = tk.IntVar(value=0)
        self.same_kisakod_gap = tk.IntVar(value=0)
        
        self.max_black_first_per_day = tk.IntVar(value=0)
        self.max_first_uses_per_kisakod = tk.IntVar(value=0)
        
        self.global_first_stock = tk.IntVar(value=0)
        self.global_total_stock = tk.IntVar(value=0)
        
        self.prioritize_by_newness = tk.BooleanVar(value=False)
        self.prioritize_by_stock = tk.BooleanVar(value=False)
        
        self.progress_queue = queue.Queue()
        self.decision_queue = queue.Queue()
        self.decision_result = None
        self.decision_event = threading.Event()
        self.is_running = False
        
        self.create_widgets()
        self.auto_load_settings()
        self.setup_auto_save_triggers()
        self.check_progress_queue()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        file_frame = ttk.LabelFrame(main_frame, text="Stok Dosyası", padding="5")
        file_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        file_frame.columnconfigure(0, weight=1)
        
        ttk.Entry(file_frame, textvariable=self.excel_path, state="readonly").grid(
            row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5)
        )
        ttk.Button(file_frame, text="Dosya Seç...", command=self.select_file).grid(
            row=0, column=1
        )
        
        notebook = ttk.Notebook(main_frame)
        notebook.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        
        self.create_plan_tab(notebook)
        self.create_first_tab(notebook)
        self.create_back_tab(notebook)
        self.create_advanced_tab(notebook)
        self.create_global_tab(notebook)
        self.create_preferred_tab(notebook)
        self.create_output_tab(notebook)
        
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, sticky=(tk.W, tk.E))
        
        self.run_button = ttk.Button(
            button_frame,
            text="Planı Oluştur",
            command=self.run_planner,
            style="Accent.TButton"
        )
        self.run_button.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            button_frame,
            text="Ayarları Sıfırla",
            command=self.reset_settings
        ).pack(side=tk.LEFT, padx=5)
    
    def create_plan_tab(self, notebook):
        """Plan Settings tab"""
        scroll_frame = ScrollableFrame(notebook)
        notebook.add(scroll_frame, text="Plan Ayarları")
        frame = scroll_frame.scrollable_frame
        
        row = 0
        
        ttk.Label(frame, text="Plan Başlangıç Günü:", font=("Arial", 10, "bold")).grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        ttk.Combobox(
            frame,
            textvariable=self.start_day,
            values=["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"],
            state="readonly",
            width=20
        ).grid(row=row, column=1, sticky=tk.W, pady=5, padx=5)
        row += 1
        
        ttk.Label(frame, text="Kaç Günlük Plan (1-7):", font=("Arial", 10, "bold")).grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        ttk.Spinbox(
            frame,
            from_=1,
            to=7,
            textvariable=self.num_days,
            width=20
        ).grid(row=row, column=1, sticky=tk.W, pady=5, padx=5)
        row += 1
        
        ttk.Separator(frame, orient="horizontal").grid(
            row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10
        )
        row += 1
        
        ttk.Label(frame, text="Post Saatleri (Sabit)", font=("Arial", 10, "bold")).grid(
            row=row, column=0, columnspan=2, sticky=tk.W, pady=5
        )
        row += 1
        
        ttk.Label(frame, text="Hafta içi: 12 post/gün", font=("Arial", 9)).grid(
            row=row, column=0, columnspan=2, sticky=tk.W, padx=20
        )
        row += 1
        
        ttk.Label(frame, text="09:00, 10:30, 11:30, 12:30, 13:30, 14:30,", font=("Arial", 8)).grid(
            row=row, column=0, columnspan=2, sticky=tk.W, padx=40
        )
        row += 1
        
        ttk.Label(frame, text="15:30, 16:30, 17:30, 19:30, 21:00, 22:30", font=("Arial", 8)).grid(
            row=row, column=0, columnspan=2, sticky=tk.W, padx=40
        )
        row += 1
        
        ttk.Label(frame, text="Haftasonu: 10 post/gün", font=("Arial", 9)).grid(
            row=row, column=0, columnspan=2, sticky=tk.W, padx=20, pady=(10, 0)
        )
        row += 1
        
        ttk.Label(frame, text="11:00, 12:00, 13:00, 14:00, 15:00,", font=("Arial", 8)).grid(
            row=row, column=0, columnspan=2, sticky=tk.W, padx=40
        )
        row += 1
        
        ttk.Label(frame, text="16:00, 17:00, 18:30, 19:30, 21:00", font=("Arial", 8)).grid(
            row=row, column=0, columnspan=2, sticky=tk.W, padx=40
        )
    
    def create_first_tab(self, notebook):
        """FIRST Product Criteria tab"""
        scroll_frame = ScrollableFrame(notebook)
        notebook.add(scroll_frame, text="FIRST Ürün Kriterleri")
        frame = scroll_frame.scrollable_frame
        
        row = 0
        
        ttk.Label(frame, text="Mevsim Filtresi:", font=("Arial", 10, "bold")).grid(
            row=row, column=0, columnspan=2, sticky=tk.W, pady=5
        )
        row += 1
        
        ttk.Checkbutton(frame, text="Yazlık", variable=self.use_yazlik_front).grid(
            row=row, column=0, sticky=tk.W, padx=20
        )
        ttk.Checkbutton(frame, text="Kışlık", variable=self.use_kislik_front).grid(
            row=row, column=1, sticky=tk.W
        )
        row += 1
        
        ttk.Separator(frame, orient="horizontal").grid(
            row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10
        )
        row += 1
        
        # Cekim
        ttk.Label(frame, text="Cekim Filtresi:", font=("Arial", 10, "bold")).grid(
            row=row, column=0, columnspan=2, sticky=tk.W, pady=5
        )
        row += 1
        
        ttk.Checkbutton(frame, text="EVET", variable=self.cekim_front_evet).grid(
            row=row, column=0, sticky=tk.W, padx=20
        )
        ttk.Checkbutton(frame, text="NA", variable=self.cekim_front_na).grid(
            row=row, column=1, sticky=tk.W
        )
        row += 1
        
        ttk.Separator(frame, orient="horizontal").grid(
            row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10
        )
        row += 1
        
        # One Atilma Tarihi
        ttk.Label(frame, text="One Atilma Tarihi Filtresi:", font=("Arial", 10, "bold")).grid(
            row=row, column=0, columnspan=2, sticky=tk.W, pady=5
        )
        row += 1
        
        ttk.Checkbutton(frame, text="Önde hiç kullanılmamışlar (önceliklidir)", variable=self.one_atilma_allow_na).grid(
            row=row, column=0, columnspan=2, sticky=tk.W, padx=20
        )
        row += 1
        
        ttk.Label(frame, text="Referans Tarih (T) (yyyy-mm-dd):", font=("Arial", 9)).grid(
            row=row, column=0, sticky=tk.W, padx=20, pady=5
        )
        ttk.Entry(frame, textvariable=self.one_atilma_date, width=15).grid(
            row=row, column=1, sticky=tk.W, pady=5
        )
        row += 1
        
        ttk.Label(frame, text="Minimum Gün Sayısı (X):", font=("Arial", 9)).grid(
            row=row, column=0, sticky=tk.W, padx=20, pady=5
        )
        ttk.Spinbox(frame, from_=0, to=365, textvariable=self.one_atilma_days, width=15).grid(
            row=row, column=1, sticky=tk.W, pady=5
        )
        row += 1
        
        ttk.Label(frame, text="(Ürün kabul: One Atilma < T - X gün)", font=("Arial", 8, "italic")).grid(
            row=row, column=0, columnspan=2, sticky=tk.W, padx=40
        )
        row += 1
        
        ttk.Separator(frame, orient="horizontal").grid(
            row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10
        )
        row += 1
        
        ttk.Label(frame, text="Minimum Toplam Stok:", font=("Arial", 10, "bold")).grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        ttk.Spinbox(frame, from_=0, to=10000, textvariable=self.min_stock_front, width=15).grid(
            row=row, column=1, sticky=tk.W, pady=5
        )
        row += 1
        
        ttk.Separator(frame, orient="horizontal").grid(
            row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10
        )
        row += 1
        
        ttk.Label(frame, text="Beden/Stok Kuralları:", font=("Arial", 10, "bold")).grid(
            row=row, column=0, columnspan=3, sticky=tk.W, pady=5
        )
        row += 1
        
        ttk.Label(frame, text="Beden Sayısı", font=("Arial", 9, "bold")).grid(
            row=row, column=0, padx=20
        )
        ttk.Label(frame, text="Min Kaç Bedende (Y)", font=("Arial", 9, "bold")).grid(
            row=row, column=1, padx=5
        )
        ttk.Label(frame, text="Min Stok Değeri (Z)", font=("Arial", 9, "bold")).grid(
            row=row, column=2, padx=5
        )
        row += 1
        
        for i in range(1, 9):
            ttk.Label(frame, text=f"{i}", font=("Arial", 9)).grid(
                row=row, column=0, padx=20, pady=2
            )
            ttk.Spinbox(frame, from_=0, to=8, textvariable=self.front_size_y[i], width=10).grid(
                row=row, column=1, padx=5, pady=2
            )
            ttk.Spinbox(frame, from_=0, to=100, textvariable=self.front_size_z[i], width=10).grid(
                row=row, column=2, padx=5, pady=2
            )
            row += 1
        
        ttk.Separator(frame, orient="horizontal").grid(
            row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10
        )
        row += 1
        
        ttk.Label(frame, text="NOS/DVM Minimumları:", font=("Arial", 10, "bold")).grid(
            row=row, column=0, columnspan=2, sticky=tk.W, pady=5
        )
        row += 1
        
        ttk.Label(frame, text="Minimum NOS FIRST sayısı:", font=("Arial", 9)).grid(
            row=row, column=0, sticky=tk.W, padx=20, pady=5
        )
        ttk.Spinbox(frame, from_=0, to=100, textvariable=self.min_nos_front, width=15).grid(
            row=row, column=1, sticky=tk.W, pady=5
        )
        row += 1
        
        ttk.Label(frame, text="Minimum DVM FIRST sayısı:", font=("Arial", 9)).grid(
            row=row, column=0, sticky=tk.W, padx=20, pady=5
        )
        ttk.Spinbox(frame, from_=0, to=100, textvariable=self.min_dvm_front, width=15).grid(
            row=row, column=1, sticky=tk.W, pady=5
        )
    
    def create_back_tab(self, notebook):
        """BACK Product Criteria tab"""
        scroll_frame = ScrollableFrame(notebook)
        notebook.add(scroll_frame, text="BACK Ürün Kriterleri")
        frame = scroll_frame.scrollable_frame
        
        row = 0
        
        ttk.Label(frame, text="Mevsim Filtresi:", font=("Arial", 10, "bold")).grid(
            row=row, column=0, columnspan=2, sticky=tk.W, pady=5
        )
        row += 1
        
        ttk.Checkbutton(frame, text="Yazlık", variable=self.use_yazlik_back).grid(
            row=row, column=0, sticky=tk.W, padx=20
        )
        ttk.Checkbutton(frame, text="Kışlık", variable=self.use_kislik_back).grid(
            row=row, column=1, sticky=tk.W
        )
        row += 1
        
        ttk.Separator(frame, orient="horizontal").grid(
            row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10
        )
        row += 1
        
        # Cekim
        ttk.Label(frame, text="Cekim Filtresi:", font=("Arial", 10, "bold")).grid(
            row=row, column=0, columnspan=2, sticky=tk.W, pady=5
        )
        row += 1
        
        ttk.Checkbutton(frame, text="EVET", variable=self.cekim_back_evet).grid(
            row=row, column=0, sticky=tk.W, padx=20
        )
        ttk.Checkbutton(frame, text="NA", variable=self.cekim_back_na).grid(
            row=row, column=1, sticky=tk.W
        )
        row += 1
        
        ttk.Separator(frame, orient="horizontal").grid(
            row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10
        )
        row += 1
        
        ttk.Label(frame, text="Minimum Toplam Stok:", font=("Arial", 10, "bold")).grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        ttk.Spinbox(frame, from_=0, to=10000, textvariable=self.min_stock_back, width=15).grid(
            row=row, column=1, sticky=tk.W, pady=5
        )
        row += 1
        
        ttk.Separator(frame, orient="horizontal").grid(
            row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10
        )
        row += 1
        
        ttk.Label(frame, text="Beden/Stok Kuralları:", font=("Arial", 10, "bold")).grid(
            row=row, column=0, columnspan=3, sticky=tk.W, pady=5
        )
        row += 1
        
        ttk.Label(frame, text="Beden Sayısı", font=("Arial", 9, "bold")).grid(
            row=row, column=0, padx=20
        )
        ttk.Label(frame, text="Min Kaç Bedende (Y)", font=("Arial", 9, "bold")).grid(
            row=row, column=1, padx=5
        )
        ttk.Label(frame, text="Min Stok Değeri (Z)", font=("Arial", 9, "bold")).grid(
            row=row, column=2, padx=5
        )
        row += 1
        
        for i in range(1, 9):
            ttk.Label(frame, text=f"{i}", font=("Arial", 9)).grid(
                row=row, column=0, padx=20, pady=2
            )
            ttk.Spinbox(frame, from_=0, to=8, textvariable=self.back_size_y[i], width=10).grid(
                row=row, column=1, padx=5, pady=2
            )
            ttk.Spinbox(frame, from_=0, to=100, textvariable=self.back_size_z[i], width=10).grid(
                row=row, column=2, padx=5, pady=2
            )
            row += 1
    
    def create_advanced_tab(self, notebook):
        """Advanced Rules tab"""
        scroll_frame = ScrollableFrame(notebook)
        notebook.add(scroll_frame, text="Gelişmiş Kurallar")
        frame = scroll_frame.scrollable_frame
        
        row = 0
        
        ttk.Label(frame, text="Günlük Kısıtlar:", font=("Arial", 10, "bold")).grid(
            row=row, column=0, columnspan=2, sticky=tk.W, pady=5
        )
        row += 1
        
        ttk.Label(frame, text="Aynı ürün cinsi ardışık limit:", font=("Arial", 9)).grid(
            row=row, column=0, sticky=tk.W, padx=20, pady=5
        )
        ttk.Spinbox(frame, from_=0, to=10, textvariable=self.max_same_uruncinsi, width=15).grid(
            row=row, column=1, sticky=tk.W, pady=5
        )
        row += 1
        
        ttk.Label(frame, text="Minimum farklı ürün cinsi/gün:", font=("Arial", 9)).grid(
            row=row, column=0, sticky=tk.W, padx=20, pady=5
        )
        ttk.Spinbox(frame, from_=0, to=20, textvariable=self.min_distinct_uruncinsi, width=15).grid(
            row=row, column=1, sticky=tk.W, pady=5
        )
        row += 1
        
        ttk.Label(frame, text="Aynı renk ardışık limit:", font=("Arial", 9)).grid(
            row=row, column=0, sticky=tk.W, padx=20, pady=5
        )
        ttk.Spinbox(frame, from_=0, to=10, textvariable=self.max_same_color, width=15).grid(
            row=row, column=1, sticky=tk.W, pady=5
        )
        row += 1
        
        ttk.Label(frame, text="Minimum farklı renk/gün:", font=("Arial", 9)).grid(
            row=row, column=0, sticky=tk.W, padx=20, pady=5
        )
        ttk.Spinbox(frame, from_=0, to=20, textvariable=self.min_distinct_color, width=15).grid(
            row=row, column=1, sticky=tk.W, pady=5
        )
        row += 1
        
        ttk.Separator(frame, orient="horizontal").grid(
            row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10
        )
        row += 1
        
        ttk.Label(frame, text="Aynı KisaKod Kuralı:", font=("Arial", 10, "bold")).grid(
            row=row, column=0, columnspan=2, sticky=tk.W, pady=5
        )
        row += 1
        
        ttk.Label(frame, text="Minimum ara gün sayısı:", font=("Arial", 9)).grid(
            row=row, column=0, sticky=tk.W, padx=20, pady=5
        )
        ttk.Spinbox(frame, from_=0, to=7, textvariable=self.same_kisakod_gap, width=15).grid(
            row=row, column=1, sticky=tk.W, pady=5
        )
        row += 1
        
        ttk.Label(frame, text="(0 = kısıt yok, 1+ = N gün bekle)", font=("Arial", 8, "italic")).grid(
            row=row, column=0, columnspan=2, sticky=tk.W, padx=40
        )
        row += 1
        
        ttk.Label(frame, text="Aynı KisaKod max kullanım (FIRST):", font=("Arial", 9)).grid(
            row=row, column=0, sticky=tk.W, padx=20, pady=5
        )
        ttk.Spinbox(frame, from_=0, to=20, textvariable=self.max_first_uses_per_kisakod, width=15).grid(
            row=row, column=1, sticky=tk.W, pady=5
        )
        row += 1
        
        ttk.Label(frame, text="(0 = kısıt yok, sadece FIRST için)", font=("Arial", 8, "italic")).grid(
            row=row, column=0, columnspan=2, sticky=tk.W, padx=40
        )
        row += 1
        
        ttk.Separator(frame, orient="horizontal").grid(
            row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10
        )
        row += 1
        
        ttk.Label(frame, text="FIRST Renk Kısıtı:", font=("Arial", 10, "bold")).grid(
            row=row, column=0, columnspan=2, sticky=tk.W, pady=5
        )
        row += 1
        
        ttk.Label(frame, text="Günde max kaç FIRST SİYAH renk:", font=("Arial", 9)).grid(
            row=row, column=0, sticky=tk.W, padx=20, pady=5
        )
        ttk.Spinbox(frame, from_=0, to=20, textvariable=self.max_black_first_per_day, width=15).grid(
            row=row, column=1, sticky=tk.W, pady=5
        )
        row += 1
        
        ttk.Label(frame, text="(0 = kısıt yok)", font=("Arial", 8, "italic")).grid(
            row=row, column=0, columnspan=2, sticky=tk.W, padx=40
        )
    
    def create_global_tab(self, notebook):
        """Global Stock Targets tab"""
        scroll_frame = ScrollableFrame(notebook)
        notebook.add(scroll_frame, text="Global Stok Hedefleri")
        frame = scroll_frame.scrollable_frame
        
        row = 0
        
        ttk.Label(frame, text="Global Stok Hedefleri:", font=("Arial", 10, "bold")).grid(
            row=row, column=0, columnspan=2, sticky=tk.W, pady=5
        )
        row += 1
        
        ttk.Label(frame, text="Tüm FIRST ürünlerin toplam stoku (minimum):", font=("Arial", 9)).grid(
            row=row, column=0, sticky=tk.W, padx=20, pady=5
        )
        ttk.Spinbox(frame, from_=0, to=100000, textvariable=self.global_first_stock, width=15).grid(
            row=row, column=1, sticky=tk.W, pady=5
        )
        row += 1
        
        ttk.Label(frame, text="Tüm ürünlerin (FIRST+BACK) toplam stoku (minimum):", font=("Arial", 9)).grid(
            row=row, column=0, sticky=tk.W, padx=20, pady=5
        )
        ttk.Spinbox(frame, from_=0, to=100000, textvariable=self.global_total_stock, width=15).grid(
            row=row, column=1, sticky=tk.W, pady=5
        )
        row += 1
        
        ttk.Separator(frame, orient="horizontal").grid(
            row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10
        )
        row += 1
        
        ttk.Label(frame, text="Global Önceliklendirme:", font=("Arial", 10, "bold")).grid(
            row=row, column=0, columnspan=2, sticky=tk.W, pady=5
        )
        row += 1
        
        ttk.Checkbutton(
            frame, 
            text="Yeniliğe göre önceliklendir (KisaKod yıl + sıra)", 
            variable=self.prioritize_by_newness
        ).grid(row=row, column=0, columnspan=2, sticky=tk.W, padx=20, pady=5)
        row += 1
        
        ttk.Checkbutton(
            frame, 
            text="Stok miktarına göre önceliklendir", 
            variable=self.prioritize_by_stock
        ).grid(row=row, column=0, columnspan=2, sticky=tk.W, padx=20, pady=5)
        row += 1
        
        ttk.Label(frame, text="(Her ikisi veya hiçbiri seçilirse mevcut sıralama kullanılır)", font=("Arial", 8, "italic")).grid(
            row=row, column=0, columnspan=2, sticky=tk.W, padx=40
        )
        row += 1
        
        ttk.Separator(frame, orient="horizontal").grid(
            row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10
        )
        row += 1
        
        ttk.Label(frame, text="Not:", font=("Arial", 9, "bold")).grid(
            row=row, column=0, columnspan=2, sticky=tk.W, pady=5
        )
        row += 1
        
        ttk.Label(frame, text="Bu hedefler karşılanmazsa, sistem uyarı verecek", font=("Arial", 8)).grid(
            row=row, column=0, columnspan=2, sticky=tk.W, padx=20
        )
        row += 1
        
        ttk.Label(frame, text="ve best-effort modda devam etmek isteyip istemediğinizi soracaktır.", font=("Arial", 8)).grid(
            row=row, column=0, columnspan=2, sticky=tk.W, padx=20
        )
    
    def _attach_entry_context_menu(self, entry):
        """Attach right-click context menu with Cut/Copy/Paste/Select All to Entry widget"""
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Kes\tCtrl+X", command=lambda: entry.event_generate("<<Cut>>"))
        menu.add_command(label="Kopyala\tCtrl+C", command=lambda: entry.event_generate("<<Copy>>"))
        menu.add_command(label="Yapıştır\tCtrl+V", command=lambda: entry.event_generate("<<Paste>>"))
        menu.add_separator()
        menu.add_command(label="Tümünü Seç\tCtrl+A", command=lambda: (entry.select_range(0, 'end'), entry.icursor('end')))
        
        def show_menu(event):
            entry.focus_set()
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()
        
        entry.bind("<Button-3>", show_menu)
        entry.bind("<Control-a>", lambda e: (entry.select_range(0, 'end'), entry.icursor('end'), 'break'))
        entry.bind("<Control-Insert>", lambda e: (entry.event_generate("<<Copy>>"), 'break'))
        entry.bind("<Shift-Insert>", lambda e: (entry.event_generate("<<Paste>>"), 'break'))
        entry.bind("<Shift-Delete>", lambda e: (entry.event_generate("<<Cut>>"), 'break'))
    
    def create_preferred_tab(self, notebook):
        """Preferred FIRST Products tab (up to 10 rows)"""
        scroll_frame = ScrollableFrame(notebook)
        notebook.add(scroll_frame, text="Tercihli FIRST Ürünler")
        frame = scroll_frame.scrollable_frame
        
        row = 0
        
        ttk.Label(frame, text="Tercihli FIRST Ürünler (İsteğe Bağlı):", font=("Arial", 10, "bold")).grid(
            row=row, column=0, columnspan=3, sticky=tk.W, pady=5
        )
        row += 1
        
        ttk.Label(frame, text="Bu ürünler FIRST olarak plana dahil edilmeye çalışılacaktır.", font=("Arial", 9)).grid(
            row=row, column=0, columnspan=3, sticky=tk.W, padx=20, pady=5
        )
        row += 1
        
        ttk.Label(frame, text="Gün+Saat seçilirse: O gün o saatte kullanılır (hard constraint)", font=("Arial", 8, "italic")).grid(
            row=row, column=0, columnspan=3, sticky=tk.W, padx=20
        )
        row += 1
        
        ttk.Label(frame, text="Sadece KisaKod+Renk girilirse: Herhangi bir günde kullanılır", font=("Arial", 8, "italic")).grid(
            row=row, column=0, columnspan=3, sticky=tk.W, padx=20
        )
        row += 1
        
        ttk.Separator(frame, orient="horizontal").grid(
            row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10
        )
        row += 1
        
        ttk.Label(frame, text="#", font=("Arial", 9, "bold"), width=3).grid(
            row=row, column=0, sticky=tk.W, padx=5
        )
        ttk.Label(frame, text="KisaKod+Renk", font=("Arial", 9, "bold"), width=20).grid(
            row=row, column=1, sticky=tk.W, padx=5
        )
        ttk.Label(frame, text="Gün", font=("Arial", 9, "bold"), width=15).grid(
            row=row, column=2, sticky=tk.W, padx=5
        )
        ttk.Label(frame, text="Saat", font=("Arial", 9, "bold"), width=10).grid(
            row=row, column=3, sticky=tk.W, padx=5
        )
        row += 1
        
        gun_options = ["", "Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
        weekday_times = ["", "09:00", "10:30", "11:30", "12:30", "13:30", "14:30", "15:30", "16:30", "17:30", "19:30", "21:00", "22:30"]
        weekend_times = ["", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00", "17:00", "18:30", "19:30", "21:00"]
        
        self.preferred_entries = []
        for i in range(10):
            kisakodrenk_var = tk.StringVar()
            gun_var = tk.StringVar()
            time_var = tk.StringVar()
            
            ttk.Label(frame, text=f"{i+1}.", font=("Arial", 9)).grid(
                row=row, column=0, sticky=tk.W, padx=5, pady=2
            )
            
            kisakodrenk_entry = ttk.Entry(frame, textvariable=kisakodrenk_var, width=20)
            kisakodrenk_entry.grid(row=row, column=1, sticky=tk.W, padx=5, pady=2)
            self._attach_entry_context_menu(kisakodrenk_entry)
            
            gun_combo = ttk.Combobox(frame, textvariable=gun_var, width=15, state="readonly", values=gun_options)
            gun_combo.grid(row=row, column=2, sticky=tk.W, padx=5, pady=2)
            
            time_combo = ttk.Combobox(frame, textvariable=time_var, width=10, state="readonly")
            time_combo.grid(row=row, column=3, sticky=tk.W, padx=5, pady=2)
            
            def on_gun_change(event, gun_v=gun_var, time_v=time_var, time_c=time_combo, wdt=weekday_times, wet=weekend_times):
                gun = gun_v.get()
                if not gun:
                    time_c['values'] = [""]
                    time_v.set("")
                    time_c['state'] = 'disabled'
                elif gun in ["Cumartesi", "Pazar"]:
                    time_c['values'] = wet
                    time_c['state'] = 'readonly'
                else:
                    time_c['values'] = wdt
                    time_c['state'] = 'readonly'
            
            gun_combo.bind('<<ComboboxSelected>>', on_gun_change)
            time_combo['state'] = 'disabled'
            
            self.preferred_entries.append({
                'kisakodrenk': kisakodrenk_var,
                'kisakodrenk_entry': kisakodrenk_entry,
                'gun': gun_var,
                'time': time_var,
                'gun_combo': gun_combo,
                'time_combo': time_combo
            })
            
            row += 1
        
        ttk.Separator(frame, orient="horizontal").grid(
            row=row, column=0, columnspan=4, sticky=(tk.W, tk.E), pady=10
        )
        row += 1
        
        ttk.Label(frame, text="Önemli Notlar:", font=("Arial", 9, "bold")).grid(
            row=row, column=0, columnspan=4, sticky=tk.W, pady=5
        )
        row += 1
        
        ttk.Label(frame, text="• Saat seçilirse gün de seçilmelidir (zorunlu)", font=("Arial", 8)).grid(
            row=row, column=0, columnspan=4, sticky=tk.W, padx=20
        )
        row += 1
        
        ttk.Label(frame, text="• Gün plan aralığı içinde olmalıdır", font=("Arial", 8)).grid(
            row=row, column=0, columnspan=4, sticky=tk.W, padx=20
        )
        row += 1
        
        ttk.Label(frame, text="• Tercihli ürünler tüm FIRST kriterlerine uymalıdır", font=("Arial", 8)).grid(
            row=row, column=0, columnspan=4, sticky=tk.W, padx=20
        )
    
    def create_output_tab(self, notebook):
        """Output and Status tab"""
        frame = ttk.Frame(notebook, padding="10")
        notebook.add(frame, text="Çıktı ve Durum")
        
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        
        self.output_text = scrolledtext.ScrolledText(
            frame,
            wrap=tk.WORD,
            width=80,
            height=30,
            font=("Courier", 9)
        )
        self.output_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    
    def select_file(self):
        filename = filedialog.askopenfilename(
            title="Stok Dosyasını Seç",
            filetypes=[("Excel files", "*.xlsx *.xls"), ("All files", "*.*")]
        )
        if filename:
            self.excel_path.set(filename)
            self.append_output(f"Dosya seçildi: {filename}\n")
    
    def append_output(self, text):
        self.output_text.insert(tk.END, text)
        self.output_text.see(tk.END)
        self.output_text.update_idletasks()
    
    def clear_output(self):
        self.output_text.delete(1.0, tk.END)
    
    def check_progress_queue(self):
        try:
            while True:
                msg = self.progress_queue.get_nowait()
                self.append_output(msg + "\n")
        except queue.Empty:
            pass
        
        try:
            while True:
                decision_msg = self.decision_queue.get_nowait()
                result = messagebox.askyesno(
                    "Kriter Uyarısı",
                    decision_msg + "\n\nBest-effort ile devam edilsin mi?",
                    icon="warning"
                )
                self.decision_result = result
                self.decision_event.set()
        except queue.Empty:
            pass
        
        self.root.after(100, self.check_progress_queue)
    
    def on_progress(self, msg):
        self.progress_queue.put(msg)
    
    def on_decision(self, msg):
        self.decision_queue.put(msg)
        self.decision_event.clear()
        self.decision_event.wait()
        return self.decision_result
    
    def on_relaxation_choice(self, suggestions, message, missing_first, missing_back):
        """Handle relaxation choice dialog with checkboxes and three buttons - thread-safe version"""
        import threading
        
        choice_result = {"choice": "manual", "selected": []}
        choice_event = threading.Event()
        
        def show_dialog():
            dialog = tk.Toplevel(self.root)
            dialog.title("Kriter Uyarısı / Bu ayarlarla plan oluşturulamıyor (v2.1)")
            dialog.geometry("950x700")
            dialog.minsize(700, 500)
            dialog.resizable(True, True)
            dialog.transient(self.root)
            dialog.grab_set()
            
            def on_window_close():
                choice_result["choice"] = "manual"
                choice_result["selected"] = []
                dialog.destroy()
                choice_event.set()
            
            dialog.protocol("WM_DELETE_WINDOW", on_window_close)
            
            frame = ttk.Frame(dialog, padding="10")
            frame.pack(fill="both", expand=True)
            
            title_label = ttk.Label(frame, text="Bu ayarlarla plan oluşturulamıyor.", 
                                    font=("Arial", 12, "bold"))
            title_label.pack(pady=(0, 5))
            
            missing_label = ttk.Label(frame, 
                                      text=f"Eksik FIRST sayısı: {missing_first} post, Eksik BACK sayısı: {missing_back} ürün.",
                                      font=("Arial", 10, "italic"),
                                      foreground="red")
            missing_label.pack(pady=(0, 5))
            
            subtitle_label = ttk.Label(frame, text="Tüm esnetilebilir kurallar listelenmiştir. Hangilerini gevşetmek istediğinizi seçin.",
                                       font=("Arial", 10))
            subtitle_label.pack(pady=(0, 10))
            
            content_container = ttk.Frame(frame)
            content_container.pack(fill="both", expand=True)
            
            canvas = tk.Canvas(content_container, borderwidth=0, highlightthickness=0)
            scrollbar = ttk.Scrollbar(content_container, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)
            
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            
            window_id = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            
            def on_content_resize(event):
                canvas.itemconfig(window_id, width=event.width)
            
            content_container.bind("<Configure>", on_content_resize)
            
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            
            checkbox_vars = []
            for i, sug in enumerate(suggestions):
                preselected = sug.get("preselected", True)
                var = tk.BooleanVar(value=preselected)
                checkbox_vars.append(var)
                
                cb_frame = ttk.Frame(scrollable_frame)
                cb_frame.pack(fill="x", pady=5, padx=5)
                
                cb = ttk.Checkbutton(cb_frame, variable=var)
                cb.pack(side="left", padx=(0, 5))
                
                impact = sug.get('estimated_new_candidates', 0)
                if impact > 0:
                    impact_text = f"Tahmini etki: +{impact} aday"
                else:
                    impact_text = "Tahmini etki: +0 aday (düşük etki)"
                
                label_text = f"{sug['rule_name']}: {sug['original_value']} → {sug['suggested_value']}, {impact_text}"
                label = ttk.Label(cb_frame, text=label_text, wraplength=800)
                label.pack(side="left", fill="x", expand=True)
            
            button_frame = ttk.Frame(frame)
            button_frame.pack(fill="x", pady=(10, 10), side="bottom")
            
            def on_manual():
                choice_result["choice"] = "manual"
                choice_result["selected"] = []
                dialog.destroy()
                choice_event.set()
            
            def on_retry_strict():
                selected = [sug for i, sug in enumerate(suggestions) if checkbox_vars[i].get()]
                choice_result["choice"] = "retry_strict"
                choice_result["selected"] = selected
                dialog.destroy()
                choice_event.set()
            
            def on_continue_best():
                selected = [sug for i, sug in enumerate(suggestions) if checkbox_vars[i].get()]
                choice_result["choice"] = "continue_best"
                choice_result["selected"] = selected
                dialog.destroy()
                choice_event.set()
            
            manual_button = ttk.Button(button_frame, text="Hayır, ayarları manuel düzelteceğim", 
                                       command=on_manual)
            manual_button.pack(side="top", fill="x", padx=10, pady=(0, 6))
            
            retry_button = ttk.Button(button_frame, text="Seçili esnetmeleri uygula ve tekrar dene", 
                                      command=on_retry_strict)
            retry_button.pack(side="top", fill="x", padx=10, pady=(0, 6))
            
            best_button = ttk.Button(button_frame, text="Evet, seçili esnetmelerle best-effort ile devam et", 
                                     command=on_continue_best)
            best_button.pack(side="top", fill="x", padx=10, pady=(0, 6))
            
            dialog.wait_window()
        
        self.root.after(0, show_dialog)
        
        if not choice_event.wait(timeout=300):
            print("WARNING: Relaxation choice dialog timed out after 5 minutes")
            return "manual", []
        
        return choice_result["choice"], choice_result["selected"]
    
    def collect_config(self) -> PlanConfig:
        """Collect all GUI values into a PlanConfig object"""
        config = PlanConfig(
            stock_excel_path=self.excel_path.get(),
            plan_start_day_name=self.start_day.get(),
            plan_num_days=self.num_days.get(),
        )
        
        config.use_yazlik_front = self.use_yazlik_front.get()
        config.use_kislik_front = self.use_kislik_front.get()
        
        cekim_front = []
        if self.cekim_front_evet.get():
            cekim_front.append("EVET")
        if self.cekim_front_na.get():
            cekim_front.append("NA")
        config.allowed_cekim_front = cekim_front
        
        config.one_atilma_allow_na = self.one_atilma_allow_na.get()
        config.prioritize_never_used_first = self.one_atilma_allow_na.get()
        config.one_atilma_reference_date = self.one_atilma_date.get()
        config.one_atilma_min_days = self.one_atilma_days.get()
        config.min_total_stock_front = self.min_stock_front.get()
        config.min_nos_front = self.min_nos_front.get()
        config.min_dvm_front = self.min_dvm_front.get()
        
        for i in range(1, 9):
            y = self.front_size_y[i].get()
            z = self.front_size_z[i].get()
            config.front_size_stock_rules[i] = (y, z)
        
        config.use_yazlik_back = self.use_yazlik_back.get()
        config.use_kislik_back = self.use_kislik_back.get()
        
        cekim_back = []
        if self.cekim_back_evet.get():
            cekim_back.append("EVET")
        if self.cekim_back_na.get():
            cekim_back.append("NA")
        config.allowed_cekim_back = cekim_back
        
        config.min_total_stock_back = self.min_stock_back.get()
        
        for i in range(1, 9):
            y = self.back_size_y[i].get()
            z = self.back_size_z[i].get()
            config.back_size_stock_rules[i] = (y, z)
        
        config.max_same_uruncinsi_in_a_row_per_day = self.max_same_uruncinsi.get()
        config.min_distinct_uruncinsi_per_day = self.min_distinct_uruncinsi.get()
        config.max_same_color_in_a_row_per_day = self.max_same_color.get()
        config.min_distinct_color_per_day = self.min_distinct_color.get()
        config.same_kisakod_min_gap_days = self.same_kisakod_gap.get()
        
        config.max_black_first_per_day = self.max_black_first_per_day.get()
        config.max_first_uses_per_kisakod = self.max_first_uses_per_kisakod.get()
        
        config.global_min_first_stock_sum = self.global_first_stock.get()
        config.global_min_total_stock_sum = self.global_total_stock.get()
        
        config.prioritize_by_newness = self.prioritize_by_newness.get()
        config.prioritize_by_stock = self.prioritize_by_stock.get()
        
        from config import PreferredFirstProduct
        for entry in self.preferred_entries:
            kisakodrenk = entry['kisakodrenk'].get().strip()
            gun = entry['gun'].get().strip()
            time = entry['time'].get().strip()
            
            if kisakodrenk:
                config.preferred_first_products.append(
                    PreferredFirstProduct(
                        kisakodrenk=kisakodrenk,
                        gun=gun if gun else None,
                        time=time if time else None
                    )
                )
        
        return config
    
    def run_planner(self):
        if self.is_running:
            messagebox.showwarning("Uyarı", "Plan oluşturma zaten çalışıyor!")
            return
        
        missing_fields = self.validate_required_fields()
        if missing_fields:
            messagebox.showerror(
                "Eksik Bilgiler",
                "Plan oluşturmak için aşağıdaki alanlar doldurulmalıdır:\n\n" + 
                "\n".join(f"• {field}" for field in missing_fields) +
                "\n\nLütfen bu alanları doldurup tekrar deneyin."
            )
            return
        
        self.auto_save_settings()
        
        config = self.collect_config()
        errors = config.validate()
        
        if errors:
            messagebox.showerror(
                "Eksik Bilgiler",
                "Lütfen tüm gerekli alanları doldurun:\n\n" + "\n".join(f"- {e}" for e in errors)
            )
            return
        
        if not os.path.exists(config.stock_excel_path):
            messagebox.showerror("Hata", "Seçilen dosya bulunamadı!")
            return
        
        self.clear_output()
        self.append_output("Plan oluşturma başlatılıyor...\n\n")
        
        self.is_running = True
        self.run_button.config(state="disabled")
        self.root.config(cursor="watch")
        
        thread = threading.Thread(target=self.run_planner_thread, args=(config,), daemon=True)
        thread.start()
    
    def run_planner_thread(self, config):
        try:
            cfg_dict = config.to_dict()
            
            result = run_planner_with_best_effort(
                excel_path=config.stock_excel_path,
                start_day=config.plan_start_day_name,
                num_days=config.plan_num_days,
                mode_front="Her ikisi",  # Handled by config
                mode_back="Her ikisi",   # Handled by config
                on_progress=self.on_progress,
                on_relaxation_choice=self.on_relaxation_choice,
                config_override=cfg_dict
            )
            
            self.root.after(0, self.on_planner_complete, result)
            
        except Exception as e:
            import traceback
            error_msg = f"Beklenmeyen hata:\n{str(e)}\n\n{traceback.format_exc()}"
            self.root.after(0, self.on_planner_error, error_msg)
    
    def on_planner_complete(self, result):
        self.is_running = False
        self.run_button.config(state="normal")
        self.root.config(cursor="")
        
        if result["success"]:
            messagebox.showinfo(
                "Başarılı",
                f"Plan başarıyla oluşturuldu!\n\n"
                f"Excel: {result['output_excel']}\n"
                f"Markdown: {result['output_md']}"
            )
        else:
            messagebox.showerror(
                "Hata",
                f"Plan oluşturulamadı:\n\n{result.get('error', 'Bilinmeyen hata')}"
            )
    
    def on_planner_error(self, error_msg):
        self.is_running = False
        self.run_button.config(state="normal")
        self.root.config(cursor="")
        
        self.append_output(f"\n{error_msg}\n")
        messagebox.showerror("Hata", "Plan oluşturma sırasında hata oluştu. Detaylar için çıktı alanına bakın.")
    
    def setup_auto_save_triggers(self):
        """Setup auto-save triggers on field changes"""
        def trigger_auto_save(*args):
            self.auto_save_settings()
        
        self.excel_path.trace_add("write", trigger_auto_save)
        self.start_day.trace_add("write", trigger_auto_save)
        self.num_days.trace_add("write", trigger_auto_save)
        
        self.use_yazlik_front.trace_add("write", trigger_auto_save)
        self.use_kislik_front.trace_add("write", trigger_auto_save)
        self.cekim_front_evet.trace_add("write", trigger_auto_save)
        self.cekim_front_na.trace_add("write", trigger_auto_save)
        
        self.one_atilma_allow_na.trace_add("write", trigger_auto_save)
        self.one_atilma_date.trace_add("write", trigger_auto_save)
        self.one_atilma_days.trace_add("write", trigger_auto_save)
        self.min_stock_front.trace_add("write", trigger_auto_save)
        self.min_nos_front.trace_add("write", trigger_auto_save)
        self.min_dvm_front.trace_add("write", trigger_auto_save)
        
        for i in range(1, 9):
            self.front_size_y[i].trace_add("write", trigger_auto_save)
            self.front_size_z[i].trace_add("write", trigger_auto_save)
        
        self.use_yazlik_back.trace_add("write", trigger_auto_save)
        self.use_kislik_back.trace_add("write", trigger_auto_save)
        self.cekim_back_evet.trace_add("write", trigger_auto_save)
        self.cekim_back_na.trace_add("write", trigger_auto_save)
        self.min_stock_back.trace_add("write", trigger_auto_save)
        
        for i in range(1, 9):
            self.back_size_y[i].trace_add("write", trigger_auto_save)
            self.back_size_z[i].trace_add("write", trigger_auto_save)
        
        self.max_same_uruncinsi.trace_add("write", trigger_auto_save)
        self.min_distinct_uruncinsi.trace_add("write", trigger_auto_save)
        self.max_same_color.trace_add("write", trigger_auto_save)
        self.min_distinct_color.trace_add("write", trigger_auto_save)
        self.same_kisakod_gap.trace_add("write", trigger_auto_save)
        
        self.max_black_first_per_day.trace_add("write", trigger_auto_save)
        self.max_first_uses_per_kisakod.trace_add("write", trigger_auto_save)
        
        self.global_first_stock.trace_add("write", trigger_auto_save)
        self.global_total_stock.trace_add("write", trigger_auto_save)
        
        self.prioritize_by_newness.trace_add("write", trigger_auto_save)
        self.prioritize_by_stock.trace_add("write", trigger_auto_save)
    
    def get_settings_file_path(self):
        """Get path to settings file"""
        return os.path.join(os.path.expanduser("~"), ".instagram_planner_settings.json")
    
    def auto_save_settings(self):
        """Automatically save current settings to local file"""
        try:
            import json
            config = self.collect_config()
            settings_file = self.get_settings_file_path()
            with open(settings_file, 'w', encoding='utf-8') as f:
                json.dump(config.to_dict(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Auto-save failed: {e}")
    
    def auto_load_settings(self):
        """Automatically load settings from local file on startup"""
        try:
            import json
            settings_file = self.get_settings_file_path()
            if os.path.exists(settings_file):
                with open(settings_file, 'r', encoding='utf-8') as f:
                    cfg_dict = json.load(f)
                self.load_settings_into_gui(cfg_dict)
        except Exception as e:
            print(f"Auto-load failed: {e}")
    
    def load_settings_into_gui(self, cfg_dict):
        """Load settings dictionary into GUI fields"""
        if 'stock_excel_path' in cfg_dict:
            self.excel_path.set(cfg_dict['stock_excel_path'])
        if 'plan_start_day_name' in cfg_dict:
            self.start_day.set(cfg_dict['plan_start_day_name'])
        if 'plan_num_days' in cfg_dict:
            self.num_days.set(cfg_dict['plan_num_days'])
        
        if 'use_yazlik_front' in cfg_dict:
            self.use_yazlik_front.set(cfg_dict['use_yazlik_front'])
        if 'use_kislik_front' in cfg_dict:
            self.use_kislik_front.set(cfg_dict['use_kislik_front'])
        
        if 'allowed_cekim_front' in cfg_dict:
            cekim_front = cfg_dict['allowed_cekim_front']
            self.cekim_front_evet.set('EVET' in cekim_front)
            self.cekim_front_na.set('NA' in cekim_front)
        
        if 'one_atilma_allow_na' in cfg_dict:
            self.one_atilma_allow_na.set(cfg_dict['one_atilma_allow_na'])
        if 'one_atilma_reference_date' in cfg_dict:
            self.one_atilma_date.set(cfg_dict['one_atilma_reference_date'])
        if 'one_atilma_min_days' in cfg_dict:
            self.one_atilma_days.set(cfg_dict['one_atilma_min_days'])
        if 'min_total_stock_front' in cfg_dict:
            self.min_stock_front.set(cfg_dict['min_total_stock_front'])
        if 'min_nos_front' in cfg_dict:
            self.min_nos_front.set(cfg_dict['min_nos_front'])
        if 'min_dvm_front' in cfg_dict:
            self.min_dvm_front.set(cfg_dict['min_dvm_front'])
        
        if 'front_size_stock_rules' in cfg_dict:
            rules = cfg_dict['front_size_stock_rules']
            if isinstance(rules, list):
                for item in rules:
                    if isinstance(item, (list, tuple)) and len(item) == 2:
                        size_count, (y, z) = item
                        if size_count in self.front_size_y:
                            self.front_size_y[size_count].set(y)
                            self.front_size_z[size_count].set(z)
        
        if 'use_yazlik_back' in cfg_dict:
            self.use_yazlik_back.set(cfg_dict['use_yazlik_back'])
        if 'use_kislik_back' in cfg_dict:
            self.use_kislik_back.set(cfg_dict['use_kislik_back'])
        
        if 'allowed_cekim_back' in cfg_dict:
            cekim_back = cfg_dict['allowed_cekim_back']
            self.cekim_back_evet.set('EVET' in cekim_back)
            self.cekim_back_na.set('NA' in cekim_back)
        
        if 'min_total_stock_back' in cfg_dict:
            self.min_stock_back.set(cfg_dict['min_total_stock_back'])
        
        if 'back_size_stock_rules' in cfg_dict:
            rules = cfg_dict['back_size_stock_rules']
            if isinstance(rules, list):
                for item in rules:
                    if isinstance(item, (list, tuple)) and len(item) == 2:
                        size_count, (y, z) = item
                        if size_count in self.back_size_y:
                            self.back_size_y[size_count].set(y)
                            self.back_size_z[size_count].set(z)
        
        if 'max_same_uruncinsi_in_a_row_per_day' in cfg_dict:
            self.max_same_uruncinsi.set(cfg_dict['max_same_uruncinsi_in_a_row_per_day'])
        if 'min_distinct_uruncinsi_per_day' in cfg_dict:
            self.min_distinct_uruncinsi.set(cfg_dict['min_distinct_uruncinsi_per_day'])
        if 'max_same_color_in_a_row_per_day' in cfg_dict:
            self.max_same_color.set(cfg_dict['max_same_color_in_a_row_per_day'])
        if 'min_distinct_color_per_day' in cfg_dict:
            self.min_distinct_color.set(cfg_dict['min_distinct_color_per_day'])
        if 'same_kisakod_min_gap_days' in cfg_dict:
            self.same_kisakod_gap.set(cfg_dict['same_kisakod_min_gap_days'])
        
        if 'max_black_first_per_day' in cfg_dict:
            self.max_black_first_per_day.set(cfg_dict['max_black_first_per_day'])
        if 'max_first_uses_per_kisakod' in cfg_dict:
            self.max_first_uses_per_kisakod.set(cfg_dict['max_first_uses_per_kisakod'])
        
        if 'global_min_first_stock_sum' in cfg_dict:
            self.global_first_stock.set(cfg_dict['global_min_first_stock_sum'])
        if 'global_min_total_stock_sum' in cfg_dict:
            self.global_total_stock.set(cfg_dict['global_min_total_stock_sum'])
        
        if 'prioritize_by_newness' in cfg_dict:
            self.prioritize_by_newness.set(cfg_dict['prioritize_by_newness'])
        if 'prioritize_by_stock' in cfg_dict:
            self.prioritize_by_stock.set(cfg_dict['prioritize_by_stock'])
        
        if 'preferred_first_products' in cfg_dict:
            preferred_list = cfg_dict['preferred_first_products']
            if isinstance(preferred_list, list):
                for i, pref in enumerate(preferred_list):
                    if i < len(self.preferred_entries):
                        entry = self.preferred_entries[i]
                        
                        kisakodrenk = pref.get('kisakodrenk', '')
                        gun = pref.get('gun', '')
                        time = pref.get('time', '')
                        
                        entry['kisakodrenk'].set(kisakodrenk)
                        entry['gun'].set(gun)
                        entry['time'].set(time)
                        
                        gun_combo = entry.get('gun_combo')
                        time_combo = entry.get('time_combo')
                        
                        if gun_combo and time_combo:
                            if gun:
                                weekday_times = ["", "09:00", "10:30", "11:30", "12:30", "13:30", "14:30", "15:30", "16:30", "17:30", "19:30", "21:00", "22:30"]
                                weekend_times = ["", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00", "17:00", "18:30", "19:30", "21:00"]
                                
                                if gun in ["Cumartesi", "Pazar"]:
                                    time_combo['values'] = weekend_times
                                else:
                                    time_combo['values'] = weekday_times
                                time_combo['state'] = 'readonly'
                            else:
                                time_combo['values'] = [""]
                                time_combo['state'] = 'disabled'
    
    def reset_settings(self):
        """Reset all settings to default values and clear saved settings"""
        if self.is_running:
            messagebox.showwarning("Uyarı", "Plan oluşturma sürerken ayarları sıfırlayamazsınız.")
            return
        
        result = messagebox.askyesno(
            "Ayarları Sıfırla",
            "Tüm ayarlar silinecek ve varsayılan değerlere dönülecek.\nDevam etmek istiyor musunuz?"
        )
        if result:
            self.excel_path.set("")
            self.start_day.set("Pazartesi")
            self.num_days.set(7)
            
            self.use_yazlik_front.set(False)
            self.use_kislik_front.set(False)
            self.cekim_front_evet.set(False)
            self.cekim_front_na.set(False)
            
            self.one_atilma_allow_na.set(False)
            self.one_atilma_date.set("")
            self.one_atilma_days.set(0)
            self.min_stock_front.set(0)
            self.min_nos_front.set(0)
            self.min_dvm_front.set(0)
            
            for i in range(1, 9):
                self.front_size_y[i].set(0)
                self.front_size_z[i].set(0)
            
            self.use_yazlik_back.set(False)
            self.use_kislik_back.set(False)
            self.cekim_back_evet.set(False)
            self.cekim_back_na.set(False)
            self.min_stock_back.set(0)
            
            for i in range(1, 9):
                self.back_size_y[i].set(0)
                self.back_size_z[i].set(0)
            
            self.max_same_uruncinsi.set(0)
            self.min_distinct_uruncinsi.set(0)
            self.max_same_color.set(0)
            self.min_distinct_color.set(0)
            self.same_kisakod_gap.set(0)
            
            self.max_black_first_per_day.set(0)
            self.max_first_uses_per_kisakod.set(0)
            
            self.global_first_stock.set(0)
            self.global_total_stock.set(0)
            
            self.prioritize_by_newness.set(False)
            self.prioritize_by_stock.set(False)
            
            for entry in getattr(self, "preferred_entries", []):
                entry['kisakodrenk'].set("")
                entry['gun'].set("")
                entry['time'].set("")
                
                gun_combo = entry.get('gun_combo')
                time_combo = entry.get('time_combo')
                if gun_combo:
                    gun_combo.set("")
                if time_combo:
                    time_combo['values'] = [""]
                    time_combo.set("")
                    time_combo['state'] = 'disabled'
            
            self.clear_output()
            
            self.auto_save_settings()
            
            messagebox.showinfo("Başarılı", "Tüm ayarlar sıfırlandı.")
    
    def validate_required_fields(self):
        """Validate all required fields before plan generation"""
        missing_fields = []
        
        if not self.excel_path.get():
            missing_fields.append("Stok dosyası (Excel)")
        
        if not self.start_day.get():
            missing_fields.append("Plan başlangıç günü")
        
        if not self.num_days.get() or self.num_days.get() < 1:
            missing_fields.append("Kaç günlük plan (1-7)")
        
        if not self.use_yazlik_front.get() and not self.use_kislik_front.get():
            missing_fields.append("FIRST mevsim seçimi (Yazlık veya Kışlık)")
        
        if not self.use_yazlik_back.get() and not self.use_kislik_back.get():
            missing_fields.append("BACK mevsim seçimi (Yazlık veya Kışlık)")
        
        if not self.cekim_front_evet.get() and not self.cekim_front_na.get():
            missing_fields.append("FIRST Çekim seçimi (en az bir seçenek)")
        
        if not self.cekim_back_evet.get() and not self.cekim_back_na.get():
            missing_fields.append("BACK Çekim seçimi (en az bir seçenek)")
        
        if not self.prioritize_by_newness.get() and not self.prioritize_by_stock.get():
            missing_fields.append("Önceliklendirme (Yenilik veya Stok)")
        
        return missing_fields


def main():
    root = tk.Tk()
    
    try:
        root.tk.call("source", "azure.tcl")
        root.tk.call("set_theme", "light")
    except:
        pass
    
    app = PlannerGUI(root)
    
    root.mainloop()


if __name__ == "__main__":
    main()
