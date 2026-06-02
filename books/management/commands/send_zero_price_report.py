from django.core.management.base import BaseCommand

from books.utils import send_zero_price_report


class Command(BaseCommand):
    help = 'Odeslat report produktů s nulovou cenou na servisní email.'

    def handle(self, *args, **options):
        count, email = send_zero_price_report()
        if not email:
            self.stdout.write(self.style.WARNING('Není nakonfigurován servisní email.'))
            return

        if count == 0:
            self.stdout.write(self.style.SUCCESS('Nejsou žádné produkty s nulovou cenou.'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Odesláno {count} produktů na {email}.'))
