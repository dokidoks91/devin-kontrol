# Instagram Post Planner

A Windows desktop application for generating weekly Instagram post plans for Turkish fashion e-commerce brands. The application applies complex business rules to create optimized posting schedules based on stock data.

## Features

- **GUI Application**: Easy-to-use Windows interface built with Tkinter
- **Standalone .exe**: Run on any Windows machine without Python installed
- **Smart Planning**: Applies complex filters for seasonal products, stock levels, NOS/DVM requirements
- **Flexible Configuration**: Configurable start day, duration, and seasonal modes
- **Dual Output**: Generates both Excel (.xlsx) and Markdown (.md) files

## Quick Start

### Option 1: Run with Python (Development)

1. **Install Python 3.8+** from [python.org](https://www.python.org/)

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the GUI application:**
   ```bash
   python gui_app.py
   ```

4. **Or run the CLI version:**
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

### GUI Application

1. **Launch the application** (either `python gui_app.py` or `InstagramPostPlanner.exe`)

2. **Select stock file:** Click "Dosya Seç..." and choose your Excel file (stokdosya.xlsx)

3. **Configure plan:**
   - **Plan Başlangıç Günü**: Select starting day (Pazartesi, Salı, etc.)
   - **Kaç Günlük Plan**: Enter number of days (1-7)
   - **Front Ürün Modu**: Select seasonal mode for first products (Yazlık/Kışlık/Her ikisi)
   - **Back Ürün Modu**: Select seasonal mode for back products (Yazlık/Kışlık/Her ikisi)

4. **Generate plan:** Click "Planı Oluştur"

5. **View results:** The output area shows progress and summary. Output files are saved next to your Excel file:
   - `instagram_haftalik_plan.xlsx`
   - `instagram_haftalik_plan.md`

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

Excel spreadsheet with columns:
- **PostGunu**: Day of the week (in Turkish)
- **PostSaati**: Post time
- **Sira**: Position (1 = first product, 2-10 = back products)
- **KisaKod**: Product short code
- **Renk**: Color
- **UrunCinsi**: Product type
- **IlkUrunToplamStok**: First product total stock
- **UrunToplamStok**: Product total stock
- **kisakodrenk**: Unique product identifier (KisaKod + Renk)

### 2. instagram_haftalik_plan.md

Markdown table with the same data, suitable for documentation or sharing.

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
├── instagram_auto_post.py    # Original CLI script with all business logic
├── planner.py                 # Refactored core planning module
├── gui_app.py                 # Tkinter GUI application
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

See `AUDIT.md` for a comprehensive audit report. Recent fixes include:

1. **Critical runtime bug fix** (merge syntax error)
2. **Cekim filter correction** (now accepts both "EVET" and "NA")
3. **Markdown output fix** (added missing kisakodrenk column)
4. **One Atilma Tarihi improvement** (better NaT/empty handling)
5. **Daily constraints enforcement** (repair mechanism for min-distinct rules)

## License

Copyright © 2025. All rights reserved.

## Support

For issues or questions, please open an issue on the GitHub repository.
