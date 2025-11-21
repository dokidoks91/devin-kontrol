#!/usr/bin/env python3
import pandas as pd
import os
from datetime import datetime, timedelta
from collections import Counter
import warnings

warnings.filterwarnings("ignore")

# ============================================================
# 1. CONFIG – Admin benzeri ayarlar
# ============================================================

DEFAULT_CFG = {
    # Planlama
    "plan_start_day_name": "Pazartesi",   # Kullanıcıdan sorulacak, varsayılan
    "plan_num_days": 7,                   # 1–7 arası

    # Saatler
    "weekday_times": [
        "09:00", "10:30", "11:30", "12:30", "13:30", "14:30",
        "15:30", "16:30", "17:30", "19:30", "21:00", "22:30",
    ],
    # Haftasonu: günde 10 post (toplam 80 post)
    "weekend_times": [
        "11:00", "12:00", "13:00", "14:00", "15:00",
        "16:00", "17:00", "18:30", "19:30", "21:00",
    ],

    # Excel
    "stock_excel_path": "stokdosya.xlsx",  # Aynı klasördeki stok dosyası

    # FRONT (ilk ürün) – Yazlık / Kışlık
    "use_yazlik_front": True,
    "use_kislik_front": True,

    # BACK (arka ürün) – Yazlık / Kışlık
    "use_yazlik_back": True,
    "use_kislik_back": True,

    # Cekim filtreleri – hepsi UPPERCASE tutulacak: EVET, NA, ...
    "allowed_cekim_front": ["EVET", "NA"],
    "allowed_cekim_back": ["EVET", "NA"],

    # One Atilma Tarihi kuralı (sadece FIRST için)
    # Referans tarih: bu tarihten X gün geriye bakıyoruz
    "one_atilma_reference_date": "2025-02-01",  # yyyy-mm-dd
    "one_atilma_min_days": 45,                  # Son X gün içinde ilk ürün olanlar elenir

    # Min toplam stok
    "min_total_stock_front": 15,
    "min_total_stock_back": 5,

    # Beden / stok kuralları: (required_size_count, min_sizes_with_stock, min_stock_value)
    "front_size_stock_rules": [
        (4, 3, 1),
        (1, 1, 5),
    ],
    "back_size_stock_rules": [
        (4, 3, 1),
        (1, 1, 5),
    ],

    # Haftalık FIRST NOS / DVM minimumları
    "min_nos_front": 2,
    "min_dvm_front": 2,

    # Gün içi ardışık / çeşitlilik kuralları
    "max_same_uruncinsi_in_a_row_per_day": 3,
    "min_distinct_uruncinsi_per_day": 2,
    "max_same_color_in_a_row_per_day": 3,
    "min_distinct_color_per_day": 3,

    # Önceliklendirme
    "priority_mode_front": "stock_then_newest",  # stock_then_newest / newest_then_stock / none
    "priority_mode_back": "stock_then_newest",
}


TURKISH_DAYS = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]


# ============================================================
# 2. Yardımcı input fonksiyonları
# ============================================================

def _ask_int(prompt: str, default: int, min_val: int = None, max_val: int = None) -> int:
    raw = input(f"{prompt} [{default}]: ").strip()
    if not raw:
        return default
    try:
        val = int(raw)
        if min_val is not None and val < min_val:
            raise ValueError
        if max_val is not None and val > max_val:
            raise ValueError
        return val
    except ValueError:
        print("  → Geçersiz sayı, varsayılan kullanıldı.")
        return default


def _ask_day_name(prompt: str, default: str) -> str:
    raw = input(f"{prompt} [{default}]: ").strip()
    if not raw:
        return default
    normalized = raw.capitalize()
    if normalized not in TURKISH_DAYS:
        print("  → Geçersiz gün adı, varsayılan kullanılacak.")
        return default
    return normalized


def ask_plan_settings(cfg: dict) -> None:
    print("\n=== INSTAGRAM HAFTALIK PLAN AYARLARI ===\n")
    start_day = _ask_day_name(
        "Plan başlangıç günü (Pazartesi, Salı, Çarşamba, Perşembe, Cuma, Cumartesi, Pazar)",
        cfg["plan_start_day_name"],
    )
    cfg["plan_start_day_name"] = start_day

    num_days = _ask_int("Kaç günlük plan oluşturulsun (1–7 arası)", cfg["plan_num_days"], 1, 7)
    cfg["plan_num_days"] = num_days

    print(f"\nPlan: {start_day} başlangıçlı, {num_days} günlük olarak ayarlandı.\n")


# ============================================================
# 3. Ortak yardımcı fonksiyonlar
# ============================================================

def ask_best_effort_or_abort(reason_text: str) -> bool:
    """
    Ortak uyarı / karar fonksiyonu.
    True dönerse: best-effort ile devam et.
    False dönerse: işlemi iptal et.
    
    IMPORTANT: This function should ONLY be called from CLI mode.
    When running from GUI, the decide callback should be used instead.
    """
    import sys
    
    if not hasattr(sys, 'stdin') or sys.stdin is None or (hasattr(sys.stdin, 'isatty') and not sys.stdin.isatty()):
        raise RuntimeError(
            "Interactive CLI prompt attempted in GUI mode. "
            "This is a bug - the decide callback should have been used instead. "
            "Please report this error with the context where it occurred."
        )
    
    print("\n" + "=" * 70)
    print("⚠ KRİTER UYARISI")
    print("=" * 70)
    print(reason_text)
    print("\n1) Kriteri KORU ve plan üretimini İPTAL ET")
    print("2) BEST-EFFORT plan üret, bu kuralı karşılamasa da devam et")
    secim = input("Seçiminiz (1/2) [1]: ").strip()
    if secim == "2":
        print("\n→ Best-effort mod seçildi, kural TAM karşılanmasa da devam ediyorum.\n")
        return True
    print("\n→ Kriter korundu, plan üretimi iptal ediliyor.\n")
    return False


# ============================================================
# 4. Veri yükleme ve hazırlık
# ============================================================

def load_stock_data(cfg: dict) -> pd.DataFrame:
    """
    Load and normalize stock data from Excel file.
    
    Applies strict normalization to ensure data consistency:
    - Nos: "E" or "" (empty)
    - DVM: "DVM" or "" (empty)
    - Cekim: "EVET", "NA", "#YOK", or "" (empty)
    
    Raises ValueError if any unexpected values are found.
    """
    from product_helpers import normalize_stock_columns
    
    excel_path = cfg["stock_excel_path"]

    if not os.path.exists(excel_path):
        alt_path = "instagram_stok.xlsx"
        if os.path.exists(alt_path):
            excel_path = alt_path
        else:
            raise FileNotFoundError(f"Stok dosyası bulunamadı: {excel_path}")

    print(f"Stok verisi yükleniyor: {excel_path}")
    df = pd.read_excel(excel_path, engine="openpyxl")

    df = normalize_stock_columns(df)

    return df


def build_unique_products(df: pd.DataFrame) -> pd.DataFrame:
    print("\nUnique ürünler oluşturuluyor (kisakodrenk)...")

    df["KisaKod"] = df["KisaKod"].astype(str)
    df["Renk"] = df["Renk"].astype(str)
    df["kisakodrenk"] = df["KisaKod"] + df["Renk"]

    # toplam stok
    total_stock_per_product = df.groupby("kisakodrenk")["ToplamStok"].sum().to_dict()

    agg_cols = {
        "KisaKod": "first",
        "Renk": "first",
        "UrunCinsi": "first",
        "Sezon": "first",
        "Nos": "first",
        "DVM": "first",
        "Cekim": "first",
    }
    if "One Atilma Tarihi" in df.columns:
        agg_cols["One Atilma Tarihi"] = "first"

    unique_products = df.groupby("kisakodrenk").agg(agg_cols).reset_index()
    unique_products["total_stock"] = unique_products["kisakodrenk"].map(total_stock_per_product)

    # Beden sayısı ve stok listesi
    size_info = []
    for kisakodrenk, group in df.groupby("kisakodrenk"):
        size_stocks = list(group["ToplamStok"])
        size_info.append(
            {
                "kisakodrenk": kisakodrenk,
                "size_count": len(size_stocks),
                "size_stocks": size_stocks,
            }
        )
    size_df = pd.DataFrame(size_info)
    unique_products = unique_products.merge(size_df, on="kisakodrenk", how="left")

    def _season_digit(val):
        s = str(val)
        if len(s) >= 1 and s[0].isdigit():
            return int(s[0])
        return 0

    def _season_seq(val):
        s = str(val)
        if len(s) >= 4:
            last_three = s[-3:]
            digits_only = ''.join(c for c in last_three if c.isdigit())
            if digits_only:
                return int(digits_only)
        return 0

    unique_products["season_digit"] = unique_products["KisaKod"].apply(_season_digit)
    unique_products["season_seq"] = unique_products["KisaKod"].apply(_season_seq)

    print(f"Toplam unique ürün (kisakodrenk): {len(unique_products)}")
    return unique_products


# ============================================================
# 5. Takvim oluşturma
# ============================================================

def build_post_calendar(cfg: dict):
    start_day_name = cfg["plan_start_day_name"]
    num_days = cfg["plan_num_days"]

    weekday_times = cfg["weekday_times"]
    weekend_times = cfg["weekend_times"]

    if start_day_name not in TURKISH_DAYS:
        raise ValueError(f"Geçersiz başlangıç günü: {start_day_name}")

    start_idx = TURKISH_DAYS.index(start_day_name)

    calendar = []
    for i in range(num_days):
        day_idx = (start_idx + i) % 7
        day_name = TURKISH_DAYS[day_idx]
        is_weekend = day_idx in (5, 6)  # Cumartesi, Pazar

        times = weekend_times if is_weekend else weekday_times
        for time in times:
            calendar.append(
                {
                    "day_name": day_name,
                    "time": time,
                    "day_idx": day_idx,
                    "is_weekend": is_weekend,
                }
            )

    print(f"\nTakvim oluşturuldu: {num_days} gün, başlangıç: {start_day_name}")
    print(f"Toplam post slotu: {len(calendar)}")
    return calendar


# ============================================================
# 6. Filtre fonksiyonları
# ============================================================

def check_yazlik_kislik(row, use_yazlik: bool, use_kislik: bool) -> bool:
    """Yazlık / kışlık kuralı + Nos='E' durumu."""
    sezon = str(row.get("Sezon", "") or "")
    nos = str(row.get("Nos", "") or "")

    # Nos = E ise her zaman geçerli
    if nos == "E":
        return True

    is_yazlik = len(sezon) >= 2 and sezon[1] == "Y"
    is_kislik = len(sezon) >= 2 and sezon[1] != "Y"

    if use_yazlik and is_yazlik:
        return True
    if use_kislik and is_kislik:
        return True
    return False


def check_size_stock_rules(size_stocks, rules) -> bool:
    size_count = len(size_stocks)
    for required_size_count, min_sizes_with_stock, min_stock_value in rules:
        if size_count == required_size_count:
            cnt = sum(1 for s in size_stocks if s >= min_stock_value)
            if cnt >= min_sizes_with_stock:
                return True
    return False


def check_one_atilma_tarihi_front(row, cfg: dict) -> bool:
    """One Atilma Tarihi - sadece FIRST için."""
    value = row.get("One Atilma Tarihi", None)

    if value is None or pd.isna(value):
        return True
    s = str(value).strip().upper()
    if s in ("", "NAN", "NA", "#N/A", "NAT"):
        return True

    try:
        ref_date_str = cfg.get("one_atilma_reference_date")
        min_days = cfg.get("one_atilma_min_days")
        
        if not ref_date_str or not min_days:
            return True
        
        ref_date = None
        for fmt in ["%Y-%m-%d", "%d.%m.%Y"]:
            try:
                ref_date = datetime.strptime(ref_date_str, fmt)
                break
            except:
                continue
        
        if ref_date is None:
            return True
        
        threshold = ref_date - timedelta(days=int(min_days))
        one_date = pd.to_datetime(value, dayfirst=True, errors='coerce')
        if pd.isna(one_date):
            return True
        return one_date < threshold
    except Exception:
        return True


def filter_first_products(unique_products: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    print("\n--- FIRST ürün havuzu filtreleniyor ---")
    filtered = unique_products.copy()
    initial = len(filtered)

    # Yazlık / Kışlık + Nos=E
    filtered = filtered[
        filtered.apply(
            lambda r: check_yazlik_kislik(
                r, cfg["use_yazlik_front"], cfg["use_kislik_front"]
            ),
            axis=1,
        )
    ]
    print(f"Yazlık/Kışlık filtresi sonrası: {len(filtered)} (çıkan: {initial - len(filtered)})")

    # Cekim
    allowed_cekim = [c.upper() for c in cfg["allowed_cekim_front"]]
    filtered = filtered[filtered["Cekim"].isin(allowed_cekim)]
    print(f"Cekim filtresi sonrası: {len(filtered)}")

    # One Atilma Tarihi
    if "One Atilma Tarihi" in filtered.columns:
        filtered = filtered[
            filtered.apply(lambda r: check_one_atilma_tarihi_front(r, cfg), axis=1)
        ]
        print(f"One Atilma Tarihi filtresi sonrası: {len(filtered)}")
        
        def is_never_used(val):
            if val is None or pd.isna(val):
                return True
            s = str(val).strip().upper()
            return s in ("", "NAN", "NA", "#N/A", "NAT")
        
        filtered["never_used_first"] = filtered["One Atilma Tarihi"].apply(is_never_used)
        never_used_count = filtered["never_used_first"].sum()
        print(f"  - Hiç kullanılmamış (#N/A): {never_used_count}")
        print(f"  - Tarih bazlı: {len(filtered) - never_used_count}")

    # Min stok
    filtered = filtered[filtered["total_stock"] >= cfg["min_total_stock_front"]]
    print(f"Min toplam stok filtresi sonrası: {len(filtered)}")

    # Beden / stok kombinasyonu
    filtered = filtered[
        filtered.apply(
            lambda r: check_size_stock_rules(r["size_stocks"], cfg["front_size_stock_rules"]),
            axis=1,
        )
    ]
    print(f"Beden/stok kuralı sonrası: {len(filtered)}")

    print(f"Toplam FIRST adayı: {len(filtered)}")
    return filtered


def filter_back_products(unique_products: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    print("\n--- BACK ürün havuzu filtreleniyor ---")
    filtered = unique_products.copy()
    initial = len(filtered)

    filtered = filtered[
        filtered.apply(
            lambda r: check_yazlik_kislik(
                r, cfg["use_yazlik_back"], cfg["use_kislik_back"]
            ),
            axis=1,
        )
    ]
    print(f"Yazlık/Kışlık filtresi sonrası: {len(filtered)} (çıkan: {initial - len(filtered)})")

    allowed_cekim = [c.upper() for c in cfg["allowed_cekim_back"]]
    filtered = filtered[filtered["Cekim"].isin(allowed_cekim)]
    print(f"Cekim filtresi sonrası: {len(filtered)}")

    filtered = filtered[filtered["total_stock"] >= cfg["min_total_stock_back"]]
    print(f"Min toplam stok filtresi sonrası: {len(filtered)}")

    filtered = filtered[
        filtered.apply(
            lambda r: check_size_stock_rules(r["size_stocks"], cfg["back_size_stock_rules"]),
            axis=1,
        )
    ]
    print(f"Beden/stok kuralı sonrası: {len(filtered)}")

    print(f"Toplam BACK adayı: {len(filtered)}")
    return filtered


# ============================================================
# 7. Önceliklendirme ve gün içi kısıtlar
# ============================================================

def prioritize_products(products: pd.DataFrame, cfg: dict, mode_key: str) -> pd.DataFrame:
    """
    Prioritize products based on global prioritization settings.
    
    Uses new prioritization switches:
    - prioritize_by_newness: sort by year digit + sequence number
    - prioritize_by_stock: sort by total stock (per-kisakodrenk)
    - prioritize_never_used_first: prioritize products never used as FIRST (One Atilma Tarihi = #N/A)
    
    If only one is selected, use that as primary sort key.
    If both or neither selected, use legacy mode_key behavior.
    """
    prioritize_newness = cfg.get("prioritize_by_newness", False)
    prioritize_stock = cfg.get("prioritize_by_stock", False)
    prioritize_never_used = cfg.get("prioritize_never_used_first", True)
    
    if prioritize_newness and not prioritize_stock:
        sort_keys = ["season_digit", "season_seq", "total_stock"]
        ascending = [False, False, False]
    elif prioritize_stock and not prioritize_newness:
        sort_keys = ["total_stock", "season_digit", "season_seq"]
        ascending = [False, False, False]
    else:
        mode = cfg.get(mode_key, "stock_then_newest")
        if mode == "stock_then_newest":
            sort_keys = ["total_stock", "season_digit", "season_seq"]
            ascending = [False, False, False]
        elif mode == "newest_then_stock":
            sort_keys = ["season_digit", "season_seq", "total_stock"]
            ascending = [False, False, False]
        else:
            return products.reset_index(drop=True)
    
    if mode_key == "priority_mode_front" and "never_used_first" in products.columns and prioritize_never_used:
        sort_keys = ["never_used_first"] + sort_keys
        ascending = [False] + ascending
    
    return products.sort_values(by=sort_keys, ascending=ascending).reset_index(drop=True)


def check_per_day_constraints(day_posts, cfg: dict, is_final_check: bool = False):
    """
    day_posts: aynı güne ait post listesi (sırayla).
    Her post: {"first_product": {...}, ...}
    """
    if not day_posts:
        return True, []

    violations = []

    first_products = [p["first_product"] for p in day_posts]

    # 1) Ardışık aynı UrunCinsi
    max_consecutive_uc = cfg["max_same_uruncinsi_in_a_row_per_day"]
    if max_consecutive_uc >= 0:
        current = None
        consecutive = 0
        for product in first_products:
            uc = product.get("UrunCinsi")
            if uc == current:
                consecutive += 1
                if consecutive > max_consecutive_uc:
                    violations.append(
                        f"Aynı UrunCinsi ardışık sayısı {consecutive} > {max_consecutive_uc}"
                    )
                    break
            else:
                current = uc
                consecutive = 0

    # 2) Ardışık aynı renk
    max_consecutive_color = cfg["max_same_color_in_a_row_per_day"]
    if max_consecutive_color >= 0:
        current = None
        consecutive = 0
        for product in first_products:
            renk = product.get("Renk")
            if renk == current:
                consecutive += 1
                if consecutive > max_consecutive_color:
                    violations.append(
                        f"Aynı renk ardışık sayısı {consecutive} > {max_consecutive_color}"
                    )
                    break
            else:
                current = renk
                consecutive = 0

    # Final kontrolde minimum distinct UrunCinsi / renk
    if is_final_check:
        min_distinct_uc = cfg.get("min_distinct_uruncinsi_per_day", 0)
        if min_distinct_uc > 0:
            distinct_uc = len({p.get("UrunCinsi") for p in first_products})
            if distinct_uc < min_distinct_uc:
                violations.append(
                    f"Farklı UrunCinsi sayısı {distinct_uc} < minimum istenen {min_distinct_uc}"
                )

        min_distinct_color = cfg.get("min_distinct_color_per_day", 0)
        if min_distinct_color > 0:
            distinct_colors = len({p.get("Renk") for p in first_products})
            if distinct_colors < min_distinct_color:
                violations.append(
                    f"Farklı renk sayısı {distinct_colors} < minimum istenen {min_distinct_color}"
                )

    return len(violations) == 0, violations


# ============================================================
# 8. FIRST ürünlerin atanması
# ============================================================

def assign_preferred_first_products(calendar, first_candidates: pd.DataFrame, cfg: dict, used_first_kisakodrenk: set):
    """
    Assign preferred FIRST products to their designated slots.
    Returns (posts, updated_used_set)
    """
    def norm_day(s):
        """Normalize Turkish day name to canonical form"""
        if not s:
            return ""
        s_normalized = str(s).strip().upper()
        
        day_map = {
            "PAZARTESI": "Pazartesi",
            "SALI": "Salı",
            "ÇARŞAMBA": "Çarşamba",
            "PERŞEMBE": "Perşembe",
            "CUMA": "Cuma",
            "CUMARTESI": "Cumartesi",
            "PAZAR": "Pazar",
        }
        
        return day_map.get(s_normalized, str(s).strip())
    
    def norm_time(t):
        """Normalize time to HH:MM string format with zero-padded hours - handles edge cases"""
        if not t:
            return ""
        if isinstance(t, str):
            t_str = t.strip()
            try:
                t_str = t_str.replace("-", ":").replace(".", ":").replace(" ", "")
                
                parts = t_str.split(":")
                if len(parts) >= 2:
                    hour = int(parts[0])
                    minute = int(parts[1])
                    hour = max(0, min(23, hour))
                    minute = max(0, min(59, minute))
                    return f"{hour:02d}:{minute:02d}"
                elif len(parts) == 1:
                    hour = int(parts[0])
                    hour = max(0, min(23, hour))
                    return f"{hour:02d}:00"
                return t_str
            except:
                return t_str
        try:
            return t.strftime("%H:%M")
        except:
            return str(t).strip()
    
    preferred_products = cfg.get("preferred_first_products", [])
    if not preferred_products:
        return [], used_first_kisakodrenk
    
    print(f"\nTercihli FIRST ürünler atanıyor... ({len(preferred_products)} adet)")
    posts = []
    
    day_slots = {}
    day_time_slots = {}
    for slot in calendar:
        day_name = norm_day(slot.get("day_name"))
        time = norm_time(slot.get("time"))
        if day_name not in day_slots:
            day_slots[day_name] = []
        day_slots[day_name].append(slot)
        key = (day_name, time)
        if key not in day_time_slots:
            day_time_slots[key] = []
        day_time_slots[key].append(slot)
    
    print(f"  Takvimde {len(calendar)} slot var")
    print(f"  İlk 5 slot: {list(day_time_slots.keys())[:5]}")
    
    for i, pref in enumerate(preferred_products, 1):
        kisakodrenk = pref.get("kisakodrenk", "").strip().upper()
        if not kisakodrenk:
            continue
        
        pref_gun = norm_day(pref.get("gun", ""))
        pref_time = norm_time(pref.get("time", ""))
        
        print(f"\n  Tercihli ürün {i}: {kisakodrenk}")
        print(f"    İstenen gün: '{pref_gun}', saat: '{pref_time}'")
        
        matching_products = first_candidates[
            first_candidates["kisakodrenk"].str.upper() == kisakodrenk
        ]
        
        if matching_products.empty:
            print(f"    ❌ Stok dosyasında bulunamadı veya FIRST kriterlerini karşılamıyor")
            continue
        
        print(f"    ✓ FIRST havuzunda bulundu")
        product = matching_products.iloc[0]
        
        if pref_gun and pref_time:
            slot_key = (pref_gun, pref_time)
            print(f"    Aranan slot key: {slot_key}")
            if slot_key not in day_time_slots or not day_time_slots[slot_key]:
                available_times = []
                if pref_gun in day_slots:
                    available_times = [norm_time(s.get("time")) for s in day_slots[pref_gun][:5]]
                print(f"    ❌ Slot bulunamadı: {pref_gun} {pref_time}")
                if available_times:
                    print(f"    Mevcut saatler: {available_times}")
                continue
            
            slot = day_time_slots[slot_key][0]
            post = {
                "day_name": slot["day_name"],
                "time": slot["time"],
                "date": slot.get("date"),
                "first_product": product.to_dict(),
                "is_preferred": True,
                "preferred_gun": pref_gun,
                "preferred_time": pref_time,
            }
            posts.append(post)
            used_first_kisakodrenk.add(kisakodrenk)
            print(f"    ✓ ATANDI: {pref_gun} {pref_time}")
        
        elif pref_gun:
            if pref_gun not in day_slots or not day_slots[pref_gun]:
                print(f"    ❌ Gün bulunamadı: {pref_gun}")
                print(f"    Mevcut günler: {list(day_slots.keys())[:7]}")
                continue
            
            slot = day_slots[pref_gun][0]
            post = {
                "day_name": slot["day_name"],
                "time": slot["time"],
                "date": slot.get("date"),
                "first_product": product.to_dict(),
                "is_preferred": True,
                "preferred_gun": pref_gun,
                "preferred_time": None,
            }
            posts.append(post)
            used_first_kisakodrenk.add(kisakodrenk)
            print(f"    ✓ ATANDI: {pref_gun} (herhangi bir saat)")
        
        else:
            post = {
                "day_name": None,
                "time": None,
                "date": None,
                "first_product": product.to_dict(),
                "is_preferred": True,
                "preferred_gun": None,
                "preferred_time": None,
                "needs_slot_assignment": True,
            }
            posts.append(post)
            used_first_kisakodrenk.add(kisakodrenk)
            print(f"    ✓ İŞARETLENDİ (slot atanacak)")
    
    print(f"\n  Toplam {len(posts)} tercihli ürün atandı/işaretlendi")
    return posts, used_first_kisakodrenk


def assign_first_products(calendar, first_candidates: pd.DataFrame, cfg: dict, decide=None):
    print("\nFIRST ürünler post slotlarına atanıyor...")

    first_candidates = prioritize_products(first_candidates, cfg, "priority_mode_front")
    
    used_first_kisakodrenk = set()
    preferred_posts, used_first_kisakodrenk = assign_preferred_first_products(
        calendar, first_candidates, cfg, used_first_kisakodrenk
    )
    
    print(f"\n🔍 Tercihli ürün ataması sonrası:")
    print(f"  Toplam tercihli post: {len(preferred_posts)}")
    
    posts_with_slots = [p for p in preferred_posts if not p.get("needs_slot_assignment")]
    posts_needing_slots = [p for p in preferred_posts if p.get("needs_slot_assignment")]
    
    print(f"  Slot'u olan: {len(posts_with_slots)}")
    print(f"  Slot bekleyen: {len(posts_needing_slots)}")
    
    occupied_slots = {(p["day_name"], p["time"]) for p in posts_with_slots}
    print(f"  Dolu slot sayısı: {len(occupied_slots)}")
    
    available_slots = [s for s in calendar if (s["day_name"], s["time"]) not in occupied_slots]
    print(f"  Kalan boş slot: {len(available_slots)}")

    posts = list(posts_with_slots)
    
    for pref_post in posts_needing_slots:
        if available_slots:
            slot = available_slots.pop(0)
            pref_post["day_name"] = slot["day_name"]
            pref_post["time"] = slot["time"]
            pref_post["date"] = slot.get("date")
            del pref_post["needs_slot_assignment"]
            posts.append(pref_post)
            print(f"  ✓ Tercihli ürün ({pref_post['first_product']['kisakodrenk']}) atandı: {slot['day_name']} {slot['time']}")
        else:
            print(f"  Uyarı: Tercihli ürün ({pref_post['first_product']['kisakodrenk']}) için boş slot bulunamadı")
    
    kisakod_last_day_index = {}
    min_gap_days = cfg.get("same_kisakod_min_gap_days", 0)
    print(f"🔍 DEBUG: same_kisakod_min_gap_days in assignment = {min_gap_days}")
    
    from product_helpers import is_black_color
    max_black_per_day = cfg.get("max_black_first_per_day", 0)
    black_count_per_day = {}
    
    max_kisakod_uses = cfg.get("max_first_uses_per_kisakod", 0)
    kisakod_first_usage_count = {}

    # Gün bazında slotları grupla (sadece available_slots kullan)
    day_slots = {}
    for slot in available_slots:
        day_name = slot["day_name"]
        day_slots.setdefault(day_name, []).append(slot)

    # available_slots sırasına göre günler
    ordered_days = []
    for slot in available_slots:
        if slot["day_name"] not in ordered_days:
            ordered_days.append(slot["day_name"])

    for day_index, day_name in enumerate(ordered_days):
        slots = day_slots[day_name]
        day_posts = []

        for slot in slots:
            assigned = False
            attempts = 0
            max_attempts = len(first_candidates)
            for idx, product in first_candidates.iterrows():
                attempts += 1
                if attempts > max_attempts:
                    print(f"  ⚠️ Max attempts ({max_attempts}) reached for slot {day_name} {slot['time']}")
                    break
                kisakodrenk = product["kisakodrenk"]
                if kisakodrenk in used_first_kisakodrenk:
                    continue
                
                kisakod = product["KisaKod"]
                if kisakod in kisakod_last_day_index:
                    last_day_idx = kisakod_last_day_index[kisakod]
                    days_since = day_index - last_day_idx
                    if days_since < min_gap_days:
                        continue
                
                if max_kisakod_uses > 0:
                    current_uses = kisakod_first_usage_count.get(kisakod, 0)
                    if current_uses >= max_kisakod_uses:
                        continue
                
                renk = product.get("Renk", "")
                if max_black_per_day > 0 and is_black_color(renk):
                    current_black = black_count_per_day.get(day_name, 0)
                    if current_black >= max_black_per_day:
                        continue

                test_post = {
                    "day_name": day_name,
                    "time": slot["time"],
                    "first_product": product.to_dict(),
                }
                test_day_posts = day_posts + [test_post]

                is_valid, _ = check_per_day_constraints(test_day_posts, cfg, is_final_check=False)
                if is_valid:
                    posts.append(test_post)
                    day_posts.append(test_post)
                    used_first_kisakodrenk.add(kisakodrenk)
                    kisakod_last_day_index[kisakod] = day_index
                    
                    kisakod_first_usage_count[kisakod] = kisakod_first_usage_count.get(kisakod, 0) + 1
                    
                    if is_black_color(renk):
                        black_count_per_day[day_name] = black_count_per_day.get(day_name, 0) + 1
                    
                    assigned = True
                    break

            if not assigned:
                print(f"  Uyarı: {day_name} {slot['time']} için FIRST ürün bulunamadı.")

        # Gün sonunda final kontrol ve repair denemesi
        ok, violations = check_per_day_constraints(day_posts, cfg, is_final_check=True)
        if not ok:
            print(f"\n  [GÜNSEL KISIT] {day_name} için min-distinct kuralları sağlanamadı, repair deneniyor...")
            
            for attempt in range(min(3, len(day_posts))):
                if attempt >= len(day_posts):
                    break
                    
                slot_idx = len(day_posts) - 1 - attempt
                old_post = day_posts[slot_idx]
                old_kisakodrenk = old_post["first_product"]["kisakodrenk"]
                old_kisakod = old_post["first_product"]["KisaKod"]
                
                for idx, product in first_candidates.iterrows():
                    kisakodrenk = product["kisakodrenk"]
                    if kisakodrenk in used_first_kisakodrenk:
                        continue
                    
                    kisakod = product["KisaKod"]
                    if kisakod in kisakod_last_day_index:
                        last_day_idx = kisakod_last_day_index[kisakod]
                        days_since = day_index - last_day_idx
                        if days_since < min_gap_days:
                            continue
                    
                    test_day_posts = day_posts.copy()
                    test_post = {
                        "day_name": day_name,
                        "time": old_post["time"],
                        "first_product": product.to_dict(),
                    }
                    test_day_posts[slot_idx] = test_post
                    
                    is_valid, _ = check_per_day_constraints(test_day_posts, cfg, is_final_check=True)
                    if is_valid:
                        day_posts[slot_idx] = test_post
                        used_first_kisakodrenk.remove(old_kisakodrenk)
                        used_first_kisakodrenk.add(kisakodrenk)
                        
                        if old_kisakod in kisakod_last_day_index and kisakod_last_day_index[old_kisakod] == day_index:
                            del kisakod_last_day_index[old_kisakod]
                        kisakod_last_day_index[kisakod] = day_index
                        
                        for i, p in enumerate(posts):
                            if p["day_name"] == day_name and p["time"] == old_post["time"]:
                                posts[i] = test_post
                                break
                        
                        print(f"    → Repair başarılı: {old_post['time']} slotu güncellendi")
                        ok = True
                        break
                
                if ok:
                    break
            
            if not ok:
                ok_final, violations_final = check_per_day_constraints(day_posts, cfg, is_final_check=True)
                if not ok_final:
                    reason_text = f"{day_name} günü için günlük kısıtlar sağlanamıyor:\n"
                    for v in violations_final:
                        reason_text += f"  - {v}\n"
                    reason_text += "\nBu günlük kısıtları karşılayamıyorum."
                    
                    if decide:
                        if not decide(reason_text):
                            return []
                    else:
                        if not ask_best_effort_or_abort(reason_text):
                            return []

    preferred_count = sum(1 for p in posts if p.get("is_preferred"))
    print(f"\nToplam atanan FIRST post sayısı: {len(posts)}")
    print(f"  Bunlardan {preferred_count} tanesi tercihli ürün")
    if preferred_count > 0:
        print(f"  Tercihli ürünler: {[p['first_product']['kisakodrenk'] for p in posts if p.get('is_preferred')]}")
    return posts


def check_advanced_first_constraints(posts, cfg: dict, decide) -> bool:
    """
    Check advanced FIRST-only constraints after assignment.
    
    These rules are enforced as hard constraints:
    - max_black_first_per_day: Max black FIRST products per day
    - max_first_uses_per_kisakod: Max FIRST uses per KisaKod
    
    If either rule is violated, show best-effort dialog and allow user to abort.
    
    Args:
        posts: List of posts with assigned FIRST products
        cfg: Configuration dict
        decide: Callback function for best-effort dialog
        
    Returns:
        True if constraints pass or user accepts best-effort mode
        False if user chooses to abort
    """
    from validator import compute_black_first_counts_by_day, compute_first_uses_per_kisakod
    
    max_black_per_day = cfg.get("max_black_first_per_day", 0)
    max_kisakod_uses = cfg.get("max_first_uses_per_kisakod", 0)
    
    if max_black_per_day == 0 and max_kisakod_uses == 0:
        return True
    
    violations = []
    
    if max_black_per_day > 0:
        black_counts = compute_black_first_counts_by_day(posts)
        for day_name, count in black_counts.items():
            if count > max_black_per_day:
                violations.append(f"Günlük SİYAH FIRST limiti aşıldı: {day_name} günü {count} adet (limit: {max_black_per_day})")
    
    if max_kisakod_uses > 0:
        kisakod_counts = compute_first_uses_per_kisakod(posts)
        for kisakod, count in kisakod_counts.items():
            if count > max_kisakod_uses:
                violations.append(f"KisaKod FIRST kullanım limiti aşıldı: {kisakod} {count} kez kullanıldı (limit: {max_kisakod_uses})")
    
    # If no violations, return True
    if not violations:
        return True
    
    violation_msg = "\n".join(violations)
    full_msg = f"Gelişmiş FIRST kuralları ihlal edildi:\n\n{violation_msg}\n\nBu ayarlarla plan oluşturulamıyor. Best-effort yöntemle devam etmek ister misiniz?"
    
    user_choice = decide(full_msg)
    
    if user_choice:
        print("\n⚠️  Best-effort modunda devam ediliyor (Gelişmiş FIRST kuralları gevşetildi)")
        return True
    else:
        print("\n❌ Plan oluşturma iptal edildi (Gelişmiş FIRST kuralları karşılanamadı)")
        return False


# ============================================================
# 9. BACK ürünlerin atanması
# ============================================================

def assign_back_products(posts, back_candidates: pd.DataFrame, cfg: dict):
    print("\nBACK ürünler atanıyor...")

    back_candidates = prioritize_products(back_candidates, cfg, "priority_mode_back")

    used_back_kisakodrenk = set()

    first_kisakod_counts = Counter(p["first_product"]["KisaKod"] for p in posts)
    multi_first_kisakod = {k for k, v in first_kisakod_counts.items() if v > 1}

    for post in posts:
        first_product = post["first_product"]
        first_kisakod = first_product["KisaKod"]
        first_uruncinsi = first_product["UrunCinsi"]
        first_kisakodrenk = first_product["kisakodrenk"]

        back_list = []

        # a) Aynı KisaKod'un diğer renkleri
        same_kisakod = back_candidates[
            (back_candidates["KisaKod"] == first_kisakod)
            & (back_candidates["kisakodrenk"] != first_kisakodrenk)
        ]

        for _, prod in same_kisakod.iterrows():
            kr = prod["kisakodrenk"]
            if first_kisakod not in multi_first_kisakod:
                if kr in used_back_kisakodrenk:
                    continue
            back_list.append(prod.to_dict())
            used_back_kisakodrenk.add(kr)
            if len(back_list) >= 9:
                break

        # b) Aynı UrunCinsi (farklı KisaKod)
        if len(back_list) < 9:
            same_uruncinsi = back_candidates[
                (back_candidates["UrunCinsi"] == first_uruncinsi)
                & (back_candidates["KisaKod"] != first_kisakod)
            ]
            
            kisakod_order = []
            seen_kisakod = set()
            for kk in same_uruncinsi["KisaKod"].tolist():
                if kk not in seen_kisakod:
                    seen_kisakod.add(kk)
                    kisakod_order.append(kk)
            
            for kk in kisakod_order:
                group = same_uruncinsi[same_uruncinsi["KisaKod"] == kk]
                for _, prod in group.iterrows():
                    kr = prod["kisakodrenk"]
                    if kr in used_back_kisakodrenk:
                        continue
                    back_list.append(prod.to_dict())
                    used_back_kisakodrenk.add(kr)
                    if len(back_list) >= 9:
                        break
                if len(back_list) >= 9:
                    break

        # c) Geri kalan herhangi uygun ürün
        if len(back_list) < 9:
            for _, prod in back_candidates.iterrows():
                kr = prod["kisakodrenk"]
                if kr == first_kisakodrenk:
                    continue
                if kr in used_back_kisakodrenk:
                    continue
                back_list.append(prod.to_dict())
                used_back_kisakodrenk.add(kr)
                if len(back_list) >= 9:
                    break

        post["back_products"] = back_list

        if len(back_list) < 9:
            print(
                f"  Uyarı: {post['day_name']} {post['time']} için sadece {len(back_list)} BACK ürün bulunabildi."
            )

    print(f"Unique arka ürün sayısı: {len(used_back_kisakodrenk)}")
    return posts


# ============================================================
# 10. Kısıt analizi & NOS/DVM kontrolü
# ============================================================

def run_constraint_analyzer(calendar, first_candidates: pd.DataFrame, back_candidates: pd.DataFrame, cfg: dict, unique_products: pd.DataFrame = None, decide=None) -> bool:
    print("\n" + "=" * 70)
    print("KISIT ANALİZİ")
    print("=" * 70)

    total_posts = len(calendar)
    required_first = total_posts
    required_back = total_posts * 9

    available_first = len(first_candidates)
    available_back = len(back_candidates)

    print(f"Toplam post slotu: {total_posts}")
    print(f"Gerekli FIRST adedi: {required_first}, aday FIRST sayısı: {available_first}")
    print(f"Gerekli BACK adedi:  {required_back}, aday BACK sayısı:  {available_back}")

    if available_first >= required_first and available_back >= required_back:
        print("\n✓ Aday sayıları, teorik olarak yeterli görünüyor.")
        return True

    try:
        from constraint_analyzer import analyze_constraints
        violations, suggestions, message = analyze_constraints(
            calendar, first_candidates, back_candidates, cfg, unique_products
        )
        text = message + "\n\nBest-effort yöntemiyle devam etmek ister misiniz?"
    except Exception as e:
        print(f"Uyarı: Constraint analyzer hatası: {e}")
        reason_lines = [
            "Aday ürün sayıları bazı kısıtları karşılamıyor:",
            f"- FIRST aday sayısı: {available_first} (gereken: {required_first})",
            f"- BACK  aday sayısı: {available_back} (gereken: {required_back})",
            "",
            "Öneriler (manuel olarak kriterleri güncellerken kullanabilirsin):",
            f"- min_total_stock_front değerini biraz düşürmeyi deneyebilirsin. (şu an: {cfg.get('min_total_stock_front', 'N/A')})",
            f"- min_total_stock_back değerini biraz düşürmeyi deneyebilirsin. (şu an: {cfg.get('min_total_stock_back', 'N/A')})",
            "- Yazlık + Kışlık filtrelerini genişletebilirsin (use_yazlik_*/use_kislik_*).",
            "- Beden/stok kurallarını (front/back_size_stock_rules) biraz gevşetebilirsin.",
        ]
        text = "\n".join(reason_lines)
    
    if decide:
        return decide(text)
    return ask_best_effort_or_abort(text)


def check_weekly_nos_dvm(posts, cfg: dict, first_candidates: pd.DataFrame, calendar=None, back_candidates: pd.DataFrame = None, unique_products: pd.DataFrame = None, decide=None) -> bool:
    # Plandaki distinct kisakodrenk
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

    # Havuzda mevcut adaylar
    nos_first_pool = {
        r["kisakodrenk"]
        for _, r in first_candidates.iterrows()
        if r.get("Nos", "") == "E"
    }
    dvm_first_pool = {
        r["kisakodrenk"]
        for _, r in first_candidates.iterrows()
        if r.get("DVM", "") == "DVM"
    }

    min_nos = cfg.get("min_nos_front", 0)
    min_dvm = cfg.get("min_dvm_front", 0)

    print("\nPlana dair NOS/DVM özet:")
    print(f"NOS='E' FIRST (distinct kisakodrenk) sayısı planda: {len(nos_first_plan)} (hedef: {min_nos})")
    print(f"DVM='DVM' FIRST (distinct kisakodrenk) sayısı planda: {len(dvm_first_plan)} (hedef: {min_dvm})")

    # Eğer hedefler zaten tutuyorsa sorun yok
    if len(nos_first_plan) >= min_nos and len(dvm_first_plan) >= min_dvm:
        return True

    try:
        from constraint_analyzer import analyze_constraints
        violations, suggestions, message = analyze_constraints(
            calendar or [], first_candidates, back_candidates or pd.DataFrame(), 
            cfg, unique_products, posts
        )
        text = message + "\n\nBest-effort yöntemiyle devam etmek ister misiniz?"
    except Exception as e:
        print(f"Uyarı: Constraint analyzer hatası: {e}")
        reason_lines = ["NOS/DVM FIRST minimumu tam karşılanamıyor:", ""]
        if len(nos_first_plan) < min_nos:
            reason_lines.append(f"- NOS hedefi karşılanamadı: {len(nos_first_plan)} < {min_nos}")
            reason_lines.append(
                f"  (Havuzda NOS='E' FIRST adayı sayısı: {len(nos_first_pool)})"
            )
        if len(dvm_first_plan) < min_dvm:
            reason_lines.append(f"- DVM hedefi karşılanamadı: {len(dvm_first_plan)} < {min_dvm}")
            reason_lines.append(
                f"  (Havuzda DVM='DVM' FIRST adayı sayısı: {len(dvm_first_pool)})"
            )
        text = "\n".join(reason_lines)
    
    if decide:
        return decide(text)
    return ask_best_effort_or_abort(text)


# ============================================================
# 11. Dışa aktarma ve özet
# ============================================================

def build_first_kriter_detay_sheet(posts, cfg: dict, raw_df: pd.DataFrame) -> pd.DataFrame:
    """
    Build FIRST_Kriter_Detay sheet with detailed criteria for each FIRST product.
    One row per FIRST product (per post).
    """
    print("\nFIRST_Kriter_Detay sheet oluşturuluyor...")
    
    rows = []
    
    # Compute One Atilma Tarihi threshold
    one_atilma_threshold = None
    ref_date_str = cfg.get("one_atilma_reference_date")
    min_days = cfg.get("one_atilma_min_days")
    
    if ref_date_str and min_days:
        try:
            ref_date = None
            for fmt in ["%Y-%m-%d", "%d.%m.%Y"]:
                try:
                    ref_date = datetime.strptime(ref_date_str, fmt)
                    break
                except:
                    continue
            
            if ref_date:
                one_atilma_threshold = ref_date - timedelta(days=int(min_days))
            else:
                print(f"⚠️  Uyarı: One Atilma Tarihi referans tarihi ayrıştırılamadı: {ref_date_str}")
        except Exception as e:
            print(f"⚠️  Uyarı: One Atilma Tarihi hesaplaması başarısız: {e}")
    
    for post in posts:
        first = post["first_product"]
        kisakodrenk = first["kisakodrenk"]
        
        row = {
            "PostGunu": post["day_name"],
            "PostSaati": post["time"],
            "KisaKod": first["KisaKod"],
            "Renk": first["Renk"],
            "UrunCinsi": first["UrunCinsi"],
            "IlkUrunToplamStok": first["total_stock"],
            "Tercihli": "Evet" if post.get("is_preferred") else "Hayır",
            "Tercihli_Gun": post.get("preferred_gun", ""),
            "Tercihli_Saat": post.get("preferred_time", ""),
            "Tercihli_Durum": "SUCCESS" if post.get("is_preferred") else "N/A",
        }
        
        # 1.1 One Atilma Tarihi
        if one_atilma_threshold:
            row["Beklenen_OneAtilmaTarihi"] = one_atilma_threshold.strftime("%Y-%m-%d")
            
            one_atilma_val = first.get("One Atilma Tarihi")
            if one_atilma_val is None or pd.isna(one_atilma_val):
                row["Gerceklesen_OneAtilma"] = "Atılmamış"
                row["OneAtilma_Kriter_Status"] = "OK"
            else:
                s = str(one_atilma_val).strip().upper()
                if s in ("", "NAN", "NA", "#N/A", "NAT", "#YOK"):
                    row["Gerceklesen_OneAtilma"] = "Atılmamış"
                    row["OneAtilma_Kriter_Status"] = "OK"
                else:
                    try:
                        one_date = pd.to_datetime(one_atilma_val, dayfirst=True, errors='coerce')
                        if pd.isna(one_date):
                            row["Gerceklesen_OneAtilma"] = "Atılmamış"
                            row["OneAtilma_Kriter_Status"] = "OK"
                        else:
                            days_diff = (one_atilma_threshold - one_date).days
                            row["Gerceklesen_OneAtilma"] = f"{one_date.strftime('%Y-%m-%d')} ({days_diff} gün önce)"
                            row["OneAtilma_Kriter_Status"] = "OK" if one_date < one_atilma_threshold else "FAILED"
                    except:
                        row["Gerceklesen_OneAtilma"] = "Atılmamış"
                        row["OneAtilma_Kriter_Status"] = "OK"
        else:
            row["Beklenen_OneAtilmaTarihi"] = "N/A"
            row["Gerceklesen_OneAtilma"] = "N/A"
            row["OneAtilma_Kriter_Status"] = "N/A"
        
        min_stock_first = cfg.get("min_total_stock_front", 0)
        row["Beklenen_MinToplamStok_FIRST"] = min_stock_first
        row["Gerceklesen_ToplamStok_FIRST"] = first["total_stock"]
        row["ToplamStok_Status"] = "OK" if first["total_stock"] >= min_stock_first else "FAILED"
        
        product_sizes = raw_df[raw_df["kisakodrenk"] == kisakodrenk]
        beden_sayisi = len(product_sizes)
        row["Beden_Sayisi"] = beden_sayisi
        
        size_rules = cfg.get("front_size_stock_rules", [])
        applicable_rule = None
        
        # size_rules is a list of (size_count, y, z) tuples
        # Find the rule with the largest size_count that is <= beden_sayisi
        if isinstance(size_rules, list):
            for item in size_rules:
                if isinstance(item, (list, tuple)) and len(item) == 3:
                    size_count, y, z = item
                    if beden_sayisi >= size_count:
                        applicable_rule = (y, z)
        
        if applicable_rule and isinstance(applicable_rule, (list, tuple)) and len(applicable_rule) == 2:
            min_sizes_with_stock, min_stock_per_size = applicable_rule
            row["Beklenen_Min_Beden_Adedi"] = min_sizes_with_stock
            row["Beklenen_Min_Stok_Per_Beden"] = min_stock_per_size
            
            sizes_with_enough_stock = product_sizes[product_sizes["ToplamStok"] >= min_stock_per_size]
            actual_sizes_count = len(sizes_with_enough_stock)
            row["Gerceklesen_Min_Beden_Adedi"] = actual_sizes_count
            
            if len(sizes_with_enough_stock) > 0:
                row["Gerceklesen_Min_Stok_Per_Beden"] = sizes_with_enough_stock["ToplamStok"].min()
            else:
                row["Gerceklesen_Min_Stok_Per_Beden"] = 0
            
            row["BedenStok_Kriter_Status"] = "OK" if actual_sizes_count >= min_sizes_with_stock else "FAILED"
        else:
            row["Beklenen_Min_Beden_Adedi"] = "N/A"
            row["Beklenen_Min_Stok_Per_Beden"] = "N/A"
            row["Gerceklesen_Min_Beden_Adedi"] = "N/A"
            row["Gerceklesen_Min_Stok_Per_Beden"] = "N/A"
            row["BedenStok_Kriter_Status"] = "N/A"
        
        row["Nos"] = "Evet" if first.get("Nos", "") == "E" else ""
        row["DVM"] = "Evet" if first.get("DVM", "") == "DVM" else ""
        
        cekim_val = first.get("Cekim", "")
        if cekim_val == "EVET":
            row["Cekim"] = "EVET"
        elif cekim_val in ("NA", "#YOK"):
            row["Cekim"] = cekim_val
        else:
            row["Cekim"] = ""
        
        sezon = first.get("Sezon", "")
        use_yazlik = cfg.get("use_yazlik_front", True)
        use_kislik = cfg.get("use_kislik_front", True)
        if use_yazlik and use_kislik:
            row["Mevsim_Filtre_Sonucu"] = "Yazlık/Kışlık"
        elif use_yazlik:
            row["Mevsim_Filtre_Sonucu"] = "Yazlık"
        elif use_kislik:
            row["Mevsim_Filtre_Sonucu"] = "Kışlık"
        else:
            row["Mevsim_Filtre_Sonucu"] = "N/A"
        
        rows.append(row)
    
    return pd.DataFrame(rows)


def build_global_kriter_ozet_sheet(posts, cfg: dict) -> pd.DataFrame:
    """
    Build Global_Kriter_Ozet sheet with global and advanced rules.
    One row per rule.
    """
    print("\nGlobal_Kriter_Ozet sheet oluşturuluyor...")
    
    rows = []
    
    posts_by_day = {}
    for post in posts:
        day_name = post["day_name"]
        posts_by_day.setdefault(day_name, []).append(post)
    
    
    max_consecutive_uruncinsi_config = cfg.get("max_same_uruncinsi_in_a_row_per_day", 0)
    max_consecutive_uruncinsi_actual = 0
    for day_posts in posts_by_day.values():
        consecutive = 1
        max_in_day = 1
        for i in range(1, len(day_posts)):
            if day_posts[i]["first_product"]["UrunCinsi"] == day_posts[i-1]["first_product"]["UrunCinsi"]:
                consecutive += 1
                max_in_day = max(max_in_day, consecutive)
            else:
                consecutive = 1
        max_consecutive_uruncinsi_actual = max(max_consecutive_uruncinsi_actual, max_in_day)
    
    rows.append({
        "Kriter_adi": "Ayni_UrunCinsi_Ardisik_Limit",
        "Beklenen": max_consecutive_uruncinsi_config if max_consecutive_uruncinsi_config > 0 else "0 (No consecutive allowed)",
        "Gerceklesen": max_consecutive_uruncinsi_actual,
        "Status": "OK" if max_consecutive_uruncinsi_config == 0 or max_consecutive_uruncinsi_actual <= max_consecutive_uruncinsi_config else "FAILED"
    })
    
    min_distinct_uruncinsi_config = cfg.get("min_distinct_uruncinsi_per_day", 0)
    min_distinct_uruncinsi_actual = float('inf')
    for day_posts in posts_by_day.values():
        distinct_count = len({p["first_product"]["UrunCinsi"] for p in day_posts})
        min_distinct_uruncinsi_actual = min(min_distinct_uruncinsi_actual, distinct_count)
    if min_distinct_uruncinsi_actual == float('inf'):
        min_distinct_uruncinsi_actual = 0
    
    rows.append({
        "Kriter_adi": "Min_Farkli_UrunCinsi_Gunluk",
        "Beklenen": min_distinct_uruncinsi_config,
        "Gerceklesen": min_distinct_uruncinsi_actual,
        "Status": "OK" if min_distinct_uruncinsi_actual >= min_distinct_uruncinsi_config else "FAILED"
    })
    
    max_consecutive_color_config = cfg.get("max_same_color_in_a_row_per_day", 0)
    max_consecutive_color_actual = 0
    for day_posts in posts_by_day.values():
        consecutive = 1
        max_in_day = 1
        for i in range(1, len(day_posts)):
            if day_posts[i]["first_product"]["Renk"] == day_posts[i-1]["first_product"]["Renk"]:
                consecutive += 1
                max_in_day = max(max_in_day, consecutive)
            else:
                consecutive = 1
        max_consecutive_color_actual = max(max_consecutive_color_actual, max_in_day)
    
    rows.append({
        "Kriter_adi": "Ayni_Renk_Ardisik_Limit",
        "Beklenen": max_consecutive_color_config if max_consecutive_color_config > 0 else "0 (No consecutive allowed)",
        "Gerceklesen": max_consecutive_color_actual,
        "Status": "OK" if max_consecutive_color_config == 0 or max_consecutive_color_actual <= max_consecutive_color_config else "FAILED"
    })
    
    min_distinct_color_config = cfg.get("min_distinct_color_per_day", 0)
    min_distinct_color_actual = float('inf')
    for day_posts in posts_by_day.values():
        distinct_count = len({p["first_product"]["Renk"] for p in day_posts})
        min_distinct_color_actual = min(min_distinct_color_actual, distinct_count)
    if min_distinct_color_actual == float('inf'):
        min_distinct_color_actual = 0
    
    rows.append({
        "Kriter_adi": "Min_Farkli_Renk_Gunluk",
        "Beklenen": min_distinct_color_config,
        "Gerceklesen": min_distinct_color_actual,
        "Status": "OK" if min_distinct_color_actual >= min_distinct_color_config else "FAILED"
    })
    
    
    min_gap_config = cfg.get("same_kisakod_min_gap_days", 0)
    kisakod_day_indices = {}
    day_order = []
    for post in posts:
        if post["day_name"] not in day_order:
            day_order.append(post["day_name"])
    
    min_gap_actual = float('inf')
    for i, post in enumerate(posts):
        kisakod = post["first_product"]["KisaKod"]
        day_idx = day_order.index(post["day_name"])
        
        if kisakod in kisakod_day_indices:
            last_day_idx = kisakod_day_indices[kisakod]
            gap = day_idx - last_day_idx
            min_gap_actual = min(min_gap_actual, gap)
        
        kisakod_day_indices[kisakod] = day_idx
    
    if min_gap_actual == float('inf'):
        min_gap_actual = "N/A"
        gap_status = "N/A"
    else:
        gap_status = "OK" if min_gap_actual >= min_gap_config else "FAILED"
    
    rows.append({
        "Kriter_adi": "Ayni_KisaKod_Min_Ara_Gun",
        "Beklenen": min_gap_config,
        "Gerceklesen": min_gap_actual,
        "Status": gap_status
    })
    
    from validator import compute_first_uses_per_kisakod, compute_black_first_counts_by_day
    
    max_kisakod_uses_config = cfg.get("max_first_uses_per_kisakod", 0)
    kisakod_usage_count = compute_first_uses_per_kisakod(posts)
    max_kisakod_uses_actual = max(kisakod_usage_count.values()) if kisakod_usage_count else 0
    
    rows.append({
        "Kriter_adi": "Ayni_KisaKod_MAX_FIRST_Kullanim",
        "Beklenen": max_kisakod_uses_config if max_kisakod_uses_config > 0 else "0 (No limit on KisaKod uses)",
        "Gerceklesen": max_kisakod_uses_actual,
        "Status": "OK" if max_kisakod_uses_config == 0 or max_kisakod_uses_actual <= max_kisakod_uses_config else "FAILED"
    })
    
    max_black_config = cfg.get("max_black_first_per_day", 0)
    black_counts_by_day = compute_black_first_counts_by_day(posts)
    max_black_actual = max(black_counts_by_day.values()) if black_counts_by_day else 0
    
    rows.append({
        "Kriter_adi": "FIRST_Siyah_Gunluk_Limit",
        "Beklenen": max_black_config if max_black_config > 0 else "0 (No limit on black products)",
        "Gerceklesen": max_black_actual,
        "Status": "OK" if max_black_config == 0 or max_black_actual <= max_black_config else "FAILED"
    })
    
    
    first_stock_target = cfg.get("global_min_first_stock_sum", 0)
    unique_first_kisakodrenk = {p["first_product"]["kisakodrenk"]: p["first_product"]["total_stock"] for p in posts}
    first_stock_actual = sum(unique_first_kisakodrenk.values())
    
    rows.append({
        "Kriter_adi": "First_Stok_Hedefi",
        "Beklenen": first_stock_target,
        "Gerceklesen": first_stock_actual,
        "Status": "OK" if first_stock_actual >= first_stock_target else "FAILED"
    })
    
    total_stock_target = cfg.get("global_min_total_stock_sum", 0)
    unique_all_kisakodrenk = unique_first_kisakodrenk.copy()
    for post in posts:
        for bp in post.get("back_products", []):
            if bp["kisakodrenk"] not in unique_all_kisakodrenk:
                unique_all_kisakodrenk[bp["kisakodrenk"]] = bp["total_stock"]
    total_stock_actual = sum(unique_all_kisakodrenk.values())
    
    rows.append({
        "Kriter_adi": "Tum_Urunler_Stok_Hedefi",
        "Beklenen": total_stock_target,
        "Gerceklesen": total_stock_actual,
        "Status": "OK" if total_stock_actual >= total_stock_target else "FAILED"
    })
    
    prioritize_newness = cfg.get("prioritize_by_newness", False)
    prioritize_stock = cfg.get("prioritize_by_stock", False)
    
    if prioritize_newness and not prioritize_stock:
        expected_priority = "Yeni > Stok"
    elif prioritize_stock and not prioritize_newness:
        expected_priority = "Stok > Yeni"
    else:
        expected_priority = "Serbest"
    
    rows.append({
        "Kriter_adi": "Global_Onceliklendirme",
        "Beklenen": expected_priority,
        "Gerceklesen": expected_priority,
        "Status": "OK"
    })
    
    return pd.DataFrame(rows)


def export_to_excel(posts, cfg: dict, raw_df: pd.DataFrame = None, validation_df=None, relaxations_applied=None) -> pd.DataFrame:
    print("\nExcel çıktısı oluşturuluyor...")

    rows = []
    for post in posts:
        first = post["first_product"]
        first_stock = first["total_stock"]

        rows.append(
            {
                "PostGunu": post["day_name"],
                "PostSaati": post["time"],
                "Sira": 1,
                "KisaKod": first["KisaKod"],
                "Renk": first["Renk"],
                "UrunCinsi": first["UrunCinsi"],
                "IlkUrunToplamStok": first_stock,
                "UrunToplamStok": first_stock,
                "kisakodrenk": first["kisakodrenk"],
            }
        )

        for i, bp in enumerate(post.get("back_products", []), start=2):
            rows.append(
                {
                    "PostGunu": post["day_name"],
                    "PostSaati": post["time"],
                    "Sira": i,
                    "KisaKod": bp["KisaKod"],
                    "Renk": bp["Renk"],
                    "UrunCinsi": bp["UrunCinsi"],
                    "IlkUrunToplamStok": first_stock,
                    "UrunToplamStok": bp["total_stock"],
                    "kisakodrenk": bp["kisakodrenk"],
                }
            )

    df = pd.DataFrame(rows)

    df["day_order"] = df["PostGunu"].apply(lambda d: TURKISH_DAYS.index(d) if d in TURKISH_DAYS else 999)
    df = df.sort_values(["day_order", "PostSaati", "Sira"]).drop(columns=["day_order"])

    output_path = "instagram_haftalik_plan.xlsx"
    
    first_kriter_df = None
    global_kriter_df = None
    relaxations_df = None
    
    if raw_df is not None:
        first_kriter_df = build_first_kriter_detay_sheet(posts, cfg, raw_df)
        global_kriter_df = build_global_kriter_ozet_sheet(posts, cfg)
    
    if relaxations_applied and len(relaxations_applied) > 0:
        relaxation_rows = []
        for sug in relaxations_applied:
            relaxation_rows.append({
                "Rule_Name": sug.get("rule_name", ""),
                "Original_Value": str(sug.get("original_value", "")),
                "Relaxed_Value": str(sug.get("suggested_value", "")),
                "New_Candidate_Count": sug.get("estimated_new_candidates", 0),
                "Applied": "YES"
            })
        relaxations_df = pd.DataFrame(relaxation_rows)
    
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Plan", index=False)
        
        if first_kriter_df is not None:
            first_kriter_df.to_excel(writer, sheet_name="FIRST_Kriter_Detay", index=False)
        
        if global_kriter_df is not None:
            global_kriter_df.to_excel(writer, sheet_name="Global_Kriter_Ozet", index=False)
        
        if relaxations_df is not None:
            relaxations_df.to_excel(writer, sheet_name="Relaxations", index=False)
        
        if validation_df is not None:
            validation_df.to_excel(writer, sheet_name="Kriter_Ozet_Old", index=False)
    
    print(f"Excel dosyası yazıldı: {output_path}")
    print(f"  - Plan: {len(df)} satır")
    if first_kriter_df is not None:
        print(f"  - FIRST_Kriter_Detay: {len(first_kriter_df)} satır")
    if global_kriter_df is not None:
        print(f"  - Global_Kriter_Ozet: {len(global_kriter_df)} satır")
    if relaxations_df is not None:
        print(f"  - Relaxations: {len(relaxations_df)} satır")
    
    return df


def export_to_markdown(posts, cfg: dict):
    print("\nMarkdown çıktısı oluşturuluyor...")

    output_path = "instagram_haftalik_plan.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# Instagram Haftalık Plan\n\n")
        f.write(f"**Oluşturulma:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**Başlangıç günü:** {cfg['plan_start_day_name']}\n\n")
        f.write(f"**Gün sayısı:** {cfg['plan_num_days']}\n\n")
        f.write("---\n\n")

        f.write(
            "| PostGunu | PostSaati | Sira | KisaKod | Renk | UrunCinsi | IlkUrunToplamStok | UrunToplamStok | kisakodrenk |\n"
        )
        f.write(
            "|----------|-----------|------|---------|------|-----------|-------------------|----------------|-------------|\n"
        )

        for post in posts:
            first = post["first_product"]
            first_stock = first["total_stock"]
            f.write(
                f"| {post['day_name']} | {post['time']} | 1 | {first['KisaKod']} | {first['Renk']} | {first['UrunCinsi']} | {first_stock} | {first_stock} | {first['kisakodrenk']} |\n"
            )
            for i, bp in enumerate(post.get("back_products", []), start=2):
                f.write(
                    f"| {post['day_name']} | {post['time']} | {i} | {bp['KisaKod']} | {bp['Renk']} | {bp['UrunCinsi']} | {first_stock} | {bp['total_stock']} | {bp['kisakodrenk']} |\n"
                )

    print(f"Markdown dosyası yazıldı: {output_path}")


def print_summary(posts, cfg: dict, first_candidates: pd.DataFrame, back_candidates: pd.DataFrame):
    print("\n" + "=" * 70)
    print("PLAN ÖZETİ")
    print("=" * 70)

    # Günlere göre post sayısı
    day_counts = Counter(p["day_name"] for p in posts)
    print("\nGünlük post adetleri:")
    for day in TURKISH_DAYS:
        if day in day_counts:
            print(f"  {day}: {day_counts[day]}")

    print(f"\nToplam post sayısı: {len(posts)}")

    distinct_first = len({p["first_product"]["kisakodrenk"] for p in posts})
    distinct_back = set()
    for p in posts:
        for bp in p.get("back_products", []):
            distinct_back.add(bp["kisakodrenk"])
    print(f"\nDistinct FIRST ürün adedi: {distinct_first}")
    print(f"Distinct BACK ürün adedi:  {len(distinct_back)}")

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

    print(f"\nPlan içindeki NOS='E' FIRST (distinct): {len(nos_first_plan)} (hedef: {cfg['min_nos_front']})")
    print(f"Plan içindeki DVM='DVM' FIRST (distinct): {len(dvm_first_plan)} (hedef: {cfg['min_dvm_front']})")

    print("\nAday havuzu büyüklükleri:")
    nos_pool = {
        r["kisakodrenk"]
        for _, r in first_candidates.iterrows()
        if r.get("Nos", "") == "E"
    }
    dvm_pool = {
        r["kisakodrenk"]
        for _, r in first_candidates.iterrows()
        if r.get("DVM", "") == "DVM"
    }
    print(f"  NOS='E' FIRST aday adedi: {len(nos_pool)}")
    print(f"  DVM='DVM' FIRST aday adedi: {len(dvm_pool)}")

    print("\n" + "=" * 70 + "\n")


# ============================================================
# 12. main()
# ============================================================

def main():
    print("=" * 70)
    print("INSTAGRAM WEEKLY POST PLANNER")
    print("=" * 70)

    cfg = DEFAULT_CFG.copy()
    ask_plan_settings(cfg)

    try:
        raw_df = load_stock_data(cfg)
        unique_products = build_unique_products(raw_df)
        calendar = build_post_calendar(cfg)

        first_candidates = filter_first_products(unique_products, cfg)
        back_candidates = filter_back_products(unique_products, cfg)

        if not run_constraint_analyzer(calendar, first_candidates, back_candidates, cfg):
            return

        posts = assign_first_products(calendar, first_candidates, cfg)
        if not posts:
            print("Hiç FIRST ürün atanamadı, plan oluşturulamadı.")
            return

        # Haftalık NOS/DVM hard-kural kontrolü
        if not check_weekly_nos_dvm(posts, cfg, first_candidates):
            return

        posts = assign_back_products(posts, back_candidates, cfg)

        plan_df = export_to_excel(posts, cfg, raw_df)
        export_to_markdown(posts, cfg)
        print_summary(posts, cfg, first_candidates, back_candidates)

        print("\n✓ Plan oluşturma tamamlandı!")
        print("\nOluşturulan planın ilk 20 satırı:")
        print(plan_df.head(20).to_string(index=False))

    except Exception as e:
        print(f"\n✗ Hata oluştu: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
