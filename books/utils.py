import re
import requests

from django.conf import settings
from django.core.mail import send_mail

from .models import Book, ShopConfig


def verify_address(street: str, city: str, postal_code: str, country: str) -> dict:
    """Verify a postal address using an external service or a local fallback.

    Returns a dictionary with keys:
    - valid: bool
    - message: str
    - warning: Optional[str]
    """
    if not getattr(settings, 'ADDRESS_VERIFICATION_ENABLED', False):
        return {'valid': True, 'message': 'Adresu není nutné ověřovat.'}

    api_url = getattr(settings, 'ADDRESS_VERIFICATION_API_URL', 'mock')
    if api_url == 'mock':
        is_valid = postal_code.isdigit() and len(postal_code) == 5 and bool(street.strip()) and bool(city.strip())
        return {
            'valid': is_valid,
            'message': 'Adresa je formálně v pořádku.' if is_valid else 'České PSČ nebo adresa nejsou ve správném formátu.',
        }

    payload = {
        'street': street,
        'city': city,
        'postal_code': postal_code,
        'country': country,
    }
    headers = {'Content-Type': 'application/json'}
    api_key = getattr(settings, 'ADDRESS_VERIFICATION_API_KEY', None)
    if api_key:
        headers['Authorization'] = f'Bearer {api_key}'

    try:
        response = requests.post(api_url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        return {
            'valid': bool(data.get('valid', False)),
            'message': data.get('message', 'Adresa nebyla ověřena.'),
            'warning': data.get('warning'),
        }
    except requests.RequestException as exc:
        return {
            'valid': False,
            'message': f'Nelze ověřit adresu: {exc}',
        }


def _normalize_image_url(url):
    if not url:
        return None
    return url.strip()


def _safe_request_json(url, params=None, headers=None):
    try:
        response = requests.get(url, params=params or {}, headers=headers or {}, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return None


PEMIC_ANNOTATION_PATTERN = re.compile(r'https?://(?:www\.)?pemic-books\.cz/ASPX/Annotation\.aspx', re.IGNORECASE)


def _is_pemic_annotation_url(url):
    return bool(url and PEMIC_ANNOTATION_PATTERN.search(url))


def _safe_request_text(url, headers=None):
    try:
        response = requests.get(url, headers=headers or {}, timeout=10)
        response.raise_for_status()
        text = response.text or ''
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text or None
    except requests.RequestException:
        return None


def _looks_like_url_only_text(value):
    if not value:
        return False
    text = value.strip()
    return bool(re.match(r'^(https?://\S+)$', text))


def _find_pemic_url_in_text(value):
    if not value:
        return None
    match = re.search(r'https?://[^\s"\)\]]+', value)
    if match and _is_pemic_annotation_url(match.group(0)):
        return match.group(0)
    return None


def _extract_pemic_url_from_book(book):
    if not book:
        return None

    candidates = [book.preview_url, book.cover_image]
    if book.cover_images:
        candidates.extend(book.cover_images)
    if _looks_like_url_only_text(book.description):
        candidates.append(book.description)
    url = _find_pemic_url_in_text(book.description)
    if url:
        candidates.append(url)

    for candidate in candidates:
        if not candidate:
            continue
        if _is_pemic_annotation_url(candidate):
            return candidate
    return None


def fetch_pemic_description(url):
    if not _is_pemic_annotation_url(url):
        return None
    return _safe_request_text(url)


def populate_book_description_from_pemic(book, save=True):
    if not book:
        return None

    pemic_url = _extract_pemic_url_from_book(book)
    if not pemic_url:
        if book.description and book.description.strip() and not _looks_like_url_only_text(book.description):
            return book.description
        return None

    description = fetch_pemic_description(pemic_url)
    if description and save:
        book.description = description
        book.save(update_fields=['description'])
    return description


def _openlibrary_cover_urls_by_isbn(isbn):
    if not isbn:
        return []
    url = 'https://openlibrary.org/api/books'
    params = {
        'bibkeys': f'ISBN:{isbn}',
        'format': 'json',
        'jscmd': 'data',
    }
    data = _safe_request_json(url, params=params)
    if not data:
        return []

    record = data.get(f'ISBN:{isbn}', {})
    cover = record.get('cover', {})
    urls = [cover.get(size) for size in ('large', 'medium', 'small') if cover.get(size)]
    return [url for url in map(_normalize_image_url, urls) if url]


def _openlibrary_search_cover_urls(title, author=None):
    if not title:
        return []
    query = title
    if author:
        query = f'{query} {author}'
    url = 'https://openlibrary.org/search.json'
    params = {'q': query, 'limit': 8}
    data = _safe_request_json(url, params=params)
    if not data:
        return []

    urls = []
    for doc in data.get('docs', []):
        cover_id = doc.get('cover_i')
        if cover_id:
            urls.append(f'https://covers.openlibrary.org/b/id/{cover_id}-L.jpg')
        isbns = doc.get('isbn') or []
        for isbn in isbns[:2]:
            urls.append(f'https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg')
        edition_keys = doc.get('edition_key') or []
        if edition_keys:
            urls.append(f'https://covers.openlibrary.org/b/olid/{edition_keys[0]}-L.jpg')
    return [url for url in map(_normalize_image_url, dict.fromkeys(urls)) if url]


def _google_books_cover_urls(isbn=None, title=None, author=None):
    queries = []
    if isbn:
        queries.append(f'isbn:{isbn}')
    if title and author:
        queries.append(f'intitle:{title}+inauthor:{author}')
    elif title:
        queries.append(f'intitle:{title}')

    api_url = 'https://www.googleapis.com/books/v1/volumes'
    api_key = getattr(settings, 'GOOGLE_BOOKS_API_KEY', None)
    headers = {'Accept': 'application/json'}
    urls = []

    for query in queries:
        params = {'q': query}
        if api_key:
            params['key'] = api_key
        data = _safe_request_json(api_url, params=params, headers=headers)
        if not data:
            continue
        for item in data.get('items', [])[:5]:
            image_links = item.get('volumeInfo', {}).get('imageLinks', {})
            for key in ('extraLarge', 'large', 'medium', 'thumbnail', 'smallThumbnail'):
                if image_links.get(key):
                    urls.append(image_links.get(key))
        if urls:
            break

    return [url for url in map(_normalize_image_url, dict.fromkeys(urls)) if url]


def fetch_book_cover_urls(book):
    if not book:
        return []

    identifiers = []
    if book.isbn:
        identifiers.append(book.isbn)
    if book.ean and book.ean != book.isbn:
        identifiers.append(book.ean)

    urls = []
    for identifier in identifiers:
        urls.extend(_openlibrary_cover_urls_by_isbn(identifier))
        if urls:
            break

    if not urls:
        urls.extend(_openlibrary_search_cover_urls(book.title, book.author))

    if not urls:
        urls.extend(_google_books_cover_urls(isbn=book.isbn or book.ean, title=book.title, author=book.author))

    return [url for url in map(_normalize_image_url, dict.fromkeys(urls)) if url]


def populate_book_cover_images(book, save=True):
    if not book:
        return []

    if book.primary_image:
        return book.image_gallery

    urls = fetch_book_cover_urls(book)
    if not urls:
        return []

    book.cover_images = urls
    if not book.cover_image:
        book.cover_image = urls[0]
    if save:
        book.save(update_fields=['cover_image', 'cover_images'])
    return urls


def send_zero_price_report():
    config = ShopConfig.get_solo()
    email = config.service_email or getattr(settings, 'SERVICE_EMAIL', None)
    if not email:
        return 0, None

    books = Book.objects.filter(price__lte=0)
    if not books.exists():
        return 0, email

    lines = [
        f"{book.pk}: {book.title} — {book.author} | cena={book.price} | kategorie={book.category}"
        for book in books
    ]
    message = 'Produkty s nulovou cenou pro kontrolu administrátorem:\n\n' + '\n'.join(lines)
    send_mail(
        'Denní report: nulová cena u produktů',
        message,
        getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@freshbooks.local'),
        [email],
        fail_silently=False,
    )
    return books.count(), email
