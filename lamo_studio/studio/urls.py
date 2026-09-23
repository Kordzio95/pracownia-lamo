"""Adresy w aplikacji - jaki adres uruchamia jaką funkcję z views.py.

Adresy są po polsku, bo linki idą do klientów z Polski.
"""

from django.urls import path

from . import views

app_name = "studio"
# dzięki temu w szablonach piszę {% url 'studio:projects' %} zamiast wpisywać adres na sztywno

urlpatterns = [
    # --- panel fotografa (logowanie sprawdza views.py) ---
    path("panel/", views.panel_projects, name="projects"),  # lista projektów
    path("panel/nowy/", views.panel_project_new, name="project_new"),  # nowy projekt
    path("panel/p/<int:pk>/", views.panel_project_detail, name="project_detail"),
    # <int:pk> - numer projektu z adresu, tylko liczba
    path("panel/p/<int:pk>/parametry/", views.panel_project_edit, name="project_edit"),
    path("panel/p/<int:pk>/projektuj/", views.panel_designer, name="designer"),  # kreator dla pracowni
    path("panel/p/<int:pk>/do-druku/", views.panel_print, name="print_sheet"),  # arkusz do druku
    path("panel/p/<int:pk>/pdf/", views.panel_pdf, name="pdf"),  # pobranie PDF
    path("panel/p/<int:pk>/zdjecia/", views.panel_photos_upload, name="photos_upload"),
    path("panel/p/<int:pk>/zdjecia/<int:photo_id>/usun/", views.panel_photo_delete, name="photo_delete"),
    # numer projektu i numer zdjęcia
    path("panel/p/<int:pk>/akcja/", views.panel_project_action, name="project_action"),
    # jedno wejście na różne akcje (status, link, otwarcie dla klienta)

    # --- kreator dla klienta ---
    path("k/<str:token>/", views.client_creator, name="client_creator"),
    # krótki adres bo idzie SMS-em. w adresie jest losowy token a nie numer,
    # bo numer łatwo zgadnąć (/k/5/ -> /k/6/)

    # --- api dla kreatora (JavaScript woła to w tle) ---
    path("api/projekt/<str:token>", views.api_project, name="api_project"),  # stan albumu
    path("api/projekt/<str:token>/zapisz", views.api_save, name="api_save"),  # autozapis
    path("api/projekt/<str:token>/zdjecia", views.api_photos, name="api_photos"),  # dodanie zdjęć
    path("api/projekt/<str:token>/zdjecia/<int:photo_id>/ulubione", views.api_photo_flag, name="api_photo_flag"),
    # api też tylko z tokenem, inaczej dałoby się wyciągnąć dane bokiem
]
