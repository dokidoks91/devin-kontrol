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
    """
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
    excel_path = cfg["stock_excel_path"]

    if not os.path.exists(excel_path):
        alt_path = "instagram_stok.xlsx"
        if os.path.exists(alt_path):
            excel_path = alt_path
        else:
            raise FileNotFoundError(f"Stok dosyası bulunamadı: {excel_path}")

    print(f"Stok verisi yükleniyor: {excel_path}")
    df = pd.read_excel(excel_path, engine="openpyxl")

    # Temel normalize – Türkçe karakterler korunur, sadece bazı kolonlar upper yapılır
    for col in ["KisaKod", "Renk", "UrunCinsi", "Sezon", "Nos", "DVM", "Cekim"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    # NOS, DVM, Cekim, Sezon için uppercase (kıyaslama için)
    if "Nos" in df.columns:
        df["Nos"] = df["Nos"].str.upper()
    if "DVM" in df.columns:
        df["DVM"] = df["DVM"].str.upper()
    if "Cekim" in df.columns:
        df["Cekim"] = df["Cekim"].str.upper()
    if "Sezon" in df.columns:
        df["Sezon"] = df["Sezon"].str.upper()

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

    # Sezon rakamları (5Y131 vs 4K..., vs 3S... gibi)
    def _season_digit(val):
        s = str(val)
        if len(s) >= 1 and s[0].isdigit():
            return int(s[0])
        return 0

    def _season_seq(val):
        s = str(val)
        if len(s) >= 4 and s[-3:].isdigit():
            return int(s[-3:])
        return 0

    unique_products["season_digit"] = unique_products["Sezon"].apply(_season_digit)
    unique_products["season_seq"] = unique_products["Sezon"].apply(_season_seq)

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
        ref_date = datetime.strptime(cfg["one_atilma_reference_date"], "%Y-%m-%d")
        min_days = int(cfg["one_atilma_min_days"])
        threshold = ref_date - timedelta(days=min_days)
        one_date = pd.to_datetime(value)
        return one_date < threshold
    except Exception:
        # Anlaşılmaz tarih varsa, güvenli olmak için GEÇERLİ sayıyoruz
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
    mode = cfg.get(mode_key, "stock_then_newest")
    if mode == "stock_then_newest":
        return products.sort_values(
            by=["total_stock", "season_digit", "season_seq"],
            ascending=[False, False, False],
        ).reset_index(drop=True)
    elif mode == "newest_then_stock":
        return products.sort_values(
            by=["season_digit", "season_seq", "total_stock"],
            ascending=[False, False, False],
        ).reset_index(drop=True)
    else:
        return products.reset_index(drop=True)


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

def assign_first_products(calendar, first_candidates: pd.DataFrame, cfg: dict):
    print("\nFIRST ürünler post slotlarına atanıyor...")

    first_candidates = prioritize_products(first_candidates, cfg, "priority_mode_front")

    posts = []
    used_first_kisakodrenk = set()
    
    kisakod_last_day_index = {}
    min_gap_days = cfg.get("same_kisakod_min_gap_days", 0)

    # Gün bazında slotları grupla
    day_slots = {}
    for slot in calendar:
        day_name = slot["day_name"]
        day_slots.setdefault(day_name, []).append(slot)

    # calendar sırasına göre günler
    ordered_days = []
    for slot in calendar:
        if slot["day_name"] not in ordered_days:
            ordered_days.append(slot["day_name"])

    for day_index, day_name in enumerate(ordered_days):
        slots = day_slots[day_name]
        day_posts = []

        for slot in slots:
            assigned = False
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
                    
                    if not ask_best_effort_or_abort(reason_text):
                        return []

    print(f"\nToplam atanan FIRST post sayısı: {len(posts)}")
    return posts


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
            for _, prod in same_uruncinsi.iterrows():
                kr = prod["kisakodrenk"]
                if kr in used_back_kisakodrenk:
                    continue
                back_list.append(prod.to_dict())
                used_back_kisakodrenk.add(kr)
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
        if str(p["first_product"].get("Nos", "")).upper() == "E"
    }
    dvm_first_plan = {
        p["first_product"]["kisakodrenk"]
        for p in posts
        if str(p["first_product"].get("DVM", "")).upper() == "DVM"
    }

    # Havuzda mevcut adaylar
    nos_first_pool = {
        r["kisakodrenk"]
        for _, r in first_candidates.iterrows()
        if str(r.get("Nos", "")).upper() == "E"
    }
    dvm_first_pool = {
        r["kisakodrenk"]
        for _, r in first_candidates.iterrows()
        if str(r.get("DVM", "")).upper() == "DVM"
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

def export_to_excel(posts, cfg: dict, validation_df=None) -> pd.DataFrame:
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
    
    if validation_df is not None:
        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Plan", index=False)
            validation_df.to_excel(writer, sheet_name="Kriter_Ozet", index=False)
        print(f"Excel dosyası yazıldı: {output_path} (Plan: {len(df)} satır, Kriter_Ozet: {len(validation_df)} satır)")
    else:
        df.to_excel(output_path, index=False, engine="openpyxl")
        print(f"Excel dosyası yazıldı: {output_path} (toplam satır: {len(df)})")
    
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
        if str(p["first_product"].get("Nos", "")).upper() == "E"
    }
    dvm_first_plan = {
        p["first_product"]["kisakodrenk"]
        for p in posts
        if str(p["first_product"].get("DVM", "")).upper() == "DVM"
    }

    print(f"\nPlan içindeki NOS='E' FIRST (distinct): {len(nos_first_plan)} (hedef: {cfg['min_nos_front']})")
    print(f"Plan içindeki DVM='DVM' FIRST (distinct): {len(dvm_first_plan)} (hedef: {cfg['min_dvm_front']})")

    print("\nAday havuzu büyüklükleri:")
    nos_pool = {
        r["kisakodrenk"]
        for _, r in first_candidates.iterrows()
        if str(r.get("Nos", "")).upper() == "E"
    }
    dvm_pool = {
        r["kisakodrenk"]
        for _, r in first_candidates.iterrows()
        if str(r.get("DVM", "")).upper() == "DVM"
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

        plan_df = export_to_excel(posts, cfg)
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
