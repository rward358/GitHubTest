#!/usr/bin/env python3
"""
Analyze a PDF to understand its structure for recipe extraction.
"""

import sys
try:
    import fitz
    import pdfplumber
except ImportError:
    print("Missing dependencies. Install with: pip install PyMuPDF pdfplumber")
    sys.exit(1)

def analyze_pdf(pdf_path):
    """Analyze PDF structure and content."""

    print(f"\n{'='*80}")
    print(f"ANALYZING: {pdf_path}")
    print(f"{'='*80}\n")

    # Get page count
    with pdfplumber.open(pdf_path) as pdf:
        print(f"Total Pages: {len(pdf.pages)}\n")

        # Analyze first page
        print("="*80)
        print("PAGE 1 - Title Analysis")
        print("="*80)

        if len(pdf.pages) > 0:
            page1 = pdf.pages[0]
            text1 = page1.extract_text()
            print("Text content (first 500 chars):")
            print(text1[:500] if text1 else "No text found")
            print()

        # Analyze first page with PyMuPDF for font info
        doc = fitz.open(pdf_path)
        if len(doc) > 0:
            first_page = doc[0]
            blocks = first_page.get_text("dict")["blocks"]

            print("\nFont Analysis (first 10 text blocks):")
            print("-" * 80)
            count = 0
            for block in blocks:
                if "lines" in block and count < 10:
                    for line in block["lines"]:
                        for span in line["spans"]:
                            text = span["text"].strip()
                            if text:
                                font = span.get("font", "")
                                size = span.get("size", 0)
                                y_pos = span.get("bbox", [0, 0, 0, 0])[1]
                                print(f"Text: '{text[:50]}...'")
                                print(f"  Font: {font}, Size: {size:.1f}, Y-pos: {y_pos:.1f}")
                                count += 1
                                if count >= 10:
                                    break

        # Analyze second page
        print("\n" + "="*80)
        print("PAGE 2 - Ingredient Table Analysis")
        print("="*80)

        if len(pdf.pages) > 1:
            page2 = pdf.pages[1]

            # Check for tables
            tables = page2.extract_tables()
            print(f"\nNumber of tables found: {len(tables)}")

            if tables:
                print("\nFirst table structure:")
                print("-" * 80)
                table = tables[0]
                print(f"Table has {len(table)} rows")
                print("\nFirst 5 rows:")
                for i, row in enumerate(table[:5]):
                    print(f"Row {i}: {row}")
            else:
                print("\nNo tables found. Raw text from page 2:")
                print("-" * 80)
                text2 = page2.extract_text()
                print(text2[:800] if text2 else "No text found")
        else:
            print("\nPDF has only 1 page")

        doc.close()

    print("\n" + "="*80)
    print("Analysis Complete")
    print("="*80)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python analyze_pdf.py <path_to_pdf>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    analyze_pdf(pdf_path)
