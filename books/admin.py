from django.contrib import admin
from .models import Book, Order, OrderItem, ShopConfig


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ('sortkod', 'title', 'author', 'book_type', 'currency', 'stock', 'available', 'created_at')
    list_filter = ('book_type', 'available')
    search_fields = ('title', 'author', 'sortkod', 'category')


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
