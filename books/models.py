from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Book(models.Model):
    sortkod = models.CharField(max_length=50, unique=True, blank=True, null=True)
    title = models.CharField(max_length=255)
    author = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(0.01)])
    cover_image = models.URLField(blank=True)
    cover_images = models.JSONField(blank=True, null=True, default=list)
    publisher = models.CharField(max_length=255, blank=True)
    ean = models.CharField(max_length=32, blank=True)
    isbn = models.CharField(max_length=32, blank=True)
    book_type = models.CharField(max_length=128, blank=True)
    category = models.CharField(max_length=255, blank=True)
    currency = models.CharField(max_length=8, default='CZK')
    stock = models.IntegerField(default=0)
    available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @classmethod
    def find_by_external_code(cls, code):
        if not code:
            return None
        code = str(code).strip()
        return cls.objects.filter(
            models.Q(sortkod=code) | models.Q(ean=code) | models.Q(isbn=code)
        ).first()

    @property
    def image_gallery(self):
        images = []
        if self.cover_image:
            images.append(self.cover_image)
        if self.cover_images:
            for image in self.cover_images:
                if image and image not in images:
                    images.append(image)
        return images

    @property
    def primary_image(self):
        gallery = self.image_gallery
        return gallery[0] if gallery else ''

    def publisher_image_suggestions(self):
        if not self.publisher:
            return []
        suggestions = []
        related_books = Book.objects.filter(publisher__iexact=self.publisher).exclude(pk=self.pk)
        for related in related_books:
            for image in related.image_gallery:
                if image and image not in suggestions:
                    suggestions.append(image)
        return suggestions[:4]

    def __str__(self):
        return f"{self.title} — {self.author}"


class ShopConfig(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    service_email = models.EmailField(
        blank=True,
        null=True,
        help_text='Email pro denní report produktů s nulovou cenou nebo chybnou konfigurací.',
    )
    shop_name = models.CharField(max_length=128, default='FreshBooks')
    maintenance_mode = models.BooleanField(default=False)
    hide_zero_price_products = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Nastavení obchodu'
        verbose_name_plural = 'Nastavení obchodu'

    def __str__(self):
        return 'Nastavení obchodu'

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Order(models.Model):
    STATUS_NEW = 'new'
    STATUS_PROCESSING = 'processing'
    STATUS_SHIPPED = 'shipped'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'

    ORDER_STATUS_CHOICES = [
        (STATUS_NEW, 'Nová objednávka'),
        (STATUS_PROCESSING, 'Ve zpracování'),
        (STATUS_SHIPPED, 'Odesláno'),
        (STATUS_COMPLETED, 'Dokončeno'),
        (STATUS_CANCELLED, 'Zrušeno'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='orders',
    )
    customer_name = models.CharField(max_length=255)
    external_order_id = models.CharField(max_length=128, blank=True, null=True, unique=True)
    source_system = models.CharField(max_length=64, blank=True, null=True)
    payment_code = models.CharField(max_length=64, blank=True, null=True)
    shipping_code = models.CharField(max_length=64, blank=True, null=True)
    email = models.EmailField(blank=True)
    address = models.TextField()
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=ORDER_STATUS_CHOICES, default=STATUS_NEW)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Objednávka #{self.pk} — {self.customer_name}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    book = models.ForeignKey(Book, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=8, decimal_places=2)

    @property
    def line_total(self):
        return self.unit_price * self.quantity

    def __str__(self):
        return f"{self.quantity} × {self.book.title}"
