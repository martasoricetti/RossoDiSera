from email.policy import default

from django.utils.translation import gettext_lazy as _
import pycountry
import requests
from django.core.exceptions import ValidationError
from django.db import models
from django.forms import ModelForm, Select
import logging
from django import forms
from django.contrib.auth.models import User

logger = logging.getLogger(__name__)


def get_countries_choices():
    empty_choice = [('', '--- Seleziona un Paese ---')]
    country_choices = [
        (c.alpha_2, c.name)
        for c in pycountry.countries
    ]
    country_choices.sort(key=lambda x: x[1])
    return empty_choice + country_choices

class City(models.Model):
    name = models.CharField(max_length=25)
    country_code = models.CharField(max_length=2, choices=get_countries_choices())
    country = models.CharField(max_length=50, blank=True)
    latitude = models.FloatField(blank=True)
    longitude = models.FloatField(blank=True)
    elevation = models.FloatField(blank=True)

    users = models.ManyToManyField(
        User,
        through='FavoriteCity',
        related_name='favorite_cities',
        blank=True
    )

    def __str__(self):
        return self.name

    #for the admin panel, the default is  citys
    class Meta:
        verbose_name_plural = 'cities'

    def clean(self):
        self.name = str(self.name).capitalize().strip()

        if City.objects.filter(name__iexact=self.name, country_code=self.country_code).exists():
            raise ValidationError("Città già presente con questo codice paese")

        url = f"https://geocoding-api.open-meteo.com/v1/search?name={self.name}&count=1&language=it&format=json&countryCode={self.country_code}"
        try:
            res = requests.get(url, timeout=5)
            res.raise_for_status()
            data = res.json()
            results = data.get('results')
            if not results:
                raise ValidationError("Città non trovata")

            first = results[0]
            api_name = first['name']
            country = first['country']
            api_lat = first.get('latitude')
            api_lon = first.get('longitude')
            api_elev = first.get('elevation')

            if api_name.lower() != self.name.lower():
                raise ValidationError("Forse non è la città che stavi cercando")

            if self.latitude != api_lat:
                logger.warning(
                    f"La latitudine per {self.name} è stata corretta tramite API (modello: {self.latitude}, API: {api_lat})")
                self.latitude = api_lat

            if self.longitude != api_lon:
                logger.warning(
                    f"La longitudine per {self.name} è stata corretta tramite API (modello: {self.longitude}, API: {api_lon})")
                self.longitude = api_lon

            if api_elev is not None and self.elevation != api_elev:
                logger.warning(
                    f"L'altitudine per {self.name} è stata corretta tramite API (modello: {self.elevation}, API: {api_elev})")
                self.elevation = api_elev

            self.country = country

        except requests.RequestException:
            raise ValidationError("Errore durante la verifica della città")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class CityForm(forms.Form):
    name = forms.CharField(
        label='Nome città',
        max_length=25,
        widget=forms.TextInput(attrs={
            'class': 'w-full bg-white/90 backdrop-blur-sm placeholder:text-slate-500 text-slate-800 text-lg border border-white/30 rounded-xl px-6 py-4 transition-all duration-300 ease focus:outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-400/50 hover:border-blue-300 shadow-xl',
            'placeholder': 'Inserisci nome città...',
            'autocomplete': 'off'
        })
    )

    country_code = forms.ChoiceField(
        label='Paese',
        choices=[],
        widget=forms.Select(attrs={
            'class': 'w-full bg-white/90 backdrop-blur-sm text-slate-800 text-lg border border-white/30 rounded-xl px-6 py-4 transition-all duration-300 ease focus:outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-400/50 hover:border-blue-300 shadow-xl appearance-none',
        })
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['country_code'].choices = get_countries_choices()


class FavoriteCity(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    city = models.ForeignKey(City, on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.city.name

    class Meta:
        unique_together = ('user', 'city')  # evita duplicati
        verbose_name_plural = 'Favorite Cities'