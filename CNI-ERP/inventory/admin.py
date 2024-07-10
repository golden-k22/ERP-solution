from django.contrib import admin
from inventory.models import Material, Asset, PPE, Hardware, Stationary
# Register your models here.
admin.site.register(Material)
admin.site.register(Asset)
admin.site.register(PPE)
admin.site.register(Stationary)
admin.site.register(Hardware)