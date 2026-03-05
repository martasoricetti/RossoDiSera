
from django.urls import path
from .views import index, dashboard, remove_favorite

app_name = 'weather_app'

urlpatterns = [
    path('', index, name='index'),
    path('dashboard', dashboard, name='dashboard'),
    path('remove/<int:city_id>/', remove_favorite, name='remove_favorite')
]
