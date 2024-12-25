
import json
import os

import pytz
from django.db import IntegrityError
from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect, JsonResponse
from django.utils.decorators import method_decorator
from django.views import generic
from django.utils.safestring import mark_safe
from datetime import timedelta, datetime, date
import calendar
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy, reverse
from notifications.signals import notify

from accounts.models import User, NotificationPrivilege,UserStatus
from calendarapp.models import Event
from calendarapp.utils import Calendar
from calendarapp.forms import EventForm

from django.views.generic import ListView

from sales.decorater import ajax_login_required
from accounts.email import send_mail


def get_date(req_day):
    if req_day:
        year, month = (int(x) for x in req_day.split("-"))
        return date(year, month, day=1)
    return datetime.today()


def prev_month(d):
    first = d.replace(day=1)
    prev_month = first - timedelta(days=1)
    month = "month=" + str(prev_month.year) + "-" + str(prev_month.month)
    return month


def next_month(d):
    days_in_month = calendar.monthrange(d.year, d.month)[1]
    last = d.replace(day=days_in_month)
    next_month = last + timedelta(days=1)
    month = "month=" + str(next_month.year) + "-" + str(next_month.month)
    return month

@login_required(login_url="signup")
def create_event(request):
    form = EventForm(request.POST or None)
    if request.POST and form.is_valid():
        title = form.cleaned_data["title"]
        description = form.cleaned_data["description"]
        start_time = form.cleaned_data["start_time"]
        end_time = form.cleaned_data["end_time"]
        Event.objects.get_or_create(
            user=request.user,
            title=title,
            description=description,
            start_time=start_time,
            end_time=end_time,
        )
        return HttpResponseRedirect(reverse("calendarapp:calendar"))
    return render(request, "event.html", {"form": form})



class CalendarViewNew(LoginRequiredMixin, generic.View):
    login_url = "accounts:signin"
    template_name = "calendarapp/calendar.html"
    form_class = EventForm

    def get(self, request, *args, **kwargs):
        forms = self.form_class()
        events = Event.objects.get_all_events()
        events_month = Event.objects.get_running_events()
        event_list = []
        # start: '2020-09-16T16:00:00'
        for event in events:
            event_list.append(
                {
                    "title": event.title,
                    "start": event.start_time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "end": event.end_time.strftime("%Y-%m-%dT%H:%M:%S"),

                }
            )
        context = {"form": forms, "events": event_list,
                   "events_month": events_month}
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        forms = self.form_class(request.POST)
        if forms.is_valid():
            form = forms.save(commit=False)
            form.user = request.user
            form.save()

            sender = User.objects.filter(role="Managers").first()
            is_email = NotificationPrivilege.objects.get(user_id=sender.id).is_email
            description = '<a href="/calender/">Calendar: New event {0} has been created by {1}. You are cordially.</a>'.format(
                form.title, form.user.first_name)
            user_status=UserStatus.objects.get(status='resigned')
            for receiver in User.objects.exclude(status=user_status).filter(username=form.user.username):
                if receiver.notificationprivilege.project_no_created:
                    notify.send(sender, recipient=receiver, verb='Message', level="success",
                                description=description)
                    if is_email and receiver.email:
                        send_mail(receiver.email, "Project Awarded.", description)
            return redirect("/calender")
        context = {"form": forms}
        return render(request, self.template_name, context)


    def delete(self, request, *args, **kwargs):
        forms = self.form_class(request.POST)
        context = {"form": forms}
        return render(request, self.template_name, context)


class AllEventsListView(ListView):
    """ All event list views """

    template_name = "calendarapp/events_list.html"
    model = Event

    def get_queryset(self):
        return Event.objects.get_all_events(user=self.request.user)


class RunningEventsListView(ListView):
    """ Running events list view """

    template_name = "calendarapp/events_list.html"
    model = Event

    def get_queryset(self):
        return Event.objects.get_running_events(user=self.request.user)

@method_decorator(login_required, name='dispatch')
class EventList(ListView):
    model = Event
    template_name = "calendarapp/events_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['events'] = Event.objects.all()
        return context

@ajax_login_required
def ajax_all_events(request):
    if request.method == "POST":
        events = Event.objects.all().order_by('start_time')
        return render(request, 'calendarapp/ajax-events.html', {'events': events})
@ajax_login_required
def ajax_get_event(request):
    if request.method == "POST":
        event_id = request.POST.get('event_id')
        event = Event.objects.get(id=event_id)
        data = {
            'id': event.id,
            'subject': event.title,
            'location': event.location,
            'description': event.description,
            'start_time': event.start_time.strftime('%d %b, %Y %H:%M'),
            'end_time': event.end_time.strftime('%d %b, %Y %H:%M'),
        }
        return JsonResponse(json.dumps(data), safe=False)
@ajax_login_required
def ajax_filter_events(request):
    if request.method == "POST":
        search_subject = request.POST.get('search_subject')
        daterange = request.POST.get('daterange')
        if daterange:
            startdate = datetime.strptime(daterange.split()[0], '%Y.%m.%d').replace(tzinfo=pytz.utc)
            enddate = datetime.strptime(daterange.split()[2], '%Y.%m.%d').replace(tzinfo=pytz.utc)

        events = Event.objects.all()
        if search_subject!="":
            events=events.filter(title=search_subject)
        if daterange != "":
            events=events.filter(start_time__gte=startdate, start_time__lte=enddate)
        return render(request, 'calendarapp/ajax-events.html', {'events': events})

@ajax_login_required
def ajax_delete_event(request):
    if request.method == "POST":
        event_id = request.POST.get('event_id')
        event = Event.objects.get(id=event_id)
        event.delete()
        return JsonResponse({'status': 'ok'})
@ajax_login_required
def ajax_add_event(request):
    if request.method == "POST":
        event_id=request.POST.get('event_id')
        subject = request.POST.get('subject')
        location = request.POST.get('location')
        description = request.POST.get('description')
        start_time = request.POST.get('start_time')
        end_time = request.POST.get('end_time')
        if start_time=="None":
            start_time=None
        if end_time=="None":
            end_time=None

        if event_id == "-1":
            return JsonResponse({
                "status": "Success",
                "messages": "Event information added!"
            })
        else:
            try:
                event = Event.objects.get(id=event_id)
                event.title = subject
                event.location = location
                event.description = description
                event.start_time = start_time
                event.end_time = end_time
                event.save()

                return JsonResponse({
                    "status": "Success",
                    "messages": "Event information updated!"
                })

            except IntegrityError as e:
                return JsonResponse({
                    "status": "Error",
                    "messages": "Error is existed!"
                })
def task():
    sender = User.objects.filter(role="Managers").first()
    is_email = NotificationPrivilege.objects.get(user_id=sender.id).is_email
    now_date = datetime.now(pytz.timezone(os.getenv("TIME_ZONE"))).date()
    events = Event.objects.all()
    for event in events:
        to_date = event.start_time.date()
        diff_days = (to_date - now_date).days
        if diff_days > 0:
            if diff_days == 1:
                # notification send
                description = '<a href="/event-list/">Calendar: The  event {0} will be held at tomorrow, kindly take note.</a>'.format(
                    event.title)
                user_status=UserStatus.objects.get(status='resigned')
                for receiver in User.objects.exclude(status=user_status).all():
                    if receiver.notificationprivilege.maintenance_reminded:
                        notify.send(sender, recipient=receiver, verb='Message', level="success",
                                    description=description)
                        if is_email and receiver.email:
                            send_mail(receiver.email, "Notification for Event.", description)