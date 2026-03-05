from django.contrib import admin
from .models import City, FavoriteCity

admin.site.register(City)
admin.site.register(FavoriteCity)