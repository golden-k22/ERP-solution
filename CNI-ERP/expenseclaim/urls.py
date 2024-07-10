from django.conf.urls import url
from expenseclaim import views

urlpatterns = [
    url(r'^expenseclaim/$', views.ExpenseClaimView.as_view(), name='all_expenses_claim'),
    url(r'^admin-expense-claim/$', views.ExpenseAdminClaimView.as_view(), name='all_expenses_claim_summary'),
    url(r'^ajax_add_expenses_claim/$', views.expensesclaimadd, name='ajax_add_expenses_claim'),
    url(r'^ajax_delete_expenses_claim/$', views.expenseClaimdelete, name='ajax_delete_expenses_claim'),
    url(r'^ajax_delete_expense_item/$', views.expenseClaimItemdelete, name='ajax_delete_expense_item'),
    url(r'^ajax_get_expenses_claim/$', views.getExpensesClaim, name='ajax_get_expenses_claim'),
    url(r'^all-expenses-detail/(?P<pk>[0-9]+)/$', views.ExpenseAdminClaimDetailView.as_view(), name='all_expenses_detail'),
    url(r'^expenses-claim-detail/(?P<pk>[0-9]+)/$', views.ExpenseClaimDetailView.as_view(), name='expenses_claim_detail'),
    url(r'^ajax_check_expenseclaim/$', views.check_expenses_number, name='ajax_check_expenseclaim'),
    url(r'^ajax_update_expenses_claim/$', views.UpdateExpenses, name='ajax_update_expenses_claim'),
    url(r'^ajax_add_expenses_details/$', views.expensesclaimdetailsadd, name='ajax_add_expenses_details'),
    url(r'^ajax_update_expenses_file/$', views.expensesclaimfilesadd, name='ajax_update_expenses_file'),
    url(r'^ajax_delete_expenses_claim_file/$', views.expenseClaimFiledelete, name='ajax_delete_expenses_claim_file'),
    url(r'^export_claim_pdf/(?P<value>\w+)/$', views.exportClaimPDF, name='export_claim_pdf'),
    url(r'^ajax_get_expenses_item/$', views.getExpenseItem, name='ajax_get_expenses_item'),
    url(r'^ajax_check_receipt_no/$', views.checkReceiptNo, name='ajax_check_receipt_no'),
]
