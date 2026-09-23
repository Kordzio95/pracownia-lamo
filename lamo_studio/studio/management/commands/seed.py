"""Komenda `python manage.py seed` - wrzuca cennik do pustej bazy i robi konto.

Po pobraniu projektu baza jest pusta, a bez cennika nie ma jak liczyć ceny,
więc jedną komendą wszystko jest gotowe.
"""

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from studio.models import AlbumFormat, CoverColor, CoverMaterial, Foil

# cennik pracowni: (nazwa, szerokość cm, wysokość cm, cena, dopłata za rozkładówkę powyżej 5)
FORMATS = [
    ("20×20 cm", 20, 20, 189, 12),
    ("25×25 cm", 25, 25, 249, 12),
    ("30×30 cm", 30, 30, 329, 16),
    ("A4 poziomy", 29.7, 21, 279, 12),
]
# materiał i tłoczenie to dopłaty do ceny formatu
MATERIALS = [("Aksamit", 45), ("Len", 20), ("Płótno", 0), ("Ekoskóra", 35)]
COLORS = [
    ("Pudrowy róż", "#C39199"), ("Szałwia", "#8E9B87"), ("Czekolada", "#5A423A"),
    ("Butelkowa zieleń", "#2F4A3C"), ("Dymny błękit", "#6A7E8C"), ("Karmel", "#B08968"),
    ("Ecru", "#E7DBCB"), ("Bordo", "#6E2B33"),
]
FOILS = [("Złote tłoczenie", 25), ("Srebrne tłoczenie", 25), ("Bezbarwne tłoczenie", 15), ("Brak", 0)]


class Command(BaseCommand):
    help = "Wypełnia bazę ofertą pracowni i tworzy konto fotografa."
    # opis komendy w `manage.py help seed`

    def add_arguments(self, parser):
        # login i hasło można podać w komendzie, jak nie to są domyślne
        # (konto pokazowe tylko lokalnie, w internecie trzeba zmienić hasło)
        parser.add_argument("--user", default="monika")
        parser.add_argument("--password", default="lamo12345")

    def handle(self, *args, **options):
        # enumerate daje numer pozycji, zapisuję go jako kolejność na liście
        for order, (name, w, h, price, extra) in enumerate(FORMATS):
            # jak już jest to aktualizuje, jak nie ma to dodaje. można puścić 2 razy i nie będzie duplikatów
            AlbumFormat.objects.update_or_create(
                name=name,
                defaults={"width_cm": w, "height_cm": h, "base_price": price,
                          "price_per_extra_spread": extra, "order": order},
            )
        for order, (name, price) in enumerate(MATERIALS):
            CoverMaterial.objects.update_or_create(name=name, defaults={"price": price, "order": order})
        for order, (name, hex_code) in enumerate(COLORS):
            CoverColor.objects.update_or_create(name=name, defaults={"hex_code": hex_code, "order": order})
        for order, (name, price) in enumerate(FOILS):
            Foil.objects.update_or_create(name=name, defaults={"price": price, "order": order})

        # konto fotografa, zwykły User z Django
        user, created = User.objects.get_or_create(
            username=options["user"],
            defaults={"is_staff": True, "is_superuser": True, "first_name": "Monika"},
        )
        if created:  # hasło tylko dla nowego konta, żeby nie nadpisać zmienionego
            user.set_password(options["password"])
            # w bazie jest hash hasła, nie samo hasło
            user.save()
            self.stdout.write(self.style.SUCCESS(
                f"Konto {user.username} utworzone (hasło: {options['password']})"))
        else:
            self.stdout.write(f"Konto {user.username} już istnieje.")
        self.stdout.write(self.style.SUCCESS("Oferta pracowni gotowa."))
