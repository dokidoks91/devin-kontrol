#!/usr/bin/env python3
"""
Product Helper Functions

This module contains helper functions for product calculations and sorting.
All helpers follow the global rule: stock of a product = sum of ToplamStok 
over all sizes for that exact kisakodrenk (KisaKod + Renk).
"""

import pandas as pd
from typing import Tuple


def get_total_stock_per_kisakodrenk(df: pd.DataFrame) -> dict:
    """
    Calculate total stock per kisakodrenk (KisaKod + Renk).
    
    Global rule: Stock of a product = sum of ToplamStok over all sizes 
    for that exact kisakodrenk. Never aggregate across colors.
    
    Args:
        df: DataFrame with columns: kisakodrenk, ToplamStok
        
    Returns:
        dict mapping kisakodrenk to total stock
    """
    if "kisakodrenk" not in df.columns or "ToplamStok" not in df.columns:
        return {}
    
    return df.groupby("kisakodrenk")["ToplamStok"].sum().to_dict()


def product_recency_key(kisakod: str) -> Tuple[int, int]:
    """
    Calculate recency key for sorting products by newness.
    
    Newness definition:
    - First digit of KisaKod = last digit of year (5 = 2025, 3 = 2023)
    - Last 3 digits = sequence number (higher = newer)
    
    Examples:
        5Y530 → (5, 530) - year 2025, sequence 530
        3K035 → (3, 35) - year 2023, sequence 35
        5K234 → (5, 234) - year 2025, sequence 234
    
    For products within same year, higher sequence = newer.
    For products in different years, higher year digit = newer.
    
    Args:
        kisakod: Product code (e.g., "5Y530", "3K035")
        
    Returns:
        tuple: (year_digit, sequence_number)
               Returns (-1, -1) for malformed codes to sort them last
    """
    kisakod_str = str(kisakod).strip()
    
    if len(kisakod_str) < 4:
        return (-1, -1)
    
    year_digit = -1
    if kisakod_str[0].isdigit():
        year_digit = int(kisakod_str[0])
    
    sequence_num = -1
    try:
        last_three = kisakod_str[-3:]
        digits_only = ''.join(c for c in last_three if c.isdigit())
        if digits_only:
            sequence_num = int(digits_only)
    except (ValueError, IndexError):
        pass
    
    return (year_digit, sequence_num)


def normalize_color_for_comparison(color: str) -> str:
    """
    Normalize color string for comparison.
    
    Converts to uppercase to handle Turkish characters correctly.
    Turkish has special uppercase rules: i -> İ, ı -> I
    
    Args:
        color: Color string (e.g., "Siyah", "SİYAH", "SIYAH")
        
    Returns:
        Normalized uppercase color string
    """
    if not color:
        return ""
    
    color_str = str(color)
    color_str = color_str.replace('i', 'İ').replace('ı', 'I')
    return color_str.upper()


def is_black_color(color: str) -> bool:
    """
    Check if a color is black (SİYAH in Turkish).
    
    Handles Turkish uppercase correctly:
    - "Siyah" -> "SİYAH" (i -> İ)
    - "SIYAH" -> "SİYAH" (I -> İ after normalization)
    
    Args:
        color: Color string
        
    Returns:
        True if color is exactly "SİYAH" (case-insensitive with Turkish rules)
    """
    normalized = normalize_color_for_comparison(color)
    return normalized in ("SİYAH", "SIYAH")
