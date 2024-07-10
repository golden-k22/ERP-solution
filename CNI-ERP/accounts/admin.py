from django.contrib import admin
from accounts.models import User, UserAddress, Role, WorkLog, MaterialLog, AssetLog, OTCalculation, Holiday,Privilege, Uom
from django.contrib.auth.admin import UserAdmin
# Register your models here.

class UserIAdmin(UserAdmin):
    fieldsets = (
        (None, {'fields': ('email', 'password', 'username', 'last_login','nric','nationality','wp_type','wp_no',  'role', 'wp_expiry',  'passport_no', 'passport_expiry','dob', 'phone', 'fcm_token', 'signature' )}),
        ('Permissions', {'fields': (
            'is_active',
            'is_staff',
            'is_superuser',
            'groups',
            'user_permissions',
        )}),
    )
    add_fieldsets = (
        (
            None,
            {
                'classes': ('wide',),
                'fields': ('username','email',  'password1', 'password2')
            }
        ),
    )

    list_display = ('username','email', 'phone', 'nric', 'nationality','wp_type', 'wp_no',  'role')
    filter_horizontal = ('groups', 'user_permissions',)

admin.site.register(User, UserIAdmin)
admin.site.register(UserAddress)
admin.site.register(Role)
admin.site.register(WorkLog)
admin.site.register(MaterialLog)
admin.site.register(AssetLog)
admin.site.register(OTCalculation)
admin.site.register(Holiday)
admin.site.register(Privilege)
admin.site.register(Uom)
