#!/usr/bin/env python3
"""
Instagram Post Planner - Windows GUI Application

A simple Tkinter-based GUI for the Instagram post planning tool.
Allows users to select an Excel file, configure planning parameters,
and generate weekly post plans with a visual interface.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import queue
import os
import sys
from planner import run_planner


class PlannerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Instagram Post Planner")
        self.root.geometry("800x600")
        self.root.resizable(True, True)
        
        self.excel_path = tk.StringVar()
        self.start_day = tk.StringVar(value="Pazartesi")
        self.num_days = tk.IntVar(value=7)
        self.mode_front = tk.StringVar(value="Her ikisi")
        self.mode_back = tk.StringVar(value="Her ikisi")
        
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
        main_frame.columnconfigure(1, weight=1)
        
        row = 0
        
        ttk.Label(main_frame, text="Stok Dosyası:", font=("Arial", 10, "bold")).grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        row += 1
        
        file_frame = ttk.Frame(main_frame)
        file_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        file_frame.columnconfigure(0, weight=1)
        
        ttk.Entry(file_frame, textvariable=self.excel_path, state="readonly").grid(
            row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5)
        )
        ttk.Button(file_frame, text="Dosya Seç...", command=self.select_file).grid(
            row=0, column=1
        )
        row += 1
        
        ttk.Separator(main_frame, orient="horizontal").grid(
            row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10
        )
        row += 1
        
        ttk.Label(main_frame, text="Plan Başlangıç Günü:", font=("Arial", 10)).grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        day_combo = ttk.Combobox(
            main_frame,
            textvariable=self.start_day,
            values=["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"],
            state="readonly",
            width=15
        )
        day_combo.grid(row=row, column=1, sticky=tk.W, pady=5)
        row += 1
        
        ttk.Label(main_frame, text="Kaç Günlük Plan (1-7):", font=("Arial", 10)).grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        ttk.Spinbox(
            main_frame,
            from_=1,
            to=7,
            textvariable=self.num_days,
            width=15
        ).grid(row=row, column=1, sticky=tk.W, pady=5)
        row += 1
        
        ttk.Label(main_frame, text="Front Ürün Modu:", font=("Arial", 10)).grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        ttk.Combobox(
            main_frame,
            textvariable=self.mode_front,
            values=["Yazlık", "Kışlık", "Her ikisi"],
            state="readonly",
            width=15
        ).grid(row=row, column=1, sticky=tk.W, pady=5)
        row += 1
        
        ttk.Label(main_frame, text="Back Ürün Modu:", font=("Arial", 10)).grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        ttk.Combobox(
            main_frame,
            textvariable=self.mode_back,
            values=["Yazlık", "Kışlık", "Her ikisi"],
            state="readonly",
            width=15
        ).grid(row=row, column=1, sticky=tk.W, pady=5)
        row += 1
        
        ttk.Separator(main_frame, orient="horizontal").grid(
            row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10
        )
        row += 1
        
        self.run_button = ttk.Button(
            main_frame,
            text="Planı Oluştur",
            command=self.run_planner,
            style="Accent.TButton"
        )
        self.run_button.grid(row=row, column=0, columnspan=2, pady=10)
        row += 1
        
        ttk.Label(main_frame, text="Çıktı ve Durum:", font=("Arial", 10, "bold")).grid(
            row=row, column=0, sticky=tk.W, pady=(10, 5)
        )
        row += 1
        
        self.output_text = scrolledtext.ScrolledText(
            main_frame,
            wrap=tk.WORD,
            width=80,
            height=20,
            font=("Courier", 9)
        )
        self.output_text.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        main_frame.rowconfigure(row, weight=1)
        row += 1
    
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
    
    def run_planner(self):
        if self.is_running:
            messagebox.showwarning("Uyarı", "Plan oluşturma zaten çalışıyor!")
            return
        
        if not self.excel_path.get():
            messagebox.showerror("Hata", "Lütfen önce bir stok dosyası seçin!")
            return
        
        if not os.path.exists(self.excel_path.get()):
            messagebox.showerror("Hata", "Seçilen dosya bulunamadı!")
            return
        
        self.clear_output()
        self.append_output("Plan oluşturma başlatılıyor...\n\n")
        
        self.is_running = True
        self.run_button.config(state="disabled")
        self.root.config(cursor="watch")
        
        thread = threading.Thread(target=self.run_planner_thread, daemon=True)
        thread.start()
    
    def run_planner_thread(self):
        try:
            result = run_planner(
                excel_path=self.excel_path.get(),
                start_day=self.start_day.get(),
                num_days=self.num_days.get(),
                mode_front=self.mode_front.get(),
                mode_back=self.mode_back.get(),
                on_progress=self.on_progress,
                on_decision=self.on_decision
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
