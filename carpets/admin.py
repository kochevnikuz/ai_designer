# carpets/admin.py
from django.contrib import admin
from .models import Loom, Collection, PaletteColor, CarpetDesign

class PaletteColorInline(admin.TabularInline):
    model = PaletteColor
    extra = 8 # По умолчанию показываем 8 полей для цветов

@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = ('name', 'loom', 'horizontal_nodes', 'color_count')
    inlines = [PaletteColorInline] # Цвета будут редактироваться прямо внутри коллекции

admin.site.register(Loom)
admin.site.register(CarpetDesign)