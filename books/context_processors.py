from .models import Book


def wishlist_count(request):
    wishlist = request.session.get('wishlist', [])
    return {
        'wishlist_count': len(set(wishlist)) if wishlist else 0,
    }
