import base64
import time
from functools import partial
from django.db.models.aggregates import Sum
from django.http.response import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic.list import ListView
from notifications.signals import notify

from maintenance.models import MainSr, MainSRSignature, Maintenance,Schedule
from project.models import DOSignature, DoItem, Pc, Project, OT, Do, Bom, BomLog, ProjectFile, \
    SRSignature, Sr, SrItem, Team, ActivitySchedule, ScheduleUsers, PcDetail, InvoiceFormat
from accounts.models import Uom, User, NotificationPrivilege, UserStatus
from sales.decorater import ajax_login_required
from django.db import IntegrityError
from django.db.utils import DataError
from django.http import JsonResponse
import json
from django.views.generic.detail import DetailView
from django.views import generic
from django.db.models import Q
import pytz
import decimal
import requests
from project.resources import BomResource, DoItemResource, ProjectResource, SrItemResource, TeamResource, \
    ProjectOtResource
from accounts.models import Holiday, WorkLog
import os
from sales.models import Company, Contact, Quotation, Scope, ProductSalesDo, SalesDOSignature, ProductSales, \
    ProductSalesDoItem, GST
from sales.views import add_default_project_files
from siteprogress.models import SiteProgress
from siteprogress.resources import SiteProgressResource
from toolbox.models import ToolBoxDescription, ToolBoxItem, ToolBoxObjective
from dateutil import parser as date_parser
import pandas as pd
from reportlab.platypus import SimpleDocTemplate, Table, Image, Spacer, TableStyle, PageBreak, Paragraph
from reportlab.pdfgen import canvas
from reportlab.rl_config import defaultPageSize
from reportlab.lib.utils import ImageReader
from reportlab.lib import colors
from reportlab.lib.units import inch, cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from io import BytesIO
from reportlab.lib.pagesizes import A4, landscape, portrait
from django.core.files.base import ContentFile
from datetime import datetime, time, date, timedelta
from textwrap import wrap
from accounts.email import send_mail
from project.whatsapp_msg import send_whatsapp_msg
import math


# Create your views here.

@method_decorator(login_required, name='dispatch')
class ProjectSummaryView(ListView):
    model = Project
    template_name = "projects/project-summary-list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['contacts'] = User.objects.all()
        context['customers'] = Project.objects.all().order_by('company_nameid').values('company_nameid').distinct()
        for customer in context['customers']:
            customer_id=customer['company_nameid']
            if Company.objects.filter(id=customer_id).exists():
                customer_name=Company.objects.get(id=customer_id).name
            else:
                customer_name=""
            customer['company_name']=customer_name
        context['proj_incharges'] = Project.objects.exclude(proj_incharge=None).order_by('proj_incharge').values(
            'proj_incharge').distinct()
        context['proj_nos'] = Project.objects.all().order_by('proj_id').values('proj_id').distinct()
        context['date_years'] = sorted(set(d.start_date.year for d in Project.objects.all()), reverse=True)
        context['proj_status']=Project.Status

        current_year = datetime.today().year
        if current_year in list(set([d.start_date.year for d in Project.objects.all()])):
            context['exist_current_year'] = True
        else:
            context['exist_current_year'] = False
        return context

def haversine(lat1, lon1, lat2, lon2):
    # Convert latitude and longitude from degrees to radians
    lat1 = math.radians(lat1)
    lon1 = math.radians(lon1)
    lat2 = math.radians(lat2)
    lon2 = math.radians(lon2)

    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    # Radius of Earth in kilometers
    R = 6371.0

    # Distance in kilometers
    distance = R * c
    return distance

def scheduleing_task():
    sql_query = """
        Select 
            tsu.id,
            tsu.user_id, 
            tsu.project_id, 
            tsu.shift, 
            tu.username, 
            tu.phone, 
            tp.proj_name 
        from tb_schedule_users as tsu
        LEFT JOIN 
            tb_user as tu ON tu.id=tsu.user_id
        LEFT JOIN 
            tb_project as tp ON tp.id = tsu.project_id
        WHERE 
            tsu.date=CURDATE()
    """
    users = ScheduleUsers.objects.raw(sql_query)
    for user in users:
        message=f"Hi, {user.username}. You have a schedule on the project : {user.proj_name} shift : {user.shift}."
        send_whatsapp_msg(user.phone, message)
        
        

def worklog_task():
    sender = User.objects.filter(role="Managers").first()
    is_email = NotificationPrivilege.objects.get(user_id=sender.id).is_email
    not_resigned_status=UserStatus.objects.get(status="resigned").id
    # Construct the SQL query with the retrieved status ID
    sql_query = """
        SELECT  
                tu.id,
                tu.username,
                tu.empid,
                tu.email,
                tw.latest_checkin_time,
                tw.checkout_time,
                tp.id as w_proj_id,
                tp.proj_name,
                tsu.project_id as s_proj_id,
                tsp.proj_name as s_proj_name,
                tp.latitude as p_latitude,
                tp.longitude as p_longitude,
                tw.checkout_lat as c_latitude,
                tw.checkout_lng as c_longitude,
                tot.approved_hour,
                CASE 
                    WHEN tw.projectcode IS NOT NULL THEN 1 
                    ELSE 0 
                END AS is_checkin_today,
                CASE 
                    WHEN tp.id =tsu.project_id THEN 1 
                    WHEN tsu.project_id IS Not NULL AND tp.id != tsu.project_id THEN 2 -- checkin Wrong project 
                    WHEN tsu.project_id IS Not NULL AND tw.latest_checkin_time is NULL THEN 3 -- Didn't checkin
                    ELSE 0 
                END AS is_correct
								
            FROM 
                tb_user AS tu
            LEFT JOIN 
                (
                    SELECT 
                        emp_no,
                        projectcode,
                        checkout_time,
                        MAX(checkin_time) AS latest_checkin_time,
                        checkout_lat,
                        checkout_lng
                    FROM 
                        tb_worklog
                            WHERE
                                DATE(checkin_time) = CURDATE()
                    GROUP BY 
                        emp_no
                ) AS tw ON tu.empid = tw.emp_no
            LEFT JOIN
                (
                    SELECT 
                        user_id,
                        project_id,
                        MAX(date) AS latest_date
                    FROM 
                        tb_schedule_users
                            WHERE
                                    DATE(date) = CURDATE()
                    GROUP BY 
                        user_id
                ) AS tsu ON tsu.user_id = tu.id
            LEFT JOIN 
                tb_project AS tp ON tw.projectcode = tp.proj_id
            LEFT JOIN 
                tb_project AS tsp ON tsu.project_id = tsp.id
            LEFT JOIN 
                tb_ot AS tot ON tot.proj_id = tp.proj_id and DATE(date)=CURDATE()
            WHERE
                (tu.status_id != {} OR tu.status_id IS NULL)
                AND tu.role IN ('Supervisors', 'Workers');
    """.format(not_resigned_status)
    users = User.objects.raw(sql_query)
    for user in users:
        worklog_checkin=NotificationPrivilege.objects.get(user_id=user.id).worklog_checkin
        if worklog_checkin==True:
            # notification send
            if user.is_correct==2:
                description = '<a href="/scheduling/">{0} : Checked in wrong project. {1} instead of {2}</a>'.format(
                    user.username, user.proj_name, user.s_proj_name)
                notify.send(sender, recipient=user, verb='Message', level="success",
                            description=description)
                if is_email and user.email:
                    send_mail(user.email, "Notification for Project Schedule Checkin: ", description)
            if user.is_correct==3:
                description = '<a href="/scheduling/">{0} : Please check in project - {1}.</a>'.format(
                    user.username, user.s_proj_name)
                notify.send(sender, recipient=user, verb='Message', level="success",
                            description=description)
                if is_email and user.email:
                    send_mail(user.email, "Notification for Project Schedule Checkin: ", description)
            
            if user.checkout_time:
                checkout_time = user.checkout_time.time()
                # Define 5:00 PM as a time object
                five_pm = time(17, 0)  # 17:00 is 5:00 PM in 24-hour format
                # Compare the current time with 5:00 PM
                if checkout_time > five_pm and user.approved_hour>0:
                    description = '<a href="/project-ot/">{0} : Checked out after 5:00 PM without approved OT for project - {1}.</a>'.format(
                        user.username, user.proj_name)
                    notify.send(sender, recipient=user, verb='Message', level="success",
                                description=description)
                    if is_email and user.email:
                        send_mail(user.email, "Notification for Project Schedule Checkin: ", description)
            if user.c_latitude:
                distance=haversine(float(user.p_latitude), float(user.p_longitude), float(user.c_latitude), float(user.c_longitude))
                if distance>0.5:
                    description = '<a href="/work-log/">{0} : Checked out more than 500m for project - {1}.</a>'.format(
                        user.username, user.proj_name)
                    notify.send(sender, recipient=user, verb='Message', level="success",
                                description=description)
                    if is_email and user.email:
                        send_mail(user.email, "Notification for Worklog Checkout distance: ", description)
            

def task():
    print("--------------- Project view task started. --------------")
    sender = User.objects.filter(role="Managers").first()
    reminder_signature = NotificationPrivilege.objects.get(user_id=sender.id).reminder_signature
    reminder_invoice = NotificationPrivilege.objects.get(user_id=sender.id).reminder_invoice
    is_email = NotificationPrivilege.objects.get(user_id=sender.id).is_email
    now_date = datetime.now(pytz.timezone(os.getenv("TIME_ZONE"))).date()

    # Notify before Project End Date
    projects=Project.objects.filter(end_date__gte=now_date)
    for project in projects:
        setting_weeks=NotificationPrivilege.objects.get(user_id=sender.id).project_end
        end_date=project.end_date
        diff_days=(end_date-now_date).days
        if diff_days==setting_weeks*7:
            # notification send
            description = '<a href="/project-summary-detail/'+str(project.id)+'">Project No {0} : will be ended in {1} weeks.</a>'.format(
                project.proj_id, setting_weeks)
            user_status=UserStatus.objects.get(status='resigned')
            for receiver in User.objects.exclude(status=user_status).filter(Q(username=project.proj_incharge) |Q(role='Managers')).distinct():
                if receiver.notificationprivilege.project_end:
                    notify.send(sender, recipient=receiver, verb='Message', level="success",
                                description=description)
                    if is_email and receiver.email:
                        send_mail(receiver.email, "Notification for Project End Data: ", description)

    proj_dos = Do.objects.all()
    for do in proj_dos:
        to_date = do.date
        diff_days = (now_date - to_date).days
        diff_mod = diff_days % reminder_signature
        project=do.project
        print("--------------- Project Do notification time. --------------", datetime.now(pytz.timezone(os.getenv("TIME_ZONE"))) )
        print(diff_days)
        diff_mod=0
        if diff_mod == 0:
            do_signature = DOSignature.objects.filter(do_id=do.id)
            if do.status=="Signed":
                pass
            else:
                # notification send
                description = '<a href="/project-summary-detail/'+str(do.project_id)+'/delivery-order-detail/'+str(do.id)+'">Project Do No : {0} - follow up with customer and get signature.</a>'.format(
                    do.do_no)
                user_status=UserStatus.objects.get(status='resigned')
                for receiver in User.objects.exclude(status=user_status).filter(Q(username=project.proj_incharge) |Q(role='Managers')).distinct():
                    if receiver.notificationprivilege.project_no_created:
                        notify.send(sender, recipient=receiver, verb='Message', level="success",
                                    description=description)
                        if is_email and receiver.email:
                            send_mail(receiver.email, "Notification for Project Do No", description)

        diff_mod_invoice = diff_days % reminder_invoice
        if diff_mod_invoice == 0:
            do_signature = DOSignature.objects.filter(do_id=do.id)
            if do_signature or do.document:
                # notification send
                if not do.invoice_no:
                    description = 'Project Do No : {0} - work order completed, please invoice.'.format(
                        do.do_no)
                    user_status=UserStatus.objects.get(status='resigned')
                    for receiver in User.objects.exclude(status=user_status).filter(role__in=['Managers', 'Admins']):
                        print("--------------- Send notification... --------------",receiver.email)
                        if receiver.notificationprivilege.project_no_created:
                            notify.send(sender, recipient=receiver, verb='Message', level="success",
                                        description=description)
                            if is_email and receiver.email:
                                send_mail(receiver.email, "Invoice Notification for Project Do No", description)

    proj_srs = Sr.objects.all()
    for sr in proj_srs:
        project=sr.project
        to_date = sr.date
        diff_days = (to_date - now_date).days
        diff_mod = diff_days % reminder_signature
        if diff_mod == 0:
            sr_signature = SRSignature.objects.filter(sr_id=sr.id)
            if sr.status=="Signed":
                pass
            else:
                # notification send
                description = '<a href="/project-detail/'+str(sr.project_id)+'/service-report-detail/'+str(sr.id)+'">Project Sr No : {0} - follow up with customer and get signature</a>'.format(
                    sr.sr_no)
                user_status=UserStatus.objects.get(status='resigned')
                for receiver in User.objects.exclude(status=user_status).filter(Q(username=project.proj_incharge) |Q(role='Managers')).distinct():
                    if receiver.notificationprivilege.project_no_created:
                        notify.send(sender, recipient=receiver, verb='Message', level="success",
                                    description=description)
                        if is_email and receiver.email:
                            send_mail(receiver.email, "Notification for Project Sr No", description)

        diff_mod_invoice = diff_days % reminder_invoice
        if diff_days>=0 & diff_mod_invoice == 0:
            sr_signature = SRSignature.objects.filter(sr_id=sr.id)
            if sr_signature or sr.document:
                # notification send
                if not sr.invoice_no:
                    description = 'Project Sr No : {0} - work order completed, please invoice.'.format(
                        sr.sr_no)
                    user_status=UserStatus.objects.get(status='resigned')
                    for receiver in User.objects.exclude(status=user_status).filter(role__in=['Managers', 'Admins']):
                        if receiver.notificationprivilege.project_no_created:
                            notify.send(sender, recipient=receiver, verb='Message', level="success",
                                        description=description)
                            if is_email and receiver.email:
                                send_mail(receiver.email, "Invoice Notification for Project Sr No", description)
    proj_pcs = Pc.objects.all()
    for pc in proj_pcs:
        project=pc.project
        to_date = pc.date
        diff_days = (now_date - to_date).days
        diff_mod = diff_days % reminder_signature
        if diff_mod == 0:
            if pc.status=="Signed":
                pass
            else:
                # notification send
                description = '<a href="/project-summary-detail/'+str(pc.project_id)+'">Project Pc No : {0} - follow up with customer and get signature</a>'.format(
                    pc.pc_no)
                user_status=UserStatus.objects.get(status='resigned')
                for receiver in User.objects.exclude(status=user_status).filter(Q(username=project.proj_incharge) |Q(role='Managers')).distinct():
                    if receiver.notificationprivilege.project_no_created:
                        notify.send(sender, recipient=receiver, verb='Message', level="success",
                                    description=description)
                        if is_email and receiver.email:
                            send_mail(receiver.email, "Notification for Project Pc No", description)

        diff_mod_invoice = diff_days % reminder_invoice
        if diff_mod_invoice == 0:
            if pc.document:
                # notification send
                if not pc.invoice_no:
                    description = 'Project Pc No : {0} - work order completed, please invoice.'.format(
                        pc.pc_no)
                    user_status=UserStatus.objects.get(status='resigned')
                    for receiver in User.objects.exclude(status=user_status).filter(role__in=['Managers', 'Admins']):
                        if receiver.notificationprivilege.project_no_created:
                            notify.send(sender, recipient=receiver, verb='Message', level="success",
                                        description=description)
                            if is_email and receiver.email:
                                send_mail(receiver.email, "Invoice Notification for Project Pc No", description)

    product_sales_dos = ProductSalesDo.objects.all()
    for psd in product_sales_dos:
        to_date = psd.date
        diff_days = (now_date - to_date).days
        diff_mod = diff_days % reminder_signature
        if diff_mod == 0:
            psd_signature = SalesDOSignature.objects.filter(do_id=psd.id)
            if psd.status=="Signed":
                pass
            else:
                # notification send
                description = '<a href="/sales-detail/'+str(psd.product_sales_id)+'/delivery-order-detail/'+str(psd.id)+'">Sales Do No : {0} - follow up with customer and get signature</a>'.format(
                    psd.do_no)
                user_status=UserStatus.objects.get(status='resigned')
                for receiver in User.objects.exclude(status=user_status).filter(role='Managers').distinct():
                    if receiver.notificationprivilege.project_no_created:
                        notify.send(sender, recipient=receiver, verb='Message', level="success",
                                    description=description)
                        if is_email and receiver.email:
                            send_mail(receiver.email, "Notification for Sales Do No", description)

        diff_mod_invoice = diff_days % reminder_invoice
        if diff_mod_invoice == 0:
            psd_signature = SalesDOSignature.objects.filter(do_id=psd.id)
            if psd_signature or psd.document:
                # notification send
                if not psd.invoice_no:
                    description = 'Sales Do No : {0} - work order completed, please invoice.'.format(
                        psd.do_no)
                    user_status=UserStatus.objects.get(status='resigned')
                    for receiver in User.objects.exclude(status=user_status).filter(role__in=['Managers', 'Admins']):
                        if receiver.notificationprivilege.project_no_created:
                            notify.send(sender, recipient=receiver, verb='Message', level="success",
                                        description=description)
                            if is_email and receiver.email:
                                send_mail(receiver.email, "Invoice Notification for Sales Do No", description)

    maintenance_srs = MainSr.objects.all()
    for sr in maintenance_srs:
        project=sr.maintenance
        to_date = sr.date
        diff_days = (to_date-now_date).days
        diff_mod = diff_days % reminder_signature
        if diff_mod == 0:
            sr_signature = MainSRSignature.objects.filter(sr_id=sr.id)
            if sr.status=="Signed":
                pass
            else:
                # notification send
                description = '<a href="/maintenance-detail/'+str(sr.maintenance_id)+'/service-report-detail/'+str(sr.id)+'">Maintenance Sr No : {0} - follow up with customer and get signature</a>'.format(
                    sr.sr_no)
                user_status=UserStatus.objects.get(status='resigned')
                for receiver in User.objects.exclude(status=user_status).filter(Q(username=project.proj_incharge) |Q(role='Managers')).distinct():
                    if receiver.notificationprivilege.project_no_created:
                        notify.send(sender, recipient=receiver, verb='Message', level="success",
                                    description=description)
                        if is_email and receiver.email:
                            send_mail(receiver.email, "Notification for Maintenance Sr No", description)

        diff_mod_invoice = diff_days % reminder_invoice
        if diff_days>=0 & diff_mod_invoice == 0:
            sr_signature = MainSRSignature.objects.filter(sr_id=sr.id)
            if sr_signature or sr.document:
                # notification send
                if not sr.invoice_no:
                    description = 'Maintenance Sr No : {0} - work order completed, please invoice.'.format(
                        sr.sr_no)
                    user_status=UserStatus.objects.get(status='resigned')
                    for receiver in User.objects.exclude(status=user_status).filter(role__in=['Managers', 'Admins']):
                        if receiver.notificationprivilege.project_no_created:
                            notify.send(sender, recipient=receiver, verb='Message', level="success",
                                        description=description)
                            if is_email and receiver.email:
                                send_mail(receiver.email, "Invoice Notification for Maintenance Sr No", description)

    maintenance_schedules = Schedule.objects.all()
    for schedule in maintenance_schedules:
        to_date = schedule.date
        diff_days = (to_date - now_date).days
        reminder_days = int(schedule.reminder)
        if diff_days > 0:
            if diff_days == reminder_days:
                # notification send
                description = '<a href="/maintenance-detail/' + str(
                    schedule.maintenance_id) + '">Maintenance No : {0} -  You have scheduled a reminder for {1}, kindly follow up.</a>'.format(
                    schedule.maintenance.main_no, schedule.description)
                user_status=UserStatus.objects.get(status='resigned')
                for receiver in User.objects.exclude(status=user_status).all():
                    if receiver.notificationprivilege.maintenance_reminded:
                        notify.send(sender, recipient=receiver, verb='Message', level="success",
                                    description=description)
                        if is_email and receiver.email:
                            send_mail(receiver.email, "Notification for Schedule end.", description)
    maintenances = Maintenance.objects.all()
    for maintenance in maintenances:
        end_date = maintenance.end_date
        diff_days = (end_date - now_date).days
        setting_weeks = NotificationPrivilege.objects.get(user_id=sender.id).contract_end
        if diff_days > 0:
            if diff_days == setting_weeks * 7:
                # notification send
                description = '<a href="/maintenance-detail/' + str(
                    maintenance.id) + '">Maintenance No : {0} -  Contract is ending {1} weeks later, kindly inform to customer.</a>'.format(
                    maintenance.main_no, setting_weeks)
                user_status=UserStatus.objects.get(status='resigned')
                for receiver in User.objects.exclude(status=user_status).all():
                    if receiver.notificationprivilege.maintenance_reminded:
                        notify.send(sender, recipient=receiver, verb='Message', level="success",
                                    description=description)
                        if is_email and receiver.email:
                            send_mail(receiver.email, "Notification for Contract end.", description)
    devices = Device.objects.all()
    for device in devices:
        end_date = device.expiry_date
        diff_days = (end_date - now_date).days
        setting_weeks = NotificationPrivilege.objects.get(user_id=sender.id).hardware_end
        if diff_days > 0:
            if diff_days == setting_weeks * 7:
                # notification send
                description = '<a href="/maintenance-detail/' + str(
                    device.maintenance_id) + '">Maintenance No : {0} -{1} is expiry {2} weeks later, kindly inform to customer.</a>'.format(
                    device.maintenance.main_no, device.hardware_code, setting_weeks)
                user_status=UserStatus.objects.get(status='resigned')
                for receiver in User.objects.exclude(status=user_status).all():
                    if receiver.notificationprivilege.maintenance_reminded:
                        notify.send(sender, recipient=receiver, verb='Message', level="success",
                                    description=description)
                        if is_email and receiver.email:
                            send_mail(receiver.email, "Notification for Hardware end.", description)


def ajax_export_project(request):
    resource = ProjectResource()
    dataset = resource.export()
    response = HttpResponse(dataset.csv, content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="project-summary.csv"'
    return response


def ajax_export_projectot(request):
    resource = ProjectOtResource()
    dataset = resource.export()
    response = HttpResponse(dataset.csv, content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="project-ot.csv"'
    return response


def ajax_import_project(request):
    if request.method == 'POST':
        org_column_names = ['proj_id', 'company_nameid', 'proj_name', 'start_date', 'end_date', 'proj_incharge',
                            'proj_status']

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
                exist_count = Project.objects.filter(proj_id=row["proj_id"]).count()
                if exist_count == 0:
                    try:
                        project = Project(
                            proj_id=row["proj_id"],
                            company_nameid=row["company_nameid"],
                            proj_name=row["proj_name"],
                            start_date=datetime.strptime(row["start_date"], '%Y-%m-%d').replace(
                                tzinfo=pytz.utc),
                            end_date=datetime.strptime(row["end_date"], '%Y-%m-%d').replace(tzinfo=pytz.utc),
                            proj_incharge=row["proj_incharge"],
                            proj_status=row["proj_status"],
                        )
                        project.save()
                        success_record += 1
                    except Exception as e:
                        print(e)
                        failed_record += 1
                else:
                    try:
                        project = Project.objects.filter(proj_id=row["proj_id"])[0]
                        project.proj_id = row["proj_id"]
                        project.company_nameid = row["company_nameid"]
                        project.proj_name = row["proj_name"]
                        project.start_date = datetime.strptime(row["start_date"], '%Y-%m-%d').replace(
                            tzinfo=pytz.utc)
                        project.end_date = datetime.strptime(row["end_date"], '%Y-%m-%d').replace(
                            tzinfo=pytz.utc)
                        project.proj_incharge = row["proj_incharge"]
                        project.proj_status = row["proj_status"]

                        project.save()
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


def ajax_import_projectot(request):
    if request.method == 'POST':
        org_column_names = ['proj_id', 'date', 'approved_hour', 'approved_by', 'proj_name']

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
                exist_count = OT.objects.filter(proj_id=row["proj_id"]).count()
                if exist_count == 0:
                    try:
                        projectot = OT(
                            proj_id=row["proj_id"],
                            approved_hour=row["approved_hour"],
                            proj_name=row["proj_name"],
                            date=datetime.strptime(row["date"], '%Y-%m-%d %H:%M:%S').replace(tzinfo=pytz.utc),
                            approved_by=row["approved_by"]
                        )
                        projectot.save()
                        success_record += 1
                    except Exception as e:
                        print(e)
                        failed_record += 1
                else:
                    try:
                        projectot = OT.objects.filter(proj_id=row["proj_id"])[0]
                        projectot.proj_id = row["proj_id"]
                        projectot.approved_hour = row["approved_hour"]
                        projectot.proj_name = row["proj_name"]
                        projectot.start_date = datetime.strptime(row["date"], '%Y-%m-%d %H:%M:%S').replace(
                            tzinfo=pytz.utc)
                        projectot.approved_by = row["approved_by"]

                        projectot.save()
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
def ajax_summarys(request):
    if request.method == "POST":
        current_year = datetime.today().year
        projects = Project.objects.filter(start_date__iso_year=current_year)

        return render(request, 'projects/ajax-project.html', {'projects': projects})


@ajax_login_required
def ajax_summarys_filter(request):
    if request.method == "POST":
        search_projectno = request.POST.get('search_projectno')
        incharge_filter = request.POST.get('incharge_filter')
        search_customer = request.POST.get('search_customer')
        search_years = json.loads(request.POST.get('search_years', '[]'))
        status = request.POST.get('status')
        projects = Project.objects.all()

        projects = projects.filter(start_date__iso_year__in = search_years)
        if search_projectno != "":
            projects = projects.filter(proj_id__iexact=search_projectno)
        if search_customer != "":
            projects = projects.filter(company_nameid_id=search_customer)
        if incharge_filter != "":
            projects = projects.filter(proj_incharge__iexact=incharge_filter)
        if status != "":
            projects = projects.filter(proj_status=status)

        return render(request, 'projects/ajax-project.html', {'projects': projects})


@ajax_login_required
def summaryadd(request):
    if request.method == "POST":
        proj_no = request.POST.get('proj_no')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        customer = request.POST.get('customer')
        project = request.POST.get('project')

        summaryid = request.POST.get('summaryid')
        if summaryid == "-1":
            try:
                newproject=Project.objects.create(
                    proj_id=proj_no,
                    start_date=start_date,
                    end_date=end_date,
                    company_nameid=customer,
                    proj_name=project
                )

                add_default_project_files(newproject.id)
                return JsonResponse({
                    "status": "Success",
                    "messages": "Summary information added!"
                })
            except IntegrityError as e:
                return JsonResponse({
                    "status": "Error",
                    "messages": "Already Project is existed!"
                })
        else:
            try:
                summary = Project.objects.get(id=summaryid)
                summary.proj_id = proj_no
                summary.start_date = start_date
                summary.end_date = end_date
                summary.company_nameid = customer
                summary.proj_name = project
                summary.save()

                return JsonResponse({
                    "status": "Success",
                    "messages": "Summary information updated!"
                })

            except IntegrityError as e:
                return JsonResponse({
                    "status": "Error",
                    "messages": "Already Project is existed!"
                })


@method_decorator(login_required, name='dispatch')
class ProjectOTView(ListView):
    model = OT
    template_name = "projects/projectOT-list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['projectots'] = OT.objects.all()
        context['approved_users'] = User.objects.filter(
            Q(role__icontains='Managers') | Q(role__icontains='Engineers') | Q(is_staff=True))
        context['approveds'] = self.request.user.username

        context['projectot_nos'] = OT.objects.exclude(proj_id=None).order_by('proj_id').values('proj_id').distinct()
        context['proj_nos'] = Project.objects.filter(proj_status="On-going").order_by('proj_id').values(
            'proj_id').distinct()
        return context


@method_decorator(login_required, name='dispatch')
class approvedOTView(ListView):
    model = OT
    template_name = "projects/approved-ot.html"


@ajax_login_required
def ajax_get_projectname(request):
    if request.method == "POST":
        proj_id = request.POST.get('proj_id')
        if Project.objects.filter(proj_id__iexact=proj_id).exists():
            project = Project.objects.get(proj_id__iexact=proj_id)
            data = {
                "status": "exist",
                "project_name": project.proj_name
            }

            return JsonResponse(data)
        else:
            data = {
                "status": "not exist",
            }
            return JsonResponse(data)


# @ajax_login_required
# def check_ot_number(request):
#     if request.method == "POST":
#         if OT.objects.all().exists():
#             ot= OT.objects.all().order_by('-ot_id')[0]
#             data = {
#                 "status": "exist",
#                 "ot_id": ot.ot_id
#             }

#             return JsonResponse(data)
#         else:
#             data = {
#                 "status": "no exist"
#             }

#             return JsonResponse(data)

@ajax_login_required
def ajax_projectots(request):
    if request.method == "POST":
        current_year = datetime.today().year
        current_month = datetime.today().month
        projectots = OT.objects.filter(date__year=current_year, date__month=current_month)

        return render(request, 'projects/ajax-projectot.html', {'projectots': projectots})


@ajax_login_required
def ajax_projectots_filter(request):
    if request.method == "POST":
        search_projectno = request.POST.get('search_projectno')
        daterange = request.POST.get('daterange')
        if daterange:
            startdate = datetime.strptime(daterange.split()[0], '%Y.%m.%d').replace(tzinfo=pytz.utc)
            enddate = datetime.strptime(daterange.split()[2], '%Y.%m.%d').replace(tzinfo=pytz.utc)
        search_approved = request.POST.get('search_approved')
        if search_projectno != "" and daterange == "" and search_approved == "":
            projectots = OT.objects.filter(proj_id__iexact=search_projectno)

        elif search_projectno != "" and daterange != "" and search_approved == "":
            projectots = OT.objects.filter(proj_id__iexact=search_projectno, date__gte=startdate, date__lte=enddate)

        elif search_projectno != "" and daterange != "" and search_approved != "":
            projectots = OT.objects.filter(proj_id__iexact=search_projectno, date__gte=startdate, date__lte=enddate,
                                           approved_by__iexact=search_approved)

        elif search_projectno == "" and daterange != "" and search_approved == "":
            projectots = OT.objects.filter(date__gte=startdate, date__lte=enddate)

        elif search_projectno == "" and daterange != "" and search_approved != "":
            projectots = OT.objects.filter(date__gte=startdate, date__lte=enddate, approved_by__iexact=search_approved)

        elif search_projectno == "" and daterange == "" and search_approved != "":
            projectots = OT.objects.filter(approved_by__iexact=search_approved)

        elif search_projectno != "" and daterange == "" and search_approved != "":
            projectots = OT.objects.filter(proj_id__iexact=search_projectno, approved_by__iexact=search_approved)

        return render(request, 'projects/ajax-projectot.html', {'projectots': projectots})


@ajax_login_required
def getProjectSummary(request):
    if request.method == "POST":
        summaryid = request.POST.get('summaryid')
        summary = Project.objects.get(id=summaryid)
        if summary.end_date:
            data = {
                'proj_id': summary.proj_id,
                'start_date': summary.start_date.strftime('%d %b, %Y'),
                'end_date': summary.end_date.strftime('%d %b, %Y'),
                'customer': str(summary.company_nameid),
                'proj_name': summary.proj_name
            }
        else:
            data = {
                'proj_id': summary.proj_id,
                'start_date': summary.start_date.strftime('%d %b, %Y'),
                'end_date': "",
                'customer': str(summary.company_nameid),
                'proj_name': summary.proj_name
            }
        return JsonResponse(json.dumps(data), safe=False)


@method_decorator(login_required, name='dispatch')
class ProjectDetailView(DetailView):
    model = Project
    template_name = "projects/project-detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        content_pk = self.kwargs.get('pk')
        summary = Project.objects.get(id=content_pk)
        context['companies'] = Company.objects.all()
        context['summary'] = summary
        context['project_pk'] = content_pk
        context['contacts'] = Contact.objects.all()
        context['contact_users'] = User.objects.filter(
            (Q(role__icontains='Supervisors') | Q(role__icontains='Workers')) & ~Q(status_id=2))
        context['uoms'] = Uom.objects.all()
        context['projects_incharge'] = User.objects.filter(
            (Q(role__icontains='Managers') | Q(role__icontains='Engineers') | Q(is_staff=True)) & ~Q(status_id=2))
        context['dolist'] = Do.objects.filter(project_id=content_pk)
        context['filelist'] = ProjectFile.objects.filter(project_id=content_pk)
        context['bomlist'] = Bom.objects.filter(project_id=content_pk)
        context['teamlist'] = Team.objects.filter(project_id=content_pk)
        context['srlist'] = Sr.objects.filter(project_id=content_pk)
        context['pclist'] = Pc.objects.filter(project_id=content_pk)
        context['total_claim_sum'] = Pc.objects.filter(project_id=content_pk).aggregate(Sum('amount'))['amount__sum']
        if PcDetail.objects.filter(project_id=content_pk).exists():
            context['pc_detail'] = PcDetail.objects.get(project_id=content_pk)
        quotation = summary.quotation
        projectitems = Scope.objects.filter(quotation_id=quotation.id,subject__is_optional=None)


        if Scope.objects.filter(quotation_id=quotation.id, subject__is_optional=None).exists():
            subtotal = Scope.objects.filter(quotation_id=quotation.id, subject__is_optional=None).aggregate(Sum('amount'))[
                'amount__sum']
            total_gp = 0.0
            total_cost = 0.0
            for scope in projectitems:
                total_gp += float(scope.gp)
                total_cost += float(scope.cost)
                if subtotal == 0:
                    scope.allocation_perc = 0
                else:
                    scope.allocation_perc = 100 * scope.amount / subtotal
                scope.save()
            gst_default=GST.objects.last()
            if gst_default:
                gst_default=float(gst_default.gst)
            else:
                gst_default=0.09
            context['gst_default'] = gst_default*100
            gst = (float(subtotal) - float(quotation.discount)) * gst_default
            context['subtotal'] = subtotal
            context['gst'] = gst
            final_total = float(subtotal) - float(quotation.discount) + gst
            context['final_total'] = final_total
            quotation.total = subtotal
            quotation.gst = gst
            quotation.finaltotal = final_total
            if total_cost == 0:
                margin = 0
            else:
                margin = (float(quotation.total) - total_cost - float(quotation.discount)) * 100 / (
                        float(quotation.total) - float(quotation.discount))
            quotation.totalgp = total_gp
            quotation.margin = margin
            # quotation.save()

        # subtotal = 0
        # for obj in projectitems:
        #     obj.childs = Scope.objects.filter(quotation_id=quotation.id, parent_id=obj.id)
        #     obj.cumulativeqty = \
        #         SiteProgress.objects.filter(project_id=content_pk, description__iexact=obj.description).aggregate(
        #             Sum('qty'))['qty__sum']
        #
        #     obj.cumulativeperc = 0
        #     if obj.childs.count() != 0:
        #         tempObjperc = float(obj.allocation_perc) / obj.childs.count()
        #     for subobj in obj.childs:
        #         subobj.cumulativeqty = \
        #             SiteProgress.objects.filter(project_id=content_pk,
        #                                         description__iexact=subobj.description).aggregate(
        #                 Sum('qty'))['qty__sum']
        #
        #         if subobj.allocation_perc and subobj.cumulativeqty:
        #             subobj.cumulativeperc = float(subobj.cumulativeqty / subobj.qty) * float(subobj.allocation_perc)
        #         else:
        #             subobj.cumulativeperc = 0
        #         obj.cumulativeperc += tempObjperc * subobj.cumulativeperc / 100
        #
        #     subtotal += obj.cumulativeperc


        context['projectitems'] = projectitems
        context['projectitemall'] = Scope.objects.filter(quotation_id=quotation.id)
        context['quotation_pk'] = quotation.id
        site_progress = SiteProgress.objects.filter(project_id=content_pk)
        context['site_progress'] = site_progress
        projectitemactivitys = Scope.objects.filter(quotation_id=quotation.id)
        context['projectitemactivitys'] = projectitemactivitys
        context['toolboxitems'] = ToolBoxItem.objects.filter(project_id=content_pk, manager="Engineer")
        context['tbm_objectives'] = ToolBoxObjective.objects.all()
        context['tbm_descriptions'] = ToolBoxDescription.objects.all()
        return context


@ajax_login_required
def ajax_filter_description(request):
    if request.method == "POST":
        toolbox_objective = request.POST.get('toolbox_objective')
        descriptions = ToolBoxDescription.objects.filter(objective_id=toolbox_objective)
        return render(request, 'projects/ajax-tbm-description.html', {'descriptions': descriptions})


@ajax_login_required
def ajax_add_proj_file(request):
    if request.method == "POST":
        name = request.POST.get('filename')
        fileid = request.POST.get('fileid')
        projectid = request.POST.get('projectid')
        if fileid == "-1":
            try:
                ProjectFile.objects.create(
                    name=name,
                    document=request.FILES.get('document'),
                    uploaded_by_id=request.user.id,
                    project_id=projectid,
                    date=datetime.now().date()
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
        else:
            try:
                projectfile=ProjectFile.objects.get(id=fileid)
                projectfile.name=name
                projectfile.document=request.FILES.get('document')
                projectfile.uploaded_by_id=request.user.id
                projectfile.date=datetime.now().date()
                projectfile.save()
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
def ajax_all_mandays(request):
    if request.method == "POST":
        proj_id = request.POST.get('proj_id')
        current_year = datetime.today().year
        current_month = datetime.today().month
        holiday_cnt = Holiday.objects.filter(date__year=current_year, date__month=current_month).count()

        str_query = "SELECT F.id, F.projectcode,  F.emp_no, F.estimated_mandays, F.start_date, F.end_date, F.projectcode, F.checkin_time, F.checkout_time, TIMESTAMPDIFF(MINUTE, F.checkin_time, F.checkout_time) as `difference` FROM (SELECT W.id, W.projectcode, W.emp_no, P.estimated_mandays, P.start_date, P.end_date, W.checkin_time, W.checkout_time FROM tb_worklog AS W, tb_project as P WHERE W.projectcode = P.proj_id) AS F WHERE F.projectcode = " + "'" + proj_id + "'" + " ORDER BY Date(F.checkin_time), F.emp_no"

        query_ots = WorkLog.objects.raw(str_query)
        total_1hr = 0
        total_2hr = 0
        temp_working_hrs = 0

        if len(query_ots) > 0:
            estimated_mandays = query_ots[0].estimated_mandays
            actual_mondays = 0
            temp_emp_no = query_ots[0].emp_no
            temp_checkin = query_ots[0].checkin_time.date()
        else:
            estimated_mandays = ""
            actual_mondays = 0
            temp_emp_no = ""
            temp_checkin = ""
        for q in query_ots:

            q.firsthr = 0
            q.meal_allowance = 0
            q.secondhr = 0
            q.ph = holiday_cnt
            if q.checkout_time is not None and q.checkin_time is not None:
                modetime = timedelta(hours=17)

                t_out = q.checkout_time
                t_in = q.checkin_time
                if q.checkout_time.date() > q.checkin_time.date():
                    timediff = timedelta(hours=t_out.hour, minutes=t_out.minute,
                                                  seconds=t_out.second) + timedelta(hours=24)
                else:
                    timediff = timedelta(hours=t_out.hour, minutes=t_out.minute, seconds=t_out.second)

                timestart = timedelta(hours=t_in.hour, minutes=t_in.minute, seconds=t_in.second)

                check_weekday = q.checkin_time.weekday()


                # For Sunday
                if check_weekday == 6:
                    # over 5:00 pm
                    if timediff > modetime:
                        min_check = (timediff - modetime).total_seconds() // 60
                        mins = min_check // 15
                        # over 5 hours of overtime allow meals.

                        if mins >= 20:
                            q.firsthr += mins * 0.25 - 0.5
                            q.meal_allowance += 1
                        # under 5 hours of overtime just consider 1.5HR
                        else:
                            q.firsthr += mins * 0.25

                        # For the 2.0HR part of over 5:00 pm
                        if modetime > timestart:
                            hr2_min_check = (modetime - timestart).total_seconds() // 60
                            hr2_mins = hr2_min_check // 15
                            if hr2_mins > 16:
                                q.secondhr += hr2_mins * 0.25 - 1
                            else:
                                q.secondhr += hr2_mins * 0.25
                    else:
                        ph_min_check = (q.checkout_time - q.checkin_time).total_seconds() // 60
                        ph_mins = ph_min_check // 15
                        if ph_mins >= 24:
                            q.secondhr += (ph_mins * 0.25 - 1)
                        else:
                            q.secondhr += (ph_mins * 0.25)
                # For normal days (Mon ~ Sat)
                else:
                    if timediff > modetime:
                        min_check = (timediff - modetime).total_seconds() // 60
                        mins = min_check // 15
                        if mins >= 20:
                            q.firsthr += (mins * 0.25 - 0.5)
                            q.meal_allowance += 1
                        else:
                            q.firsthr += (mins * 0.25)
                if temp_emp_no == q.emp_no and temp_checkin == q.checkin_time.date():
                    temp_working_hrs += q.difference
                else:
                    if temp_working_hrs > 240:
                        actual_mondays += 1
                    else:
                        actual_mondays += 0.5
                    temp_emp_no = q.emp_no
                    temp_checkin = q.checkin_time.date()
                    temp_working_hrs=q.difference

        if temp_working_hrs!=0 and temp_working_hrs>240:
            actual_mondays += 1
        elif temp_working_hrs!=0 and temp_working_hrs<=240:
            actual_mondays += 0.5

        empdata = []
        for query_ot in query_ots:
            if str(query_ot.emp_no) in empdata:
                pass
            else:
                empdata.append(query_ot.emp_no)

        for empd in empdata:
            for query_ot in query_ots:
                if empd == query_ot.emp_no:
                    # s_firstht = min(float(query_ot.approved_hour), float(query_ot.firsthr))
                    # s_secondht = min(float(query_ot.approved_hour), float(query_ot.secondhr))
                    s_firstht = float(query_ot.firsthr)
                    s_secondht = float(query_ot.secondhr)
                    total_1hr += float(s_firstht)
                    total_2hr += float(s_secondht)

        return render(request, 'projects/ajax-mandays-list.html',
                      {'mandays': query_ots, 'estimated_mandays': estimated_mandays, 'actual_mondays': actual_mondays,
                       'total_1hr': total_1hr, 'total_2hr': total_2hr})


@ajax_login_required
def ajax_filter_mandays(request):
    if request.method == "POST":
        proj_id = request.POST.get('proj_id')
        startDate = request.POST.get('startDate')
        endDate = request.POST.get('endDate')
        str_query = "SELECT F.id, F.approved_hour, F.emp_no, F.projectcode, F.checkin_time, F.checkout_time FROM (SELECT W.id, W.emp_no, O.approved_hour, W.projectcode, W.checkin_time, W.checkout_time FROM tb_worklog AS W, tb_ot as O WHERE W.projectcode = O.proj_id and DATE(W.checkin_time) = DATE(O.date)) AS F WHERE F.projectcode = " + "'" + proj_id + "'" + "AND F.checkin_time >= " + "'" + startDate + "'" + " AND F.checkout_time <= " + "'" + endDate + "'"
        query_ots = WorkLog.objects.raw(str_query)
        total_1hr = 0
        total_2hr = 0
        for q in query_ots:
            if q.checkout_time is not None and q.checkin_time is not None:
                modetime = timedelta(hours=17)
                holiday_modetime = timedelta(hours=8)

                t_out = q.checkout_time
                t_in = q.checkin_time
                if q.checkout_time.date() > q.checkin_time.date():
                    timediff = timedelta(hours=t_out.hour, minutes=t_out.minute,
                                                  seconds=t_out.second) + timedelta(hours=24)
                else:
                    timediff = timedelta(hours=t_out.hour, minutes=t_out.minute, seconds=t_out.second)

                timestart = timedelta(hours=t_in.hour, minutes=t_in.minute, seconds=t_in.second)

                check_weekday = q.checkin_time.weekday()
                check_holiday = Holiday.objects.filter(date=q.checkin_time.date()).exists()

                q.firsthr = 0
                q.meal_allowance = 0
                q.secondhr = 0
                q.ph = 0

                # For holiday
                if check_holiday == True:
                    q.ph += 1

                # For Sunday
                if check_weekday == 6:
                    # over 5:00 pm
                    if timediff > modetime:
                        min_check = (timediff - modetime).total_seconds() // 60
                        mins = min_check // 15
                        # over 5 hours of overtime allow meals.

                        if mins >= 20:
                            q.firsthr += mins * 0.25 - 0.5
                            q.meal_allowance += 1
                        # under 5 hours of overtime just consider 1.5HR
                        else:
                            q.firsthr += mins * 0.25

                        # For the 2.0HR part of over 5:00 pm
                        if modetime > timestart:
                            hr2_min_check = (modetime - timestart).total_seconds() // 60
                            hr2_mins = hr2_min_check // 15
                            if hr2_mins > 16:
                                q.secondhr += hr2_mins * 0.25 - 1
                            else:
                                q.secondhr += hr2_mins * 0.25
                    else:
                        ph_min_check = (q.checkout_time - q.checkin_time).total_seconds() // 60
                        ph_mins = ph_min_check // 15
                        if ph_mins >= 24:
                            q.secondhr += (ph_mins * 0.25 - 1)
                        else:
                            q.secondhr += (ph_mins * 0.25)
                # For normal days (Mon ~ Sat)
                else:
                    if timediff > modetime:
                        min_check = (timediff - modetime).total_seconds() // 60
                        mins = min_check // 15
                        if mins >= 20:
                            q.firsthr += (mins * 0.25 - 0.5)
                            q.meal_allowance += 1
                        else:
                            q.firsthr += (mins * 0.25)

        for q in query_ots:
            if q.checkout_time is not None and q.checkin_time is not None:
                total_1hr += float(str(q.firsthr).replace('HR', ''))
                total_2hr += float(str(q.secondhr).replace('HR', ''))
        return render(request, 'projects/ajax-mandays-list.html',
                      {'mandays': query_ots, 'total_1hr': total_1hr, 'total_2hr': total_2hr})


@ajax_login_required
def UpdateSummary(request):
    if request.method == "POST":

        company_nameid = request.POST.get('company_nameid')
        proj_name = request.POST.get('proj_name')
        worksite_address = request.POST.get('worksite_address')
        contact_person = request.POST.get('contact_person')
        email = request.POST.get('email')
        tel = request.POST.get('tel')
        fax = request.POST.get('fax')
        proj_incharge = request.POST.get('proj_incharge')
        site_incharge = request.POST.get('site_incharge')
        proj_postalcode = request.POST.get('postal_code')
        site_tel = request.POST.get('site_tel')
        RE = request.POST.get('re')
        proj_id = request.POST.get('proj_id')
        qtt_id = request.POST.get('qtt_id')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        latitude = request.POST.get('latitude')
        longitude = request.POST.get('longitude')
        proj_status = request.POST.get('proj_status')
        variation_order = request.POST.get('variation_order')
        note = request.POST.get('note')
        summaryid = request.POST.get('summaryid')

        payload = {
            'searchVal': proj_postalcode,
            'returnGeom': 'Y',
            'getAddrDetails': 'Y',
            'pageNum': '1'
        }
        print(latitude)
        print(longitude)
        # get long and lat data using postal code
        # mapinfo = requests.get('https://developers.onemap.sg/commonapi/search',
        try:
            mapinfo = requests.get('https://www.onemap.gov.sg/api/common/elastic/search',
                                   headers={"content-type": "application/json"}, params=payload)
            lat_lon_data = mapinfo.json()["results"]
            # lat_lon_data=[]
            if (len(lat_lon_data) != 0):
                latitude = lat_lon_data[0]["LATITUDE"]
                longitude = lat_lon_data[0]["LONGITUDE"]
        except OSError as e:
            print(e)

        try:
            summary = Project.objects.get(id=summaryid)
            prev_status=summary.proj_status
            prev_incharge=summary.proj_incharge

            summary.company_nameid_id = company_nameid
            summary.proj_name = proj_name
            summary.worksite_address = worksite_address
            summary.contact_person_id = contact_person
            summary.email = email
            summary.tel = tel
            summary.fax = fax
            summary.qtt_id = qtt_id
            summary.proj_id = proj_id
            summary.proj_incharge = proj_incharge
            summary.site_incharge = site_incharge
            summary.site_tel = site_tel
            summary.start_date = start_date
            summary.end_date = end_date
            summary.proj_postalcode = proj_postalcode
            summary.latitude = latitude
            summary.longitude = longitude
            summary.proj_status = proj_status
            summary.variation_order = variation_order
            summary.note = note
            summary.RE = RE
            summary.save()
            if summary.proj_incharge!=prev_incharge:
                sender = User.objects.filter(role="Managers").first()
                is_email = NotificationPrivilege.objects.get(user_id=sender.id).is_email
                description = '<a href="/project-summary-detail/'+str(summary.id)+'">Project No : {0} - Assigned to you.</a>'.format(
                    summary.proj_name)
                user_status=UserStatus.objects.get(status='resigned')
                for receiver in User.objects.exclude(status=user_status).filter(username=summary.proj_incharge):
                    if receiver.notificationprivilege.project_no_created:
                        notify.send(sender, recipient=receiver, verb='Message', level="success",
                                    description=description)
                        if is_email and receiver.email:
                            send_mail(receiver.email, "Project Awarded.", description)
            if summary.proj_status!=prev_status:
                sender = User.objects.filter(role="Managers").first()
                is_email = NotificationPrivilege.objects.get(user_id=sender.id).is_email
                description = '<a href="/project-summary-detail/'+str(summary.id)+'">Project Name : {0} - Status Changed from {1} to {2}.</a>'.format(
                    summary.proj_name, prev_status, summary.proj_status)
                user_status=UserStatus.objects.get(status='resigned')
                for receiver in User.objects.exclude(status=user_status).filter(Q(username=summary.proj_incharge) |Q(role='Managers')).distinct():
                    if receiver.notificationprivilege.project_no_created:
                        notify.send(sender, recipient=receiver, verb='Message', level="success",
                                    description=description)
                        if is_email and receiver.email:
                            send_mail(receiver.email, "Project Status Changed.", description)
            if latitude == "":
                return JsonResponse({
                    "status": "Wrong",
                    "messages": "Cannot get the latitude and longitude data!"
                })
            else:
                return JsonResponse({
                    "status": "Success",
                    "messages": "Project Summary information updated!"
                })
        except IntegrityError as e:
            print(e)
            return JsonResponse({
                "status": "Error",
                "messages": "Error is existed!"
            })


@ajax_login_required
def UpdatePcDetail(request):
    if request.method == "POST":

        proj_id = request.POST.get('proj_id')
        summaryid = request.POST.get('summaryid')
        project_sum = request.POST.get('project_sum')
        retention_amount = request.POST.get('retention_amount')
        retention_date = request.POST.get('retention_date')
        if project_sum=="" or retention_amount=="":
            return JsonResponse({
                "status": "Wrong",
                "messages": "Don't leave blank, insert a zero number instead."
            })
        try:
            if PcDetail.objects.filter(project_id=summaryid).exists():
                pcDetail=PcDetail.objects.get(project_id=summaryid)
                pcDetail.project_sum=project_sum
                pcDetail.retention_amt=retention_amount
                pcDetail.date_collect_retention=retention_date
                pcDetail.save()
            else:
                PcDetail.objects.create(
                    project_sum=project_sum,
                    retention_amt=retention_amount,
                    date_collect_retention=retention_date,
                    project_id=summaryid
                )
            return JsonResponse({
                "status": "Success",
                "messages": "Project PC information updated!"
            })
        except IntegrityError as e:
            print(e)
            return JsonResponse({
                "status": "Error",
                "messages": "Error is existed!"
            })


@ajax_login_required
def summarydelete(request):
    if request.method == "POST":
        summaryid = request.POST.get('summaryid')
        summary = Project.objects.get(id=summaryid)
        summary.delete()

        return JsonResponse({'status': 'ok'})


@ajax_login_required
def otadd(request):
    if request.method == "POST":
        proj_id = request.POST.get('proj_id')
        date = request.POST.get('date')
        approved_hour = request.POST.get('approved_hour')
        approved_by = request.POST.get('approved_by')
        comment = request.POST.get('comment')
        proj_name = request.POST.get('proj_name')
        otid = request.POST.get('otid')
        if otid == "-1":
            try:
                if OT.objects.filter(proj_id__iexact=proj_id, date=date.split(" ")[0]).exists():
                    return JsonResponse({
                        "status": "Error",
                        "messages": "Already Data is existed!"
                    })
                else:

                    OT.objects.create(
                        proj_id=proj_id,
                        date=date_parser.parse(date).replace(tzinfo=pytz.utc),
                        approved_hour=approved_hour,
                        approved_by=approved_by,
                        comment=comment,
                        proj_name=proj_name
                    )
                    return JsonResponse({
                        "status": "Success",
                        "messages": "OT information added!"
                    })
            except IntegrityError as e:
                return JsonResponse({
                    "status": "Error",
                    "messages": "Error is existed!"
                })
        else:
            try:
                ot = OT.objects.get(id=otid)
                ot.proj_id = proj_id
                ot.date = date
                ot.approved_hour = approved_hour
                ot.approved_by = approved_by
                ot.comment = comment
                ot.proj_name = proj_name
                ot.save()

                return JsonResponse({
                    "status": "Success",
                    "messages": "OT information updated!"
                })

            except IntegrityError as e:
                return JsonResponse({
                    "status": "Error",
                    "messages": "Error is existed!"
                })


@ajax_login_required
def getProjectOt(request):
    if request.method == "POST":
        otid = request.POST.get('otid')
        ot = OT.objects.get(id=otid)
        data = {
            'proj_id': ot.proj_id,
            'date': ot.date.strftime('%d %b, %Y'),
            'comment': ot.comment,
            'approved_by': ot.approved_by,
            'proj_name': ot.proj_name,
            'approved_hour': ot.approved_hour
        }
        return JsonResponse(json.dumps(data, cls=DecimalEncoder), safe=False)


@ajax_login_required
def otdelete(request):
    if request.method == "POST":
        otid = request.POST.get('otid')
        ot = OT.objects.get(id=otid)
        ot.delete()

        return JsonResponse({'status': 'ok'})


class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            return str(o)
        return super(DecimalEncoder, self).default(o)


@ajax_login_required
def check_do_number(request):
    if request.method == "POST":
        projDoNum=221000
        salesDoNum=221000
        if Do.objects.all().exists():
            projDo = Do.objects.all().order_by('-do_no')[0]
            projDoNum = int(projDo.do_no[3:])
        if ProductSalesDo.objects.all().exists():
            salesDo = ProductSalesDo.objects.all().order_by('-do_no')[0]
            salesDoNum=int(salesDo.do_no[3:])
        max_do_num = max([projDoNum, salesDoNum])

        data = {
            "status": "exist",
            "do_no": max_do_num
        }
        return JsonResponse(data)


@ajax_login_required
def getBom(request):
    if request.method == "POST":
        bomid = request.POST.get('bomid')
        bom = Bom.objects.get(id=bomid)
        if bom.date:

            data = {
                'description': bom.description,
                'uom': bom.uom_id,
                'ordered_qty': bom.ordered_qty,
                'brand': bom.brand,
                'delivered_qty': bom.delivered_qty,
                'delivered_po_no': bom.delivered_po_no,
                'date': bom.date.strftime('%d %b, %Y'),
                'remark': bom.remark,
            }
        else:
            data = {
                'description': bom.description,
                'uom': bom.uom_id,
                'ordered_qty': bom.ordered_qty,
                'brand': bom.brand,
                'delivered_qty': bom.delivered_qty,
                'delivered_po_no': bom.delivered_po_no,
                'date': '',
                'remark': bom.remark,
            }
        return JsonResponse(json.dumps(data), safe=False)


@ajax_login_required
def bomModal(request):
    if request.method == "POST":
        uoms = Uom.objects.all()
        item_cnt = request.POST.get('item_cnt')
        return render(request, 'projects/ajax-bom-modal.html', {'uoms': uoms, 'item_cnt': item_cnt})


@ajax_login_required
def bomadd(request):
    if request.method == "POST":
        items = json.loads(request.POST.get('items'))
        for item in items:
            description = item.get('description')
            uom = item.get('uom')
            ordered_qty = item.get('ordered_qty')
            brand = item.get('brand')
            delivery_qty = item.get('delivery_qty')
            if (delivery_qty == ""):
                delivery_qty = 0
            delivered_po_no = item.get('delivered_po_no')
            date = item.get('date')
            if date == "":
                date = None
            remark = item.get('remark')
            projectid = item.get('projectid')
            bomid = item.get('bomid')
            if bomid == "-1":
                try:
                    Bom.objects.create(
                        description=description,
                        uom_id=uom,
                        ordered_qty=ordered_qty,
                        brand=brand,
                        delivered_qty=delivery_qty,
                        delivered_po_no=delivered_po_no,
                        date=date,
                        remark=remark,
                        project_id=projectid,
                    )
                except IntegrityError as e:
                    return JsonResponse({
                        "status": "Error",
                        "messages": "Already Bom is existed!"
                    })
            else:
                try:
                    bom = Bom.objects.get(id=bomid)
                    bom.description = description
                    bom.uom_id = uom
                    bom.ordered_qty = ordered_qty
                    bom.brand = brand
                    bom.delivered_qty = delivery_qty
                    bom.delivered_po_no = delivered_po_no
                    bom.date = date
                    bom.remark = remark
                    bom.project_id = projectid
                    bom.save()

                except IntegrityError as e:
                    return JsonResponse({
                        "status": "Error",
                        "messages": "Already Bom is existed!"
                    })

        return JsonResponse({
            "status": "Success",
            "messages": "Bom information added!"
        })


@ajax_login_required
def bomlogadd(request):
    if request.method == "POST":
        description = request.POST.get('description')
        uom = request.POST.get('uom')
        delivered_qty = request.POST.get('delivered_qty')
        if (delivered_qty == ""):
            delivered_qty = 0
        do_no = request.POST.get('do_no')
        date = request.POST.get('date')
        if date == "":
            date = None
        remark = request.POST.get('remark')
        projectid = request.POST.get('projectid')
        bomid = request.POST.get('bomid')
        bomlogid = request.POST.get('bomlogid')
        if bomlogid == "-1":
            try:
                BomLog.objects.create(
                    description=description,
                    uom_id=uom,
                    delivered_qty=delivered_qty,
                    do_no=do_no,
                    date=date,
                    remark=remark,
                    bom_id=bomid,
                    project_id=projectid,
                )
                total_delivered_qty = \
                    BomLog.objects.filter(bom_id=bomid, project_id=projectid).aggregate(Sum('delivered_qty'))[
                        'delivered_qty__sum']
                bom = Bom.objects.get(id=bomid)
                bom.delivered_qty = total_delivered_qty
                bom.save()
                return JsonResponse({
                    "status": "Success",
                    "messages": "Bom Log information added!"
                })
            except IntegrityError as e:
                print(e)
                return JsonResponse({
                    "status": "Error",
                    "messages": "Already Bom Log is existed!"
                })


@ajax_login_required
def doadd(request):
    if request.method == "POST":
        do_no = request.POST.get('do_no')
        date = request.POST.get('dodate')
        if date == "":
            date = None
        projectid = request.POST.get('projectid')
        project_name = request.POST.get('project_name')
        doid = request.POST.get('doid')
        # if request.user.signature != "":
        #     status = "Signed"
        # else:
        #     status = "Open"
        if doid == "-1":
            if Do.objects.filter(do_no=do_no).exists() or ProductSalesDo.objects.filter(do_no=do_no).exists():
                return JsonResponse({
                    "status": "Error",
                    "messages": "This id has been taken by others, please close current window and create again.",
                })
            else:
                try:
                    do = Do.objects.create(
                        do_no=do_no,
                        date=date,
                        status="Open",
                        created_by_id=request.user.id,
                        project_id=projectid
                    )
                    return JsonResponse({
                        "status": "Success",
                        "messages": "Do information added!",
                        "newDoId": do.id,
                        "method": "add"
                    })
                except IntegrityError as e:
                    return JsonResponse({
                        "status": "Error",
                        "messages": "Already Do is existed!",
                    })
        else:
            try:
                do = Do.objects.get(id=doid)
                do.do_no = do_no
                do.date = date
                do.created_by_id = request.user.id
                # do.status = "Open"
                do.upload_by_id = request.user.id
                # do.project_id = projectid
                do.save()

                return JsonResponse({
                    "status": "Success",
                    "messages": "Do information updated!",
                    "newDoId": do.id,
                    "method": "update"
                })

            except IntegrityError as e:
                return JsonResponse({
                    "status": "Error",
                    "messages": "Already Do is existed!"
                })


@ajax_login_required
def dodocadd(request):
    if request.method == "POST":
        projectid = request.POST.get('projectid')
        dodocid = request.POST.get('dodocid')
        try:
            do = Do.objects.get(id=dodocid)
            do.upload_by_id = request.user.id
            do.project_id = projectid
            if request.FILES.get('document'):
                do.document = request.FILES.get('document')
                if do.status!="Signed":
                    # notification send
                    sender = User.objects.filter(role="Managers").first()
                    is_email = NotificationPrivilege.objects.get(user_id=sender.id).is_email

                    description = '<a href="/project-detail/' + str(
                        projectid) + '/delivery-order-detail/'+str(do.id)+'">Project Do No : {0} Status updated from {1} to Signed</a>'.format(
                        do.do_no, do.status)
                    user_status=UserStatus.objects.get(status='resigned')
                    for receiver in User.objects.exclude(status=user_status).filter(
                            Q(username=do.project.proj_incharge) | Q(role='Managers')).distinct():
                        if receiver.notificationprivilege.do_status:
                            notify.send(sender, recipient=receiver, verb='Message', level="success",
                                        description=description)
                            if is_email and receiver.email:
                                send_mail(receiver.email, "Notification for Do Status : ", description)
                do.status = "Signed"
            do.save()

            return JsonResponse({
                "status": "Success",
                "messages": "Do Document uploaded!"
            })

        except IntegrityError as e:
            return JsonResponse({
                "status": "Error",
                "messages": "Error!"
            })


@ajax_login_required
def srdocadd(request):
    if request.method == "POST":
        projectid = request.POST.get('projectid')
        srdocid = request.POST.get('srdocid')
        try:
            sr = Sr.objects.get(id=srdocid)
            sr.uploaded_by_id = request.user.id
            sr.project_id = projectid
            if request.FILES.get('document'):
                sr.document = request.FILES.get('document')
                if sr.status != "Signed":
                    # notification send
                    sender = User.objects.filter(role="Managers").first()
                    is_email = NotificationPrivilege.objects.get(user_id=sender.id).is_email

                    description = '<a href="/project-detail/' + str(
                        sr.project_id) + '/service-report-detail/' + str(
                        sr.id) + '">Project Sr No : {0} Status updated from {1} to Signed</a>'.format(
                        sr.sr_no, sr.status)
                    user_status=UserStatus.objects.get(status='resigned')
                    for receiver in User.objects.exclude(status=user_status).filter(
                            Q(username=sr.project.proj_incharge) | Q(role='Managers')).distinct():
                        if receiver.notificationprivilege.do_status:
                            notify.send(sender, recipient=receiver, verb='Message', level="success",
                                        description=description)
                            if is_email and receiver.email:
                                send_mail(receiver.email, "Notification for Sr Status : ", description)
                sr.status = "Signed"
            sr.save()

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
def pcdocadd(request):
    if request.method == "POST":
        projectid = request.POST.get('projectid')
        pcdocid = request.POST.get('pcdocid')
        try:
            pc = Pc.objects.get(id=pcdocid)
            pc.uploaded_by_id = request.user.id
            pc.project_id = projectid
            if request.FILES.get('document'):
                pc.document = request.FILES.get('document')
                pc.status = "Signed"
            pc.save()

            return JsonResponse({
                "status": "Success",
                "messages": "PC Document uploaded!"
            })

        except IntegrityError as e:
            return JsonResponse({
                "status": "Error",
                "messages": "Error!"
            })


@ajax_login_required
def teamadd(request):
    if request.method == "POST":
        teamuser = request.POST.get('teamuser')
        priority = request.POST.get('priority')
        teamid = request.POST.get('teamid')
        projectid = request.POST.get('projectid')
        tuser = User.objects.get(id=int(teamuser))
        if teamid == "-1":
            if Team.objects.filter(emp_no=tuser.empid, project_id=projectid).exists():
                return JsonResponse({
                    "status": "Error",
                    "messages": "Already Team is existed!"
                })
            else:
                try:
                    Team.objects.create(
                        emp_no=tuser.empid,
                        first_name=tuser.first_name,
                        last_name=tuser.last_name,
                        role=tuser.role,
                        priority=priority,
                        project_id=projectid,
                        user_id=tuser.id
                    )
                    return JsonResponse({
                        "status": "Success",
                        "messages": "Team information added!"
                    })
                except IntegrityError as e:
                    return JsonResponse({
                        "status": "Error",
                        "messages": "Already Team is existed!"
                    })
        else:
            try:
                team = Team.objects.get(id=teamid)
                if team.emp_no!=tuser.empid:
                    if Team.objects.filter(emp_no=tuser.empid, project_id=projectid).exists():
                        return JsonResponse({
                            "status": "Error",
                            "messages": "Already Team is existed!"
                        })

                team.emp_no = tuser.empid
                team.first_name = tuser.first_name
                team.last_name = tuser.last_name
                team.role = tuser.role
                team.priority = priority
                team.project_id = projectid
                team.user_id = tuser.id
                team.save()

                return JsonResponse({
                    "status": "Success",
                    "messages": "Team information updated!"
                })

            except IntegrityError as e:
                return JsonResponse({
                    "status": "Error",
                    "messages": "Already Team is existed!"
                })


@ajax_login_required
def getTeam(request):
    if request.method == "POST":
        teamid = request.POST.get('teamid')
        team = Team.objects.get(id=teamid)
        data = {
            'teamuser': str(team.user_id),
            'priority': team.priority,

        }
        return JsonResponse(json.dumps(data), safe=False)


@ajax_login_required
def deleteTeam(request):
    if request.method == "POST":
        team_id = request.POST.get('team_id')
        team = Team.objects.get(id=team_id)
        team.delete()

        return JsonResponse({'status': 'ok'})


@ajax_login_required
def deleteFile(request):
    if request.method == "POST":
        filedel_id = request.POST.get('filedel_id')
        projfile = ProjectFile.objects.get(id=filedel_id)
        projfile.delete()

        return JsonResponse({'status': 'ok'})


@ajax_login_required
def deleteBom(request):
    if request.method == "POST":
        bomdel_id = request.POST.get('bomdel_id')
        bom = Bom.objects.get(id=bomdel_id)
        bomlog = BomLog.objects.get(bom=bomdel_id)
        bomlog.delete()
        bom.delete()

        return JsonResponse({'status': 'ok'})


@ajax_login_required
def deleteDo(request):
    if request.method == "POST":
        dodel_id = request.POST.get('dodel_id')
        dodata = Do.objects.get(id=dodel_id)
        doitem = DoItem.objects.filter(do=dodel_id)
        dosign = DOSignature.objects.filter(do=dodel_id)
        doitem.delete()
        dosign.delete()
        dodata.delete()

        return JsonResponse({'status': 'ok'})


@ajax_login_required
def deleteSR(request):
    if request.method == "POST":
        srdel_id = request.POST.get('srdel_id')
        srdata = Sr.objects.get(id=srdel_id)
        sritems = SrItem.objects.filter(sr=srdel_id)
        srsign = SRSignature.objects.filter(sr=srdel_id)
        srsign.delete()
        sritems.delete()
        srdata.delete()

        return JsonResponse({'status': 'ok'})


@ajax_login_required
def deletePc(request):
    if request.method == "POST":
        pcdel_id = request.POST.get('pcdel_id')
        pcdata = Pc.objects.get(id=pcdel_id)
        pcdata.delete()
        return JsonResponse({'status': 'ok'})


def ajax_export_team(request, projectid):
    resource = TeamResource()
    queryset = Team.objects.filter(project_id=projectid)
    dataset = resource.export(queryset)
    response = HttpResponse(dataset.csv, content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="project_team.csv"'
    return response


def ajax_export_bom(request, projectid):
    resource = BomResource()
    queryset = Bom.objects.filter(project_id=projectid)
    dataset = resource.export(queryset)
    response = HttpResponse(dataset.csv, content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="project_bom.csv"'
    return response


def ajax_export_siteprogress(request, projectid):
    resource = SiteProgressResource()
    queryset = SiteProgress.objects.filter(project_id=projectid)
    dataset = resource.export(queryset)
    response = HttpResponse(dataset.csv, content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="site_progress_log.csv"'
    return response


@method_decorator(login_required, name='dispatch')
class DoDetailView(DetailView):
    model = Do
    pk_url_kwarg = 'dopk'
    template_name = "projects/delivery-order-detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        proj_pk = self.kwargs.get('pk')
        do_pk = self.kwargs.get('dopk')
        summary = Project.objects.get(id=proj_pk)
        context['summary'] = summary
        context['project_pk'] = proj_pk
        context['delivery_pk'] = do_pk
        delivery_order = Do.objects.get(id=do_pk)
        context['contacts'] = User.objects.all()
        context['companies'] = Company.objects.all()
        context['delivery_order'] = delivery_order
        quotation = summary.quotation
        context['doitems'] = DoItem.objects.filter(project_id=proj_pk, do_id=do_pk)
        context['quotation'] = quotation
        if (DOSignature.objects.filter(project_id=proj_pk, do_id=do_pk).exists()):
            context['dosignature'] = DOSignature.objects.get(project_id=proj_pk, do_id=do_pk)
        else:
            context['dosignature'] = None
        # context['projectitemall'] = Scope.objects.filter(quotation_id=quotation.id, bal_qty__gt=0)
        context['projectitemall'] = Scope.objects.filter(quotation_id=quotation.id, parent_id__isnull=True)
        return context


@method_decorator(login_required, name='dispatch')
class DoSignatureCreate(generic.CreateView):
    model = DOSignature
    fields = '__all__'
    template_name = "projects/delivery-signature.html"

    def post(self, request, *args, **kwargs):
        if request.method == 'POST':
            sign_name = request.POST.get("sign_name")
            sign_nric = request.POST.get("sign_nric")
            sign_date = request.POST.get("sign_date")
            DOSignature.objects.create(
                signature=request.POST.get('signature'),
                name=sign_name,
                nric=sign_nric,
                update_date=datetime.strptime(sign_date, '%d %b %Y'),
                do_id=self.kwargs.get('dopk'),
                project_id=self.kwargs.get('pk')
            )
            return HttpResponseRedirect(
                '/project-detail/' + self.kwargs.get('pk') + '/delivery-order-detail/' + self.kwargs.get('dopk'))


@method_decorator(login_required, name='dispatch')
class DoSignatureUpdate(generic.UpdateView):
    model = DOSignature
    pk_url_kwarg = 'signpk'
    fields = '__all__'
    template_name = "projects/delivery-signature.html"

    def post(self, request, *args, **kwargs):
        if request.method == 'POST':
            sign_name = request.POST.get("sign_name")
            sign_nric = request.POST.get("sign_nric")
            sign_date = request.POST.get("sign_date")
            doSignature = DOSignature.objects.get(id=self.kwargs.get('signpk'))
            doSignature.signature = request.POST.get('signature')
            doSignature.name = sign_name
            doSignature.nric = sign_nric
            doSignature.update_date = datetime.strptime(sign_date.replace(',', ""), '%d %b %Y').date()
            doSignature.do_id = self.kwargs.get('dopk')
            doSignature.project_id = self.kwargs.get('pk')
            doSignature.save()

            return HttpResponseRedirect(
                '/project-detail/' + self.kwargs.get('pk') + '/delivery-order-detail/' + self.kwargs.get('dopk'))


@ajax_login_required
def deliverysignadd(request):
    if request.method == "POST":
        name = request.POST.get('name')
        nric = request.POST.get('nric')
        date = request.POST.get('date')
        signature = request.POST.get('signature')
        deliveryid = request.POST.get('deliveryid')
        projectid = request.POST.get('projectid')
        default_base64 = request.POST.get("default_base64")
        doid = request.POST.get('doid')

        format, imgstr = default_base64.split(';base64,')
        ext = format.split('/')[-1]
        signature_image = ContentFile(base64.b64decode(imgstr),
                                      name='delivery-sign-' + date.today().strftime("%d-%m-%Y") + "." + ext)
        if deliveryid == "-1":
            try:
                DOSignature.objects.create(
                    name=name,
                    nric=nric,
                    update_date=date,
                    signature=signature,
                    do_id=doid,
                    project_id=projectid,
                    signature_image=signature_image
                )
                do=Do.objects.get(id=doid)
                if do.status!="Signed":
                    # notification send
                    sender = User.objects.filter(role="Managers").first()
                    is_email = NotificationPrivilege.objects.get(user_id=sender.id).is_email

                    description = '<a href="/project-detail/' + str(
                        projectid) + '/delivery-order-detail/'+str(do.id)+'">Project Do No : {0} Status updated from {1} to Signed</a>'.format(
                        do.do_no, do.status)
                    user_status=UserStatus.objects.get(status='resigned')
                    for receiver in User.objects.exclude(status=user_status).filter(
                            Q(username=do.project.proj_incharge) | Q(role='Managers')).distinct():
                        if receiver.notificationprivilege.do_status:
                            notify.send(sender, recipient=receiver, verb='Message', level="success",
                                        description=description)
                            if is_email and receiver.email:
                                send_mail(receiver.email, "Notification for Do Status : ", description)
                do.status="Signed"
                do.save()
                return JsonResponse({
                    "status": "Success",
                    "messages": "Delivery Signature information added!"
                })
            except IntegrityError as e:
                return JsonResponse({
                    "status": "Error",
                    "messages": "Error is existed!"
                })
        else:
            try:
                dosignature = DOSignature.objects.get(id=deliveryid)
                dosignature.name = name
                dosignature.nric = nric
                dosignature.update_date = date
                dosignature.signature = signature
                dosignature.do_id = doid
                dosignature.project_id = projectid
                dosignature.signature_image = signature_image
                dosignature.save()

                return JsonResponse({
                    "status": "Success",
                    "messages": "Delivery Signature information updated!"
                })

            except IntegrityError as e:
                return JsonResponse({
                    "status": "Error",
                    "messages": "Error is existed!"
                })


@ajax_login_required
def getDeliverySign(request):
    if request.method == "POST":
        deliveryid = request.POST.get('deliveryid')
        dosignature = DOSignature.objects.get(id=deliveryid)
        data = {
            'name': dosignature.name,
            'nric': dosignature.nric,
            'date': dosignature.update_date.strftime('%d %b, %Y'),
            'signature': dosignature.signature
        }
        return JsonResponse(json.dumps(data), safe=False)


@ajax_login_required
def getServiceSign(request):
    if request.method == "POST":
        serviceid = request.POST.get('serviceid')
        srsignature = SRSignature.objects.get(id=serviceid)
        data = {
            'name': srsignature.name,
            'nric': srsignature.nric,
            'date': srsignature.update_date.strftime('%d %b, %Y'),
            'signature': srsignature.signature
        }
        return JsonResponse(json.dumps(data), safe=False)


@ajax_login_required
def ajax_get_uom_name(request):
    if request.method == "POST":
        itemdescription = request.POST.get('itemdescription')
        project_id = request.POST.get("proj_id")
        project = Project.objects.get(id=project_id)
        quotation = project.quotation

        if Scope.objects.filter(quotation_id=quotation.id, description=itemdescription).exists():
            uom = Scope.objects.filter(quotation_id=quotation.id, description=itemdescription)[0]
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
def ajax_add_sr_invoice_no(request):
    if request.method == "POST":
        proj_type = request.POST.get('proj_type')
        invoice_no = request.POST.get('invoice_no')
        sr_id = request.POST.get('sr_id')
        try:
            invoice_format=InvoiceFormat.objects.last()
            prefix_len=len(invoice_format.prefix)
            input_suffix_len=len(invoice_no)-prefix_len
            if invoice_format.prefix==invoice_no[:prefix_len] and invoice_format.suffix==input_suffix_len:
                if proj_type=="1":
                    projSr=Sr.objects.get(id=sr_id)
                    projSr.invoice_no=invoice_no
                    projSr.save()
                elif proj_type=="2":
                    mainSr=MainSr.objects.get(id=sr_id)
                    mainSr.invoice_no=invoice_no
                    mainSr.save()
                return JsonResponse({
                    "status": "Success",
                    "messages": "Invoice Successfully added!"
                })
            else:
                return JsonResponse({
                    "status": "Failed",
                    "messages": f"Invoice No format should be '{invoice_format.prefix}-{invoice_format.suffix} characters'."
                })
        except DataError as e:
            return JsonResponse({
                "status": "Failed",
                "messages": f"Invoice No format should be '{invoice_format.prefix}-{invoice_format.suffix} characters'."
            })
        except AttributeError as e:
            return JsonResponse({
                "status": "Failed",
                "messages": "Please define invoice format first."
            })

@ajax_login_required
def ajax_add_do_invoice_no(request):
    if request.method == "POST":
        proj_type = request.POST.get('proj_type')
        invoice_no = request.POST.get('invoice_no')
        do_id = request.POST.get('do_id')
        try:
            invoice_format=InvoiceFormat.objects.last()
            prefix_len=len(invoice_format.prefix)
            input_suffix_len=len(invoice_no)-prefix_len
            if invoice_format.prefix==invoice_no[:prefix_len] and invoice_format.suffix==input_suffix_len:
                if proj_type=="1":
                    projDo=Do.objects.get(id=do_id)
                    projDo.invoice_no=invoice_no
                    projDo.save()
                elif proj_type=="2":
                    salesDo=ProductSalesDo.objects.get(id=do_id)
                    salesDo.invoice_no=invoice_no
                    salesDo.save()
                return JsonResponse({
                    "status": "Success",
                    "messages": "Invoice Successfully added!"
                })
            else:
                return JsonResponse({
                    "status": "Failed",
                    "messages": f"Invoice No format should be '{invoice_format.prefix}-{invoice_format.suffix} characters'."
                })
        except DataError as e:
            return JsonResponse({
                "status": "Failed",
                "messages": f"Invoice No format should be '{invoice_format.prefix}-{invoice_format.suffix} characters'."
            })
        except AttributeError as e:
            return JsonResponse({
                "status": "Failed",
                "messages": "Please define invoice format first."
            })
@ajax_login_required
def ajax_add_pc_invoice_no(request):
    if request.method == "POST":
        invoice_no = request.POST.get('invoice_no')
        pc_id = request.POST.get('pc_id')
        try:
            invoice_format=InvoiceFormat.objects.last()
            prefix_len=len(invoice_format.prefix)
            input_suffix_len=len(invoice_no)-prefix_len
            if invoice_format.prefix==invoice_no[:prefix_len] and invoice_format.suffix==input_suffix_len:
                projPc=Pc.objects.get(id=pc_id)
                projPc.invoice_no=invoice_no
                projPc.save()
                return JsonResponse({
                    "status": "Success",
                    "messages": "Invoice Successfully added!"
                })
            else:
                return JsonResponse({
                    "status": "Failed",
                    "messages": f"Invoice No format should be '{invoice_format.prefix}-{invoice_format.suffix} characters'."
                })
        except DataError as e:
            return JsonResponse({
                "status": "Failed",
                "messages": f"Invoice No format should be '{invoice_format.prefix}-{invoice_format.suffix} characters'."
            })
        except AttributeError as e:
            return JsonResponse({
                "status": "Failed",
                "messages": "Please define invoice format first."
            })


@ajax_login_required
def servicesignadd(request):
    if request.method == "POST":
        name = request.POST.get('name')
        nric = request.POST.get('nric')
        date = request.POST.get('date')
        signature = request.POST.get('signature')
        serviceid = request.POST.get('serviceid')
        projectid = request.POST.get('projectid')
        default_base64 = request.POST.get("default_base64")
        srid = request.POST.get('srid')

        format, imgstr = default_base64.split(';base64,')
        ext = format.split('/')[-1]
        signature_image = ContentFile(base64.b64decode(imgstr),
                                      name='service-sign-' + date.today().strftime("%d-%m-%Y") + "." + ext)
        if serviceid == "-1":
            try:
                SRSignature.objects.create(
                    name=name,
                    nric=nric,
                    update_date=date,
                    signature=signature,
                    sr_id=srid,
                    project_id=projectid,
                    signature_image=signature_image
                )
                sr=Sr.objects.get(id=srid)
                if sr.status != "Signed":
                    # notification send
                    sender = User.objects.filter(role="Managers").first()
                    is_email = NotificationPrivilege.objects.get(user_id=sender.id).is_email

                    description = '<a href="/project-detail/' + str(
                        sr.project_id) + '/service-report-detail/' + str(
                        sr.id) + '">Project Sr No : {0} Status updated from {1} to Signed</a>'.format(
                        sr.sr_no, sr.status)
                    user_status=UserStatus.objects.get(status='resigned')
                    for receiver in User.objects.exclude(status=user_status).filter(
                            Q(username=sr.project.proj_incharge) | Q(role='Managers')).distinct():
                        if receiver.notificationprivilege.do_status:
                            notify.send(sender, recipient=receiver, verb='Message', level="success",
                                        description=description)
                            if is_email and receiver.email:
                                send_mail(receiver.email, "Notification for Sr Status : ", description)
                sr.status = "Signed"
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
                srsignature = SRSignature.objects.get(id=serviceid)
                srsignature.name = name
                srsignature.nric = nric
                srsignature.update_date = date
                srsignature.signature = signature
                srsignature.sr_id = srid
                srsignature.project_id = projectid
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


@ajax_login_required
def check_sr_number(request):
    if request.method == "POST":
        projSrNum = 221000
        mainSrNum = 221000
        if Sr.objects.all().exists():
            projSr = Sr.objects.all().order_by('-sr_no')[0]
            projSrNum = int(projSr.sr_no[3:])
        if MainSr.objects.all().exists():
            mainSr = MainSr.objects.all().order_by('-sr_no')[0]
            mainSrNum = int(mainSr.sr_no[3:])
        max_sr_num = max([projSrNum, mainSrNum])
        data = {
            "status": "exist",
            "sr_no": max_sr_num
        }
        return JsonResponse(data)


@ajax_login_required
def check_pc_number(request):
    if request.method == "POST":
        if Pc.objects.all().exists():
            pc = Pc.objects.all().order_by('-pc_no')[0]
            data = {
                "status": "exist",
                "pc_no": pc.pc_no.replace('CPC', '').split()[0]
            }

            return JsonResponse(data)
        else:
            data = {
                "status": "no exist"
            }

            return JsonResponse(data)


@ajax_login_required
def sradd(request):
    if request.method == "POST":
        sr_no = request.POST.get('sr_no')
        date = request.POST.get('srdate')
        if date == "":
            date = None
        projectid = request.POST.get('projectid')
        project_name = request.POST.get('project_name')
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
                sr = Sr.objects.create(
                    sr_no=sr_no,
                    date=date,
                    status="Open",
                    created_by_id=request.user.id,
                    project_id=projectid,
                )
                return JsonResponse({
                    "status": "Success",
                    "method": "add",
                    "newSrID": sr.id,
                    "messages": "Service Report information added!"
                })
            except IntegrityError as e:
                return JsonResponse({
                    "status": "Error",
                    "messages": "Already SR is existed!"
                })
        else:
            try:
                sr = Sr.objects.get(id=srid)
                sr.sr_no = sr_no
                sr.date = date
                sr.status = "Open"
                sr.created_by_id = request.user.id,
                # sr.uploaded_by_id=request.user.id
                sr.project_id = projectid
                sr.save()

                return JsonResponse({
                    "status": "Success",
                    "method": "update",
                    "newSrID": sr.id,
                    "messages": "Service Report information updated!"
                })

            except IntegrityError as e:
                return JsonResponse({
                    "status": "Error",
                    "messages": "Already SR is existed!"
                })


@ajax_login_required
def pcadd(request):
    if request.method == "POST":
        pc_no = request.POST.get('pc_no')
        amount = request.POST.get('amount')
        pay_cert_no = request.POST.get('pay_cert_no')
        date = request.POST.get('pcdate')
        if date == "":
            date = None
        projectid = request.POST.get('projectid')
        pcid = request.POST.get('pcid')
        # if request.user.signature != "":
        #     status = "Signed"
        # else:
        #     status = "Open"
        if pcid == "-1":
            try:
                pc = Pc.objects.create(
                    pc_no=pc_no,
                    amount=amount,
                    payment_cert_no=pay_cert_no,
                    date=date,
                    status="Open",
                    # uploaded_by_id=request.user.id,
                    project_id=projectid,
                )
                return JsonResponse({
                    "status": "Success",
                    "method": "add",
                    "newPcID": pc.id,
                    "messages": "Progress Claim information added!"
                })
            except IntegrityError as e:
                return JsonResponse({
                    "status": "Error",
                    "messages": "Already PC is existed!"
                })
        else:
            try:
                pc = Pc.objects.get(id=pcid)
                pc.pc_no = pc_no
                pc.payment_cert_no = pay_cert_no
                pc.amount = amount
                pc.date = date
                # pc.status = "Open"
                # pc.uploaded_by_id=request.user.id
                pc.project_id = projectid
                pc.save()

                return JsonResponse({
                    "status": "Success",
                    "method": "update",
                    "newPcID": pc.id,
                    "messages": "Progress Claim information updated!"
                })

            except IntegrityError as e:
                return JsonResponse({
                    "status": "Error",
                    "messages": "Already PC is existed!"
                })


@method_decorator(login_required, name='dispatch')
class SrDetailView(DetailView):
    model = Sr
    pk_url_kwarg = 'srpk'
    template_name = "projects/service-report-detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        proj_pk = self.kwargs.get('pk')
        sr_pk = self.kwargs.get('srpk')
        summary = Project.objects.get(id=proj_pk)
        context['summary'] = summary
        context['project_pk'] = proj_pk
        context['service_pk'] = sr_pk
        service_report = Sr.objects.get(id=sr_pk)
        # if service_report.remark =="":
        #     service_report.remark=summary.proj_name
        context['contacts'] = Contact.objects.all()
        context['uoms'] = Uom.objects.all()
        context['service_report'] = service_report
        quotation = summary.quotation
        context['sritems'] = SrItem.objects.filter(project_id=proj_pk, sr_id=sr_pk)
        context['quotation'] = quotation
        if (SRSignature.objects.filter(project_id=proj_pk, sr_id=sr_pk).exists()):
            context['srsignature'] = SRSignature.objects.get(project_id=proj_pk, sr_id=sr_pk)
        else:
            context['srsignature'] = None
        context['projectitemall'] = Scope.objects.filter(quotation_id=quotation.id, parent_id__isnull=True)
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
def ajax_update_service_report(request):
    if request.method == "POST":
        srtype = request.POST.get('srtype')
        srpurpose = request.POST.get('srpurpose')
        srsystem = request.POST.get('srsystem')
        timein = request.POST.get('timein')
        timeout = request.POST.get('timeout')
        remark = request.POST.get('remark')
        servicepk = request.POST.get('servicepk')

        srdata = Sr.objects.get(id=servicepk)
        srdata.srtype = srtype
        srdata.srpurpose = srpurpose
        srdata.srsystem = srsystem
        if timein!="NaN-NaN-NaN aN:aN":
            srdata.time_in = date_parser.parse(timein).replace(tzinfo=pytz.utc)
        if timeout!="NaN-NaN-NaN aN:aN":
            srdata.time_out = date_parser.parse(timeout).replace(tzinfo=pytz.utc)
        srdata.remark = remark
        srdata.save()

        return JsonResponse({
            "status": "Success",
            "messages": "Service Report information updated!"
        })


@ajax_login_required
def ajax_update_progress_claim(request):
    if request.method == "POST":
        pcclaimno = request.POST.get('pcclaimno')
        # terms = request.POST.get("terms")
        less_previous_claim = request.POST.get("less_previous_claim")
        progresspk = request.POST.get('progresspk')

        pcdata = Pc.objects.get(id=progresspk)
        pcdata.claim_no = int(pcclaimno)
        # pcdata.terms = terms
        pcdata.less_previous_claim = less_previous_claim
        pcdata.save()

        return JsonResponse({
            "status": "Success",
            "messages": "Progress Claim information updated!"
        })


@method_decorator(login_required, name='dispatch')
class SrSignatureCreate(generic.CreateView):
    model = SRSignature
    fields = '__all__'
    template_name = "projects/service-signature.html"

    def post(self, request, *args, **kwargs):
        if request.method == 'POST':
            sign_name = request.POST.get("sign_name")
            sign_nric = request.POST.get("sign_nric")
            sign_date = request.POST.get("sign_date")
            SRSignature.objects.create(
                signature=request.POST.get('signature'),
                name=sign_name,
                nric=sign_nric,
                update_date=datetime.strptime(sign_date, '%d %b %Y'),
                sr_id=self.kwargs.get('srpk'),
                project_id=self.kwargs.get('pk')
            )
            return HttpResponseRedirect(
                '/project-detail/' + self.kwargs.get('pk') + '/service-report-detail/' + self.kwargs.get('srpk'))


@method_decorator(login_required, name='dispatch')
class SrSignatureUpdate(generic.UpdateView):
    model = SRSignature
    pk_url_kwarg = 'signpk'
    fields = '__all__'
    template_name = "projects/service-signature.html"

    def post(self, request, *args, **kwargs):
        if request.method == 'POST':
            sign_name = request.POST.get("sign_name")
            sign_nric = request.POST.get("sign_nric")
            sign_date = request.POST.get("sign_date")
            srSignature = SRSignature.objects.get(id=self.kwargs.get('signpk'))
            srSignature.signature = request.POST.get('signature')
            srSignature.name = sign_name
            srSignature.nric = sign_nric
            srSignature.update_date = datetime.strptime(sign_date.replace(',', ""), '%d %b %Y').date()
            srSignature.sr_id = self.kwargs.get('srpk')
            srSignature.project_id = self.kwargs.get('pk')
            srSignature.save()

            return HttpResponseRedirect(
                '/project-detail/' + self.kwargs.get('pk') + '/service-report-detail/' + self.kwargs.get('srpk'))


@ajax_login_required
def deleteSRItem(request):
    if request.method == "POST":
        sritem_del_id = request.POST.get('del_id')
        sritem = SrItem.objects.get(id=sritem_del_id)
        sritem.delete()

        return JsonResponse({'status': 'ok'})


@ajax_login_required
def deleteDOItem(request):
    if request.method == "POST":
        doitem_del_id = request.POST.get('del_id')
        doitem = DoItem.objects.get(id=doitem_del_id)
        doitem.delete()

        projectid = doitem.project_id
        description = doitem.description
        quotationid = Project.objects.get(id=projectid).quotation_id
        scope = Scope.objects.get(quotation_id=quotationid, description__iexact=description)
        do_items = DoItem.objects.filter(project_id=projectid, description__iexact=description).aggregate(Sum('qty'))
        if do_items['qty__sum']:
            scope.bal_qty = int(scope.qty) - int(do_items['qty__sum'])
        else:
            scope.bal_qty = int(scope.qty)
        scope.save()
        return JsonResponse({'status': 'ok'})


@ajax_login_required
def srItemAdd(request):
    if request.method == "POST":
        projectid = request.POST.get('projectid')
        items = json.loads(request.POST.get('items'))
        srid = request.POST.get('srid')
        for item in items:
            description = item.get('description')
            qty = item.get('qty')
            uom = item.get('uom')
            sritemid = item.get('sritemid')
            if sritemid == "-1":
                try:
                    SrItem.objects.create(
                        description=description,
                        qty=qty,
                        uom_id=uom,
                        project_id=projectid,
                        sr_id=srid
                    )
                except IntegrityError as e:
                    return JsonResponse({
                        "status": "Error",
                        "messages": "Already SR Item is existed!"
                    })
            else:
                try:
                    sritem = SrItem.objects.get(id=sritemid)
                    sritem.description = description
                    sritem.qty = qty
                    sritem.uom_id = uom
                    sritem.project_id = projectid
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

        return JsonResponse({
            "status": "Success",
            "messages": "Service Report Item information added!"
        })

@ajax_login_required
def doItemAdd(request):
    if request.method == "POST":
        projectid = request.POST.get('projectid')
        doid = request.POST.get('doid')
        items = json.loads(request.POST.get('items'))
        for item in items:
            description = item.get('description')
            qty = item.get('qty')
            uom = item.get('uom')
            doitemid = item.get('doitemid')

            if doitemid == "-1":
                try:
                    DoItem.objects.create(
                        description=description,
                        qty=qty,
                        uom_id=uom,
                        project_id=projectid,
                        do_id=doid
                    )
                    quotationid = Project.objects.get(id=projectid).quotation_id
                    scope = Scope.objects.get(quotation_id=quotationid, description__iexact=description)
                    do_items = DoItem.objects.filter(project_id=projectid, description__iexact=description).aggregate(
                        Sum('qty'))
                    scope.bal_qty = int(scope.qty) - int(do_items['qty__sum'])
                    scope.save()
                except IntegrityError as e:
                    return JsonResponse({
                        "status": "Error",
                        "messages": "Already DO Item is existed!"
                    })
            else:
                try:

                    doitem = DoItem.objects.get(id=doitemid)
                    doitem.description = description
                    doitem.qty = qty
                    doitem.uom_id = uom
                    doitem.project_id = projectid
                    doitem.do_id = doid
                    doitem.save()

                    quotationid = Project.objects.get(id=projectid).quotation_id
                    scope = Scope.objects.get(quotation_id=quotationid, description__iexact=description)
                    do_items = DoItem.objects.filter(project_id=projectid, description__iexact=description).aggregate(
                        Sum('qty'))
                    scope.bal_qty = int(scope.qty) - int(do_items['qty__sum'])
                    scope.save()

                    return JsonResponse({
                        "status": "Success",
                        "messages": "Delivery Order Item information updated!"
                    })

                except IntegrityError as e:
                    return JsonResponse({
                        "status": "Error",
                        "messages": "Already DO Item is existed!"
                    })


        return JsonResponse({
            "status": "Success",
            "messages": "Delivery Order Item information added!"
        })
@ajax_login_required
def getDoItem(request):
    if request.method == "POST":
        doitemid = request.POST.get('doitemid')
        doitem = DoItem.objects.get(id=doitemid)

        data = {
            'description': doitem.description,
            'qty': doitem.qty,
            'uom': doitem.uom.name,
            'uom_id': doitem.uom_id,
        }
        return JsonResponse(json.dumps(data), safe=False)

@ajax_login_required
def getSrItem(request):
    if request.method == "POST":
        sritemid = request.POST.get('sritemid')
        sritem = SrItem.objects.get(id=sritemid)
        data = {
            'description': sritem.description,
            'qty': sritem.qty,
            'uom': sritem.uom.name,
            'uom_id': sritem.uom_id,
        }
        return JsonResponse(json.dumps(data), safe=False)



def ajax_export_do_item(request, projectid, doid):
    resource = DoItemResource()
    queryset = DoItem.objects.filter(project_id=projectid, do_id=doid)
    dataset = resource.export(queryset)
    response = HttpResponse(dataset.csv, content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="project_do_items.csv"'
    return response


def ajax_export_sr_item(request, projectid, srid):
    resource = SrItemResource()
    queryset = SrItem.objects.filter(project_id=projectid, sr_id=srid)
    dataset = resource.export(queryset)
    response = HttpResponse(dataset.csv, content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="project_sr_items.csv"'
    return response


@ajax_login_required
def UpdateDeliveryOrder(request):
    if request.method == "POST":
        company_nameid = request.POST.get('company_nameid')
        address = request.POST.get('address')
        attn = request.POST.get('attn')
        tel = request.POST.get('tel')
        shipto = request.POST.get('shipto')
        proj_id = request.POST.get('proj_id')
        doid = request.POST.get('doid')
        remarks = request.POST.get('remarks')

        try:
            delivery = Do.objects.get(id=doid)
            delivery.company_nameid = company_nameid
            delivery.address = address
            delivery.attn = attn
            delivery.tel = tel
            delivery.ship_to = shipto
            delivery.remarks = remarks
            delivery.save()

            return JsonResponse({
                "status": "Success",
                "messages": "Delivery Order information updated!"
            })
        except IntegrityError as e:
            print(e)
            return JsonResponse({
                "status": "Error",
                "messages": "Error is existed!"
            })


@method_decorator(login_required, name='dispatch')
class BomDetailView(DetailView):
    model = Bom
    pk_url_kwarg = 'bompk'
    template_name = "projects/bomlog-detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        proj_pk = self.kwargs.get('pk')
        bom_pk = self.kwargs.get('bompk')
        context['project_pk'] = proj_pk
        context['bom_pk'] = bom_pk
        context['uoms'] = Uom.objects.all()
        context['bom_logs'] = BomLog.objects.filter(bom_id=bom_pk)
        context['delivered_total'] = \
            BomLog.objects.filter(bom_id=bom_pk, project_id=proj_pk).aggregate(Sum('delivered_qty'))[
                'delivered_qty__sum']
        return context


@ajax_login_required
def subitemadd(request):
    if request.method == "POST":
        description = request.POST.get('description')
        uom = request.POST.get('uom')
        qty = request.POST.get('qty')
        # allocation_perc = request.POST.get('allocation')
        allocation_perc = 100
        quotationid = request.POST.get('quotationid')
        itemid = request.POST.get('itemid')
        Scope.objects.create(
            description=description,
            uom_id=uom,
            qty=qty,
            allocation_perc=allocation_perc,
            quotation_id=quotationid,
            parent_id=itemid,
        )
        # #parent allocation_perc update
        # parent = Scope.objects.get(id=itemid)
        # allocation_sum = Scope.objects.filter(parent_id=itemid).aggregate(Sum('allocation_perc'))['allocation_perc__sum']
        # parent.allocation_perc = allocation_sum
        # parent.save()

        return JsonResponse({
            "status": "Success",
            "messages": "Scope Item information added!"
        })


@ajax_login_required
def getItem(request):
    if request.method == "POST":
        iid = request.POST.get('iid')
        item = Scope.objects.get(id=iid)
        data = {
            'description': item.description,
            'uom_id': item.uom.id,
            'uom': item.uom.name,
            'qty': item.qty,
            'allocation': item.allocation_perc,
        }
        return JsonResponse(json.dumps(data), safe=False)


@ajax_login_required
def getItemUom(request):
    if request.method == "POST":
        itemdescription = request.POST.get('itemdescription')
        quotationid = request.POST.get('quotationid')
        item = Scope.objects.get(quotation_id=quotationid, description__iexact=itemdescription)
        product_sales=ProductSales.objects.filter(quotation_id=quotationid)
        used_qty=ProductSalesDoItem.objects.filter(product_sales__in=product_sales).aggregate(Sum('qty'))['qty__sum']
        if used_qty is None:
            used_qty=0
        data = {
            'uom_id': item.uom_id,
            'uom': item.uom.name,
            'item_qty': item.bal_qty-used_qty,
        }
        return JsonResponse(json.dumps(data), safe=False)


@ajax_login_required
def itemadd(request):
    if request.method == "POST":
        description = request.POST.get('description')
        uom = request.POST.get('uom')
        qty = request.POST.get('qty')
        allocation = request.POST.get('allocation')
        iid = request.POST.get('iid')

        try:
            scope = Scope.objects.get(id=iid)
            scope.description = description
            scope.uom_id = uom
            scope.qty = qty
            scope.bal_qty = qty
            scope.allocation_perc = allocation

            scope.save()
            # #parent allocation_perc update
            # parent = Scope.objects.get(id=scope.parent_id)
            # allocation_sum = Scope.objects.filter(parent_id=scope.parent_id).aggregate(Sum('allocation_perc'))['allocation_perc__sum']
            # parent.allocation_perc = allocation_sum
            # parent.save()
            return JsonResponse({
                "status": "Success",
                "messages": "Scope information updated!"
            })
        except IntegrityError as e:
            print(e)
            return JsonResponse({
                "status": "Error",
                "messages": "Already Scope is existed!"
            })


@ajax_login_required
def siteprogressadd(request):
    if request.method == "POST":
        date = request.POST.get('date')
        description = request.POST.get('description')
        remark = request.POST.get('remark')
        qty = request.POST.get('qty')
        siteid = request.POST.get('siteid')
        projectid = request.POST.get('projectid')
        if siteid == "-1":
            try:
                SiteProgress.objects.create(
                    description=description,
                    remark=remark,
                    qty=qty,
                    date=date,
                    project_id=projectid
                )
                return JsonResponse({
                    "status": "Success",
                    "messages": "Site Progress information added!"
                })
            except IntegrityError as e:
                return JsonResponse({
                    "status": "Error",
                    "messages": "Error is existed!"
                })
        else:
            try:
                siteprogress = SiteProgress.objects.get(id=siteid)
                siteprogress.description = description
                siteprogress.date = date
                siteprogress.remark = remark
                siteprogress.qty = qty
                siteprogress.project_id = projectid
                siteprogress.save()

                return JsonResponse({
                    "status": "Success",
                    "messages": "Site Progress information updated!"
                })

            except IntegrityError as e:
                return JsonResponse({
                    "status": "Error",
                    "messages": "Error is existed!"
                })


@ajax_login_required
def getSiteProgress(request):
    if request.method == "POST":
        siteid = request.POST.get('siteid')
        site = SiteProgress.objects.get(id=siteid)
        data = {
            'description': site.description,
            'date': site.date.strftime('%d %b, %Y'),
            'remark': str(site.remark),
            'qty': site.qty
        }
        return JsonResponse(json.dumps(data), safe=False)


@ajax_login_required
def sitedelete(request):
    if request.method == "POST":
        siteid = request.POST.get('siteid')
        site = SiteProgress.objects.get(id=siteid)
        site.delete()

        return JsonResponse({'status': 'ok'})


@ajax_login_required
def toolboxitemadd(request):
    if request.method == "POST":
        description = request.POST.get('description')
        objective = request.POST.get('objective')
        remark = request.POST.get('remark')
        activity = request.POST.get('activity')
        manager = request.POST.get('manager')
        projectid = request.POST.get('projectid')
        toolboxitemid = request.POST.get('toolboxid')

        if toolboxitemid == "-1":
            try:
                ToolBoxItem.objects.create(
                    objective=objective,
                    remark=remark,
                    manager=manager,
                    description=description,
                    project_id=projectid,
                )
                return JsonResponse({
                    "status": "Success",
                    "messages": "ToolBox Item information added!",

                })
            except IntegrityError as e:
                return JsonResponse({
                    "status": "Error",
                    "messages": "Error is existed!"
                })
        else:
            try:
                tbmitem = ToolBoxItem.objects.get(id=toolboxitemid)
                tbmitem.activity = activity
                tbmitem.objective = objective
                tbmitem.remark = remark
                tbmitem.manager = manager
                tbmitem.description = description
                tbmitem.project_id = projectid
                tbmitem.save()

                return JsonResponse({
                    "status": "Success",
                    "messages": "ToolBox Item information updated!",
                })

            except IntegrityError as e:
                return JsonResponse({
                    "status": "Error",
                    "messages": "Error is existed!"
                })


@ajax_login_required
def getToolBoxItem(request):
    if request.method == "POST":
        toolboxid = request.POST.get('toolboxid')
        tbmitem = ToolBoxItem.objects.get(id=toolboxid)
        data = {
            'activity': tbmitem.activity,
            'objective': tbmitem.objective,
            'description': tbmitem.description,
            'remark': tbmitem.remark,
        }
        return JsonResponse(json.dumps(data), safe=False)


@ajax_login_required
def tbmitemdelete(request):
    if request.method == "POST":
        tbmitemid = request.POST.get('tbmitemdel_id')
        tbmitem = ToolBoxItem.objects.get(id=tbmitemid)
        tbmitem.delete()

        return JsonResponse({'status': 'ok'})


def exportSrPDF(request, value):
    sr = Sr.objects.get(id=value)
    project = sr.project
    quotation = project.quotation
    sritems = SrItem.objects.filter(sr_id=value)

    domain = os.getenv("DOMAIN")
    logo = Image('http://' + domain + '/static/assets/images/printlogo.png', hAlign='LEFT')
    response = HttpResponse(content_type='application/pdf')
    currentdate = date.today().strftime("%d-%m-%Y")
    pdfname = sr.sr_no + ".pdf"
    response['Content-Disposition'] = 'attachment; filename={}'.format(pdfname)
    story = []
    buff = BytesIO()
    doc = SimpleDocTemplate(buff, pagesize=portrait(A4), rightMargin=0.25 * inch, leftMargin=0.45 * inch,
                            topMargin=4.3 * inch, bottomMargin=2.7 * inch, title=pdfname)
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
                # ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                # ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
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
    # exportD._argH[1] = 0.3 * inch
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
                  Paragraph('''<para><font size=9>%s</font></para>'''% (str(remarks).replace('\n','<br />\n')),ps)]]
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
    doc.build(story, canvasmaker=NumberedCanvas, onFirstPage=partial(header_sr, sr=sr, value=value, domain=domain), onLaterPages=partial(header_sr, sr=sr, value=value, domain=domain))
    response.write(buff.getvalue())
    buff.close()

    return response


def exportPcPDF(request, value):
    pc = Pc.objects.get(id=value)
    project = pc.project
    domain = os.getenv("DOMAIN")
    response = HttpResponse(content_type='application/pdf')
    currentdate = date.today().strftime("%d-%m-%Y")
    pdfname = pc.pc_no + ".pdf"
    response['Content-Disposition'] = 'attachment; filename="{}"'.format(pdfname)
    story = []
    buff = BytesIO()
    doc = SimpleDocTemplate(buff, pagesize=landscape(A4), rightMargin=0.25 * inch, leftMargin=0.25 * inch,
                            topMargin=1.4 * inch, bottomMargin=0.5 * inch, title=pdfname)
    styleSheet = getSampleStyleSheet()

    story.append(Spacer(1, 16))
    if pc.claim_no:
        claimno = pc.claim_no
    else:
        claimno = ""
    quotation = project.quotation
    if quotation.company_nameid.unit:
        qunit = quotation.company_nameid.unit
    else:
        qunit = ""
    if quotation.sale_person:
        qsale_person = quotation.sale_person
    else:
        qsale_person = ""

    if quotation.terms:
        qterms = quotation.terms
    else:
        qterms = ""
    if quotation.po_no:
        qpo_no = quotation.po_no
    else:
        qpo_no = ""
    pcindata = [
        [Paragraph('''<para align=left><font size=10><b>To: </b></font></para>'''),
         Paragraph('''<para align=left><font size=10>%s</font></para>''' % (quotation.company_nameid)), "", "", "",
         Paragraph('''<para align=center><font size=16><b>PROGRESS CLAIM</b></font></para>''')],
        ["", Paragraph('''<para align=left><font size=10>%s</font></para>''' % (quotation.address + "  " + qunit)), "",
         "", "", ""],
        ["", Paragraph('''<para align=left><font size=10>%s</font></para>''' % (quotation.address + "  " + qunit)), "",
         "", "", Paragraph('''<para align=left><font size=10>Pc No: %s</font></para>''' % (pc.pc_no))],
        ["", "", "", "", "",
         Paragraph('''<para align=left><font size=10>Project No.: %s</font></para>''' % (project.proj_id))],
        # ["", "", "", "", "",
        #  Paragraph('''<para align=left><font size=10>Remarks.: %s</font></para>''' % (project.proj_id))],
        [Paragraph('''<para align=left><font size=10><b>Attn :</b></font></para>'''), Paragraph(
            '''<para align=left><font size=10>%s</font></para>''' % (
                    project.contact_person.salutation + " " + project.contact_person.contact_person)),
         Paragraph('''<para align=left><font size=10><b>Email :</b></font></para>'''),
         Paragraph('''<para align=left><font size=10>%s</font></para>''' % (project.email)), "",
         Paragraph('''<para align=left><font size=10>Sales: %s</font></para>''' % (qsale_person))],
        [Paragraph('''<para align=left><font size=10><b>Tel :</b></font></para>'''),
         Paragraph('''<para align=left><font size=10>%s</font></para>''' % (project.tel)),
         Paragraph('''<para align=left><font size=10><b>Fax :</b></font></para>'''),
         Paragraph('''<para align=left><font size=10>%s</font></para>''' % (project.fax)), "",
         Paragraph('''<para align=left><font size=10>Terms: %s Days</font></para>''' % (qterms))],
        ["", "", "", "", "", Paragraph('''<para align=left><font size=10>PO No.: %s</font></para>''' % (qpo_no))],
        [Paragraph('''<para align=left><font size=10><b>Project:</b></font></para>'''),
         Paragraph('''<para align=left><font size=10>%s</font></para>''' % (project.RE)), "", "", "", Paragraph(
            '''<para align=left><font size=10>Date Prepared: %s</font></para>''' % (pc.date.strftime("%d/%m/%Y")))],
        ["", "", "", "", "",
         Paragraph('''<para align=left><font size=10>Prog. Claim No: %s</font></para>''' % (claimno))],
    ]
    pcintable = Table(
        pcindata,
        style=[
            ('VALIGN', (-1, 0), (-1, 0), 'TOP'),
            ('ALIGN', (-1, 0), (-1, 0), 'CENTER'),
            ('SPAN', (-1, 0), (-1, 1)),
            ('SPAN', (3, 4), (4, 4)),
            ('SPAN', (1, 7), (4, 7)),
            ('SPAN', (1, 2), (4, 2)),
            ('SPAN', (1, 1), (4, 1)),
        ],
    )
    pcintable._argW[0] = 0.7 * inch
    pcintable._argW[1] = 1.28 * inch
    pcintable._argW[2] = 0.7 * inch
    pcintable._argW[3] = 1.28 * inch
    pcintable._argW[4] = 4.568 * inch
    pcintable._argW[5] = 2.27 * inch
    pcintable._argH[0] = 0.2 * inch
    pcintable._argH[1] = 0.2 * inch
    pcintable._argH[2] = 0.2 * inch
    pcintable._argH[3] = 0.2 * inch
    pcintable._argH[4] = 0.2 * inch
    pcintable._argH[5] = 0.2 * inch
    pcintable._argH[6] = 0.2 * inch
    pcintable._argH[7] = 0.2 * inch
    pcintable._argH[8] = 0.2 * inch
    story.append(pcintable)
    story.append(Spacer(1, 10))
    pc_data = [
        [Paragraph('''<para align=center><font size=10><b>S/N</b></font></para>'''),
         Paragraph('''<para align=center><font size=10><b>Description</b></font></para>'''),
         Paragraph('''<para align=center><font size=10><b>QTY</b></font></para>'''),
         Paragraph('''<para align=center><font size=10><b>UOM</b></font></para>'''),
         Paragraph('''<para align=center><font size=10><b>Percentage</b></font></para>'''),
         Paragraph('''<para align=center spaceb=2><font size=10><b>Unit Rate</b></font></para>'''),
         Paragraph(
             '''<para align=center spaceb=2><font size=10><b>Sub</b></font><br/><font size=10><b>Amount</b></font></para>'''),
         Paragraph('''<para align=center><font size=10><b>Current Claim</b></font></para>'''), "",
         Paragraph('''<para align=center><font size=10><b>Cumulative Claim</b></font></para>'''), ""
         ],
        ["", "", "", "", "", "", "",
         Paragraph(
             '''<para align=center spaceb=2><font size=10><b>Work Done</b></font><br/><font size=10><b>(Qty)</b></font></para>'''),
         Paragraph('''<para align=center><font size=10><b>Total Amount</b></font></para>'''),
         Paragraph(
             '''<para align=center spaceb=2><font size=10><b>Work Done</b></font><br/><font size=10><b>(Qty)</b></font></para>'''),
         Paragraph('''<para align=center><font size=10><b>Total Amount</b></font></para>''')
         ],
    ]
    total_pcworkdone_qty = 0
    if len(pc_data) < 4:
        story.append(PageBreak())
        story.append(Spacer(1, 15))
    style_sign = ParagraphStyle(name='left', fontSize=10, parent=styleSheet['Normal'])
    if pc.less_previous_claim:
        less_previous_claim = pc.less_previous_claim
        pccurrent = Table(
            [
                [Paragraph('''<para align=left><font size=10><b>Current Claim Amount:</b></font></para>'''), Paragraph(
                    '''<para align=left><font size=10>%s</font></para>''' % (
                            "$ " + '%.2f' % (total_pcworkdone_qty * 1.08)))],
                [Paragraph('''<para align=left><font size=10><b>Less Previous Claim:</b></font></para>'''), Paragraph(
                    '''<para align=left><font size=10>%s</font></para>''' % (
                            "$ " + '%.2f' % float(less_previous_claim)))]
            ],
            style=[
                ('VALIGN', (0, 0), (1, 0), 'MIDDLE'),
                ('ALIGN', (0, 0), (1, 0), 'LEFT'),
            ],
        )
    else:
        less_previous_claim = ""
        pccurrent = Table(
            [
                [Paragraph('''<para align=left><font size=10><b>Current Claim Amount:</b></font></para>'''), Paragraph(
                    '''<para align=left><font size=10>%s</font></para>''' % (
                            "$ " + '%.2f' % (total_pcworkdone_qty * 1.08)))],
                [Paragraph('''<para align=left><font size=10><b>Less Previous Claim:</b></font></para>'''),
                 Paragraph('''<para align=left><font size=10>%s</font></para>''' % (""))]
            ],
            style=[
                ('VALIGN', (0, 0), (1, 0), 'MIDDLE'),
                ('ALIGN', (0, 0), (1, 0), 'LEFT'),
            ],
        )
    pccurrent._argW[0] = 1.888 * inch
    pccurrent._argW[1] = 8.9 * inch
    story.append(pccurrent)
    story.append(Spacer(1, 10))
    sign_title1 = '''
        <para align=left>
            <font size=10><b>Signature: </b></font>
        </para>
    '''
    sign_title2 = '''
        <para align=left>
            <font size=10><b>Signature: </b></font>
        </para>
    '''
    if request.user.signature:
        sign_logo = Image('http://' + domain + request.user.signature.url, width=0.8 * inch, height=0.8 * inch,
                          hAlign='LEFT')
    else:
        sign_logo = ""
        # sign_logo = Image('http://' + domain + '/static/assets/images/logo.png', hAlign='LEFT')
    pctable1 = Table(
        [
            [Paragraph('''<para align=left><font size=12><b>Prepared By:</b></font></para>'''), "", "",
             Paragraph('''<para align=left><font size=12><b>Certified By:</b></font></para>''')],
        ],
        style=[
            ('VALIGN', (0, 0), (0, -1), 'TOP'),
        ],
    )
    pctable1._argW[0] = 2.394 * inch
    pctable1._argW[1] = 2.50 * inch
    pctable1._argW[2] = 2.50 * inch
    pctable1._argW[3] = 3.394 * inch
    story.append(pctable1)
    pctable2 = Table(
        [
            [Paragraph('''<para align=left><font size=9><b>Name:</b></font></para>'''),
             Paragraph('''<para align=left><font size=9>%s</font></para>''' % (request.user.first_name)), "",
             Paragraph('''<para align=left><font size=9><b>Name:</b></font></para>'''),
             Paragraph('''<para align=left><font size=9></font></para>''')]
        ],
        style=[
            ('VALIGN', (0, 0), (0, -1), 'TOP'),
        ],
    )
    pctable2._argW[0] = 0.8 * inch
    pctable2._argW[1] = 2.994 * inch
    pctable2._argW[2] = 3.6 * inch
    pctable2._argW[3] = 0.8 * inch
    pctable2._argW[4] = 2.594 * inch
    story.append(Spacer(1, 10))
    story.append(pctable2)
    if pc.uploaded_by:
        if pc.uploaded_by.signature:
            auto_sign = Image('http://' + domain + pc.uploaded_by.signature.url, hAlign='LEFT')
        else:
            auto_sign = ""
            # auto_sign = Image('http://' + domain + '/static/assets/images/logo.png', hAlign='LEFT')
    else:
        auto_sign = ""
        # auto_sign = Image('http://' + domain + '/static/assets/images/logo.png', hAlign='LEFT')
    pctable3 = Table(
        [
            [Paragraph(sign_title1, style_sign), "", "", Paragraph(sign_title2, style_sign), ""],
            ["", sign_logo, "", "", ""]
        ],
        style=[
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('SPAN', (3, 1), (4, -1)),
        ],
    )
    story.append(Spacer(1, 10))
    pctable3._argW[0] = 1.0 * inch
    pctable3._argW[1] = 2.794 * inch
    pctable3._argW[2] = 3.6 * inch
    pctable3._argW[3] = 1.0 * inch
    pctable3._argW[4] = 2.394 * inch
    story.append(pctable3)

    doc.build(story, canvasmaker=LandScapeNumberedCanvas)
    response.write(buff.getvalue())
    buff.close()

    return response


def exportDoPDF(request, value):
    do = Do.objects.get(id=value)
    project = do.project
    quotation = project.quotation
    doitems = DoItem.objects.filter(do_id=value)
    # domain = request.META['HTTP_HOST']
    domain = os.getenv("DOMAIN")
    logo = Image('http://' + domain + '/static/assets/images/printlogo.png', hAlign='LEFT')
    response = HttpResponse(content_type='application/pdf')
    currentdate = date.today().strftime("%d-%m-%Y")
    pdfname = do.do_no + ".pdf"
    response['Content-Disposition'] = 'attachment; filename="{}"'.format(pdfname)

    story = []
    data = [
        [Paragraph('''<para align=center><font size=10><b>S/N</b></font></para>'''),
         Paragraph('''<para align=center><font size=10><b>Description</b></font></para>'''),
         Paragraph('''<para align=center><font size=10><b>UOM</b></font></para>'''),
         Paragraph('''<para align=center><font size=10><b>QTY</b></font></para>''')],
    ]
    buff = BytesIO()
    doc = SimpleDocTemplate(buff, pagesize=portrait(A4), rightMargin=0.25 * inch, leftMargin=0.45 * inch,
                            topMargin=3.5 * inch, bottomMargin=3.1 * inch, title=pdfname)

    if doitems.exists():
        index = 1
        for doitem in doitems:
            temp_data = []
            description = '''
                <para align=left>
                    %s
                </para>
            ''' % (str(doitem.description))
            pddes = Paragraph(description)
            temp_data.append(str(index))
            temp_data.append(pddes)
            temp_data.append(str(doitem.uom))
            temp_data.append(str(doitem.qty))
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
                ('ALIGN', (1, 1), (1, -1), 'LEFT'),
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
    if do.remarks:
        remarks = do.remarks
    else:
        remarks = ""

    remark_data=[[Paragraph('''<para><font size=10><b>Remarks: </b></font></para>'''),
                  Paragraph('''<para><font size=9>%s</font></para>'''% (str(remarks).replace('\n','<br />\n')))]]
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

    doc.build(story, canvasmaker=NumberedCanvas, onFirstPage=partial(header, do=do, value=value, domain=domain), onLaterPages=partial(header, do=do, value=value, domain=domain))

    response.write(buff.getvalue())
    buff.close()
    return response



# Function to split the text into lines
def split_text(text, max_length):
    words = text.split(' ')
    lines = []
    current_line = ""
    for word in words:
        if len(current_line) + len(word) + 1 <= max_length:
            if current_line:
                current_line += " " + word
            else:
                current_line = word
        else:
            lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)
    return lines

# Header for Do
def header(canvas, doc, do, value, domain):
    RIGHT_X = 370
    CONTENT_PADDING=10
    LEFT_X_1 = 40
    LEFT_X_2 = 90
    LEFT_X_3 = 220
    LEFT_X_4 = 250
    LEFT_X_5 = 300
    TOP_MARGIN = 130
    LINE_SPACE = 15
    MAX_LINE_LENGTH=50

    canvas.saveState()
    project = do.project
    quotation = project.quotation
    if do.date:
        dodate = do.date.strftime('%d/%m/%Y')
    else:
        dodate = " "
    if quotation.sale_person:
        qsale_person = quotation.sale_person
    else:
        qsale_person = ""
    if quotation.terms:
        qterms = str(quotation.terms) + " Days"
    else:
        qterms = ""
    if quotation.po_no:
        qpo_no = quotation.po_no
    else:
        qpo_no = ""

    canvas.setFont("Helvetica-Bold", 16)
    canvas.drawString(RIGHT_X+20, canvas.PAGE_HEIGHT - TOP_MARGIN, "DELIVERY ORDER")
    canvas.setFont("Helvetica-Bold", 10)
    canvas.drawString(RIGHT_X, canvas.PAGE_HEIGHT - TOP_MARGIN - LINE_SPACE, "DO No: ")
    canvas.drawString(RIGHT_X, canvas.PAGE_HEIGHT - TOP_MARGIN - 2 * LINE_SPACE, "Project No: ")
    canvas.drawString(RIGHT_X, canvas.PAGE_HEIGHT - TOP_MARGIN - 3 * LINE_SPACE, "Date: ")
    canvas.drawString(RIGHT_X, canvas.PAGE_HEIGHT - TOP_MARGIN - 4 * LINE_SPACE, "Sales: ")
    canvas.drawString(RIGHT_X, canvas.PAGE_HEIGHT - TOP_MARGIN - 5 * LINE_SPACE, "Terms: ")
    canvas.drawString(RIGHT_X, canvas.PAGE_HEIGHT - TOP_MARGIN - 6 * LINE_SPACE, "PO No: ")
    canvas.setFont("Helvetica", 10)
    canvas.drawString(RIGHT_X+4*CONTENT_PADDING, canvas.PAGE_HEIGHT - TOP_MARGIN - LINE_SPACE, "%s" % (do.do_no))
    canvas.drawString(RIGHT_X+6*CONTENT_PADDING, canvas.PAGE_HEIGHT - TOP_MARGIN - 2 * LINE_SPACE, "%s" % (project.proj_id))
    canvas.drawString(RIGHT_X+4*CONTENT_PADDING, canvas.PAGE_HEIGHT - TOP_MARGIN - 3 * LINE_SPACE, "%s" % (dodate))
    canvas.drawString(RIGHT_X+4*CONTENT_PADDING, canvas.PAGE_HEIGHT - TOP_MARGIN - 4 * LINE_SPACE, "%s" % (qsale_person))
    canvas.drawString(RIGHT_X+4*CONTENT_PADDING, canvas.PAGE_HEIGHT - TOP_MARGIN - 5 * LINE_SPACE, "%s" % (qterms))
    canvas.drawString(RIGHT_X+4*CONTENT_PADDING, canvas.PAGE_HEIGHT - TOP_MARGIN - 6 * LINE_SPACE, "%s" % (qpo_no))

    bill_to1=project.company_nameid
    if Quotation.objects.filter(qtt_id__iexact=project.qtt_id).exists():
        quotation = Quotation.objects.get(qtt_id__iexact=project.qtt_id)
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
    else:
        address = ""
        qunit = ""
        country = ""
        postalcode = ""
    if do.ship_to:
        shipto = do.ship_to
    else:
        shipto = ""
    if do.remarks:
        remarks = do.remarks
    else:
        remarks = ""
    canvas.setFont("Helvetica-Bold", 10)
    canvas.drawString(LEFT_X_1, canvas.PAGE_HEIGHT - TOP_MARGIN + 2, "Bill To: ")
    canvas.drawString(LEFT_X_1, canvas.PAGE_HEIGHT - TOP_MARGIN - 4 * LINE_SPACE, "Ship To:  ")
    canvas.drawString(LEFT_X_1, canvas.PAGE_HEIGHT - TOP_MARGIN - 6 * LINE_SPACE, "Attn:  ")
    canvas.drawString(LEFT_X_3, canvas.PAGE_HEIGHT - TOP_MARGIN - 6 * LINE_SPACE, "Tel:  ")
    canvas.drawString(LEFT_X_1, canvas.PAGE_HEIGHT - TOP_MARGIN - 7 * LINE_SPACE, "Subject: ")
    # canvas.drawString(LEFT_X_1, canvas.PAGE_HEIGHT - TOP_MARGIN - 7 * LINE_SPACE, "Remarks: ")

    canvas.setFont("Helvetica", 10)
    canvas.drawString(LEFT_X_2, canvas.PAGE_HEIGHT - TOP_MARGIN + 2, "%s" % (bill_to1))


    # Split the text into lines
    lines = split_text(address+" "+qunit, MAX_LINE_LENGTH)
    # Draw the text, line by line
    y_position = canvas.PAGE_HEIGHT - TOP_MARGIN - LINE_SPACE
    for line in lines:
        canvas.drawString(LEFT_X_2, y_position, "%s" % (line))
        y_position -= LINE_SPACE  # Move down for the next line

    canvas.drawString(LEFT_X_2, canvas.PAGE_HEIGHT - TOP_MARGIN - 3 * LINE_SPACE, "%s %s" % (country, postalcode))
    shiptoobject = canvas.beginText(LEFT_X_2, canvas.PAGE_HEIGHT - TOP_MARGIN - 4 * LINE_SPACE)
    for line in shipto.splitlines(False):
        shiptoobject.textLine(line.rstrip())
    canvas.drawText(shiptoobject)
    canvas.drawString(LEFT_X_2, canvas.PAGE_HEIGHT - TOP_MARGIN - 6 * LINE_SPACE, "%s" % (project.contact_person.salutation + " " + project.contact_person.contact_person))
    canvas.drawString(LEFT_X_4, canvas.PAGE_HEIGHT - TOP_MARGIN - 6 * LINE_SPACE, "%s" % (project.tel))
    # canvas.drawString(LEFT_X_2, canvas.PAGE_HEIGHT - TOP_MARGIN - 6 * LINE_SPACE, "%s" % (project.RE))
    subjectobject = canvas.beginText(LEFT_X_2, canvas.PAGE_HEIGHT - TOP_MARGIN - 7 * LINE_SPACE)
    for line in project.RE.splitlines(False):
        subjectobject.textLine(line.rstrip())
    canvas.drawText(subjectobject)

    dosignature = DOSignature.objects.filter(do_id=value)
    if dosignature.exists():
        dosign_data = DOSignature.objects.get(do_id=value)
        sign_name = dosign_data.name
        sign_nric = dosign_data.nric
        sign_date = dosign_data.update_date.strftime('%d/%m/%Y')
        sign_logo = ImageReader('http://' + domain + dosign_data.signature_image.url)
        sign_string=sign_name + "/" + sign_nric + "/" + sign_date
    else:
        sign_name = ""
        sign_nric = ""
        sign_date = ""
        sign_logo = ""
        sign_string = ""
    if do.created_by:
        if do.created_by.signature:
            auto_sign = ImageReader('http://' + domain + do.created_by.signature.url)
        else:
            auto_sign = ""
    else:
        auto_sign = ""

    canvas.setFont("Helvetica", 9)
    canvas.drawString(LEFT_X_1, canvas.PAGE_HEIGHT - TOP_MARGIN - 33 * LINE_SPACE,
                      "%s" % ("Received the above Goods in Good Order & Condition."))
    canvas.drawString(LEFT_X_1, canvas.PAGE_HEIGHT - TOP_MARGIN - 34 * LINE_SPACE, "%s" % (
        "Please be informed that unless payment is received in full, CNI Technology Pte Ltd will remain as the rightful owner of the delivered"))
    canvas.drawString(LEFT_X_1, canvas.PAGE_HEIGHT - TOP_MARGIN - 35 * LINE_SPACE,
                      "%s" % ("equipment(s)/material(s) on site."))

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
    MAX_LINE_LENGTH = 60

    canvas.saveState()

    project = sr.project
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
    canvas.drawString(RIGHT_X, canvas.PAGE_HEIGHT - TOP_MARGIN - 3 * LINE_SPACE, "Project No: ")
    canvas.drawString(RIGHT_X, canvas.PAGE_HEIGHT - TOP_MARGIN - 4 * LINE_SPACE, "Time In: ")
    canvas.drawString(RIGHT_X, canvas.PAGE_HEIGHT - TOP_MARGIN - 5 * LINE_SPACE, "Time Out: ")
    canvas.setFont("Helvetica", 10)
    canvas.drawString(RIGHT_X+3*CONTENT_PADDING, canvas.PAGE_HEIGHT - TOP_MARGIN - LINE_SPACE, "%s" % (sr.sr_no))
    canvas.drawString(RIGHT_X+3*CONTENT_PADDING, canvas.PAGE_HEIGHT - TOP_MARGIN - 2 * LINE_SPACE, "%s" % (sr.date.strftime('%d/%m/%Y')))
    canvas.drawString(RIGHT_X+3*CONTENT_PADDING, canvas.PAGE_HEIGHT - TOP_MARGIN - 3 * LINE_SPACE, "%s" % (project.proj_id))
    canvas.drawString(RIGHT_X+3*CONTENT_PADDING, canvas.PAGE_HEIGHT - TOP_MARGIN - 4 * LINE_SPACE, "%s" % (time_in))
    canvas.drawString(RIGHT_X+3*CONTENT_PADDING, canvas.PAGE_HEIGHT - TOP_MARGIN - 5 * LINE_SPACE, "%s" % (time_out))

    canvas.setFont("Helvetica-Bold", 10)
    canvas.drawString(LEFT_X_1, canvas.PAGE_HEIGHT - TOP_MARGIN + 2, "To: ")
    canvas.drawString(LEFT_X_1, canvas.PAGE_HEIGHT - TOP_MARGIN - 4 * LINE_SPACE, "Attn:")
    canvas.drawString(LEFT_X_3, canvas.PAGE_HEIGHT - TOP_MARGIN - 4 * LINE_SPACE, "Email:")
    canvas.drawString(LEFT_X_1, canvas.PAGE_HEIGHT - TOP_MARGIN - 5 * LINE_SPACE, "Tel:")
    canvas.drawString(LEFT_X_3, canvas.PAGE_HEIGHT - TOP_MARGIN - 5 * LINE_SPACE, "Fax:")
    canvas.drawString(LEFT_X_1, canvas.PAGE_HEIGHT - TOP_MARGIN - 6 * LINE_SPACE, "Worksite:")
    canvas.drawString(LEFT_X_1, canvas.PAGE_HEIGHT - TOP_MARGIN - 8 * LINE_SPACE, "Service Type:")
    canvas.drawString(LEFT_X_1, canvas.PAGE_HEIGHT - TOP_MARGIN - 9 * LINE_SPACE, "System:")
    canvas.drawString(LEFT_X_1, canvas.PAGE_HEIGHT - TOP_MARGIN - 10 * LINE_SPACE, "Purpose:")
    canvas.drawString(LEFT_X_1, canvas.PAGE_HEIGHT - TOP_MARGIN - 11 * LINE_SPACE, "Subject:")
    canvas.setFont("Helvetica", 10)
    canvas.drawString(LEFT_X_2, canvas.PAGE_HEIGHT - TOP_MARGIN + 2, "%s" % (quotation.company_nameid))
    
    # Split the text into lines
    lines = split_text(address+" "+qunit, MAX_LINE_LENGTH)
    # Draw the text, line by line
    y_position = canvas.PAGE_HEIGHT - TOP_MARGIN - LINE_SPACE
    for line in lines:
        canvas.drawString(LEFT_X_2, y_position, "%s" % (line))
        y_position -= LINE_SPACE  # Move down for the next line

    canvas.drawString(LEFT_X_2, canvas.PAGE_HEIGHT - TOP_MARGIN - 3 * LINE_SPACE, "%s %s" % (country, postalcode))

    canvas.drawString(LEFT_X_2, canvas.PAGE_HEIGHT - TOP_MARGIN - 4 * LINE_SPACE, "%s" % (project.contact_person.salutation + " " + project.contact_person.contact_person))
    test_email=wrap(project.email, 25)
    t=canvas.beginText(LEFT_X_4, canvas.PAGE_HEIGHT - TOP_MARGIN - 4 * LINE_SPACE)
    t.textLines(test_email)
    canvas.drawText(t)
    canvas.drawString(LEFT_X_2, canvas.PAGE_HEIGHT - TOP_MARGIN - 5 * LINE_SPACE, "%s" % (project.tel))
    canvas.drawString(LEFT_X_4, canvas.PAGE_HEIGHT - TOP_MARGIN - 5 * LINE_SPACE, "%s" % (project.fax))
    canvas.drawString(LEFT_X_2, canvas.PAGE_HEIGHT - TOP_MARGIN - 6 * LINE_SPACE, "%s" % (worksite_address))
    canvas.drawString(LEFT_X_2+20, canvas.PAGE_HEIGHT - TOP_MARGIN - 8 * LINE_SPACE, "%s" % (srtype))
    canvas.drawString(LEFT_X_2, canvas.PAGE_HEIGHT - TOP_MARGIN - 9 * LINE_SPACE, "%s" % (srsystem))
    canvas.drawString(LEFT_X_2, canvas.PAGE_HEIGHT - TOP_MARGIN - 10 * LINE_SPACE, "%s" % (srpurpose))

    canvas.drawString(LEFT_X_2, canvas.PAGE_HEIGHT - TOP_MARGIN - 11 * LINE_SPACE, "%s" % (project.RE))
    # remarksobject = canvas.beginText(LEFT_X_2, canvas.PAGE_HEIGHT - TOP_MARGIN - 11 * LINE_SPACE)
    # for line in srremark.splitlines(False):
    #     remarksobject.textLine(line.rstrip())
    # canvas.drawText(remarksobject)


    srsignature = SRSignature.objects.filter(sr_id=value)

    if srsignature.exists():
        srsign_data = SRSignature.objects.get(sr_id=value)
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
        # self.domain = settings.HOST_NAME
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


class LandScapeNumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []
        self.PAGE_HEIGHT = defaultPageSize[0]
        self.PAGE_WIDTH = defaultPageSize[1]
        self.domain = os.getenv('DOMAIN')
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
        self.drawString(150, self.PAGE_HEIGHT - 50, "CNI TECHNOLOGYPTE LTD")
        self.setFont("Helvetica", 10)
        self.drawString(150, self.PAGE_HEIGHT - 65, "Block 3023 Ubi Road 3, #02-15 Ubi Plex 1, Singapore 408663")
        self.drawString(150, self.PAGE_HEIGHT - 80, "Tel.6747 6169 Fax.7647 5669")
        self.drawString(150, self.PAGE_HEIGHT - 95, "RCB No.201318779M")
        self.setFont("Times-Roman", 9)
        self.drawRightString(self.PAGE_WIDTH / 2.0 + 10, 0.35 * inch,
                             "Page %d of %d" % (self._pageNumber, page_count))




@method_decorator(login_required, name='dispatch')
class ScheduleView(ListView):
    model = Project
    template_name = "projects/schedule-overview.html"
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        current_date = datetime.now(pytz.timezone(os.getenv("TIME_ZONE")))
        projects = Project.objects.filter(proj_status="On-going")
        context['proj_nos'] = projects
        return context
@ajax_login_required
def get_planning_table(request):
    if request.method == "POST":
        project_no = request.POST.get('project_no')
        start_date = request.POST.get('start_date')
        start_date=datetime.strptime(start_date, '%d/%m/%Y')
        activities=[]
        if project_no is not None:
            project=Project.objects.get(proj_id=project_no)
            activities=Scope.objects.filter(quotation_id=project.quotation.id, parent_id__isnull=True).order_by('id')
        qtys=[[],[],[],[],[],[],[],[]]
        shifts=[]
        users=[[],[],[],[],[],[],[],[]]
        for date_id in range(0,8):
            plan_date = start_date + timedelta(days=date_id)
            for act_id, activity in enumerate(activities):
                if ActivitySchedule.objects.filter(scope_id=activity.id, date=plan_date).exists():
                    act_schedule=ActivitySchedule.objects.get(scope_id=activity.id, date=plan_date)
                    qtys[date_id].append(act_schedule.qty)
                else:
                    qtys[date_id].append(0)

            if ScheduleUsers.objects.filter(project_id=project.id, date=plan_date).exists():
                schedule_users = ScheduleUsers.objects.filter(project_id=project.id, date=plan_date)
                for s_user in schedule_users:
                    users[date_id].append(s_user.user)
                shifts.append(schedule_users[0].shift)
            else:
                users[date_id].append("")
                shifts.append("")
        return render(request, 'projects/ajax-planning-list.html', {'start_date': start_date, 'activities':activities, 'qtys':qtys , 'shifts': shifts, 'users': users})

@ajax_login_required
def get_overview_table(request):
    if request.method == "POST":
        view_unit = request.POST.get('view_unit')
        start_date = request.POST.get('start_date')
        start_date=datetime.strptime(start_date, '%d/%m/%Y')
        if view_unit=="Week":
            periods=7
        else:
            periods=31
        schedule_projects=[]
        total_user_cnt = User.objects.filter(role__in=["Workers", "Supervisors"]).exclude(status_id=2).count()
        assigned_cnts=[]
        balanced_cnts=[]
        max_cnt=0
        for date_id in range(0, periods):
            plan_date = start_date + timedelta(days=date_id)
            assigned_users=ScheduleUsers.objects.filter(date=plan_date).values('user_id').distinct()
            assigned_user_cnts=User.objects.filter(id__in=assigned_users,role__in=["Workers", "Supervisors"]).exclude(status_id=2).count()
            assigned_cnts.append(assigned_user_cnts)
            balanced_cnt=total_user_cnt-assigned_user_cnts
            balanced_cnts.append(balanced_cnt)

            schedules=ScheduleUsers.objects.filter(date=plan_date).values('project_id', 'shift').distinct()
            for schedule in schedules:
                project=Project.objects.get(id=schedule['project_id'])
                schedule['project']=project
                scopes=Scope.objects.filter(quotation_id=project.quotation_id, parent_id__isnull=True)
                activity_schedules=ActivitySchedule.objects.filter(date=plan_date,scope__in=scopes).values('scope', 'qty')
                for activity in activity_schedules:
                    scope_description=Scope.objects.get(id=activity['scope'], parent_id__isnull=True).description
                    activity['scope']=scope_description
                schedule['activities']=activity_schedules
                assigned_user_ids=ScheduleUsers.objects.filter(date=plan_date, project_id=schedule['project_id']).values('user_id')
                assigned_users=User.objects.filter(id__in=assigned_user_ids)
                schedule['users']=assigned_users
                schedule['user_cnt']=len(assigned_users)
            if len(schedules)>max_cnt:
                max_cnt=len(schedules)
            schedule_projects.append(schedules)

        # print("===========", schedule_projects)
        return render(request, 'projects/ajax-overview-list.html', {'start_date': start_date, 'max_cnt':max_cnt, 'assigned_cnts':assigned_cnts,'balanced_cnts':balanced_cnts,'schedule_projects':schedule_projects})

@ajax_login_required
def get_planning_modal(request):
    if request.method == "POST":
        project_no = request.POST.get('project_no')
        start_date = request.POST.get('start_date')
        start_date=datetime.strptime(start_date, '%d/%m/%Y')
        activities=[]
        if project_no is not None:
            project=Project.objects.get(proj_id=project_no)
            activities=Scope.objects.filter(quotation_id=project.quotation.id, parent_id__isnull=True).order_by('id')
            teams=Team.objects.filter(project_id=project.id)

        return render(request, 'projects/ajax-planning-modal.html', {'start_date': start_date, 'activities':activities, 'teams': teams})

@ajax_login_required
def get_overview_modal(request):
    if request.method == "POST":
        project_id = request.POST.get('project_id')
        plan_date = request.POST.get('plan_date')
        plan_date=datetime.strptime(plan_date, '%d/%m/%Y')
        activities=[]
        project=Project.objects.get(id=project_id)
        scopes=Scope.objects.filter(quotation_id=project.quotation_id, parent_id__isnull=True)
        activity_schedules=ActivitySchedule.objects.filter(date=plan_date,scope__in=scopes).values('scope', 'qty')
        for activity in activity_schedules:
            scope_description=Scope.objects.get(id=activity['scope'], parent_id__isnull=True).description
            activity['scope']=scope_description
            activities.append(activity)

        return render(request, 'projects/ajax-overview-modal.html', {'activities':activities})

@ajax_login_required
def edit_planning_modal(request):
    if request.method == "POST":
        project_no = request.POST.get('project_no')
        start_date = request.POST.get('start_date')
        start_date=datetime.strptime(start_date, '%d/%m/%Y')
        activities=[]
        if project_no is not None:
            project=Project.objects.get(proj_id=project_no)
            activities=Scope.objects.filter(quotation_id=project.quotation.id, parent_id__isnull=True).order_by('id')
            teams=Team.objects.filter(project_id=project.id)
        qtys = [[], [], [], [], [], [], [], []]
        shifts = []
        users = [[], [], [], [], [], [], [], []]
        for date_id in range(0, 8):
            plan_date = start_date + timedelta(days=date_id)
            for act_id, activity in enumerate(activities):
                if ActivitySchedule.objects.filter(scope_id=activity.id, date=plan_date).exists():
                    act_schedule = ActivitySchedule.objects.get(scope_id=activity.id, date=plan_date)
                    qtys[date_id].append(act_schedule.qty)
                else:
                    qtys[date_id].append(0)

            if ScheduleUsers.objects.filter(project_id=project.id, date=plan_date).exists():
                schedule_users = ScheduleUsers.objects.filter(project_id=project.id, date=plan_date)
                for s_user in schedule_users:
                    user_id=s_user.user.id
                    user_name=s_user.user.username
                    users[date_id].append({"user_id":user_id, "user_name":user_name})
                shifts.append(schedule_users[0].shift)
            else:
                users[date_id].append("")
                shifts.append("Day")
        return render(request, 'projects/ajax-edit-planning-modal.html', {'start_date': start_date, 'activities':activities, 'teams': teams, 'qtys':qtys , 'edit_shifts': shifts, 'edit_users': users})
@ajax_login_required
def get_activity_ids(request):
    if request.method == "POST":
        project_no = request.POST.get('project_no')
        if project_no is not None:
            project=Project.objects.get(proj_id=project_no)
            activities=Scope.objects.filter(quotation_id=project.quotation.id, parent_id__isnull=True).order_by('id')
            data=[]
            for activity in activities:
                activity_id = {
                    "activity_id": activity.id
                }
                data.append(activity_id)

        return JsonResponse(json.dumps(data), safe=False)
@ajax_login_required
def add_activities(request):
    if request.method == "POST":
        is_edit = request.POST.get('is_edit')
        project_no = request.POST.get('project_no')
        start_date = request.POST.get('start_date')
        start_date = datetime.strptime(start_date, '%d/%m/%Y')
        plans = request.POST.get('plans')
        team_users = request.POST.get('team_users')
        plans=eval(plans)
        team_users=eval(team_users)
        if project_no is not None:
            project=Project.objects.get(proj_id=project_no)
            activities=Scope.objects.filter(quotation_id=project.quotation.id, parent_id__isnull=True).order_by('id')
            try:
                for act_id, activity in enumerate(activities):
                    for date_id in range(0,8):
                        scope_id=activity.id
                        plan_date=start_date+timedelta(days=date_id)
                        proj_users=team_users[date_id]
                        shift=plans[date_id][-1]
                        qty=plans[date_id][act_id]

                        if ActivitySchedule.objects.filter(scope_id=scope_id, date=plan_date).exists():
                            # if is_edit=="-1": # For new adding
                            #     return JsonResponse({
                            #         "status": "Error",
                            #         "messages": "Schedule already Exists in %s. please select start date again."%(plan_date.strftime("%d/%B/%Y"))
                            #     })
                            # else: # For edit
                            activity_schedule=ActivitySchedule.objects.get(scope_id=scope_id, date=plan_date)
                            activity_schedule.qty=int(qty)
                            activity_schedule.save()
                            ScheduleUsers.objects.filter(project_id=project.id, date=plan_date).delete()
                            for user_id in proj_users:
                                ScheduleUsers.objects.create(
                                    project_id=project.id,
                                    user_id=user_id,
                                    shift=shift,
                                    date=plan_date,
                                )
                        else:
                            activity_schedule = ActivitySchedule.objects.create(
                                scope_id=scope_id,
                                qty=int(qty),
                                date=plan_date,
                            )
                            ScheduleUsers.objects.filter(project_id=project.id, date=plan_date).delete()
                            for user_id in proj_users:
                                ScheduleUsers.objects.create(
                                    project_id=project.id,
                                    user_id=user_id,
                                    shift=shift,
                                    date=plan_date,
                                )

                return JsonResponse({
                    "status": "Success",
                    "messages": "Schedule was successfully added!"
                })
            except IntegrityError as e:
                return JsonResponse({
                    "status": "Error",
                    "messages": "Error occured!"
                })


@method_decorator(login_required, name='dispatch')
class AllProjectListView(ListView):
    model = Project
    template_name = "projects/all-projects-list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['companys'] = Company.objects.all()

        return context


@ajax_login_required
def ajax_all_projects(request):
    if request.method == "POST":

        projects = Project.objects.all()
        sales=ProductSales.objects.all()
        maintenance=Maintenance.objects.all()

        data_list=[]
        for project in projects:
            data={}
            data['proj_no']=project.proj_id
            data['customer']=project.company_nameid
            data['subject']=project.RE
            if project.quotation:
                data['sales_type']=project.quotation.sale_type
            else:
                data['sales_type'] =""
            data['status']=project.proj_status
            data['url']="project_summary_detail"
            data['proj_id']=project.id
            data_list.append(data)
        for project in sales:
            data={}
            data['proj_no']=project.prod_sale_id
            data['customer']=project.company_nameid
            data['subject']=project.RE
            if project.quotation:
                data['sales_type'] = project.quotation.sale_type
            else:
                data['sales_type'] = ""
            data['status']=project.sales_status
            data['url']="sales_summary_detail"
            data['proj_id']=project.id
            data_list.append(data)
        for project in maintenance:
            data={}
            data['proj_no']=project.main_no
            data['customer']=project.company_nameid
            data['subject']=project.RE
            if project.quotation:
                data['sales_type'] = project.quotation.sale_type
            else:
                data['sales_type'] = ""
            data['status']=project.main_status
            data['url']="maintenance_detail"
            data['proj_id']=project.id
            data_list.append(data)


        return render(request, 'projects/ajax-all-projects.html', {'projects': data_list})



@ajax_login_required
def ajax_do_items(request):
    if request.method == "POST":
        item_cnt = request.POST.get('item_cnt')
        quotation_id = request.POST.get('quotation_id')
        project_item_all = Scope.objects.filter(quotation_id=quotation_id, parent_id__isnull=True)
        return render(request, 'projects/ajax-do-items.html',
                      {'project_item_all': project_item_all, 'item_cnt': item_cnt, 'quotation_id':quotation_id})


@ajax_login_required
def ajax_sr_items(request):
    if request.method == "POST":
        item_cnt = request.POST.get('item_cnt')
        quotation_id = request.POST.get('quotation_id')
        project_item_all = Scope.objects.filter(quotation_id=quotation_id, parent_id__isnull=True)
        return render(request, 'projects/ajax-sr-items.html',
                      {'project_item_all': project_item_all, 'item_cnt': item_cnt, 'quotation_id':quotation_id})
