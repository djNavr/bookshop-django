from django.core.management.base import BaseCommand
from books.models import Book
from books.utils import fetch_book_cover_urls


class Command(BaseCommand):
    help = 'Doplní chybějící obalové obrázky knih z Open Library nebo Google Books.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=0, help='Maximální počet knih ke zpracování.')
        parser.add_argument('--dry-run', action='store_true', help='Neukládat změny, pouze nahlásit, co by se doplnilo.')

    def handle(self, *args, **options):
        queryset = Book.objects.all().order_by('pk')
        limit = options['limit']
        processed = 0
        updated = 0
        skipped = 0

        for book in queryset:
            if book.primary_image:
                skipped += 1
                continue
            if limit and processed >= limit:
                break

            processed += 1
            urls = fetch_book_cover_urls(book)
            if not urls:
                self.stdout.write(self.style.WARNING(f'Nenalezen obrázek pro: {book.title} ({book.pk})'))
                continue

            self.stdout.write(self.style.SUCCESS(f'Nalezeno {len(urls)} obrázků pro: {book.title} ({book.pk})'))
            if not options['dry_run']:
                book.cover_images = urls
                if not book.cover_image:
                    book.cover_image = urls[0]
                book.save(update_fields=['cover_image', 'cover_images'])
                updated += 1

        self.stdout.write(self.style.SUCCESS(
            f'Hotovo: zpracováno {processed}, upraveno {updated}, přeskočeno {skipped}.'
        ))
