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
        
        if config_override:
            min_gap_value = config_override.get("same_kisakod_min_gap_days", "NOT_SET")
            emit(f"🔍 DEBUG: same_kisakod_min_gap_days at strict pass start = {min_gap_value}")
        
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
        
        emit(f"\n🔍 Prioritization config:")
        emit(f"   prioritize_by_newness = {cfg.get('prioritize_by_newness', False)}")
        emit(f"   prioritize_by_stock = {cfg.get('prioritize_by_stock', False)}")
        
        preferred_products = cfg.get("preferred_first_products", [])
        emit(f"\n📋 Preferred FIRST products loaded: {len(preferred_products)} items")
        if preferred_products:
            for i, pref in enumerate(preferred_products[:5], 1):
                kisakodrenk = pref.get("kisakodrenk", "")
                gun = pref.get("gun", "")
                time = pref.get("time", "")
                emit(f"   {i}. {kisakodrenk} - {gun} {time if time else '(herhangi bir saat)'}")
            if len(preferred_products) > 5:
                emit(f"   ... ve {len(preferred_products) - 5} daha")
        
        # Analyze and compute relaxation suggestions (Two-phase approach)
        from best_effort_analyzer import BestEffortAnalyzer
        
        analyzer = BestEffortAnalyzer(calendar, unique_products, cfg, raw_df)
        
        emit("\n📊 Phase 1: Analyzing pool-based constraints...")
        phase1_result = analyzer.analyze_and_suggest_relaxations(posts=None)
        
        emit("\n📊 Phase 2: Running trial assignment to analyze assignment-based constraints...")
        phase2_suggestions = []
        missing_first = 0
        missing_back = 0
        prioritization_is_blocking = False
        try:
            first_candidates = filter_first_products(unique_products, cfg)
            trial_posts = assign_first_products(calendar, first_candidates, cfg, decide=lambda msg: True)
            
            if trial_posts:
                back_candidates = filter_back_products(unique_products, cfg)
                trial_posts = assign_back_products(trial_posts, back_candidates, cfg)
                
                phase2_result = analyzer.analyze_and_suggest_relaxations(posts=trial_posts)
                phase2_suggestions = phase2_result["suggestions"]
                emit(f"   Trial assignment produced {len(trial_posts)} posts for analysis")
                
                required_first = len(calendar)
                placed_first = sum(1 for p in trial_posts if p.get("first_product"))
                missing_first = max(0, required_first - placed_first)
                
                required_back_per_post = 9
                required_back = len(calendar) * required_back_per_post
                placed_back = sum(len(p.get("back_products", [])) for p in trial_posts)
                missing_back = max(0, required_back - placed_back)
                
                emit(f"   Trial counts: {placed_first}/{required_first} FIRST, {placed_back}/{required_back} BACK")
                
                from instagram_auto_post import check_advanced_first_constraints
                constraints_pass = True
                try:
                    constraints_pass = check_advanced_first_constraints(trial_posts, cfg, decide=lambda msg: True)
                except Exception as e:
                    emit(f"   ⚠️  Advanced constraint check failed: {e}")
                    constraints_pass = False
                
                if missing_first == 0 and missing_back == 0 and not constraints_pass and cfg.get("prioritize_by_newness") and not cfg.get("prioritize_by_stock"):
                    emit(f"\n🔍 Detecting prioritization blocking: missing_first=0, missing_back=0, but advanced constraints failed")
                    emit(f"   Current: prioritize_by_newness=True, prioritize_by_stock=False (recency only)")
                    emit(f"   Suggestion: Enable stock as secondary priority to reduce constraint conflicts")
                    prioritization_is_blocking = True
                
                if not constraints_pass:
                    emit(f"   ⚠️  Trial posts violate advanced constraints (max black per day, max KisaKod uses)")
                    emit(f"   Note: Counts show 0/0 but advanced constraints block placement")
                    emit(f"   Actual counts: missing_first={missing_first}, missing_back={missing_back}")
            else:
                emit(f"   Trial assignment returned empty - using realistic fallback counts")
                missing_first = len(calendar)
                missing_back = len(calendar) * 9
        except Exception as e:
            emit(f"   Trial assignment failed: {e}")
            emit(f"   Using fallback counts (may be inaccurate)")
            missing_first = len(calendar)
            missing_back = len(calendar) * 9
        
        if preferred_products and trial_posts:
            emit(f"\n📋 Preferred FIRST products placement check:")
            all_stock_kisakodrenk = set(unique_products["kisakodrenk"].str.upper())
            first_pool_kisakodrenk = set(first_candidates["kisakodrenk"].str.upper())
            placed_kisakodrenk = set(p["first_product"]["kisakodrenk"].upper() for p in trial_posts if p.get("first_product"))
            
            for i, pref in enumerate(preferred_products, 1):
                kisakodrenk = pref.get("kisakodrenk", "").strip().upper()
                if not kisakodrenk:
                    continue
                
                if kisakodrenk not in all_stock_kisakodrenk:
                    emit(f"   ❌ {i}. {kisakodrenk}: Stok dosyasında bulunamadı")
                elif kisakodrenk not in first_pool_kisakodrenk:
                    emit(f"   ⚠️  {i}. {kisakodrenk}: FIRST havuzuna giremedi (sezon/çekim/stok filtreleri)")
                elif kisakodrenk in placed_kisakodrenk:
                    emit(f"   ✓ {i}. {kisakodrenk}: Plana atandı")
                else:
                    emit(f"   ⚠️  {i}. {kisakodrenk}: Havuzda ama atama aşamasında yer bulamadı (günlük kısıtlar)")
        
        all_suggestions = phase1_result["suggestions"] + phase2_suggestions
        seen_rules = {}
        for sug in all_suggestions:
            rule_type = sug["rule_type"]
            rule_name = sug.get("rule_name", rule_type)
            key = (rule_type, rule_name)
            if key not in seen_rules:
                seen_rules[key] = sug
            else:
                existing = seen_rules[key]
                if sug.get("estimated_new_candidates", 0) > existing.get("estimated_new_candidates", 0):
                    seen_rules[key] = sug
        
        suggestions = list(seen_rules.values())
        
        if prioritization_is_blocking:
            priority_suggestion = {
                "rule_type": "PRIORITY_mode",
                "original_value": "Yalnızca yeniliğe göre",
                "suggested_value": "Yenilik + stok (ikincil öncelik)",
                "estimated_new_candidates": 9999,
                "note": "Atama kısıtlarıyla çakışmaları azaltır (yüksek etki)",
                "preselected": True
            }
            suggestions.append(priority_suggestion)
            emit(f"\n⚠️  Added PRIORITY_mode suggestion: Enable stock as secondary priority")
        
        for sug in suggestions:
            if sug["rule_type"] in ["FIRST_stock", "FIRST_size_stock"] and missing_first == 0:
                sug["estimated_new_candidates"] = 0
                original_note = sug.get("note", "")
                if original_note:
                    sug["note"] = f"{original_note} (düşük etki - FIRST slotları zaten dolu)"
                else:
                    sug["note"] = "(düşük etki - FIRST slotları zaten dolu)"
        
        suggestions.sort(key=lambda s: s.get("estimated_new_candidates", 0), reverse=True)
        
        result = phase1_result
        result["suggestions"] = suggestions
        soft_violations = result["soft_violations"]
        hard_violations = result["hard_violations"]
        diagnostics = result["diagnostics"]
        dialog_message = result["message"]
        
        emit("\n📋 Constraint Diagnostics:")
        emit(f"   FIRST pool: {diagnostics.get('first_pool_size', 0)} candidates (need {diagnostics.get('required_first', 0)})")
        emit(f"   BACK pool: {diagnostics.get('back_pool_size', 0)} candidates (need {diagnostics.get('required_back', 0)})")
        emit(f"   Soft violations: {len(soft_violations)}")
        emit(f"   Hard violations: {len(hard_violations)}")
        emit(f"   Relaxation suggestions: {len(suggestions)}")
        
        if not suggestions and hard_violations:
            hard_rules_list = "\n".join([f"  - {v['rule_name']}: {v['reason']}" for v in hard_violations])
            error_msg = f"Plan oluşturulamadı - sadece esnetilemez (hard) kurallar ihlal edildi:\n\n{hard_rules_list}\n\nBu kurallar esnetilemiyor. Lütfen ayarları manuel olarak düzeltin."
            emit(f"\n❌ {error_msg}")
            return {
                "success": False,
                "summary_text": error_msg,
                "error": "Only hard rules violated",
                "relaxations_applied": []
            }
        
        if not suggestions and soft_violations:
            soft_rules_list = "\n".join([f"  - {v['rule_name']}: {v['reason']}" for v in soft_violations])
            error_msg = f"Plan oluşturulamadı - esnetilebilir kurallar ihlal edildi ancak öneri üretilemedi:\n\n{soft_rules_list}\n\nLütfen ayarları manuel olarak düzeltin."
            emit(f"\n⚠️ {error_msg}")
            return {
                "success": False,
                "summary_text": error_msg,
                "error": "Soft rules violated but no suggestions",
                "relaxations_applied": []
            }
        
        if not suggestions:
            emit("\n❌ Plan oluşturulamadı ancak ihlal edilen kural tespit edilemedi")
            return {
                "success": False,
                "summary_text": "Plan oluşturulamadı ve esnetme önerisi bulunamadı.",
                "error": "No relaxation suggestions available",
                "relaxations_applied": []
            }
        
        emit(f"\n{dialog_message}")
        
        emit(f"\n🔍 Dialog path: INITIAL (first attempt)")
        emit(f"   Suggestions count: {len(suggestions)}")
        emit(f"   Actual counts: missing_first={missing_first}, missing_back={missing_back}")
        
        if on_relaxation_choice:
            choice, selected_suggestions = on_relaxation_choice(suggestions, dialog_message, missing_first, missing_back)
        else:
            print("\nSeçenekler:")
            print("1. Ayarları manuel düzelteceğim (abort)")
            print("2. Best-effort ile devam et (apply)")
            user_input = input("Seçiminiz (1/2): ").strip()
            choice = "apply" if user_input == "2" else "manual"
            selected_suggestions = suggestions
        
        if choice == "manual" or choice == "abort":
            emit("\n⏸️  Kullanıcı ayarları manuel düzeltmeyi seçti - plan iptal edildi")
            return {
                "success": False,
                "summary_text": "Plan iptal edildi - lütfen ayarları düzeltin ve tekrar deneyin.",
                "error": "User chose to adjust settings manually",
                "relaxations_applied": []
            }
        
        if choice == "retry_strict":
            emit("\n" + "=" * 70)
            emit("Retry: Applying selected relaxations and retrying strict mode")
            emit("=" * 70)
            
            max_retries = 3
            retry_count = 0
            previous_cfg = cfg.copy()
            previous_suggestions_signature = None
            
            while retry_count < max_retries:
                retry_count += 1
                emit(f"\n🔄 Retry attempt {retry_count}/{max_retries}")
                
                relaxed_cfg = analyzer.apply_relaxations(selected_suggestions)
                
                if relaxed_cfg == previous_cfg:
                    emit("\n⚠️  Selected relaxations produced no config changes - stopping retry loop")
                    return {
                        "success": False,
                        "summary_text": "Seçili esnetmeler yapılandırmayı değiştirmedi. Lütfen farklı kurallar seçin veya ayarları manuel düzeltin.",
                        "error": "No config changes from selected relaxations",
                        "relaxations_applied": selected_suggestions
                    }
                
                previous_cfg = relaxed_cfg.copy()
                
                result = run_planner(
                    excel_path=excel_path,
                    start_day=start_day,
                    num_days=num_days,
                    mode_front=mode_front,
                    mode_back=mode_back,
                    on_progress=on_progress,
                    on_decision=None,
                    config_override=relaxed_cfg,
                )
                
                if result["success"]:
                    emit(f"\n✓ Retry succeeded after {retry_count} attempt(s)")
                    result["relaxations_applied"] = selected_suggestions
                    return result
                
                emit(f"\n⚠️  Retry attempt {retry_count} failed - analyzing again...")
                
                analyzer_retry = BestEffortAnalyzer(calendar, unique_products, relaxed_cfg, raw_df)
                phase1_retry = analyzer_retry.analyze_and_suggest_relaxations(posts=None)
                
                try:
                    first_candidates_retry = filter_first_products(unique_products, relaxed_cfg)
                    trial_posts_retry = assign_first_products(calendar, first_candidates_retry, relaxed_cfg, decide=lambda msg: True)
                    
                    if trial_posts_retry:
                        back_candidates_retry = filter_back_products(unique_products, relaxed_cfg)
                        trial_posts_retry = assign_back_products(trial_posts_retry, back_candidates_retry, relaxed_cfg)
                        
                        phase2_retry = analyzer_retry.analyze_and_suggest_relaxations(posts=trial_posts_retry)
                        phase2_suggestions_retry = phase2_retry["suggestions"]
                        
                        required_first_retry = len(calendar)
                        placed_first_retry = sum(1 for p in trial_posts_retry if p.get("first_product"))
                        missing_first = max(0, required_first_retry - placed_first_retry)
                        
                        required_back_retry = len(calendar) * 9
                        placed_back_retry = sum(len(p.get("back_products", [])) for p in trial_posts_retry)
                        missing_back = max(0, required_back_retry - placed_back_retry)
                    else:
                        emit(f"   Trial assignment returned empty - using realistic fallback counts")
                        phase2_suggestions_retry = []
                        missing_first = len(calendar)
                        missing_back = len(calendar) * 9
                except Exception as e:
                    emit(f"   Trial assignment failed: {e}")
                    emit(f"   Using fallback counts (may be inaccurate)")
                    phase2_suggestions_retry = []
                    missing_first = len(calendar)
                    missing_back = len(calendar) * 9
                
                all_suggestions_retry = phase1_retry["suggestions"] + phase2_suggestions_retry
                seen_rules_retry = {}
                for sug in all_suggestions_retry:
                    rule_type = sug["rule_type"]
                    rule_name = sug.get("rule_name", rule_type)
                    key = (rule_type, rule_name)
                    if key not in seen_rules_retry:
                        seen_rules_retry[key] = sug
                    else:
                        existing = seen_rules_retry[key]
                        if sug.get("estimated_new_candidates", 0) > existing.get("estimated_new_candidates", 0):
                            seen_rules_retry[key] = sug
                
                suggestions_retry = list(seen_rules_retry.values())
                suggestions_retry.sort(key=lambda s: s.get("estimated_new_candidates", 0), reverse=True)
                
                if not suggestions_retry:
                    emit("\n❌ No more relaxation suggestions available")
                    return {
                        "success": False,
                        "summary_text": "Esnetmeler uygulandı ancak plan hala oluşturulamadı ve daha fazla öneri yok.",
                        "error": "No more suggestions after retry",
                        "relaxations_applied": selected_suggestions
                    }
                
                current_suggestions_signature = tuple(sorted([
                    (s["rule_type"], s.get("rule_name", s["rule_type"]), s.get("suggested_value", ""))
                    for s in suggestions_retry
                ]))
                
                if previous_suggestions_signature is not None and current_suggestions_signature == previous_suggestions_signature:
                    emit("\n⚠️  Suggestions unchanged from previous iteration - stopping retry loop")
                    emit(f"   Suggestions signature: {len(current_suggestions_signature)} rules")
                    return {
                        "success": False,
                        "summary_text": "Öneriler değişmedi. Daha fazla esnetme mümkün değil. Lütfen ayarları manuel düzeltin.",
                        "error": "Suggestions unchanged - no convergence",
                        "relaxations_applied": selected_suggestions
                    }
                
                total_estimated = sum(s.get("estimated_new_candidates", 0) for s in suggestions_retry)
                emit(f"   Total estimated impact: {total_estimated} new candidates")
                
                if total_estimated == 0:
                    emit("\n⚠️  All suggestions have zero estimated impact - stopping retry loop")
                    return {
                        "success": False,
                        "summary_text": "Tüm önerilerin tahmini etkisi sıfır. Daha fazla esnetme fayda sağlamayacak. Lütfen ayarları manuel düzeltin.",
                        "error": "Zero estimated impact - no benefit from relaxations",
                        "relaxations_applied": selected_suggestions
                    }
                
                previous_suggestions_signature = current_suggestions_signature
                
                emit(f"\n🔍 Dialog path: RETRY (attempt {retry_count})")
                emit(f"   Suggestions count: {len(suggestions_retry)}")
                emit(f"   Actual counts: missing_first={missing_first}, missing_back={missing_back}")
                
                if on_relaxation_choice:
                    choice, selected_suggestions = on_relaxation_choice(suggestions_retry, "", missing_first, missing_back)
                    
                    if choice == "manual" or choice == "abort":
                        emit("\n⏸️  Kullanıcı ayarları manuel düzeltmeyi seçti")
                        return {
                            "success": False,
                            "summary_text": "Plan iptal edildi - lütfen ayarları düzeltin ve tekrar deneyin.",
                            "error": "User chose to adjust settings manually",
                            "relaxations_applied": selected_suggestions
                        }
                    
                    if choice == "continue_best":
                        break
                else:
                    break
            
            if retry_count >= max_retries:
                emit(f"\n❌ Maximum retries ({max_retries}) reached without success")
                return {
                    "success": False,
                    "summary_text": f"Maksimum deneme sayısına ({max_retries}) ulaşıldı. Plan oluşturulamadı.",
                    "error": "Max retries reached",
                    "relaxations_applied": selected_suggestions
                }
        
        emit("\n" + "=" * 70)
        emit("PASS 2: Best-effort mode - applying selected relaxations")
        emit("=" * 70)
        
        relaxed_cfg = analyzer.apply_relaxations(selected_suggestions)
        
        result = run_planner(
            excel_path=excel_path,
            start_day=start_day,
            num_days=num_days,
            mode_front=mode_front,
            mode_back=mode_back,
            on_progress=on_progress,
            on_decision=lambda msg: True,
            config_override=relaxed_cfg,
        )
        
        if result["success"]:
            emit("\n✓ Best-effort mode succeeded - plan generated with relaxations")
            result["relaxations_applied"] = selected_suggestions
        else:
            emit("\n❌ Best-effort mode also failed - cannot generate plan")
            result["relaxations_applied"] = selected_suggestions
        
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
        
        preferred_products = cfg.get("preferred_first_products", [])
        emit(f"\n📋 Preferred FIRST products loaded: {len(preferred_products)} items")
        if preferred_products:
            for i, pref in enumerate(preferred_products[:5], 1):
                kisakodrenk = pref.get("kisakodrenk", "")
                gun = pref.get("gun", "")
                time = pref.get("time", "")
                emit(f"   {i}. {kisakodrenk} - {gun} {time if time else '(herhangi bir saat)'}")
            if len(preferred_products) > 5:
                emit(f"   ... ve {len(preferred_products) - 5} daha")
        
        if config_override and "preferred_first_products" in config_override:
            from config import PlanConfig
            temp_config = PlanConfig(**config_override)
            pref_errors = temp_config.validate_preferred_products_advanced(calendar)
            if pref_errors:
                error_msg = "Tercihli FIRST ürün doğrulama hataları:\n" + "\n".join(pref_errors)
                emit(error_msg)
                return {
                    "success": False,
                    "summary_text": error_msg,
                    "error": "Preferred FIRST products validation failed"
                }
        
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
        
        if preferred_products:
            emit(f"\n📋 Preferred FIRST products placement check:")
            all_stock_kisakodrenk = set(unique_products["kisakodrenk"].str.upper())
            first_pool_kisakodrenk = set(first_candidates["kisakodrenk"].str.upper())
            placed_kisakodrenk = set(p["first_product"]["kisakodrenk"].upper() for p in posts if p.get("first_product"))
            
            for i, pref in enumerate(preferred_products, 1):
                kisakodrenk = pref.get("kisakodrenk", "").strip().upper()
                if not kisakodrenk:
                    continue
                
                if kisakodrenk not in all_stock_kisakodrenk:
                    emit(f"   ❌ {i}. {kisakodrenk}: Stok dosyasında bulunamadı")
                elif kisakodrenk not in first_pool_kisakodrenk:
                    emit(f"   ⚠️  {i}. {kisakodrenk}: FIRST havuzuna giremedi (sezon/çekim/stok filtreleri)")
                elif kisakodrenk in placed_kisakodrenk:
                    emit(f"   ✓ {i}. {kisakodrenk}: Plana atandı")
                else:
                    emit(f"   ⚠️  {i}. {kisakodrenk}: Havuzda ama atama aşamasında yer bulamadı (günlük kısıtlar)")
            emit("")
        
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
