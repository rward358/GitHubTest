#!/usr/bin/env python3
"""
Example usage of the Recipe Extractor library
"""

from recipe_extractor import RecipeExtractor, RecipeDatabase


def example_basic_usage():
    """Basic example: Extract recipes from a folder"""

    # Create extractor
    extractor = RecipeExtractor(output_dir="my_extracted_recipes")

    # Process all PDFs in a folder
    recipes = extractor.process_folder("./recipe_pdfs")

    # Create database and add recipes
    db = RecipeDatabase(db_path="my_recipes.db")
    db.add_recipes(recipes)

    # Export to JSON
    db.export_to_json("my_recipes.json")

    db.close()

    print(f"Processed {len(recipes)} recipes!")


def example_single_file():
    """Example: Process a single PDF file"""

    extractor = RecipeExtractor()

    # Process single file
    recipe = extractor.process_pdf("./recipe_pdfs/chocolate_cake.pdf")

    print(f"Recipe: {recipe['title']}")
    print(f"Ingredients: {len(recipe['ingredients'])}")
    print(f"Instructions: {len(recipe['instructions'])}")

    # Add to database
    db = RecipeDatabase()
    db.add_recipe(recipe)
    db.close()


def example_query_database():
    """Example: Query the recipe database"""
    import sqlite3

    conn = sqlite3.connect('recipes.db')
    cursor = conn.cursor()

    # Get all recipe titles
    cursor.execute("SELECT id, title FROM recipes")
    recipes = cursor.fetchall()

    print("All Recipes:")
    for recipe_id, title in recipes:
        print(f"  {recipe_id}: {title}")

    # Get ingredients for first recipe
    if recipes:
        recipe_id = recipes[0][0]
        cursor.execute("""
            SELECT ingredient FROM ingredients
            WHERE recipe_id = ?
        """, (recipe_id,))

        ingredients = cursor.fetchall()
        print(f"\nIngredients for '{recipes[0][1]}':")
        for ing in ingredients:
            print(f"  - {ing[0]}")

    # Search recipes by ingredient
    search_term = "chocolate"
    cursor.execute("""
        SELECT DISTINCT r.title
        FROM recipes r
        JOIN ingredients i ON r.id = i.recipe_id
        WHERE i.ingredient LIKE ?
    """, (f'%{search_term}%',))

    results = cursor.fetchall()
    print(f"\nRecipes containing '{search_term}':")
    for title in results:
        print(f"  - {title[0]}")

    conn.close()


def example_custom_parsing():
    """Example: Process and manually adjust recipe data"""

    extractor = RecipeExtractor()
    recipe = extractor.process_pdf("./recipe_pdfs/my_recipe.pdf")

    # Manually adjust if automatic parsing missed something
    recipe['title'] = "My Custom Recipe Title"
    recipe['ingredients'].append("1 cup love")

    # Save to database
    db = RecipeDatabase()
    db.add_recipe(recipe)
    db.close()


if __name__ == "__main__":
    print("Recipe Extractor Examples\n")
    print("Uncomment the example you want to run:\n")

    # Uncomment to run examples:
    # example_basic_usage()
    # example_single_file()
    # example_query_database()
    # example_custom_parsing()

    print("Edit this file to uncomment and run examples!")
