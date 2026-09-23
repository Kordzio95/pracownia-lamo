"""Modele, czyli tabele w bazie.

Po kolei to wygląda tak: fotograf -> projekt -> rozkładówka -> strona -> miejsce na zdjęcie.
Do tego jest cennik (formaty, materiały, kolory, tłoczenia) z którego projekt wybiera.
"""

import secrets  # do losowania tokenów do linków

from django.contrib.auth.models import User  # fotograf to zwykły user z Django
from django.db import models
from django.urls import reverse  # robi adres z nazwy, żeby nie wpisywać go ręcznie


def new_token() -> str:
    """Losowy token do linku dla klienta."""
    # nie daje numeru projektu w linku, bo ktoś by wpisał następny numer i zobaczył cudzy album
    # WAŻNE: od tego zależy bezpieczeństwo linków. mniejsza liczba = krótszy token, łatwiej zgadnąć
    return secrets.token_urlsafe(16)


# --- cennik pracowni ---
# ceny są w bazie a nie w kodzie, żeby Monika mogła je zmieniać sama w adminie


class CoverMaterial(models.Model):
    """Materiał okładki (aksamit, len itd.)."""

    name = models.CharField("nazwa", max_length=60, unique=True)  # unique, żeby nie było dwóch takich samych
    price = models.DecimalField("dopłata (zł)", max_digits=7, decimal_places=2, default=0)
    # Decimal a nie float, bo float przy pieniądzach potrafi zgubić grosze
    is_active = models.BooleanField("dostępny", default=True)
    # zamiast kasować wyłączam, stare projekty dalej działają
    order = models.PositiveIntegerField("kolejność", default=0)  # kolejność na liście

    class Meta:
        verbose_name = "materiał okładki"  # polskie nazwy w adminie
        verbose_name_plural = "materiały okładek"
        ordering = ["order", "name"]

    def __str__(self):
        # to się pokazuje np. na liście w formularzu
        return self.name


class CoverColor(models.Model):
    """Kolor okładki razem z kodem HEX."""

    name = models.CharField("nazwa", max_length=60, unique=True)
    hex_code = models.CharField("kolor (HEX)", max_length=7, default="#C39199")
    # kolor w jednym miejscu, żeby podgląd i wydruk miały ten sam odcień
    is_active = models.BooleanField("dostępny", default=True)
    order = models.PositiveIntegerField("kolejność", default=0)

    class Meta:
        verbose_name = "kolor okładki"
        verbose_name_plural = "kolory okładek"
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class AlbumFormat(models.Model):
    """Format albumu - wymiary i cena."""

    name = models.CharField("nazwa", max_length=60, unique=True)  # np. "25 × 25 cm"
    width_cm = models.DecimalField("szerokość (cm)", max_digits=5, decimal_places=1, default=25)
    height_cm = models.DecimalField("wysokość (cm)", max_digits=5, decimal_places=1, default=25)
    # z tych wymiarów liczy się kształt strony na ekranie i rozmiar pliku do druku (render.py)
    base_price = models.DecimalField("cena bazowa (zł)", max_digits=8, decimal_places=2, default=249)
    price_per_extra_spread = models.DecimalField(
        "dopłata za rozkładówkę powyżej 5", max_digits=7, decimal_places=2, default=12
    )
    # 5 rozkładówek jest w cenie, za każdą następną się dopłaca (tak liczy pracownia)
    is_active = models.BooleanField("dostępny", default=True)
    order = models.PositiveIntegerField("kolejność", default=0)

    class Meta:
        verbose_name = "format albumu"
        verbose_name_plural = "formaty albumów"
        ordering = ["order", "name"]

    def __str__(self):
        return self.name

    @property
    def ratio(self):
        # szerokość / wysokość, po tym przeglądarka rysuje kształt strony
        # property czyli liczone na bieżąco, nie ma tego w bazie
        return float(self.width_cm) / float(self.height_cm)


class Foil(models.Model):
    """Tłoczenie napisu na okładce."""

    name = models.CharField("nazwa", max_length=60, unique=True)  # złote, srebrne, bezbarwne, brak
    price = models.DecimalField("dopłata (zł)", max_digits=7, decimal_places=2, default=0)
    is_active = models.BooleanField("dostępny", default=True)
    order = models.PositiveIntegerField("kolejność", default=0)

    class Meta:
        verbose_name = "tłoczenie"
        verbose_name_plural = "tłoczenia"
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


# --- projekt ---


class Project(models.Model):
    """Projekt albumu. Najważniejsza tabela, reszta jest do niej podpięta."""

    class Status(models.TextChoices):
        # w bazie siedzi krótki kod, np. "draft", a na ekranie polski napis "szkic"
        DRAFT = "draft", "szkic"
        SENT = "sent", "wysłany do klienta"
        IN_PROGRESS = "in_progress", "klient projektuje"
        SUBMITTED = "submitted", "oddany do pracowni"
        APPROVED = "approved", "zatwierdzony"
        PRINTING = "printing", "w druku"
        DONE = "done", "zrealizowany"

    photographer = models.ForeignKey(
        User, verbose_name="fotograf", on_delete=models.CASCADE, related_name="projects"
    )
    # czyj to projekt. jak się usunie fotografa to jego projekty też lecą (CASCADE)

    name = models.CharField("nazwa projektu", max_length=120)  # np. "Chrzest Zosi"
    client_name = models.CharField("klient", max_length=120, blank=True)
    client_email = models.EmailField("e-mail klienta", blank=True)  # sam sprawdza czy to mail
    client_phone = models.CharField("telefon klienta", max_length=40, blank=True)
    # blank=True czyli nie trzeba wpisywać. klient nie ma konta, tylko imię i kontakt

    # --- rzeczy z cennika ---
    # PROTECT - nie da się usunąć np. koloru, jak jakiś projekt go używa
    album_format = models.ForeignKey(
        AlbumFormat, verbose_name="format", on_delete=models.PROTECT, related_name="projects"
    )
    cover_material = models.ForeignKey(
        CoverMaterial, verbose_name="materiał okładki", on_delete=models.PROTECT, related_name="projects"
    )
    cover_color = models.ForeignKey(
        CoverColor, verbose_name="kolor okładki", on_delete=models.PROTECT, related_name="projects"
    )
    foil = models.ForeignKey(
        Foil, verbose_name="tłoczenie", on_delete=models.PROTECT, related_name="projects"
    )
    cover_title = models.CharField("tytuł na okładce", max_length=60, blank=True)
    cover_subtitle = models.CharField("podpis na okładce", max_length=60, blank=True)

    # --- wygląd środka albumu ---
    spreads_count = models.PositiveIntegerField("liczba rozkładówek", default=10)
    page_gap = models.PositiveIntegerField("odstęp między zdjęciami (px)", default=10)
    page_padding = models.PositiveIntegerField("margines strony (px)", default=14)
    page_bg = models.CharField("tło strony", max_length=7, default="#FFFCF8")
    # to jest w pikselach z podglądu, render.py przelicza to na wydruk

    # --- co klient może ---
    client_can_upload = models.BooleanField("klient może wgrywać własne zdjęcia", default=True)
    client_editing_enabled = models.BooleanField("klient może projektować album", default=False)
    # WAŻNE: ten przełącznik decyduje czy klient może cokolwiek zapisać w albumie
    # na start wyłączone, fotograf najpierw szykuje album a potem otwiera klientowi
    # sprawdzane na serwerze przy zapisie (views.api_save), nie tylko schowane przyciski

    status = models.CharField("status", max_length=20, choices=Status.choices, default=Status.DRAFT)
    token = models.CharField("token linku", max_length=64, default=new_token, unique=True, db_index=True)
    # WAŻNE: po tokenie klient wchodzi do albumu. zmiana tokena = stary link przestaje działać
    # new_token bez nawiasów! wtedy django woła to dla każdego nowego projektu.
    # z nawiasami wszystkie by miały ten sam token
    # db_index, żeby szybko szukało po tokenie
    note = models.TextField("notatka pracowni", blank=True)  # widzi tylko pracownia
    client_note = models.TextField("uwagi klienta", blank=True)  # to co klient dopisze

    created_at = models.DateTimeField("utworzono", auto_now_add=True)  # ustawia się raz
    updated_at = models.DateTimeField("zmodyfikowano", auto_now=True)  # przy każdym zapisie
    submitted_at = models.DateTimeField("oddany przez klienta", null=True, blank=True)
    # puste dopóki klient nie odda projektu

    class Meta:
        verbose_name = "projekt"
        verbose_name_plural = "projekty"
        ordering = ["-updated_at"]  # minus = najnowsze na górze

    def __str__(self):
        return self.name

    # --- adresy ---
    def get_absolute_url(self):
        # adres karty projektu w panelu
        return reverse("studio:project_detail", args=[self.pk])

    def client_url(self):
        # link dla klienta, z tokenem
        return reverse("studio:client_creator", args=[self.token])

    def reset_token(self):
        """Nowy link, stary przestaje działać."""
        self.token = new_token()
        self.save(update_fields=["token", "updated_at"])  # zapisuje tylko te 2 pola

    # --- wyliczenia ---
    # tego nie trzymam w bazie tylko liczę na bieżąco

    @property
    def pages_count(self):
        return self.spreads_count * 2  # rozkładówka = 2 strony

    @property
    def used_slots(self):
        # ile miejsc ma już zdjęcie
        return Slot.objects.filter(page__spread__project=self, photo__isnull=False).count()

    @property
    def total_slots(self):
        # ile jest miejsc w ogóle (zależy od układów stron)
        return Slot.objects.filter(page__spread__project=self).count()

    def price(self):
        """Cena orientacyjna z cennika."""
        # WAŻNE: tu jest cały wzór na cenę, zmiana tutaj zmienia cenę w panelu, adminie i kreatorze
        # liczona na bieżąco, więc zmiana cennika od razu jest widoczna.
        # jakby to szło na produkcję to trzeba by zapisać cenę przy przyjęciu zamówienia
        fmt = self.album_format
        extra = max(0, self.spreads_count - 5)  # max żeby nie wyszło na minusie
        return (
            fmt.base_price
            + self.cover_material.price
            + self.foil.price
            + extra * fmt.price_per_extra_spread
        )

    def build_spreads(self, count=None, layout="two_v"):
        """Dorabia brakujące rozkładówki."""
        # WAŻNE: to nigdy nie kasuje rozkładówek, tylko dokłada. dzięki temu praca klienta nie ginie
        # zaczyna od tych co już są i dokłada tylko brakujące,
        # więc jak się powiększy album to praca klienta zostaje
        count = count or self.spreads_count
        existing = self.spreads.count()
        for index in range(existing, count):
            spread = self.spreads.create(index=index)
            for side in (Page.Side.LEFT, Page.Side.RIGHT):
                page = spread.pages.create(side=side, layout=layout)
                page.rebuild_slots()  # robi tyle miejsc ile ma układ
        return self.spreads.count()

    def log(self, kind, note="", author=None):
        """Dodaje wpis do historii projektu."""
        return self.events.create(kind=kind, note=note, author=author)


class SessionPhoto(models.Model):
    """Zdjęcie z sesji (od fotografa albo od klienta)."""

    project = models.ForeignKey(
        Project, verbose_name="projekt", on_delete=models.CASCADE, related_name="photos"
    )
    image = models.ImageField("plik", upload_to="sesje/%Y/%m/")
    # w bazie jest tylko ścieżka, plik leży w folderze media, podzielone na rok/miesiąc
    original_name = models.CharField("nazwa pliku", max_length=200, blank=True)
    # nazwa z aparatu np IMG_8559.jpeg, bo django czasem zmienia nazwę pliku
    order = models.PositiveIntegerField("kolejność", default=0)
    is_favorite = models.BooleanField("ulubione", default=False)  # gwiazdka w kreatorze
    uploaded_by_client = models.BooleanField("wgrane przez klienta", default=False)
    # zdjęcia z telefonu klienta bywają za małe do druku, dlatego to zaznaczam
    created_at = models.DateTimeField("wgrano", auto_now_add=True)

    class Meta:
        verbose_name = "zdjęcie sesji"
        verbose_name_plural = "zdjęcia sesji"
        ordering = ["order", "id"]

    def __str__(self):
        return self.original_name or f"zdjęcie {self.pk}"

    @property
    def times_used(self):
        # ile razy zdjęcie jest w albumie, żeby klient nie wstawił tego samego 5 razy
        return self.slots.count()


class Spread(models.Model):
    """Rozkładówka czyli dwie strony obok siebie."""

    # album się ogląda rozkładówkami i do druku też idzie rozkładówka jako jeden arkusz

    project = models.ForeignKey(
        Project, verbose_name="projekt", on_delete=models.CASCADE, related_name="spreads"
    )
    index = models.PositiveIntegerField("numer rozkładówki", default=0)  # od zera

    class Meta:
        verbose_name = "rozkładówka"
        verbose_name_plural = "rozkładówki"
        ordering = ["index"]
        unique_together = [("project", "index")]
        # baza nie pozwoli na dwie rozkładówki z tym samym numerem w jednym projekcie

    def __str__(self):
        return f"rozkładówka {self.index + 1}"  # +1 bo ludzie liczą od 1


class Page(models.Model):
    """Jedna strona albumu i jej układ."""

    LAYOUTS = [
        # lewa wartość idzie do bazy, prawa widzi klient
        ("full", "1 duże"),
        ("two_v", "2 obok siebie"),
        ("two_h", "2 jedno nad drugim"),
        ("three", "1 + 2"),
        ("four", "4 w kratę"),
        ("six", "6 małych"),
        ("frame", "1 w ramce"),
        ("blank", "puste"),
    ]
    SLOT_COUNTS = {"full": 1, "two_v": 2, "two_h": 2, "three": 3, "four": 4, "six": 6, "frame": 1, "blank": 0}
    # ile zdjęć wchodzi w dany układ
    # WAŻNE: jak tu coś zmienisz, to trzeba to samo zmienić w creator.html (LAYOUTS)
    # i w render.py (LAYOUTS), inaczej podgląd i PDF będą się różnić

    class Side(models.TextChoices):
        LEFT = "L", "lewa"
        RIGHT = "R", "prawa"

    spread = models.ForeignKey(
        Spread, verbose_name="rozkładówka", on_delete=models.CASCADE, related_name="pages"
    )
    side = models.CharField("strona", max_length=1, choices=Side.choices)
    layout = models.CharField("układ", max_length=20, choices=LAYOUTS, default="two_v")
    caption = models.CharField("podpis", max_length=120, blank=True)
    # podpis pod zdjęciami, jak jest to render.py robi na niego miejsce na dole

    class Meta:
        verbose_name = "strona"
        verbose_name_plural = "strony"
        ordering = ["spread__index", "side"]  # sortowanie po polu z innej tabeli
        unique_together = [("spread", "side")]  # jedna lewa i jedna prawa

    def __str__(self):
        return f"{self.spread} — strona {self.get_side_display()}"

    def rebuild_slots(self):
        """Ustawia tyle miejsc na zdjęcia ile ma układ."""
        # nie kasuje wszystkiego, tylko usuwa nadmiar albo dokłada brakujące,
        # dzięki temu zdjęcia które już są zostają na miejscu
        target = self.SLOT_COUNTS.get(self.layout, 0)
        current = list(self.slots.order_by("index"))
        for extra in current[target:]:  # to co jest ponad
            extra.delete()
        for index in range(len(current), target):  # to czego brakuje
            self.slots.create(index=index)
        return target


class Slot(models.Model):
    """Miejsce na zdjęcie na stronie + kadrowanie."""

    page = models.ForeignKey(Page, verbose_name="strona", on_delete=models.CASCADE, related_name="slots")
    index = models.PositiveIntegerField("pozycja", default=0)  # które miejsce, od zera
    photo = models.ForeignKey(
        SessionPhoto,
        verbose_name="zdjęcie",
        on_delete=models.SET_NULL,  # jak się usunie zdjęcie to miejsce robi się puste
        null=True,
        blank=True,
        related_name="slots",
    )
    zoom = models.FloatField("przybliżenie", default=1.0)
    offset_x = models.FloatField("przesunięcie w poziomie (%)", default=0)
    offset_y = models.FloatField("przesunięcie w pionie (%)", default=0)
    # kadr to tylko 3 liczby, pliku nie przycinam. oryginał zostaje cały i ostry.
    # przesunięcie jest w procentach więc działa i na telefonie i w dużym pliku do druku

    class Meta:
        verbose_name = "miejsce na zdjęcie"
        verbose_name_plural = "miejsca na zdjęcia"
        ordering = ["index"]
        unique_together = [("page", "index")]

    def __str__(self):
        return f"{self.page} — miejsce {self.index + 1}"


class ProjectEvent(models.Model):
    """Historia projektu - kto co i kiedy zrobił."""

    # przydaje się jak klient mówi "przecież zapisałem" - widać wtedy, czy zapis doszedł

    class Kind(models.TextChoices):
        CREATED = "created", "utworzono projekt"
        PHOTOS = "photos", "wgrano zdjęcia"
        LINK = "link", "wysłano link klientowi"
        CLIENT_SAVE = "client_save", "klient zapisał układ"
        SUBMITTED = "submitted", "klient oddał projekt"
        STATUS = "status", "zmiana statusu"
        NOTE = "note", "notatka"

    project = models.ForeignKey(
        Project, verbose_name="projekt", on_delete=models.CASCADE, related_name="events"
    )
    kind = models.CharField("zdarzenie", max_length=20, choices=Kind.choices)
    note = models.CharField("opis", max_length=250, blank=True)  # np. "wgrano 12 zdjęć"
    author = models.ForeignKey(
        User, verbose_name="autor", on_delete=models.SET_NULL, null=True, blank=True
    )
    # puste = zrobił to klient (nie ma konta)
    created_at = models.DateTimeField("kiedy", auto_now_add=True)

    class Meta:
        verbose_name = "zdarzenie"
        verbose_name_plural = "historia projektu"
        ordering = ["-created_at"]  # najnowsze na górze

    def __str__(self):
        return f"{self.get_kind_display()} — {self.created_at:%Y-%m-%d %H:%M}"
