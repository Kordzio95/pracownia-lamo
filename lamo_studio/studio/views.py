"""Widoki, czyli co się dzieje po wejściu na dany adres.

Kolejność w pliku:
  1. funkcje pomocnicze (cennik, projekt do JSON, zapis układu),
  2. panel fotografa - tylko po zalogowaniu,
  3. strona klienta - wchodzi się linkiem z tokenem, bez konta,
  4. API dla kreatora - z tym gada JavaScript w przeglądarce.
"""

import json  # kreator wysyła i dostaje dane w JSON

from django.conf import settings
from django.contrib import messages  # komunikaty typu "zapisano" na górze strony
from django.contrib.auth.decorators import login_required  # wpuszcza tylko zalogowanych
from django.db import transaction
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone  # data i godzina ze strefą czasową
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST  # widok przyjmie tylko POST

from .forms import ProjectForm
from .render import build_pdf  # robienie PDF jest w osobnym pliku
from .models import (
    AlbumFormat,
    CoverColor,
    CoverMaterial,
    Foil,
    Page,
    Project,
    ProjectEvent,
    SessionPhoto,
    Slot,
)


# --- pomocnicze ---
def catalog():
    """Aktualny cennik do formularzy i kreatora."""
    # tylko aktywne pozycje, wyłączone znikają z listy ale stare projekty dalej działają
    return {
        "formats": AlbumFormat.objects.filter(is_active=True),
        "materials": CoverMaterial.objects.filter(is_active=True),
        "colors": CoverColor.objects.filter(is_active=True),
        "foils": Foil.objects.filter(is_active=True),
    }


def project_payload(project: Project) -> dict:
    """Cały projekt jako słownik (JSON) dla kreatora."""
    # kreator dostaje to raz przy wejściu i potem pracuje na tym u siebie,
    # dlatego przesuwanie zdjęć jest od razu, bez czekania na serwer

    photos = [
        {
            "id": photo.pk,
            "url": photo.image.url,  # adres pliku
            "name": photo.original_name or photo.image.name.rsplit("/", 1)[-1],
            # jak nie ma oryginalnej nazwy to biorę samą nazwę pliku ze ścieżki
            "fav": photo.is_favorite,
        }
        for photo in project.photos.all()
    ]

    spreads = []
    for spread in project.spreads.prefetch_related("pages__slots").all():
        # prefetch_related pobiera strony i miejsca za jednym razem,
        # inaczej byłoby osobne zapytanie do bazy dla każdej strony
        pages = {}
        for page in spread.pages.all():
            pages[page.side] = {
                "layout": page.layout,
                "caption": page.caption,
                "slots": [
                    None  # puste miejsce = null
                    if slot.photo_id is None
                    else {
                        "photo": slot.photo_id,  # sam numer zdjęcia wystarczy
                        "zoom": slot.zoom,
                        "x": slot.offset_x,
                        "y": slot.offset_y,
                    }
                    for slot in page.slots.all()
                ],
            }
        spreads.append({"L": pages.get("L"), "R": pages.get("R")})  # lewa i prawa strona

    return {
        "id": project.pk,
        "name": project.name,
        "status": project.status,
        "statusLabel": project.get_status_display(),  # polski napis statusu
        "title": project.cover_title,
        "sub": project.cover_subtitle,
        "format": {
            "id": project.album_format_id,
            "name": project.album_format.name,
            "ratio": project.album_format.ratio,  # proporcja strony do rysowania
        },
        "material": {"id": project.cover_material_id, "name": project.cover_material.name},
        "color": {"id": project.cover_color_id, "name": project.cover_color.name, "hex": project.cover_color.hex_code},
        "foil": {"id": project.foil_id, "name": project.foil.name},
        "gap": project.page_gap,
        "pad": project.page_padding,
        "pageBg": project.page_bg,
        "spreadsCount": project.spreads_count,
        "canUpload": project.client_can_upload,
        "canEdit": project.client_editing_enabled,  # czy pokazać narzędzia do edycji
        "clientNote": project.client_note,
        "price": float(project.price()),  # Decimal nie wejdzie do JSON, więc na float
        "photos": photos,
        "pages": spreads,
    }


@transaction.atomic
def apply_layout(project: Project, data: dict, *, by_client: bool):
    """Zapisuje do bazy układ stron który przyszedł z kreatora."""
    # atomic = albo zapisze się wszystko, albo nic, żeby nie został pół stary pół nowy album
    # by_client mówi kto zapisuje - klient może mniej niż fotograf

    spreads_in = data.get("pages") or []  # jak nie ma klucza to pusta lista

    # klient mógł usunąć rozkładówki, więc najpierw kasuję nadmiar a potem dokładam brakujące
    project.spreads.exclude(index__lt=len(spreads_in)).delete()
    project.build_spreads(count=len(spreads_in))

    photo_ids = set(project.photos.values_list("pk", flat=True))
    # numery zdjęć z TEGO projektu. niżej wstawiam tylko zdjęcia z tej listy,
    # więc jak ktoś podstawi numer cudzego zdjęcia to zostanie pominięte

    for index, spread_data in enumerate(spreads_in):
        spread = project.spreads.get(index=index)
        for side in ("L", "R"):
            page_data = spread_data.get(side) or {}
            page, _ = Page.objects.get_or_create(spread=spread, side=side)
            # bierze stronę albo ją tworzy jak jej nie ma

            layout = page_data.get("layout", "two_v")
            page.layout = layout if layout in Page.SLOT_COUNTS else "two_v"
            # nie ufam przeglądarce - nieznany układ zamieniam na domyślny
            page.caption = (page_data.get("caption") or "")[:120]  # przycinam do długości pola
            page.save()
            page.rebuild_slots()  # tyle miejsc ile ma nowy układ

            slots_in = page_data.get("slots") or []
            for slot in page.slots.order_by("index"):
                incoming = slots_in[slot.index] if slot.index < len(slots_in) else None
                # jak lista jest krótsza to nie wywali błędu
                if incoming and incoming.get("photo") in photo_ids:
                    slot.photo_id = incoming["photo"]
                    slot.zoom = float(incoming.get("zoom") or 1)
                    slot.offset_x = float(incoming.get("x") or 0)
                    slot.offset_y = float(incoming.get("y") or 0)
                else:
                    # nie ma zdjęcia albo nie z tego projektu - miejsce puste
                    slot.photo = None
                    slot.zoom, slot.offset_x, slot.offset_y = 1.0, 0, 0
                slot.save()

    # --- ustawienia dla obu (fotograf i klient) ---
    if "gap" in data:
        project.page_gap = max(0, min(40, int(data["gap"])))
        # pilnuję żeby było od 0 do 40, bo ktoś mógłby wysłać np 9999
    if "pad" in data:
        project.page_padding = max(0, min(60, int(data["pad"])))
    if data.get("pageBg"):
        project.page_bg = str(data["pageBg"])[:7]  # kolor #RRGGBB ma 7 znaków

    # --- tylko od klienta ---
    if by_client:
        if "title" in data:
            project.cover_title = str(data["title"])[:60]
        if "sub" in data:
            project.cover_subtitle = str(data["sub"])[:60]
        if data.get("clientNote") is not None:
            project.client_note = str(data["clientNote"])[:2000]
            # "is not None" żeby dało się też skasować uwagi (pusty tekst)
        if project.status in (Project.Status.SENT, Project.Status.DRAFT):
            project.status = Project.Status.IN_PROGRESS
            # pierwszy zapis klienta zmienia status na "klient projektuje"

    project.spreads_count = max(1, len(spreads_in))  # co najmniej 1 rozkładówka
    project.save()


# --- panel fotografa ---
@login_required
def panel_projects(request):
    """Lista projektów fotografa, z filtrem i szukaniem."""
    projects = (
        Project.objects.filter(photographer=request.user)
        # tylko projekty zalogowanego fotografa, cudzych nie widać
        .select_related("album_format", "cover_material", "cover_color", "foil")
        # dociąga format, materiał itd. jednym zapytaniem
        .prefetch_related("photos")
    )

    status = request.GET.get("status")  # filtr z adresu np ?status=submitted
    if status:
        projects = projects.filter(status=status)

    query = request.GET.get("q", "").strip()
    if query:
        projects = projects.filter(name__icontains=query) | projects.filter(client_name__icontains=query)
        # szukanie po nazwie projektu LUB po nazwisku klienta, wielkość liter bez znaczenia

    return render(
        request,
        "studio/panel_projects.html",
        {
            "projects": projects,
            "statuses": Project.Status.choices,  # do zakładek z filtrem
            "active_status": status or "",
            "query": query,
            "counts": {
                # liczniki: ile wszystkich i ile czeka na pracownię
                "all": Project.objects.filter(photographer=request.user).count(),
                "submitted": Project.objects.filter(
                    photographer=request.user, status=Project.Status.SUBMITTED
                ).count(),
            },
        },
    )


@login_required
def panel_project_new(request):
    """Nowy projekt: formularz + od razu można dać zdjęcia."""
    if request.method == "POST":  # POST = zapisz, GET = pokaż pusty formularz
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save(commit=False)
            # jeszcze nie zapisuję, bo trzeba dopisać fotografa
            project.photographer = request.user  # właściciel z logowania, nie z formularza
            project.save()
            project.build_spreads()  # od razu puste rozkładówki
            project.log(ProjectEvent.Kind.CREATED, project.name, request.user)

            for uploaded in request.FILES.getlist("photos"):
                # getlist bo można wybrać dużo plików naraz
                SessionPhoto.objects.create(
                    project=project,
                    image=uploaded,
                    original_name=uploaded.name[:200],
                    order=project.photos.count(),  # kolejność jak przy wgrywaniu
                )
            count = project.photos.count()
            if count:
                project.log(ProjectEvent.Kind.PHOTOS, f"wgrano {count} zdjęć", request.user)
            messages.success(request, f"Projekt „{project.name}” utworzony.")
            return redirect(project.get_absolute_url())
            # przekierowanie po zapisie, żeby F5 nie zrobiło drugiego projektu
    else:
        form = ProjectForm()
    return render(request, "studio/panel_project_form.html", {"form": form, "is_new": True})


@login_required
def panel_project_detail(request, pk):
    """Karta projektu: parametry, zdjęcia, link, historia."""
    project = get_object_or_404(
        Project.objects.select_related("album_format", "cover_material", "cover_color", "foil"),
        pk=pk,
        photographer=request.user,  # musi być mój projekt
    )
    # cudzy projekt = 404, nie pokazuje nawet że taki istnieje (jest na to test)

    return render(
        request,
        "studio/panel_project_detail.html",
        {
            "project": project,
            "photos": project.photos.all(),
            "events": project.events.all()[:25],  # ostatnie 25 wpisów
            "client_link": request.build_absolute_uri(project.client_url()),
            # pełny link z adresem serwera, żeby dało się go skopiować i wysłać
            "spreads": project.spreads.prefetch_related("pages__slots__photo"),
            "studio_email": settings.STUDIO_EMAIL,
        },
    )


@login_required
def panel_project_edit(request, pk):
    """Edycja parametrów projektu."""
    project = get_object_or_404(Project, pk=pk, photographer=request.user)
    if request.method == "POST":
        form = ProjectForm(request.POST, instance=project)
        # ten sam formularz co przy nowym, tylko z danymi projektu
        if form.is_valid():
            form.save()
            project.build_spreads()
            # jak zwiększono liczbę rozkładówek to dokłada brakujące, reszta zostaje
            messages.success(request, "Parametry projektu zapisane.")
            return redirect(project.get_absolute_url())
    else:
        form = ProjectForm(instance=project)  # formularz z obecnymi wartościami
    return render(request, "studio/panel_project_form.html", {"form": form, "project": project})


@login_required
@require_POST
def panel_photos_upload(request, pk):
    """Dodanie zdjęć do projektu."""
    # tylko POST, bo to zmienia dane
    project = get_object_or_404(Project, pk=pk, photographer=request.user)
    files = request.FILES.getlist("photos")
    start = project.photos.count()  # numeruję dalej od tego co już jest
    for offset, uploaded in enumerate(files):
        SessionPhoto.objects.create(
            project=project,
            image=uploaded,
            original_name=uploaded.name[:200],
            order=start + offset,
        )
    if files:
        project.log(ProjectEvent.Kind.PHOTOS, f"wgrano {len(files)} zdjęć", request.user)
        messages.success(request, f"Dodano {len(files)} zdjęć do sesji.")
    else:
        messages.error(request, "Nie wybrano żadnych plików.")
    return redirect(project.get_absolute_url())


@login_required
@require_POST
def panel_photo_delete(request, pk, photo_id):
    """Usuwa zdjęcie z sesji."""
    project = get_object_or_404(Project, pk=pk, photographer=request.user)
    photo = get_object_or_404(SessionPhoto, pk=photo_id, project=project)
    # sprawdzam dwie rzeczy: projekt mój i zdjęcie z tego projektu
    photo.delete()
    # miejsca gdzie było to zdjęcie robią się puste (SET_NULL w modelu)
    messages.success(request, "Zdjęcie usunięte z sesji.")
    return redirect(project.get_absolute_url())


@login_required
@require_POST
def panel_project_action(request, pk):
    """Jeden adres na drobne akcje z karty projektu."""
    # co zrobić mówi ukryte pole "action" w formularzu
    project = get_object_or_404(Project, pk=pk, photographer=request.user)
    action = request.POST.get("action")

    if action == "enable_client":
        # otwieram kreator dla klienta
        project.client_editing_enabled = True
        if project.status == Project.Status.DRAFT:
            project.status = Project.Status.SENT  # status sam przeskakuje dalej
        project.save()
        project.log(ProjectEvent.Kind.LINK, "udostępniono kreator klientowi", request.user)
        messages.success(request, "Klient może teraz projektować album — wyślij mu link.")

    elif action == "disable_client":
        # blokuję edycję, np jak album idzie do druku
        project.client_editing_enabled = False
        project.save()
        project.log(ProjectEvent.Kind.STATUS, "zablokowano edycję klientowi", request.user)
        messages.success(request, "Edycja przez klienta wyłączona.")

    elif action == "reset_token":
        # nowy link, stary przestaje działać (np jak link poszedł do złej osoby)
        project.reset_token()
        project.log(ProjectEvent.Kind.LINK, "wygenerowano nowy link", request.user)
        messages.success(request, "Nowy link wygenerowany — stary przestał działać.")

    elif action == "set_status":
        status = request.POST.get("status")
        if status in dict(Project.Status.choices):
            # tylko dozwolone statusy, żeby nie wpisać byle czego
            project.status = status
            project.save()
            project.log(ProjectEvent.Kind.STATUS, project.get_status_display(), request.user)
            messages.success(request, f"Status: {project.get_status_display()}.")

    elif action == "note":
        project.note = request.POST.get("note", "")[:2000]
        project.save()
        project.log(ProjectEvent.Kind.NOTE, "zaktualizowano notatkę", request.user)
        messages.success(request, "Notatka zapisana.")

    return redirect(project.get_absolute_url())  # wracam na kartę projektu


@login_required
def panel_designer(request, pk):
    """Kreator dla fotografa - ten sam co u klienta, tylko z pełnymi prawami."""
    # jeden szablon creator.html dla obu, różnica jest w zmiennej "mode"
    project = get_object_or_404(Project, pk=pk, photographer=request.user)
    project.build_spreads()  # na wszelki wypadek, jakby brakowało rozkładówek
    return render(
        request,
        "studio/creator.html",
        {
            "project": project,
            "payload": json.dumps(project_payload(project), ensure_ascii=False),
            # projekt od razu w stronie jako JSON, ensure_ascii=False żeby były polskie znaki
            "mode": "studio",  # tryb pracowni - wszystkie narzędzia
            "save_url": f"/api/projekt/{project.token}/zapisz",
            "upload_url": f"/api/projekt/{project.token}/zdjecia",
            **catalog(),  # dorzuca cennik do szablonu
        },
    )


@login_required
def panel_print(request, pk):
    """Arkusz do druku - co jest na której stronie."""
    # to się drukuje na kartce i ma się przy składaniu albumu
    project = get_object_or_404(Project, pk=pk, photographer=request.user)
    rows = []
    for spread in project.spreads.prefetch_related("pages__slots__photo"):
        for page in spread.pages.all():
            rows.append(
                {
                    "number": spread.index * 2 + (1 if page.side == "L" else 2),
                    # z numeru rozkładówki robię numer strony: 0 -> strony 1 i 2, 1 -> 3 i 4
                    "layout": page.get_layout_display(),  # polska nazwa układu
                    "caption": page.caption,
                    "photos": [
                        slot.photo.original_name or slot.photo.image.name
                        for slot in page.slots.all()
                        if slot.photo_id  # puste pomijam
                    ],
                }
            )
    rows.sort(key=lambda row: row["number"])  # po kolei strona po stronie
    return render(request, "studio/panel_print.html", {"project": project, "rows": rows})


@login_required
def panel_pdf(request, pk):
    """Pobranie PDF do druku (300 dpi)."""
    project = get_object_or_404(Project, pk=pk, photographer=request.user)

    # opcje z adresu, domyślnie wszystko włączone
    with_bleed = request.GET.get("spad", "1") == "1"  # spad 3 mm
    marks = request.GET.get("znaczniki", "1") == "1"  # znaczniki cięcia
    cover = request.GET.get("okladka", "1") == "1"  # strona z okładką

    pdf = build_pdf(project, with_bleed=with_bleed, marks=marks, include_cover=cover)
    # całe robienie PDF jest w render.py
    project.log(ProjectEvent.Kind.NOTE, "wyeksportowano PDF do druku", request.user)

    safe = "".join(ch if ch.isalnum() or ch in " -_" else "_" for ch in project.name).strip() or "album"
    # czyszczę nazwę pliku z dziwnych znaków (/ : itd), jak nic nie zostanie to "album"

    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{safe} - do druku.pdf"'
    # attachment = plik się pobiera zamiast otwierać w przeglądarce
    return response


# --- strona klienta ---
def client_creator(request, token):
    """Kreator dla klienta, wchodzi się linkiem z tokenem."""
    # bez logowania, bo klient nie ma konta. zabezpieczeniem jest losowy token
    project = get_object_or_404(Project, token=token)
    # zły token = zwykłe 404
    project.build_spreads()
    return render(
        request,
        "studio/creator.html",  # ten sam szablon co u fotografa
        {
            "project": project,
            "payload": json.dumps(project_payload(project), ensure_ascii=False),
            "mode": "client",  # tryb klienta - bez narzędzi pracowni
            "save_url": f"/api/projekt/{project.token}/zapisz",
            "upload_url": f"/api/projekt/{project.token}/zdjecia",
            "studio_email": settings.STUDIO_EMAIL,  # kontakt do pracowni
            **catalog(),
        },
    )


# --- API dla kreatora ---
# te funkcje woła JavaScript z kreatora, odpowiadają JSON-em a nie stroną
#
# csrf_exempt wyłącza ochronę CSRF, bo klient nie ma konta ani sesji.
# to jest słabe miejsce, do poprawy - np. token CSRF dawany przy wejściu w link.
# na razie chroni to tylko to, że trzeba znać token projektu


@csrf_exempt
@require_POST
@transaction.atomic
def api_save(request, token):
    """Zapis układu z kreatora (autozapis i oddanie projektu)."""
    project = get_object_or_404(Project, token=token)

    by_client = not (request.user.is_authenticated and request.user == project.photographer)
    # jak zalogowany jest właściciel to pracownia, w każdym innym wypadku traktuję jako klienta

    if by_client and not project.client_editing_enabled:
        return JsonResponse({"ok": False, "error": "Pracownia zablokowała edycję tego projektu."}, status=403)
        # tu jest prawdziwa blokada, na serwerze. schowanie przycisków by nie wystarczyło

    try:
        data = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return HttpResponseBadRequest("nieprawidłowe dane")
        # zepsuty JSON = błąd 400, a nie wywalenie serwera

    apply_layout(project, data, by_client=by_client)  # zapis jest w funkcji wyżej

    if data.get("submit"):
        # klient kliknął "oddaj do pracowni"
        project.status = Project.Status.SUBMITTED
        project.submitted_at = timezone.now()
        project.save()
        project.log(ProjectEvent.Kind.SUBMITTED, "klient oddał projekt do pracowni")
    elif by_client:
        last = project.events.filter(kind=ProjectEvent.Kind.CLIENT_SAVE).first()
        if not last or (timezone.now() - last.created_at).total_seconds() > 600:
            project.log(ProjectEvent.Kind.CLIENT_SAVE, "autozapis układu")
            # autozapis leci co chwilę, więc do historii wpisuję max raz na 10 minut

    return JsonResponse(
        {
            # odsyłam to co kreator pokazuje po zapisie
            "ok": True,
            "saved_at": timezone.localtime().strftime("%H:%M"),  # godzina zapisu
            "status": project.get_status_display(),
            "used": project.used_slots,  # ile miejsc wypełnione
            "price": float(project.price()),  # cena mogła się zmienić
        }
    )


@csrf_exempt
@require_POST
def api_photos(request, token):
    """Wgrywanie zdjęć z kreatora (pracownia, albo klient jak ma zgodę)."""
    project = get_object_or_404(Project, token=token)
    is_studio = request.user.is_authenticated and request.user == project.photographer

    if not is_studio and not (project.client_can_upload and project.client_editing_enabled):
        return JsonResponse({"ok": False, "error": "Wgrywanie zdjęć jest wyłączone."}, status=403)
        # klient musi mieć włączone oba: projektowanie i wgrywanie

    files = request.FILES.getlist("photos")
    start = project.photos.count()
    created = []
    for offset, uploaded in enumerate(files):
        photo = SessionPhoto.objects.create(
            project=project,
            image=uploaded,
            original_name=uploaded.name[:200],
            order=start + offset,
            uploaded_by_client=not is_studio,  # zaznaczam że to od klienta
        )
        created.append({"id": photo.pk, "url": photo.image.url, "name": photo.original_name, "fav": False})
        # odsyłam nowe zdjęcia, żeby kreator je pokazał bez odświeżania

    if created:
        project.log(
            ProjectEvent.Kind.PHOTOS,
            f"{'pracownia' if is_studio else 'klient'} wgrał(a) {len(created)} zdjęć",
            request.user if is_studio else None,  # klient nie ma konta, więc bez autora
        )
    return JsonResponse({"ok": True, "photos": created})


@csrf_exempt
@require_POST
def api_photo_flag(request, token, photo_id):
    """Gwiazdka "ulubione" przy zdjęciu."""
    project = get_object_or_404(Project, token=token)
    photo = get_object_or_404(SessionPhoto, pk=photo_id, project=project)
    # zdjęcie musi być z tego projektu
    photo.is_favorite = not photo.is_favorite  # przełącza tak/nie
    photo.save(update_fields=["is_favorite"])  # zapisuje tylko to jedno pole
    return JsonResponse({"ok": True, "fav": photo.is_favorite})


def api_project(request, token):
    """Aktualny stan projektu w JSON."""
    project = get_object_or_404(Project, token=token)
    return JsonResponse(project_payload(project))
