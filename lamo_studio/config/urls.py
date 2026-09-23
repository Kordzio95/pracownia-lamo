"""Główne adresy projektu. Resztę przekazuję do studio/urls.py."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.shortcuts import redirect
from django.urls import include, path

urlpatterns = [
    path("", lambda request: redirect("studio:projects")),
    # sam adres strony przenosi od razu do panelu
    path("admin/", admin.site.urls),  # admin Django (cennik, dane)
    path(
        "panel/login/",
        # logowanie gotowe z Django, zmieniam tylko wygląd na swój szablon
        auth_views.LoginView.as_view(template_name="studio/login.html"),
        name="login",
    ),
    path("panel/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", include("studio.urls")),  # reszta adresów z aplikacji studio
]

# zdjęcia z folderu media pokazuje Django tylko w trybie DEBUG (lokalnie)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
