import argparse
import csv
import os
import sys
import zipfile
from pathlib import Path

import django

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myshop.settings')
django.setup()

from books.models import Book  # noqa: E402
from books.utils import fetch_book_cover_urls  # noqa: E402


def normalize_text(value):
    if value is None:
        return ''
    return value.strip()


def normalize_decimal(value):
    if not value:
        return 0
    text = value.replace(' ', '').replace('"', '').replace("'", '')
    text = text.replace(',', '.')
    try:
        return float(text)
    except ValueError:
        return 0


def normalize_int(value):
    if not value:
        return 0
    text = value.replace(' ', '').replace('"', '').replace("'", '').replace(',', '.')
    try:
        return int(round(float(text)))
    except ValueError:
        return 0


def normalize_availability(value):
    if not value:
        return False
    code = value.strip().upper()
    return code in {'S', 'R', 'D', 'Z'}


def load_csv_from_zip(zip_path, encodings=None):
    with zipfile.ZipFile(zip_path) as archive:
        name = archive.namelist()[0]
        raw = archive.open(name).read()

    if encodings is None:
        encodings = ['utf-8', 'cp1250', 'iso-8859-2', 'latin-1']

    text = None
    for encoding in encodings:
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue

    if text is None:
        text = raw.decode('utf-8', errors='replace')

    lines = text.splitlines()
    reader = csv.DictReader(lines, skipinitialspace=True)
    rows = []
    for row in reader:
        cleaned = {}
        for key, value in row.items():
            if key is None:
                continue
            cleaned_key = normalize_text(key)
            cleaned[cleaned_key] = normalize_text(value)
        rows.append(cleaned)
    return rows


def build_record_map(rows, key_name):
    result = {}
    for row in rows:
        key = row.get(key_name)
        if key:
            result[key] = row
    return result


def import_catalogue(catalogue_path, price_path, stock_path):
    catalogue_rows = load_csv_from_zip(catalogue_path, encodings=['cp1250', 'utf-8', 'iso-8859-2', 'latin-1'])
    price_rows = load_csv_from_zip(price_path)
    stock_rows = load_csv_from_zip(stock_path)

    prices = build_record_map(price_rows, 'SORTKOD')
    stocks = build_record_map(stock_rows, 'SORTKOD')

    created = 0
    updated = 0
    skipped = 0

    for row in catalogue_rows:
        sortkod = row.get('SORTKOD')
        if not sortkod:
            skipped += 1
            continue

        title = row.get('SORTNAZEV') or row.get('SORTNAZEV') or ''
        if not title:
            skipped += 1
            continue

        author = row.get('SORTAUTOR') or row.get('SORTAUTOR2') or ''
        author = author.replace(';', ',')

        description = ' '.join(
            part for part in [row.get('SORTPODNAZEV', ''), row.get('ANOTACE', '')] if part
        )

        image_candidates = [row.get('PICTURE'), row.get('PICTURE_SMALL'), row.get('PICTURE_FULL')]
        cover_image = next((img for img in image_candidates if img), '')
        cover_images = [img for img in image_candidates if img]
        publisher = row.get('NAKLADATELSTVI') or row.get('VYDAVATELSTVI') or row.get('NAKLADATEL') or ''
        ean = row.get('EAN', '')
        isbn = row.get('ISBN', '')
        dostupnost = row.get('DOSTUPNOST', '')
        book_type = row.get('SORTDRUH', '')
        category = row.get('SKUPNAZEV', '')

        if not cover_images:
            fallback_images = fetch_book_cover_urls(Book(title=title, author=author, isbn=isbn, ean=ean))
            if fallback_images:
                cover_images = fallback_images
                cover_image = cover_images[0]

        price_row = prices.get(sortkod, {})
        price_value = normalize_decimal(price_row.get('PRODCENA') or price_row.get('AKCECENA') or row.get('CENA'))

        stock_row = stocks.get(sortkod, {})
        stock_qty = normalize_int(
            stock_row.get('MNOZSTVI_CELK') or stock_row.get('MNOZSTVI_KUS') or stock_row.get('MNOZSTVI_KUS')
        )
        has_stock_row = bool(stock_row)
        available = stock_qty > 0
        if not has_stock_row:
            available = normalize_availability(dostupnost)
            if available and stock_qty == 0:
                stock_qty = 1

        if price_value <= 0:
            available = False
            stock_qty = 0

        currency = (price_row.get('MENA') or row.get('MENA') or 'CZK').strip() or 'CZK'

        defaults = {
            'title': title,
            'author': author,
            'description': description,
            'price': price_value,
            'currency': currency,
            'cover_image': cover_image,
            'cover_images': cover_images,
            'publisher': publisher,
            'ean': ean,
            'isbn': isbn,
            'book_type': book_type,
            'category': category,
            'stock': stock_qty,
            'available': available,
        }

        book, created_flag = Book.objects.update_or_create(sortkod=sortkod, defaults=defaults)
        if created_flag:
            created += 1
        else:
            updated += 1

    print(f'Imported {created} new books, updated {updated} existing books, skipped {skipped} rows.')


def main():
    parser = argparse.ArgumentParser(description='Import book catalogue, price, and stock data into Django.')
    parser.add_argument('--catalogue', required=True, help='Path to the catalogue ZIP file')
    parser.add_argument('--price', required=True, help='Path to the price ZIP file')
    parser.add_argument('--stock', required=True, help='Path to the stock ZIP file')

    args = parser.parse_args()
    import_catalogue(args.catalogue, args.price, args.stock)


if __name__ == '__main__':
    main()
