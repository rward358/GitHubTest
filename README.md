# PDF Recipe Database Extractor

A Python tool that automatically extracts recipes, ingredients, images, and instructions from PDF files and creates a comprehensive searchable database.

## Features

- **Automatic PDF Processing**: Scans folders of recipe PDFs
- **Smart Image Extraction**: Extracts exactly ONE main dish photo per recipe
  - Identifies the recipe title from bold text on the first page
  - Names the image file based on the extracted recipe title
  - Filters by size (>50KB) and dimensions (300x300+)
  - Selects the largest, highest-quality image
  - Automatically excludes icons and ingredient photos
- **Text Parsing**: Intelligently parses recipe text to identify:
  - Recipe title from bold text on first page
  - Ingredients from tables on second page
  - Step-by-step instructions
- **Ingredient Analysis**: Advanced ingredient parsing that extracts:
  - Ingredients from tables on page 2 of PDFs
  - Ingredient name
  - Quantity and unit (e.g., "200g", "1 cup")
  - Serving size (e.g., "2P" = 2 people)
  - Automatic calculation of per-person amounts
- **Ingredient Table**: Creates comprehensive tables showing:
  - All ingredients across all recipes
  - Amounts per person for easy comparison
  - Export to JSON and CSV formats
- **Database Creation**: Creates a SQLite database with all extracted information
- **JSON Export**: Option to export the entire database to JSON format
- **Batch Processing**: Process multiple PDFs at once

## Installation

1. Clone this repository:
```bash
git clone <repository-url>
cd GitHubTest
```

2. Install required dependencies:
```bash
pip install -r requirements.txt
```

### Dependencies

- **PyMuPDF** (fitz): For PDF processing and image extraction
- **pdfplumber**: For advanced text extraction
- **Pillow**: For image processing

## Usage

### Basic Usage

Process all PDFs in a folder:

```bash
python recipe_extractor.py /path/to/recipe/pdfs
```

### Advanced Options

```bash
# Specify custom output directory
python recipe_extractor.py /path/to/pdfs --output-dir my_recipes

# Use custom database name
python recipe_extractor.py /path/to/pdfs --db my_recipes.db

# Export to JSON after processing
python recipe_extractor.py /path/to/pdfs --export-json

# Create ingredient table with per-person amounts
python recipe_extractor.py /path/to/pdfs --ingredient-table

# Export ingredients to CSV
python recipe_extractor.py /path/to/pdfs --ingredient-csv

# Print ingredient table to console
python recipe_extractor.py /path/to/pdfs --print-table

# Combine multiple options
python recipe_extractor.py /path/to/pdfs --export-json --ingredient-table --ingredient-csv --print-table
```

### Command-line Arguments

- `folder`: **(Required)** Path to folder containing PDF recipe files
- `--output-dir`: Output directory for extracted images (default: `extracted_recipes`)
- `--db`: Database file name (default: `recipes.db`)
- `--export-json`: Export the database to JSON format
- `--ingredient-table`: Create ingredient table JSON with per-person amounts
- `--ingredient-csv`: Export ingredients to CSV format
- `--print-table`: Print formatted ingredient table to console

## Output Structure

After processing, you'll have:

1. **SQLite Database** (`recipes.db`):
   - `recipes` table: Core recipe information
   - `ingredients` table: Individual ingredients for each recipe
   - `instructions` table: Step-by-step cooking instructions
   - `images` table: All extracted images

2. **Extracted Images** (`extracted_recipes/images/`):
   - Main dish photos from each recipe PDF

3. **JSON Export** (optional):
   - Complete database exported in JSON format

## Database Schema

### recipes
- `id`: Unique recipe identifier
- `filename`: Original PDF filename
- `title`: Recipe title
- `main_image`: Path to main dish photo
- `full_text`: Complete extracted text
- `created_at`: Timestamp

### ingredients
- `id`: Unique identifier
- `recipe_id`: Foreign key to recipes
- `raw_text`: Original ingredient line from PDF
- `ingredient_name`: Parsed ingredient name
- `quantity`: Numeric quantity
- `unit`: Unit of measurement (g, cup, tbsp, etc.)
- `servings`: Number of people (from "2P", "4P" notation)
- `quantity_per_person`: Calculated amount per person

### instructions
- `id`: Unique identifier
- `recipe_id`: Foreign key to recipes
- `step_number`: Order of the step
- `instruction`: Instruction text

### images
- `id`: Unique identifier
- `recipe_id`: Foreign key to recipes
- `image_path`: Path to extracted image

## Example

```bash
# Process recipes with all export options
python recipe_extractor.py ./my_recipe_pdfs --export-json --ingredient-table --print-table

# Output:
# Processing: ./my_recipe_pdfs/chocolate_cake.pdf
# Processing: ./my_recipe_pdfs/pasta_carbonara.pdf
# Found 2 PDF files
# Extracted 2 recipes
# Recipes saved to database: recipes.db
# Exported 2 recipes to recipes.json
# Ingredient table created: ingredient_table.json
# Total unique ingredients: 15
#
# ================================================================================
# INGREDIENT TABLE - Amounts Per Person
# ================================================================================
#
# CHICKEN BREAST:
#   Pasta Carbonara: 100.00 g per person (Total: 200 g for 2P)
#
# FLOUR:
#   Chocolate Cake: 0.50 cup per person (Total: 2 cups for 4P)
# ...
```

## Ingredient Table Format

The ingredient table groups all ingredients across recipes and shows per-person amounts:

**JSON format** (`ingredient_table.json`):
```json
{
  "chicken breast": [
    {
      "recipe": "Pasta Carbonara",
      "quantity": 200,
      "unit": "g",
      "servings": 2,
      "quantity_per_person": 100.0,
      "raw_text": "200g chicken breast (2P)"
    }
  ],
  "flour": [
    {
      "recipe": "Chocolate Cake",
      "quantity": 2,
      "unit": "cup",
      "servings": 4,
      "quantity_per_person": 0.5,
      "raw_text": "2 cups flour (4P)"
    }
  ]
}
```

**CSV format** (`ingredients.csv`):
```
Ingredient,Recipe,Quantity,Unit,Servings,Quantity Per Person,Raw Text
chicken breast,Pasta Carbonara,200,g,2,100.0,200g chicken breast (2P)
flour,Chocolate Cake,2,cup,4,0.5,2 cups flour (4P)
```

## Querying the Database

You can query the SQLite database using any SQLite client or Python:

```python
import sqlite3

conn = sqlite3.connect('recipes.db')
cursor = conn.cursor()

# Find all recipes with "chocolate" in the title
cursor.execute("SELECT title FROM recipes WHERE title LIKE '%chocolate%'")
print(cursor.fetchall())

# Get all ingredients for a specific recipe with amounts
cursor.execute("""
    SELECT ingredient_name, quantity, unit, servings, quantity_per_person
    FROM ingredients i
    JOIN recipes r ON i.recipe_id = r.id
    WHERE r.title = 'Chocolate Cake'
""")
for name, qty, unit, servings, qty_pp in cursor.fetchall():
    print(f"{name}: {qty} {unit} for {servings} people ({qty_pp} {unit} per person)")

# Find all recipes that use a specific ingredient
cursor.execute("""
    SELECT r.title, i.quantity, i.unit, i.quantity_per_person
    FROM recipes r
    JOIN ingredients i ON r.id = i.recipe_id
    WHERE i.ingredient_name LIKE '%chicken%'
""")
print(cursor.fetchall())

# Get average amount per person for a specific ingredient across recipes
cursor.execute("""
    SELECT ingredient_name, AVG(quantity_per_person) as avg_per_person, unit
    FROM ingredients
    WHERE ingredient_name = 'flour' AND quantity_per_person IS NOT NULL
    GROUP BY ingredient_name, unit
""")
print(cursor.fetchall())

conn.close()
```

## Notes

- The tool works best with well-formatted recipe PDFs
- **Recipe structure**: Expects PDFs with:
  - Page 1: Recipe title in bold at the top
  - Page 2: Ingredients table
- **Title extraction**: Automatically identifies the recipe title by looking for bold, large text at the top of the first page
- **Image naming**: Each image is named based on the extracted recipe title (e.g., "Chocolate_Cake.jpg")
- **One image per recipe**: Only the largest, highest-quality image is extracted (>50KB, minimum 300x300 pixels)
- **Ignores ingredient photos**: Small ingredient images and icons are automatically filtered out
- **Ingredient extraction**: Extracts ingredients from tables on page 2 of the PDF
  - Automatically detects and parses table structure
  - Falls back to text parsing if no table found
- **Ingredient parsing**: Supports various formats:
  - "200g chicken breast (2P)" → 100g per person
  - "1 cup flour" → parsed to quantity=1, unit="cup"
  - "1/2 tsp salt" → converts fractions to decimals
  - "2-3 cups rice" → averages ranges
- **Serving notation**: Use "(2P)", "(4P)", etc. in your PDFs to indicate serving sizes
- Recipe parsing uses pattern matching to identify instruction sections

## Troubleshooting

### No text extracted
- Some PDFs may be scanned images. Consider using OCR (pytesseract)
- Ensure PDFs are not password-protected

### Missing dependencies
```bash
pip install --upgrade PyMuPDF pdfplumber Pillow
```

## Future Enhancements

- OCR support for scanned recipe PDFs
- AI-powered recipe parsing using LLMs (OpenAI, Anthropic)
- Nutrition information extraction
- Automatic recipe categorization
- Web interface for browsing recipes

## License

MIT License