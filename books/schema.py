import graphene
from graphene_django import DjangoObjectType
from .models import Book


class BookType(DjangoObjectType):
    class Meta:
        model = Book
        fields = ('id', 'sortkod', 'title', 'author', 'description', 'price', 'currency', 'cover_image', 'ean', 'isbn', 'book_type', 'category', 'stock', 'available')


class Query(graphene.ObjectType):
    books = graphene.List(BookType)
    book = graphene.Field(BookType, id=graphene.Int())

    def resolve_books(root, info):
        return Book.objects.all().order_by('-created_at')

    def resolve_book(root, info, id):
        try:
            return Book.objects.get(pk=id)
        except Book.DoesNotExist:
            return None
