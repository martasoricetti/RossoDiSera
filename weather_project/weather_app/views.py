from cms.views import login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import render, redirect
from .models import City, CityForm, FavoriteCity
import requests
from django.contrib import messages

def find_city (city_name, country_code):
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={city_name}&count=1&language=it&format=json&countryCode={country_code}"
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

        if api_name.lower() != city_name.lower():
            raise ValidationError("Forse non è la città che stavi cercando")

        return {'country': country,
                'lat': api_lat,
                'lon': api_lon,
                'el':api_elev}

    except requests.RequestException:
        raise ValidationError("Errore durante la verifica della città")

def fetch_weather (name, country_code, country, lat,long,el):
    WEATHER_CODES = {
        0: {"desc": "Clear sky", "icon": "sun"},
        1: {"desc": "Mainly clear", "icon": "sun"},
        2: {"desc": "Partly cloudy", "icon": "cloud-sun"},
        3: {"desc": "Overcast", "icon": "cloud"},
        45: {"desc": "Fog", "icon": "smog"},
        48: {"desc": "Depositing rime fog", "icon": "smog"},
        51: {"desc": "Light Drizzle", "icon": "cloud-drizzle"},
        53: {"desc": "Moderate Drizzle", "icon": "cloud-drizzle"},
        55: {"desc": "Dense Drizzle", "icon": "cloud-rain"},
        56: {"desc": "Light Freezing Drizzle", "icon": "cloud-hail-mixed"},
        57: {"desc": "Dense Freezing Drizzle", "icon": "cloud-hail-mixed"},
        61: {"desc": "Slight Rain", "icon": "cloud-sun-rain"},
        63: {"desc": "Moderate Rain", "icon": "cloud-rain"},
        65: {"desc": "Heavy Rain", "icon": "cloud-showers-heavy"},
        66: {"desc": "Light Freezing Rain", "icon": "cloud-hail-mixed"},
        67: {"desc": "Heavy Freezing Rain", "icon": "cloud-hail-mixed"},
        71: {"desc": "Slight Snow", "icon": "snowflake"},
        73: {"desc": "Moderate Snow", "icon": "snowflake"},
        75: {"desc": "Heavy Snow", "icon": "snowflake"},
        77: {"desc": "Snow grains", "icon": "snowflake"},
        80: {"desc": "Slight Rain Showers", "icon": "cloud-sun-rain"},
        81: {"desc": "Moderate Rain Showers", "icon": "cloud-rain"},
        82: {"desc": "Violent Rain Showers", "icon": "cloud-showers-heavy"},
        85: {"desc": "Slight Snow Showers", "icon": "snowflake"},
        86: {"desc": "Heavy Snow Showers", "icon": "snowflake"},
        95: {"desc": "Thunderstorm", "icon": "bolt"},
        96: {"desc": "Thunderstorm with slight hail", "icon": "cloud-bolt"},
        99: {"desc": "Thunderstorm with heavy hail", "icon": "cloud-bolt"}
    }
    try:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": long,
            "elevation": el,
            "hourly": "temperature_2m",
            "current": ["weather_code", "precipitation", "temperature_2m", "relative_humidity_2m",
                        "apparent_temperature", "wind_speed_10m"],
            "daily": "uv_index_max",
            "timezone": "auto",
        }
        responses = requests.get(url, params=params)
        if responses.status_code == 200:
            weather = responses.json()
            current_weather = weather['current']
            current_units = weather['current_units']
            daily_weather = weather['daily']
            weather_code = current_weather['weather_code']
            description = WEATHER_CODES.get(weather_code)['desc']
            icon = WEATHER_CODES.get(weather_code)['icon']
            weather_data = {
                'city': name,
                'country': country,
                'country_code': country_code,
                'time': current_weather['time'],
                'description': description,
                'icon': icon,
                'temperature': current_weather['temperature_2m'],
                'feels_like_temp': current_weather['apparent_temperature'],
                'humidity': current_weather['relative_humidity_2m'],
                'wind_speed': current_weather['wind_speed_10m'],
                'uv': daily_weather['uv_index_max'][0],
                'units': {
                    'temperature': current_units['temperature_2m'],
                    'humidity': current_units['relative_humidity_2m'],
                    'wind_speed': current_units['wind_speed_10m']
                }
            }
            return weather_data
    except requests.RequestException:
        raise ValidationError(f"Errore durante la richiesta all'API per avere i dati del meteo di {name}")

def index(request):
    weather_data = []

    if request.method == 'POST':
        form = CityForm(request.POST)
        if form.is_valid():

            city_data = form.cleaned_data
            city_name = city_data['name']
            country_code = city_data['country_code']
            city_data_from_api = find_city(city_name, country_code)
            country = city_data_from_api['country']
            lat = city_data_from_api['lat']
            long = city_data_from_api['lon']
            el = city_data_from_api['el']

            weather_data = fetch_weather(city_name, country_code, country, lat, long, el)

    else:
        # Se request.method è GET (cioè quando l'utente apre la pagina la prima volta)
        # Inizializziamo un form vuoto.
        form = CityForm()

    context = {'weather': weather_data, 'form': form}
    return render(request, 'weather_app/index.html', context)

@login_required
def dashboard(request):
    all_weather_data = []
    if request.method == 'POST':
        form = CityForm(request.POST)
        if form.is_valid():
            city_data = form.cleaned_data
            city_name = city_data['name']
            country_code = city_data['country_code']
            city_data_from_api = find_city(city_name, country_code)
            country = city_data_from_api['country']
            lat = city_data_from_api['lat']
            long = city_data_from_api['lon']
            el = city_data_from_api['el']

            weather_data = fetch_weather(city_name, country_code, country, lat, long, el)
            city, _ = City.objects.get_or_create(
                name=city_name,
                country_code=country_code,
                defaults={
                    'latitude': lat,
                    'longitude': long,
                    'elevation': el,
                }
            )
            # Aggiunge la città ai preferiti dell'utente
            FavoriteCity.objects.get_or_create(
                user=request.user,
                city=city
            )
            return redirect('weather_app:dashboard')
    else:
        # Se request.method è GET (cioè quando l'utente apre la pagina la prima volta)
        # Inizializziamo un form vuoto.
        form = CityForm()


    # Prendi tutte le città preferite dell'utente loggato.
    # select_related('city') ottimizza le query al DB evitando il problema N+1
    user_favorites = FavoriteCity.objects.filter(user=request.user).select_related('city')

    for fav in user_favorites:
        city = fav.city

        # Usa i dati salvati nel DB per richiamare l'API.
        # Nota: nel tuo codice find_city forniva "country" ma in get_or_create non lo stavi salvando.
        # Usa city.country se lo hai aggiunto al modello City, altrimenti usa city.country_code
        weather_data = fetch_weather(
            city.name,
            city.country_code,
            city.country,  # Sostituisci con city.country se presente nel tuo DB
            city.latitude,
            city.longitude,
            city.elevation
        )
        weather_data["city_id"] = city.id
        # Aggiungiamo i dati di questa città alla lista
        all_weather_data.append(weather_data)

    # Passiamo sia il form che la lista dei dati meteo al template
    context = {
        'form': form,
        'all_weather_data': all_weather_data
    }
    return render(request, 'weather_app/dashboard.html', context)

@login_required
def remove_favorite(request, city_id):
    if request.method == 'POST':
        # Cancella solo il record FavoriteCity di questo utente per questa città
        FavoriteCity.objects.filter(
            user=request.user,
            city_id=city_id  # city_id evita un'ulteriore query al DB
        ).delete()
    return redirect('weather_app:dashboard')
