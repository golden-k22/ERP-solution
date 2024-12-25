import base64
import datetime
from functools import partial

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views.generic.list import ListView
import pytz
from django.views import generic
from maintenance.models import Device, MainSRSignature, MainSr, MainSrItem, Maintenance, MaintenanceFile, Schedule
from accounts.models import Uom, User, NotificationPrivilege, UserStatus
from maintenance.resources import MainSrItemResource, MaintenanceResource
from project.models import Sr
from sales.decorater import ajax_login_required
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.db import IntegrityError
import json
from django.views.generic.detail import DetailView
from django.db.models import Q
from dateutil import parser as date_parser
import pandas as pd
import os
from sales.models import Company, Contact, Quotation, Scope

from reportlab.platypus import SimpleDocTemplate, Table, Image, Spacer, TableStyle, PageBreak, Paragraph
from reportlab.pdfgen import canvas
from reportlab.rl_config import defaultPageSize
from reportlab.lib.utils import ImageReader
from reportlab.lib import colors
from reportlab.lib.units import inch, cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from io import BytesIO
from reportlab.lib.pagesizes import A4, landscape, portrait
from notifications.signals import notify
from textwrap import wrap
from accounts.email import send_mail


# Create your views here.
@method_decorator(login_required, name='dispatch')
class MaintenanceView(ListView):
    model = Maintenance
    template_name = "maintenance/maintenance-list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['maintenances'] = Maintenance.objects.all()
        context['maintenance_nos'] = Maintenance.objects.all().order_by('main_no').values('main_no').distinct()
        context['in_charges'] = Maintenance.objects.all().order_by('main_no').values('proj_incharge').distinct()
        context['contacts'] = User.objects.all()
        return context



@ajax_login_required
def ajax_filter_maintenance(request):
    if request.method == "POST":
        search_maintenance_no = request.POST.get('search_maintenance_no')
        search_incharge = request.POST.get('search_incharge')
        daterange = request.POST.get('daterange')

        maintenance = Maintenance.objects.all()
        if daterange:
            startdate = datetime.datetime.strptime(daterange.split()[0], '%Y.%m.%d').replace(tzinfo=pytz.utc)
            enddate = datetime.datetime.strptime(daterange.split()[2], '%Y.%m.%d').replace(tzinfo=pytz.utc)

        if search_maintenance_no != "":
            maintenance = maintenance.filter(main_no__iexact=search_maintenance_no)
        if search_incharge != "":
            maintenance = maintenance.filter(proj_incharge=search_incharge)
        if daterange != "":
            maintenance = maintenance.filter(start_date__gte=startdate, start_date__lte=enddate)
        return render(request, 'maintenance/ajax-maintenance.html', {'maintenances': maintenance})

# def task():
#     sender = User.objects.filter(role="Managers").first()
#     is_email = NotificationPrivilege.objects.get(user_id=sender.id).is_email
#     now_date = datetime.datetime.now(pytz.timezone(os.getenv("TIME_ZONE"))).date()
#     maintenance_schedules = Schedule.objects.all()
#     for schedule in maintenance_schedules:
#         to_date = schedule.date
#         diff_days = (to_date - now_date).days
#         reminder_days = int(schedule.reminder)
#         if diff_days > 0:
#             if diff_days == reminder_days:
#                 # notification send
#                 description = '<a href="/maintenance-detail/'+str(schedule.maintenance_id)+'">Maintenance No : {0} -  You have scheduled a reminder for {1}, kindly follow up.</a>'.format(
#                     schedule.maintenance.main_no, schedule.description)
#                 for receiver in User.objects.all():
#                     if receiver.notificationprivilege.maintenance_reminded:
#                         notify.send(sender, recipient=receiver, verb='Message', level="success",
#                                     description=description)
#                         if is_email and receiver.email:
#                             send_mail(receiver.email, "Notification for Schedule end.", description)
#     maintenances = Maintenance.objects.all()
#     for maintenance in maintenances:
#         end_date = maintenance.end_date
#         diff_days = (end_date - now_date).days
#         setting_weeks=NotificationPrivilege.objects.get(user_id=sender.id).contract_end
#         if diff_days > 0:
#             if diff_days==setting_weeks*7:
#                 # notification send
#                 description = '<a href="/maintenance-detail/'+str(maintenance.id)+'">Maintenance No : {0} -  Contract is ending {1} weeks later, kindly inform to customer.</a>'.format(
#                     maintenance.main_no, setting_weeks)
#                 for receiver in User.objects.all():
#                     if receiver.notificationprivilege.maintenance_reminded:
#                         notify.send(sender, recipient=receiver, verb='Message', level="success",
#                                     description=description)
#                         if is_email and receiver.email:
#                             send_mail(receiver.email, "Notification for Contract end.", description)
#     devices = Device.objects.all()
#     for device in devices:
#         end_date = device.expiry_date
#         diff_days = (end_date - now_date).days
#         setting_weeks=NotificationPrivilege.objects.get(user_id=sender.id).hardware_end
#         if diff_days > 0:
#             if diff_days==setting_weeks*7:
#                 # notification send
#                 description = '<a href="/maintenance-detail/'+str(device.maintenance_id)+'">Maintenance No : {0} -{1} is expiry {2} weeks later, kindly inform to customer.</a>'.format(
#                     device.maintenance.main_no,device.hardware_code, setting_weeks)
#                 for receiver in User.objects.all():
#                     if receiver.notificationprivilege.maintenance_reminded:
#                         notify.send(sender, recipient=receiver, verb='Message', level="success",
#                                     description=description)
#                         if is_email and receiver.email:
#                             send_mail(receiver.email, "Notification for Hardware end.", description)

@ajax_login_required
def maintenanceadd(request):
    if request.method == "POST":
        main_no = request.POST.get('main_no')
        in_incharge = request.POST.get('in_incharge')
        end_date = request.POST.get('end_date')
        start_date = request.POST.get('start_date')
        customer = request.POST.get('customer')
        maintenanceid = request.POST.get('maintenanceid')
        if maintenanceid == "-1":
            try:
                Maintenance.objects.create(
                    main_no=main_no,
                    end_date=end_date,
                    in_incharge=in_incharge,
                    start_date=start_date,
                    contact_person_id=customer,
                )
                return JsonResponse({
                    "status": "Success",
                    "messages": "Company information added!"
                })
            except IntegrityError as e:
                return JsonResponse({
                    "status": "Error",
                    "messages": "Already this email is existed!"
                })
        else:
            try:
                mainte = Maintenance.objects.get(id=maintenanceid)
                mainte.main_no = main_no
                mainte.in_incharge = in_incharge
                mainte.end_date = end_date
                mainte.start_date = start_date
                mainte.contact_person_id = customer
                mainte.save()

                return JsonResponse({
                    "status": "Success",
                    "messages": "Maintenance information updated!"
                })

            except IntegrityError as e:
                return JsonResponse({
                    "status": "Error",
                    "messages": "Error is existed!"
                })


@ajax_login_required
def getMaintenanace(request):
    if request.method == "POST":
        maintenanceid = request.POST.get('maintenanceid')
        main = Maintenance.objects.get(id=maintenanceid)
        data = {
            'main_no': main.main_no,
            'start_date': main.start_date.strftime('%d %b, %Y'),
            'end_date': main.end_date.strftime('%d %b, %Y'),
            'contactperson': str(main.contact_person_id),
            'in_incharge': main.in_incharge
        }
        return JsonResponse(json.dumps(data), safe=False)


@ajax_login_required
def maintenancedelete(request):
    if request.method == "POST":
        maintenanceid = request.POST.get('maintenanceid')
        main = Maintenance.objects.get(id=maintenanceid)
        main.delete()

        return JsonResponse({'status': 'ok'})


@method_decorator(login_required, name='dispatch')
class MaintenanceDetailView(DetailView):
    model = Maintenance
    template_name = "maintenance/maintenance-detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        content_pk = self.kwargs.get('pk')
        summary = Maintenance.objects.get(id=content_pk)
        context['maintenance'] = summary
        context['maintenance_pk'] = content_pk
        context['contacts'] = Contact.objects.all()
        context['companies'] = Company.objects.all()
        context['uoms'] = Uom.objects.all()
        context['projects_incharge'] = User.objects.filter(
            Q(role__icontains='Managers') | Q(role__icontains='Engineers') | Q(is_staff=True))
        context['filelist'] = MaintenanceFile.objects.filter(maintenance_id=content_pk)
        context['srlist'] = MainSr.objects.filter(maintenance_id=content_pk)
        quotation = summary.quotation
        # maintenanceitems = Scope.objects.filter(quotation_id=quotation.id, parent=None)
        maintenanceitems = Scope.objects.filter(quotation_id=quotation.id)
        context['maintenanceitems'] = maintenanceitems
        context["devices"] = Device.objects.filter(maintenance_id=content_pk)
        context['suppliers'] = Company.objects.filter(associate="Supplier")
        context['schedules'] = Schedule.objects.filter(maintenance_id=content_pk)

        return context


@ajax_login_required
def UpdateMain(request):
    if request.method == "POST":

        company_nameid = request.POST.get('company_nameid')
        worksite_address = request.POST.get('worksite_address')
        contact_person = request.POST.get('contact_person')
        email = request.POST.get('email')
        tel = request.POST.get('tel')
        fax = request.POST.get('fax')
        proj_incharge = request.POST.get('proj_incharge')
        site_incharge = request.POST.get('site_incharge')
        site_tel = request.POST.get('site_tel')
        RE = request.POST.get('re')
        main_no = request.POST.get('main_no')
        note = request.POST.get('note')
        quot_no = request.POST.get('quot_no')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        main_status = request.POST.get('main_status')
        mainid = request.POST.get('mainid')

        try:
            main = Maintenance.objects.get(id=mainid)

            main.company_nameid_id = company_nameid
            main.worksite_address = worksite_address
            main.contact_person_id = contact_person
            main.email = email
            main.tel = tel
            main.fax = fax
            main.quot_no = quot_no
            main.main_no = main_no
            main.proj_incharge = proj_incharge
            main.site_incharge = site_incharge
            main.site_tel = site_tel
            main.start_date = start_date
            main.end_date = end_date
            main.main_status = main_status
            main.RE = RE
            main.save()

            return JsonResponse({
                "status": "Success",
                "messages": "Maintenance information updated!"
            })
        except IntegrityError as e:
            print(e)
            return JsonResponse({
                "status": "Error",
                "messages": "Error is existed!"
            })


@ajax_login_required
def ajax_add_main_file(request):
    if request.method == "POST":
        name = request.POST.get('filename')
        fileid = request.POST.get('fileid')
        maintenanceid = request.POST.get('maintenanceid')
        if fileid == "-1":
            try:
                MaintenanceFile.objects.create(
                    name=name,
                    document=request.FILES.get('document'),
                    uploaded_by_id=request.user.id,
                    maintenance_id=maintenanceid,
                    date=datetime.datetime.now().date()
                )
                return JsonResponse({
                    "status": "Success",
                    "messages": "Project File information added!"
                })
            except IntegrityError as e:
                return JsonResponse({
                    "status": "Error",
                    "messages": "Error is existed!"
                })


@ajax_login_required
def deleteMainFile(request):
    if request.method == "POST":
        filedel_id = request.POST.get('filedel_id')
        mainfile = MaintenanceFile.objects.get(id=filedel_id)
        mainfile.delete()

        return JsonResponse({'status': 'ok'})


@ajax_login_required
def ajax_check_main_srnumber(request):
    if request.method == "POST":
        if MainSr.objects.all().exists():
            mainsr = MainSr.objects.all().order_by('-sr_no')[0]
            data = {
                "status": "exist",
                "sr_no": mainsr.sr_no.replace('CSR', '').split()[0]
            }

            return JsonResponse(data)
        else:
            data = {
                "status": "no exist"
            }

            return JsonResponse(data)


@ajax_login_required
def mainsradd(request):
    if request.method == "POST":
        sr_no = request.POST.get('sr_no')
        date = request.POST.get('srdate')
        if date == "":
            date = None
        maintenanceid = request.POST.get('maintenanceid')
        srid = request.POST.get('srid')
        # if request.user.signature != "":
        #     status = "Signed"
        # else:
        #     status = "Open"
        if srid == "-1":
            if Sr.objects.filter(sr_no=sr_no).exists() or MainSr.objects.filter(sr_no=sr_no).exists():
                return JsonResponse({
                    "status": "Error",
                    "messages": "This id has been taken by others, please close current window and create again.",
                })
            try:
                maintenance=Maintenance.objects.get(id=maintenanceid)
                MainSr.objects.create(
                    sr_no=sr_no,
                    date=date,
                    status="Open",
                    # uploaded_by_id=request.user.id,
                    maintenance_id=maintenanceid,
                )
                return JsonResponse({
                    "status": "Success",
                    "messages": "Service Report information added!"
                })
            except IntegrityError as e:
                return JsonResponse({
                    "status": "Error",
                    "messages": "Already SR is existed!"
                })
        else:
            try:
                sr = MainSr.objects.get(id=srid)
                sr.sr_no = sr_no
                sr.date = date
                # sr.status = status
                # sr.uploaded_by_id=request.user.id
                sr.maintenance_id = maintenanceid
                sr.save()

                return JsonResponse({
                    "status": "Success",
                    "messages": "Service Report information updated!"
                })

            except IntegrityError as e:
                return JsonResponse({
                    "status": "Error",
                    "messages": "Already SR is existed!"
                })


@ajax_login_required
def mainsrdocadd(request):
    if request.method == "POST":
        maintenanceid = request.POST.get('maintenanceid')
        srdocid = request.POST.get('srdocid')
        try:
            mainsr = MainSr.objects.get(id=srdocid)
            mainsr.uploaded_by_id = request.user.id
            mainsr.maintenance_id = maintenanceid
            if request.FILES.get('document'):
                mainsr.document = request.FILES.get('document')
                if mainsr.status!="Signed":
                    # notification send
                    sender = User.objects.filter(role="Managers").first()
                    is_email = NotificationPrivilege.objects.get(user_id=sender.id).is_email

                    description = '<a href="/maintenance-detail/' + str(
                        mainsr.maintenance_id) + '/service-report-detail/'+str(mainsr.id)+'">Project Sr No : {0} Status updated from {1} to Signed</a>'.format(
                        mainsr.sr_no, mainsr.status)
                    user_status=UserStatus.objects.get(status='resigned')
                    for receiver in User.objects.exclude(status=user_status).filter(
                            Q(username=mainsr.maintenance.proj_incharge) | Q(role='Managers')).distinct():
                        if receiver.notificationprivilege.do_status:
                            notify.send(sender, recipient=receiver, verb='Message', level="success",
                                        description=description)
                            if is_email and receiver.email:
                                send_mail(receiver.email, "Notification for Sr Status : ", description)
                mainsr.status="Signed"
            mainsr.save()

            return JsonResponse({
                "status": "Success",
                "messages": "Sr Document uploaded!"
            })

        except IntegrityError as e:
            return JsonResponse({
                "status": "Error",
                "messages": "Error!"
            })


@ajax_login_required
def deleteMainSR(request):
    if request.method == "POST":
        srdel_id = request.POST.get('srdel_id')
        mainsrdata = MainSr.objects.get(id=srdel_id)
        mainsritems = MainSrItem.objects.filter(sr=srdel_id)
        mainsrsign = MainSRSignature.objects.filter(sr=srdel_id)

        mainsritems.delete()
        mainsrsign.delete()
        mainsrdata.delete()

        return JsonResponse({'status': 'ok'})


@method_decorator(login_required, name='dispatch')
class MainSrDetailView(DetailView):
    model = MainSr
    pk_url_kwarg = 'srpk'
    template_name = "maintenance/service-report-detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        main_pk = self.kwargs.get('pk')
        sr_pk = self.kwargs.get('srpk')
        summary = Maintenance.objects.get(id=main_pk)
        context['summary'] = summary
        context['maintenance_pk'] = main_pk
        context['service_pk'] = sr_pk
        service_report = MainSr.objects.get(id=sr_pk)
        context['contacts'] = Contact.objects.all()
        context['uoms'] = Uom.objects.all()
        context['service_report'] = service_report
        quotation = summary.quotation
        # sritems = Scope.objects.filter(quotation_id=quotation.id,parent=None)
        context['sritems'] = MainSrItem.objects.filter(maintenance_id=main_pk, sr_id=sr_pk)
        # context['sritems'] = sritems
        context['quotation'] = quotation

        if (MainSRSignature.objects.filter(maintenance_id=main_pk, sr_id=sr_pk).exists()):
            context['srsignature'] = MainSRSignature.objects.get(maintenance_id=main_pk, sr_id=sr_pk)
        else:
            context['srsignature'] = None
        context['projectitemall'] = Scope.objects.filter(quotation_id=quotation.id)
        if service_report.time_in is None:
            context['sr_time_in'] ="0000-00-00 00:00:00"
        else:
            context['sr_time_in']=service_report.time_in.strftime("%Y-%m-%d %H:%M:%S")
        if service_report.time_out is None:
            context['sr_time_out'] ="0000-00-00 00:00:00"
        else:
            context['sr_time_out']=service_report.time_out.strftime("%Y-%m-%d %H:%M:%S");
        return context


@ajax_login_required
def ajax_update_main_service_report(request):
    if request.method == "POST":
        srtype = request.POST.get('srtype')
        srpurpose = request.POST.get('srpurpose')
        srsystem = request.POST.get('srsystem')
        timein = request.POST.get('timein')
        timeout = request.POST.get('timeout')
        remark = request.POST.get('remark')
        servicepk = request.POST.get('servicepk')
        worksite = request.POST.get('worksite')

        srdata = MainSr.objects.get(id=servicepk)
        srdata.srtype = srtype
        srdata.srpurpose = srpurpose
        srdata.srsystem = srsystem

        if timein!="NaN-NaN-NaN aN:aN":
            srdata.time_in = date_parser.parse(timein).replace(tzinfo=pytz.utc)
        if timeout!="NaN-NaN-NaN aN:aN":
            srdata.time_out = date_parser.parse(timeout).replace(tzinfo=pytz.utc)
        maintenance=srdata.maintenance
        maintenance.worksite_address=worksite
        maintenance.save()
        srdata.remark = remark
        srdata.save()

        return JsonResponse({
            "status": "Success",
            "messages": "Service Report information updated!"
        })


@ajax_login_required
def mainsrItemAdd(request):
    if request.method == "POST":
        description = request.POST.get('description')
        qty = request.POST.get('qty')
        uom = request.POST.get('uom')
        sritemid = request.POST.get('sritemid')
        maintenanceid = request.POST.get('maintenanceid')
        srid = request.POST.get('srid')

        if sritemid == "-1":
            try:
                MainSrItem.objects.create(
                    description=description,
                    qty=qty,
                    uom_id=uom,
                    maintenance_id=maintenanceid,
                    sr_id=srid
                )
                return JsonResponse({
                    "status": "Success",
                    "messages": "Service Report Item information added!"
                })
            except IntegrityError as e:
                return JsonResponse({
                    "status": "Error",
                    "messages": "Already SR Item is existed!"
                })
        else:
            try:
                sritem = MainSrItem.objects.get(id=sritemid)
                sritem.description = description
                sritem.qty = qty
                sritem.uom_id = uom
                sritem.maintenance_id = maintenanceid
                sritem.sr_id = srid
                sritem.save()

                return JsonResponse({
                    "status": "Success",
                    "messages": "Service Report Item information updated!"
                })

            except IntegrityError as e:
                return JsonResponse({
                    "status": "Error",
                    "messages": "Already SR Item is existed!"
                })


@ajax_login_required
def getMainSrItem(request):
    if request.method == "POST":
        sritemid = request.POST.get('sritemid')
        sritem = MainSrItem.objects.get(id=sritemid)
        data = {
            'description': sritem.description,
            'qty': sritem.qty,
            'uom': sritem.uom_id,
        }
        return JsonResponse(json.dumps(data), safe=False)


@ajax_login_required
def deleteMainSRItem(request):
    if request.method == "POST":
        sritem_del_id = request.POST.get('del_id')
        sritem = MainSrItem.objects.get(id=sritem_del_id)
        sritem.delete()

        return JsonResponse({'status': 'ok'})


def ajax_export_main_sr_item(request, maintenanceid, srid):
    resource = MainSrItemResource()
    queryset = MainSrItem.objects.filter(maintenance_id=maintenanceid, sr_id=srid)
    dataset = resource.export(queryset)
    response = HttpResponse(dataset.csv, content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="project_maintenance_sr_items.csv"'
    return response


@method_decorator(login_required, name='dispatch')
class MainSrSignatureCreate(generic.CreateView):
    model = MainSRSignature
    fields = '__all__'
    template_name = "maintenance/service-signature.html"

    def post(self, request, *args, **kwargs):
        if request.method == 'POST':
            sign_name = request.POST.get("sign_name")
            sign_nric = request.POST.get("sign_nric")
            sign_date = request.POST.get("sign_date")
            MainSRSignature.objects.create(
                signature=request.POST.get('signature'),
                name=sign_name,
                nric=sign_nric,
                update_date=datetime.datetime.strptime(sign_date, '%d %b %Y'),
                sr_id=self.kwargs.get('srpk'),
                maintenance_id=self.kwargs.get('pk')
            )
            return HttpResponseRedirect(
                '/maintenance-detail/' + self.kwargs.get('pk') + '/service-report-detail/' + self.kwargs.get('srpk'))


@method_decorator(login_required, name='dispatch')
class MainSrSignatureUpdate(generic.UpdateView):
    model = MainSRSignature
    pk_url_kwarg = 'signpk'
    fields = '__all__'
    template_name = "maintenance/service-signature.html"

    def post(self, request, *args, **kwargs):
        if request.method == 'POST':
            sign_name = request.POST.get("sign_name")
            sign_nric = request.POST.get("sign_nric")
            sign_date = request.POST.get("sign_date")
            srSignature = MainSRSignature.objects.get(id=self.kwargs.get('signpk'))
            srSignature.signature = request.POST.get('signature')
            srSignature.name = sign_name
            srSignature.nric = sign_nric
            srSignature.update_date = datetime.datetime.strptime(sign_date.replace(',', ""), '%d %b %Y').date()
            srSignature.sr_id = self.kwargs.get('srpk')
            srSignature.maintenance_id = self.kwargs.get('pk')
            srSignature.save()

            return HttpResponseRedirect(
                '/maintenance-detail/' + self.kwargs.get('pk') + '/service-report-detail/' + self.kwargs.get('srpk'))


@ajax_login_required
def maindeviceadd(request):
    if request.method == "POST":
        hardware_code = request.POST.get('hardware_code')
        hardware_desc = request.POST.get('hardware_desc')
        serial_number = request.POST.get('serial_number')
        uom_id = request.POST.get('uom')
        expiry_date = request.POST.get('expiry_date')
        licensing_date = request.POST.get('licensing_date')
        if licensing_date:
            licensing = licensing_date
        else:
            licensing = None
        remark = request.POST.get('remark')
        stock_qty = request.POST.get('stock_qty')
        brand = request.POST.get('brand')
        supplier = request.POST.get('supplier')
        maintenanceid = request.POST.get('maintenanceid')
        deviceid = request.POST.get('deviceid')
        if deviceid == "-1":
            try:
                obj = Device(
                    hardware_code=hardware_code,
                    hardware_desc=hardware_desc,
                    serial_number=serial_number,
                    uom=Uom.objects.get(id=uom_id),
                    expiry_date=expiry_date,
                    licensing_date=licensing,
                    remark=remark,
                    qty=stock_qty,
                    brand=brand,
                    supplier_name=supplier,
                    maintenance_id=maintenanceid
                )
                obj.save()
                return JsonResponse({
                    "status": "Success",
                    "messages": "Device information added!"
                })
            except IntegrityError as e:
                return JsonResponse({
                    "status": "Error",
                    "messages": "Hardware code Already is existed!"
                })
        else:
            try:
                device = Device.objects.get(id=deviceid)
                device.hardware_code = hardware_code
                device.hardware_desc = hardware_desc
                device.serial_number = serial_number
                device.uom = Uom.objects.get(id=uom_id)
                device.supplier_name = supplier
                device.expiry_date = expiry_date
                device.licensing_date = licensing
                device.remark = remark
                device.qty = stock_qty
                device.brand = brand
                device.maintenance_id = maintenanceid

                device.save()

                return JsonResponse({
                    "status": "Success",
                    "messages": "Device information updated!"
                })

            except IntegrityError as e:
                return JsonResponse({
                    "status": "Error",
                    "messages": "Error is existed!"
                })


@ajax_login_required
def getDevice(request):
    if request.method == "POST":
        deviceid = request.POST.get('deviceid')
        device = Device.objects.get(id=deviceid)
        if device.licensing_date:
            data = {
                'hardware_code': device.hardware_code,
                'serial_number': device.serial_number,
                'hardware_desc': device.hardware_desc,
                'stock_qty': device.qty,
                'expiry_date': device.expiry_date.strftime('%d %b, %Y'),
                'licensing_date': device.licensing_date.strftime('%d %b, %Y'),
                'remark': device.remark,
                'uom': device.uom.id,
                'brand': device.brand,
                'supplier': device.supplier_name

            }
        else:
            data = {
                'hardware_code': device.hardware_code,
                'serial_number': device.serial_number,
                'hardware_desc': device.hardware_desc,
                'stock_qty': device.qty,
                'expiry_date': device.expiry_date.strftime('%d %b, %Y'),
                'licensing_date': '',
                'remark': device.remark,
                'uom': device.uom.id,
                'brand': device.brand,
                'supplier': device.supplier_name

            }
        return JsonResponse(json.dumps(data), safe=False)


@ajax_login_required
def devicedelete(request):
    if request.method == "POST":
        deviceid = request.POST.get('deviceid')
        device = Device.objects.get(id=deviceid)
        device.delete()

        return JsonResponse({'status': 'ok'})


@ajax_login_required
def scheduleadd(request):
    if request.method == "POST":
        description = request.POST.get('description')
        remark = request.POST.get('remark')
        reminder = request.POST.get('reminder')
        date = request.POST.get('date')
        if date == "":
            date = None
        maintenanceid = request.POST.get('maintenanceid')
        scheduleid = request.POST.get('scheduleid')
        if scheduleid == "-1":
            try:
                Schedule.objects.create(
                    description=description,
                    remark=remark,
                    reminder=reminder,
                    date=date,
                    maintenance_id=maintenanceid,
                )
                return JsonResponse({
                    "status": "Success",
                    "messages": "Schedule information added!"
                })
            except IntegrityError as e:
                return JsonResponse({
                    "status": "Error",
                    "messages": "Already Bom is existed!"
                })
        else:
            try:
                schedule = Schedule.objects.get(id=scheduleid)
                schedule.description = description
                schedule.reminder = reminder
                schedule.date = date
                schedule.remark = remark
                schedule.maintenance_id = maintenanceid
                schedule.save()

                return JsonResponse({
                    "status": "Success",
                    "messages": "Schedule information updated!"
                })

            except IntegrityError as e:
                return JsonResponse({
                    "status": "Error",
                    "messages": "Already Schedule is existed!"
                })


@ajax_login_required
def scheduledelete(request):
    if request.method == "POST":
        scheduleid = request.POST.get('scheduleid')
        schedule = Schedule.objects.get(id=scheduleid)
        schedule.delete()

        return JsonResponse({'status': 'ok'})


@ajax_login_required
def getSchedule(request):
    if request.method == "POST":
        scheduleid = request.POST.get('scheduleid')
        schedule = Schedule.objects.get(id=scheduleid)
        data = {
            'date': schedule.date.strftime('%d %b, %Y'),
            'description': schedule.description,
            'remark': schedule.remark,
            'reminder': schedule.reminder
        }

        return JsonResponse(json.dumps(data), safe=False)


def exportMainSrPDF(request, value):
    sr = MainSr.objects.get(id=value)
    maintenance = sr.maintenance
    quotation = maintenance.quotation
    sritems = MainSrItem.objects.filter(sr_id=value)

    domain = os.getenv("DOMAIN")
    logo = Image('http://' + domain + '/static/assets/images/printlogo.png', hAlign='LEFT')
    response = HttpResponse(content_type='application/pdf')
    # currentdate = datetime.date.today().strftime("%d-%m-%Y")
    pdfname = sr.sr_no + ".pdf"
    response['Content-Disposition'] = 'attachment; filename={}'.format(pdfname)
    story = []
    buff = BytesIO()
    doc = SimpleDocTemplate(buff, pagesize=portrait(A4), rightMargin=0.25 * inch, leftMargin=0.45 * inch,
                            topMargin=4.2 * inch, bottomMargin=0.25 * inch, title=pdfname)
    styleSheet = getSampleStyleSheet()
    data = [
        [Paragraph('''<para align=center><font size=10><b>S/N</b></font></para>'''),
         Paragraph('''<para align=center><font size=10><b>Description</b></font></para>'''),
         Paragraph('''<para align=center><font size=10><b>UOM</b></font></para>'''),
         Paragraph('''<para align=center><font size=10><b>QTY</b></font></para>''')],
    ]

    index = 1
    if sritems.exists():
        for sritem in sritems:
            temp_data = []
            description = '''
                <para align=left>
                    %s
                </para>
            ''' % (str(sritem.description))
            pdes = Paragraph(description, styleSheet["BodyText"])
            temp_data.append(str(index))
            temp_data.append(pdes)
            if sritem.uom is None:
                temp_data.append("")
                temp_data.append("")
            else:
                temp_data.append(str(sritem.uom))
                temp_data.append(str(sritem.qty))
            data.append(temp_data)
            index += 1

        exportD = Table(
            data,
            style=[
                ('BACKGROUND', (0, 0), (5, 0), "#5a9bd5"),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('VALIGN', (0, 0), (-1, -1), "TOP"),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (0, 0), (1, -1), 'CENTER'),
            ],
        )
    else:
        data.append(["No data available in table", "", "", ""])
        exportD = Table(
            data,
            style=[
                ('BACKGROUND', (0, 0), (-1, 0), "#5a9bd5"),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('SPAN', (0, 1), (-1, -1)),
            ],
        )
        exportD._argH[1] = 0.3 * inch
    exportD._argW[0] = 0.40 * inch
    exportD._argW[1] = 5.456 * inch
    exportD._argW[2] = 0.732 * inch
    exportD._argW[3] = 0.732 * inch
    story.append(exportD)
    story.append(Spacer(1, 10))
    if sr.remark:
        remarks = sr.remark
    else:
        remarks = ""
    ps = ParagraphStyle('remarks', fontSize=9, leading=15)
    remark_data=[[Paragraph('''<para><font size=10><b>Remarks: </b></font></para>'''),
                  Paragraph('''<para><font size=9>%s</font></para>'''% (str(remarks).replace('\n','<br />\n')), ps)]]
    remark_table = Table(
        remark_data,
        style=[
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ],
    )
    remark_table._argW[0] = 0.9 * inch
    remark_table._argW[1] = 6.5 * inch
    story.append(remark_table)
    if len(data) > 5:
        story.append(PageBreak())

    doc.build(story, canvasmaker=NumberedCanvas, onFirstPage=partial(header_sr, sr=sr, value=value, domain=domain), onLaterPages=partial(header_sr, sr=sr, value=value, domain=domain))

    response.write(buff.getvalue())
    buff.close()

    return response

# Header for SR
def header_sr(canvas, doc, sr, value, domain):
    RIGHT_X = 410
    CONTENT_PADDING=20
    LEFT_X_1 = 45
    LEFT_X_2 = 95
    LEFT_X_3 = 220
    LEFT_X_4 = 255
    LEFT_X_5 = 300
    TOP_MARGIN = 130
    LINE_SPACE = 15

    canvas.saveState()
    project = sr.maintenance
    quotation = project.quotation

    if quotation.company_nameid.address:
        address = quotation.company_nameid.address
    else:
        address = " "
    if quotation.company_nameid.unit:
        qunit = quotation.company_nameid.unit
    else:
        qunit = " "
    if quotation.company_nameid.country:
        country = quotation.company_nameid.country.name
    else:
        country = " "
    if quotation.company_nameid.postal_code != "":
        postalcode = quotation.company_nameid.postal_code
    else:
        postalcode = " "
    if sr.srpurpose:
        srpurpose = sr.srpurpose
    else:
        srpurpose = " "
    if sr.srsystem:
        srsystem = sr.srsystem
    else:
        srsystem = " "
    if sr.srtype:
        srtype = sr.srtype
    else:
        srtype = " "
    if sr.time_out:
        time_out = sr.time_out.strftime('%d/%m/%Y %H:%M')
    else:
        time_out = " "
    if sr.time_in:
        time_in = sr.time_in.strftime('%d/%m/%Y %H:%M')
    else:
        time_in = " "
    if sr.remark:
        srremark = sr.remark
    else:
        srremark = " "
    if project.worksite_address:
        worksite_address = project.worksite_address
    else:
        worksite_address = " "
    canvas.setFont("Helvetica-Bold", 16)
    canvas.drawString(RIGHT_X, canvas.PAGE_HEIGHT - TOP_MARGIN, "SERVICE REPORT")
    canvas.setFont("Helvetica-Bold", 10)
    canvas.drawString(RIGHT_X, canvas.PAGE_HEIGHT - TOP_MARGIN - LINE_SPACE, "SR No: ")
    canvas.drawString(RIGHT_X, canvas.PAGE_HEIGHT - TOP_MARGIN - 2 * LINE_SPACE, "Date: ")
    canvas.drawString(RIGHT_X, canvas.PAGE_HEIGHT - TOP_MARGIN - 3 * LINE_SPACE, "Maintenance No: ")
    canvas.drawString(RIGHT_X, canvas.PAGE_HEIGHT - TOP_MARGIN - 4 * LINE_SPACE, "Time In: ")
    canvas.drawString(RIGHT_X, canvas.PAGE_HEIGHT - TOP_MARGIN - 5 * LINE_SPACE, "Time Out: ")
    canvas.setFont("Helvetica", 10)
    canvas.drawString(RIGHT_X+4.2*CONTENT_PADDING, canvas.PAGE_HEIGHT - TOP_MARGIN - LINE_SPACE, "%s" % (sr.sr_no))
    canvas.drawString(RIGHT_X+4.2*CONTENT_PADDING, canvas.PAGE_HEIGHT - TOP_MARGIN - 2 * LINE_SPACE, "%s" % (sr.date.strftime('%d/%m/%Y')))
    canvas.drawString(RIGHT_X+4.2*CONTENT_PADDING, canvas.PAGE_HEIGHT - TOP_MARGIN - 3 * LINE_SPACE, "%s" % (project.main_no))
    canvas.drawString(RIGHT_X+4.2*CONTENT_PADDING, canvas.PAGE_HEIGHT - TOP_MARGIN - 4 * LINE_SPACE, "%s" % (time_in))
    canvas.drawString(RIGHT_X+4.2*CONTENT_PADDING, canvas.PAGE_HEIGHT - TOP_MARGIN - 5 * LINE_SPACE, "%s" % (time_out))

    canvas.setFont("Helvetica-Bold", 10)
    canvas.drawString(LEFT_X_1, canvas.PAGE_HEIGHT - TOP_MARGIN + 2, "To: ")
    canvas.drawString(LEFT_X_1, canvas.PAGE_HEIGHT - TOP_MARGIN - 3 * LINE_SPACE, "Attn:")
    canvas.drawString(LEFT_X_3, canvas.PAGE_HEIGHT - TOP_MARGIN - 3 * LINE_SPACE, "Email:")
    canvas.drawString(LEFT_X_1, canvas.PAGE_HEIGHT - TOP_MARGIN - 4.8 * LINE_SPACE, "Tel:")
    canvas.drawString(LEFT_X_3, canvas.PAGE_HEIGHT - TOP_MARGIN - 4.8 * LINE_SPACE, "Fax:")
    canvas.drawString(LEFT_X_1, canvas.PAGE_HEIGHT - TOP_MARGIN - 6 * LINE_SPACE, "Worksite:")
    canvas.drawString(LEFT_X_1, canvas.PAGE_HEIGHT - TOP_MARGIN - 8 * LINE_SPACE, "Service Type:")
    canvas.drawString(LEFT_X_1, canvas.PAGE_HEIGHT - TOP_MARGIN - 9 * LINE_SPACE, "System:")
    canvas.drawString(LEFT_X_1, canvas.PAGE_HEIGHT - TOP_MARGIN - 10 * LINE_SPACE, "Purpose:")
    canvas.drawString(LEFT_X_1, canvas.PAGE_HEIGHT - TOP_MARGIN - 11 * LINE_SPACE, "Subject:")
    canvas.setFont("Helvetica", 10)
    canvas.drawString(LEFT_X_2, canvas.PAGE_HEIGHT - TOP_MARGIN + 2, "%s" % (quotation.company_nameid))
    canvas.drawString(LEFT_X_2, canvas.PAGE_HEIGHT - TOP_MARGIN - LINE_SPACE, "%s %s" % (address, qunit))
    canvas.drawString(LEFT_X_2, canvas.PAGE_HEIGHT - TOP_MARGIN - 2 * LINE_SPACE, "%s %s" % (country, postalcode))

    canvas.drawString(LEFT_X_2, canvas.PAGE_HEIGHT - TOP_MARGIN - 3 * LINE_SPACE, "%s" % (project.contact_person.salutation + " " + project.contact_person.contact_person))
    test_email = wrap(project.email, 25)
    t = canvas.beginText(LEFT_X_4, canvas.PAGE_HEIGHT - TOP_MARGIN - 3 * LINE_SPACE)
    t.textLines(test_email)
    canvas.drawText(t)
    canvas.drawString(LEFT_X_2, canvas.PAGE_HEIGHT - TOP_MARGIN - 4.8 * LINE_SPACE, "%s" % (project.tel))
    canvas.drawString(LEFT_X_4, canvas.PAGE_HEIGHT - TOP_MARGIN - 4.8 * LINE_SPACE, "%s" % (project.fax))
    canvas.drawString(LEFT_X_2, canvas.PAGE_HEIGHT - TOP_MARGIN - 6 * LINE_SPACE, "%s" % (worksite_address))
    canvas.drawString(LEFT_X_2+20, canvas.PAGE_HEIGHT - TOP_MARGIN - 8 * LINE_SPACE, "%s" % (srtype))
    canvas.drawString(LEFT_X_2, canvas.PAGE_HEIGHT - TOP_MARGIN - 9 * LINE_SPACE, "%s" % (srsystem))
    canvas.drawString(LEFT_X_2, canvas.PAGE_HEIGHT - TOP_MARGIN - 10 * LINE_SPACE, "%s" % (srpurpose))
    canvas.drawString(LEFT_X_2, canvas.PAGE_HEIGHT - TOP_MARGIN - 11 * LINE_SPACE, "%s" % (project.RE))

    # remarksobject = canvas.beginText(LEFT_X_2, canvas.PAGE_HEIGHT - TOP_MARGIN - 11 * LINE_SPACE)
    # for line in srremark.splitlines(False):
    #     remarksobject.textLine(line.rstrip())
    # canvas.drawText(remarksobject)

    srsignature = MainSRSignature.objects.filter(sr_id=value)
    if srsignature.exists():
        srsign_data = MainSRSignature.objects.get(sr_id=value)
        sign_name = srsign_data.name
        sign_nric = srsign_data.nric
        sign_date = srsign_data.update_date.strftime('%d/%m/%Y')
        sign_logo = ImageReader('http://' + domain + srsign_data.signature_image.url)
        sign_string = sign_name + "/" + sign_nric + "/" + sign_date
    else:
        sign_name = ""
        sign_nric = ""
        sign_date = ""
        sign_logo = ""
        sign_string = ""
    if sr.created_by:
        if sr.created_by.signature:
            auto_sign = ImageReader('http://' + domain + sr.created_by.signature.url)
        else:
            auto_sign = ""
    else:
        auto_sign = ""

    canvas.setFont("Helvetica", 9)
    canvas.drawString(LEFT_X_1, canvas.PAGE_HEIGHT - TOP_MARGIN - 35 * LINE_SPACE,
                      "%s" % ("Received the above Goods in Good Order & Condition."))

    canvas.setFont("Helvetica-Bold", 12)
    canvas.drawString(LEFT_X_1, canvas.PAGE_HEIGHT - TOP_MARGIN - 37 * LINE_SPACE, "%s" % (
        "For Customers:"))
    canvas.drawString(LEFT_X_5, canvas.PAGE_HEIGHT - TOP_MARGIN - 37 * LINE_SPACE,
                      "%s" % ("For CNI TECHNOLOGY PTE LTD:"))
    if sign_logo!="":
        canvas.drawImage(sign_logo, LEFT_X_1, canvas.PAGE_HEIGHT - TOP_MARGIN - 42 * LINE_SPACE, width=150/2, height=105/2, mask='auto')
    if auto_sign!="":
        canvas.drawImage(auto_sign, LEFT_X_5, canvas.PAGE_HEIGHT - TOP_MARGIN - 42 * LINE_SPACE, width=150/2, height=105/2, mask='auto')

    canvas.setFont("Helvetica", 9)
    canvas.drawString(LEFT_X_1, canvas.PAGE_HEIGHT - TOP_MARGIN - 43 * LINE_SPACE, "%s" % (sign_string))
    canvas.setFont("Helvetica-Bold", 10)
    canvas.drawString(LEFT_X_1, canvas.PAGE_HEIGHT - TOP_MARGIN - 44 * LINE_SPACE, "%s" % ("Name/Sign & Stamp/NRIC (last 4 digits)/Date"))
    canvas.drawString(LEFT_X_5, canvas.PAGE_HEIGHT - TOP_MARGIN - 44 * LINE_SPACE, "%s" % ("Authorised Signature"))

    canvas.restoreState()
class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []
        self.PAGE_HEIGHT = defaultPageSize[1]
        self.PAGE_WIDTH = defaultPageSize[0]        
        self.domain = os.getenv("DOMAIN")
        self.logo = ImageReader('http://' + self.domain + '/static/assets/images/printlogo.png')

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        """add page info to each page (page x of y)"""
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_number(self, page_count):
        self.drawImage(self.logo, 50, self.PAGE_HEIGHT - 100, width=70, height=70, mask='auto')
        self.setFont("Helvetica-Bold", 16)
        self.drawString(150, self.PAGE_HEIGHT - 50, "CNI TECHNOLOGY PTE LTD")
        self.setFont("Helvetica", 10)
        self.drawString(150, self.PAGE_HEIGHT - 65, "Block 3023 Ubi Road 3, #02-15 Ubi Plex 1, Singapore 408663")
        self.drawString(150, self.PAGE_HEIGHT - 80, "Tel.6747 6169 Fax.7647 5669")
        self.drawString(150, self.PAGE_HEIGHT - 95, "RCB No.201318779M")
        self.setFont("Times-Roman", 9)
        self.drawRightString(self.PAGE_WIDTH / 2.0 + 10, 0.35 * inch,
                             "Page %d of %d" % (self._pageNumber, page_count))


def ajax_export_maintenance(request):
    resource = MaintenanceResource()
    dataset = resource.export()
    response = HttpResponse(dataset.csv, content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="maintenance-summary.csv"'
    return response


def ajax_import_maintenance(request):
    if request.method == 'POST':
        org_column_names = ['main_no', 'customer', 'start_date', 'end_date', 'in_incharge', 'main_status']

        csv_file = request.FILES['file']
        contents = csv_file.read().decode('UTF-8')
        path = "temp.csv"
        f = open(path, 'w')
        f.write(contents)
        f.close()

        df = pd.read_csv(path)
        df.fillna("", inplace=True)
        column_names = list(df)

        if len(column_names) == 1:
            df = pd.read_csv(path, delimiter=';', decimal=',', encoding='utf-8')
            df.fillna("", inplace=True)
            column_names = list(df)

        dif_len = len(list(set(org_column_names) - set(column_names)))

        if dif_len == 0:
            record_count = len(df.index)
            success_record = 0
            failed_record = 0
            exist_record = 0
            for index, row in df.iterrows():
                exist_count = Maintenance.objects.filter(main_no=row["main_no"]).count()
                if exist_count == 0:
                    try:
                        maintenance = Maintenance(
                            main_no=row["main_no"],
                            customer=row["customer"],
                            start_date=datetime.datetime.strptime(row["start_date"], '%Y-%m-%d').replace(
                                tzinfo=pytz.utc),
                            end_date=datetime.datetime.strptime(row["end_date"], '%Y-%m-%d').replace(tzinfo=pytz.utc),
                            in_incharge=row["in_incharge"],
                            main_status=row["main_status"],
                        )
                        maintenance.save()
                        success_record += 1
                    except Exception as e:
                        print(e)
                        failed_record += 1
                else:
                    try:
                        maintenance = Maintenance.objects.filter(main_no=row["main_no"])[0]
                        maintenance.main_no = row["main_no"]
                        maintenance.customer = row["customer"]
                        maintenance.start_date = datetime.datetime.strptime(row["start_date"], '%Y-%m-%d').replace(
                            tzinfo=pytz.utc)
                        maintenance.end_date = datetime.datetime.strptime(row["end_date"], '%Y-%m-%d').replace(
                            tzinfo=pytz.utc)
                        maintenance.in_incharge = row["in_incharge"]
                        maintenance.main_status = row["main_status"]

                        maintenance.save()
                        exist_record += 1
                    except Exception as e:
                        print(e)
                        failed_record += 1
            os.remove(path)
            return JsonResponse({'status': 'true', 'error_code': '0', 'total': record_count, 'success': success_record,
                                 'failed': failed_record, 'exist': exist_record})
        else:
            os.remove(path)
            # column count is not equals
            return JsonResponse({'status': 'false', 'error_code': '1'})
    return HttpResponse("Ok")

@ajax_login_required
def getMainSrSign(request):
    if request.method == "POST":
        serviceid = request.POST.get('serviceid')
        srsignature = MainSRSignature.objects.get(id=serviceid)
        data = {
            'name': srsignature.name,
            'nric': srsignature.nric,
            'date': srsignature.update_date.strftime('%d %b, %Y'),
            'signature': srsignature.signature
        }
        return JsonResponse(json.dumps(data), safe=False)


@ajax_login_required
def addMainSrSign(request):
    if request.method == "POST":
        name = request.POST.get('name')
        nric = request.POST.get('nric')
        date = request.POST.get('date')
        signature = request.POST.get('signature')
        serviceid = request.POST.get('serviceid')
        maintenance_id = request.POST.get('maintenance_id')
        default_base64 = request.POST.get("default_base64")
        srid = request.POST.get('srid')

        format, imgstr = default_base64.split(';base64,')
        ext = format.split('/')[-1]
        signature_image = ContentFile(base64.b64decode(imgstr),
                                      name='service-sign-' + datetime.date.today().strftime("%Y-%m-%d") + "." + ext)
        if serviceid == "-1":
            try:
                MainSRSignature.objects.create(
                    name=name,
                    nric=nric,
                    update_date=date,
                    signature=signature,
                    sr_id=srid,
                    maintenance_id=maintenance_id,
                    signature_image=signature_image
                )

                sr=MainSr.objects.get(id=srid)
                if sr.status!="Signed":
                    # notification send
                    sender = User.objects.filter(role="Managers").first()
                    is_email = NotificationPrivilege.objects.get(user_id=sender.id).is_email

                    description = '<a href="/maintenance-detail/' + str(
                        sr.maintenance_id) + '/service-report-detail/'+str(sr.id)+'">Project Sr No : {0} Status updated from {1} to Signed</a>'.format(
                        sr.sr_no, sr.status)
                    user_status=UserStatus.objects.get(status='resigned')
                    for receiver in User.objects.exclude(status=user_status).filter(
                            Q(username=sr.maintenance.proj_incharge) | Q(role='Managers')).distinct():
                        if receiver.notificationprivilege.do_status:
                            notify.send(sender, recipient=receiver, verb='Message', level="success",
                                        description=description)
                            if is_email and receiver.email:
                                send_mail(receiver.email, "Notification for Sr Status : ", description)
                sr.status="Signed"
                sr.save()
                return JsonResponse({
                    "status": "Success",
                    "messages": "Service Signature information added!"
                })
            except IntegrityError as e:
                return JsonResponse({
                    "status": "Error",
                    "messages": "Error is existed!"
                })
        else:
            try:
                srsignature = MainSRSignature.objects.get(id=serviceid)
                srsignature.name = name
                srsignature.nric = nric
                srsignature.update_date = date
                srsignature.signature = signature
                srsignature.sr_id = srid
                srsignature.maintenance_id = maintenance_id
                srsignature.signature_image = signature_image
                srsignature.save()

                return JsonResponse({
                    "status": "Success",
                    "messages": "Service Signature information updated!"
                })

            except IntegrityError as e:
                return JsonResponse({
                    "status": "Error",
                    "messages": "Error is existed!"
                })
