from django.contrib import admin
from django.urls import path
from books import views as book_views
from graphene_django.views import GraphQLView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', book_views.index, name='index'),
    path('books/<int:pk>/', book_views.detail, name='book-detail'),
    path('graphql', GraphQLView.as_view(graphiql=True)),
]
