#!/usr/bin/env python3
"""
Validator Module for Instagram Post Planner

This module validates the final plan against all constraints and generates
a detailed report for the Kriter_Ozet (Criteria Summary) sheet.
"""

from typing import List, Dict, Any
from dataclasses import dataclass
from collections import Counter
import pandas as pd


@dataclass
class ConstraintResult:
    """Result of validating a single constraint"""
    kriter_adi: str  # Constraint name
    beklenen_deger: str  # Expected value
    gerceklesen_deger: str  # Actual achieved value
    durum: str  # Status: "OK" or "FAILED"
    notlar: str = ""  # Additional notes


class PlanValidator:
    """Validates a completed plan against all constraints"""
    
    def __init__(self, posts: List[Dict], cfg: Dict, first_candidates: pd.DataFrame, back_candidates: pd.DataFrame):
        """
        Initialize validator with plan data.
        
        Args:
            posts: List of post dictionaries with first_product and back_products
            cfg: Configuration dictionary with all constraints
            first_candidates: DataFrame of FIRST product candidates
            back_candidates: DataFrame of BACK product candidates
        """
        self.posts = posts
        self.cfg = cfg
        self.first_candidates = first_candidates
        self.back_candidates = back_candidates
        self.results: List[ConstraintResult] = []
    
    def validate_all(self) -> List[ConstraintResult]:
        """
        Run all validation checks and return list of ConstraintResult objects.
        """
        self.results = []
        
        self._validate_nos_dvm()
        
        self._validate_stock_targets()
        
        self._validate_global_stock_targets()
        
        self._validate_per_day_constraints()
        
        self._validate_new_first_constraints()
        
        self._validate_uniqueness()
        
        self._validate_seasonal()
        
        self._validate_size_stock_rules()
        
        return self.results
    
    def _validate_nos_dvm(self):
        """Validate NOS and DVM minimum counts"""
        nos_first_plan = {
            p["first_product"]["kisakodrenk"]
            for p in self.posts
            if p["first_product"].get("Nos", "") == "E"
        }
        dvm_first_plan = {
            p["first_product"]["kisakodrenk"]
            for p in self.posts
            if p["first_product"].get("DVM", "") == "DVM"
        }
        
        min_nos = self.cfg.get("min_nos_front", 0)
        min_dvm = self.cfg.get("min_dvm_front", 0)
        
        self.results.append(ConstraintResult(
            kriter_adi="Minimum NOS FIRST sayısı",
            beklenen_deger=f">= {min_nos}",
            gerceklesen_deger=str(len(nos_first_plan)),
            durum="OK" if len(nos_first_plan) >= min_nos else "FAILED"
        ))
        
        self.results.append(ConstraintResult(
            kriter_adi="Minimum DVM FIRST sayısı",
            beklenen_deger=f">= {min_dvm}",
            gerceklesen_deger=str(len(dvm_first_plan)),
            durum="OK" if len(dvm_first_plan) >= min_dvm else "FAILED"
        ))
    
    def _validate_stock_targets(self):
        """Validate per-product minimum stock requirements"""
        min_stock_front = self.cfg.get("min_total_stock_front", 0)
        min_stock_back = self.cfg.get("min_total_stock_back", 0)
        
        first_below_min = []
        for p in self.posts:
            stock = p["first_product"].get("total_stock", 0)
            if stock < min_stock_front:
                first_below_min.append(p["first_product"]["kisakodrenk"])
        
        self.results.append(ConstraintResult(
            kriter_adi="FIRST ürün minimum stok",
            beklenen_deger=f"Tüm FIRST ürünler >= {min_stock_front}",
            gerceklesen_deger=f"{len(self.posts) - len(first_below_min)}/{len(self.posts)} ürün uygun",
            durum="OK" if len(first_below_min) == 0 else "FAILED",
            notlar=f"Uygun olmayan: {', '.join(first_below_min[:5])}" if first_below_min else ""
        ))
        
        back_below_min = []
        for p in self.posts:
            for bp in p.get("back_products", []):
                stock = bp.get("total_stock", 0)
                if stock < min_stock_back:
                    back_below_min.append(bp["kisakodrenk"])
        
        total_back = sum(len(p.get("back_products", [])) for p in self.posts)
        self.results.append(ConstraintResult(
            kriter_adi="BACK ürün minimum stok",
            beklenen_deger=f"Tüm BACK ürünler >= {min_stock_back}",
            gerceklesen_deger=f"{total_back - len(back_below_min)}/{total_back} ürün uygun",
            durum="OK" if len(back_below_min) == 0 else "FAILED",
            notlar=f"Uygun olmayan: {', '.join(set(back_below_min[:5]))}" if back_below_min else ""
        ))
    
    def _validate_global_stock_targets(self):
        """
        Validate global stock sum targets.
        
        Per user requirement: Count each kisakodrenk once even if used multiple times.
        Sum stock per unique kisakodrenk (per-color aggregation).
        """
        global_min_first = self.cfg.get("global_min_first_stock_sum", 0)
        global_min_total = self.cfg.get("global_min_total_stock_sum", 0)
        
        unique_first_kisakodrenk = {}
        for p in self.posts:
            kkr = p["first_product"]["kisakodrenk"]
            if kkr not in unique_first_kisakodrenk:
                unique_first_kisakodrenk[kkr] = p["first_product"].get("total_stock", 0)
        
        first_stock_sum = sum(unique_first_kisakodrenk.values())
        
        self.results.append(ConstraintResult(
            kriter_adi="Global FIRST stok toplamı",
            beklenen_deger=f">= {global_min_first}",
            gerceklesen_deger=str(first_stock_sum),
            durum="OK" if first_stock_sum >= global_min_first else "FAILED",
            notlar=f"{len(unique_first_kisakodrenk)} unique FIRST kisakodrenk"
        ))
        
        unique_all_kisakodrenk = unique_first_kisakodrenk.copy()
        for p in self.posts:
            for bp in p.get("back_products", []):
                kkr = bp["kisakodrenk"]
                if kkr not in unique_all_kisakodrenk:
                    unique_all_kisakodrenk[kkr] = bp.get("total_stock", 0)
        
        total_stock_sum = sum(unique_all_kisakodrenk.values())
        
        self.results.append(ConstraintResult(
            kriter_adi="Global toplam (FIRST+BACK) stok toplamı",
            beklenen_deger=f">= {global_min_total}",
            gerceklesen_deger=str(total_stock_sum),
            durum="OK" if total_stock_sum >= global_min_total else "FAILED",
            notlar=f"{len(unique_all_kisakodrenk)} unique kisakodrenk total"
        ))
    
    def _validate_per_day_constraints(self):
        """Validate per-day distinct and consecutive constraints"""
        max_same_uruncinsi = self.cfg.get("max_same_uruncinsi_in_a_row_per_day", 999)
        min_distinct_uruncinsi = self.cfg.get("min_distinct_uruncinsi_per_day", 0)
        max_same_color = self.cfg.get("max_same_color_in_a_row_per_day", 999)
        min_distinct_color = self.cfg.get("min_distinct_color_per_day", 0)
        
        posts_by_day = {}
        for p in self.posts:
            day = p["day_name"]
            if day not in posts_by_day:
                posts_by_day[day] = []
            posts_by_day[day].append(p)
        
        uruncinsi_violations = []
        color_violations = []
        
        for day, day_posts in posts_by_day.items():
            uruncinsi_set = {p["first_product"]["UrunCinsi"] for p in day_posts}
            if len(uruncinsi_set) < min_distinct_uruncinsi:
                uruncinsi_violations.append(f"{day}: {len(uruncinsi_set)}")
            
            color_set = {p["first_product"]["Renk"] for p in day_posts}
            if len(color_set) < min_distinct_color:
                color_violations.append(f"{day}: {len(color_set)}")
        
        self.results.append(ConstraintResult(
            kriter_adi="Günlük minimum farklı ürün cinsi",
            beklenen_deger=f"Her gün >= {min_distinct_uruncinsi}",
            gerceklesen_deger=f"{len(posts_by_day) - len(uruncinsi_violations)}/{len(posts_by_day)} gün uygun",
            durum="OK" if len(uruncinsi_violations) == 0 else "FAILED",
            notlar=f"Uygun olmayan günler: {', '.join(uruncinsi_violations)}" if uruncinsi_violations else ""
        ))
        
        self.results.append(ConstraintResult(
            kriter_adi="Günlük minimum farklı renk",
            beklenen_deger=f"Her gün >= {min_distinct_color}",
            gerceklesen_deger=f"{len(posts_by_day) - len(color_violations)}/{len(posts_by_day)} gün uygun",
            durum="OK" if len(color_violations) == 0 else "FAILED",
            notlar=f"Uygun olmayan günler: {', '.join(color_violations)}" if color_violations else ""
        ))
    
    def _validate_new_first_constraints(self):
        """Validate new FIRST-only constraints (black color limit, max KisaKod uses)"""
        from product_helpers import is_black_color
        
        max_black_per_day = self.cfg.get("max_black_first_per_day", 0)
        max_kisakod_uses = self.cfg.get("max_first_uses_per_kisakod", 0)
        
        if max_black_per_day > 0:
            posts_by_day = {}
            for p in self.posts:
                day = p["day_name"]
                if day not in posts_by_day:
                    posts_by_day[day] = []
                posts_by_day[day].append(p)
            
            black_violations = []
            for day, day_posts in posts_by_day.items():
                black_count = sum(1 for p in day_posts if is_black_color(p["first_product"].get("Renk", "")))
                if black_count > max_black_per_day:
                    black_violations.append(f"{day}: {black_count}")
            
            self.results.append(ConstraintResult(
                kriter_adi="Günlük max SİYAH FIRST ürün sayısı",
                beklenen_deger=f"Her gün <= {max_black_per_day}" if max_black_per_day > 0 else "Kısıt yok",
                gerceklesen_deger=f"{len(posts_by_day) - len(black_violations)}/{len(posts_by_day)} gün uygun",
                durum="OK" if len(black_violations) == 0 else "FAILED",
                notlar=f"Limit aşan günler: {', '.join(black_violations)}" if black_violations else ""
            ))
        
        if max_kisakod_uses > 0:
            kisakod_counts = Counter(p["first_product"]["KisaKod"] for p in self.posts)
            violations = {k: v for k, v in kisakod_counts.items() if v > max_kisakod_uses}
            
            self.results.append(ConstraintResult(
                kriter_adi="Aynı KisaKod max FIRST kullanım sayısı",
                beklenen_deger=f"Her KisaKod <= {max_kisakod_uses} kez" if max_kisakod_uses > 0 else "Kısıt yok",
                gerceklesen_deger=f"{len(kisakod_counts) - len(violations)}/{len(kisakod_counts)} KisaKod uygun",
                durum="OK" if len(violations) == 0 else "FAILED",
                notlar=f"Limit aşan KisaKod: {', '.join([f'{k}({v})' for k, v in list(violations.items())[:5]])}" if violations else ""
            ))
    
    def _validate_uniqueness(self):
        """Validate that each kisakodrenk is used only once (with exceptions)"""
        all_kisakodrenk = []
        
        for p in self.posts:
            all_kisakodrenk.append(p["first_product"]["kisakodrenk"])
            for bp in p.get("back_products", []):
                all_kisakodrenk.append(bp["kisakodrenk"])
        
        counter = Counter(all_kisakodrenk)
        duplicates = {k: v for k, v in counter.items() if v > 1}
        
        self.results.append(ConstraintResult(
            kriter_adi="Kisakodrenk teklik kuralı",
            beklenen_deger="Her kisakodrenk en fazla 1 kez (istisnalar hariç)",
            gerceklesen_deger=f"{len(duplicates)} tekrarlı kisakodrenk",
            durum="OK" if len(duplicates) == 0 else "FAILED",
            notlar=f"Tekrarlı: {', '.join(list(duplicates.keys())[:5])}" if duplicates else ""
        ))
        
        min_gap_days = self.cfg.get("same_kisakod_min_gap_days", 0)
        if min_gap_days > 0:
            day_order = []
            day_posts = {}
            for p in self.posts:
                day = p["day_name"]
                if day not in day_order:
                    day_order.append(day)
                if day not in day_posts:
                    day_posts[day] = []
                day_posts[day].append(p)
            
            kisakod_violations = []
            kisakod_last_day_idx = {}
            
            for day_idx, day in enumerate(day_order):
                for p in day_posts[day]:
                    kisakod = p["first_product"]["KisaKod"]
                    if kisakod in kisakod_last_day_idx:
                        last_idx = kisakod_last_day_idx[kisakod]
                        gap = day_idx - last_idx
                        if gap < min_gap_days:
                            kisakod_violations.append(f"{kisakod} (gap: {gap} < {min_gap_days})")
                    kisakod_last_day_idx[kisakod] = day_idx
            
            self.results.append(ConstraintResult(
                kriter_adi="Aynı KisaKod minimum ara gün sayısı",
                beklenen_deger=f"Minimum {min_gap_days} gün ara",
                gerceklesen_deger=f"{len(kisakod_violations)} ihlal",
                durum="OK" if len(kisakod_violations) == 0 else "FAILED",
                notlar=f"İhlaller: {', '.join(kisakod_violations[:5])}" if kisakod_violations else ""
            ))
    
    def _validate_seasonal(self):
        """Validate seasonal (Yazlık/Kışlık) correctness"""
        use_yazlik_front = self.cfg.get("use_yazlik_front", True)
        use_kislik_front = self.cfg.get("use_kislik_front", True)
        
        violations = []
        for p in self.posts:
            sezon = str(p["first_product"].get("Sezon", ""))
            nos = str(p["first_product"].get("Nos", ""))
            
            if nos == "E":
                continue
            
            is_yazlik = len(sezon) >= 2 and sezon[1] == "Y"
            is_kislik = len(sezon) >= 2 and sezon[1] != "Y"
            
            if is_yazlik and not use_yazlik_front:
                violations.append(f"{p['first_product']['kisakodrenk']} (Yazlık)")
            elif is_kislik and not use_kislik_front:
                violations.append(f"{p['first_product']['kisakodrenk']} (Kışlık)")
        
        self.results.append(ConstraintResult(
            kriter_adi="FIRST Yazlık/Kışlık uygunluğu",
            beklenen_deger=f"Yazlık: {use_yazlik_front}, Kışlık: {use_kislik_front}",
            gerceklesen_deger=f"{len(self.posts) - len(violations)}/{len(self.posts)} uygun",
            durum="OK" if len(violations) == 0 else "FAILED",
            notlar=f"Uygun olmayan: {', '.join(violations[:5])}" if violations else ""
        ))
    
    def _validate_size_stock_rules(self):
        """Validate size/stock rules (sample check on FIRST products)"""
        front_rules = self.cfg.get("front_size_stock_rules", [])
        
        if not front_rules:
            return
        
        violations = []
        for p in self.posts:
            size_stocks = p["first_product"].get("size_stocks", [])
            size_count = len(size_stocks)
            
            matches_any_rule = False
            for required_size_count, min_sizes_with_stock, min_stock_value in front_rules:
                if size_count == required_size_count:
                    cnt = sum(1 for s in size_stocks if s >= min_stock_value)
                    if cnt >= min_sizes_with_stock:
                        matches_any_rule = True
                        break
            
            if not matches_any_rule:
                violations.append(p["first_product"]["kisakodrenk"])
        
        self.results.append(ConstraintResult(
            kriter_adi="FIRST beden/stok kuralları",
            beklenen_deger=f"{len(front_rules)} kural tanımlı",
            gerceklesen_deger=f"{len(self.posts) - len(violations)}/{len(self.posts)} uygun",
            durum="OK" if len(violations) == 0 else "FAILED",
            notlar=f"Uygun olmayan: {', '.join(violations[:5])}" if violations else ""
        ))
    
    def get_summary_text(self) -> str:
        """Generate human-readable summary text"""
        lines = []
        lines.append("\n" + "=" * 70)
        lines.append("KRİTER DOĞRULAMA ÖZETİ")
        lines.append("=" * 70)
        
        ok_count = sum(1 for r in self.results if r.durum == "OK")
        failed_count = sum(1 for r in self.results if r.durum == "FAILED")
        
        lines.append(f"\nToplam kriter: {len(self.results)}")
        lines.append(f"Başarılı: {ok_count}")
        lines.append(f"Başarısız: {failed_count}")
        lines.append("")
        
        if failed_count > 0:
            lines.append("BAŞARISIZ KRİTERLER:")
            for r in self.results:
                if r.durum == "FAILED":
                    lines.append(f"  ✗ {r.kriter_adi}")
                    lines.append(f"    Beklenen: {r.beklenen_deger}")
                    lines.append(f"    Gerçekleşen: {r.gerceklesen_deger}")
                    if r.notlar:
                        lines.append(f"    Not: {r.notlar}")
        
        lines.append("=" * 70)
        return "\n".join(lines)
    
    def to_dataframe(self) -> pd.DataFrame:
        """Convert validation results to DataFrame for Excel export"""
        data = []
        for r in self.results:
            data.append({
                "Kriter_Adi": r.kriter_adi,
                "Beklenen_Deger": r.beklenen_deger,
                "Gerceklesen_Deger": r.gerceklesen_deger,
                "Durum": r.durum,
                "Notlar": r.notlar
            })
        return pd.DataFrame(data)


def compute_black_first_counts_by_day(posts: List[Dict]) -> Dict[str, int]:
    """
    Compute count of black FIRST products per day.
    
    Shared helper used by:
    - assign_first_products (assignment-time checking)
    - check_advanced_first_constraints (post-assignment validation)
    - _validate_new_first_constraints (reporting)
    - build_global_kriter_ozet_sheet (reporting)
    
    Args:
        posts: List of post dictionaries with first_product
        
    Returns:
        dict mapping day_name to count of black FIRST products
    """
    from product_helpers import is_black_color
    
    black_counts = {}
    for post in posts:
        day_name = post["day_name"]
        renk = post["first_product"].get("Renk", "")
        
        if day_name not in black_counts:
            black_counts[day_name] = 0
        
        if is_black_color(renk):
            black_counts[day_name] += 1
    
    return black_counts


def compute_first_uses_per_kisakod(posts: List[Dict]) -> Dict[str, int]:
    """
    Compute count of FIRST uses per KisaKod.
    
    Shared helper used by:
    - assign_first_products (assignment-time checking)
    - check_advanced_first_constraints (post-assignment validation)
    - _validate_new_first_constraints (reporting)
    - build_global_kriter_ozet_sheet (reporting)
    
    Args:
        posts: List of post dictionaries with first_product
        
    Returns:
        dict mapping KisaKod to count of FIRST uses
    """
    from collections import Counter
    
    kisakod_counts = Counter(post["first_product"]["KisaKod"] for post in posts)
    return dict(kisakod_counts)


def validate_plan(posts: List[Dict], cfg: Dict, first_candidates: pd.DataFrame, back_candidates: pd.DataFrame) -> tuple:
    """
    Convenience function to validate a plan and return results.
    
    Returns:
        tuple: (results_list, summary_text, results_dataframe)
    """
    validator = PlanValidator(posts, cfg, first_candidates, back_candidates)
    results = validator.validate_all()
    summary = validator.get_summary_text()
    df = validator.to_dataframe()
    
    return results, summary, df
