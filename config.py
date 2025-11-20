#!/usr/bin/env python3
"""
Configuration module for Instagram Post Planner

This module defines the configuration structure for all planning parameters.
NO numeric thresholds are hard-coded - everything must come from GUI inputs.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta


@dataclass
class PreferredFirstProduct:
    """Single preferred FIRST product with optional gun/time constraints"""
    kisakodrenk: str  # e.g., "0K009SİYAH"
    gun: Optional[str] = None  # Day name: Pazartesi, Salı, etc.
    time: Optional[str] = None  # HH:MM format, must match weekday/weekend times
    
    def is_valid(self) -> tuple[bool, str]:
        """
        Validate this preferred product entry.
        Returns (is_valid, error_message)
        """
        if not self.kisakodrenk or not self.kisakodrenk.strip():
            return True, ""  # Empty row is valid (ignored)
        
        if self.time and not self.gun:
            return False, "Saat seçilen tercihli FIRST ürün için gün de seçmelisiniz."
        
        return True, ""


@dataclass
class PlanConfig:
    """Complete configuration for Instagram post planning"""
    
    # ============================================================
    # ============================================================
    stock_excel_path: str
    plan_start_day_name: str  # Pazartesi, Salı, etc.
    plan_num_days: int  # 1-7
    
    weekday_times: List[str] = field(default_factory=lambda: [
        "09:00", "10:30", "11:30", "12:30", "13:30", "14:30",
        "15:30", "16:30", "17:30", "19:30", "21:00", "22:30",
    ])
    weekend_times: List[str] = field(default_factory=lambda: [
        "11:00", "12:00", "13:00", "14:00", "15:00",
        "16:00", "17:00", "18:30", "19:30", "21:00",
    ])
    
    # ============================================================
    # ============================================================
    
    use_yazlik_front: bool = True
    use_kislik_front: bool = True
    
    allowed_cekim_front: List[str] = field(default_factory=lambda: ["EVET", "NA"])
    
    one_atilma_allow_na: bool = True  # Allow #N/A values
    one_atilma_reference_date: Optional[str] = None  # yyyy-mm-dd format
    one_atilma_min_days: Optional[int] = None  # X days
    
    min_total_stock_front: Optional[int] = None
    
    front_size_stock_rules: Dict[int, tuple] = field(default_factory=dict)
    
    min_nos_front: Optional[int] = None
    min_dvm_front: Optional[int] = None
    
    # ============================================================
    # ============================================================
    
    use_yazlik_back: bool = True
    use_kislik_back: bool = True
    
    allowed_cekim_back: List[str] = field(default_factory=lambda: ["EVET", "NA"])
    
    min_total_stock_back: Optional[int] = None
    
    back_size_stock_rules: Dict[int, tuple] = field(default_factory=dict)
    
    # ============================================================
    # ============================================================
    
    max_same_uruncinsi_in_a_row_per_day: Optional[int] = None
    
    min_distinct_uruncinsi_per_day: Optional[int] = None
    
    max_same_color_in_a_row_per_day: Optional[int] = None
    
    min_distinct_color_per_day: Optional[int] = None
    
    same_kisakod_min_gap_days: Optional[int] = None
    
    max_black_first_per_day: Optional[int] = None
    
    max_first_uses_per_kisakod: Optional[int] = None
    
    # ============================================================
    # ============================================================
    
    global_min_first_stock_sum: Optional[int] = None
    
    global_min_total_stock_sum: Optional[int] = None
    
    # ============================================================
    # ============================================================
    
    prioritize_by_newness: bool = False
    prioritize_by_stock: bool = False
    
    priority_mode_front: str = "stock_then_newest"
    priority_mode_back: str = "stock_then_newest"
    
    # ============================================================
    # ============================================================
    
    preferred_first_products: List[PreferredFirstProduct] = field(default_factory=list)
    
    def validate(self) -> List[str]:
        """
        Validate that all required fields are set.
        Returns list of error messages (empty if valid).
        """
        errors = []
        
        if not self.stock_excel_path:
            errors.append("Stok dosyası seçilmedi")
        if not self.plan_start_day_name:
            errors.append("Plan başlangıç günü seçilmedi")
        if not self.plan_num_days or self.plan_num_days < 1 or self.plan_num_days > 7:
            errors.append("Plan gün sayısı 1-7 arası olmalı")
        
        if self.min_total_stock_front is None:
            errors.append("FIRST ürün minimum stok değeri girilmedi")
        if self.min_nos_front is None:
            errors.append("Minimum NOS FIRST sayısı girilmedi")
        if self.min_dvm_front is None:
            errors.append("Minimum DVM FIRST sayısı girilmedi")
        
        if not self.one_atilma_allow_na:
            if not self.one_atilma_reference_date:
                errors.append("One Atilma Tarihi referans tarihi girilmedi")
            if self.one_atilma_min_days is None:
                errors.append("One Atilma Tarihi minimum gün sayısı girilmedi")
        
        for size_count in range(1, 9):
            if size_count not in self.front_size_stock_rules:
                errors.append(f"FIRST beden/stok kuralı eksik: {size_count} beden için değer girilmedi")
        
        if self.min_total_stock_back is None:
            errors.append("BACK ürün minimum stok değeri girilmedi")
        
        for size_count in range(1, 9):
            if size_count not in self.back_size_stock_rules:
                errors.append(f"BACK beden/stok kuralı eksik: {size_count} beden için değer girilmedi")
        
        if self.max_same_uruncinsi_in_a_row_per_day is None:
            errors.append("Aynı ürün cinsi ardışık limit girilmedi")
        if self.min_distinct_uruncinsi_per_day is None:
            errors.append("Günlük minimum farklı ürün cinsi sayısı girilmedi")
        if self.max_same_color_in_a_row_per_day is None:
            errors.append("Aynı renk ardışık limit girilmedi")
        if self.min_distinct_color_per_day is None:
            errors.append("Günlük minimum farklı renk sayısı girilmedi")
        if self.same_kisakod_min_gap_days is None:
            errors.append("Aynı KisaKod minimum ara gün sayısı girilmedi")
        
        if self.global_min_first_stock_sum is None:
            errors.append("Global FIRST stok hedefi girilmedi")
        if self.global_min_total_stock_sum is None:
            errors.append("Global toplam stok hedefi girilmedi")
        
        for i, pref in enumerate(self.preferred_first_products, 1):
            is_valid, error_msg = pref.is_valid()
            if not is_valid:
                errors.append(f"Tercihli FIRST ürün {i}: {error_msg}")
        
        return errors
    
    def validate_preferred_products_advanced(self, calendar: List[dict]) -> List[str]:
        """
        Advanced validation for preferred products that requires calendar context.
        This should be called during plan generation after calendar is built.
        
        Args:
            calendar: List of post slots with day_name, time
        
        Returns:
            List of error messages (empty if valid)
        """
        errors = []
        
        available_days = set()
        gun_time_slots = {}
        for slot in calendar:
            day_name = slot.get('day_name')
            time = slot.get('time')
            available_days.add(day_name)
            key = (day_name, time)
            if key not in gun_time_slots:
                gun_time_slots[key] = []
            gun_time_slots[key].append(slot)
        
        used_slots = {}
        
        for i, pref in enumerate(self.preferred_first_products, 1):
            if isinstance(pref, dict):
                kisakodrenk = (pref.get("kisakodrenk") or "").strip()
                gun = (pref.get("gun") or "").strip()
                time = (pref.get("time") or "").strip()
            else:
                kisakodrenk = (pref.kisakodrenk or "").strip()
                gun = (pref.gun or "").strip()
                time = (pref.time or "").strip()
            
            if not kisakodrenk:
                continue
            
            if gun and gun not in available_days:
                errors.append(
                    f"Tercihli FIRST ürün {i} ({kisakodrenk}): "
                    f"Tercihli First ürün için seçilen gün planda yok. başka gün seçer misin."
                )
                continue
            
            if gun and time:
                slot_key = (gun, time)
                
                if slot_key not in gun_time_slots:
                    errors.append(
                        f"Tercihli FIRST ürün {i} ({kisakodrenk}): "
                        f"Gün {gun} saat {time} plan aralığında değil"
                    )
                    continue
                
                if slot_key in used_slots:
                    other_idx = used_slots[slot_key]
                    errors.append(
                        f"Bu tarih ve saatte iki tercihli FIRST ürünü yerleştirilemez. Lütfen düzeltin. "
                        f"(Ürün {i}: {kisakodrenk} ve Ürün {other_idx} - {gun} {time})"
                    )
                else:
                    used_slots[slot_key] = i
        
        return errors
    
    def to_dict(self) -> dict:
        """Convert to dictionary format compatible with existing code"""
        front_rules = []
        for size_count in sorted(self.front_size_stock_rules.keys()):
            y, z = self.front_size_stock_rules[size_count]
            if y > 0 and z > 0:  # Only include valid rules
                front_rules.append((size_count, y, z))
        
        back_rules = []
        for size_count in sorted(self.back_size_stock_rules.keys()):
            y, z = self.back_size_stock_rules[size_count]
            if y > 0 and z > 0:  # Only include valid rules
                back_rules.append((size_count, y, z))
        
        return {
            "stock_excel_path": self.stock_excel_path,
            "plan_start_day_name": self.plan_start_day_name,
            "plan_num_days": self.plan_num_days,
            "weekday_times": self.weekday_times,
            "weekend_times": self.weekend_times,
            
            "use_yazlik_front": self.use_yazlik_front,
            "use_kislik_front": self.use_kislik_front,
            "allowed_cekim_front": self.allowed_cekim_front,
            "one_atilma_reference_date": self.one_atilma_reference_date,
            "one_atilma_min_days": self.one_atilma_min_days,
            "min_total_stock_front": self.min_total_stock_front or 0,
            "front_size_stock_rules": front_rules,
            "min_nos_front": self.min_nos_front or 0,
            "min_dvm_front": self.min_dvm_front or 0,
            
            "use_yazlik_back": self.use_yazlik_back,
            "use_kislik_back": self.use_kislik_back,
            "allowed_cekim_back": self.allowed_cekim_back,
            "min_total_stock_back": self.min_total_stock_back or 0,
            "back_size_stock_rules": back_rules,
            
            "max_same_uruncinsi_in_a_row_per_day": self.max_same_uruncinsi_in_a_row_per_day or 0,
            "min_distinct_uruncinsi_per_day": self.min_distinct_uruncinsi_per_day or 0,
            "max_same_color_in_a_row_per_day": self.max_same_color_in_a_row_per_day or 0,
            "min_distinct_color_per_day": self.min_distinct_color_per_day or 0,
            
            "priority_mode_front": self.priority_mode_front,
            "priority_mode_back": self.priority_mode_back,
            
            "same_kisakod_min_gap_days": self.same_kisakod_min_gap_days or 0,
            "max_black_first_per_day": self.max_black_first_per_day or 0,
            "max_first_uses_per_kisakod": self.max_first_uses_per_kisakod or 0,
            
            "global_min_first_stock_sum": self.global_min_first_stock_sum or 0,
            "global_min_total_stock_sum": self.global_min_total_stock_sum or 0,
            
            "prioritize_by_newness": self.prioritize_by_newness,
            "prioritize_by_stock": self.prioritize_by_stock,
            
            "preferred_first_products": [
                {
                    "kisakodrenk": p.kisakodrenk,
                    "gun": p.gun,
                    "time": p.time
                }
                for p in self.preferred_first_products
                if p.kisakodrenk and p.kisakodrenk.strip()
            ],
        }


def create_default_config() -> PlanConfig:
    """
    Create a config with reasonable defaults for GUI initialization.
    Note: These are just UI defaults, not business rule defaults.
    User must fill in all values before running.
    """
    config = PlanConfig(
        stock_excel_path="",
        plan_start_day_name="Pazartesi",
        plan_num_days=7,
    )
    
    for size_count in range(1, 9):
        config.front_size_stock_rules[size_count] = (0, 0)
        config.back_size_stock_rules[size_count] = (0, 0)
    
    return config
