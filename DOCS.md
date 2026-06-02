# Bookshop Project Documentation

## Overview

This project is a small e-commerce shop built with Django and Graphene (GraphQL). It uses:

- Django for backend and templating
- SQLite for local development
- Graphene-Django for GraphQL queries
- Bootstrap 5 for UI styling

## Project Structure

- `manage.py` — Django command-line utility.
- `requirements.txt` — Python dependencies.
- `myshop/` — Django project settings, URLs, WSGI, and GraphQL schema.
- `books/` — Django app containing book models, views, admin registration, and GraphQL schema.
- `templates/` — Base and page templates for the frontend.
- `static/css/style.css` — Custom styling.
- `scripts/seed.py` — Sample book creation script.

## Running the Project

1. Create and activate a virtual environment:

```bash
cd /Users/navr/Projects/bookshop
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run database migrations:

```bash
python manage.py migrate
```

4. Seed example books:

```bash
python scripts/seed.py
```

5. Start the local server:

```bash
python manage.py runserver
```

Access the site at `http://127.0.0.1:8000` and GraphQL at `http://127.0.0.1:8000/graphql`.

## Editing the Project

### Change book fields

Edit `books/models.py` to add fields like:

- `category = models.CharField(max_length=100, blank=True)`
- `stock = models.IntegerField(default=0)`
- `rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)`

Then regenerate migrations:

```bash
python manage.py makemigrations books
python manage.py migrate
```

Also update templates and GraphQL schema in `books/schema.py`.

### Add a cart

1. Create a `Cart` and `CartItem` model in `books/models.py`.
2. Add views and templates for cart display.
3. Add `Add to cart` actions in the product detail template.
4. Optionally use sessions or authenticated user carts.

### Add checkout and payments

1. Add order models like `Order` and `OrderItem`.
2. Add checkout forms and payment integration.
3. Use a payment provider like Stripe, PayPal, or a mock payment flow.

### Add search, filters, and categories

- Add a search view or GraphQL filter for book title and author.
- Add a `Category` model with relationships to `Book`.
- Add UI controls and filter logic.

### Add GraphQL mutations

Extend `books/schema.py` with mutations for:

- creating books
- updating books
- adding items to cart
- placing orders

Graphene mutations can be added as:

```python
class CreateBook(graphene.Mutation):
    class Arguments:
        title = graphene.String(required=True)
        author = graphene.String(required=True)
        # ...

    book = graphene.Field(BookType)

    def mutate(self, info, title, author, ...):
        book = Book.objects.create(...)
        return CreateBook(book=book)
```

## Git Setup

This project has been initialized locally with git.

To connect it to a remote repository, run:

```bash
git remote add origin git@github.com:YOUR_USERNAME/YOUR_REPO.git
 git push -u origin main
```

If you want to use GitHub, create the repo on GitHub first and then add the remote.

## Useful files to edit

- `README.md` — project overview and instructions.
- `DOCS.md` — extension and feature guide.
- `books/models.py` — core product data.
- `books/views.py` — page behavior.
- `books/schema.py` — GraphQL API.
- `books/templates/books/*.html` — UI layout.
- `static/css/style.css` — styling.

## Next features to add

- user accounts and login/signup
- cart and checkout flow
- product categories and tags
- search and filtering
- GraphQL mutations and admin controls
- shopping cart persistence for guests and users
- order history pages
