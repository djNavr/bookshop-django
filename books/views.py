from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.db.models import Count
from django.shortcuts import render, get_object_or_404, redirect

from .forms import CheckoutForm, RegistrationForm, ShopConfigForm
from .models import Book, Order, OrderItem, ShopConfig
from .utils import verify_address


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


def _get_shop_config():
    return ShopConfig.get_solo()


def index(request):
    config = _get_shop_config()
    books = Book.objects.all().order_by('-created_at')
    if config.hide_zero_price_products:
        books = books.filter(price__gt=0)

    book_type = request.GET.get('book_type', '')
    category = request.GET.get('category', '')
    category_group = request.GET.get('category_group', '')
    in_stock = request.GET.get('in_stock', '')
    q = request.GET.get('q', '').strip()

    if in_stock == '1':
        books = books.filter(available=True, stock__gt=0)
    if book_type:
        books = books.filter(book_type=book_type)
    if category:
        books = books.filter(category=category)
    elif category_group:
        books = books.filter(category__startswith=category_group)
    if q:
        books = books.filter(title__icontains=q)

    book_types = Book.objects.all()
    if config.hide_zero_price_products:
        book_types = book_types.filter(price__gt=0)
    book_types = book_types.values_list('book_type', flat=True).distinct().order_by('book_type')

    return render(request, 'books/index.html', {
        'books': books,
        'book_types': [bt for bt in book_types if bt],
        'selected_filters': {
            'book_type': book_type,
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
    return render(request, 'books/detail.html', {'book': book})


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
    messages.success(request, f'Přidáno do košíku: {book.title}')
    return redirect('cart_view')


def cart_view(request):
    items, total = _get_cart_items(request)
    return render(request, 'books/cart.html', {'items': items, 'total': total})


def checkout(request):
    items, total = _get_cart_items(request)
    if not items:
        messages.warning(request, 'Košík je prázdný. Přidejte prosím nejprve položky.')
        return redirect('index')

    if request.method == 'POST':
        form = CheckoutForm(request.POST)
        if form.is_valid():
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

                for item in items:
                    book = item['book']
                    if not book.available or item['quantity'] > book.stock:
                        messages.error(request, f'Kniha {book.title} není momentálně dostupná v požadovaném množství.')
                        return redirect('cart_view')

                order = Order.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    customer_name=form.cleaned_data['name'],
                    email=form.cleaned_data['email'],
                    address=form.get_address(),
                    total_price=total,
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
                messages.success(request, 'Objednávka byla přijata. Děkujeme za nákup!')
                return redirect('checkout_success', order_id=order.pk)
    else:
        initial = {}
        if request.user.is_authenticated:
            initial = {
                'name': request.user.get_full_name() or request.user.username,
                'email': request.user.email,
                'country': 'Česká republika',
            }
        form = CheckoutForm(initial=initial)

    return render(request, 'books/checkout.html', {
        'items': items,
        'total': total,
        'form': form,
    })


def checkout_success(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    return render(request, 'books/checkout_success.html', {'order': order})


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

    lines = [
        f"{book.pk}: {book.title} — {book.author} | cena={book.price} | kategorie={book.category}"
        for book in books
    ]
    body = 'Produkty s nulovou cenou pro kontrolu administrátorem:\n\n' + '\n'.join(lines)
    send_mail(
        'Denní report: nulová cena u produktů',
        body,
        getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@freshbooks.local'),
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
def order_list(request):
    orders = request.user.orders.order_by('-created_at')
    return render(request, 'books/orders.html', {'orders': orders})


@login_required(login_url='login')
def order_detail(request, pk):
    order = get_object_or_404(Order, pk=pk, user=request.user)
    return render(request, 'books/order_detail.html', {'order': order})
