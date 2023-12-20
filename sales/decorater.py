from functools import wraps
from django.http import HttpResponse
import json
from django.shortcuts import render

def ajax_login_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated:
            return view_func(request, *args, **kwargs)
        jsondata = json.dumps({ 'not_authenticated': True })
        return HttpResponse(jsondata, content_type='application/json')
    return wrapper

def sale_report_privilege_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.privilege.sales_report == "Full Access":
            return view_func(request, *args, **kwargs)
        else:
            return render(request, 'not_allowed.html')
    return wrapper

def admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.is_staff == True:
            return view_func(request, *args, **kwargs)
        else:

            return render(request, 'not_allowed.html')
    return wrapper