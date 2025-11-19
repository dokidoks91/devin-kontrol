# DEVIN_INSTRUCTIONS.md  
## Full Technical Specification for `instagram_auto_post.py`  
### (Complete System Specification for Devin – 100% Comprehensive Version)

---

# 1. SYSTEM PURPOSE

This system generates a **weekly Instagram post plan** for a Turkish fashion e‑commerce brand.

Each Instagram post contains:

- **1 FIRST (front) product**
- **9 BACK products**

The script builds a weekly plan based on complex business rules involving:

- Stock thresholds  
- Season logic (Yazlık / Kışlık)  
- NOS (E) and DVM (DVM) product requirements  
- Color and category distributions  
- Product usage uniqueness  
- Historical posting gap (“One Atilma Tarihi”)  
- Daily sequencing rules  
- Exception rules for matching KisaKod families  
- Calendar slot filling (12 posts on weekdays, 10 on weekends)  
- Start day and number of days configurable  

The output is:

- `instagram_haftalik_plan.xlsx`  
- `instagram_haftalik_plan.md`

---

# 2. TERMINOLOGY

### **Unique product**
A unique product is always defined as:

```
kisakodrenk = KisaKod + Renk
```

Example:
- KisaKod = “ELB123”
- Renk = “Siyah”

→ unique ID = “ELB123Siyah”

### **Total stock of a unique product**
Sum of `ToplamStok` across all sizes for that exact `kisakodrenk`.

### **Size count**
Count of distinct size rows for that `kisakodrenk`.

### **First product**
The product shown as the first video in a post.

### **Back products**
The 9 products listed after the first one.

---

# 3. FILTERS – FIRST PRODUCT POOL

Below is the **FULL AND STRICT** list of filters for selecting FIRST products.  
Each product must pass **ALL** of them.

---

## 3.1 Yazlık / Kışlık rules (front)

A product is Yazlık OR Kışlık depending on `Sezon` second character:

### **YAZLIK if:**
- `Sezon[1] == 'Y'`
  **OR**
- `Nos == 'E'` (NOS overrides everything)

### **KIŞLIK if:**
- `Sezon[1] != 'Y'`
  **OR**
- `Nos == 'E'`

### **Front-specific switches**
```python
use_yazlik_front = True/False
use_kislik_front = True/False
```
If both False → invalid.

### IMPORTANT:
- `Nos` cell must be normalized via `.str.strip().str.upper()`
- `Nos='E'` **bypasses season** — product is eligible whether or not season matches.

---

## 3.2 `Cekim` filter

```python
allowed_cekim_front = ["EVET", "NA"]
```

Normalize with `.str.strip().str.upper()`.

Excel may contain:
- “Evet”
- “evet”
- “ EVET”
- “na”
- “Na”

All should be matched correctly.

---

## 3.3 Minimum total stock

```python
min_total_stock_front = X   # e.g., 20
```

Unique product total stock must be >= X.

---

## 3.4 Size/stock combination rule

A list of tuples:

```
(required_size_count, min_sizes_with_stock, min_stock_value)
```

Example:
```
front_size_stock_rules = [
  (4, 3, 1),   # if product has 4 sizes → at least 3 sizes must have stock ≥ 1
  (1, 1, 5)    # if product has 1 size → that size must have stock ≥ 5
]
```

A product is eligible if it satisfies **at least one** of the tuples.

---

## 3.5 One Atilma Tarihi (FIRST only)

Two cases allowed:

1. **#N/A** or empty → always allowed
2. **Date value** must be older than:
```
(reference_date - X days)
```
X is configurable (`one_atilma_gap_days = 45`).

Normalization:
- Empty strings
- NaT
- “#N/A”
must all be treated as “never posted → allowed”.

---

## 3.6 Weekly minimum NOS (hard rule)

Distinct FIRST kisakodrenk with:

```
Nos == "E"
```

must be >= `min_nos_front`.

If not enough:
- Script must STOP and ask user:
  - Adjust constraints?
  - Continue in best‑effort mode?

---

## 3.7 Weekly minimum DVM (hard rule)

Distinct FIRST kisakodrenk with:

```
DVM == "DVM"
```

must be >= `min_dvm_front`.

Same enforcement mechanism:
- Ask user if they want best-effort or abort.

---

## 3.8 FIRST product uniqueness per week

Each `kisakodrenk` can be FIRST at most once in the entire plan.

---

## 3.9 Per‑day FIRST product constraints

### **(1) max_same_uruncinsi_in_a_row_per_day**
If set to 0 → same UrunCinsi cannot be used in two consecutive posts that day.

If set to 1 → can appear consecutively twice.

General rule:
```
Count of consecutive same UrunCinsi <= max_same_uruncinsi_in_a_row_per_day
```

### **(2) min_distinct_uruncinsi_per_day**
On each day, distinct FIRST UrunCinsi count >= this value.

### **(3) max_same_color_in_a_row_per_day**
Same logic as UrunCinsi but for Renk.

### **(4) min_distinct_color_per_day**
Distinct daily FONT colors >= this setting.

---

# 4. FILTERS – BACK PRODUCT POOL

Similar to FIRST, but with separate configurations.

---

## 4.1 Yazlık / Kışlık (back)

Uses:

```
use_yazlik_back
use_kislik_back
```

Same logic as front:
- Nos = 'E' bypasses season.

---

## 4.2 `Cekim` filter (back)

Separate allowed values:

```
allowed_cekim_back = ["EVET", "NA"]
```

---

## 4.3 Minimum total stock (back)

```
min_total_stock_back = X
```

---

## 4.4 Back size/stock combination rules

Separate list:

```
back_size_stock_rules = [
   (4, 3, 1),
   (1, 1, 5)
]
```

---

# 5. BACK PRODUCT PLACEMENT LOGIC

For each post:

### Step 1: Place FIRST product in slot 1.

### Step 2: Fill BACK positions 2–10 in this order:

---

## 5.1 SAME KisaKod – use all other colors

Products must:

- Share same KisaKod
- Pass back filters
- Not violate uniqueness (except the special exception below)

Each color is used **once per week**, unless exception applies.

---

## 5.2 SAME UrunCinsi (different KisaKod)

Then choose products whose:
- UrunCinsi == first_product.UrunCinsi
- KisaKod != first_product.KisaKod
- Pass back filters

You can pick multiple KisaKod families here, each offering 1 or more `kisakodrenk`.

---

## 5.3 ANY back candidate

If still not full, pull from global back pool.

---

# 6. GLOBAL UNIQUENESS OF BACK PRODUCTS

### Default rule:
Every unique `kisakodrenk` can be used **once** as BACK throughout the week.

### Exception:
If week contains multiple posts where FIRST products share **the same KisaKod**, then:

For that KisaKod only:
- ALL its eligible colors can be repeated across those posts.

This exception applies only to back items, and only for that KisaKod.

---

# 7. DAILY & WEEKLY CALENDAR

---

## 7.1 Daily post times

### Weekdays (Mon–Fri) → **12 posts/day**
```
09:00
10:30
11:30
12:30
13:30
14:30
15:30
16:30
17:30
19:30
21:00
22:30
```

### Weekend (Sat–Sun) → **10 posts/day**
```
11:00
12:00
13:00
14:00
15:00
16:00
17:00
18:30
19:30
21:00
```

These are **fixed** and must be respected.

---

## 7.2 Start day and number of days

User must be able to configure:

- `start_day_name = "Pazartesi" / "Çarşamba" / etc`
- `num_days = 7` (or any number)

Examples the system must support:

- “Çarşambadan başla ve 4 günlük plan yap”
- “Cumadan başla ve 6 gün sürsün”

---

# 8. BEST-EFFORT DECISION SYSTEM

The script must include:

### `run_constraint_analyzer(front_pool, back_pool, config)`
Detects:

- Not enough FIRST candidates  
- Not enough NOS first  
- Not enough DVM first  
- Not enough BACK candidates  
- Size/stock rules eliminating too many products  
- Yazlık/Kışlık too restrictive  
- Cekim too restrictive  
- Min stock constraints too restrictive  

The analyzer must produce human-friendly messages:

> “Sadece 8 uygun NOS ‘E’ ürünü buldum ama min_nos_front = 12.  
>  Bu kuralı karşılayabilmem için ya min_nos_front’u 8’e indir ya da Yazlık + Kışlık birlikte aktif olsun.”

### `ask_best_effort_or_abort(msg)`
Asks user:

```
Bu kriterler karşılanamıyor. 
(1) Kriteri değiştirmek ister misin?
(2) Best-effort plana devam edilsin mi?
```

Script then follows user's choice.

---

# 9. OUTPUT FORMAT

### For each post row:

| PostGunu | PostSaati | Sira | KisaKod | Renk | UrunCinsi | IlkUrunToplamStok | UrunToplamStok | kisakodrenk |

Two files:

- `instagram_haftalik_plan.xlsx`
- `instagram_haftalik_plan.md`

Markdown table must be GitHub‑renderable.

---

# 10. SCRIPT ARCHITECTURE

### Recommended internal structure:

```
load_excel()
normalize_fields()
build_unique_products()
apply_front_filters()
apply_back_filters()
run_constraint_analyzer()
select_first_products()
distribute_first_products_into_days()
place_back_products()
apply_daily_constraints()
generate_output_files()
```

---

# 11. TEST HARNESS (for Devin)

A synthetic dataframe:

```
[
 {KisaKod:"ELB1", Renk:"Siyah", Sezon:"5Y", Nos:"",   DVM:"",   Cekim:"Evet", ToplamStok:12, Beden:"S"},
 {KisaKod:"ELB1", Renk:"Kırmızı", Sezon:"5Y", Nos:"E", DVM:"",  Cekim:"EVET", ToplamStok:9,  Beden:"M"},
 {KisaKod:"TSH1", Renk:"Beyaz", Sezon:"4K", Nos:"",   DVM:"DVM", Cekim:"Na",   ToplamStok:11, Beden:"L"},
 ...
]
```

Tests:

- Yazlık/Kışlık filter behavior  
- Nos override behavior  
- DVM counting  
- min_total_stock rules  
- size_stock_rules behavior  
- exception for repeated colors of same KisaKod  
- daily constraints (color / uruncinsi repetition)  
- best-effort analyzer  
- start_day_name logic  
- weekend/weekday post count validation  

---

# 12. CHECKLIST FOR DEVIN

Devin must verify:

### **Field normalization**
- Nos, DVM, Cekim stripped + upper  
- Turkish characters preserved  
- No accidental ascii conversion  

### **All filters fully enforced**
- Yazlık/Kışlık front/back separate  
- Cekim front/back separate  
- Min stock front/back  
- Size-stock rules front/back  
- One Atilma Tarihi logic correct  
- FIRST uniqueness correct  
- NOS/DVM weekly HARD enforced  
- Best-effort escalation correct  

### **Back placement**
- Same KisaKod → same-Uruncinsi → global  
- Back uniqueness respected except special KisaKod exception  

### **Day constraints**
- max/min color  
- max/min UrunCinsi  
- Consecutive logic actually implemented  

### **Calendar**
- 12 weekday slots  
- 10 weekend slots  
- Start day offset works  
- num_days works  

### **Output correctness**
- All required columns exist  
- Sorting by day & time correct  

---

# END OF SPEC  
This is the full specification.  
