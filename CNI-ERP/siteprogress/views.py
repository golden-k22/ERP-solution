import datetime
import json
import os

import pytz
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.views.generic.list import ListView
from accounts.models import Uom
from sales.models import Quotation, Scope
from siteprogress.models import SiteProgress, ProgressLog, SiteProgressPlan, SiteProgressRepeated
from project.models import Project
from sales.decorater import ajax_login_required
from django.db import IntegrityError
from django.http import JsonResponse
from django.db.models import Sum, Q


# Create your views here.
@method_decorator(login_required, name='dispatch')
class SiteProgressView(ListView):
    model = SiteProgress
    template_name = "siteprogress/progress.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['uoms'] = Uom.objects.all()
        context['projects'] = Project.objects.filter(proj_status__exact="On-going").exclude(proj_name=None)
        context['descriptions'] = SiteProgress.objects.order_by('description').values('description').distinct()
        context['scopedescriptions'] = Scope.objects.all()
        return context


@ajax_login_required
def ajax_get_activity(request):
    if request.method == "POST":
        project_id = request.POST.get("proj_id")
        prject = Project.objects.get(id=project_id)
        quotation = Quotation.objects.get(qtt_id__iexact=prject.qtt_id)
        projectitems = Scope.objects.filter(quotation_id=quotation.id)
        return render(request, 'siteprogress/ajax-description.html', {'scopedescriptions': projectitems})


@ajax_login_required
def overViewList(request):
    if request.method == "POST":
        # overviews = SiteProgress.objects.all()
        overviews = []
        return render(request, 'siteprogress/ajax-overview.html', {'overviews': overviews})

@ajax_login_required
def planningOverViewList(request):
    if request.method == "POST":
        # overviews = SiteProgress.objects.all()
        overviews = []
        return render(request, 'siteprogress/ajax-planning_overview.html', {'overviews': overviews})


@ajax_login_required
def overViewFilterList(request):
    if request.method == "POST":
        proj_id = request.POST.get("proj_id")
        overviews = SiteProgress.objects.filter(project_id=proj_id)

        return render(request, 'siteprogress/ajax-overview.html', {'overviews': overviews})

@ajax_login_required
def planningOverViewFilterList(request):
    if request.method == "POST":
        proj_id = request.POST.get("proj_id")
        overviews = SiteProgressPlan.objects.filter(project_id=proj_id)
        return render(request, 'siteprogress/ajax-planning_overview.html', {'overviews': overviews})


@ajax_login_required
def progressLogList(request):
    if request.method == "POST":
        # progresslogs = ProgressLog.objects.all()
        progresslogs = []
        return render(request, 'siteprogress/ajax-progresslogs.html', {'progresslogs': progresslogs})


@ajax_login_required
def progressLogFilterList(request):
    if request.method == "POST":
        proj_id = request.POST.get("proj_id")
        prject = Project.objects.get(id=proj_id)
        quotation = Quotation.objects.get(qtt_id__iexact=prject.qtt_id)
        projectitems = Scope.objects.filter(quotation_id=quotation.id, parent=None)
        subtotal = 0
        for obj in projectitems:
            obj.childs = Scope.objects.filter(quotation_id=quotation.id, parent_id=obj.id)
            obj.cumulativeqty = \
            SiteProgress.objects.filter(project_id=proj_id, description__iexact=obj.description).aggregate(Sum('qty'))[
                'qty__sum']
            # if obj.allocation_perc and obj.cumulativeqty:
            #     obj.cumulativeperc = float(obj.cumulativeqty / obj.qty) * float(obj.allocation_perc)
            # else:
            #     obj.cumulativeperc = 0
            obj.cumulativeperc = 0
            if obj.childs.count() != 0:
                tempObjperc = float(obj.allocation_perc) / obj.childs.count()

            for subobj in obj.childs:

                subobj.cumulativeqty = \
                SiteProgress.objects.filter(project_id=proj_id, description__iexact=subobj.description).aggregate(
                    Sum('qty'))['qty__sum']
                if subobj.allocation_perc and subobj.cumulativeqty:
                    subobj.cumulativeperc = float(subobj.cumulativeqty / subobj.qty) * float(subobj.allocation_perc)
                else:
                    subobj.cumulativeperc = 0

                obj.cumulativeperc += tempObjperc * subobj.cumulativeperc / 100
            subtotal += obj.cumulativeperc

        return render(request, 'siteprogress/ajax-progresslogs.html',
                      {'progresslogs': projectitems, 'subtotal': subtotal})


@ajax_login_required
def ajax_get_uom_name(request):
    if request.method == "POST":
        progressdescription = request.POST.get('progressdescription')
        project_id = request.POST.get("proj_id")
        project = Project.objects.get(id=project_id)
        quotation = project.quotation

        if Scope.objects.filter(quotation_id=quotation.id, description=progressdescription).exists():
            uom = Scope.objects.filter(quotation_id=quotation.id, description=progressdescription)[0]
            data = {
                "status": "exist",
                "uom": uom.uom_id,
            }

            return JsonResponse(data)
        else:
            data = {
                "status": "no exist"
            }

            return JsonResponse(data)


@ajax_login_required
def ajax_plog_items(request):
    if request.method == "POST":
        project_id = request.POST.get('proj_id')
        project = Project.objects.get(id=project_id)
        quotation = project.quotation
        scopedescriptions=Scope.objects.filter(quotation_id=quotation.id, parent_id__isnull=True)
        uoms = Uom.objects.all()
        item_cnt = request.POST.get('item_cnt')
        return render(request, 'siteprogress/ajax-log-modal.html',
                      {'uoms': uoms, 'scopedescriptions': scopedescriptions, 'item_cnt': item_cnt})

@ajax_login_required
def ajax_planning_items(request):
    if request.method == "POST":
        project_id = request.POST.get('proj_id')
        project = Project.objects.get(id=project_id)
        quotation = project.quotation
        scopedescriptions=Scope.objects.filter(quotation_id=quotation.id, parent_id__isnull=True)
        uoms = Uom.objects.all()
        item_cnt = request.POST.get('item_cnt')
        return render(request, 'siteprogress/ajax-planning-modal.html',
                      {'uoms': uoms, 'scopedescriptions': scopedescriptions, 'item_cnt': item_cnt})


@ajax_login_required
def progressadd(request):
    if request.method == "POST":
        items = json.loads(request.POST.get('items'))
        for item in items:
            description = item.get('description')
            uom = item.get('uom')
            qty = item.get('qty')
            date = item.get('date')
            progressid = item.get('progressid')
            projectid = item.get('projectid')
            if progressid == "-1":
                try:
                    SiteProgress.objects.create(
                        description=description,
                        uom_id=uom,
                        qty=qty,
                        date=date,
                        updated_by=request.user.empid,
                        project_id=projectid
                    )
                except IntegrityError as e:
                    return JsonResponse({
                        "status": "Error",
                        "messages": "Already Site Progress is existed!"
                    })
            else:
                try:
                    siteprogress = SiteProgress.objects.get(id=progressid)
                    siteprogress.description = description
                    siteprogress.uom_id = uom
                    siteprogress.qty = qty
                    siteprogress.date = date
                    siteprogress.updated_by = request.user.empid
                    siteprogress.project_id = projectid
                    siteprogress.save()

                except IntegrityError as e:
                    return JsonResponse({
                        "status": "Error",
                        "messages": "Already Site Progress is existed!"
                    })

        return JsonResponse({
            "status": "Success",
            "messages": "Site Progress information added!"
        })

@ajax_login_required
def planningadd(request):
    if request.method == "POST":
        items = json.loads(request.POST.get('items'))
        for item in items:
            description = item.get('description')
            uom = item.get('uom')
            qty = item.get('qty')
            date = item.get('date')
            planningid = item.get('planningid')
            projectid = item.get('projectid')
            if planningid == "-1":
                try:
                    SiteProgressPlan.objects.create(
                        description=description,
                        uom_id=uom,
                        qty=qty,
                        date=date,
                        updated_by=request.user.empid,
                        project_id=projectid
                    )
                except IntegrityError as e:
                    return JsonResponse({
                        "status": "Error",
                        "messages": "Already Site Progress is existed!"
                    })
            else:
                try:
                    siteprogress = SiteProgressPlan.objects.get(id=planningid)
                    siteprogress.description = description
                    siteprogress.uom_id = uom
                    siteprogress.qty = qty
                    siteprogress.date = date
                    siteprogress.updated_by = request.user.empid
                    siteprogress.project_id = projectid
                    siteprogress.save()

                except IntegrityError as e:
                    return JsonResponse({
                        "status": "Error",
                        "messages": "Already Site Progress is existed!"
                    })

        return JsonResponse({
            "status": "Success",
            "messages": "Site Progress information added!"
        })


@ajax_login_required
def ajax_delete_progresslog(request):
    if request.method == "POST":
        pro_log_id = request.POST.get('pro_log_id')
        siteprogress = SiteProgress.objects.get(id=pro_log_id)
        siteprogress.delete()

        return JsonResponse({'status': 'ok'})
@ajax_login_required
def ajax_delete_planning(request):
    if request.method == "POST":
        plan_id = request.POST.get('plan_id')
        siteprogress_plan = SiteProgressPlan.objects.get(id=plan_id)
        siteprogress_plan.delete()

        return JsonResponse({'status': 'ok'})


@ajax_login_required
def ajax_get_progresslog(request):
    if request.method == "POST":
        proglogid = request.POST.get('proglogid')
        sp = SiteProgress.objects.get(id=proglogid)
        data = {
            'description': sp.description,
            'date': sp.date.strftime('%d %b, %Y'),
            'qty': sp.qty,
            'uom': sp.uom_id,
        }
        return JsonResponse(json.dumps(data), safe=False)
@ajax_login_required
def ajax_get_planning(request):
    if request.method == "POST":
        planningid = request.POST.get('planningid')
        sp = SiteProgressPlan.objects.get(id=planningid)
        data = {
            'description': sp.description,
            'date': sp.date.strftime('%d %b, %Y'),
            'qty': sp.qty,
            'uom': sp.uom_id,
        }
        return JsonResponse(json.dumps(data), safe=False)

@ajax_login_required
def ajax_submit_planning(request):
    if request.method == "POST":
        proj_id = request.POST.get('proj_id')
        plans = SiteProgressPlan.objects.filter(project_id=proj_id)
        for plan in plans:
            try:
                SiteProgress.objects.create(
                    description=plan.description,
                    uom=plan.uom,
                    qty=plan.qty,
                    date=plan.date,
                    updated_by=plan.updated_by,
                    project=plan.project
                )
                plan.delete()
            except IntegrityError as e:
                return JsonResponse({
                    "status": "Error",
                })
        return JsonResponse({'status': 'Success'})

@ajax_login_required
def ajax_repeat_planning(request):
    if request.method == "POST":
        proj_id = request.POST.get('proj_id')
        now_date = datetime.datetime.now(pytz.timezone(os.getenv("TIME_ZONE")))
        plans = SiteProgress.objects.filter(project_id=proj_id, date__gte=(now_date - datetime.timedelta(days=1)).date(),date__lt=now_date.date())
        if plans:
            for plan in plans:
                try:
                    SiteProgress.objects.create(
                        description=plan.description,
                        uom=plan.uom,
                        qty=plan.qty,
                        date=now_date.date(),
                        updated_by=plan.updated_by,
                        project=plan.project
                    )
                except IntegrityError as e:
                    return JsonResponse({
                        "status": "Error",
                    })
            SiteProgressRepeated.objects.create(
                project_id=proj_id,
                date=now_date.date(),
            )
            return JsonResponse({'status': 'Success'})
        else:
            return JsonResponse({'status': 'no data'})

@ajax_login_required
def ajax_is_repeated(request):
    if request.method == "POST":
        proj_id = request.POST.get('proj_id')
        now_date = datetime.datetime.now(pytz.timezone(os.getenv("TIME_ZONE")))
        plans = SiteProgressRepeated.objects.filter(project_id=proj_id, date__gte=now_date.date())
        if plans:
            return JsonResponse({'is_repeated': 'True'})
        else:
            return JsonResponse({'is_repeated': 'False'})

def check_plans():
    plans = SiteProgressPlan.objects.all()
    plans.delete()
