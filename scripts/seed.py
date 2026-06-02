import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myshop.settings')
django.setup()

from books.models import Book

SAMPLES = [
    {
        'title': 'The Fresh Start Guide',
        'author': 'A. Writer',
        'description': 'A modern take on starting fresh.',
        'price': '14.99',
        'cover_image': 'https://images.unsplash.com/photo-1524995997946-a1c2e315a42f',
    },
    {
        'title': 'Design Patterns for Readers',
        'author': 'B. Author',
        'description': 'Readable patterns for everyday code.',
        'price': '29.50',
        'cover_image': 'https://images.unsplash.com/photo-1512820790803-83ca734da794',
    },
    {
        'title': 'GraphQL in Practice',
        'author': 'C. Dev',
        'description': 'A practical guide to GraphQL APIs with Django.',
        'price': '24.00',
        'cover_image': 'https://images.unsplash.com/photo-1516979187457-637abb4f9353',
    },
]


def run():
    for data in SAMPLES:
        Book.objects.create(**data)
    print('Seeded sample books')


if __name__ == '__main__':
    run()
