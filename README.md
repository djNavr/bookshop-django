E-Shop (Django + GraphQL)
===============================

This is a minimal e-shop scaffold built with Django and Graphene (GraphQL), focused on selling books.

Quick start

1. Create a virtualenv and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Run migrations and create a superuser:

```bash
python manage.py migrate
python manage.py createsuperuser
```

3. Seed sample books (optional):

```bash
python scripts/seed.py
```

4. Import the real product catalog from ZIP files:

```bash
python scripts/import_catalog.py \
  --catalogue /Users/navr/Downloads/catalogue_3102c132-cacc-487e-bbf2-2875632a8c59.zip \
  --price /Users/navr/Downloads/Price_3102c132-cacc-487e-bbf2-2875632a8c59.zip \
  --stock /Users/navr/Downloads/stock_3102c132-cacc-487e-bbf2-2875632a8c59.zip
```

5. Run the dev server:

```bash
python manage.py runserver
```

Open http://127.0.0.1:8000 to view the shop and http://127.0.0.1:8000/graphql for GraphiQL.

Notes
- Uses SQLite for simplicity. For production, switch to PostgreSQL and configure static files.
- This scaffold is inspired by Saleor-style concepts (Django + GraphQL) but intentionally small and easy to run.

Git and Documentation
- The project is initialized as a local git repository.
- See `DOCS.md` for how to edit features, add new pages, and connect a remote repository.
- To push to GitHub, add a remote and push:

```bash
git remote add origin git@github.com:YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```
