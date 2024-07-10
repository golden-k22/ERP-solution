from django.contrib.auth.decorators import login_required
from django.http.response import HttpResponse
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView
from django.shortcuts import render, redirect
from accounts.models import User
from notifications.signals import notify

# Create your views here.
@method_decorator(login_required, name='dispatch')
class Dashboard(TemplateView):
    template_name = "dashboard/dashboard.html"

def handler404(request, exception):
    return render(request, '404.html', status=404)

def handler500(request):
    return render(request, '500.html', status=500)

def message(request):
    try:
        if request.method == 'POST':
            sender = User.objects.get(username=request.user)
            receiver = User.objects.get(id=request.POST.get('user_id'))
            for receiver in User.objects.all():
                notify.send(sender, recipient=receiver, verb='Message', description=request.POST.get('message'))
            return redirect('/')
        else:
            return HttpResponse("Invalid request")
    except Exception as e:
        print(e)
        return HttpResponse("Please login from admin site for sending messages")

def schedule_cron_job():
    print("cron job starting")
