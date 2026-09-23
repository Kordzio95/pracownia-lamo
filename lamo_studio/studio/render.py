"""Robienie pliku PDF do druku z rozkładówek.

Przeglądarka liczy w pikselach ekranu, a drukarnia chce milimetry przy 300 dpi.
Tutaj biorę te same dane co kreator (układ, odstępy, kadr) i przeliczam je na wydruk,
dzięki temu wydruk wygląda tak jak podgląd.
"""

from __future__ import annotations  # żeby zapis typów działał też na starszym Pythonie

import io  # PDF robię w pamięci, bez zapisywania na dysk
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFont  # Pillow - obrazki, rysowanie, zapis do PDF

DPI = 300  # standard do druku
MM_PER_INCH = 25.4  # 1 cal = 25,4 mm
BLEED_MM = 3.0          # spad
# spad to 3 mm zdjęcia wychodzące poza format, żeby po obcięciu nie było białej krawędzi
SCREEN_PAGE_PX = 520.0  # tyle ma strona w kreatorze na ekranie
# potrzebne do przeliczenia odstępów z ekranu na wydruk

# układ -> (ile kolumn, wysokości rzędów, komórki: kolumna, rząd, colspan, rowspan)
LAYOUTS: dict[str, tuple[int, list[float], list[tuple[int, int, int, int]]]] = {
    # to samo co siatka CSS w kreatorze, tylko w liczbach
    # colspan/rowspan jak w tabeli HTML, zdjęcie może zająć np 2 kolumny
    "full": (1, [1.0], [(0, 0, 1, 1)]),
    "two_v": (2, [1.0], [(0, 0, 1, 1), (1, 0, 1, 1)]),
    "two_h": (1, [1.0, 1.0], [(0, 0, 1, 1), (0, 1, 1, 1)]),
    "three": (2, [1.4, 1.0], [(0, 0, 2, 1), (0, 1, 1, 1), (1, 1, 1, 1)]),
    # górny rząd wyższy (1.4), duże zdjęcie na górze i dwa małe pod spodem
    "four": (2, [1.0, 1.0], [(0, 0, 1, 1), (1, 0, 1, 1), (0, 1, 1, 1), (1, 1, 1, 1)]),
    "six": (3, [1.0, 1.0], [(c, r, 1, 1) for r in range(2) for c in range(3)]),
    # 6 miejsc robię pętlą zamiast wypisywać ręcznie
    "frame": (1, [1.0], [(0, 0, 1, 1)]),  # jedno zdjęcie z większym marginesem (niżej)
    "blank": (1, [1.0], []),  # pusta strona
}


def mm_to_px(mm: float) -> int:
    """Milimetry na piksele przy 300 dpi."""
    # np strona 200 mm -> 200 / 25,4 * 300 = 2362 px
    # max(1, ...) żeby nigdy nie wyszło 0
    return max(1, round(mm / MM_PER_INCH * DPI))


def parse_hex(value: str, fallback=(255, 252, 248)) -> tuple[int, int, int]:
    """Kolor #RRGGBB na trzy liczby (R, G, B) dla Pillow."""
    text = (value or "").strip().lstrip("#")
    if len(text) != 6:
        return fallback  # zły kolor to biorę domyślny, zamiast się wywalić
    try:
        return tuple(int(text[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
        # po 2 znaki na kolor, liczone szesnastkowo
    except ValueError:
        return fallback


@dataclass
class Box:
    """Prostokąt w pikselach: x, y lewego górnego rogu i szerokość, wysokość."""
    # zamiast krotki (x, y, w, h), bo box.w łatwiej się czyta niż box[2]
    x: int
    y: int
    w: int
    h: int


def cells(layout: str, area: Box, gap: int) -> list[Box]:
    """Dzieli stronę na miejsca na zdjęcia wg układu."""
    cols, rows, spec = LAYOUTS.get(layout, LAYOUTS["two_v"])
    # nieznany układ = domyślny
    if not spec:
        return []  # pusta strona

    col_w = (area.w - gap * (cols - 1)) / cols
    # szerokość kolumny: odejmuję odstępy między kolumnami i dzielę resztę po równo
    total = sum(rows)
    row_h = [(area.h - gap * (len(rows) - 1)) * value / total for value in rows]
    # wysokości rzędów wg proporcji z LAYOUTS

    row_top = []  # gdzie zaczyna się każdy rząd
    top = 0.0
    for height in row_h:
        row_top.append(top)
        top += height + gap

    boxes = []
    for col, row, colspan, rowspan in spec:
        width = col_w * colspan + gap * (colspan - 1)
        # jak zdjęcie zajmuje 2 kolumny to bierze też odstęp między nimi
        height = sum(row_h[row:row + rowspan]) + gap * (rowspan - 1)
        boxes.append(
            Box(
                x=area.x + round(col * (col_w + gap)),
                y=area.y + round(row_top[row]),
                w=round(width),
                h=round(height),
            )
        )
        # zaokrąglam dopiero na końcu, inaczej błędy by się sumowały
    return boxes


def fit_cover(image: Image.Image, box: Box, zoom: float, off_x: float, off_y: float) -> Image.Image:
    """Wycina ze zdjęcia kadr który wypełni miejsce (z zoomem i przesunięciem)."""
    # działa jak object-fit: cover w CSS. wycinam z oryginału, więc jest ostre

    zoom = max(1.0, min(4.0, float(zoom or 1)))  # zoom od 1 do 4, tak jak w kreatorze
    src_w, src_h = image.size
    target = box.w / box.h  # proporcja miejsca

    # największy kawałek zdjęcia o proporcji miejsca
    if src_w / src_h > target:
        # zdjęcie szersze - cała wysokość, obcinam boki
        crop_h = src_h
        crop_w = crop_h * target
    else:
        # zdjęcie wyższe - cała szerokość, obcinam górę i dół
        crop_w = src_w
        crop_h = crop_w / target

    # zoom = mniejszy wycinek rozciągnięty na to samo miejsce
    crop_w /= zoom
    crop_h /= zoom

    # przesunięcie w procentach, z minusem bo jak zdjęcie idzie w prawo to kadr w lewo
    left = (src_w - crop_w) / 2 - (off_x or 0) / 100 * crop_w
    top = (src_h - crop_h) / 2 - (off_y or 0) / 100 * crop_h

    left = max(0, min(src_w - crop_w, left))
    top = max(0, min(src_h - crop_h, top))
    # pilnuję żeby kadr nie wyszedł poza zdjęcie (byłaby czarna plama)

    crop = image.crop((round(left), round(top), round(left + crop_w), round(top + crop_h)))
    return crop.resize((box.w, box.h), Image.LANCZOS)
    # LANCZOS - najlepsza jakość skalowania, trochę wolniej ale ostrzej


def load_font(size: int):
    """Szuka czcionki która jest na komputerze."""
    # na Windowsie i Linuksie czcionki są w innych miejscach, więc próbuję po kolei
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/georgia.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue  # nie ma, próbuję następną
    return ImageFont.load_default()
    # jak żadnej nie ma to wbudowana, brzydka ale działa


def render_spread(spread, project, *, with_bleed: bool, marks: bool) -> Image.Image:
    """Rysuje jedną rozkładówkę (2 strony) jako obrazek 300 dpi."""
    # dwie strony razem bo w drukarni to jeden arkusz

    page_w = mm_to_px(float(project.album_format.width_cm) * 10)  # cm -> mm -> px
    page_h = mm_to_px(float(project.album_format.height_cm) * 10)
    bleed = mm_to_px(BLEED_MM) if with_bleed else 0

    sheet = Image.new("RGB", (page_w * 2 + bleed * 2, page_h + bleed * 2), (255, 255, 255))
    # arkusz = 2 strony + spad z każdej strony. np album 20x20 daje 4794 x 2432 px
    draw = ImageDraw.Draw(sheet)
    bg = parse_hex(project.page_bg)
    draw.rectangle([0, 0, sheet.width, sheet.height], fill=bg)
    # tło na cały arkusz razem ze spadem

    # przeliczenie odstępów z ekranu na druk
    scale = page_w / SCREEN_PAGE_PX
    # np 2362 / 520 = ok 4,5 czyli 10 px na ekranie to ok 45 px na wydruku
    gap = max(0, round(project.page_gap * scale))
    pad = max(0, round(project.page_padding * scale))
    caption_font = load_font(round(page_h * 0.028))
    # czcionka jako procent wysokości strony, żeby pasowała do każdego formatu

    pages = {page.side: page for page in spread.pages.all()}
    for order, side in enumerate(("L", "R")):  # 0 = lewa, 1 = prawa
        page = pages.get(side)
        if page is None:
            continue  # nie ma strony, lecę dalej
        origin_x = bleed + order * page_w  # prawa strona zaczyna się dalej o szerokość strony
        area = Box(origin_x + pad, bleed + pad, page_w - pad * 2, page_h - pad * 2)
        # miejsce na zdjęcia = strona minus marginesy

        if page.layout == "frame":
            inset_x, inset_y = round(area.w * 0.10), round(area.h * 0.10)
            area = Box(area.x + inset_x, area.y + inset_y, area.w - inset_x * 2, area.h - inset_y * 2)
            # "w ramce" = jedno zdjęcie z dodatkowym marginesem 10%

        caption_band = round(page_h * 0.085) if page.caption else 0
        if caption_band:
            area = Box(area.x, area.y, area.w, area.h - caption_band)
        # jak jest podpis to zostawiam na niego pasek na dole, żeby nie wchodził na zdjęcia

        boxes = cells(page.layout, area, gap)  # dzielę na miejsca
        for slot in page.slots.order_by("index"):
            if slot.index >= len(boxes) or not slot.photo_id:
                continue  # puste miejsce - pomijam
            box = boxes[slot.index]
            try:
                with Image.open(slot.photo.image.path) as source:
                    # with sam zamyka plik po wszystkim
                    photo = source.convert("RGB")
                    # na RGB, żeby PNG z przezroczystością albo CMYK też działały
                    sheet.paste(fit_cover(photo, box, slot.zoom, slot.offset_x, slot.offset_y), (box.x, box.y))
            except (FileNotFoundError, OSError):
                draw.rectangle([box.x, box.y, box.x + box.w, box.y + box.h], fill=(235, 228, 218))
                # jak nie ma pliku to wstawiam szare pole zamiast wywalać cały eksport

        if page.caption:
            text_y = area.y + area.h + caption_band / 2  # środek paska na podpis
            draw.text(
                (origin_x + page_w / 2, text_y),
                page.caption,
                font=caption_font,
                fill=(107, 90, 81),  # ciemny brąz
                anchor="mm",  # tekst wyśrodkowany w tym punkcie
            )

    if marks and bleed:
        # znaczniki cięcia w rogach, pokazują gdzie ciąć. tylko jak jest spad
        mark = round(bleed * 0.8)
        for x in (bleed, sheet.width - bleed):
            for y in (bleed, sheet.height - bleed):
                draw.line([(x, y - mark), (x, y + mark)], fill=(120, 120, 120), width=2)
                draw.line([(x - mark, y), (x + mark, y)], fill=(120, 120, 120), width=2)
        centre = bleed + page_w
        draw.line([(centre, 0), (centre, mark)], fill=(160, 160, 160), width=2)
        draw.line([(centre, sheet.height - mark), (centre, sheet.height)], fill=(160, 160, 160), width=2)
        # kreski na środku góra i dół - tu jest zgięcie albumu

    return sheet


def render_cover(project) -> Image.Image:
    """Pierwsza strona pliku z danymi zamówienia."""
    # to jeszcze nie jest prawdziwa okładka do druku (brakuje grzbietu), na razie strona z info
    page_w = mm_to_px(float(project.album_format.width_cm) * 10)
    page_h = mm_to_px(float(project.album_format.height_cm) * 10)
    sheet = Image.new("RGB", (page_w * 2, page_h), parse_hex(project.cover_color.hex_code))
    # tło w kolorze okładki
    draw = ImageDraw.Draw(sheet)
    title_font = load_font(round(page_h * 0.075))
    small_font = load_font(round(page_h * 0.028))

    centre = (sheet.width / 2, page_h * 0.42)
    draw.text(centre, project.cover_title or project.name, font=title_font, fill=(255, 255, 255), anchor="mm")
    # jak nie ma tytułu to nazwa projektu
    if project.cover_subtitle:
        draw.text((sheet.width / 2, page_h * 0.52), project.cover_subtitle.upper(),
                  font=small_font, fill=(255, 255, 255), anchor="mm")
        # podpis dużymi literami

    lines = [
        # dane zamówienia dla pracowni
        f"format {project.album_format.name}"
        f" · rozkładówka {float(project.album_format.width_cm) * 2:g} × {float(project.album_format.height_cm):g} cm",
        # :g obcina zera, będzie "40" a nie "40.0"
        f"okładka: {project.cover_material.name}, {project.cover_color.name}, {project.foil.name}",
        f"{project.spreads_count} rozkładówek · {project.pages_count} stron · 300 dpi, spad {BLEED_MM:.0f} mm",
        f"klient: {project.client_name or '—'}",
    ]
    for index, line in enumerate(lines):
        draw.text((sheet.width / 2, page_h * 0.72 + index * page_h * 0.045), line,
                  font=small_font, fill=(255, 255, 255), anchor="mm")
        # każda linijka trochę niżej
    return sheet


def build_pdf(project, *, with_bleed: bool = True, marks: bool = True, include_cover: bool = True) -> bytes:
    """Robi cały PDF: strona tytułowa i wszystkie rozkładówki."""
    # gwiazdka * - opcje trzeba podawać po nazwie, np build_pdf(p, with_bleed=False)

    pages: list[Image.Image] = []
    if include_cover:
        pages.append(render_cover(project))
    for spread in project.spreads.prefetch_related("pages__slots__photo").all():
        # pobiera od razu strony, miejsca i zdjęcia, żeby nie pytać bazy sto razy
        pages.append(render_spread(spread, project, with_bleed=with_bleed, marks=marks))
    if not pages:
        pages.append(render_cover(project))
        # PDF musi mieć choć jedną stronę

    buffer = io.BytesIO()  # plik w pamięci
    first, rest = pages[0], pages[1:]
    first.save(
        buffer,
        format="PDF",
        save_all=True,          # wszystkie strony, nie tylko pierwsza
        append_images=rest,     # reszta stron
        resolution=DPI,         # 300 dpi zapisane w pliku
        title=project.name,     # tytuł we właściwościach pliku
        author="Pracownia Lamo",
    )
    for image in pages:
        image.close()  # zwalniam pamięć
    return buffer.getvalue()  # gotowy plik idzie do widoku panel_pdf
