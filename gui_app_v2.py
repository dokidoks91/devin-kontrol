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
from planner import run_planner


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
        
        self.use_yazlik_front = tk.BooleanVar(value=True)
        self.use_kislik_front = tk.BooleanVar(value=True)
        self.cekim_front_evet = tk.BooleanVar(value=True)
        self.cekim_front_na = tk.BooleanVar(value=True)
        self.one_atilma_allow_na = tk.BooleanVar(value=True)
        self.one_atilma_date = tk.StringVar(value="2025-02-01")
        self.one_atilma_days = tk.IntVar(value=45)
        self.min_stock_front = tk.IntVar(value=15)
        self.min_nos_front = tk.IntVar(value=2)
        self.min_dvm_front = tk.IntVar(value=2)
        
        self.front_size_y = {}
        self.front_size_z = {}
        for i in range(1, 9):
            self.front_size_y[i] = tk.IntVar(value=0)
            self.front_size_z[i] = tk.IntVar(value=0)
        
        self.use_yazlik_back = tk.BooleanVar(value=True)
        self.use_kislik_back = tk.BooleanVar(value=True)
        self.cekim_back_evet = tk.BooleanVar(value=True)
        self.cekim_back_na = tk.BooleanVar(value=True)
        self.min_stock_back = tk.IntVar(value=5)
        
        self.back_size_y = {}
        self.back_size_z = {}
        for i in range(1, 9):
            self.back_size_y[i] = tk.IntVar(value=0)
            self.back_size_z[i] = tk.IntVar(value=0)
        
        self.max_same_uruncinsi = tk.IntVar(value=3)
        self.min_distinct_uruncinsi = tk.IntVar(value=2)
        self.max_same_color = tk.IntVar(value=3)
        self.min_distinct_color = tk.IntVar(value=3)
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
            text="Ayarları Kaydet",
            command=self.save_config
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            button_frame,
            text="Ayarları Yükle",
            command=self.load_config
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
        
        ttk.Checkbutton(frame, text="#N/A değerlerine izin ver", variable=self.one_atilma_allow_na).grid(
            row=row, column=0, columnspan=2, sticky=tk.W, padx=20
        )
        row += 1
        
        ttk.Label(frame, text="Referans Tarih (T):", font=("Arial", 9)).grid(
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
        
        return config
    
    def run_planner(self):
        if self.is_running:
            messagebox.showwarning("Uyarı", "Plan oluşturma zaten çalışıyor!")
            return
        
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
            
            result = run_planner(
                excel_path=config.stock_excel_path,
                start_day=config.plan_start_day_name,
                num_days=config.plan_num_days,
                mode_front="Her ikisi",  # Handled by config
                mode_back="Her ikisi",   # Handled by config
                on_progress=self.on_progress,
                on_decision=self.on_decision,
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
    
    def save_config(self):
        """Save current configuration to file"""
        filename = filedialog.asksaveasfilename(
            title="Ayarları Kaydet",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            import json
            config = self.collect_config()
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(config.to_dict(), f, indent=2, ensure_ascii=False)
            messagebox.showinfo("Başarılı", f"Ayarlar kaydedildi: {filename}")
    
    def load_config(self):
        """Load configuration from file"""
        filename = filedialog.askopenfilename(
            title="Ayarları Yükle",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            import json
            with open(filename, 'r', encoding='utf-8') as f:
                cfg_dict = json.load(f)
            messagebox.showinfo("Başarılı", f"Ayarlar yüklendi: {filename}")


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
