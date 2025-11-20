#!/usr/bin/env python3
"""
Instagram Post Planner - Core Business Logic Module

This module contains the refactored planning logic from instagram_auto_post.py.
It can be called from CLI, GUI, or any other interface.

Supports interactive best-effort mode with two-pass flow:
1. Strict pass: Try to generate plan with original config
2. If fails: Show dialog with relaxation suggestions
3. Best-effort pass: Apply relaxations and re-run (if user chooses)
"""

import os
from copy import deepcopy
from typing import Optional, Tuple, List, Dict, Any
from instagram_auto_post import (
    DEFAULT_CFG,
    load_stock_data,
    build_unique_products,
    build_post_calendar,
    filter_first_products,
    filter_back_products,
    run_constraint_analyzer,
    assign_first_products,
    check_advanced_first_constraints,
    check_weekly_nos_dvm,
    assign_back_products,
    export_to_excel,
    export_to_markdown,
    print_summary,
)


def run_planner_with_best_effort(
    excel_path: str,
    start_day: str,
    num_days: int,
    mode_front: str = "Her ikisi",
    mode_back: str = "Her ikisi",
    on_progress=None,
    on_relaxation_choice=None,
    config_override=None,
) -> dict:
    """
    Two-pass planner with interactive best-effort mode.
    
    PASS 1 (Strict): Try to generate plan with original config
    PASS 2 (Best-effort): If fails, show dialog and optionally apply relaxations
    
    Args:
        excel_path: Path to stock Excel file
        start_day: Starting day name in Turkish
        num_days: Number of days to plan (1-7)
        mode_front: Front product seasonal mode
        mode_back: Back product seasonal mode
        on_progress: Callback for progress updates
        on_relaxation_choice: Callback(suggestions, message) -> choice
            Returns: "manual" (user will adjust), "apply" (apply relaxations), "abort" (cancel)
        config_override: Optional config dict
        
    Returns:
        dict with success, summary_text, output files, and relaxations_applied
    """
    
    def emit(msg: str):
        """Helper to print and call on_progress callback"""
        print(msg)
        if on_progress:
            on_progress(msg)
    
    try:
        emit("=" * 70)
        emit("PASS 1: Strict mode - trying with original config")
        emit("=" * 70)
        
        result = run_planner(
            excel_path=excel_path,
            start_day=start_day,
            num_days=num_days,
            mode_front=mode_front,
            mode_back=mode_back,
            on_progress=on_progress,
            on_decision=None,  # No interactive decisions in strict pass
            config_override=config_override,
        )
        
        if result["success"]:
            emit("\n✓ Strict mode succeeded - plan generated without relaxations")
            result["relaxations_applied"] = []
            return result
        
        emit("\n⚠️  Strict mode failed - analyzing constraints...")
        
        if config_override:
            cfg = config_override.copy()
        else:
            cfg = DEFAULT_CFG.copy()
            cfg["stock_excel_path"] = excel_path
            cfg["plan_start_day_name"] = start_day
            cfg["plan_num_days"] = num_days
        
        raw_df = load_stock_data(cfg)
        unique_products = build_unique_products(raw_df)
        calendar = build_post_calendar(cfg)
        
        # Analyze and compute relaxation suggestions
        from best_effort_analyzer import BestEffortAnalyzer
        
        analyzer = BestEffortAnalyzer(calendar, unique_products, cfg, raw_df)
        suggestions, dialog_message = analyzer.analyze_and_suggest_relaxations()
        
        if not suggestions:
            emit("\n❌ No relaxation suggestions available - cannot proceed")
            return {
                "success": False,
                "summary_text": "Plan oluşturulamadı ve esnetme önerisi bulunamadı.",
                "error": "No relaxation suggestions available",
                "relaxations_applied": []
            }
        
        emit(f"\n{dialog_message}")
        
        if on_relaxation_choice:
            choice = on_relaxation_choice(suggestions, dialog_message)
        else:
            print("\nSeçenekler:")
            print("1. Ayarları manuel düzelteceğim (abort)")
            print("2. Best-effort ile devam et (apply)")
            user_input = input("Seçiminiz (1/2): ").strip()
            choice = "apply" if user_input == "2" else "manual"
        
        if choice == "manual" or choice == "abort":
            emit("\n⏸️  Kullanıcı ayarları manuel düzeltmeyi seçti - plan iptal edildi")
            return {
                "success": False,
                "summary_text": "Plan iptal edildi - lütfen ayarları düzeltin ve tekrar deneyin.",
                "error": "User chose to adjust settings manually",
                "relaxations_applied": []
            }
        
        emit("\n" + "=" * 70)
        emit("PASS 2: Best-effort mode - applying relaxations")
        emit("=" * 70)
        
        relaxed_cfg = analyzer.apply_relaxations(suggestions)
        
        result = run_planner(
            excel_path=excel_path,
            start_day=start_day,
            num_days=num_days,
            mode_front=mode_front,
            mode_back=mode_back,
            on_progress=on_progress,
            on_decision=lambda msg: True,  # Auto-accept in best-effort mode
            config_override=relaxed_cfg,
        )
        
        if result["success"]:
            emit("\n✓ Best-effort mode succeeded - plan generated with relaxations")
            result["relaxations_applied"] = suggestions
        else:
            emit("\n❌ Best-effort mode also failed - cannot generate plan")
            result["relaxations_applied"] = suggestions
        
        return result
        
    except Exception as e:
        import traceback
        error_msg = f"Hata oluştu: {str(e)}\n{traceback.format_exc()}"
        emit(error_msg)
        return {
            "success": False,
            "summary_text": error_msg,
            "error": str(e),
            "relaxations_applied": []
        }


def run_planner(
    excel_path: str,
    start_day: str,
    num_days: int,
    mode_front: str = "Her ikisi",
    mode_back: str = "Her ikisi",
    on_progress=None,
    on_decision=None,
    config_override=None,
    relaxations_applied=None,
) -> dict:
    """
    Runs the Instagram post planning logic and returns a summary dict.
    
    Args:
        excel_path: Path to the stock Excel file (stokdosya.xlsx)
        start_day: Starting day name in Turkish (e.g., "Pazartesi")
        num_days: Number of days to plan (1-7)
        mode_front: Front product seasonal mode: "Yazlık", "Kışlık", or "Her ikisi"
        mode_back: Back product seasonal mode: "Yazlık", "Kışlık", or "Her ikisi"
        on_progress: Optional callback function(message: str) for progress updates
        on_decision: Optional callback function(message: str) -> bool for user decisions
        config_override: Optional dict to override default config (for comprehensive GUI)
    
    Returns:
        dict with keys:
            - success: bool (True if plan was created successfully)
            - summary_text: str (summary of the plan or error message)
            - output_excel: str (path to Excel output file, if success)
            - output_md: str (path to Markdown output file, if success)
            - error: str (error message, if not success)
    """
    
    def emit(msg: str):
        """Helper to print and call on_progress callback"""
        print(msg)
        if on_progress:
            on_progress(msg)
    
    def decide(msg: str) -> bool:
        """Helper to handle decision prompts"""
        if on_decision:
            return on_decision(msg)
        from instagram_auto_post import ask_best_effort_or_abort
        return ask_best_effort_or_abort(msg)
    
    try:
        emit("=" * 70)
        emit("INSTAGRAM WEEKLY POST PLANNER")
        emit("=" * 70)
        
        if config_override:
            cfg = config_override.copy()
        else:
            cfg = DEFAULT_CFG.copy()
            cfg["stock_excel_path"] = excel_path
            cfg["plan_start_day_name"] = start_day
            cfg["plan_num_days"] = num_days
            
            if mode_front == "Yazlık":
                cfg["use_yazlik_front"] = True
                cfg["use_kislik_front"] = False
            elif mode_front == "Kışlık":
                cfg["use_yazlik_front"] = False
                cfg["use_kislik_front"] = True
            else:
                cfg["use_yazlik_front"] = True
                cfg["use_kislik_front"] = True
            
            if mode_back == "Yazlık":
                cfg["use_yazlik_back"] = True
                cfg["use_kislik_back"] = False
            elif mode_back == "Kışlık":
                cfg["use_yazlik_back"] = False
                cfg["use_kislik_back"] = True
            else:
                cfg["use_yazlik_back"] = True
                cfg["use_kislik_back"] = True
        
        emit(f"\nPlan: {start_day} başlangıçlı, {num_days} günlük olarak ayarlandı.")
        if not config_override:
            emit(f"Front mod: {mode_front}, Back mod: {mode_back}\n")
        
        emit("Stok verisi yükleniyor...")
        raw_df = load_stock_data(cfg)
        
        emit("Unique ürünler oluşturuluyor...")
        unique_products = build_unique_products(raw_df)
        
        emit("Takvim oluşturuluyor...")
        calendar = build_post_calendar(cfg)
        
        emit("FIRST ürün havuzu filtreleniyor...")
        first_candidates = filter_first_products(unique_products, cfg)
        
        emit("BACK ürün havuzu filtreleniyor...")
        back_candidates = filter_back_products(unique_products, cfg)
        
        emit("Kısıt analizi yapılıyor...")
        if not run_constraint_analyzer(calendar, first_candidates, back_candidates, cfg, unique_products, decide=decide):
            return {
                "success": False,
                "summary_text": "Plan üretimi iptal edildi (kısıt analizi başarısız).",
                "error": "Constraint analysis failed or user aborted"
            }
        
        emit("FIRST ürünler atanıyor...")
        posts = assign_first_products(calendar, first_candidates, cfg, decide=decide)
        if not posts:
            return {
                "success": False,
                "summary_text": "Hiç FIRST ürün atanamadı, plan oluşturulamadı.",
                "error": "No FIRST products could be assigned"
            }
        
        emit("Gelişmiş FIRST kuralları kontrol ediliyor...")
        if not check_advanced_first_constraints(posts, cfg, decide=decide):
            return {
                "success": False,
                "summary_text": "Plan üretimi iptal edildi (Gelişmiş FIRST kuralları karşılanamadı).",
                "error": "Advanced FIRST constraints not met or user aborted"
            }
        
        emit("NOS/DVM kontrolü yapılıyor...")
        if not check_weekly_nos_dvm(posts, cfg, first_candidates, calendar, back_candidates, unique_products, decide=decide):
            return {
                "success": False,
                "summary_text": "Plan üretimi iptal edildi (NOS/DVM kuralları karşılanamadı).",
                "error": "NOS/DVM requirements not met or user aborted"
            }
        
        emit("BACK ürünler atanıyor...")
        posts = assign_back_products(posts, back_candidates, cfg)
        
        emit("Plan doğrulaması yapılıyor...")
        try:
            from validator import validate_plan
            validation_results, validation_summary, validation_df = validate_plan(
                posts, cfg, first_candidates, back_candidates
            )
            emit(validation_summary)
        except Exception as e:
            emit(f"Uyarı: Doğrulama sırasında hata: {e}")
            validation_df = None
        
        emit("Excel çıktısı oluşturuluyor...")
        output_dir = os.path.dirname(os.path.abspath(excel_path))
        output_excel = os.path.join(output_dir, "instagram_haftalik_plan.xlsx")
        output_md = os.path.join(output_dir, "instagram_haftalik_plan.md")
        
        plan_df = export_to_excel(posts, cfg, raw_df, validation_df, relaxations_applied)
        
        emit("Markdown çıktısı oluşturuluyor...")
        export_to_markdown(posts, cfg)
        
        summary_lines = []
        summary_lines.append("=" * 70)
        summary_lines.append("PLAN ÖZETİ")
        summary_lines.append("=" * 70)
        
        from collections import Counter
        from instagram_auto_post import TURKISH_DAYS
        
        day_counts = Counter(p["day_name"] for p in posts)
        summary_lines.append("\nGünlük post adetleri:")
        for day in TURKISH_DAYS:
            if day in day_counts:
                summary_lines.append(f"  {day}: {day_counts[day]}")
        
        summary_lines.append(f"\nToplam post sayısı: {len(posts)}")
        
        distinct_first = len({p["first_product"]["kisakodrenk"] for p in posts})
        distinct_back = set()
        for p in posts:
            for bp in p.get("back_products", []):
                distinct_back.add(bp["kisakodrenk"])
        summary_lines.append(f"\nDistinct FIRST ürün adedi: {distinct_first}")
        summary_lines.append(f"Distinct BACK ürün adedi:  {len(distinct_back)}")
        
        nos_first_plan = {
            p["first_product"]["kisakodrenk"]
            for p in posts
            if p["first_product"].get("Nos", "") == "E"
        }
        dvm_first_plan = {
            p["first_product"]["kisakodrenk"]
            for p in posts
            if p["first_product"].get("DVM", "") == "DVM"
        }
        
        summary_lines.append(f"\nPlan içindeki NOS='E' FIRST (distinct): {len(nos_first_plan)} (hedef: {cfg['min_nos_front']})")
        summary_lines.append(f"Plan içindeki DVM='DVM' FIRST (distinct): {len(dvm_first_plan)} (hedef: {cfg['min_dvm_front']})")
        
        summary_lines.append("\n" + "=" * 70)
        summary_lines.append("\n✓ Plan oluşturma tamamlandı!")
        summary_lines.append(f"\nÇıktı dosyaları:")
        summary_lines.append(f"  Excel: {output_excel}")
        summary_lines.append(f"  Markdown: {output_md}")
        
        summary_text = "\n".join(summary_lines)
        emit(summary_text)
        
        return {
            "success": True,
            "summary_text": summary_text,
            "output_excel": output_excel,
            "output_md": output_md,
        }
        
    except Exception as e:
        import traceback
        error_msg = f"Hata oluştu: {str(e)}\n{traceback.format_exc()}"
        emit(error_msg)
        return {
            "success": False,
            "summary_text": error_msg,
            "error": str(e)
        }


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Kullanım: python planner.py <excel_path> [start_day] [num_days] [mode_front] [mode_back]")
        sys.exit(1)
    
    excel_path = sys.argv[1]
    start_day = sys.argv[2] if len(sys.argv) > 2 else "Pazartesi"
    num_days = int(sys.argv[3]) if len(sys.argv) > 3 else 7
    mode_front = sys.argv[4] if len(sys.argv) > 4 else "Her ikisi"
    mode_back = sys.argv[5] if len(sys.argv) > 5 else "Her ikisi"
    
    result = run_planner(excel_path, start_day, num_days, mode_front, mode_back)
    
    if not result["success"]:
        sys.exit(1)
