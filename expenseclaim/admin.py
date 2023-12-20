from django.contrib import admin
from expenseclaim.models import ExpensesClaim, ExpensesClaimDetail

# Register your models here.
admin.site.register(ExpensesClaim)
admin.site.register(ExpensesClaimDetail)