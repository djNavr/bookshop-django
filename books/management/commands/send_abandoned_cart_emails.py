"""Management command to send reminder emails for abandoned carts.

Usage:
    python manage.py send_abandoned_cart_emails
    python manage.py send_abandoned_cart_emails --hours 48  # custom delay

Schedule via cron (every hour):
    0 * * * * /opt/bookshop/.venv/bin/python /opt/bookshop/manage.py send_abandoned_cart_emails >> /home/ec2-user/abandoned_cart.log 2>&1
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from books.models import AbandonedCart, Book, ShopConfig


class Command(BaseCommand):
    help = "Send reminder emails for abandoned shopping carts."

    def add_arguments(self, parser):
        parser.add_argument(
            "--hours",
            type=int,
            default=24,
            help="Send reminders for carts abandoned at least this many hours ago (default: 24).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would be sent without actually sending.",
        )

    def handle(self, *args, **options):
        hours = options["hours"]
        dry_run = options["dry_run"]
        cutoff = timezone.now() - timedelta(hours=hours)
        sender_email = ShopConfig.get_from_email()

        carts = AbandonedCart.objects.filter(
            converted=False,
            reminder_sent_at__isnull=True,
            updated_at__lte=cutoff,
            email__gt="",  # only carts with a known e-mail
        )

        sent = 0
        skipped = 0

        for cart in carts:
            items_data = self._resolve_items(cart.cart_data)
            if not items_data:
                skipped += 1
                continue

            total = sum(i["price"] * i["quantity"] for i in items_data)
            restore_url = self._build_restore_url(cart.pk)

            subject = "Zapomněli jste na košík — FreshBooks"
            html_body = render_to_string(
                "books/email/abandoned_cart.html",
                {
                    "items": items_data,
                    "total": total,
                    "restore_url": restore_url,
                },
            )
            text_body = (
                f"Váš košík na vás čeká!\n\n"
                + "\n".join(
                    f"- {i['title']} × {i['quantity']} = {i['price'] * i['quantity']} Kč"
                    for i in items_data
                )
                + f"\n\nCelkem: {total} Kč\n\nDokončit objednávku: {restore_url}"
            )

            if dry_run:
                self.stdout.write(
                    f"[DRY RUN] Would send to {cart.email}: {len(items_data)} items, total {total} Kč"
                )
            else:
                try:
                    send_mail(
                        subject=subject,
                        message=text_body,
                        from_email=sender_email,
                        recipient_list=[cart.email],
                        html_message=html_body,
                        fail_silently=False,
                    )
                    cart.reminder_sent_at = timezone.now()
                    cart.save(update_fields=["reminder_sent_at"])
                    sent += 1
                    self.stdout.write(self.style.SUCCESS(f"Sent to {cart.email}"))
                except Exception as exc:
                    self.stderr.write(f"Failed to send to {cart.email}: {exc}")
                    skipped += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Sent: {sent}, Skipped: {skipped}, Total candidates: {carts.count() if not dry_run else '(dry run)'}"
            )
        )

    def _resolve_items(self, cart_data: dict) -> list[dict]:
        """Return list of {title, quantity, price} dicts for items in the cart."""
        if not cart_data:
            return []
        book_pks = [int(pk) for pk in cart_data.keys()]
        books = {b.pk: b for b in Book.objects.filter(pk__in=book_pks, price__gt=0)}
        result = []
        for pk_str, qty in cart_data.items():
            book = books.get(int(pk_str))
            if book and qty > 0:
                result.append(
                    {"title": book.title, "quantity": qty, "price": book.price}
                )
        return result

    def _build_restore_url(self, cart_pk: int) -> str:
        base = getattr(settings, "SITE_URL", "https://ec2-13-60-251-54.eu-north-1.compute.amazonaws.com")
        path = reverse("restore_cart", args=[cart_pk])
        return f"{base}{path}"
