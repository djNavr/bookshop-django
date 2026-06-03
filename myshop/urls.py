from django.contrib import admin
from django.urls import path
from django.contrib.auth import views as auth_views
from books import views as book_views
from graphene_django.views import GraphQLView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', book_views.index, name='index'),
    path('categories/', book_views.categories, name='categories'),
    path('books/<int:pk>/', book_views.detail, name='book-detail'),
    path('cart/', book_views.cart_view, name='cart_view'),
    path('cart/add/<int:pk>/', book_views.cart_add, name='cart_add'),
    path('checkout/', book_views.checkout, name='checkout'),
    path('checkout/success/<int:order_id>/', book_views.checkout_success, name='checkout_success'),
    path('orders/', book_views.order_list, name='order_list'),
    path('orders/<int:pk>/', book_views.order_detail, name='order_detail'),
    path('accounts/register/', book_views.register, name='register'),
    path('accounts/login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(next_page='index'), name='logout'),
    path('admin/settings/', book_views.admin_settings, name='admin_settings'),
    path('admin/zero-price-report/', book_views.zero_price_report, name='zero_price_report'),
    path('contact/', book_views.contact, name='contact'),
    path('graphql', GraphQLView.as_view(graphiql=True)),
]
