# Pracownia Lamo - panel fotografa i kreator fotoksiążek

Aplikacja w Django z bazą danych. Fotograf zakłada projekt albumu, wgrywa zdjęcia z sesji
i wysyła klientowi jeden link. Klient bez zakładania konta układa album w przeglądarce,
a gotowy układ wraca do panelu pracowni.

## Jak uruchomić na Windowsie

Otwórz PowerShell w folderze projektu i wpisz kolejno:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py seed
python manage.py runserver
```

Potem wejdź w przeglądarce na **http://127.0.0.1:8000/panel/**

Dane logowania utworzone przez `seed`:

- użytkownik: `monika`
- hasło: `lamo12345`

Hasło zmienisz komendą `python manage.py changepassword monika`.
Własne konto dodasz przez `python manage.py createsuperuser`.

W PyCharmie: otwórz folder jako projekt, wskaż interpreter z `.venv`,
a jako konfigurację uruchomieniową wybierz `manage.py runserver`.

## Jak się z tego korzysta

1. **Nowy projekt** - nazwa, klient, format, liczba rozkładówek, okładka (materiał, kolor,
   tłoczenie, napis). Od razu można wgrać zdjęcia z sesji.
2. **Karta projektu** - zdjęcia sesji z licznikiem wykorzystania, specyfikacja, cena
   orientacyjna, status, notatka pracowni, historia zdarzeń.
3. **Pozwól, by klient zaprojektował album** - jedno kliknięcie otwiera kreator i daje link
   `.../k/<token>/`. Link można skopiować albo wysłać e-mailem gotową treścią. „Nowy link"
   unieważnia poprzedni.
4. **Kreator** (ten sam dla pracowni i klienta) - 8 układów strony, przeciąganie zdjęć na
   miejsca, zamiana zdjęć miejscami, kadrowanie (przybliżenie i przesunięcie), podpisy stron,
   tło stron, odstępy i marginesy, ulubione, filtry „ukryj użyte" i „tylko ulubione",
   automatyczne rozłożenie zdjęć, cofanie zmian, autozapis na serwer.
5. **Klient oddaje projekt** - z uwagami; status zmienia się na „oddany do pracowni",
   a Monika widzi w karcie cały układ strona po stronie.
6. **Przygotuj do druku** - arkusz produkcyjny ze specyfikacją i spisem stron
   (układ, nazwy plików, podpisy) do wydruku lub zapisu w PDF.
7. **Pobierz PDF do druku** - składa gotowe rozkładówki w 300 dpi dokładnie tak, jak wyglądają
   w kreatorze: te same układy, odstępy, marginesy, tło stron, kadrowanie i podpisy. Do wyboru
   3 mm spadu na obcięcie, znaczniki cięcia z linią zgięcia i karta tytułowa ze specyfikacją.
   Album 20×20 cm daje arkusze 406 × 206 mm (rozkładówka ze spadem).
8. **Ustawienia** (`/admin/`) - formaty, materiały, kolory, tłoczenia i ceny; wszystko
   po polsku, bez wchodzenia w kod.

## Model danych

| Model | Rola |
| --- | --- |
| `Project` | projekt albumu: klient, parametry, status, token linku |
| `SessionPhoto` | zdjęcie z sesji przypisane do projektu |
| `Spread` → `Page` → `Slot` | rozkładówka, strona z układem, miejsce na zdjęcie z kadrowaniem |
| `AlbumFormat`, `CoverMaterial`, `CoverColor`, `Foil` | cennik i oferta pracowni |
| `ProjectEvent` | historia: kto i kiedy co zrobił |

## API kreatora

| Metoda | Adres | Opis |
| --- | --- | --- |
| GET | `/api/projekt/<token>` | cały projekt w JSON |
| POST | `/api/projekt/<token>/zapisz` | zapis układu (autozapis), `submit: true` oddaje projekt |
| POST | `/api/projekt/<token>/zdjecia` | wgranie zdjęć |
| POST | `/api/projekt/<token>/zdjecia/<id>/ulubione` | przełączenie ulubionego |

Klient może zapisywać tylko wtedy, gdy pracownia włączyła edycję - inaczej serwer odpowiada
błędem 403 i album jest wyłącznie do przeglądania.

## Przed pokazaniem w internecie

Do pracy na komputerze wystarcza ustawienie domyślne. Gdyby aplikacja miała trafić na serwer,
trzeba w `config/settings.py` ustawić `DEBUG = False`, wpisać własny `SECRET_KEY`, ograniczyć
`ALLOWED_HOSTS` i podać serwerowi katalogi `static/` oraz `media/`.
