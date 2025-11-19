#!/usr/bin/env python3
"""
Constraint Analyzer Module for Instagram Post Planner

This module analyzes constraints when they cannot be met and suggests
relaxations to help the user understand what adjustments might help.
"""

from typing import List, Dict, Any, Tuple
import pandas as pd


class ConstraintAnalyzer:
    """Analyzes constraints and suggests relaxations"""
    
    def __init__(self, calendar: List[Dict], first_candidates: pd.DataFrame, 
                 back_candidates: pd.DataFrame, cfg: Dict, unique_products: pd.DataFrame):
        """
        Initialize analyzer with planning context.
        
        Args:
            calendar: List of post slots
            first_candidates: Current FIRST product candidates
            back_candidates: Current BACK product candidates
            cfg: Configuration dictionary
            unique_products: All unique products before filtering
        """
        self.calendar = calendar
        self.first_candidates = first_candidates
        self.back_candidates = back_candidates
        self.cfg = cfg
        self.unique_products = unique_products
        self.violations = []
        self.suggestions = []
    
    def analyze_first_pool_size(self) -> Tuple[List[str], List[str]]:
        """
        Analyze FIRST product pool and suggest relaxations if too small.
        
        Returns:
            tuple: (violations, suggestions)
        """
        violations = []
        suggestions = []
        
        required_posts = len(self.calendar)
        available_first = len(self.first_candidates)
        
        if available_first < required_posts:
            violations.append(
                f"FIRST ürün havuzu yetersiz: {available_first} aday var, {required_posts} post gerekli"
            )
            
            self._analyze_stock_constraint("FIRST", suggestions)
            self._analyze_one_atilma_constraint(suggestions)
            self._analyze_size_stock_constraint("FIRST", suggestions)
        
        return violations, suggestions
    
    def analyze_back_pool_size(self) -> Tuple[List[str], List[str]]:
        """
        Analyze BACK product pool and suggest relaxations if too small.
        
        Returns:
            tuple: (violations, suggestions)
        """
        violations = []
        suggestions = []
        
        required_back = len(self.calendar) * 9
        available_back = len(self.back_candidates)
        
        if available_back < required_back:
            violations.append(
                f"BACK ürün havuzu yetersiz: {available_back} aday var, ~{required_back} gerekli"
            )
            
            self._analyze_stock_constraint("BACK", suggestions)
            self._analyze_size_stock_constraint("BACK", suggestions)
        
        return violations, suggestions
    
    def analyze_nos_dvm_requirements(self, posts: List[Dict]) -> Tuple[List[str], List[str]]:
        """
        Analyze NOS/DVM requirements.
        
        Args:
            posts: Current posts with FIRST products assigned
            
        Returns:
            tuple: (violations, suggestions)
        """
        violations = []
        suggestions = []
        
        nos_first_plan = {
            p["first_product"]["kisakodrenk"]
            for p in posts
            if str(p["first_product"].get("Nos", "")).upper() == "E"
        }
        dvm_first_plan = {
            p["first_product"]["kisakodrenk"]
            for p in posts
            if str(p["first_product"].get("DVM", "")).upper() == "DVM"
        }
        
        min_nos = self.cfg.get("min_nos_front", 0)
        min_dvm = self.cfg.get("min_dvm_front", 0)
        
        if len(nos_first_plan) < min_nos:
            violations.append(
                f"NOS hedefi karşılanamadı: {len(nos_first_plan)} < {min_nos}"
            )
            
            nos_pool = sum(1 for _, r in self.first_candidates.iterrows() 
                          if str(r.get("Nos", "")).upper() == "E")
            
            if nos_pool < min_nos:
                suggestions.append(
                    f"NOS hedefini {min_nos} → {nos_pool} düşürürseniz, mevcut havuzla karşılanabilir"
                )
            else:
                suggestions.append(
                    f"Havuzda {nos_pool} NOS ürün var ama atama sırasında kullanılamadı. "
                    "Diğer kısıtları gevşeterek daha fazla NOS ürün kullanılabilir"
                )
        
        if len(dvm_first_plan) < min_dvm:
            violations.append(
                f"DVM hedefi karşılanamadı: {len(dvm_first_plan)} < {min_dvm}"
            )
            
            dvm_pool = sum(1 for _, r in self.first_candidates.iterrows() 
                          if str(r.get("DVM", "")).upper() == "DVM")
            
            if dvm_pool < min_dvm:
                suggestions.append(
                    f"DVM hedefini {min_dvm} → {dvm_pool} düşürürseniz, mevcut havuzla karşılanabilir"
                )
            else:
                suggestions.append(
                    f"Havuzda {dvm_pool} DVM ürün var ama atama sırasında kullanılamadı. "
                    "Diğer kısıtları gevşeterek daha fazla DVM ürün kullanılabilir"
                )
        
        return violations, suggestions
    
    def _analyze_stock_constraint(self, product_type: str, suggestions: List[str]):
        """Analyze minimum stock constraint and suggest relaxation"""
        if product_type == "FIRST":
            min_stock = self.cfg.get("min_total_stock_front", 0)
            candidates = self.first_candidates
        else:
            min_stock = self.cfg.get("min_total_stock_back", 0)
            candidates = self.back_candidates
        
        if min_stock == 0:
            return
        
        all_products = self.unique_products
        
        filtered = all_products.copy()
        
        for new_threshold in [min_stock - 5, min_stock - 10, min_stock - 15]:
            if new_threshold < 0:
                continue
            
            additional = len(filtered[
                (filtered["total_stock"] >= new_threshold) & 
                (filtered["total_stock"] < min_stock)
            ])
            
            if additional > 0:
                suggestions.append(
                    f"{product_type} minimum stok {min_stock} → {new_threshold} düşürülürse, "
                    f"+{additional} ürün daha kullanılabilir"
                )
                break
    
    def _analyze_one_atilma_constraint(self, suggestions: List[str]):
        """Analyze One Atilma Tarihi constraint and suggest relaxation"""
        min_days = self.cfg.get("one_atilma_min_days", 0)
        
        if min_days == 0:
            return
        
        for new_days in [min_days - 15, min_days - 30]:
            if new_days < 0:
                continue
            
            suggestions.append(
                f"One Atilma Tarihi minimum gün sayısı {min_days} → {new_days} düşürülürse, "
                f"daha fazla ürün kullanılabilir"
            )
            break
    
    def _analyze_size_stock_constraint(self, product_type: str, suggestions: List[str]):
        """Analyze size/stock rules and suggest relaxation"""
        if product_type == "FIRST":
            rules = self.cfg.get("front_size_stock_rules", [])
        else:
            rules = self.cfg.get("back_size_stock_rules", [])
        
        if not rules:
            return
        
        suggestions.append(
            f"{product_type} beden/stok kurallarını gevşetirseniz (Y veya Z değerlerini düşürürseniz), "
            f"daha fazla ürün kullanılabilir"
        )
    
    def format_dialog_message(self, violations: List[str], suggestions: List[str]) -> str:
        """
        Format violations and suggestions into a user-friendly dialog message.
        
        Args:
            violations: List of constraint violations
            suggestions: List of relaxation suggestions
            
        Returns:
            str: Formatted message for dialog
        """
        lines = []
        lines.append("Bu ayarlarla plan oluşturulamıyor.")
        lines.append("")
        lines.append("Eksik kalan kriterler:")
        for v in violations:
            lines.append(f"  - {v}")
        
        if suggestions:
            lines.append("")
            lines.append("Daha fazla ürün bulmak için şu yumuşatma opsiyonları var:")
            for s in suggestions:
                lines.append(f"  - {s}")
        
        return "\n".join(lines)


def analyze_constraints(calendar: List[Dict], first_candidates: pd.DataFrame,
                       back_candidates: pd.DataFrame, cfg: Dict,
                       unique_products: pd.DataFrame = None,
                       posts: List[Dict] = None) -> Tuple[List[str], List[str], str]:
    """
    Convenience function to analyze constraints and return formatted results.
    
    Args:
        calendar: List of post slots
        first_candidates: FIRST product candidates
        back_candidates: BACK product candidates
        cfg: Configuration dictionary
        unique_products: All unique products (optional, for deeper analysis)
        posts: Current posts (optional, for NOS/DVM analysis)
        
    Returns:
        tuple: (violations, suggestions, formatted_message)
    """
    if unique_products is None:
        unique_products = pd.concat([first_candidates, back_candidates]).drop_duplicates()
    
    analyzer = ConstraintAnalyzer(calendar, first_candidates, back_candidates, cfg, unique_products)
    
    all_violations = []
    all_suggestions = []
    
    v, s = analyzer.analyze_first_pool_size()
    all_violations.extend(v)
    all_suggestions.extend(s)
    
    v, s = analyzer.analyze_back_pool_size()
    all_violations.extend(v)
    all_suggestions.extend(s)
    
    if posts:
        v, s = analyzer.analyze_nos_dvm_requirements(posts)
        all_violations.extend(v)
        all_suggestions.extend(s)
    
    message = analyzer.format_dialog_message(all_violations, all_suggestions)
    
    return all_violations, all_suggestions, message
