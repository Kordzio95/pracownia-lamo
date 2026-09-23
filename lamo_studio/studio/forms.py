"""Formularz projektu.

ModelForm robi pola sam z modelu, więc nie muszę ich pisać drugi raz.
"""

from django import forms

from .models import Project


class MultiFileInput(forms.ClearableFileInput):
    """Pole do wybrania kilku plików naraz."""

    # Django standardowo pozwala na jeden plik, a fotograf wrzuca całą sesję
    allow_multiple_selected = True


class MultiFileField(forms.FileField):
    """Pole które zwraca listę plików a nie jeden plik."""

    widget = MultiFileInput

    def clean(self, data, initial=None):
        # sprawdzam każdy plik osobno zwykłą walidacją, puste pomijam
        files = data if isinstance(data, (list, tuple)) else [data]
        return [super(MultiFileField, self).clean(f, initial) for f in files if f]


class ProjectForm(forms.ModelForm):
    """Formularz do nowego projektu i do edycji."""

    photos = MultiFileField(
        # tego pola nie ma w modelu Project, zdjęcia zapisuje widok osobno
        label="Zdjęcia z sesji",
        required=False,  # zdjęcia można dodać później
        widget=MultiFileInput(attrs={"multiple": True, "accept": "image/*"}),
        # accept - w oknie wyboru pokazują się tylko zdjęcia
        help_text="Możesz wgrać wiele plików naraz — także później, w karcie projektu.",
    )

    class Meta:
        model = Project
        fields = [
            # wypisane ręcznie a nie "__all__", żeby nikt nie zmienił przez formularz
            # tokena, statusu albo fotografa
            "name",
            "client_name",
            "client_email",
            "client_phone",
            "album_format",
            "spreads_count",
            "cover_material",
            "cover_color",
            "foil",
            "cover_title",
            "cover_subtitle",
            "client_editing_enabled",
            "client_can_upload",
            "note",
        ]
        widgets = {
            "note": forms.Textarea(attrs={"rows": 3}),  # niska notatka
            "spreads_count": forms.NumberInput(attrs={"min": 1, "max": 60}),
            # od 1 do 60 rozkładówek
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # dodaję klasę CSS "inp" do pól, żeby wszystkie wyglądały tak samo
        for name, field in self.fields.items():
            if name == "photos":
                continue  # pole na pliki ma swój wygląd
            css = field.widget.attrs.get("class", "")
            if isinstance(field.widget, forms.CheckboxInput):
                continue  # checkboxy pomijam
            field.widget.attrs["class"] = (css + " inp").strip()
            # dopisuję do tego co już jest, nie nadpisuję
