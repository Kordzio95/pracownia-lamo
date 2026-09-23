"""Panel admina z Django - do cennika i do podglądania danych.

Codziennie fotograf pracuje w /panel/, a tutaj zmienia się ceny
i można zajrzeć w dane jak coś nie działa.
"""

from django.contrib import admin
from django.utils.html import format_html  # bezpieczne wstawianie HTML

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
    Spread,
)


# --- cennik: formaty, materiały, kolory, tłoczenia ---
# ceny zmienia się tutaj w przeglądarce, bez ruszania kodu

@admin.register(AlbumFormat)  # pokazuje tabelę w adminie
class AlbumFormatAdmin(admin.ModelAdmin):
    list_display = ("name", "width_cm", "height_cm", "base_price", "price_per_extra_spread", "is_active")
    # kolumny na liście
    list_editable = ("base_price", "price_per_extra_spread", "is_active")
    # ceny można zmieniać od razu na liście


@admin.register(CoverMaterial)
class CoverMaterialAdmin(admin.ModelAdmin):
    list_display = ("name", "price", "is_active", "order")
    list_editable = ("price", "is_active", "order")


@admin.register(CoverColor)
class CoverColorAdmin(admin.ModelAdmin):
    list_display = ("name", "swatch", "hex_code", "is_active", "order")
    list_editable = ("hex_code", "is_active", "order")

    @admin.display(description="próbka")
    def swatch(self, obj):
        # kółko w danym kolorze, żeby było widać jaki to odcień
        return format_html(
            '<span style="display:inline-block;width:26px;height:26px;border-radius:50%;'
            'border:1px solid #ccc;background:{}"></span>',
            obj.hex_code,
        )


@admin.register(Foil)
class FoilAdmin(admin.ModelAdmin):
    list_display = ("name", "price", "is_active", "order")
    list_editable = ("price", "is_active", "order")


class SessionPhotoInline(admin.TabularInline):
    # zdjęcia pokazane w środku projektu
    model = SessionPhoto
    extra = 0  # bez pustych wierszy
    fields = ("thumb", "image", "original_name", "order", "is_favorite", "uploaded_by_client")
    readonly_fields = ("thumb",)

    @admin.display(description="miniatura")
    def thumb(self, obj):
        if obj.pk and obj.image:
            return format_html('<img src="{}" style="height:56px;border-radius:4px">', obj.image.url)
        return "—"


class ProjectEventInline(admin.TabularInline):
    """Historia projektu."""
    model = ProjectEvent
    extra = 0
    readonly_fields = ("kind", "note", "author", "created_at")
    can_delete = False
    # historii nie da się zmieniać ręcznie, wpisy robi sam program


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "client_name",
        "album_format",
        "spreads_count",
        "status",
        "photos_count",
        "price_display",
        "updated_at",
    )
    list_filter = ("status", "album_format", "cover_material", "photographer")
    # filtry z boku
    search_fields = ("name", "client_name", "client_email", "cover_title")
    # szukanie np po nazwisku klienta
    readonly_fields = ("token", "created_at", "updated_at", "submitted_at", "price_display")
    # tokena i dat nie zmienia się ręcznie, zmiana tokena zepsułaby link klienta
    inlines = [SessionPhotoInline, ProjectEventInline]  # zdjęcia i historia na tej samej stronie
    fieldsets = (
        # pola podzielone na sekcje, bo jest ich dużo
        ("Podstawy", {"fields": ("photographer", "name", "status", "note")}),
        ("Klient", {"fields": ("client_name", "client_email", "client_phone", "client_note")}),
        (
            "Album",
            {
                "fields": (
                    "album_format",
                    "spreads_count",
                    "cover_material",
                    "cover_color",
                    "foil",
                    "cover_title",
                    "cover_subtitle",
                )
            },
        ),
        ("Wygląd stron", {"fields": ("page_gap", "page_padding", "page_bg")}),
        ("Dostęp klienta", {"fields": ("client_editing_enabled", "client_can_upload", "token")}),
        ("Daty i cena", {"fields": ("created_at", "updated_at", "submitted_at", "price_display")}),
    )

    @admin.display(description="zdjęcia")
    def photos_count(self, obj):
        return obj.photos.count()  # ile zdjęć w projekcie

    @admin.display(description="cena")
    def price_display(self, obj):
        return f"{obj.price():.2f} zł"
        # ta sama funkcja price() co w kreatorze, więc cena wszędzie ta sama


class SlotInline(admin.TabularInline):
    model = Slot
    extra = 0


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ("__str__", "layout", "caption")
    list_filter = ("layout", "side")
    inlines = [SlotInline]


@admin.register(Spread)
class SpreadAdmin(admin.ModelAdmin):
    list_display = ("project", "index")
    list_filter = ("project",)


@admin.register(SessionPhoto)
class SessionPhotoAdmin(admin.ModelAdmin):
    list_display = ("original_name", "project", "order", "is_favorite", "times_used", "uploaded_by_client")
    list_filter = ("project", "is_favorite", "uploaded_by_client")


@admin.register(ProjectEvent)
class ProjectEventAdmin(admin.ModelAdmin):
    list_display = ("project", "kind", "note", "author", "created_at")
    list_filter = ("kind", "project")


# --- napisy w nagłówku admina ---
# zamiast "Django administration" nazwa pracowni
admin.site.site_header = "Pracownia Lamo — panel administracyjny"
admin.site.site_title = "Lamo"
admin.site.index_title = "Zarządzanie fotoksiążkami"
