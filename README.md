# Instagram Post Planner

A Windows desktop application for generating weekly Instagram post plans for Turkish fashion e-commerce brands. The application applies complex business rules to create optimized posting schedules based on stock data.

## Features

- **Comprehensive GUI Application**: Tabbed interface with 30+ configurable parameters
- **Standalone .exe**: Run on any Windows machine without Python installed
- **Smart Planning**: Applies complex filters for seasonal products, stock levels, NOS/DVM requirements
- **Fully Configurable**: ALL constraints configurable via GUI - no hard-coded values
- **Constraint Validation**: Automatic validation with detailed Kriter_Ozet (Criteria Summary) sheet
- **Smart Suggestions**: Constraint analyzer suggests relaxations when requirements can't be met
- **Dual Output**: Generates both Excel (.xlsx) and Markdown (.md) files
- **Best-Effort Mode**: Continue with partial plans when constraints can't be fully met

## Quick Start

### Option 1: Run with Python (Development)

1. **Install Python 3.8+** from [python.org](https://www.python.org/)

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the comprehensive GUI application (recommended):**
   ```bash
   python gui_app_v2.py
   ```

4. **Or run the simple GUI:**
   ```bash
   python gui_app.py
   ```

5. **Or run the CLI version:**
   ```bash
   python instagram_auto_post.py
   ```

### Option 2: Use Standalone .exe (Windows)

1. **Download** `InstagramPostPlanner.exe` from the releases page (or build it yourself - see below)

2. **Double-click** `InstagramPostPlanner.exe` to launch the GUI

3. **Select your stock file** (stokdosya.xlsx) and configure the plan

4. **Click "Planı Oluştur"** to generate the plan

## Building the Standalone .exe

To build the Windows executable yourself:

1. **Ensure Python 3.8+ is installed** and in your PATH

2. **Run the build script:**
   ```bash
   build_exe.bat
   ```

3. **Find the executable:**
   ```
   dist\InstagramPostPlanner.exe
   ```

4. **Distribute:** Copy `InstagramPostPlanner.exe` to any Windows machine and run it without Python

**Note:** The .exe file will be 80-100MB due to pandas. This is normal and expected.

### Manual Build (Alternative)

If you prefer to build manually:

```bash
pip install pandas openpyxl pyinstaller
pyinstaller --onefile --noconsole --name InstagramPostPlanner --hidden-import openpyxl gui_app.py
```

## Usage

### Comprehensive GUI Application (gui_app_v2.py)

The comprehensive GUI provides full control over all planning parameters through a tabbed interface:

1. **Launch the application** (either `python gui_app_v2.py` or `InstagramPostPlanner.exe`)

2. **Plan Settings Tab:**
   - Select stock Excel file
   - Choose start day (Pazartesi → Pazar)
   - Set number of days (1-7)

3. **FIRST Criteria Tab:**
   - Yazlık/Kışlık filters (checkboxes)
   - Cekim filters (EVET/NA multi-select)
   - One Atilma Tarihi settings (allow #N/A, date T, days X)
   - Minimum total stock
   - Size/stock rules (8 rows: for each size count, set min sizes with stock Y and min stock value Z)
   - Minimum NOS FIRST count
   - Minimum DVM FIRST count

4. **BACK Criteria Tab:**
   - Same configuration options as FIRST, but separate values

5. **Advanced Rules Tab:**
   - Max same UrunCinsi consecutive per day
   - Min distinct UrunCinsi per day
   - Max same color consecutive per day
   - Min distinct color per day
   - Same KisaKod minimum gap days (0-7)

6. **Global Targets Tab:**
   - Minimum total stock sum for all FIRST products
   - Minimum total stock sum for ALL products (FIRST + BACK)

7. **Generate plan:** Click "Planı Oluştur"

8. **View results:** The output area shows progress, validation summary, and constraint analysis. Output files are saved next to your Excel file:
   - `instagram_haftalik_plan.xlsx` (with Plan and Kriter_Ozet sheets)
   - `instagram_haftalik_plan.md`

### Simple GUI Application (gui_app.py)

For basic usage with default constraints:

1. **Launch:** `python gui_app.py` or use the old .exe
2. **Select stock file**
3. **Configure:** Start day, number of days, seasonal modes
4. **Generate plan**

### CLI Application

For command-line usage:

```bash
python instagram_auto_post.py
```

Follow the interactive prompts to configure and generate the plan.

### Programmatic Usage

You can also use the planner module in your own Python scripts:

```python
from planner import run_planner

result = run_planner(
    excel_path="path/to/stokdosya.xlsx",
    start_day="Pazartesi",
    num_days=7,
    mode_front="Her ikisi",
    mode_back="Her ikisi"
)

if result["success"]:
    print(f"Plan created: {result['output_excel']}")
else:
    print(f"Error: {result['error']}")
```

## Output Files

The application generates two output files in the same directory as your input Excel file:

### 1. instagram_haftalik_plan.xlsx

Excel workbook with TWO sheets:

**Sheet 1: Plan**
- **PostGunu**: Day of the week (in Turkish)
- **PostSaati**: Post time
- **Sira**: Position (1 = first product, 2-10 = back products)
- **KisaKod**: Product short code
- **Renk**: Color
- **UrunCinsi**: Product type
- **IlkUrunToplamStok**: First product total stock
- **UrunToplamStok**: Product total stock
- **kisakodrenk**: Unique product identifier (KisaKod + Renk)

**Sheet 2: Kriter_Ozet (Criteria Summary)**
- **Kriter_Adi**: Constraint name
- **Beklenen_Deger**: Expected value
- **Gerceklesen_Deger**: Actual achieved value
- **Durum**: Status (OK / FAILED)
- **Notlar**: Additional notes

This sheet validates all constraints including:
- NOS/DVM minimum counts
- Per-product stock requirements
- Global stock targets (FIRST sum, total sum)
- Per-day distinct UrunCinsi/color requirements
- Uniqueness rules
- Seasonal correctness
- Size/stock rules

### 2. instagram_haftalik_plan.md

Markdown table with the same plan data, suitable for documentation or sharing.

## Business Rules

The planner applies complex business rules including:

- **Seasonal Filters**: Yazlık (summer) / Kışlık (winter) product selection
- **Stock Requirements**: Minimum stock levels and size/stock combinations
- **NOS/DVM Requirements**: Minimum counts for special product categories
- **Daily Constraints**: Max consecutive same category/color, min distinct per day
- **Uniqueness Rules**: Each product used once as FIRST, with exceptions for same KisaKod families
- **Calendar Rules**: 12 posts on weekdays, 10 posts on weekends with specific times
- **One Atilma Tarihi**: Historical posting gap enforcement

For detailed specification, see `DEVIN_INSTRUCTIONS (1).md` and `AUDIT.md`.

## Project Structure

```
devin-kontrol/
├── instagram_auto_post.py    # Core business logic and CLI script
├── planner.py                 # Planning orchestration module
├── config.py                  # Configuration dataclass (Phase 1)
├── validator.py               # Constraint validation module (Phase 2)
├── constraint_analyzer.py     # Constraint analysis and suggestions (Phase 3)
├── gui_app.py                 # Simple Tkinter GUI application
├── gui_app_v2.py              # Comprehensive GUI with all parameters (Phase 1)
├── build_exe.bat              # Windows .exe build script
├── requirements.txt           # Python dependencies
├── stokdosya.xlsx            # Sample stock data file
├── AUDIT.md                   # Comprehensive audit report
├── DEVIN_INSTRUCTIONS (1).md  # Full technical specification
└── README.md                  # This file
```

## Requirements

- **Python**: 3.8 or higher (for development/CLI)
- **Dependencies**: pandas, openpyxl (see requirements.txt)
- **OS**: Windows (for .exe), or any OS with Python for CLI/GUI

## Troubleshooting

### GUI doesn't start

- Ensure Python 3.8+ is installed
- Install dependencies: `pip install -r requirements.txt`
- Try running from command line to see error messages: `python gui_app.py`

### .exe build fails

- Ensure PyInstaller is installed: `pip install pyinstaller`
- Try manual build command (see "Manual Build" section above)
- Check that all dependencies are installed

### Plan generation fails

- Verify your Excel file has all required columns (see specification)
- Check the output area for specific error messages
- Ensure stock data meets minimum requirements (enough products, stock levels, etc.)

### Best-effort prompts

If the planner cannot meet all constraints (e.g., not enough NOS products), it will prompt you:
- **Option 1**: Abort and adjust your constraints
- **Option 2**: Continue with best-effort plan (may not meet all requirements)

## Recent Updates

### Phase 1-3: Comprehensive Configuration System (Latest)

**Phase 1: Full Configuration GUI**
- New `gui_app_v2.py` with tabbed interface for 30+ parameters
- `config.py` module with PlanConfig dataclass
- All constraints now configurable via GUI (no hard-coded values)
- Save/Load configuration to JSON
- 6 tabs: Plan Settings, FIRST Criteria, BACK Criteria, Advanced Rules, Global Targets, Output

**Phase 2: Validation System**
- New `validator.py` module for comprehensive constraint validation
- Kriter_Ozet (Criteria Summary) sheet in Excel output
- Validates: NOS/DVM counts, stock targets, global stock sums, per-day constraints, uniqueness, seasonal correctness, size/stock rules
- Human-readable validation summary in output

**Phase 3: Constraint Analyzer**
- New `constraint_analyzer.py` module for smart suggestions
- Analyzes why constraints fail and suggests specific relaxations
- Data-driven suggestions based on actual pool sizes
- Ready for integration into best-effort dialogs

### Initial Audit and Fixes

See `AUDIT.md` for a comprehensive audit report. Initial fixes included:

1. **Critical runtime bug fix** (merge syntax error)
2. **Cekim filter correction** (now accepts both "EVET" and "NA")
3. **Markdown output fix** (added missing kisakodrenk column)
4. **One Atilma Tarihi improvement** (better NaT/empty handling)
5. **Daily constraints enforcement** (repair mechanism for min-distinct rules)

## License

Copyright © 2025. All rights reserved.

## Support

For issues or questions, please open an issue on the GitHub repository.
