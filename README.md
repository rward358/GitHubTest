# PDF Recipe Database Extractor

A Python tool that automatically extracts recipes, ingredients, images, and instructions from PDF files and creates a comprehensive searchable database.

## Features

- **Automatic PDF Processing**: Scans folders of recipe PDFs
- **Smart Image Extraction**: Extracts the main dish photo while ignoring small ingredient images
  - Filters by size (>50KB) and dimensions (300x300+)
  - Selects the largest, highest-quality image
  - Automatically excludes icons and ingredient photos
- **Text Parsing**: Intelligently parses recipe text to identify:
  - Recipe title
  - Ingredients list
  - Step-by-step instructions
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
```

### Command-line Arguments

- `folder`: **(Required)** Path to folder containing PDF recipe files
- `--output-dir`: Output directory for extracted images (default: `extracted_recipes`)
- `--db`: Database file name (default: `recipes.db`)
- `--export-json`: Export the database to JSON format

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
- `ingredient`: Ingredient text

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
# Process recipes
python recipe_extractor.py ./my_recipe_pdfs --export-json

# Output:
# Processing: ./my_recipe_pdfs/chocolate_cake.pdf
# Processing: ./my_recipe_pdfs/pasta_carbonara.pdf
# Found 2 PDF files
# Extracted 2 recipes
# Recipes saved to database: recipes.db
# Exported 2 recipes to recipes.json
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

# Get all ingredients for a specific recipe
cursor.execute("""
    SELECT i.ingredient
    FROM ingredients i
    JOIN recipes r ON i.recipe_id = r.id
    WHERE r.title = 'Chocolate Cake'
""")
print(cursor.fetchall())

conn.close()
```

## Notes

- The tool works best with well-formatted recipe PDFs
- **Image filtering**: Only extracts large, high-quality images (>50KB, minimum 300x300 pixels)
- **Ignores ingredient photos**: Small ingredient images and icons are automatically filtered out
- The largest image by file size is selected as the main dish photo
- Recipe parsing uses pattern matching to identify ingredient and instruction sections

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