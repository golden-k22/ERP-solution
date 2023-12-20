from django.shortcuts import render
from django.contrib.auth.hashers import make_password
from accounts.models import User
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from sales.decorater import ajax_login_required
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView
from notifications.signals import notify
# Create your views here.

@login_required
def change_password(request):
    if request.method == "POST":
        newpassword = request.POST.get('newpassword') 
        reset_id = request.POST.get('reset_id')
        password = make_password(newpassword)
        user = User.objects.get(id=reset_id)
        user.password = password
        user.save()
        update_session_auth_hash(request, user)

        #notification send
        sender = request.user
        description = 'Password of ' + user.empid +  ' - was changed by ' + request.user.username
        for receiver in User.objects.all():
            if receiver.notificationprivilege.password_change:
                notify.send(sender, recipient=receiver, verb='Message', level="success", description=description)

        return JsonResponse({'status': 'ok', 'messages': "Password is changed successfully"})

    else:
        return render(request, "userprofile/change-password.html")

@ajax_login_required
def check_password(request):
    if request.method == "POST":
        currentpassword = request.POST.get('currentpassword') 
        reset_id = request.POST.get('reset_id')
        user = User.objects.get(id=reset_id)
        if user.check_password(currentpassword):
            
            return JsonResponse({'status': 'ok'})
        else:
            return JsonResponse({'status': 'no'})

@method_decorator(login_required, name='dispatch')
class AboutView(TemplateView):
    template_name = "userprofile/about.html"


