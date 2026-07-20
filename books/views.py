from decimal import Decimal
import os
import time
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
import requests

from .forms import (
    CheckoutAddressForm,
    CheckoutConfirmForm,
    CheckoutPaymentForm,
    CheckoutShippingForm,
    ContactForm,
    RegistrationForm,
    ReviewForm,
    ShopConfigForm,
)
from .models import AbandonedCart, BlogPost, Book, Order, OrderItem, Review, ShopConfig
from .utils import populate_book_description_from_pemic, verify_address


def _get_cart_items(request):
    cart = request.session.get('cart', {})
    books = Book.objects.filter(pk__in=[int(pk) for pk in cart.keys()], price__gt=0) if cart else []
    items = []
    total = Decimal('0.00')
    cleaned_cart = cart.copy()

    for book in books:
        quantity = cart.get(str(book.pk), 0)
        if quantity <= 0 or book.price <= 0:
            cleaned_cart.pop(str(book.pk), None)
            continue

        line_total = book.price * quantity
        items.append({
            'book': book,
            'quantity': quantity,
            'line_total': line_total,
        })
        total += line_total

    if cleaned_cart != cart:
        request.session['cart'] = cleaned_cart
    return items, total


WISHLIST_SESSION_KEY = 'wishlist'
ZASILKOVNA_CACHE_TTL_SECONDS = 3600
_zasilkovna_branch_cache = {'fetched_at': 0, 'items': []}
CHECKOUT_DRAFT_SESSION_KEY = 'checkout_draft'
CHECKOUT_STEPS = (1, 2, 3, 4)


def _get_checkout_step(raw_step):
    try:
        step = int(raw_step)
    except (TypeError, ValueError):
        step = 1
    return step if step in CHECKOUT_STEPS else 1


def _get_checkout_draft(request):
    return dict(request.session.get(CHECKOUT_DRAFT_SESSION_KEY, {}))


def _save_checkout_draft(request, draft):
    request.session[CHECKOUT_DRAFT_SESSION_KEY] = draft
    request.session.modified = True


def _clear_checkout_draft(request):
    if CHECKOUT_DRAFT_SESSION_KEY in request.session:
        del request.session[CHECKOUT_DRAFT_SESSION_KEY]
        request.session.modified = True


def _get_shop_config():
    return ShopConfig.get_solo()


def _get_wishlist_items(request):
    wishlist = request.session.get(WISHLIST_SESSION_KEY, [])
    return Book.objects.filter(pk__in=[int(pk) for pk in wishlist]) if wishlist else []


def _get_zasilkovna_api_key():
    return getattr(settings, 'ZASILKOVNA_API_KEY', '') or os.environ.get('ZASILKOVNA_API_KEY', '')


def _fetch_zasilkovna_branches(api_key):
    now = int(time.time())
    if _zasilkovna_branch_cache['items'] and now - _zasilkovna_branch_cache['fetched_at'] < ZASILKOVNA_CACHE_TTL_SECONDS:
        return _zasilkovna_branch_cache['items']

    url = f'https://www.zasilkovna.cz/api/v4/{api_key}/branch.json'
    response = requests.get(url, timeout=15)
    response.raise_for_status()
    payload = response.json()

    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        items = payload.get('data') or payload.get('branches') or payload.get('result') or []
    else:
        items = []

    normalized = []
    for branch_item in items:
        if isinstance(items, dict) and isinstance(branch_item, str):
            branch = items[branch_item]
        else:
            branch = branch_item
        
        if not isinstance(branch, dict):
            continue
        if branch.get('isInactive'):
            continue

        code = branch.get('id') or branch.get('branchId') or branch.get('code')
        if code is None:
            continue

        name = branch.get('name') or branch.get('place') or ''
        city = branch.get('city') or ''
        street = branch.get('street') or ''
        postal_code = branch.get('zip') or ''
        country = (branch.get('country') or '').lower()
        if country and country not in {'cz', 'czech republic', 'ceska republika'}:
            continue

        latitude = branch.get('latitude') or branch.get('gps', {}).get('lat')
        longitude = branch.get('longitude') or branch.get('gps', {}).get('lng')

        normalized.append({
            'code': str(code),
            'name': name,
            'city': city,
            'street': street,
            'postal_code': postal_code,
            'latitude': float(latitude) if latitude else None,
            'longitude': float(longitude) if longitude else None,
        })

    _zasilkovna_branch_cache['fetched_at'] = now
    _zasilkovna_branch_cache['items'] = normalized
    return normalized


def zasilkovna_pickup_points(request):
    query = (request.GET.get('q') or '').strip().lower()
    if len(query) < 2:
        return JsonResponse({'results': []})

    api_key = _get_zasilkovna_api_key()
    if not api_key:
        return JsonResponse({'results': [], 'message': 'Zasilkovna API key není nastaven.'})

    try:
        branches = _fetch_zasilkovna_branches(api_key)
    except Exception:
        return JsonResponse({'results': [], 'message': 'Vyhledání výdejních míst je dočasně nedostupné.'})

    results = []
    for branch in branches:
        searchable = ' '.join(
            [branch['name'], branch['city'], branch['street'], branch['postal_code'], branch['code']]
        ).lower()
        if query not in searchable:
            continue
        label = branch['name']
        if branch['city']:
            label = f"{label}, {branch['city']}"
        address = ', '.join(part for part in [branch['street'], branch['postal_code']] if part)
        results.append({
            'code': branch['code'],
            'name': branch['name'],
            'city': branch['city'],
            'address': address,
            'label': label,
            'latitude': branch.get('latitude'),
            'longitude': branch.get('longitude'),
        })
        if len(results) >= 25:
            break

    return JsonResponse({'results': results})


def _append_query_param(url, key, value):
    parts = urlsplit(url)
    params = dict(parse_qsl(parts.query, keep_blank_values=True))
    params[key] = value
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(params), parts.fragment))


def _update_wishlist(request, pk, add=True):
    wishlist = set(request.session.get(WISHLIST_SESSION_KEY, []))
    if add:
        wishlist.add(str(pk))
    else:
        wishlist.discard(str(pk))
    request.session[WISHLIST_SESSION_KEY] = list(wishlist)


def index(request):
    config = _get_shop_config()
    books = Book.objects.all().order_by('-created_at')
    if config.hide_zero_price_products:
        books = books.filter(price__gt=0)

    book_type = request.GET.get('book_type', '')
    language = request.GET.get('language', '')
    category = request.GET.get('category', '')
    category_group = request.GET.get('category_group', '')
    publisher = request.GET.get('publisher', '')
    author = request.GET.get('author', '')
    sort_by = request.GET.get('sort', '')
    in_stock = request.GET.get('in_stock', '')
    q = request.GET.get('q', '').strip()

    if in_stock == '1':
        books = books.filter(available=True, stock__gt=0)
    if book_type:
        books = books.filter(book_type=book_type)
    if language:
        books = books.filter(language=language)
    if publisher:
        books = books.filter(publisher__iexact=publisher)
    if author:
        books = books.filter(author__icontains=author)
    if category:
        books = books.filter(category=category)
    elif category_group:
        books = books.filter(category__startswith=category_group)
    if q:
        books = books.filter(
            Q(title__icontains=q)
            | Q(author__icontains=q)
            | Q(publisher__icontains=q)
            | Q(sortkod__icontains=q)
            | Q(isbn__icontains=q)
            | Q(ean__icontains=q)
            | Q(category__icontains=q)
        )

    if sort_by == 'price_asc':
        books = books.order_by('price')
    elif sort_by == 'price_desc':
        books = books.order_by('-price')
    elif sort_by == 'oldest':
        books = books.order_by('created_at')
    else:
        books = books.order_by('-created_at')

    book_types = Book.objects.all()
    if config.hide_zero_price_products:
        book_types = book_types.filter(price__gt=0)
    book_types = book_types.values_list('book_type', flat=True).distinct().order_by('book_type')
    languages = Book.objects.exclude(language='').values_list('language', flat=True).distinct().order_by('language')
    publisher_options = Book.objects.exclude(publisher='').values('publisher').annotate(count=Count('pk')).order_by('-count')[:20]
    author_options = Book.objects.exclude(author='').values('author').annotate(count=Count('pk')).order_by('-count')[:20]
    if config.hide_zero_price_products:
        book_types = book_types.filter(price__gt=0)
    book_types = book_types.values_list('book_type', flat=True).distinct().order_by('book_type')
    languages = Book.objects.exclude(language='').values_list('language', flat=True).distinct().order_by('language')

    featured_books = Book.objects.filter(available=True)
    if config.hide_zero_price_products:
        featured_books = featured_books.filter(price__gt=0)
    featured_books = featured_books.order_by('-stock', '-created_at')[:3]

    return render(request, 'books/index.html', {
        'books': books,
        'featured_books': featured_books,
        'book_types': [bt for bt in book_types if bt],
        'languages': [lang for lang in languages if lang],
        'publisher_options': [item['publisher'] for item in publisher_options],
        'author_options': [item['author'] for item in author_options],
        'selected_filters': {
            'book_type': book_type,
            'language': language,
            'publisher': publisher,
            'author': author,
            'sort': sort_by,
            'category': category,
            'category_group': category_group,
            'in_stock': in_stock,
            'q': q,
        },
    })


def detail(request, pk):
    book = get_object_or_404(Book, pk=pk)
    config = _get_shop_config()
    if config.hide_zero_price_products and book.price <= 0:
        messages.warning(request, 'Tento titul je momentálně skrytý, protože má chybnou nebo nulovou cenu.')
        return redirect('index')

    wishlist = request.session.get(WISHLIST_SESSION_KEY, [])
    populate_book_description_from_pemic(book)
    review_form = ReviewForm()
    if request.method == 'POST' and 'review_submit' in request.POST:
        review_form = ReviewForm(request.POST)
        if review_form.is_valid():
            Review.objects.create(
                book=book,
                user=request.user if request.user.is_authenticated else None,
                name=request.user.get_full_name() or request.user.username if request.user.is_authenticated else 'Host',
                rating=int(review_form.cleaned_data['rating']),
                comment=review_form.cleaned_data['comment'],
                approved=False,
            )
            messages.success(request, 'Děkujeme za vaši recenzi! Po kontrole ji brzy zveřejníme.')
            return redirect('book-detail', pk=book.pk)

    return render(request, 'books/detail.html', {
        'book': book,
        'is_in_wishlist': str(book.pk) in wishlist,
        'review_form': review_form,
    })


def search_suggestions(request):
    q = request.GET.get('q', '').strip()
    suggestions = []
    if q:
        books = Book.objects.filter(
            Q(title__icontains=q)
            | Q(author__icontains=q)
            | Q(publisher__icontains=q)
            | Q(sortkod__icontains=q)
            | Q(isbn__icontains=q)
            | Q(ean__icontains=q)
        ).order_by('-stock', '-created_at')[:8]
        for book in books:
            suggestions.append({
                'id': book.pk,
                'title': book.title,
                'author': book.author,
                'cover': book.primary_image,
                'url': book.get_absolute_url(),
                'price': f"{book.price:.2f} {book.currency}",
            })
    return JsonResponse({'suggestions': suggestions})


def wishlist_view(request):
    items = _get_wishlist_items(request)
    return render(request, 'books/wishlist.html', {'items': items})


def wishlist_add(request, pk):
    book = get_object_or_404(Book, pk=pk)
    _update_wishlist(request, book.pk, add=True)
    messages.success(request, f'Přidáno do seznamu přání: {book.title}')
    return redirect('wishlist')


def wishlist_remove(request, pk):
    book = get_object_or_404(Book, pk=pk)
    _update_wishlist(request, book.pk, add=False)
    messages.success(request, f'Odstraněno ze seznamu přání: {book.title}')
    return redirect('wishlist')


def blog_list(request):
    posts = BlogPost.objects.filter(published=True).order_by('-published_at', '-created_at')
    return render(request, 'books/blog_list.html', {'posts': posts})


def blog_detail(request, slug):
    post = get_object_or_404(BlogPost, slug=slug, published=True)
    return render(request, 'books/blog_detail.html', {'post': post})


def register(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Registrace proběhla úspěšně. Nyní můžete sledovat své objednávky.')
            return redirect('order_list')
    else:
        form = RegistrationForm()

    return render(request, 'books/register.html', {'form': form})


def _track_abandoned_cart(request):
    """Upsert AbandonedCart record for the current session."""
    cart = request.session.get('cart', {})
    if not cart:
        return
    session_key = request.session.session_key
    if not session_key:
        request.session.create()
        session_key = request.session.session_key
    email = ''
    if request.user.is_authenticated:
        email = request.user.email
    AbandonedCart.objects.update_or_create(
        session_key=session_key,
        defaults={
            'email': email,
            'cart_data': cart,
            'converted': False,
        },
    )


def cart_add(request, pk):
    book = get_object_or_404(Book, pk=pk)
    if book.price <= 0:
        messages.warning(request, 'Cena této položky není dostupná. Nelze přidat do košíku.')
        return redirect('book-detail', pk=pk)
    if not book.available or book.stock <= 0:
        messages.warning(request, 'Tato kniha momentálně není skladem.')
        return redirect('book-detail', pk=pk)

    cart = request.session.get('cart', {})
    cart[str(pk)] = cart.get(str(pk), 0) + 1
    request.session['cart'] = cart
    _track_abandoned_cart(request)
    messages.success(request, f'Přidáno do košíku: {book.title}')

    next_url = request.POST.get('next') or request.GET.get('next')
    prompt_after_add = (
        request.POST.get('prompt_after_add') == '1'
        or request.GET.get('prompt_after_add') == '1'
    )

    if next_url and url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        redirect_target = next_url
        if prompt_after_add:
            redirect_target = _append_query_param(redirect_target, 'added_to_cart', '1')
        return redirect(redirect_target)

    if prompt_after_add:
        return redirect(_append_query_param(redirect('index').url, 'added_to_cart', '1'))

    return redirect('cart_view')


def cart_view(request):
    config = _get_shop_config()
    items, total = _get_cart_items(request)
    free_shipping_threshold = config.free_shipping_threshold
    free_shipping_remaining = 0
    if total > 0 and total < free_shipping_threshold:
        free_shipping_remaining = free_shipping_threshold - total
    return render(request, 'books/cart.html', {
        'items': items,
        'total': total,
        'free_shipping_threshold': free_shipping_threshold,
        'free_shipping_remaining': free_shipping_remaining,
    })


def checkout(request, step=None):
    items, total = _get_cart_items(request)
    if not items:
        messages.warning(request, 'Košík je prázdný. Přidejte prosím nejprve položky.')
        return redirect('index')

    draft = _get_checkout_draft(request)
    current_step = _get_checkout_step(step if step is not None else request.GET.get('step'))

    if current_step > 1 and 'address' not in draft:
        return redirect('checkout')
    if current_step > 2 and 'shipping' not in draft:
        return redirect('checkout_step', step=2)
    if current_step > 3 and 'payment' not in draft:
        return redirect('checkout_step', step=3)

    address_initial = draft.get('address', {})
    if request.user.is_authenticated and not address_initial:
        address_initial = {
            'name': request.user.get_full_name() or request.user.username,
            'email': request.user.email,
            'country': 'Česká republika',
        }

    forms_by_step = {
        1: CheckoutAddressForm,
        2: CheckoutShippingForm,
        3: CheckoutPaymentForm,
        4: CheckoutConfirmForm,
    }

    initial_by_step = {
        1: address_initial,
        2: draft.get('shipping', {}),
        3: draft.get('payment', {}),
        4: {'register_account': False},
    }

    form = forms_by_step[current_step](initial=initial_by_step[current_step])

    if request.method == 'POST':
        submitted_step = _get_checkout_step(request.POST.get('step', current_step))
        if submitted_step != current_step:
            return redirect('checkout_step', step=submitted_step)

        form = forms_by_step[current_step](request.POST)
        if form.is_valid():
            if current_step == 1:
                verification = verify_address(
                    street=form.cleaned_data['street'],
                    city=form.cleaned_data['city'],
                    postal_code=form.cleaned_data['postal_code'],
                    country=form.cleaned_data['country'],
                )
                if not verification['valid']:
                    form.add_error(None, verification.get('message', 'Adresa není validní.'))
                else:
                    if verification.get('warning'):
                        messages.warning(request, verification['warning'])

                    draft['address'] = {
                        'name': form.cleaned_data['name'],
                        'email': form.cleaned_data['email'],
                        'phone': form.cleaned_data.get('phone', ''),
                        'street': form.cleaned_data['street'],
                        'city': form.cleaned_data['city'],
                        'postal_code': form.cleaned_data['postal_code'],
                        'country': form.cleaned_data['country'],
                        'is_company_order': form.cleaned_data.get('is_company_order', False),
                        'company_name': form.cleaned_data.get('company_name', ''),
                        'company_id': form.cleaned_data.get('company_id', ''),
                        'vat_id': form.cleaned_data.get('vat_id', ''),
                    }
                    _save_checkout_draft(request, draft)
                    return redirect('checkout_step', step=2)

            elif current_step == 2:
                draft['shipping'] = {
                    'shipping_method': form.cleaned_data['shipping_method'],
                    'pickup_point_name': form.cleaned_data.get('pickup_point_name', ''),
                    'pickup_point_code': form.cleaned_data.get('pickup_point_code', ''),
                }
                _save_checkout_draft(request, draft)
                return redirect('checkout_step', step=3)

            elif current_step == 3:
                draft['payment'] = {
                    'payment_method': form.cleaned_data['payment_method'],
                }
                _save_checkout_draft(request, draft)
                return redirect('checkout_step', step=4)

            elif current_step == 4:
                if 'address' not in draft or 'shipping' not in draft or 'payment' not in draft:
                    messages.warning(request, 'Objednávka není kompletní. Dokončete prosím předchozí kroky.')
                    return redirect('checkout')

                for item in items:
                    book = item['book']
                    if not book.available or item['quantity'] > book.stock:
                        messages.error(request, f'Kniha {book.title} není momentálně dostupná v požadovaném množství.')
                        return redirect('cart_view')

                address_data = draft['address']
                shipping_data = draft['shipping']
                payment_data = draft['payment']

                user_for_order = request.user if request.user.is_authenticated else None

                if form.cleaned_data.get('register_account') and not request.user.is_authenticated:
                    UserModel = get_user_model()
                    account_email = address_data['email'].strip().lower()
                    if UserModel.objects.filter(email__iexact=account_email).exists():
                        form.add_error(None, 'Účet s tímto e-mailem již existuje. Přihlaste se prosím.')
                        return render(request, 'books/checkout.html', {
                            'items': items,
                            'total': total,
                            'form': form,
                            'current_step': current_step,
                            'steps': CHECKOUT_STEPS,
                            'draft': draft,
                        })

                    base_username = account_email.split('@')[0] or 'uzivatel'
                    username = base_username
                    suffix = 1
                    while UserModel.objects.filter(username=username).exists():
                        suffix += 1
                        username = f"{base_username}{suffix}"

                    user_for_order = UserModel.objects.create_user(
                        username=username,
                        email=account_email,
                        password=form.cleaned_data['account_password1'],
                    )
                    login(request, user_for_order)

                payment_method = payment_data['payment_method']
                shipping_method = shipping_data['shipping_method']

                payment_code = 'QR' if payment_method == Order.PAYMENT_METHOD_QR else None
                if payment_method == Order.PAYMENT_METHOD_GOPAY:
                    payment_code = 'GOPAY'
                elif payment_method == Order.PAYMENT_METHOD_COMGATE:
                    payment_code = 'COMGATE'
                elif payment_method == Order.PAYMENT_METHOD_STRIPE:
                    payment_code = 'STRIPE'
                elif payment_method == Order.PAYMENT_METHOD_COD:
                    payment_code = 'COD'

                order_address = (
                    f"{address_data['street']}\n"
                    f"{address_data['postal_code']} {address_data['city']}\n"
                    f"{address_data['country']}"
                )

                order = Order.objects.create(
                    user=user_for_order,
                    customer_name=address_data['name'],
                    email=address_data['email'],
                    address=order_address,
                    total_price=total,
                    is_company_order=address_data.get('is_company_order', False),
                    company_name=address_data.get('company_name', ''),
                    company_id=address_data.get('company_id', ''),
                    vat_id=address_data.get('vat_id', ''),
                    payment_method=payment_method,
                    payment_status=Order.PAYMENT_STATUS_PENDING,
                    payment_code=payment_code,
                    shipping_method=shipping_method,
                    shipping_status=Order.SHIPPING_STATUS_PENDING,
                    pickup_point_name=shipping_data.get('pickup_point_name') or '',
                    pickup_point_code=shipping_data.get('pickup_point_code') or '',
                    payment_details=(
                        f"Zvolená platební metoda: {dict(Order.PAYMENT_METHOD_CHOICES).get(payment_method, payment_method)}"
                    ),
                    shipping_details=(
                        f"Zvolená doprava: {dict(Order.SHIPPING_METHOD_CHOICES).get(shipping_method, shipping_method)}"
                    ),
                    terms_accepted=True,
                    terms_accepted_at=timezone.now(),
                )

                for item in items:
                    book = item['book']
                    OrderItem.objects.create(
                        order=order,
                        book=book,
                        quantity=item['quantity'],
                        unit_price=book.price,
                    )
                    book.stock = max(book.stock - item['quantity'], 0)
                    if book.stock <= 0:
                        book.available = False
                    book.save()

                request.session['cart'] = {}
                _clear_checkout_draft(request)

                session_key = request.session.session_key
                if session_key:
                    AbandonedCart.objects.filter(session_key=session_key).update(converted=True)

                messages.success(request, 'Objednávka byla přijata. Děkujeme za nákup!')
                return redirect('checkout_success', order_id=order.pk)

    shipping_label = ''
    payment_label = ''
    if draft.get('shipping', {}).get('shipping_method'):
        shipping_label = dict(Order.SHIPPING_METHOD_CHOICES).get(
            draft['shipping']['shipping_method'],
            draft['shipping']['shipping_method'],
        )
    if draft.get('payment', {}).get('payment_method'):
        payment_label = dict(Order.PAYMENT_METHOD_CHOICES).get(
            draft['payment']['payment_method'],
            draft['payment']['payment_method'],
        )

    return render(request, 'books/checkout.html', {
        'items': items,
        'total': total,
        'form': form,
        'current_step': current_step,
        'steps': CHECKOUT_STEPS,
        'draft': draft,
        'shipping_label': shipping_label,
        'payment_label': payment_label,
    })


def checkout_success(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    return render(request, 'books/checkout_success.html', {'order': order})


def restore_cart(request, token):
    """Restore a cart from an abandoned-cart reminder link."""
    import hashlib
    from django.utils import timezone
    try:
        ac = AbandonedCart.objects.get(pk=token, converted=False)
    except (AbandonedCart.DoesNotExist, ValueError):
        messages.warning(request, 'Odkaz na košík je neplatný nebo vypršel.')
        return redirect('index')
    if ac.cart_data:
        request.session['cart'] = ac.cart_data
        request.session.modified = True
        messages.info(request, 'Váš košík byl obnoven. Dokončete prosím objednávku.')
    return redirect('cart_view')


def contact(request):
    config = _get_shop_config()
    destination_email = config.service_email or getattr(settings, 'DEFAULT_FROM_EMAIL', None)
    sender_email = config.sender_email or getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@freshbooks.local')
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            if destination_email:
                send_mail(
                    f"Kontakt: {dict(form.fields['topic'].choices).get(form.cleaned_data['topic'], 'Dotaz')}",
                    f"Jméno: {form.cleaned_data['name']}\nE-mail: {form.cleaned_data['email']}\n\n{form.cleaned_data['message']}",
                    sender_email,
                    [destination_email],
                    fail_silently=False,
                )
                messages.success(request, 'Děkujeme, váš dotaz byl odeslán. Odpověď pošleme na zadaný e-mail.')
                return redirect('contact')
            messages.warning(request, 'Zpráva byla připravena, ale není nastaven odpovědní email administrace.')
    else:
        form = ContactForm()

    return render(request, 'books/contact.html', {
        'form': form,
        'destination_email': destination_email,
    })


def _get_category_icon(label):
    name = (label or '').lower()
    if 'romance' in name or 'lás' in name:
        return '💕'
    if 'děts' in name or 'kids' in name or 'child' in name:
        return '🧒'
    if 'sci' in name or 'fiction' in name or 'fantasy' in name or 'sci-fi' in name:
        return '🚀'
    if 'dobrodruž' in name or 'adven' in name:
        return '🗺️'
    if 'detektiv' in name or 'thriller' in name or 'krimi' in name:
        return '🕵️'
    if 'histor' in name or 'dějin' in name:
        return '🏰'
    if 'biografi' in name or 'memoar' in name or 'life' in name:
        return '👤'
    if 'kuchař' in name or 'vaření' in name or 'food' in name:
        return '🍳'
    if 'umění' in name or 'design' in name or 'art' in name:
        return '🎨'
    if 'věda' in name or 'nauč' in name or 'učeb' in name or 'education' in name:
        return '📘'
    if 'podnik' in name or 'business' in name or 'marketing' in name:
        return '💼'
    if 'samopomoc' in name or 'psych' in name or 'wellness' in name:
        return '🌿'
    if 'poezie' in name or 'poetry' in name:
        return '✒️'
    if 'cest' in name or 'travel' in name or 'map' in name:
        return '🌍'
    return '📚'


def categories(request):
    config = _get_shop_config()
    book_types = Book.objects.all()
    all_categories = Book.objects.all()
    if config.hide_zero_price_products:
        book_types = book_types.filter(price__gt=0)
        all_categories = all_categories.filter(price__gt=0)
    book_types = book_types.values('book_type').exclude(book_type='').annotate(count=Count('pk')).order_by('-count')
    all_categories = all_categories.values('category').exclude(category='').annotate(count=Count('pk')).order_by('category')

    category_groups = {}
    for item in all_categories:
        full_label = item['category']
        count = item['count']
        parts = [part.strip() for part in full_label.split(' - ')]
        if len(parts) >= 2:
            parent_label = f"{parts[0]} - {parts[1]}"
            child_label = ' - '.join(parts[2:]) if len(parts) > 2 else parts[-1]
        else:
            parent_label = parts[0]
            child_label = parts[0]

        parent = category_groups.setdefault(parent_label, {
            'label': parent_label,
            'count': 0,
            'icon': _get_category_icon(parent_label),
            'subcategories': [],
        })
        parent['count'] += count
        parent['subcategories'].append({
            'label': child_label,
            'full_label': full_label,
            'count': count,
            'icon': _get_category_icon(child_label),
        })

    category_groups = sorted(category_groups.values(), key=lambda grp: (-grp['count'], grp['label']))
    for group in category_groups:
        group['subcategories'] = sorted(group['subcategories'], key=lambda sub: (-sub['count'], sub['label']))

    for item in book_types:
        item['icon'] = _get_category_icon(item['book_type'])

    return render(request, 'books/categories.html', {
        'book_types': book_types,
        'category_groups': category_groups,
        'config': config,
    })


def _render_zero_price_report_message(request, email, book_count):
    if book_count == 0:
        messages.info(request, 'Žádné položky s nulovou cenou nebyly nalezeny.')
    else:
        messages.success(request, f'Denní report byl odeslán na {email}. Nalezeno {book_count} produktů.')


def _send_zero_price_report(email):
    books = Book.objects.filter(price__lte=0)
    if not books.exists() or not email:
        return 0

    config = ShopConfig.get_solo()
    sender_email = config.sender_email or getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@freshbooks.local')

    lines = [
        f"{book.pk}: {book.title} — {book.author} | cena={book.price} | kategorie={book.category}"
        for book in books
    ]
    body = 'Produkty s nulovou cenou pro kontrolu administrátorem:\n\n' + '\n'.join(lines)
    send_mail(
        'Denní report: nulová cena u produktů',
        body,
        sender_email,
        [email],
        fail_silently=False,
    )
    return books.count()


@staff_member_required
def admin_settings(request):
    config = _get_shop_config()
    if request.method == 'POST':
        form = ShopConfigForm(request.POST, instance=config)
        if form.is_valid():
            form.save()
            messages.success(request, 'Nastavení obchodu bylo uloženo.')
            return redirect('admin_settings')
    else:
        form = ShopConfigForm(instance=config)
    return render(request, 'books/admin_settings.html', {'form': form, 'config': config})


@staff_member_required
def zero_price_report(request):
    config = _get_shop_config()
    report_books = Book.objects.filter(price__lte=0)
    email = config.service_email or getattr(settings, 'SERVICE_EMAIL', None)
    if request.method == 'POST':
        if not email:
            messages.error(request, 'Prosím nastavte servisní email v administraci před odesláním reportu.')
        else:
            count = _send_zero_price_report(email)
            _render_zero_price_report_message(request, email, count)
            return redirect('zero_price_report')
    return render(request, 'books/zero_price_report.html', {
        'report_books': report_books,
        'config': config,
        'service_email': email,
    })


@login_required(login_url='login')
def order_cancel(request, pk):
    order = get_object_or_404(Order, pk=pk, user=request.user)
    if order.status in [Order.STATUS_SHIPPED, Order.STATUS_COMPLETED, Order.STATUS_CANCELLED]:
        messages.warning(request, 'Tuto objednávku již nelze zrušit.')
        return redirect('order_detail', pk=order.pk)

    if request.method == 'POST':
        order.status = Order.STATUS_CANCELLED
        order.save()
        for item in order.items.all():
            book = item.book
            book.stock = book.stock + item.quantity
            book.available = True
            book.save()
        messages.success(request, 'Objednávka byla zrušena a sklad byl aktualizován.')
        return redirect('order_detail', pk=order.pk)

    return redirect('order_detail', pk=order.pk)


@login_required(login_url='login')
def order_list(request):
    orders = request.user.orders.order_by('-created_at')
    return render(request, 'books/orders.html', {'orders': orders})


@login_required(login_url='login')
def order_detail(request, pk):
    order = get_object_or_404(Order, pk=pk, user=request.user)
    return render(request, 'books/order_detail.html', {'order': order})


def page_not_found(request, exception=None):
    return render(request, '404.html', status=404)
