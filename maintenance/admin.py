import os

from django.contrib import admin

from maintenance.models import Device, MainSRSignature, MainSr, MainSrItem, Maintenance, MaintenanceFile, Schedule

admin.site.register(Maintenance)
admin.site.register(MaintenanceFile)
admin.site.register(MainSr)
admin.site.register(MainSrItem)
admin.site.register(MainSRSignature)
admin.site.register(Device)

