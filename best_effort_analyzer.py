#!/usr/bin/env python3
"""
Best-Effort Constraint Analyzer for Instagram Post Planner

This module analyzes soft constraints when they cannot be met and computes
explicit relaxation suggestions with estimated candidate counts.

HARD RULES (never relax):
- Cekim filter
- Season filter (Yazlık/Kışlık)
- Post count per day
- Uniqueness rules

SOFT RULES (can relax with user permission):
- FIRST/BACK min total stock
- FIRST/BACK size/stock combinations
- Min/max distinct UrunCinsi per day
- Min/max distinct colors per day
- Min gap days between same KisaKod
- Max weekly FIRST usage per KisaKod
- Daily FIRST "Siyah" limit
- Global FIRST/total stock targets
"""

from typing import List, Dict, Any, Tuple, Optional
import pandas as pd
from copy import deepcopy
from instagram_auto_post import (
    filter_first_products,
    filter_back_products,
    assign_first_products,
    check_per_day_constraints,
)
from product_helpers import is_black_color
from collections import Counter


class BestEffortAnalyzer:
    """Analyzes soft constraints and computes relaxation suggestions"""
    
    def __init__(self, calendar: List[Dict], unique_products: pd.DataFrame, 
                 cfg: Dict, raw_df: pd.DataFrame):
        """
        Initialize analyzer with planning context.
        
        Args:
            calendar: List of post slots
            unique_products: All unique products before filtering
            cfg: Configuration dictionary
            raw_df: Raw stock data
        """
        self.calendar = calendar
        self.unique_products = unique_products
        self.cfg = cfg
        self.raw_df = raw_df
        self.relaxations = []
    
    def analyze_and_suggest_relaxations(self, posts: Optional[List[Dict]] = None) -> Tuple[List[Dict], str]:
        """
        Analyze all soft constraints and compute relaxation suggestions.
        
        Args:
            posts: Current posts (if any were generated)
            
        Returns:
            tuple: (relaxation_suggestions, formatted_message)
            
        Each relaxation suggestion is a dict with:
            - rule_name: str
            - original_value: Any
            - suggested_value: Any
            - estimated_new_candidates: int
            - rule_type: str (e.g., "FIRST_stock", "per_day_constraint")
        """
        suggestions = []
        soft_violations = []
        hard_violations = []
        diagnostics = {}
        
        first_candidates = filter_first_products(self.unique_products, self.cfg)
        required_first = len(self.calendar)
        
        diagnostics["first_pool_size"] = len(first_candidates)
        diagnostics["required_first"] = required_first
        
        if len(first_candidates) < required_first:
            soft_violations.append({
                "rule_name": "FIRST Pool Size",
                "reason": f"Not enough FIRST candidates: {len(first_candidates)} < {required_first}",
                "observed": len(first_candidates),
                "expected": required_first,
                "is_relaxable": True
            })
        
        suggestions.extend(self._analyze_first_min_stock())
        suggestions.extend(self._analyze_first_size_stock_rules())
        
        back_candidates = filter_back_products(self.unique_products, self.cfg)
        required_back = len(self.calendar) * 9
        
        diagnostics["back_pool_size"] = len(back_candidates)
        diagnostics["required_back"] = required_back
        
        if len(back_candidates) < required_back:
            soft_violations.append({
                "rule_name": "BACK Pool Size",
                "reason": f"Not enough BACK candidates: {len(back_candidates)} < {required_back}",
                "observed": len(back_candidates),
                "expected": required_back,
                "is_relaxable": True
            })
        
        suggestions.extend(self._analyze_back_min_stock())
        suggestions.extend(self._analyze_back_size_stock_rules())
        
        if posts:
            suggestions.extend(self._analyze_per_day_constraints(posts))
            suggestions.extend(self._analyze_advanced_first_constraints(posts))
            suggestions.extend(self._analyze_global_stock_targets(posts))
        
        suggestions = [s for s in suggestions if s.get("estimated_new_candidates", 0) > 0]
        
        message = self._format_dialog_message(suggestions)
        
        return {
            "suggestions": suggestions,
            "soft_violations": soft_violations,
            "hard_violations": hard_violations,
            "diagnostics": diagnostics,
            "message": message
        }
    
    def _analyze_first_min_stock(self) -> List[Dict]:
        """Analyze FIRST min total stock constraint"""
        suggestions = []
        min_stock = self.cfg.get("min_total_stock_front", 0)
        
        if min_stock == 0:
            return suggestions
        
        for step in [5, 10, 15, 20]:
            new_threshold = max(0, min_stock - step)
            
            test_cfg = self.cfg.copy()
            test_cfg["min_total_stock_front"] = new_threshold
            new_candidates = filter_first_products(self.unique_products, test_cfg)
            current_candidates = filter_first_products(self.unique_products, self.cfg)
            
            additional = len(new_candidates) - len(current_candidates)
            
            if additional > 0:
                suggestions.append({
                    "rule_name": "FIRST Minimum Toplam Stok",
                    "original_value": min_stock,
                    "suggested_value": new_threshold,
                    "estimated_new_candidates": additional,
                    "rule_type": "FIRST_stock"
                })
                break
        
        return suggestions
    
    def _analyze_back_min_stock(self) -> List[Dict]:
        """Analyze BACK min total stock constraint"""
        suggestions = []
        min_stock = self.cfg.get("min_total_stock_back", 0)
        
        if min_stock == 0:
            return suggestions
        
        for step in [5, 10, 15, 20]:
            new_threshold = max(0, min_stock - step)
            
            test_cfg = self.cfg.copy()
            test_cfg["min_total_stock_back"] = new_threshold
            new_candidates = filter_back_products(self.unique_products, test_cfg)
            current_candidates = filter_back_products(self.unique_products, self.cfg)
            
            additional = len(new_candidates) - len(current_candidates)
            
            if additional > 0:
                suggestions.append({
                    "rule_name": "BACK Minimum Toplam Stok",
                    "original_value": min_stock,
                    "suggested_value": new_threshold,
                    "estimated_new_candidates": additional,
                    "rule_type": "BACK_stock"
                })
                break
        
        return suggestions
    
    def _analyze_first_size_stock_rules(self) -> List[Dict]:
        """Analyze FIRST size/stock rules"""
        suggestions = []
        rules = self.cfg.get("front_size_stock_rules", [])
        
        if not rules:
            return suggestions
        
        for rule in rules:
            if len(rule) == 3:
                size_count, min_sizes_with_stock, min_stock_per_size = rule
                
                if min_stock_per_size > 5:
                    new_min_stock = min_stock_per_size - 5
                    
                    test_cfg = self.cfg.copy()
                    test_rules = [r for r in rules if r != rule]
                    test_rules.append((size_count, min_sizes_with_stock, new_min_stock))
                    test_cfg["front_size_stock_rules"] = test_rules
                    
                    new_candidates = filter_first_products(self.unique_products, test_cfg)
                    current_candidates = filter_first_products(self.unique_products, self.cfg)
                    
                    additional = len(new_candidates) - len(current_candidates)
                    
                    if additional > 0:
                        suggestions.append({
                            "rule_name": f"FIRST Beden/Stok Kuralı ({size_count} beden)",
                            "original_value": f"Y={min_sizes_with_stock}, Z={min_stock_per_size}",
                            "suggested_value": f"Y={min_sizes_with_stock}, Z={new_min_stock}",
                            "estimated_new_candidates": additional,
                            "rule_type": "FIRST_size_stock"
                        })
                        break
        
        return suggestions
    
    def _analyze_back_size_stock_rules(self) -> List[Dict]:
        """Analyze BACK size/stock rules"""
        suggestions = []
        rules = self.cfg.get("back_size_stock_rules", [])
        
        if not rules:
            return suggestions
        
        for rule in rules:
            if len(rule) == 3:
                size_count, min_sizes_with_stock, min_stock_per_size = rule
                
                if min_stock_per_size > 5:
                    new_min_stock = min_stock_per_size - 5
                    
                    test_cfg = self.cfg.copy()
                    test_rules = [r for r in rules if r != rule]
                    test_rules.append((size_count, min_sizes_with_stock, new_min_stock))
                    test_cfg["back_size_stock_rules"] = test_rules
                    
                    new_candidates = filter_back_products(self.unique_products, test_cfg)
                    current_candidates = filter_back_products(self.unique_products, self.cfg)
                    
                    additional = len(new_candidates) - len(current_candidates)
                    
                    if additional > 0:
                        suggestions.append({
                            "rule_name": f"BACK Beden/Stok Kuralı ({size_count} beden)",
                            "original_value": f"Y={min_sizes_with_stock}, Z={min_stock_per_size}",
                            "suggested_value": f"Y={min_sizes_with_stock}, Z={new_min_stock}",
                            "estimated_new_candidates": additional,
                            "rule_type": "BACK_size_stock"
                        })
                        break
        
        return suggestions
    
    def _analyze_per_day_constraints(self, posts: List[Dict]) -> List[Dict]:
        """Analyze per-day constraints (UrunCinsi, colors, etc.)"""
        suggestions = []
        
        posts_by_day = {}
        for p in posts:
            day = p["day_name"]
            if day not in posts_by_day:
                posts_by_day[day] = []
            posts_by_day[day].append(p)
        
        min_distinct_uruncinsi = self.cfg.get("min_distinct_uruncinsi_per_day", 0)
        if min_distinct_uruncinsi > 0:
            violations = []
            for day, day_posts in posts_by_day.items():
                uruncinsi_set = {p["first_product"]["UrunCinsi"] for p in day_posts}
                if len(uruncinsi_set) < min_distinct_uruncinsi:
                    violations.append((day, len(uruncinsi_set)))
            
            if violations:
                min_found = min(count for _, count in violations)
                suggestions.append({
                    "rule_name": "Günlük Minimum Farklı Ürün Cinsi",
                    "original_value": min_distinct_uruncinsi,
                    "suggested_value": min_found,
                    "estimated_new_candidates": len(violations),
                    "rule_type": "per_day_uruncinsi"
                })
        
        min_distinct_colors = self.cfg.get("min_distinct_color_per_day", 0)
        if min_distinct_colors > 0:
            violations = []
            for day, day_posts in posts_by_day.items():
                color_set = {p["first_product"]["Renk"] for p in day_posts}
                if len(color_set) < min_distinct_colors:
                    violations.append((day, len(color_set)))
            
            if violations:
                min_found = min(count for _, count in violations)
                suggestions.append({
                    "rule_name": "Günlük Minimum Farklı Renk",
                    "original_value": min_distinct_colors,
                    "suggested_value": min_found,
                    "estimated_new_candidates": len(violations),
                    "rule_type": "per_day_colors"
                })
        
        min_gap_days = self.cfg.get("same_kisakod_min_gap_days", 0)
        print(f"🔍 DEBUG: same_kisakod_min_gap_days in analyzer = {min_gap_days}")
        if min_gap_days > 0:
            kisakod_days = {}
            for p in posts:
                kisakod = p["first_product"]["KisaKod"]
                day_idx = p.get("day_index", 0)
                if kisakod not in kisakod_days:
                    kisakod_days[kisakod] = []
                kisakod_days[kisakod].append(day_idx)
            
            violations = []
            for kisakod, days in kisakod_days.items():
                if len(days) > 1:
                    days_sorted = sorted(days)
                    for i in range(len(days_sorted) - 1):
                        gap = days_sorted[i + 1] - days_sorted[i]
                        if gap < min_gap_days:
                            violations.append((kisakod, gap))
            
            if violations:
                min_gap_found = min(gap for _, gap in violations)
                conservative_suggestion = max(0, min(min_gap_days - 1, min_gap_found))
                suggestions.append({
                    "rule_name": "Aynı KisaKod Minimum Ara Gün",
                    "original_value": min_gap_days,
                    "suggested_value": conservative_suggestion,
                    "estimated_new_candidates": len(violations),
                    "rule_type": "kisakod_gap"
                })
        
        return suggestions
    
    def _analyze_advanced_first_constraints(self, posts: List[Dict]) -> List[Dict]:
        """Analyze advanced FIRST constraints (black limit, max KisaKod uses)"""
        suggestions = []
        
        max_black_per_day = self.cfg.get("max_black_first_per_day", 0)
        if max_black_per_day > 0:
            posts_by_day = {}
            for p in posts:
                day = p["day_name"]
                if day not in posts_by_day:
                    posts_by_day[day] = []
                posts_by_day[day].append(p)
            
            violations = []
            for day, day_posts in posts_by_day.items():
                black_count = sum(1 for p in day_posts if is_black_color(p["first_product"].get("Renk", "")))
                if black_count > max_black_per_day:
                    violations.append((day, black_count))
            
            if violations:
                max_black_found = max(count for _, count in violations)
                suggestions.append({
                    "rule_name": "Günlük SİYAH FIRST Limiti",
                    "original_value": max_black_per_day,
                    "suggested_value": max_black_found,
                    "estimated_new_candidates": len(violations),
                    "rule_type": "black_limit"
                })
        
        max_kisakod_uses = self.cfg.get("max_first_uses_per_kisakod", 0)
        if max_kisakod_uses > 0:
            kisakod_counts = Counter(p["first_product"]["KisaKod"] for p in posts)
            violations = {k: v for k, v in kisakod_counts.items() if v > max_kisakod_uses}
            
            if violations:
                max_uses_found = max(violations.values())
                suggestions.append({
                    "rule_name": "KisaKod FIRST Kullanım Limiti",
                    "original_value": max_kisakod_uses,
                    "suggested_value": max_uses_found,
                    "estimated_new_candidates": len(violations),
                    "rule_type": "kisakod_uses"
                })
        
        return suggestions
    
    def _analyze_global_stock_targets(self, posts: List[Dict]) -> List[Dict]:
        """Analyze global stock targets"""
        suggestions = []
        
        first_kisakodrenks = {p["first_product"]["kisakodrenk"] for p in posts}
        all_kisakodrenks = first_kisakodrenks.copy()
        for p in posts:
            for bp in p.get("back_products", []):
                all_kisakodrenks.add(bp["kisakodrenk"])
        
        actual_first_stock = sum(
            self.unique_products[self.unique_products["kisakodrenk"] == kr]["total_stock"].iloc[0]
            for kr in first_kisakodrenks
            if len(self.unique_products[self.unique_products["kisakodrenk"] == kr]) > 0
        )
        
        actual_total_stock = sum(
            self.unique_products[self.unique_products["kisakodrenk"] == kr]["total_stock"].iloc[0]
            for kr in all_kisakodrenks
            if len(self.unique_products[self.unique_products["kisakodrenk"] == kr]) > 0
        )
        
        global_min_first = self.cfg.get("global_min_first_stock_sum", 0)
        if global_min_first > 0 and actual_first_stock < global_min_first:
            suggestions.append({
                "rule_name": "Global FIRST Stok Hedefi",
                "original_value": global_min_first,
                "suggested_value": actual_first_stock,
                "estimated_new_candidates": 0,
                "rule_type": "global_first_stock"
            })
        
        global_min_total = self.cfg.get("global_min_total_stock_sum", 0)
        if global_min_total > 0 and actual_total_stock < global_min_total:
            suggestions.append({
                "rule_name": "Global Toplam Stok Hedefi",
                "original_value": global_min_total,
                "suggested_value": actual_total_stock,
                "estimated_new_candidates": 0,
                "rule_type": "global_total_stock"
            })
        
        return suggestions
    
    def _format_dialog_message(self, suggestions: List[Dict]) -> str:
        """Format suggestions into Turkish dialog message"""
        if not suggestions:
            return ""
        
        lines = []
        lines.append("Bu ayarlarla plan oluşturulamıyor.")
        lines.append("")
        lines.append("Aşağıdaki esnetme önerileri ile devam etmek ister misiniz?")
        lines.append("")
        
        for i, sug in enumerate(suggestions, 1):
            lines.append(f"{i}. {sug['rule_name']}")
            lines.append(f"   Mevcut: {sug['original_value']}")
            lines.append(f"   Önerilen: {sug['suggested_value']}")
            if sug['estimated_new_candidates'] > 0:
                lines.append(f"   Tahmini etki: +{sug['estimated_new_candidates']} aday")
            lines.append("")
        
        return "\n".join(lines)
    
    def apply_relaxations(self, suggestions: List[Dict]) -> Dict:
        """
        Apply relaxation suggestions to config and return new config.
        
        Args:
            suggestions: List of relaxation suggestions
            
        Returns:
            dict: New configuration with relaxations applied
        """
        new_cfg = deepcopy(self.cfg)
        
        for sug in suggestions:
            rule_type = sug["rule_type"]
            
            if rule_type == "FIRST_stock":
                new_cfg["min_total_stock_front"] = sug["suggested_value"]
            elif rule_type == "BACK_stock":
                new_cfg["min_total_stock_back"] = sug["suggested_value"]
            elif rule_type == "FIRST_size_stock":
                pass  # Complex logic, skip for now
            elif rule_type == "BACK_size_stock":
                pass  # Complex logic, skip for now
            elif rule_type == "per_day_uruncinsi":
                new_cfg["min_distinct_uruncinsi_per_day"] = sug["suggested_value"]
            elif rule_type == "per_day_colors":
                new_cfg["min_distinct_color_per_day"] = sug["suggested_value"]
            elif rule_type == "kisakod_gap":
                new_cfg["same_kisakod_min_gap_days"] = sug["suggested_value"]
            elif rule_type == "black_limit":
                new_cfg["max_black_first_per_day"] = sug["suggested_value"]
            elif rule_type == "kisakod_uses":
                new_cfg["max_first_uses_per_kisakod"] = sug["suggested_value"]
            elif rule_type == "global_first_stock":
                new_cfg["global_min_first_stock_sum"] = sug["suggested_value"]
            elif rule_type == "global_total_stock":
                new_cfg["global_min_total_stock_sum"] = sug["suggested_value"]
        
        return new_cfg
