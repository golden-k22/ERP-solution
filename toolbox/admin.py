from django.contrib import admin
from toolbox.models import ToolBox, ToolBoxItem, ToolBoxAttendeesLog, ToolBoxDescription, ToolBoxObjective

# Register your models here.
admin.site.register(ToolBox)
admin.site.register(ToolBoxItem)
admin.site.register(ToolBoxAttendeesLog)
admin.site.register(ToolBoxObjective)
admin.site.register(ToolBoxDescription)