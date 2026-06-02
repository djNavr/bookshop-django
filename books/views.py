from django.shortcuts import render, get_object_or_404
from .models import Book


def index(request):
    books = Book.objects.all().order_by('-created_at')
    return render(request, 'books/index.html', {'books': books})


def detail(request, pk):
    book = get_object_or_404(Book, pk=pk)
    return render(request, 'books/detail.html', {'book': book})
