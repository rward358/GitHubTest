#!/usr/bin/env python3
"""
PDF Recipe Database Extractor
Extracts recipes, ingredients, and images from PDF files and creates a searchable database.
"""

import os
import json
import sqlite3
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import argparse

try:
    import fitz  # PyMuPDF
except ImportError:
    print("PyMuPDF (fitz) not installed. Install with: pip install PyMuPDF")
    fitz = None

try:
    import pdfplumber
except ImportError:
    print("pdfplumber not installed. Install with: pip install pdfplumber")
    pdfplumber = None

from PIL import Image
import io


class RecipeExtractor:
    """Extracts recipes from PDF files."""

    def __init__(self, output_dir: str = "extracted_recipes"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.images_dir = self.output_dir / "images"
        self.images_dir.mkdir(exist_ok=True)

    @staticmethod
    def sanitize_filename(name: str) -> str:
        """Convert a title to a safe filename."""
        # Remove or replace invalid filename characters
        name = re.sub(r'[<>:"/\\|?*]', '', name)
        # Replace spaces and multiple spaces with single underscore
        name = re.sub(r'\s+', '_', name.strip())
        # Limit length
        name = name[:100]
        return name or "untitled_recipe"

    def extract_title_from_first_page(self, pdf_path: str) -> str:
        """
        Extract the recipe title from the first page.
        Looks for bold text at the top of the page.
        """
        if not fitz:
            # Fallback to simple text extraction
            return self._extract_title_fallback(pdf_path)

        try:
            doc = fitz.open(pdf_path)
            if len(doc) == 0:
                doc.close()
                return "Untitled Recipe"

            first_page = doc[0]

            # Method 1: Look for bold text using font information
            blocks = first_page.get_text("dict")["blocks"]
            bold_texts = []

            for block in blocks:
                if "lines" in block:
                    for line in block["lines"]:
                        for span in line["spans"]:
                            text = span["text"].strip()
                            font = span.get("font", "").lower()
                            size = span.get("size", 0)

                            # Check if font is bold (contains "bold" in name)
                            # and text is substantial (not just punctuation)
                            if text and len(text) > 3:
                                is_bold = "bold" in font or "heavy" in font or "black" in font
                                is_large = size > 12  # Larger font size

                                if is_bold or is_large:
                                    y_position = span.get("bbox", [0, 0, 0, 0])[1]
                                    bold_texts.append({
                                        'text': text,
                                        'size': size,
                                        'y_pos': y_position,
                                        'is_bold': is_bold
                                    })

            # Sort by y-position (top to bottom) and size (largest first)
            if bold_texts:
                bold_texts.sort(key=lambda x: (x['y_pos'], -x['size']))
                # Get the first (topmost, largest) bold text
                title = bold_texts[0]['text']
                doc.close()
                return title

            # Method 2: Fallback - get first substantial line
            text = first_page.get_text()
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            if lines:
                # Find first line that's not too short or too long
                for line in lines[:5]:  # Check first 5 lines
                    if 5 < len(line) < 100:
                        doc.close()
                        return line

            doc.close()

        except Exception as e:
            print(f"Error extracting title from {pdf_path}: {e}")

        return self._extract_title_fallback(pdf_path)

    def _extract_title_fallback(self, pdf_path: str) -> str:
        """Fallback method to extract title from text."""
        text = self.extract_text_from_pdf(pdf_path)
        lines = [line.strip() for line in text.split('\n') if line.strip()]

        # Get first substantial line
        for line in lines[:5]:
            if 5 < len(line) < 100:
                return line

        return Path(pdf_path).stem.replace('_', ' ').replace('-', ' ')

    def extract_images_from_pdf(self, pdf_path: str, recipe_title: str) -> List[str]:
        """
        Extract the main dish image from a PDF file.

        Filters out small ingredient photos and icons by looking for:
        - Large file size (>50KB indicates a high-quality photo)
        - Reasonable dimensions (minimum 300x300 pixels)
        - Returns only ONE image: the largest (best quality main dish photo)

        The image is named based on the recipe title extracted from the first page.
        """
        if not fitz:
            print("PyMuPDF not available, skipping image extraction")
            return []

        candidate_images = []
        try:
            doc = fitz.open(pdf_path)

            for page_num in range(len(doc)):
                page = doc[page_num]
                image_list = page.get_images()

                for img_index, img in enumerate(image_list):
                    xref = img[0]
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    image_ext = base_image["ext"]

                    # Get image dimensions
                    width = base_image.get("width", 0)
                    height = base_image.get("height", 0)
                    file_size = len(image_bytes)

                    # Filter criteria for main dish photos:
                    # 1. File size > 50KB (filters out small ingredient icons)
                    # 2. Minimum dimensions of 300x300 (ensures reasonable quality)
                    # 3. Not extremely narrow or wide (filters out decorative elements)
                    MIN_SIZE = 50000  # 50KB
                    MIN_DIMENSION = 300
                    aspect_ratio = width / height if height > 0 else 0

                    if (file_size > MIN_SIZE and
                        width >= MIN_DIMENSION and
                        height >= MIN_DIMENSION and
                        0.5 <= aspect_ratio <= 2.0):  # Reasonable aspect ratio

                        # Store with metadata for selection (will save only the largest)
                        candidate_images.append({
                            'bytes': image_bytes,
                            'ext': image_ext,
                            'size': file_size,
                            'width': width,
                            'height': height,
                            'page': page_num
                        })

            doc.close()

            # Select and save only the largest image by file size (best quality main dish photo)
            if candidate_images:
                largest_img = max(candidate_images, key=lambda x: x['size'])

                # Save with recipe title as filename
                image_filename = f"{recipe_title}.{largest_img['ext']}"
                image_path = self.images_dir / image_filename

                with open(image_path, "wb") as img_file:
                    img_file.write(largest_img['bytes'])

                return [str(image_path)]

        except Exception as e:
            print(f"Error extracting images from {pdf_path}: {e}")

        return []

    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extract text content from a PDF file."""
        text = ""

        # Try pdfplumber first (better for structured text)
        if pdfplumber:
            try:
                with pdfplumber.open(pdf_path) as pdf:
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n"
                return text
            except Exception as e:
                print(f"pdfplumber failed for {pdf_path}: {e}")

        # Fallback to PyMuPDF
        if fitz:
            try:
                doc = fitz.open(pdf_path)
                for page in doc:
                    text += page.get_text()
                doc.close()
                return text
            except Exception as e:
                print(f"PyMuPDF failed for {pdf_path}: {e}")

        return text

    @staticmethod
    def parse_ingredient(ingredient_line: str) -> Dict[str, any]:
        """
        Parse an ingredient line to extract quantity, unit, name, and serving size.

        Examples:
        - "200g chicken breast (2P)" -> {quantity: 200, unit: 'g', name: 'chicken breast', servings: 2}
        - "1 cup flour" -> {quantity: 1, unit: 'cup', name: 'flour', servings: None}
        - "2 tbsp olive oil (4P)" -> {quantity: 2, unit: 'tbsp', name: 'olive oil', servings: 4}
        """
        original_text = ingredient_line.strip()

        # Extract serving size (e.g., "2P", "4P")
        servings = None
        servings_match = re.search(r'\((\d+)P\)', original_text, re.IGNORECASE)
        if servings_match:
            servings = int(servings_match.group(1))
            # Remove serving info from line for easier parsing
            ingredient_line = re.sub(r'\(\d+P\)', '', ingredient_line, flags=re.IGNORECASE).strip()

        # Common units (order matters - match longer units first)
        units = [
            'tablespoon', 'tablespoons', 'tbsp', 'tbs',
            'teaspoon', 'teaspoons', 'tsp',
            'cup', 'cups',
            'pound', 'pounds', 'lb', 'lbs',
            'ounce', 'ounces', 'oz',
            'kilogram', 'kilograms', 'kg',
            'gram', 'grams', 'g',
            'milligram', 'milligrams', 'mg',
            'liter', 'liters', 'l',
            'milliliter', 'milliliters', 'ml',
            'fluid ounce', 'fl oz',
            'pint', 'pints', 'pt',
            'quart', 'quarts', 'qt',
            'gallon', 'gallons', 'gal',
            'piece', 'pieces', 'pc',
            'clove', 'cloves',
            'slice', 'slices',
            'pinch', 'dash',
            'handful',
            'bunch'
        ]

        # Pattern to match quantity and unit
        # Supports: "200g", "1 cup", "1/2 cup", "1.5 tbsp", "2-3 cups"
        quantity_pattern = r'^\s*(\d+(?:[\.\/\-]\d+)?)\s*'
        unit_pattern = '|'.join(re.escape(unit) for unit in units)

        quantity = None
        unit = None
        name = ingredient_line

        # Try to match quantity
        qty_match = re.match(quantity_pattern, ingredient_line)
        if qty_match:
            qty_str = qty_match.group(1)
            # Convert fractions and ranges to decimals
            if '/' in qty_str:
                parts = qty_str.split('/')
                quantity = float(parts[0]) / float(parts[1]) if len(parts) == 2 else float(parts[0])
            elif '-' in qty_str:
                parts = qty_str.split('-')
                quantity = sum(float(p) for p in parts) / len(parts)  # Average
            else:
                quantity = float(qty_str)

            # Remove quantity from line
            ingredient_line = ingredient_line[qty_match.end():].strip()

            # Try to match unit
            unit_match = re.match(f'^({unit_pattern})\\b', ingredient_line, re.IGNORECASE)
            if unit_match:
                unit = unit_match.group(1).lower()
                # Remove unit from line
                ingredient_line = ingredient_line[unit_match.end():].strip()

        # The remaining text is the ingredient name
        # Clean up common prefixes
        name = re.sub(r'^(of\s+|to\s+)', '', ingredient_line.strip(), flags=re.IGNORECASE)
        name = name.strip(',;.')

        return {
            'raw_text': original_text,
            'quantity': quantity,
            'unit': unit,
            'name': name or original_text,
            'servings': servings,
            'quantity_per_person': quantity / servings if quantity and servings else None
        }

    def parse_recipe_text(self, text: str) -> Dict[str, any]:
        """Parse recipe text to extract title, ingredients, and instructions."""

        # Clean up text
        text = text.strip()

        # Extract title (usually the first non-empty line or largest heading)
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        title = lines[0] if lines else "Untitled Recipe"

        # Common section headers
        ingredient_headers = [
            r'ingredients?:?',
            r'what you\'?ll need:?',
            r'you\'?ll need:?',
            r'shopping list:?',
            r'supplies:?'
        ]

        instruction_headers = [
            r'instructions?:?',
            r'directions?:?',
            r'method:?',
            r'steps?:?',
            r'preparation:?',
            r'how to make:?'
        ]

        # Find ingredients section
        ingredients = []
        instructions = []

        ingredient_pattern = '|'.join(ingredient_headers)
        instruction_pattern = '|'.join(instruction_headers)

        # Split text into sections
        ingredient_match = re.search(ingredient_pattern, text, re.IGNORECASE)
        instruction_match = re.search(instruction_pattern, text, re.IGNORECASE)

        if ingredient_match and instruction_match:
            # Extract ingredients
            ing_start = ingredient_match.end()
            ing_end = instruction_match.start()
            ingredient_text = text[ing_start:ing_end]

            # Parse individual ingredients
            for line in ingredient_text.split('\n'):
                line = line.strip()
                # Filter out empty lines and section headers
                if line and not re.match(ingredient_pattern, line, re.IGNORECASE):
                    # Remove bullets and numbering
                    line = re.sub(r'^[\d\.\-\*\•]+\s*', '', line)
                    if line:
                        parsed = self.parse_ingredient(line)
                        ingredients.append(parsed)

            # Extract instructions
            inst_start = instruction_match.end()
            instruction_text = text[inst_start:]

            # Parse individual steps
            for line in instruction_text.split('\n'):
                line = line.strip()
                if line and not re.match(instruction_pattern, line, re.IGNORECASE):
                    # Remove bullets and numbering
                    line = re.sub(r'^[\d\.\-\*\•]+\s*', '', line)
                    if line and len(line) > 10:  # Filter very short lines
                        instructions.append(line)
        else:
            # Fallback: try to identify ingredients by patterns
            for line in lines[1:]:  # Skip title
                # Common ingredient patterns (amount + unit + ingredient)
                if re.search(r'\d+\s*(cup|tbsp|tsp|oz|lb|g|kg|ml|l|pound|ounce|tablespoon|teaspoon)', line, re.IGNORECASE):
                    parsed = self.parse_ingredient(line)
                    ingredients.append(parsed)
                elif len(instructions) == 0 and len(line) > 20:
                    # Longer lines are likely instructions
                    instructions.append(line)

        return {
            'title': title,
            'ingredients': ingredients,
            'instructions': instructions,
            'full_text': text
        }

    def process_pdf(self, pdf_path: str) -> Dict[str, any]:
        """Process a single PDF file and extract recipe information."""
        print(f"Processing: {pdf_path}")

        # Extract title from first page (bold text at the top)
        title = self.extract_title_from_first_page(pdf_path)

        # Sanitize title for use as filename
        safe_title = self.sanitize_filename(title)

        # Extract text
        text = self.extract_text_from_pdf(pdf_path)

        # Parse recipe (this may refine the title if needed)
        recipe_data = self.parse_recipe_text(text)

        # Use extracted title if parsing found a different one
        final_title = recipe_data.get('title', title)

        # Extract images using the sanitized title for naming
        images = self.extract_images_from_pdf(pdf_path, safe_title)

        # Combine all data
        recipe = {
            'filename': os.path.basename(pdf_path),
            'title': final_title,
            'ingredients': recipe_data.get('ingredients', []),
            'instructions': recipe_data.get('instructions', []),
            'main_image': images[0] if images else None,
            'all_images': images,
            'full_text': recipe_data.get('full_text', '')
        }

        return recipe

    def process_folder(self, folder_path: str) -> List[Dict]:
        """Process all PDF files in a folder."""
        folder = Path(folder_path)
        pdf_files = list(folder.glob("*.pdf")) + list(folder.glob("*.PDF"))

        if not pdf_files:
            print(f"No PDF files found in {folder_path}")
            return []

        print(f"Found {len(pdf_files)} PDF files")

        recipes = []
        for pdf_file in pdf_files:
            try:
                recipe = self.process_pdf(str(pdf_file))
                recipes.append(recipe)
            except Exception as e:
                print(f"Error processing {pdf_file}: {e}")

        return recipes


class RecipeDatabase:
    """Manages the recipe database."""

    def __init__(self, db_path: str = "recipes.db"):
        self.db_path = db_path
        self.conn = None
        self.create_database()

    def create_database(self):
        """Create the SQLite database schema."""
        self.conn = sqlite3.connect(self.db_path)
        cursor = self.conn.cursor()

        # Create recipes table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS recipes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT,
                title TEXT NOT NULL,
                main_image TEXT,
                full_text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create ingredients table with parsed data
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ingredients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recipe_id INTEGER,
                raw_text TEXT NOT NULL,
                ingredient_name TEXT,
                quantity REAL,
                unit TEXT,
                servings INTEGER,
                quantity_per_person REAL,
                FOREIGN KEY (recipe_id) REFERENCES recipes (id)
            )
        ''')

        # Create instructions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS instructions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recipe_id INTEGER,
                step_number INTEGER,
                instruction TEXT NOT NULL,
                FOREIGN KEY (recipe_id) REFERENCES recipes (id)
            )
        ''')

        # Create images table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recipe_id INTEGER,
                image_path TEXT,
                FOREIGN KEY (recipe_id) REFERENCES recipes (id)
            )
        ''')

        self.conn.commit()

    def add_recipe(self, recipe: Dict):
        """Add a recipe to the database."""
        cursor = self.conn.cursor()

        # Insert recipe
        cursor.execute('''
            INSERT INTO recipes (filename, title, main_image, full_text)
            VALUES (?, ?, ?, ?)
        ''', (
            recipe['filename'],
            recipe['title'],
            recipe.get('main_image'),
            recipe.get('full_text', '')
        ))

        recipe_id = cursor.lastrowid

        # Insert ingredients
        for ingredient in recipe.get('ingredients', []):
            cursor.execute('''
                INSERT INTO ingredients (
                    recipe_id, raw_text, ingredient_name, quantity,
                    unit, servings, quantity_per_person
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                recipe_id,
                ingredient.get('raw_text', ''),
                ingredient.get('name', ''),
                ingredient.get('quantity'),
                ingredient.get('unit'),
                ingredient.get('servings'),
                ingredient.get('quantity_per_person')
            ))

        # Insert instructions
        for idx, instruction in enumerate(recipe.get('instructions', []), 1):
            cursor.execute('''
                INSERT INTO instructions (recipe_id, step_number, instruction)
                VALUES (?, ?, ?)
            ''', (recipe_id, idx, instruction))

        # Insert images
        for image_path in recipe.get('all_images', []):
            cursor.execute('''
                INSERT INTO images (recipe_id, image_path)
                VALUES (?, ?)
            ''', (recipe_id, image_path))

        self.conn.commit()

    def add_recipes(self, recipes: List[Dict]):
        """Add multiple recipes to the database."""
        for recipe in recipes:
            self.add_recipe(recipe)

    def export_to_json(self, output_file: str = "recipes.json"):
        """Export the entire database to JSON."""
        cursor = self.conn.cursor()

        # Get all recipes
        cursor.execute('SELECT * FROM recipes')
        recipes_data = []

        for row in cursor.fetchall():
            recipe_id, filename, title, main_image, full_text, created_at = row

            # Get ingredients with parsed data
            cursor.execute('''
                SELECT raw_text, ingredient_name, quantity, unit, servings, quantity_per_person
                FROM ingredients WHERE recipe_id = ?
            ''', (recipe_id,))
            ingredients = [{
                'raw_text': r[0],
                'name': r[1],
                'quantity': r[2],
                'unit': r[3],
                'servings': r[4],
                'quantity_per_person': r[5]
            } for r in cursor.fetchall()]

            # Get instructions
            cursor.execute('SELECT instruction FROM instructions WHERE recipe_id = ? ORDER BY step_number', (recipe_id,))
            instructions = [r[0] for r in cursor.fetchall()]

            # Get images
            cursor.execute('SELECT image_path FROM images WHERE recipe_id = ?', (recipe_id,))
            images = [r[0] for r in cursor.fetchall()]

            recipes_data.append({
                'id': recipe_id,
                'filename': filename,
                'title': title,
                'main_image': main_image,
                'ingredients': ingredients,
                'instructions': instructions,
                'images': images,
                'created_at': created_at
            })

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(recipes_data, f, indent=2, ensure_ascii=False)

        print(f"Exported {len(recipes_data)} recipes to {output_file}")

    def create_ingredient_table(self, output_file: str = "ingredient_table.json"):
        """
        Create a comprehensive ingredient table showing all ingredients
        across all recipes with amounts per person.
        """
        cursor = self.conn.cursor()

        # Get all unique ingredient names
        cursor.execute('''
            SELECT DISTINCT LOWER(TRIM(ingredient_name)) as ingredient
            FROM ingredients
            WHERE ingredient_name IS NOT NULL AND ingredient_name != ''
            ORDER BY ingredient
        ''')

        unique_ingredients = [r[0] for r in cursor.fetchall()]

        # Build table data
        ingredient_table = {}

        for ingredient in unique_ingredients:
            # Get all recipes that use this ingredient
            cursor.execute('''
                SELECT r.title, i.quantity, i.unit, i.servings, i.quantity_per_person, i.raw_text
                FROM ingredients i
                JOIN recipes r ON i.recipe_id = r.id
                WHERE LOWER(TRIM(i.ingredient_name)) = ?
            ''', (ingredient,))

            recipes_data = []
            for row in cursor.fetchall():
                recipe_title, quantity, unit, servings, qty_per_person, raw_text = row
                recipes_data.append({
                    'recipe': recipe_title,
                    'quantity': quantity,
                    'unit': unit,
                    'servings': servings,
                    'quantity_per_person': qty_per_person,
                    'raw_text': raw_text
                })

            if recipes_data:
                ingredient_table[ingredient] = recipes_data

        # Export to JSON
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(ingredient_table, f, indent=2, ensure_ascii=False)

        print(f"\nIngredient table created: {output_file}")
        print(f"Total unique ingredients: {len(ingredient_table)}")

        return ingredient_table

    def print_ingredient_table(self):
        """Print a formatted ingredient table to console."""
        cursor = self.conn.cursor()

        # Get all unique ingredient names
        cursor.execute('''
            SELECT DISTINCT LOWER(TRIM(ingredient_name)) as ingredient
            FROM ingredients
            WHERE ingredient_name IS NOT NULL AND ingredient_name != ''
            ORDER BY ingredient
        ''')

        unique_ingredients = [r[0] for r in cursor.fetchall()]

        print("\n" + "="*80)
        print("INGREDIENT TABLE - Amounts Per Person")
        print("="*80)

        for ingredient in unique_ingredients:
            # Get all recipes that use this ingredient
            cursor.execute('''
                SELECT r.title, i.quantity, i.unit, i.servings, i.quantity_per_person
                FROM ingredients i
                JOIN recipes r ON i.recipe_id = r.id
                WHERE LOWER(TRIM(i.ingredient_name)) = ?
            ''', (ingredient,))

            recipes = cursor.fetchall()
            if recipes:
                print(f"\n{ingredient.upper()}:")
                for recipe_title, quantity, unit, servings, qty_per_person in recipes:
                    if qty_per_person:
                        print(f"  {recipe_title}: {qty_per_person:.2f} {unit or ''} per person " +
                              f"(Total: {quantity} {unit or ''} for {servings}P)")
                    elif quantity and unit:
                        print(f"  {recipe_title}: {quantity} {unit}")
                    else:
                        print(f"  {recipe_title}: (quantity not specified)")

        print("\n" + "="*80)

    def export_ingredient_csv(self, output_file: str = "ingredients.csv"):
        """Export ingredients table to CSV format."""
        import csv

        cursor = self.conn.cursor()

        # Get all ingredients with recipe info
        cursor.execute('''
            SELECT r.title, i.ingredient_name, i.quantity, i.unit,
                   i.servings, i.quantity_per_person, i.raw_text
            FROM ingredients i
            JOIN recipes r ON i.recipe_id = r.id
            WHERE i.ingredient_name IS NOT NULL AND i.ingredient_name != ''
            ORDER BY i.ingredient_name, r.title
        ''')

        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([
                'Ingredient', 'Recipe', 'Quantity', 'Unit',
                'Servings', 'Quantity Per Person', 'Raw Text'
            ])

            for row in cursor.fetchall():
                writer.writerow(row)

        print(f"Ingredient CSV exported: {output_file}")

    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()


def main():
    parser = argparse.ArgumentParser(description='Extract recipes from PDF files')
    parser.add_argument('folder', help='Folder containing PDF recipe files')
    parser.add_argument('--output-dir', default='extracted_recipes', help='Output directory for extracted data')
    parser.add_argument('--db', default='recipes.db', help='Database file name')
    parser.add_argument('--export-json', action='store_true', help='Export database to JSON')
    parser.add_argument('--ingredient-table', action='store_true', help='Create ingredient table with per-person amounts')
    parser.add_argument('--ingredient-csv', action='store_true', help='Export ingredients to CSV')
    parser.add_argument('--print-table', action='store_true', help='Print ingredient table to console')

    args = parser.parse_args()

    # Check if required libraries are available
    if not fitz and not pdfplumber:
        print("Error: Neither PyMuPDF nor pdfplumber is installed.")
        print("Install with: pip install PyMuPDF pdfplumber")
        return

    # Create extractor
    extractor = RecipeExtractor(output_dir=args.output_dir)

    # Process PDFs
    print(f"Processing PDFs from: {args.folder}")
    recipes = extractor.process_folder(args.folder)

    if not recipes:
        print("No recipes extracted")
        return

    print(f"\nExtracted {len(recipes)} recipes")

    # Create database
    db = RecipeDatabase(db_path=args.db)
    db.add_recipes(recipes)

    print(f"\nRecipes saved to database: {args.db}")

    # Export to JSON if requested
    if args.export_json:
        json_file = args.db.replace('.db', '.json')
        db.export_to_json(json_file)

    # Create ingredient table if requested
    if args.ingredient_table:
        db.create_ingredient_table('ingredient_table.json')

    # Export to CSV if requested
    if args.ingredient_csv:
        db.export_ingredient_csv('ingredients.csv')

    # Print ingredient table if requested
    if args.print_table:
        db.print_ingredient_table()

    # Print summary
    print("\n=== Summary ===")
    for recipe in recipes:
        print(f"\nTitle: {recipe['title']}")
        print(f"  Ingredients: {len(recipe['ingredients'])}")
        print(f"  Instructions: {len(recipe['instructions'])}")
        print(f"  Main Image: {recipe['main_image'] or 'None'}")

    db.close()
    print("\nDone!")


if __name__ == "__main__":
    main()
