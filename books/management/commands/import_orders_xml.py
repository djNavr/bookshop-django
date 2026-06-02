from decimal import Decimal, InvalidOperation
from pathlib import Path
from xml.etree import ElementTree as ET

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from books.models import Book, Order, OrderItem


def safe_decimal(value):
    if value is None:
        return Decimal('0.00')
    text = str(value).strip().replace(' ', '').replace(',', '.')
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return Decimal('0.00')


def parse_order_text(element, tag):
    node = element.find(tag)
    return node.text.strip() if node is not None and node.text else ''


class Command(BaseCommand):
    help = 'Import orders from a Knihy.cz B2C XML file into the local Django shop.'

    def add_arguments(self, parser):
        parser.add_argument('xml_path', help='Path to the XML order file.')
        parser.add_argument('--create-missing-books', action='store_true', help='Create placeholder Book entries for missing products.')
        parser.add_argument('--decrement-stock', action='store_true', help='Decrease stock for imported order items.')

    def handle(self, *args, **options):
        xml_path = Path(options['xml_path'])
        if not xml_path.exists():
            raise CommandError(f'XML file not found: {xml_path}')

        try:
            tree = ET.parse(xml_path)
        except ET.ParseError as exc:
            raise CommandError(f'XML parse error: {exc}')

        root = tree.getroot()
        source_system = parse_order_text(root.find('DocumentHead') or ET.Element('DocumentHead'), 'SOURCE_SYSTEM')
        order_nodes = root.findall('.//Order')
        if not order_nodes:
            self.stdout.write(self.style.WARNING('No <Order> elements found in XML.'))
            return

        imported = 0
        skipped = 0
        created_books = 0

        User = get_user_model()
        for order_node in order_nodes:
            external_id = parse_order_text(order_node, 'CISLO_OBJEDNAVKY') or parse_order_text(order_node, 'INTERNI_KOD_OBJEDNAVKY_ZAKAZNIKA')
            if not external_id:
                self.stdout.write(self.style.WARNING('Skipping order without external order ID.'))
                skipped += 1
                continue

            if Order.objects.filter(external_order_id=external_id).exists():
                self.stdout.write(self.style.WARNING(f'Skipping duplicate order: {external_id}'))
                skipped += 1
                continue

            customer_name = ' '.join(
                part for part in [parse_order_text(order_node, 'DODACI_JMENO'), parse_order_text(order_node, 'DODACI_PRIJMENI')] if part
            ).strip()
            if not customer_name:
                customer_name = ' '.join(
                    part for part in [parse_order_text(order_node, 'FAKTURACNI_JMENO'), parse_order_text(order_node, 'FAKTURACNI_PRIJMENI')] if part
                ).strip()
            if not customer_name:
                customer_name = 'Zákazník'

            email = parse_order_text(order_node, 'EMAIL')
            user = User.objects.filter(email__iexact=email).first() if email else None

            shipping_address = []
            if parse_order_text(order_node, 'DODACI_FIRMA'):
                shipping_address.append(parse_order_text(order_node, 'DODACI_FIRMA'))
            shipping_address.extend([
                parse_order_text(order_node, 'DODACI_ADRESA'),
                parse_order_text(order_node, 'DODACI_PSC') + ' ' + parse_order_text(order_node, 'DODACI_MESTO'),
                parse_order_text(order_node, 'DODACI_STAT'),
            ])
            address = '\n'.join([line for line in shipping_address if line.strip()])
            if not address:
                address = 'Adresa není uvedena'

            total_price = safe_decimal(parse_order_text(order_node, 'CELKEM_CENA_OBJEDNAVKY'))
            payment_code = parse_order_text(order_node, 'KOD_PLATBY')
            shipping_code = parse_order_text(order_node, 'KOD_DOPRAVY')

            item_nodes = order_node.findall('Line')
            if not item_nodes:
                self.stdout.write(self.style.WARNING(f'Order {external_id} contains no line items.'))
                skipped += 1
                continue

            order = Order.objects.create(
                external_order_id=external_id,
                source_system=source_system or 'B2C_XML',
                payment_code=payment_code or None,
                shipping_code=shipping_code or None,
                user=user,
                customer_name=customer_name,
                email=email or '',
                address=address,
                total_price=total_price,
            )

            imported_items = 0
            for line_node in item_nodes:
                code = parse_order_text(line_node, 'KOD_ZBOZI')
                qty_text = parse_order_text(line_node, 'CELKEM_KS')
                price_text = parse_order_text(line_node, 'CENA_ZA_KS')
                name = parse_order_text(line_node, 'NAZEV_ZBOZI')
                quantity = int(qty_text) if qty_text.isdigit() else 0
                unit_price = safe_decimal(price_text)

                if quantity <= 0 or unit_price <= 0:
                    self.stdout.write(self.style.WARNING(f'Ignoring line with zero quantity or price: {code} / {name}'))
                    continue

                book = Book.find_by_external_code(code)
                if not book and options['create_missing_books']:
                    book = Book.objects.create(
                        sortkod=code,
                        title=name or code,
                        author='',
                        description='',
                        price=unit_price,
                        currency='CZK',
                        stock=0,
                        available=False,
                    )
                    created_books += 1
                    self.stdout.write(self.style.WARNING(f'Created placeholder book for code {code}'))

                if not book:
                    self.stdout.write(self.style.WARNING(f'Skipping missing book for code {code} ({name}).'))
                    continue

                OrderItem.objects.create(
                    order=order,
                    book=book,
                    quantity=quantity,
                    unit_price=unit_price,
                )
                imported_items += 1

                if options['decrement_stock'] and book.stock >= quantity:
                    book.stock = max(book.stock - quantity, 0)
                    book.available = book.stock > 0
                    book.save()

            if imported_items == 0:
                order.delete()
                self.stdout.write(self.style.WARNING(f'Order {external_id} created without valid products and was removed.'))
                skipped += 1
                continue

            imported += 1
            self.stdout.write(self.style.SUCCESS(f'Imported order {external_id} with {imported_items} items.'))

        self.stdout.write(self.style.SUCCESS(f'Done: {imported} orders imported, {skipped} skipped, {created_books} placeholder books created.'))
