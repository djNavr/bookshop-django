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
