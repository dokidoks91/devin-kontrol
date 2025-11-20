#!/usr/bin/env python3
"""
Product Helper Functions

This module contains helper functions for product calculations and sorting.
All helpers follow the global rule: stock of a product = sum of ToplamStok 
over all sizes for that exact kisakodrenk (KisaKod + Renk).
"""

import pandas as pd
import numpy as np
from typing import Tuple, Any


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


# ============================================================================
# ============================================================================

def normalize_cell(value: Any) -> str:
    """
    Normalize a single cell value to a clean string.
    
    Handles NaN, None, and converts to uppercase with trimming.
    This is the base normalization applied to all data columns.
    
    Args:
        value: Cell value (can be str, float, None, NaN, etc.)
        
    Returns:
        Normalized string (empty string for NaN/None)
    """
    if pd.isna(value) or value is None:
        return ""
    
    s = str(value).strip().upper()
    
    if s == "NAN":
        return ""
    
    return s


def normalize_nos(value: Any) -> str:
    """
    Normalize Nos column value.
    
    Allowed values in dataset: "E", "#YOK", empty
    Normalized to: "E" or "" (empty)
    
    Logic:
    - "E" → "E" (NOS product)
    - "#YOK", "NA", empty, None → "" (not NOS)
    - Unknown values → raise ValueError
    
    Args:
        value: Raw Nos column value
        
    Returns:
        Normalized Nos value: "E" or ""
        
    Raises:
        ValueError: If value is not in allowed set
    """
    normalized = normalize_cell(value)
    
    if normalized in ("", "#YOK", "NA"):
        return ""
    
    if normalized == "E":
        return "E"
    
    raise ValueError(
        f"Unknown value in Nos column: '{value}'. "
        f"Allowed values: 'E', '#YOK', empty. "
        f"Please update the stock file."
    )


def normalize_dvm(value: Any) -> str:
    """
    Normalize DVM column value.
    
    Allowed values in dataset: "DVM", "#YOK", empty
    Normalized to: "DVM" or "" (empty)
    
    Logic:
    - "DVM" → "DVM" (DVM product)
    - "#YOK", "NA", empty, None → "" (not DVM)
    - Unknown values → raise ValueError
    
    Args:
        value: Raw DVM column value
        
    Returns:
        Normalized DVM value: "DVM" or ""
        
    Raises:
        ValueError: If value is not in allowed set
    """
    normalized = normalize_cell(value)
    
    if normalized in ("", "#YOK", "NA"):
        return ""
    
    if normalized == "DVM":
        return "DVM"
    
    raise ValueError(
        f"Unknown value in DVM column: '{value}'. "
        f"Allowed values: 'DVM', '#YOK', empty. "
        f"Please update the stock file."
    )


def normalize_cekim(value: Any) -> str:
    """
    Normalize Cekim column value.
    
    Allowed values in dataset: "EVET", "NA", "#YOK", empty
    Normalized to: "EVET", "NA", "#YOK", or "" (empty)
    
    Logic:
    - "EVET" → "EVET" (has photo shoot)
    - "NA" → "NA" (explicit NA marker)
    - "#YOK" → "#YOK" (explicit missing marker)
    - empty, None → "" (empty)
    - Unknown values → raise ValueError
    
    Note: Unlike Nos/DVM, we keep NA and #YOK distinct for Cekim
    because the GUI filter allows selecting these explicitly.
    
    Args:
        value: Raw Cekim column value
        
    Returns:
        Normalized Cekim value: "EVET", "NA", "#YOK", or ""
        
    Raises:
        ValueError: If value is not in allowed set
    """
    normalized = normalize_cell(value)
    
    if normalized in ("EVET", "NA", "#YOK", ""):
        return normalized
    
    raise ValueError(
        f"Unknown value in Cekim column: '{value}'. "
        f"Allowed values: 'EVET', 'NA', '#YOK', empty. "
        f"Please update the stock file."
    )


def normalize_stock_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize all stock data columns with strict validation.
    
    This function applies column-specific normalization to ensure
    data consistency and catch any unexpected values early.
    
    Columns normalized:
    - KisaKod, Renk, UrunCinsi: Basic trim + preserve case
    - Sezon: Trim + uppercase
    - Nos: Strict normalization to "E" or ""
    - DVM: Strict normalization to "DVM" or ""
    - Cekim: Strict normalization to "EVET", "NA", "#YOK", or ""
    
    Args:
        df: Raw DataFrame from Excel
        
    Returns:
        DataFrame with normalized columns
        
    Raises:
        ValueError: If any column contains unexpected values
    """
    df = df.copy()
    
    for col in ["KisaKod", "Renk", "UrunCinsi"]:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: str(x).strip() if pd.notna(x) else "")
    
    if "Sezon" in df.columns:
        df["Sezon"] = df["Sezon"].apply(normalize_cell)
    
    if "Nos" in df.columns:
        try:
            df["Nos"] = df["Nos"].apply(normalize_nos)
        except ValueError as e:
            raise ValueError(f"Nos column normalization failed: {e}")
    
    if "DVM" in df.columns:
        try:
            df["DVM"] = df["DVM"].apply(normalize_dvm)
        except ValueError as e:
            raise ValueError(f"DVM column normalization failed: {e}")
    
    if "Cekim" in df.columns:
        try:
            df["Cekim"] = df["Cekim"].apply(normalize_cekim)
        except ValueError as e:
            raise ValueError(f"Cekim column normalization failed: {e}")
    
    print("\n=== Data Normalization Summary ===")
    if "Nos" in df.columns:
        nos_unique = sorted(df["Nos"].unique())
        print(f"Nos unique values: {nos_unique}")
    if "DVM" in df.columns:
        dvm_unique = sorted(df["DVM"].unique())
        print(f"DVM unique values: {dvm_unique}")
    if "Cekim" in df.columns:
        cekim_unique = sorted(df["Cekim"].unique())
        print(f"Cekim unique values: {cekim_unique}")
    print("==================================\n")
    
    return df
