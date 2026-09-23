"""Testy najważniejszych reguł aplikacji.

Uruchomienie:  python manage.py test
"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import AlbumFormat, CoverColor, CoverMaterial, Foil, Project


class BazaTestowa(TestCase):
    """Wspólne dane dla wszystkich testów."""

    def setUp(self):
        self.monika = User.objects.create_user("monika", password="tajne123")
        self.obcy = User.objects.create_user("ktos_inny", password="tajne123")

        self.format = AlbumFormat.objects.create(
            name="20 × 20 cm", width_cm=20, height_cm=20, base_price=189
        )
        self.material = CoverMaterial.objects.create(name="Aksamit", price=45)
        self.kolor = CoverColor.objects.create(name="Pudrowy róż", hex_code="#C39199")
        self.foil = Foil.objects.create(name="Złote", price=25)

        self.projekt = Project.objects.create(
            photographer=self.monika,
            name="Chrzest Zosi",
            client_name="Anna Nowak",
            album_format=self.format,
            cover_material=self.material,
            cover_color=self.kolor,
            foil=self.foil,
            spreads_count=3,
        )
        self.projekt.build_spreads()


class TestModeli(BazaTestowa):
    def test_token_jest_generowany_i_unikalny(self):
        drugi = Project.objects.create(
            photographer=self.monika,
            name="Sesja rodzinna",
            album_format=self.format,
            cover_material=self.material,
            cover_color=self.kolor,
            foil=self.foil,
            spreads_count=2,
        )
        self.assertTrue(self.projekt.token)
        self.assertGreaterEqual(len(self.projekt.token), 20)
        self.assertNotEqual(self.projekt.token, drugi.token)

    def test_cena_liczy_sie_z_katalogu(self):
        # cena bazowa formatu + dopłata za materiał + dopłata za tłoczenie,
        # bez dopłat za rozkładówki, bo pięć pierwszych jest w cenie
        self.assertEqual(self.projekt.price(), 189 + 45 + 25)

    def test_kazda_rozkladowka_ponad_piec_koszuje_wiecej(self):
        self.projekt.spreads_count = 8
        self.projekt.save()
        doplata = 3 * self.format.price_per_extra_spread
        self.assertEqual(self.projekt.price(), 189 + 45 + 25 + doplata)

    def test_budowanie_rozkladowek_tworzy_strony(self):
        self.assertEqual(self.projekt.spreads.count(), 3)
        for spread in self.projekt.spreads.all():
            self.assertEqual(spread.pages.count(), 2)

    def test_liczba_miejsc_odpowiada_ukladom(self):
        self.assertEqual(self.projekt.used_slots, 0)
        self.assertGreater(self.projekt.total_slots, 0)


class TestDostepuDoPanelu(BazaTestowa):
    def test_niezalogowany_nie_wchodzi_do_panelu(self):
        odp = self.client.get(reverse("studio:projects"))
        self.assertEqual(odp.status_code, 302)
        self.assertIn("/panel/login/", odp["Location"])

    def test_fotograf_widzi_swoj_projekt(self):
        self.client.login(username="monika", password="tajne123")
        odp = self.client.get(reverse("studio:project_detail", args=[self.projekt.pk]))
        self.assertEqual(odp.status_code, 200)
        self.assertContains(odp, "Chrzest Zosi")

    def test_obcy_fotograf_nie_widzi_cudzego_projektu(self):
        self.client.login(username="ktos_inny", password="tajne123")
        odp = self.client.get(reverse("studio:project_detail", args=[self.projekt.pk]))
        self.assertEqual(odp.status_code, 404)


class TestLinkuKlienta(BazaTestowa):
    def test_poprawny_token_otwiera_kreator(self):
        odp = self.client.get(reverse("studio:client_creator", args=[self.projekt.token]))
        self.assertEqual(odp.status_code, 200)

    def test_zmyslony_token_daje_404(self):
        odp = self.client.get(reverse("studio:client_creator", args=["taki-token-nie-istnieje"]))
        self.assertEqual(odp.status_code, 404)

    def test_klient_nie_zapisze_gdy_edycja_wylaczona(self):
        self.projekt.client_editing_enabled = False
        self.projekt.save()
        odp = self.client.post(
            reverse("studio:api_save", args=[self.projekt.token]),
            data="{}",
            content_type="application/json",
        )
        self.assertEqual(odp.status_code, 403)

    def test_klient_zapisuje_gdy_edycja_wlaczona(self):
        self.projekt.client_editing_enabled = True
        self.projekt.save()
        odp = self.client.post(
            reverse("studio:api_save", args=[self.projekt.token]),
            data='{"page_gap": 12, "spreads": []}',
            content_type="application/json",
        )
        self.assertEqual(odp.status_code, 200)


class TestEksportuPdf(BazaTestowa):
    def test_niezalogowany_nie_pobierze_pdf(self):
        odp = self.client.get(reverse("studio:pdf", args=[self.projekt.pk]))
        self.assertEqual(odp.status_code, 302)

    def test_fotograf_pobiera_pdf(self):
        self.client.login(username="monika", password="tajne123")
        odp = self.client.get(reverse("studio:pdf", args=[self.projekt.pk]))
        self.assertEqual(odp.status_code, 200)
        self.assertEqual(odp["Content-Type"], "application/pdf")
        self.assertIn("attachment", odp["Content-Disposition"])
        self.assertGreater(len(odp.content), 1000)
