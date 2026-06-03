from django.contrib import admin, messages
from django.db.models import Q
from django.shortcuts import redirect
from django.urls import path, reverse
from .models import Book, Order, OrderItem, ShopConfig
from .utils import populate_book_cover_images


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ('sortkod', 'title', 'author', 'book_type', 'currency', 'stock', 'available', 'created_at')
    list_filter = ('book_type', 'available')
    search_fields = ('title', 'author', 'sortkod', 'category')
    actions = ['fill_missing_cover_images']
    change_list_template = 'admin/books/book/change_list.html'
    change_form_template = 'admin/books/book/change_form.html'

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('fill-missing-cover-images/', self.admin_site.admin_view(self.fill_missing_cover_images_view), name='books_book_fill_missing_cover_images'),
            path('<path:object_id>/fill-cover-images/', self.admin_site.admin_view(self.fill_cover_images_view), name='books_book_fill_cover_images'),
        ]
        return custom_urls + urls

    def fill_missing_cover_images(self, request, queryset):
        return self._populate_missing_cover_images(request, queryset)

    fill_missing_cover_images.short_description = 'Doplnit chybějící obalové obrázky pro vybrané knihy'

    def fill_missing_cover_images_view(self, request):
        queryset = Book.objects.filter(Q(cover_image__isnull=True) | Q(cover_image=''))
        return self._populate_missing_cover_images(request, queryset, selected=False)

    def fill_cover_images_view(self, request, object_id):
        book = Book.objects.get(pk=object_id)
        urls = populate_book_cover_images(book)
        if urls:
            messages.success(request, f'Obalové obrázky pro {book.title} byly doplněny ({len(urls)} obrázků).')
        else:
            messages.warning(request, f'Pro {book.title} se nepodařilo najít žádné obrázky.')
        return redirect(request.META.get('HTTP_REFERER') or reverse('admin:books_book_change', args=[book.pk]))

    def _populate_missing_cover_images(self, request, queryset, selected=True):
        updated = 0
        skipped = 0
        for book in queryset:
            urls = populate_book_cover_images(book)
            if urls:
                updated += 1
            else:
                skipped += 1

        if selected:
            message = f'Doplněno obalů pro {updated} vybraných knih.'
        else:
            message = f'Doplněno obalů pro {updated} knih, {skipped} knih zůstalo bez obrázku.'
        messages.success(request, message)
        return redirect(request.META.get('HTTP_REFERER') or reverse('admin:books_book_changelist'))


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


@admin.register(ShopConfig)
class ShopConfigAdmin(admin.ModelAdmin):
    fieldsets = (
        (None, {
            'fields': ('service_email', 'shop_name', 'maintenance_mode', 'hide_zero_price_products')
        }),
    )
    readonly_fields = ('id',)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('pk', 'external_order_id', 'source_system', 'user', 'customer_name', 'email', 'total_price', 'status', 'created_at')
    readonly_fields = ('total_price', 'created_at')
    list_filter = ('status', 'created_at', 'source_system')
    search_fields = ('external_order_id', 'customer_name', 'email', 'user__username')
    inlines = [OrderItemInline]
