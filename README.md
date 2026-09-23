# Pracownia Lamo - kreator fotoksiążek

Aplikacja dla pracowni fotograficznej. Fotograf zakłada projekt albumu, wgrywa zdjęcia z sesji
i wysyła klientowi jeden link. Klient bez zakładania konta układa album w przeglądarce
(przeciąga zdjęcia, wybiera układy stron, okładkę, podpisy), a gotowy projekt wraca do panelu
pracowni i można go pobrać jako PDF do druku (300 dpi).

Projekt końcowy na kursie programowania w Future Collars, robiony dla prawdziwej pracowni.
Pomysł wzięty z systemu Zalamo, na którym pracuje pracownia (funkcja "klient sam projektuje album").

## Co jest w repo

| Folder | Co to |
| --- | --- |
| `lamo_studio/` | główna aplikacja w Django: panel fotografa, kreator dla klienta, PDF |
| `kreator-web/` | wersja demo kreatora, sama strona HTML bez serwera |

## Co umie

**Panel fotografa** (po zalogowaniu)

- nowy projekt: nazwa, klient, format, ile rozkładówek, materiał i kolor okładki, tłoczenie
- wgrywanie zdjęć z sesji (dużo naraz)
- włączanie/wyłączanie projektowania dla klienta i wgrywania zdjęć przez klienta
- link z tokenem dla klienta, można zrobić nowy link
- statusy projektu i historia
- arkusz do druku i PDF
- cena liczona z cennika

**Kreator dla klienta** (tylko link, bez konta)

- 8 układów strony, przeciąganie zdjęć myszką i palcem
- przybliżanie i przesuwanie zdjęcia w ramce
- podpisy, tło stron, odstępy, marginesy
- rozłóż automatycznie, cofnij, autozapis

**PDF do druku**

- zdjęcia brane z oryginałów, nie z miniatur
- 300 dpi, spad 3 mm, znaczniki cięcia, strona z danymi zamówienia

## Technologie

- Python 3.12+, Django 5.2
- SQLite
- HTML, CSS i zwykły JavaScript (fetch + JSON)
- Pillow do zdjęć i PDF (+ pillow-heif do zdjęć z iPhone)
- testy w `django.test`

## Jak uruchomić (Windows, PowerShell)

```powershell
git clone https://github.com/Kordzio95/pracownia-lamo.git
cd pracownia-lamo\lamo_studio
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py seed
python manage.py runserver
```

`seed` wrzuca cennik i robi konto **monika / lamo12345**.

- panel: http://127.0.0.1:8000/panel/
- klient: link z tokenem, jest na karcie projektu

## Testy

```bash
python manage.py test
```

Sprawdzają m.in. tokeny, liczenie ceny, rozkładówki, czy niezalogowany nie wejdzie do panelu,
czy nie widać cudzych projektów, blokadę zapisu dla klienta i pobieranie PDF.

## Tabele w bazie

```
User (fotograf)
  └── Project - token, status, klient, co klient może
        ├── SessionPhoto   zdjęcia z sesji
        ├── ProjectEvent   historia
        └── Spread         rozkładówka
              └── Page     strona (lewa, prawa)
                    └── Slot   miejsce na zdjęcie + kadr (zoom, x, y)

Cennik: AlbumFormat, CoverMaterial, CoverColor, Foil
```

## Bezpieczeństwo

- w panelu każdy widzi tylko swoje projekty, cudzy projekt daje 404
- link dla klienta ma losowy token, a nie numer projektu
- jak fotograf wyłączy edycję, zapis klienta dostaje 403
- serwer przyjmuje tylko zdjęcia z danego projektu
- PDF tylko po zalogowaniu

## Co dalej

Na razie działa lokalnie na komputerze. Do zrobienia: okładka z grzbietem liczonym z ilości stron,
komentarze klienta przy rozkładówkach, wrzucenie na serwer z PostgreSQL.
