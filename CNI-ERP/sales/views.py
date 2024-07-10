import base64
import smtplib
import textwrap
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate
from functools import partial

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core import serializers
from django.core.files.base import ContentFile
from django.shortcuts import render
from django.http.response import HttpResponse
from django.utils.decorators import method_decorator
from django.views.generic.list import ListView

from sales.models import ProductSales, Company, Payment, Quotation, SaleReport, SaleReportComment, Contact, Scope, \
    Signature, QFile, \
    Validity, ProductSalesDo, ProductSalesDoItem, SalesDOSignature, ParentSubject, Position, Salutation
from cities_light.models import Country
from accounts.models import Privilege, Uom, User, Role, NotificationPrivilege
from django.http import JsonResponse
from django.db import IntegrityError
import json
from sales.decorater import ajax_login_required, sale_report_privilege_required
from datetime import date
from django.views.generic.detail import DetailView
import datetime
import pytz
from reportlab.platypus import SimpleDocTemplate, Table, Image, Spacer, TableStyle, PageBreak, Paragraph, Frame, \
    PageTemplate
from reportlab.lib import colors
from reportlab.lib.units import inch, cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from io import BytesIO
from reportlab.lib.pagesizes import A4, landscape, portrait
from reportlab.pdfgen import canvas
from reportlab.rl_config import defaultPageSize
from reportlab.lib.utils import ImageReader
import xlwt
from project.models import Project, Do, ProjectFile, Bom, Team, Sr, Pc, DoItem, DOSignature
from maintenance.models import Maintenance
import time
from notifications.signals import notify
from django.db.models import Sum
from decimal import Decimal
from sales.resources import CompanyResource, ContactResource
import pandas as pd
import os
from django.db.models import Q

from siteprogress.models import SiteProgress
from toolbox.models import ToolBoxDescription, ToolBoxItem, ToolBoxObjective
from textwrap import wrap


@method_decorator(login_required, name='dispatch')
class SalesSummaryView(ListView):
    model = ProductSales
    template_name = "sales/sales-summary/sales-summary-list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['sales_nos'] = ProductSales.objects.all().order_by('prod_sale_id').values('prod_sale_id').distinct()
        context['customers'] = ProductSales.objects.all().order_by('company_nameid').values('company_nameid').distinct()
        context['quotations'] = ProductSales.objects.all().order_by('quotation').values('quotation').distinct()

        # context['contacts'] = User.objects.all()
        # context['date_years'] = list(set([d.start_date.year for d in Project.objects.all()]))
        #
        # current_year = datetime.datetime.today().year
        # if current_year in list(set([d.start_date.year for d in Project.objects.all()])):
        #     context['exist_current_year'] = True
        # else:
        #     context['exist_current_year'] = False
        return context


@ajax_login_required
def ajax_summarys(request):
    if request.method == "POST":
        product_sales = ProductSales.objects.all()

        return render(request, 'sales/sales-summary/ajax-sales.html', {'product_sales': product_sales})


@method_decorator(login_required, name='dispatch')
class SalesDetailView(DetailView):
    model = ProductSales
    template_name = "sales/sales-summary/sales-detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        content_pk = self.kwargs.get('pk')
        summary = ProductSales.objects.get(id=content_pk)
        context['companies'] = Company.objects.all()
        context['summary'] = summary
        context['sale_pk'] = content_pk
        context['contacts'] = Contact.objects.all()
        context['contact_users'] = User.objects.all()
        context['uoms'] = Uom.objects.all()
        context['dolist'] = ProductSalesDo.objects.filter(product_sales=content_pk)
        quotation = summary.quotation
        projectitems = Scope.objects.filter(quotation_id=quotation.id, parent=None)
        subtotal = 0
        for obj in projectitems:
            obj.childs = Scope.objects.filter(quotation_id=quotation.id, parent_id=obj.id)
            obj.cumulativeqty = \
                SiteProgress.objects.filter(project_id=content_pk, description__iexact=obj.description).aggregate(
                    Sum('qty'))['qty__sum']

            # if obj.allocation_perc and obj.cumulativeqty:
            #     obj.cumulativeperc = float(obj.cumulativeqty / obj.qty) * float(obj.allocation_perc)
            # else:
            #     obj.cumulativeperc = 0
            # obj.cumulativeqty = 0
            obj.cumulativeperc = 0
            if obj.childs.count() != 0:
                tempObjperc = float(obj.allocation_perc) / obj.childs.count()
            for subobj in obj.childs:
                subobj.cumulativeqty = \
                    SiteProgress.objects.filter(project_id=content_pk,
                                                description__iexact=subobj.description).aggregate(
                        Sum('qty'))['qty__sum']

                if subobj.allocation_perc and subobj.cumulativeqty:
                    subobj.cumulativeperc = float(subobj.cumulativeqty / subobj.qty) * float(subobj.allocation_perc)
                else:
                    subobj.cumulativeperc = 0
                obj.cumulativeperc += tempObjperc * subobj.cumulativeperc / 100

            subtotal += obj.cumulativeperc

        # subtotal = 0
        # for allobj in Scope.objects.filter(quotation_id=quotation.id):
        #     allobj.cumulativeqty = \
        #         SiteProgress.objects.filter(project_id=content_pk, description__iexact=allobj.description).aggregate(
        #             Sum('qty'))['qty__sum']
        #     if allobj.allocation_perc and allobj.cumulativeqty:
        #         allobj.cumulativeperc = float(allobj.cumulativeqty / allobj.qty) * float(allobj.allocation_perc)
        #     else:
        #         allobj.cumulativeperc = 0
        #     subtotal = subtotal + allobj.cumulativeperc

        context['projectitems'] = projectitems
        context['projectitemall'] = Scope.objects.filter(quotation_id=quotation.id)
        context['quotation_pk'] = quotation.id
        context['subtotal'] = subtotal
        projectitemactivitys = Scope.objects.filter(quotation_id=quotation.id)
        context['projectitemactivitys'] = projectitemactivitys
        return context


@ajax_login_required
def doadd(request):
    if request.method == "POST":
        do_no = request.POST.get('do_no')
        date = request.POST.get('dodate')
        if date == "":
            date = None
        product_sales_id = request.POST.get('projectid')
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
                    do = ProductSalesDo.objects.create(
                        do_no=do_no,
                        date=date,
                        status="Open",
                        created_by_id=request.user.id,
                        product_sales_id=product_sales_id,
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
                do = ProductSalesDo.objects.get(id=doid)
                do.do_no = do_no
                do.date = date
                do.created_by_id = request.user.id
                do.status = "Open"
                do.upload_by_id = request.user.id
                do.product_sales_id = product_sales_id
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


@method_decorator(login_required, name='dispatch')
class DoDetailView(DetailView):
    model = ProductSalesDo
    pk_url_kwarg = 'dopk'
    template_name = "sales/sales-summary/delivery-order-detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        proj_pk = self.kwargs.get('pk')
        do_pk = self.kwargs.get('dopk')
        summary = ProductSales.objects.get(id=proj_pk)
        context['summary'] = summary
        context['project_pk'] = proj_pk
        context['delivery_pk'] = do_pk
        delivery_order = ProductSalesDo.objects.get(id=do_pk)
        context['contacts'] = User.objects.all()
        context['uoms'] = Uom.objects.all()
        context['companies'] = Company.objects.all()
        context['delivery_order'] = delivery_order
        quotation = summary.quotation
        context['doitems'] = ProductSalesDoItem.objects.filter(product_sales=proj_pk, do_id=do_pk)
        context['quotation'] = quotation
        if (SalesDOSignature.objects.filter(product_sales=proj_pk, do_id=do_pk).exists()):
            context['dosignature'] = SalesDOSignature.objects.get(product_sales=proj_pk, do_id=do_pk)
        else:
            context['dosignature'] = None
        context['projectitemall'] = Scope.objects.filter(quotation_id=quotation.id)
        return context


@ajax_login_required
def doItemAdd(request):
    if request.method == "POST":
        description = request.POST.get('description')
        qty = request.POST.get('qty')
        uom = request.POST.get('uom')
        uom = Uom.objects.get(name=uom)
        doitemid = request.POST.get('doitemid')
        product_sales_id = request.POST.get('projectid')
        doid = request.POST.get('doid')

        if doitemid == "-1":
            try:
                ProductSalesDoItem.objects.create(
                    description=description,
                    qty=qty,
                    uom=uom,
                    product_sales_id=product_sales_id,
                    do_id=doid
                )
                return JsonResponse({
                    "status": "Success",
                    "messages": "Delivery Order Item information added!"
                })
            except IntegrityError as e:
                return JsonResponse({
                    "status": "Error",
                    "messages": "Already DO Item is existed!"
                })
        else:
            try:
                doitem = ProductSalesDoItem.objects.get(id=doitemid)
                doitem.description = description
                doitem.qty = qty
                doitem.uom = uom
                doitem.product_sales_id = product_sales_id
                doitem.do_id = doid
                doitem.save()

                return JsonResponse({
                    "status": "Success",
                    "messages": "Delivery Order Item information updated!"
                })

            except IntegrityError as e:
                return JsonResponse({
                    "status": "Error",
                    "messages": "Already DO Item is existed!"
                })


@ajax_login_required
def getDoItem(request):
    if request.method == "POST":
        doitemid = request.POST.get('doitemid')
        doitem = ProductSalesDoItem.objects.get(id=doitemid)
        data = {
            'description': doitem.description,
            'qty': doitem.qty,
            'uom': doitem.uom_id,
        }
        return JsonResponse(json.dumps(data), safe=False)


@ajax_login_required
def deleteDOItem(request):
    if request.method == "POST":
        doitem_del_id = request.POST.get('del_id')
        doitem = ProductSalesDoItem.objects.get(id=doitem_del_id)
        doitem.delete()

        return JsonResponse({'status': 'ok'})


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
                                      name='delivery-sign-' + datetime.date.today().strftime("%d-%m-%Y") + "." + ext)
        if deliveryid == "-1":
            try:
                SalesDOSignature.objects.create(
                    name=name,
                    nric=nric,
                    update_date=date,
                    signature=signature,
                    do_id=doid,
                    product_sales_id=projectid,
                    signature_image=signature_image
                )
                salesDo = ProductSalesDo.objects.get(id=doid)
                if salesDo.status != "Signed":
                    # notification send
                    sender = User.objects.filter(role="Managers").first()
                    is_email = NotificationPrivilege.objects.get(user_id=sender.id).is_email

                    description = '<a href="/sales-detail/' + str(
                        projectid) + '/delivery-order-detail/' + str(
                        salesDo.id) + '">Project Do No : {0} Status updated from {1} to Signed</a>'.format(
                        salesDo.do_no, salesDo.status)
                    for receiver in User.objects.filter(Q(role='Managers')).distinct():
                        if receiver.notificationprivilege.do_status:
                            notify.send(sender, recipient=receiver, verb='Message', level="success",
                                        description=description)
                            if is_email and receiver.email:
                                send_mail(receiver.email, "Notification for Do Status : ", description)
                salesDo.status = "Signed"
                salesDo.save()
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
                dosignature = SalesDOSignature.objects.get(id=deliveryid)
                dosignature.name = name
                dosignature.nric = nric
                dosignature.update_date = date
                dosignature.signature = signature
                dosignature.do_id = doid
                dosignature.product_sales_id = projectid
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
        dosignature = SalesDOSignature.objects.get(id=deliveryid)
        data = {
            'name': dosignature.name,
            'nric': dosignature.nric,
            'date': dosignature.update_date.strftime('%d %b, %Y'),
            'signature': dosignature.signature
        }
        return JsonResponse(json.dumps(data), safe=False)


@ajax_login_required
def dodocadd(request):
    if request.method == "POST":
        product_sales_id = request.POST.get('projectid')
        dodocid = request.POST.get('dodocid')
        try:
            do = ProductSalesDo.objects.get(id=dodocid)
            do.upload_by_id = request.user.id
            do.product_sales_id = product_sales_id
            if request.FILES.get('document'):
                do.document = request.FILES.get('document')
                if do.status != "Signed":
                    # notification send
                    sender = User.objects.filter(role="Managers").first()
                    is_email = NotificationPrivilege.objects.get(user_id=sender.id).is_email

                    description = '<a href="/sales-detail/' + str(
                        product_sales_id) + '/delivery-order-detail/' + str(
                        do.id) + '">Project Do No : {0} Status updated from {1} to Signed</a>'.format(
                        do.do_no, do.status)
                    for receiver in User.objects.filter(Q(role='Managers')).distinct():
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
def UpdateDeliveryOrder(request):
    if request.method == "POST":
        company_nameid = request.POST.get('company_nameid')
        address = request.POST.get('address')
        attn = request.POST.get('attn')
        tel = request.POST.get('tel')
        shipto = request.POST.get('shipto')
        # product_sales_id = request.POST.get('proj_id')
        doid = request.POST.get('doid')
        remarks = request.POST.get('remarks')

        try:
            delivery = ProductSalesDo.objects.get(id=doid)
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


@ajax_login_required
def deleteDo(request):
    if request.method == "POST":
        dodel_id = request.POST.get('dodel_id')
        dodata = ProductSalesDo.objects.get(id=dodel_id)
        doitem = ProductSalesDoItem.objects.filter(do=dodel_id)
        dosign = SalesDOSignature.objects.filter(do=dodel_id)
        doitem.delete()
        dosign.delete()
        dodata.delete()

        return JsonResponse({'status': 'ok'})


@ajax_login_required
def UpdateSummary(request):
    if request.method == "POST":

        company_nameid = request.POST.get('company_nameid')
        worksite_address = request.POST.get('worksite_address')
        contact_person = request.POST.get('contact_person')
        email = request.POST.get('email')
        tel = request.POST.get('tel')
        fax = request.POST.get('fax')
        RE = request.POST.get('re')
        proj_id = request.POST.get('proj_id')
        qtt_id = request.POST.get('qtt_id')
        # latitude = request.POST.get('latitude')
        # longitude = request.POST.get('longitude')
        note = request.POST.get('note')
        summaryid = request.POST.get('summaryid')
        status = request.POST.get('sales_status')

        try:
            summary = ProductSales.objects.get(id=summaryid)

            summary.company_nameid_id = company_nameid
            summary.worksite_address = worksite_address
            summary.contact_person_id = contact_person
            summary.email = email
            summary.tel = tel
            summary.fax = fax
            summary.qtt_id = qtt_id
            summary.proj_id = proj_id
            summary.note = note
            summary.RE = RE
            summary.sales_status = status
            summary.save()

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
def ajax_summarys_filter(request):
    if request.method == "POST":
        search_sales_no = request.POST.get('search_sales_no')
        quotation = request.POST.get('quotation')
        search_customer = request.POST.get('search_customer')
        product_sales = ProductSales.objects.all()
        if search_sales_no != "":
            product_sales = product_sales.filter(prod_sale_id__iexact=search_sales_no)
        if quotation != "":
            product_sales = product_sales.filter(quotation=quotation)
        if search_customer != "":
            product_sales = product_sales.filter(company_nameid=search_customer)

        return render(request, 'sales/sales-summary/ajax-sales.html', {'product_sales': product_sales})


@ajax_login_required
def summarydelete(request):
    if request.method == "POST":
        summaryid = request.POST.get('summaryid')
        summary = ProductSales.objects.get(id=summaryid)
        summary.delete()

        return JsonResponse({'status': 'ok'})


# Create your views here.
@method_decorator(login_required, name='dispatch')
class CompanyList(ListView):
    model = Company
    template_name = "sales/company/company-list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['countrys'] = Country.objects.all()
        context['companies'] = Company.objects.order_by('name').values('name').distinct()

        return context


@ajax_login_required
def contactCompanyAdd(request):
    if request.method == "POST":
        name = request.POST.get('name')
        address = request.POST.get('address')
        unit = request.POST.get('unit')
        postalcode = request.POST.get('postalcode')
        country = request.POST.get('country')
        associate = request.POST.get('associate')
        comid = request.POST.get('comid')
        try:
            company = Company.objects.create(
                name=name,
                address=address,
                unit=unit,
                postal_code=postalcode,
                country_id=country,
                associate=associate,
            )
            return JsonResponse({
                "status": "Success",
                "messages": "Company information added!",
                'companyid': company.id,
                'companyname': company.name
            })
        except IntegrityError as e:
            return JsonResponse({
                "status": "Error",
                "messages": "Already this Company is existed!"
            })


@ajax_login_required
def ajax_export_company(request):
    resource = CompanyResource()
    dataset = resource.export()
    response = HttpResponse(dataset.csv, content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="company.csv"'
    return response


def ajax_import_company(request):
    if request.method == 'POST':
        org_column_names = ["name", "address", "unit", "postal_code", "associate"]

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
                exist_count = Company.objects.filter(name=row["name"]).count()
                if exist_count == 0:
                    try:
                        company = Company(
                            name=row["name"],
                            address=row["address"],
                            unit=row["unit"],
                            postal_code=row["postal_code"],
                            associate=row["associate"],
                        )
                        company.save()
                        success_record += 1
                    except Exception as e:
                        print(e)
                        failed_record += 1
                else:
                    try:
                        company = Company.objects.filter(name=row["name"])[0]
                        company.name = row["name"]
                        company.address = row["address"]
                        company.unit = str(row["unit"])
                        company.postal_code = row["postal_code"]
                        company.associate = row["part_number"]

                        company.save()
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


def ajax_export_contact(request):
    resource = ContactResource()
    dataset = resource.export()
    response = HttpResponse(dataset.csv, content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="contact.csv"'
    return response


def ajax_import_contact(request):
    if request.method == 'POST':
        org_column_names = ["contact_person", "tel", "fax", "email", "role"]

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
                exist_count = Contact.objects.filter(contact_person=row["contact_person"]).count()
                if exist_count == 0:
                    try:
                        contact = Contact(
                            contact_person=row["contact_person"],
                            tel=row["tel"],
                            fax=row["fax"],
                            email=row["email"],
                            role=row["role"],
                        )
                        contact.save()
                        success_record += 1
                    except Exception as e:
                        print(e)
                        failed_record += 1
                else:
                    try:
                        contact = Contact.objects.filter(contact_person=row["contact_person"])[0]
                        contact.contact_person = row["contact_person"]
                        contact.tel = row["tel"]
                        contact.fax = row["fax"]
                        contact.email = row["email"]
                        contact.role = row["role"]

                        contact.save()
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
def companyadd(request):
    if request.method == "POST":
        name = request.POST.get('name')
        address = request.POST.get('address')
        unit = request.POST.get('unit')
        postalcode = request.POST.get('postalcode')
        country = request.POST.get('country')
        associate = request.POST.get('associate')
        comid = request.POST.get('comid')
        if comid == "-1":
            try:
                company = Company.objects.create(
                    name=name,
                    address=address,
                    unit=unit,
                    postal_code=postalcode,
                    country_id=country,
                    associate=associate,
                    payment_id=Payment.objects.all().order_by('id')[0].id,
                    validity_id=Validity.objects.all().order_by('id')[3].id
                )
                return JsonResponse({
                    "status": "Success",
                    "messages": "Company information added!",
                    "companyId": company.id
                })
            except IntegrityError as e:
                return JsonResponse({
                    "status": "Error",
                    "messages": "Already this Company is existed!"
                })
        else:
            try:
                company = Company.objects.get(id=comid)
                company.name = name
                company.address = address
                company.unit = unit
                company.postal_code = postalcode
                company.country_id = country
                company.associate = associate
                company.payment_id = Payment.objects.all().order_by('id')[0].id
                company.validity_id = Validity.objects.all().order_by('id')[3].id
                company.save()

                return JsonResponse({
                    "status": "Success",
                    "messages": "Company information updated!",
                    "companyId": company.id
                })

            except IntegrityError as e:
                print(e)
                return JsonResponse({
                    "status": "Error",
                    "messages": "Error is existed!"
                })


@ajax_login_required
def ajax_companys(request):
    if request.method == "POST":
        companys = Company.objects.all()

        return render(request, 'sales/company/ajax-company.html', {'companys': companys})


@ajax_login_required
def ajax_companys_filter(request):
    if request.method == "POST":
        company = request.POST.get('company')
        search_country = request.POST.get('search_country')
        associate_filter = request.POST.get('associate_filter')
        if company != "" and search_country == "" and associate_filter == "":
            companys = Company.objects.filter(name__iexact=company)

        elif company != "" and search_country != "" and associate_filter == "":
            companys = Company.objects.filter(name__iexact=company, country_id=search_country)

        elif company != "" and search_country != "" and associate_filter != "":
            companys = Company.objects.filter(name__iexact=company, country_id=search_country,
                                              associate__iexact=associate_filter)

        elif company == "" and search_country != "" and associate_filter == "":
            companys = Company.objects.filter(country_id=search_country)

        elif company == "" and search_country != "" and associate_filter != "":
            companys = Company.objects.filter(country_id=search_country, associate__iexact=associate_filter)

        elif company == "" and search_country == "" and associate_filter != "":
            companys = Company.objects.filter(associate__iexact=associate_filter)

        elif company != "" and search_country == "" and associate_filter != "":
            companys = Company.objects.filter(name__iexact=company, associate__iexact=associate_filter)

        return render(request, 'sales/company/ajax-company.html', {'companys': companys})


@ajax_login_required
def getCompany(request):
    if request.method == "POST":
        comid = request.POST.get('comid')
        company = Company.objects.get(id=comid)
        data = {
            'name': company.name,
            'address': company.address,
            'unit': company.unit,
            'postalcode': company.postal_code,
            'country': company.country_id,
            'associate': company.associate,

        }
        return JsonResponse(json.dumps(data), safe=False)


@ajax_login_required
def companydelete(request):
    if request.method == "POST":
        com_id = request.POST.get('com_id')
        company = Company.objects.get(id=com_id)
        contact = Contact.objects.filter(company=com_id)
        contact.delete()
        company.delete()
        return JsonResponse({'status': 'ok'})


@method_decorator(login_required, name='dispatch')
class ContactList(ListView):
    model = Contact
    template_name = "sales/contact/contact-list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['companys'] = Company.objects.all().order_by('name')
        context['emails'] = Contact.objects.order_by('email').values('email').distinct()
        context['roles'] = Contact.objects.order_by('role').values('role').distinct()
        context['countrys'] = Country.objects.all()
        if self.request.user.role == "Managers" or self.request.user.is_staff == True:
            context['contact_persons'] = Contact.objects.order_by('contact_person').values('contact_person').distinct()

        else:
            context['contact_persons'] = Contact.objects.filter(created_by=self.request.user.username).order_by(
                'contact_person').values('contact_person').distinct()

        context['positions'] = Position.objects.all()
        context['salutations'] = Salutation.objects.all()
        return context


@ajax_login_required
def contactadd(request):
    if request.method == "POST":
        contactperson = request.POST.get('contactperson')
        salutation = request.POST.get('salutation')
        tel = request.POST.get('tel')
        did = request.POST.get('did')
        mobile = request.POST.get('mobile')
        fax = request.POST.get('fax')
        email = request.POST.get('email')
        role = request.POST.get('role')
        company = request.POST.get('company')
        conid = request.POST.get('conid')
        created_by = request.POST.get('created_by')

        if conid == "-1":
            try:
                Contact.objects.create(
                    contact_person=contactperson,
                    salutation=salutation,
                    tel=tel,
                    did=did,
                    mobile=mobile,
                    fax=fax,
                    email=email,
                    role=role,
                    company_id=company,
                    created_by=created_by
                )
                return JsonResponse({
                    "status": "Success",
                    "messages": "Contact information added!"
                })
            except IntegrityError as e:
                return JsonResponse({
                    "status": "Error",
                    "messages": "Already this Contact is existed!"
                })
        else:
            try:
                contact = Contact.objects.get(id=conid)
                contact.contact_person = contactperson
                contact.salutation = salutation
                contact.tel = tel
                contact.did = did
                contact.mobile = mobile
                contact.fax = fax
                contact.email = email
                contact.role = role
                contact.company_id = company
                contact.created_by = created_by
                contact.save()

                return JsonResponse({
                    "status": "Success",
                    "messages": "Contact information updated!"
                })

            except IntegrityError as e:
                print(e)
                return JsonResponse({
                    "status": "Error",
                    "messages": "Error is existed!"
                })


@ajax_login_required
def ajax_contacts(request):
    if request.method == "POST":
        user_role = request.POST.get('user_role')
        user_name = request.POST.get('user_name')
        if user_role == "Managers":
            contacts = Contact.objects.all()
        else:
            contacts = Contact.objects.filter(created_by=user_name)

        return render(request, 'sales/contact/ajax-contact.html', {'contacts': contacts})


@ajax_login_required
def ajax_qtt_items(request):
    if request.method == "POST":
        uoms = Uom.objects.all()
        item_cnt = request.POST.get('item_cnt')
        scopes = Scope.objects.filter(parent=None)
        descriptions = Scope.objects.filter(parent=None).order_by(
            'description').values('description', 'id').distinct()

        return render(request, 'sales/quotation/ajax-quotation-items.html',
                      {'uoms': uoms, 'item_cnt': item_cnt, 'scopes': scopes, 'descriptions': descriptions})


@ajax_login_required
def ajax_check_scopes(request):
    if request.method == "POST":
        quotation_id = request.POST.get('quotation_id')
        if Scope.objects.filter(quotation_id=quotation_id, parent=None).exists():
            data = {
                'scope_cnt': 1,
            }
        else:
            data = {
                "scope_cnt": 0,
            }
        return JsonResponse(json.dumps(data), safe=False)


@ajax_login_required
def ajax_contacts_filter(request):
    if request.method == "POST":
        contact_person = request.POST.get('contact_person')
        search_email = request.POST.get('search_email')
        role_filter = request.POST.get('role_filter')
        user_role = request.POST.get('user_role')
        user_name = request.POST.get('user_name')
        if user_role == "Managers":
            contacts = Contact.objects.all()
        else:
            contacts = Contact.objects.filter(created_by=user_name)

        if contact_person != "":
            contacts = contacts.filter(contact_person__iexact=contact_person)

        if search_email != "":
            contacts = contacts.filter(email=search_email)

        if role_filter != "":
            contacts = contacts.filter(role__iexact=role_filter)

        return render(request, 'sales/contact/ajax-contact.html', {'contacts': contacts})


@ajax_login_required
def getContact(request):
    if request.method == "POST":
        conid = request.POST.get('conid')
        contact = Contact.objects.get(id=conid)
        data = {
            'contact_person': str(contact.contact_person),
            'salutation': contact.salutation,
            'tel': contact.tel,
            'fax': contact.fax,
            'did': contact.did,
            'mobile': contact.mobile,
            'email': contact.email,
            'company': contact.company_id,
            'role': contact.role,

        }
        return JsonResponse(json.dumps(data), safe=False)


@ajax_login_required
def contactdelete(request):
    if request.method == "POST":
        con_id = request.POST.get('con_id')
        contact = Contact.objects.get(id=con_id)
        contact.delete()

        return JsonResponse({'status': 'ok'})


@method_decorator(login_required, name='dispatch')
class QuotationList(ListView):
    model = Quotation
    template_name = "sales/quotation/quotation-list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['contacts'] = Contact.objects.all().order_by('contact_person')
        context['companys'] = Company.objects.all().order_by('name')
        context['countrys'] = Country.objects.all()
        context['roles'] = Role.objects.all()
        if self.request.user.role == "Managers" or self.request.user.is_staff == True:
            context['qqtt_ids'] = Quotation.objects.order_by('qtt_id').values('qtt_id').distinct()
        else:
            context['qqtt_ids'] = Quotation.objects.filter(sale_person=self.request.user.username).order_by(
                'qtt_id').values('qtt_id').distinct()

        current_year = datetime.datetime.today().year
        if current_year in list(set([d.date.year for d in Quotation.objects.all()])):
            context['exist_current_year'] = True
        else:
            context['exist_current_year'] = False
        context['date_years'] = list(set([d.date.year for d in Quotation.objects.all()]))
        # context['customers'] = Quotation.objects.exclude(company_nameid=None).order_by('company_nameid').values(
        #     'company_nameid').distinct()

        context['customers'] = Company.objects.distinct().filter(
            quotation__in=Quotation.objects.exclude(company_nameid=None).order_by('company_nameid'))

        return context


@ajax_login_required
def check_quotation_number(request):
    if request.method == "POST":
        if Quotation.objects.all().exists():
            quotation = Quotation.objects.all().order_by('-qtt_id')[0]
            data = {
                "status": "exist",
                "quotation": quotation.qtt_id
            }

            return JsonResponse(data)
        else:
            data = {
                "status": "no exist"
            }

            return JsonResponse(data)


@ajax_login_required
def ajax_quotations(request):
    if request.method == "POST":
        user_name = request.POST.get('user_name')
        user_role = request.POST.get('user_role')
        current_year = datetime.datetime.today().year
        quotations = Quotation.objects.filter(date__iso_year=current_year)
        if user_role == "Sales":
            quotations = quotations.filter(sale_person=user_name)
        return render(request, 'sales/quotation/ajax-quotation.html', {'quotations': quotations})


@ajax_login_required
def ajax_quotations_filter(request):
    if request.method == "POST":
        search_quotation = request.POST.get('search_quotation')
        daterange = request.POST.get('daterange')
        user_name = request.POST.get('user_name')
        user_role = request.POST.get('user_role')
        if daterange:
            startdate = datetime.datetime.strptime(daterange.split()[0], '%Y.%m.%d').replace(tzinfo=pytz.utc)
            enddate = datetime.datetime.strptime(daterange.split()[2], '%Y.%m.%d').replace(tzinfo=pytz.utc)
        search_customer = request.POST.get('search_customer')
        search_year = request.POST.get('search_year')
        if search_year:
            if search_quotation != "" and daterange == "" and search_customer == "":
                quotations = Quotation.objects.filter(qtt_id__iexact=search_quotation, date__iso_year=search_year)

            elif search_quotation != "" and daterange != "" and search_customer == "":
                quotations = Quotation.objects.filter(qtt_id__iexact=search_quotation, date__gte=startdate,
                                                      date__lte=enddate, date__iso_year=search_year)

            elif search_quotation != "" and daterange != "" and search_customer != "":
                quotations = Quotation.objects.filter(qtt_id__iexact=search_quotation, date__gte=startdate,
                                                      date__lte=enddate, company_nameid_id=search_customer,
                                                      date__iso_year=search_year)

            elif search_quotation == "" and daterange != "" and search_customer == "":
                quotations = Quotation.objects.filter(date__gte=startdate, date__lte=enddate,
                                                      date__iso_year=search_year)

            elif search_quotation == "" and daterange != "" and search_customer != "":
                quotations = Quotation.objects.filter(date__gte=startdate, date__lte=enddate,
                                                      company_nameid_id=search_customer,
                                                      date__iso_year=search_year)

            elif search_quotation == "" and daterange == "" and search_customer != "":
                quotations = Quotation.objects.filter(company_nameid_id=search_customer)

            elif search_quotation != "" and daterange == "" and search_customer != "":
                quotations = Quotation.objects.filter(qtt_id__iexact=search_quotation,
                                                      company_nameid_id=search_customer,
                                                      date__iso_year=search_year)

            elif search_quotation == "" and daterange == "" and search_customer == "":
                quotations = Quotation.objects.filter(date__iso_year=search_year)

        else:

            if search_quotation != "" and daterange == "" and search_customer == "":
                quotations = Quotation.objects.filter(qtt_id__iexact=search_quotation)

            elif search_quotation != "" and daterange != "" and search_customer == "":
                quotations = Quotation.objects.filter(qtt_id__iexact=search_quotation, date__gte=startdate,
                                                      date__lte=enddate)

            elif search_quotation != "" and daterange != "" and search_customer != "":
                quotations = Quotation.objects.filter(qtt_id__iexact=search_quotation, date__gte=startdate,
                                                      date__lte=enddate, company_nameid_id=search_customer)

            elif search_quotation == "" and daterange != "" and search_customer == "":
                quotations = Quotation.objects.filter(date__gte=startdate, date__lte=enddate)

            elif search_quotation == "" and daterange != "" and search_customer != "":
                quotations = Quotation.objects.filter(date__gte=startdate, date__lte=enddate,
                                                      company_nameid_id=search_customer)

            elif search_quotation == "" and daterange == "" and search_customer != "":
                quotations = Quotation.objects.filter(company_nameid_id=search_customer)

            elif search_quotation != "" and daterange == "" and search_customer != "":
                quotations = Quotation.objects.filter(qtt_id__iexact=search_quotation,
                                                      company_nameid_id=search_customer)

            elif search_quotation == "" and daterange == "" and search_customer == "":
                quotations = Quotation.objects.all()

        if user_role == "Sales":
            quotations = quotations.filter(sale_person=user_name)
        return render(request, 'sales/quotation/ajax-quotation.html', {'quotations': quotations})


@ajax_login_required
def check_quotation_company(request):
    if request.method == "POST":
        company = request.POST.get('company')
        if Company.objects.filter(id=company).exists():
            company_info = Company.objects.get(id=company)
            contacts = Contact.objects.filter(company_id=company)
            contacts_data = serializers.serialize('json', list(contacts),
                                                  fields=('id', 'contact_person', 'tel', 'email', 'fax'))
            data = {
                "address": company_info.address,
                "unit": company_info.unit,
                "postalcode": company_info.postal_code,
                # "contact_person": company_info.contact_person,
                "country": company_info.country.name,
                "contacts": json.dumps(contacts_data),
            }
            return JsonResponse(data)


@ajax_login_required
def ajax_get_contact_person(request):
    if request.method == "POST":
        contact_id = request.POST.get('contact_id')
        if Contact.objects.filter(id=contact_id).exists():
            contact_info = Contact.objects.get(id=contact_id)
            data = {
                "tel": contact_info.tel,
                "email": contact_info.email,
                "fax": contact_info.fax,
            }
            return JsonResponse(data)


@ajax_login_required
def check_quotation_contact(request):
    if request.method == "POST":
        contact = request.POST.get('contact')
        if Contact.objects.filter(id=contact).exists():
            contact_info = Contact.objects.get(id=contact)
            data = {
                "tel": contact_info.tel,
                "fax": contact_info.fax,
                "email": contact_info.email
            }

            return JsonResponse(data)

        else:
            return JsonResponse({})


@ajax_login_required
def quotationadd(request):
    if request.method == "POST":
        qtt_id = request.POST.get('quotationno')
        address = request.POST.get('address')
        subject = request.POST.get('subject')
        contactperson = request.POST.get('contactperson')
        tel = request.POST.get('tel')
        fax = request.POST.get('fax')
        email = request.POST.get('email')
        company_nameid = request.POST.get('company')
        quotid = request.POST.get('quotid')
        sales_person = request.POST.get('sales_person')
        today = date.today()
        if quotid == "-1":
            if Quotation.objects.filter(qtt_id=qtt_id).exists():
                return JsonResponse({
                    "status": "Error",
                    "messages": "This id has been taken by others, please close current window and create again.",
                })
            else:
                try:
                    payment_id=Company.objects.get(id=company_nameid).payment_id
                    payment_method=Payment.objects.get(id=payment_id).method
                    validity_id=Company.objects.get(id=company_nameid).validity_id
                    validity_method=Validity.objects.get(id=validity_id).method

                    quotation = Quotation.objects.create(
                        qtt_id=qtt_id,
                        address=address,
                        RE=subject,
                        contact_person_id=contactperson,
                        tel=tel,
                        fax=fax,
                        date=today,
                        email=email,
                        company_nameid_id=company_nameid,
                        flag=True,
                        sale_person=sales_person,
                        terms=payment_method,
                        validity=validity_method,
                    )
                    return JsonResponse({
                        "status": "Success",
                        "messages": "Quotation information added!",
                        "quotationid": quotation.id,
                        "method": "add"
                    })
                except IntegrityError as e:
                    print(e)
                    return JsonResponse({
                        "status": "Error",
                        "messages": "The Same Quotation No already exist!"
                    })
        else:
            try:
                quotation = Quotation.objects.get(id=quotid)
                quotation.qtt_id = qtt_id
                quotation.address = address
                quotation.contact_person_id = contactperson
                quotation.tel = tel
                quotation.fax = fax
                quotation.email = email
                quotation.company_nameid_id = company_nameid
                quotation.RE = subject
                quotation.date = today
                quotation.save()

                return JsonResponse({
                    "status": "Success",
                    "messages": "Quotation information updated!",
                    "quotationid": quotation.id,
                    "method": "update"
                })

            except IntegrityError as e:
                return JsonResponse({
                    "status": "Error",
                    "messages": "The Same Quotation No already exist!"
                })


@ajax_login_required
def getQuotation(request):
    if request.method == "POST":
        quotid = request.POST.get('quotid')
        quotation = Quotation.objects.get(id=quotid)
        data = {
            'qtt_id': quotation.qtt_id,
            'address': quotation.address,
            'subject': quotation.note,
            'company_nameid': quotation.company_nameid.name,
            'contactperson': quotation.contact_person_id,
            'tel': quotation.tel,
            'fax': quotation.fax,
            'email': quotation.email,

        }
        return JsonResponse(json.dumps(data), safe=False)


@ajax_login_required
def quotationdelete(request):
    if request.method == "POST":
        quot_id = request.POST.get('quot_id')
        quotation = Quotation.objects.get(id=quot_id)
        quotation.delete()
        if Project.objects.filter(qtt_id__iexact=quotation.qtt_id).exists():
            project = Project.objects.get(qtt_id__iexact=quotation.qtt_id)
            project.delete()

        return JsonResponse({'status': 'ok'})


@ajax_login_required
def readnotify(request):
    if request.method == "POST":
        notifyid = request.POST.get('notifyid')
        request.user.notifications.get(id=notifyid).mark_as_read()

        return JsonResponse({'status': 'ok'})


@ajax_login_required
def unreadnotify(request):
    if request.method == "POST":
        notifyid = request.POST.get('notifyid')
        request.user.notifications.get(id=notifyid).mark_as_unread()

        return JsonResponse({'status': 'ok'})


@ajax_login_required
def removenotify(request):
    if request.method == "POST":
        notifyid = request.POST.get('notifyid')
        notification = request.user.notifications.get(id=notifyid)
        notification.delete()
        return JsonResponse({'status': 'ok'})


@ajax_login_required
def markUserNotificationsRead(request):
    if request.method == 'POST':
        user_id = request.POST['user_id']
        user = User.objects.get(pk=user_id)
        user.notifications.mark_all_as_read()

        return JsonResponse({'status': 'ok'})


@method_decorator(login_required, name='dispatch')
class QuotationDetailView(DetailView):
    model = Quotation
    template_name = "sales/quotation/quotation-detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        content_pk = self.kwargs.get('pk')
        quotation = Quotation.objects.get(id=content_pk)
        context['quotation'] = quotation
        context['quote'] = content_pk
        context['contacts'] = Contact.objects.all()
        context['companies'] = Company.objects.all()
        context['uoms'] = Uom.objects.all()
        context['validities'] = Validity.objects.all()
        data = []
        p_id = [p.id for p in Privilege.objects.all()]
        managers = User.objects.filter(role="Managers").exclude(id__in=p_id)
        if managers:
            data.append(managers)
        data.extend(User.objects.select_related('privilege'))
        context['salepersons'] = data
        # context['scope_list'] = Scope.objects.filter(quotation_id=content_pk, parent=None)
        scopes = Scope.objects.filter(quotation_id=content_pk, parent=None, subject__is_optional=None)
        if Scope.objects.filter(quotation_id=content_pk, parent=None, subject__is_optional=None).exists():
            subtotal = Scope.objects.filter(quotation_id=content_pk, parent=None, subject__is_optional=None).aggregate(Sum('amount'))[
                'amount__sum']
            total_gp = 0.0
            total_cost = 0.0
            for scope in scopes:
                total_gp += float(scope.gp)
                total_cost += float(scope.cost)
                if subtotal == 0:
                    scope.allocation_perc = 0
                else:
                    scope.allocation_perc = 100 * scope.amount / subtotal
                scope.save()
            context['scope_list'] = scopes
            gst = (float(subtotal) - float(quotation.discount)) * 0.09
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
            quotation.save()
        if Signature.objects.filter(quotation_id=content_pk).exists():
            context['signaturedata'] = Signature.objects.get(quotation_id=content_pk)
        else:
            context['signaturedata'] = []
        # Get project id and link
        project_id = ""
        link_id = ""
        project_type = ""
        if Project.objects.filter(quotation_id=content_pk):
            temp_project = Project.objects.filter(quotation_id=content_pk).order_by('-id')[0]
            project_id = temp_project.proj_id
            link_id = temp_project.id
            project_type = "Project"
        elif Maintenance.objects.filter(quotation_id=content_pk):
            temp_project = Maintenance.objects.filter(quotation_id=content_pk).order_by('-id')[0]
            project_id = temp_project.main_no
            link_id = temp_project.id
            project_type = "Maintenance"
        elif ProductSales.objects.filter(quotation_id=content_pk):
            temp_project = ProductSales.objects.filter(quotation_id=content_pk).order_by('-id')[0]
            project_id = temp_project.prod_sale_id
            link_id = temp_project.id
            project_type = "Sales"

        context['project_id'] = project_id
        context['link_id'] = link_id
        context['project_type'] = project_type

        context['file_list'] = QFile.objects.filter(quotation_id=content_pk)
        return context


@ajax_login_required
def qfileadd(request):
    if request.method == "POST":
        fname = request.POST.get('fname')
        fileid = request.POST.get('fileid')
        quotationid = request.POST.get('quotationid')

        if fileid == "-1":
            try:
                if request.FILES.get('document'):
                    QFile.objects.create(
                        name=fname,
                        user_id=request.user.id,
                        quotation_id=quotationid,
                        document=request.FILES.get('document')
                    )
                else:
                    QFile.objects.create(
                        name=fname,
                        user_id=request.user.id,
                        quotation_id=quotationid
                    )
                return JsonResponse({
                    "status": "Success",
                    "messages": "Quotation File information added!"
                })
            except IntegrityError as e:
                print(e)
                return JsonResponse({
                    "status": "Error",
                    "messages": "Quotation File Error!"
                })
        else:
            try:
                qfile = QFile.objects.get(id=fileid)
                qfile.name = fname
                if request.FILES.get('document'):
                    qfile.document = request.FILES.get('document')

                qfile.save()

                return JsonResponse({
                    "status": "Success",
                    "messages": "Quotation File information updated!"
                })

            except IntegrityError as e:
                return JsonResponse({
                    "status": "Error",
                    "messages": "Quotation File Error!"
                })


@ajax_login_required
def signaturesave(request):
    if request.method == "POST":
        sname = request.POST.get('sname')
        sdate = request.POST.get('sdate')
        quotationid = request.POST.get('quotationid')
        if Signature.objects.filter(quotation_id=quotationid).exists():
            try:
                signature = Signature.objects.get(quotation_id=quotationid)
                signature.signanture_name = sname
                signature.signature_date = sdate

                if request.FILES.get('companycamp') is not None:
                    signature.company_stamp = request.FILES.get('companycamp')
                else:
                    signature.company_stamp = ""

                c_user = User.objects.get(id=request.user.id)
                if request.FILES.get('signature') is not None:
                    c_user.signature = request.FILES.get('signature')
                    c_user.save()

                return JsonResponse({
                    "status": "Success",
                    "messages": "Signature information updated!"
                })

            except IntegrityError as e:
                return JsonResponse({
                    "status": "Error",
                    "messages": "Error is existed!"
                })
        else:
            try:
                obj = Signature(
                    signanture_name=sname,
                    signature_date=sdate,
                    quotation_id=quotationid,
                    company_stamp=request.FILES.get('companycamp')
                )
                obj.save()
                c_user = User.objects.get(id=request.user.id)
                if request.FILES.get('signature') is not None:
                    c_user.signature = request.FILES.get('signature')
                    c_user.save()

                return JsonResponse({
                    "status": "Success",
                    "messages": "Material Inventory information added!"
                })
            except IntegrityError as e:
                return JsonResponse({
                    "status": "Error",
                    "messages": "Error is existed!"
                })


@ajax_login_required
def scopeadd(request):
    if request.method == "POST":
        subject_id = request.POST.get('sub_id')
        items = json.loads(request.POST.get('items'))
        for item in items:
            sn = item.get('sn')
            qty = item.get('qty')
            uom = item.get('uom')
            description = item.get('description')
            unitprice = item.get('unitprice')
            unitcost = item.get('unitcost')
            quotationid = item.get('quotationid')
            scopeid = item.get('scopeid')
            qtt_id = item.get('qtt_id')
            is_optional=item.get('is_optional')

            if qty:
                pass
            else:
                qty = 0

            if unitprice:
                pass
            else:
                unitprice = 0

            if unitcost:
                pass
            else:
                unitcost = 0

            if scopeid == "-1":
                try:
                    if unitprice == 0 or qty == 0:
                        gp = 0
                    else:
                        gp = 100 * (float(qty) * float(unitprice) - float(unitcost) * float(qty)) / (
                                float(qty) * float(unitprice))
                    Scope.objects.create(
                        sn=sn,
                        qty=qty,
                        bal_qty=qty,
                        uom_id=uom,
                        description=description,
                        amount=Decimal(float(qty) * float(unitprice)),
                        unitprice=Decimal(unitprice),
                        unitcost=Decimal(unitcost),
                        cost=Decimal(float(unitcost) * float(qty)),
                        gp=Decimal(gp),
                        quotation_id=quotationid,
                        qtt_id=qtt_id,
                        subject_id=subject_id
                    )
                    if is_optional == '-1':
                        # subtotal = Scope.objects.filter(quotation_id=quotationid, parent=None).aggregate(Sum('amount'))[
                        #     'amount__sum']
                        # if subtotal == 0:
                        #     return JsonResponse({
                        #         "status": "Error",
                        #         "messages": "Subtotal should not be zero. please check unit price again."
                        #     })
                        if Scope.objects.filter(quotation_id=quotationid).exists():
                            subtotal = Scope.objects.filter(quotation_id=quotationid).aggregate(Sum('amount'))[
                                'amount__sum']
                            quotation = Quotation.objects.get(id=quotationid)
                            gst = (float(subtotal) - float(quotation.discount)) * 0.09
                            total_detail = float(subtotal) + gst
                            quotation.total = Decimal(total_detail)

                            final_total = float(subtotal) - float(quotation.discount) + gst
                            quotation.gst = gst
                            quotation.finaltotal = final_total
                            quotation.save()
                            if Scope.objects.filter(Q(quotation_id=quotationid), ~Q(qtt_id=None)).exists():
                                scope_temp = Scope.objects.filter(Q(quotation_id=quotationid), ~Q(qtt_id=None))[0]
                                if SaleReport.objects.filter(qtt_id__iexact=scope_temp.qtt_id).exists():
                                    salereport = SaleReport.objects.get(qtt_id__iexact=scope_temp.qtt_id)
                                    salereport.finaltotal = Decimal(total_detail)
                                    salereport.margin = Decimal(quotation.margin)
                                    salereport.save()

                except IntegrityError as e:
                    return JsonResponse({
                        "status": "Error",
                        "messages": "Already this Contact is existed!"
                    })
            else:
                try:
                    scope = Scope.objects.get(id=scopeid)
                    scope.sn = sn
                    scope.qty = qty
                    scope.bal_qty = qty
                    scope.uom_id = uom
                    scope.description = description
                    scope.amount = Decimal(float(qty) * float(unitprice))
                    scope.unitprice = Decimal(unitprice)
                    scope.unitcost = Decimal(unitcost)
                    scope.cost = Decimal(float(unitcost) * float(qty))
                    if float(unitprice) == 0.0 or float(qty) == 0:
                        scope.gp = 0
                    else:
                        scope.gp = (Decimal(
                            (float(qty) * float(unitprice)) - (float(unitcost) * float(qty)))) / Decimal(
                            (float(qty) * float(unitprice))) * 100
                    scope.quobtn_discountaddtation_id = quotationid
                    scope.qtt_id = qtt_id

                    # subtotal = Scope.objects.filter(quotation_id=quotationid, parent=None).aggregate(Sum('amount'))[
                    #     'amount__sum']
                    # if subtotal == 0:
                    #     return JsonResponse({
                    #         "status": "Error",
                    #         "messages": "Subtotal should not be zero. please check unit price again."
                    #     })
                    scope.save()
                    if is_optional == '-1':
                        if Scope.objects.filter(quotation_id=quotationid).exists():
                            subtotal = Scope.objects.filter(quotation_id=quotationid).aggregate(Sum('amount'))[
                                'amount__sum']
                            quotation = Quotation.objects.get(id=quotationid)
                            gst = (float(subtotal) - float(quotation.discount)) * 0.09
                            total_detail = float(subtotal) + gst
                            quotation.total = Decimal(total_detail)
                            quotation.save()
                            if Scope.objects.filter(Q(quotation_id=quotationid), ~Q(qtt_id=None)).exists():
                                scope_temp = Scope.objects.filter(Q(quotation_id=quotationid), ~Q(qtt_id=None))[0]
                                if SaleReport.objects.filter(qtt_id__iexact=scope_temp.qtt_id).exists():
                                    salereport = SaleReport.objects.get(qtt_id__iexact=scope_temp.qtt_id)
                                    salereport.finaltotal = Decimal(total_detail)
                                    salereport.margin = Decimal(quotation.margin)
                                    salereport.save()
                except IntegrityError as e:
                    print(e)
                    return JsonResponse({
                        "status": "Error",
                        "messages": "Error is existed!"
                    })
        return JsonResponse({
            "status": "Success",
            "messages": "Contact information added!"
        })


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        return json.JSONEncoder.default(self, obj)


@ajax_login_required
def ajax_filter_person(request):
    if request.method == "POST":
        company = request.POST.get('company')
        contacts = Contact.objects.filter(company_id=company)
        return render(request, 'sales/quotation/ajax-contact.html', {'contacts': contacts})


@ajax_login_required
def ajax_add_subject(request):
    if request.method == "POST":
        sub_id = request.POST.get('sub_id')
        subject_title = request.POST.get('title')
        quotation_id = request.POST.get('quotationid')
        if sub_id == "-1":
            try:
                ParentSubject.objects.create(
                    subject=subject_title,
                    quotation_id=quotation_id,
                )
            except IntegrityError as e:
                return JsonResponse({
                    "status": "Error",
                    "messages": "Already this Subject is existed!"
                })
            return JsonResponse({
                "status": "Success",
                "messages": "Subject created!"
            })
        else:
            try:
                subject = ParentSubject.objects.get(id=sub_id)
                subject.subject = subject_title
                subject.quotation_id = quotation_id
                subject.save()
            except IntegrityError as e:
                return JsonResponse({
                    "status": "Error",
                    "messages": "Already this Subject is existed!"
                })
            return JsonResponse({
                "status": "Success",
                "messages": "Subject created!"
            })

@ajax_login_required
def ajax_add_optional(request):
    if request.method == "POST":
        subject_title = request.POST.get('title')
        quotation_id = request.POST.get('quotationid')
        try:
            ParentSubject.objects.create(
                subject=subject_title,
                quotation_id=quotation_id,
                is_optional=True
            )
        except IntegrityError as e:
            return JsonResponse({
                "status": "Error",
                "messages": "Already this Optional is existed!"
            })
        return JsonResponse({
            "status": "Success",
            "messages": "Optional created!"})


@ajax_login_required
def ajax_add_discount(request):
    if request.method == "POST":
        discount = request.POST.get('discount')
        quotation_id = request.POST.get('quotationid')
        discount_id = request.POST.get('discount_id')
        try:
            scopes = Scope.objects.filter(quotation_id=quotation_id)
            total_gp = 0.0
            total_cost = 0.0
            for scope in scopes:
                total_cost += float(scope.cost)
                total_gp += float(scope.gp)
            quotation = Quotation.objects.get(id=quotation_id)
            if total_cost == 0:
                margin = 0
            else:
                margin = (float(quotation.total) - total_cost - float(quotation.discount)) * 100 / (
                        float(quotation.total) - float(quotation.discount))
            final_total = (float(quotation.total) - float(discount)) + float(quotation.gst)

            quotation.discount = Decimal(discount)
            quotation.totalgp = total_gp
            quotation.margin = margin
            quotation.finaltotal = final_total
            quotation.save()
        except IntegrityError as e:
            return JsonResponse({
                "status": "Error",
                "messages": "Already this Subject is existed!"
            })
        return JsonResponse({
            "status": "Success",
            "messages": "Subject created!",
            "discount": quotation.discount,
            "margin": quotation.margin,
        })


@ajax_login_required
def ajax_get_subjects(request):
    if request.method == "POST":
        quotation_id = request.POST.get('quotationid')
        subjects = ParentSubject.objects.filter(quotation_id=quotation_id).order_by('id')
        data = serializers.serialize('json', list(subjects), fields=('subject', 'id', 'is_optional'))
        return JsonResponse(json.dumps(data), safe=False)


@ajax_login_required
def ajax_get_scopedata(request):
    if request.method == "POST":
        description = request.POST.get('description')
        scopes = Scope.objects.all()
        scope = Scope.objects.filter(description=description).first()
        if scope is not None:
            data = {
                'status': "success",
                'uom_id': scope.uom_id,
                'qty': scope.qty,
                'unit_price': scope.unitprice,
                'unit_cost': scope.unitcost
            }
        else:
            data = {
                'status': "failed",
            }
        return JsonResponse(json.dumps(data, cls=DecimalEncoder), safe=False)


@ajax_login_required
def ajax_get_subject(request):
    if request.method == "POST":
        subject_id = request.POST.get('subjectid')
        subject = ParentSubject.objects.get(id=subject_id)
        data = {
            'subject': subject.subject,
        }
        return JsonResponse(json.dumps(data, cls=DecimalEncoder), safe=False)


@ajax_login_required
def subjectdelete(request):
    if request.method == "POST":
        subject_id = request.POST.get('subjectid')
        subject = ParentSubject.objects.get(id=subject_id)
        scopes = Scope.objects.filter(subject_id=subject_id)
        scopes.delete()
        subject.delete()
        return JsonResponse({'status': 'ok'})


@ajax_login_required
def ajax_subject_items(request):
    if request.method == "POST":
        quot_id = request.POST.get('quot_id')
        sub_id = request.POST.get('sub_id')
        sub_title = request.POST.get('sub_title')
        is_optional=request.POST.get('is_optional')
        scope = Scope.objects.filter(subject_id=sub_id).extra(select={'int_sn': 'CAST(sn AS INTEGER)'})\
            .order_by('int_sn')
        quotation = Quotation.objects.get(id=quot_id)
        return render(request, 'sales/quotation/ajax-subject.html',
                      {'title': sub_title, 'sub_id': sub_id, 'quotation': quotation, 'scope_list': scope, 'is_optional':is_optional})


@ajax_login_required
def getScope(request):
    if request.method == "POST":
        scopeid = request.POST.get('scopeid')
        scope = Scope.objects.get(id=scopeid)
        data = {
            'sn': scope.sn,
            'qty': scope.qty,
            'uom': scope.uom_id,
            'unitprice': scope.unitprice,
            'unitcost': scope.unitcost,
            'description': scope.description,
        }
        return JsonResponse(json.dumps(data, cls=DecimalEncoder), safe=False)


@ajax_login_required
def getFile(request):
    if request.method == "POST":
        fileid = request.POST.get('fileid')
        qfile = QFile.objects.get(id=fileid)
        if qfile.document:
            data = {
                'name': qfile.name,
                'document': qfile.document.url,
            }
        else:
            data = {
                'name': qfile.name,
                'document': "",
            }
        return JsonResponse(json.dumps(data, cls=DecimalEncoder), safe=False)


@ajax_login_required
def quotationdelete(request):
    if request.method == "POST":
        quotationid = request.POST.get('quot_id')
        quotation = Quotation.objects.get(qtt_id=quotationid)
        scopes = Scope.objects.filter(quotation=quotation.id)
        sales_repo = SaleReport.objects.filter(quotation=quotation.id)
        sales_repo_comment = SaleReportComment.objects.filter(salereport__in=sales_repo.values('id'))
        qfile = QFile.objects.filter(quotation=quotation.id)
        qfile.delete()
        scopes.delete()
        sales_repo_comment.delete()
        sales_repo.delete()
        try:
            pre_quotation= Quotation.objects.get(qtt_id=quotation.ref_quot)
            pre_quotation.flag=True
            pre_quotation.save()
        except Quotation.DoesNotExist:
            print("not previous quotation")
        quotation.delete()
        return JsonResponse({'status': 'ok'})


@ajax_login_required
def scopedelete(request):
    if request.method == "POST":
        scopeid = request.POST.get('scopeid')
        scope = Scope.objects.get(id=scopeid)
        scope.delete()
        return JsonResponse({'status': 'ok'})


@ajax_login_required
def qfiledelete(request):
    if request.method == "POST":
        fileid = request.POST.get('fileid')
        file = QFile.objects.get(id=fileid)
        file.delete()

        return JsonResponse({'status': 'ok'})


def send_mail(to_email, subject, message):
    # For Gmail
    SMTP_SERVER = "smtp.gmail.com"
    SMTP_PORT = 587
    my_email = os.getenv("DJANGO_DEFAULT_EMAIL")
    my_password = os.getenv("DJANGO_EMAIL_HOST_PASSWORD")
    msg = MIMEMultipart()
    msg['From'] = my_email
    msg['To'] = to_email
    msg['Date'] = formatdate(localtime=True)
    msg['Subject'] = subject
    msg.attach(MIMEText(message, 'html'))

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as smtpObj:
        smtpObj.ehlo()
        smtpObj.starttls()
        smtpObj.login(my_email, my_password)
        smtpObj.sendmail(my_email, to_email, msg.as_string())
        smtpObj.close()
    # print("********* Sent mail to {0} Successfully! **********".format(to_email))


@ajax_login_required
def UpdateQuotation(request):
    if request.method == "POST":

        company_nameid = request.POST.get('company_nameid')
        address = request.POST.get('address')
        contact_person = request.POST.get('contact_person')
        email = request.POST.get('email')
        tel = request.POST.get('tel')
        fax = request.POST.get('fax')
        note = request.POST.get('note')
        re = request.POST.get('re')
        qtt_id = request.POST.get('qtt_id')
        sale_type = request.POST.get('sale_type')
        date = request.POST.get('date')
        qtt_status = request.POST.get('qtt_status')
        sale_person = request.POST.get('sale_person')
        estimated_mandays = request.POST.get('estimated_mandays')
        po_no = request.POST.get('po_no')
        validity = request.POST.get('validity')
        terms = request.POST.get('terms')
        material_lead_time = request.POST.get('material_lead_time')
        quotid = request.POST.get('quotid')

        try:
            quotation = Quotation.objects.get(id=quotid)

            if quotation.qtt_status != qtt_status:
                sender = request.user
                description = 'Quotation No : ' + quotation.qtt_id + ' - status was changed as ' + qtt_status
                for receiver in User.objects.filter(role__in=["Admins", "Managers", "Sales"]):
                    notify.send(sender, recipient=receiver, verb='Message', level="success", description=description)

            quotation.company_nameid_id = company_nameid
            quotation.address = address
            quotation.contact_person_id = contact_person
            quotation.email = email
            quotation.tel = tel
            quotation.fax = fax
            quotation.qtt_id = qtt_id
            quotation.sale_type = sale_type
            quotation.date = date
            quotation.qtt_status = qtt_status
            quotation.note = note
            quotation.RE = re
            quotation.sale_person = sale_person
            quotation.estimated_mandays = estimated_mandays
            quotation.po_no = po_no
            quotation.material_leadtime = material_lead_time
            quotation.validity = validity
            quotation.terms = terms
            quotation.flag = True
            quotation.save()

            # make project_id for all auto-increamently.
            prefix = "CPJ"
            currentyear = time.strftime("%y", time.localtime())
            project_id = 0
            maintenance_id = 0
            sales_id = 0
            if Project.objects.all().exists():
                proj = Project.objects.all().order_by('-proj_id')[0]
                project_id = int(proj.proj_id[3:])
            if Maintenance.objects.all().exists():
                maintenance = Maintenance.objects.all().order_by('-main_no')[0]
                maintenance_id = int(maintenance.main_no[3:])
            if ProductSales.objects.all().exists():
                prod_sales = ProductSales.objects.all().order_by('-prod_sale_id')[0]
                sales_id = int(prod_sales.prod_sale_id[3:])
            max_id = max([project_id, maintenance_id, sales_id])
            if int(str(max_id)[0:2]) == int(currentyear):
                proj_id = prefix + str(currentyear) + str(int(str(max_id)[2:]) + 1)
            else:
                proj_id = prefix + str(currentyear) + "1000"

            if qtt_status == "Awarded" and sale_type == "Project":

                if Project.objects.filter(qtt_id__iexact=qtt_id).exists():
                    project = Project.objects.get(qtt_id__iexact=qtt_id)
                    # project.proj_id=proj_id
                    project.company_nameid_id = company_nameid
                    project.tel = tel
                    project.fax = fax
                    project.proj_status = "Open"
                    project.start_date = date
                    project.RE = re
                    project.email = email
                    project.qtt_id = qtt_id
                    project.quotation_id = quotid
                    project.estimated_mandays = estimated_mandays
                    project.save()

                else:
                    newproject = Project.objects.create(
                        proj_id=proj_id,
                        company_nameid_id=company_nameid,
                        tel=tel,
                        fax=fax,
                        proj_status="Open",
                        start_date=date,
                        RE=re,
                        email=email,
                        qtt_id=qtt_id,
                        estimated_mandays=estimated_mandays,
                        contact_person_id=contact_person,
                        quotation_id=quotid
                    )

                    add_default_project_files(newproject.id)
                    # TBM Template add part
                    tbmObjective = ToolBoxObjective.objects.all()
                    for tbmobj in tbmObjective:
                        for tbmDes in ToolBoxDescription.objects.filter(objective_id=tbmobj.id):
                            ToolBoxItem.objects.create(
                                objective=tbmobj.classify,
                                description=tbmDes.description,
                                project_id=newproject.id,
                                manager="Engineer"
                            )
                    # notification send
                    sender = request.user
                    is_email = NotificationPrivilege.objects.get(user_id=sender.id).is_email
                    if newproject.proj_name is not None:
                        project_name=newproject.proj_name
                    else:
                        project_name=""

                    description = '<a href="/project-summary-detail/' + str(newproject.id) + '">Project Name : ' + project_name + ' - New Project was created by ' + request.user.username + '</a>'
                    for receiver in User.objects.filter(role__iexact="Managers"):
                        if receiver.notificationprivilege.project_no_created:
                            notify.send(sender, recipient=receiver, verb='Message', level="success",
                                        description=description)
                            if is_email and receiver.email:
                                send_mail(receiver.email, "Notification for New Project ", description)


            elif qtt_status == "Awarded" and sale_type == "Maintenance":
                if Maintenance.objects.filter(quot_no__iexact=qtt_id).exists():

                    maintenance = Maintenance.objects.get(quot_no__iexact=qtt_id)
                    # maintenance.main_no=proj_id
                    maintenance.company_nameid_id = company_nameid
                    maintenance.tel = tel
                    maintenance.fax = fax
                    maintenance.main_status = "Open"
                    maintenance.start_date = date
                    maintenance.RE = re
                    maintenance.email = email
                    maintenance.quot_no = qtt_id
                    maintenance.contact_person_id = contact_person
                    maintenance.save()
                else:
                    Maintenance.objects.create(
                        main_no=proj_id,
                        company_nameid_id=company_nameid,
                        tel=tel,
                        fax=fax,
                        main_status="Open",
                        start_date=date,
                        RE=re,
                        quotation_id=quotid,
                        email=email,
                        quot_no=qtt_id,
                        contact_person_id=contact_person
                    )


            elif qtt_status == "Awarded" and sale_type == "Sales":
                if ProductSales.objects.filter(quotation_id=quotid).exists():
                    product_sale = ProductSales.objects.get(quotation_id=quotid)
                    product_sale.company_nameid_id = company_nameid
                    product_sale.email = email
                    product_sale.tel = tel
                    product_sale.fax = fax
                    product_sale.RE = re
                    product_sale.quotation_id = quotid
                    product_sale.note = note
                    product_sale.contact_person_id = contact_person
                    product_sale.save()
                else:

                    # prefix = "CSL"
                    # currentyear = time.strftime("%y", time.localtime())
                    # if ProductSales.objects.all().exists():
                    #     prod_sale = ProductSales.objects.all().order_by('-prod_sale_id')[0]
                    #     if int(prod_sale.prod_sale_id[3:5]) == int(currentyear):
                    #         main_id = prefix + str(currentyear) + str(int(prod_sale.prod_sale_id[5:]) + 1)
                    #     else:
                    #         main_id = prefix + str(currentyear) + "1001"
                    #
                    # else:
                    #     main_id = prefix + str(currentyear) + "1001"

                    ProductSales.objects.create(
                        prod_sale_id=proj_id,
                        company_nameid_id=company_nameid,
                        tel=tel,
                        fax=fax,
                        RE=re,
                        note=note,
                        quotation_id=quotid,
                        email=email,
                        contact_person_id=contact_person
                    )

            if SaleReport.objects.filter(qtt_id=qtt_id).exists():
                salereport = SaleReport.objects.get(qtt_id__iexact=qtt_id)
                salereport.qtt_id = qtt_id
                salereport.company_nameid_id = company_nameid
                salereport.address = address
                salereport.email = email
                salereport.sale_person = sale_person
                salereport.qtt_status = qtt_status
                salereport.sale_type = sale_type
                salereport.date = date
                salereport.RE = re
                salereport.contact_person_id = contact_person
                if Scope.objects.filter(quotation_id=quotation.id).exists():
                    subtotal = Scope.objects.filter(quotation_id=quotation.id).aggregate(Sum('amount'))['amount__sum']
                    gst = (float(subtotal) - float(quotation.discount)) * 0.09
                    total_detail = float(subtotal) + gst
                    salereport.finaltotal = Decimal(total_detail)
                    salereport.margin = Decimal(quotation.margin)
                salereport.save()
            else:
                sale = SaleReport(
                    qtt_id=qtt_id,
                    company_nameid_id=company_nameid,
                    address=address,
                    email=email,
                    sale_person=sale_person,
                    qtt_status=qtt_status,
                    sale_type=sale_type,
                    date=date,
                    RE=re,
                    quotation_id=quotid,
                    contact_person_id=contact_person,
                )
                if Scope.objects.filter(quotation_id=quotation.id).exists():
                    subtotal = Scope.objects.filter(quotation_id=quotation.id).aggregate(Sum('amount'))['amount__sum']
                    gst = (float(subtotal) - float(quotation.discount)) * 0.09
                    total_detail = float(subtotal) + gst
                    sale.finaltotal = Decimal(total_detail)
                    sale.margin = Decimal(quotation.margin)
                sale.save()
            return JsonResponse({
                "status": "Success",
                "messages": "Quotation information updated!"
            })
        except IntegrityError as e:
            print(e)
            return JsonResponse({
                "status": "Error",
                "messages": "Error is existed!"
            })


def add_default_project_files(proj_id):
    ProjectFile.objects.create(
        name="Technical Specifications",
        document=None,
        uploaded_by_id=None,
        project_id=proj_id,
        date=datetime.datetime.now().date()
    )
    ProjectFile.objects.create(
        name="Drawings",
        document=None,
        uploaded_by_id=None,
        project_id=proj_id,
        date=datetime.datetime.now().date()
    )
    ProjectFile.objects.create(
        name="Schematic",
        document=None,
        uploaded_by_id=None,
        project_id=proj_id,
        date=datetime.datetime.now().date()
    )
    ProjectFile.objects.create(
        name="Bill of Materials with Brands",
        document=None,
        uploaded_by_id=None,
        project_id=proj_id,
        date=datetime.datetime.now().date()
    )
    ProjectFile.objects.create(
        name="Catalogue",
        document=None,
        uploaded_by_id=None,
        project_id=proj_id,
        date=datetime.datetime.now().date()
    )
    ProjectFile.objects.create(
        name="Project schedule",
        document=None,
        uploaded_by_id=None,
        project_id=proj_id,
        date=datetime.datetime.now().date()
    )


@ajax_login_required
def UpdateQuotationOverride(request):
    if request.method == "POST":

        company_nameid = request.POST.get('company_nameid')
        address = request.POST.get('address')
        contact_person = request.POST.get('contact_person')
        email = request.POST.get('email')
        tel = request.POST.get('tel')
        fax = request.POST.get('fax')
        note = request.POST.get('note')
        re = request.POST.get('re')
        qtt_id = request.POST.get('qtt_id')
        sale_type = request.POST.get('sale_type')
        date = request.POST.get('date')
        qtt_status = request.POST.get('qtt_status')
        sale_person = request.POST.get('sale_person')
        po_no = request.POST.get('po_no')
        validity = request.POST.get('validity')
        terms = request.POST.get('terms')
        estimated_mandays = request.POST.get('estimated_mandays')
        material_lead_time = request.POST.get('material_lead_time')
        quotid = request.POST.get('quotid')
        if len(qtt_id.split("-")) == 1:
            new_qtt_id = qtt_id + "-1"
        else:
            new_qtt_id = qtt_id.split("-")[0] + "-" + str(int(qtt_id.split("-")[1]) + 1)
        try:
            quotation = Quotation.objects.get(id=quotid)

            # quotation.company_name=company_name
            # quotation.address=address
            # quotation.contact_person=contact_person
            # quotation.email=email
            # quotation.tel=tel
            # quotation.fax=fax
            # quotation.qtt_id=qtt_id
            # quotation.sale_type=sale_type
            # quotation.date=date
            # quotation.qtt_status=qtt_status
            # quotation.note=note
            quotation.flag = False
            # quotation.sale_person=sale_person
            quotation.save()

            new = Quotation(
                company_nameid_id=company_nameid,
                address=address,
                contact_person_id=contact_person,
                email=email,
                tel=tel,
                fax=fax,
                qtt_id=new_qtt_id,
                sale_type=sale_type,
                date=date,
                qtt_status=qtt_status,
                note=note,
                RE=re,
                sale_person=sale_person,
                estimated_mandays=estimated_mandays,
                validity=validity,
                terms=terms,
                po_no=po_no,
                material_leadtime=material_lead_time,
                flag=True,
                ref_quot=qtt_id
            )
            new.save()
            if SaleReport.objects.filter(qtt_id=qtt_id).exists():
                # salereport = SaleReport.objects.get(qtt_id__iexact=qtt_id)
                # salereport.qtt_id=qtt_id
                # salereport.company_name=company_name
                # salereport.address=address
                # salereport.email=email
                # salereport.sale_person=sale_person
                # salereport.qtt_status=qtt_status
                # salereport.sale_type=sale_type
                # salereport.date=date
                # salereport.contact_person=contact_person
                # salereport.save()
                print("exist")
            else:
                sale = SaleReport(
                    qtt_id=qtt_id,
                    company_nameid_id=company_nameid,
                    address=address,
                    email=email,
                    sale_person=sale_person,
                    qtt_status=qtt_status,
                    sale_type=sale_type,
                    date=date,
                    contact_person_id=contact_person
                )
                sale.save()

            if SaleReport.objects.filter(qtt_id=new.qtt_id).exists():
                salereport = SaleReport.objects.get(qtt_id__iexact=new.qtt_id)
                salereport.qtt_id = new.qtt_id
                salereport.company_nameid_id = company_nameid
                salereport.address = address
                salereport.email = email
                salereport.sale_person = sale_person
                salereport.qtt_status = qtt_status
                salereport.sale_type = sale_type
                salereport.date = date
                salereport.contact_person_id = contact_person
                salereport.save()
            else:
                sale = SaleReport(
                    qtt_id=new.qtt_id,
                    company_nameid_id=company_nameid,
                    address=address,
                    email=email,
                    sale_person=sale_person,
                    qtt_status=qtt_status,
                    sale_type=sale_type,
                    date=date,
                    contact_person_id=contact_person
                )
                sale.save()
            parent_subjects = ParentSubject.objects.filter(quotation_id=quotid)
            for subject in parent_subjects:
                ParentSubject.objects.create(
                    subject=subject.subject,
                    quotation_id=new.id,
                    revision_sub_id=subject.id
                )

            scopedata = Scope.objects.filter(quotation_id=quotid)
            for scoped in scopedata:
                parent_sub=ParentSubject.objects.get(revision_sub_id=scoped.subject.id)
                Scope.objects.create(
                    qty=scoped.qty,
                    uom=scoped.uom,
                    description=scoped.description,
                    amount=Decimal(float(scoped.qty) * float(scoped.unitprice)),
                    unitprice=Decimal(scoped.unitprice),
                    quotation_id=new.id,
                    qtt_id=new_qtt_id,
                    subject_id=parent_sub.id
                )
            if scopedata:

                subtotal = Scope.objects.filter(quotation_id=new.id).aggregate(Sum('amount'))['amount__sum']
                quotation = Quotation.objects.get(id=new.id)
                gst = (float(subtotal) - float(quotation.discount)) * 0.09
                total_detail = float(subtotal) + gst
                quotation.total = Decimal(total_detail)
                quotation.save()

                if SaleReport.objects.filter(qtt_id__iexact=str(quotation.qtt_id)).exists():
                    salereport = SaleReport.objects.get(qtt_id__iexact=str(quotation.qtt_id))
                    salereport.finaltotal = Decimal(total_detail)
                    salereport.margin = Decimal(quotation.margin)
                    salereport.save()

            # make project_id for all auto-increamently.
            prefix = "CPJ"
            currentyear = time.strftime("%y", time.localtime())
            proj = Project.objects.all().order_by('-proj_id')[0]
            maintenance = Maintenance.objects.all().order_by('-main_no')[0]
            prod_sales = ProductSales.objects.all().order_by('-prod_sale_id')[0]
            max_id = max([int(proj.proj_id[3:]), int(maintenance.main_no[3:]), int(prod_sales.prod_sale_id[3:])])
            if int(str(max_id)[0:2]) == int(currentyear):
                proj_id = prefix + str(currentyear) + str(int(str(max_id)[2:]) + 1)
            else:
                proj_id = prefix + str(currentyear) + "1000"

            if qtt_status == "Awarded" and sale_type == "Project":

                if Project.objects.filter(qtt_id__iexact=qtt_id).exists() == False:

                    newPro = Project.objects.create(
                        proj_id=proj_id,
                        company_nameid_id=company_nameid,
                        tel=tel,
                        fax=fax,
                        proj_status="Open",
                        start_date=date,
                        RE=re,
                        email=email,
                        estimated_mandays=estimated_mandays,
                        qtt_id=qtt_id,
                        quotation_id=new.id
                    )

                    add_default_project_files(newPro.id)
                    # TBM Template add part
                    tbmObjective = ToolBoxObjective.objects.all()
                    for tbmobj in tbmObjective:
                        for tbmDes in ToolBoxDescription.objects.filter(objective_id=tbmobj.id):
                            ToolBoxItem.objects.create(
                                objective=tbmobj.classify,
                                description=tbmDes.description,
                                project_id=newPro.id,
                                manager="Engineer"
                            )
                else:
                    project = Project.objects.get(qtt_id__iexact=qtt_id)
                    # project.proj_id=proj_id
                    project.company_nameid_id = company_nameid
                    project.tel = tel
                    project.fax = fax
                    project.proj_status = "Open"
                    project.start_date = date
                    project.RE = re
                    project.email = email
                    project.qtt_id = qtt_id
                    project.estimated_mandays = estimated_mandays
                    project.quotation_id = new.id
                    project.save()

                if Project.objects.filter(qtt_id__iexact=new.qtt_id).exists() == False:
                    newProj = Project.objects.create(
                        proj_id=proj_id,
                        company_nameid_id=company_nameid,
                        tel=tel,
                        fax=fax,
                        proj_status="Open",
                        start_date=date,
                        RE=re,
                        email=email,
                        qtt_id=new.qtt_id
                    )
                    add_default_project_files(newProj.id)
                    # TBM Template add part
                    tbmObjective = ToolBoxObjective.objects.all()
                    for tbmobj in tbmObjective:
                        for tbmDes in ToolBoxDescription.objects.filter(objective_id=tbmobj.id):
                            ToolBoxItem.objects.create(
                                objective=tbmobj.classify,
                                description=tbmDes.description,
                                project_id=newProj.id,
                                manager="Engineer"
                            )
                else:
                    project = Project.objects.get(qtt_id__iexact=qtt_id)
                    # project.proj_id=proj_id
                    project.company_nameid_id = company_nameid
                    project.tel = tel
                    project.fax = fax
                    project.proj_status = "Open"
                    project.start_date = date
                    project.RE = re
                    project.email = email
                    project.qtt_id = new.qtt_id
                    project.save()


            elif qtt_status == "Awarded" and sale_type == "Maintenance":

                if Maintenance.objects.filter(quot_no__iexact=qtt_id).exists() == False:

                    Maintenance.objects.create(
                        main_no=proj_id,
                        company_nameid_id=company_nameid,
                        tel=tel,
                        fax=fax,
                        main_status="Open",
                        start_date=date,
                        RE=re,
                        quotation_id=quotid,
                        email=email,
                        quot_no=qtt_id,
                        contact_person_id=contact_person
                    )
                else:
                    maintenance = Maintenance.objects.get(quot_no__iexact=qtt_id)
                    # maintenance.main_no=main_id
                    maintenance.company_nameid_id = company_nameid
                    maintenance.tel = tel
                    maintenance.fax = fax
                    maintenance.main_status = "Open"
                    maintenance.start_date = date
                    maintenance.RE = re
                    maintenance.email = email
                    maintenance.quot_no = qtt_id
                    maintenance.contact_person_id = contact_person
                    maintenance.save()

                if Maintenance.objects.filter(quot_no__iexact=new.qtt_id).exists() == False:

                    Maintenance.objects.create(
                        main_no=proj_id,
                        company_nameid_id=company_nameid,
                        tel=tel,
                        fax=fax,
                        main_status="Open",
                        start_date=date,
                        RE=re,
                        quotation_id=quotid,
                        email=email,
                        quot_no=new.qtt_id
                    )
                else:
                    maintenance = Maintenance.objects.get(quot_no__iexact=qtt_id)
                    # maintenance.main_no=main_id
                    maintenance.company_nameid_id = company_nameid
                    maintenance.tel = tel
                    maintenance.fax = fax
                    maintenance.main_status = "Open"
                    maintenance.start_date = date
                    maintenance.RE = re
                    maintenance.email = email
                    maintenance.quot_no = new.qtt_id
                    maintenance.save()

            return JsonResponse({
                "status": "Success",
                "messages": "Quotation information updated!"
            })
        except IntegrityError as e:
            print(e)
            return JsonResponse({
                "status": "Error",
                "messages": "Error is existed!"
            })


@method_decorator(login_required, name='dispatch')
@method_decorator(sale_report_privilege_required, name='dispatch')
class ReportView(ListView):
    model = SaleReport
    template_name = "sales/report/report-list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['companys'] = Company.objects.all()

        context['total_amount'] = SaleReport.objects.all().aggregate(Sum("finaltotal"))['finaltotal__sum'] or 0.00
        context['awarded_amount'] = \
            SaleReport.objects.all().filter(qtt_status__in=["Awarded", "Closed"]).aggregate(Sum("finaltotal"))[
                'finaltotal__sum'] or 0.00
        context['open_amount'] = SaleReport.objects.all().filter(qtt_status="Open").aggregate(Sum("finaltotal"))[
                                     'finaltotal__sum'] or 0.00
        context['statuses'] = SaleReport.Status
        if self.request.user.role == "Managers" or self.request.user.is_staff == True:
            context['sqtt_ids'] = SaleReport.objects.order_by('qtt_id').values('qtt_id').distinct()
            context['salepersons'] = SaleReport.objects.exclude(sale_person=None).order_by('sale_person').values(
                'sale_person').distinct()
        else:
            context['sqtt_ids'] = SaleReport.objects.filter(sale_person__iexact=self.request.user.username).order_by(
                'qtt_id').values('qtt_id').distinct()
            context['salepersons'] = SaleReport.objects.exclude(sale_person=None).filter(
                sale_person__iexact=self.request.user.username).order_by('sale_person').values('sale_person').distinct()
        return context


@ajax_login_required
def salereportadd(request):
    if request.method == "POST":
        qtt_id = request.POST.get('qtt_id')
        date = request.POST.get('date')
        address = request.POST.get('address')
        company_nameid = request.POST.get('company_nameid')
        sale_person = request.POST.get('sale_person')
        qtt_status = request.POST.get('qtt_status')
        reportid = request.POST.get('reportid')
        if reportid == "-1":
            try:
                SaleReport.objects.create(
                    qtt_id=qtt_id,
                    date=date,
                    company_nameid=company_nameid,
                    address=address,
                    sale_person=sale_person,
                    qtt_status=qtt_status,
                )
                return JsonResponse({
                    "status": "Success",
                    "messages": "Report information added!"
                })
            except IntegrityError as e:
                return JsonResponse({
                    "status": "Error",
                    "messages": "Error is existed!"
                })
        else:
            try:
                report = SaleReport.objects.get(id=reportid)
                report.qtt_id = qtt_id
                report.date = date
                report.address = address
                report.company_nameid = company_nameid
                report.sale_person = sale_person
                report.qtt_status = qtt_status

                report.save()

                return JsonResponse({
                    "status": "Success",
                    "messages": "Report information updated!"
                })

            except IntegrityError as e:
                return JsonResponse({
                    "status": "Error",
                    "messages": "Error is existed!"
                })


@ajax_login_required
def getReport(request):
    if request.method == "POST":
        reportid = request.POST.get('reportid')
        salereport = SaleReport.objects.get(id=reportid)
        data = {
            'qtt_id': salereport.qtt_id,
            'address': salereport.address,
            'date': salereport.date.strftime('%d %b, %Y'),
            'company_nameid': salereport.company_nameid,
            'sale_person': salereport.sale_person,
            'qtt_status': salereport.qtt_status,

        }
        return JsonResponse(json.dumps(data), safe=False)


@ajax_login_required
def reportdelete(request):
    if request.method == "POST":
        reportid = request.POST.get('reportid')
        company = SaleReport.objects.get(id=reportid)
        sales_repo_comment = SaleReportComment.objects.filter(salereport=company.id)
        sales_repo_comment.delete()
        company.delete()
        return JsonResponse({'status': 'ok'})


@method_decorator(login_required, name='dispatch')
class ReportDetailView(DetailView):
    model = SaleReport
    template_name = "sales/report/report-detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        content_pk = self.kwargs.get('pk')
        context['salereport'] = SaleReport.objects.get(id=content_pk)
        context['salerep'] = content_pk
        context['contacts'] = Contact.objects.all()
        context['comments'] = SaleReportComment.objects.filter(salereport_id=content_pk)

        return context


@ajax_login_required
def UpdateReport(request):
    if request.method == "POST":

        company_nameid = request.POST.get('company_nameid')
        address = request.POST.get('address')
        contact_person = request.POST.get('contact_person')
        email = request.POST.get('email')
        amount = request.POST.get('amount')
        sale_person = request.POST.get('sale_person')
        note = request.POST.get('note')
        qtt_id = request.POST.get('qtt_id')
        sale_type = request.POST.get('sale_type')
        date = request.POST.get('date')
        qtt_status = request.POST.get('qtt_status')
        reportid = request.POST.get('reportid')
        try:
            report = SaleReport.objects.get(id=reportid)

            report.company_nameid = company_nameid
            report.address = address
            report.contact_person_id = contact_person
            report.email = email
            report.sale_person = sale_person
            report.finaltotal = amount
            report.qtt_id = qtt_id
            report.sale_type = sale_type
            report.date = date
            report.qtt_status = qtt_status
            report.RE = note
            report.save()

            return JsonResponse({
                "status": "Success",
                "messages": "Report information updated!"
            })
        except IntegrityError as e:
            print(e)
            return JsonResponse({
                "status": "Error",
                "messages": "Error is existed!"
            })


@ajax_login_required
def addSaleComment(request):
    if request.method == "POST":

        today = date.today()
        comment = request.POST['comment']
        salereportid = request.POST['salereportid']
        commentid = request.POST['commentid']
        followup_date = request.POST['followup_date']
        if request.user.username:
            comment_by = request.user.username
        else:
            comment_by = request.user.first_name
        if commentid == "-1":
            SaleReportComment.objects.create(
                comment=comment,
                comment_by=comment_by,
                salereport_id=salereportid,
                comment_at=today,
                followup_date=followup_date,
            )

            return JsonResponse({
                "status": "Success",
                "messages": "Comment Submited!"
            })
        else:
            try:
                sreport = SaleReportComment.objects.get(id=commentid)
                sreport.comment = comment
                sreport.comment_by = comment_by
                sreport.salereport_id = salereportid
                sreport.comment_at = today
                sreport.followup_date = followup_date
                sreport.save()

                return JsonResponse({
                    "status": "Success",
                    "messages": "Report Comment information updated!"
                })

            except IntegrityError as e:
                return JsonResponse({
                    "status": "Error",
                    "messages": "Error is existed!"
                })


@method_decorator(login_required, name='dispatch')
@method_decorator(sale_report_privilege_required, name='dispatch')
class SalesItemListView(ListView):
    model = Scope
    template_name = "sales/scope/item-list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.role == "Managers" or self.request.user.is_staff == True:
            context['sqtt_ids'] = Scope.objects.order_by('qtt_id').values('qtt_id').distinct()
        else:
            context['sqtt_ids'] = Scope.objects.filter(quotation__sale_person=self.request.user.username).order_by(
                'qtt_id').values('qtt_id').distinct()
        return context


@ajax_login_required
def ajax_all_scopes(request):
    if request.method == "POST":
        scopes = Scope.objects.filter(parent=None)
        if request.user.role == "Managers" or request.user.is_staff == True:
            scopes = Scope.objects.filter(parent=None)
        else:
            scopes = Scope.objects.filter(parent=None, quotation__sale_person=request.user.username)
        return render(request, 'sales/scope/ajax-scope.html', {'scopes': scopes})


@ajax_login_required
def ajax_filter_scope(request):
    if request.method == "POST":
        search_quotation = request.POST.get('search_quotation')
        if request.user.role == "Managers" or request.user.is_staff == True:
            scopes = Scope.objects.filter(parent=None)
        else:
            scopes = Scope.objects.filter(parent=None, quotation__sale_person=request.user.username)
        if search_quotation != "":
            scopes = scopes.filter(qtt_id__iexact=search_quotation)
        return render(request, 'sales/scope/ajax-scope.html', {'scopes': scopes})


@method_decorator(login_required, name='dispatch')
@method_decorator(sale_report_privilege_required, name='dispatch')
class SalesTaskListView(ListView):
    model = SaleReportComment
    template_name = "sales/report/task-list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.role == "Managers" or self.request.user.is_staff == True:
            context['sqtt_ids'] = SaleReportComment.objects.all().order_by('salereport__qtt_id').values(
                'salereport__qtt_id').distinct()
        else:
            context['sqtt_ids'] = SaleReportComment.objects.filter(
                salereport__sale_person=self.request.user.username).order_by(
                'salereport__qtt_id').values('salereport__qtt_id').distinct()
        return context


@ajax_login_required
def ajax_all_tasks(request):
    if request.method == "POST":
        if request.user.role == "Managers" or request.user.is_staff == True:
            report_comments = SaleReportComment.objects.all()
        else:
            report_comments = SaleReportComment.objects.filter(salereport__sale_person=request.user.username)
        return render(request, 'sales/report/ajax-task.html', {'tasks': report_comments})


@ajax_login_required
def ajax_filter_task(request):
    if request.method == "POST":
        search_quotation = request.POST.get('search_quotation')
        if request.user.role == "Managers" or request.user.is_staff == True:
            report_comments = SaleReportComment.objects.all()
        else:
            report_comments = SaleReportComment.objects.filter(salereport__sale_person=request.user.username)
        if search_quotation != "":
            report_comments = report_comments.filter(salereport__qtt_id=search_quotation)
        return render(request, 'sales/report/ajax-task.html', {'tasks': report_comments})


@ajax_login_required
def ajax_reports(request):
    if request.method == "POST":
        if request.user.role == "Managers" or request.user.is_staff == True:
            reports = SaleReport.objects.all()
        else:
            reports = SaleReport.objects.filter(sale_person__iexact=request.user.username)
        for report in reports:
            if Quotation.objects.filter(id=report.quotation_id).exists():
                quotation = Quotation.objects.get(id=report.quotation_id)
                report.margin = quotation.margin
                report.save()

        total_amount = reports.aggregate(Sum("finaltotal"))['finaltotal__sum'] or 0.00
        awarded_amount = reports.filter(qtt_status__in=["Awarded", "Closed"]).aggregate(Sum("finaltotal"))[
                             'finaltotal__sum'] or 0.00
        open_amount = reports.filter(qtt_status="Open").aggregate(Sum("finaltotal"))[
                          'finaltotal__sum'] or 0.00
        return render(request, 'sales/report/ajax-report.html',
                      {'reports': reports, 'total_amount': total_amount, 'awarded_amount': awarded_amount,
                       'open_amount': open_amount})


@ajax_login_required
def ajax_filter_report(request):
    if request.method == "POST":
        search_quotation = request.POST.get('search_quotation')
        daterange = request.POST.get('daterange')
        if daterange:
            startdate = datetime.datetime.strptime(daterange.split()[0], '%Y.%m.%d').replace(tzinfo=pytz.utc)
            enddate = datetime.datetime.strptime(daterange.split()[2], '%Y.%m.%d').replace(tzinfo=pytz.utc)
        search_person = request.POST.get('search_person')
        status = request.POST.get('status')

        if request.user.role == "Managers" or request.user.is_staff == True:
            reports = SaleReport.objects.all()
        else:
            reports = SaleReport.objects.filter(sale_person__iexact=request.user.username)

        if search_quotation != "":
            reports = reports.filter(qtt_id__iexact=search_quotation)
        if daterange != "":
            reports = reports.filter(date__gte=startdate, date__lte=enddate)
        if search_person != "":
            reports = reports.filter(sale_person__iexact=search_person)
        if status != "":
            reports = reports.filter(qtt_status__iexact=status)
        total_amount = reports.aggregate(Sum("finaltotal"))['finaltotal__sum'] or 0.00
        awarded_amount = reports.filter(qtt_status__in=["Awarded", "Closed"]).aggregate(Sum("finaltotal"))[
                             'finaltotal__sum'] or 0.00
        open_amount = reports.filter(qtt_status="Open").aggregate(Sum("finaltotal"))[
                          'finaltotal__sum'] or 0.00
        return render(request, 'sales/report/ajax-report.html',
                      {'reports': reports, 'total_amount': total_amount, 'awarded_amount': awarded_amount,
                       'open_amount': open_amount})


@ajax_login_required
def getComReport(request):
    if request.method == "POST":
        commentid = request.POST.get('commentid')
        comment = SaleReportComment.objects.get(id=commentid)
        data = {
            'comment': comment.comment,
            'followup_date': comment.followup_date.strftime('%d %b, %Y'),
        }
        return JsonResponse(json.dumps(data), safe=False)


@ajax_login_required
def reportcommentdelete(request):
    if request.method == "POST":
        commentid = request.POST.get('commentid')
        comment = SaleReportComment.objects.get(id=commentid)
        comment.delete()

        return JsonResponse({'status': 'ok'})


class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []
        self.PAGE_HEIGHT = defaultPageSize[1]
        self.PAGE_WIDTH = defaultPageSize[0]
        self.domain = settings.HOST_NAME
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


# Header for Do
def header_do(canvas, doc, do, value, domain):
    RIGHT_X = 370
    CONTENT_PADDING = 10
    LEFT_X_1 = 40
    LEFT_X_2 = 90
    LEFT_X_3 = 220
    LEFT_X_4 = 250
    LEFT_X_5 = 300
    TOP_MARGIN = 130
    LINE_SPACE = 15

    canvas.saveState()
    project = do.product_sales
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
    canvas.drawString(RIGHT_X + 20, canvas.PAGE_HEIGHT - TOP_MARGIN, "DELIVERY ORDER")
    canvas.setFont("Helvetica-Bold", 10)
    canvas.drawString(RIGHT_X, canvas.PAGE_HEIGHT - TOP_MARGIN - LINE_SPACE, "DO No: ")
    canvas.drawString(RIGHT_X, canvas.PAGE_HEIGHT - TOP_MARGIN - 2 * LINE_SPACE, "Project No: ")
    canvas.drawString(RIGHT_X, canvas.PAGE_HEIGHT - TOP_MARGIN - 3 * LINE_SPACE, "Date: ")
    canvas.drawString(RIGHT_X, canvas.PAGE_HEIGHT - TOP_MARGIN - 4 * LINE_SPACE, "Sales: ")
    canvas.drawString(RIGHT_X, canvas.PAGE_HEIGHT - TOP_MARGIN - 5 * LINE_SPACE, "Terms: ")
    canvas.drawString(RIGHT_X, canvas.PAGE_HEIGHT - TOP_MARGIN - 6 * LINE_SPACE, "PO No: ")
    canvas.setFont("Helvetica", 10)
    canvas.drawString(RIGHT_X + 4 * CONTENT_PADDING, canvas.PAGE_HEIGHT - TOP_MARGIN - LINE_SPACE, "%s" % (do.do_no))
    canvas.drawString(RIGHT_X + 6 * CONTENT_PADDING, canvas.PAGE_HEIGHT - TOP_MARGIN - 2 * LINE_SPACE,
                      "%s" % (project.prod_sale_id))
    canvas.drawString(RIGHT_X + 4 * CONTENT_PADDING, canvas.PAGE_HEIGHT - TOP_MARGIN - 3 * LINE_SPACE, "%s" % (dodate))
    canvas.drawString(RIGHT_X + 4 * CONTENT_PADDING, canvas.PAGE_HEIGHT - TOP_MARGIN - 4 * LINE_SPACE,
                      "%s" % (qsale_person))
    canvas.drawString(RIGHT_X + 4 * CONTENT_PADDING, canvas.PAGE_HEIGHT - TOP_MARGIN - 5 * LINE_SPACE, "%s" % (qterms))
    canvas.drawString(RIGHT_X + 4 * CONTENT_PADDING, canvas.PAGE_HEIGHT - TOP_MARGIN - 6 * LINE_SPACE, "%s" % (qpo_no))

    bill_to1 = project.company_nameid
    if Quotation.objects.filter(id__iexact=project.quotation_id).exists():
        quotation = Quotation.objects.get(id__iexact=project.quotation_id)
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
    canvas.drawString(LEFT_X_1, canvas.PAGE_HEIGHT - TOP_MARGIN - 3 * LINE_SPACE, "Ship To:  ")
    canvas.drawString(LEFT_X_1, canvas.PAGE_HEIGHT - TOP_MARGIN - 5 * LINE_SPACE, "Attn:  ")
    canvas.drawString(LEFT_X_3, canvas.PAGE_HEIGHT - TOP_MARGIN - 5 * LINE_SPACE, "Tel:  ")
    canvas.drawString(LEFT_X_1, canvas.PAGE_HEIGHT - TOP_MARGIN - 6 * LINE_SPACE, "Subject: ")

    canvas.setFont("Helvetica", 10)
    canvas.drawString(LEFT_X_2, canvas.PAGE_HEIGHT - TOP_MARGIN + 2, "%s" % (bill_to1))
    canvas.drawString(LEFT_X_2, canvas.PAGE_HEIGHT - TOP_MARGIN - LINE_SPACE, "%s %s" % (address, qunit))
    canvas.drawString(LEFT_X_2, canvas.PAGE_HEIGHT - TOP_MARGIN - 2 * LINE_SPACE, "%s %s" % (country, postalcode))
    shiptoobject = canvas.beginText(LEFT_X_2, canvas.PAGE_HEIGHT - TOP_MARGIN - 3 * LINE_SPACE)
    for line in shipto.splitlines(False):
        shiptoobject.textLine(line.rstrip())
    canvas.drawText(shiptoobject)
    canvas.drawString(LEFT_X_2, canvas.PAGE_HEIGHT - TOP_MARGIN - 5 * LINE_SPACE,
                      "%s" % (project.contact_person.salutation + " " + project.contact_person.contact_person))
    canvas.drawString(LEFT_X_4, canvas.PAGE_HEIGHT - TOP_MARGIN - 5 * LINE_SPACE, "%s" % (project.tel))
    canvas.drawString(LEFT_X_2, canvas.PAGE_HEIGHT - TOP_MARGIN - 6 * LINE_SPACE, "%s" % (project.RE))
    # remarksobject = canvas.beginText(LEFT_X_2, canvas.PAGE_HEIGHT - TOP_MARGIN - 7 * LINE_SPACE)
    # for line in remarks.splitlines(False):
    #     remarksobject.textLine(line.rstrip())
    # canvas.drawText(remarksobject)

    dosignature = SalesDOSignature.objects.filter(do_id=value)
    if dosignature.exists():
        dosign_data = SalesDOSignature.objects.get(do_id=value)
        sign_name = dosign_data.name
        sign_nric = dosign_data.nric
        sign_date = dosign_data.update_date.strftime('%d/%m/%Y')
        sign_logo = ImageReader('http://' + domain + dosign_data.signature_image.url)
        sign_string = sign_name + "/" + sign_nric + "/" + sign_date
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
    if sign_logo != "":
        canvas.drawImage(sign_logo, LEFT_X_1, canvas.PAGE_HEIGHT - TOP_MARGIN - 42 * LINE_SPACE, width=150 / 2,
                         height=105 / 2, mask='auto')
    if auto_sign != "":
        canvas.drawImage(auto_sign, LEFT_X_5, canvas.PAGE_HEIGHT - TOP_MARGIN - 42 * LINE_SPACE, width=150 / 2,
                         height=105 / 2, mask='auto')

    canvas.setFont("Helvetica", 9)
    canvas.drawString(LEFT_X_1, canvas.PAGE_HEIGHT - TOP_MARGIN - 43 * LINE_SPACE, "%s" % (sign_string))
    canvas.setFont("Helvetica-Bold", 10)
    canvas.drawString(LEFT_X_1, canvas.PAGE_HEIGHT - TOP_MARGIN - 44 * LINE_SPACE,
                      "%s" % ("Name/Sign & Stamp/NRIC (last 4 digits)/Date"))
    canvas.drawString(LEFT_X_5, canvas.PAGE_HEIGHT - TOP_MARGIN - 44 * LINE_SPACE, "%s" % ("Authorised Signature"))

    canvas.restoreState()


# For quotation.
def header(canvas, doc, quotation):
    RIGHT_X = 440
    LEFT_X_1 = 30
    LEFT_X_2 = 60
    LEFT_X_3 = 210
    LEFT_X_4 = 250
    TOP_MARGIN = 150
    LINE_SPACE = 20

    canvas.saveState()

    if quotation.date:
        qdate = quotation.date.strftime('%d/%m/%Y')
    else:
        qdate = " "
    if quotation.sale_person:
        qsaleperson = quotation.sale_person
    else:
        qsaleperson = " "

    canvas.setFont("Helvetica-Bold", 16)
    canvas.drawString(RIGHT_X, canvas.PAGE_HEIGHT - TOP_MARGIN, "QUOTATION")
    canvas.setFont("Helvetica", 10)
    canvas.drawString(RIGHT_X, canvas.PAGE_HEIGHT - TOP_MARGIN - LINE_SPACE, "Quotation No: %s" % (quotation.qtt_id))
    canvas.drawString(RIGHT_X, canvas.PAGE_HEIGHT - TOP_MARGIN - 2 * LINE_SPACE, "Date: %s" % (qdate))
    canvas.drawString(RIGHT_X, canvas.PAGE_HEIGHT - TOP_MARGIN - 3 * LINE_SPACE, "Prepared By: %s" % (qsaleperson))

    canvas.setFont("Helvetica-Bold", 10)
    canvas.drawString(LEFT_X_1, canvas.PAGE_HEIGHT - TOP_MARGIN + 2, "To: ")
    canvas.drawString(LEFT_X_1, canvas.PAGE_HEIGHT - TOP_MARGIN - 3 * LINE_SPACE, "Attn:  ")
    canvas.drawString(LEFT_X_3, canvas.PAGE_HEIGHT - TOP_MARGIN - 3 * LINE_SPACE, "Email:  ")

    canvas.drawString(LEFT_X_1, canvas.PAGE_HEIGHT - TOP_MARGIN - 4.5 * LINE_SPACE, "Tel: ")
    canvas.drawString(LEFT_X_3, canvas.PAGE_HEIGHT - TOP_MARGIN - 4.5 * LINE_SPACE, "Fax:  ")
    canvas.drawString(LEFT_X_1, canvas.PAGE_HEIGHT - TOP_MARGIN - 6 * LINE_SPACE, "RE:  ")
    # wraps = textwrap.wrap(address, 50)
    # x_pos=LEFT_X_2
    # y_pos=canvas.PAGE_HEIGHT - TOP_MARGIN-LINE_SPACE
    # for x in range(len(wraps)):
    #     canvas.drawString(x_pos, y_pos, wraps[x])
    #     y_pos -= LINE_SPACE

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

    canvas.setFont("Helvetica", 10)
    canvas.drawString(LEFT_X_2, canvas.PAGE_HEIGHT - TOP_MARGIN + 2, "%s" % (quotation.company_nameid.name))
    canvas.drawString(LEFT_X_2, canvas.PAGE_HEIGHT - TOP_MARGIN - LINE_SPACE, "%s %s" % (address, qunit))
    canvas.drawString(LEFT_X_2, canvas.PAGE_HEIGHT - TOP_MARGIN - 2 * LINE_SPACE, "%s %s" % (country, postalcode))

    canvas.drawString(LEFT_X_2, canvas.PAGE_HEIGHT - TOP_MARGIN - 3 * LINE_SPACE,
                      "%s %s" % (quotation.contact_person.salutation, quotation.contact_person.contact_person))
    test_email = wrap(quotation.email, 25)
    t = canvas.beginText(LEFT_X_4, canvas.PAGE_HEIGHT - TOP_MARGIN - 3 * LINE_SPACE)
    t.textLines(test_email)
    canvas.drawText(t)

    # canvas.drawString(LEFT_X_4, canvas.PAGE_HEIGHT - TOP_MARGIN - 3 * LINE_SPACE, "%s" % (quotation.email))

    canvas.drawString(LEFT_X_2, canvas.PAGE_HEIGHT - TOP_MARGIN - 4.5 * LINE_SPACE, "%s" % (quotation.tel))
    canvas.drawString(LEFT_X_4, canvas.PAGE_HEIGHT - TOP_MARGIN - 4.5 * LINE_SPACE, "%s" % (quotation.fax))
    reobject = canvas.beginText(LEFT_X_2, canvas.PAGE_HEIGHT - TOP_MARGIN - 6 * LINE_SPACE)
    for line in quotation.RE.splitlines(False):
        reobject.textLine(line.rstrip())
    canvas.drawText(reobject)
    canvas.restoreState()


def exportDoPDF(request, value):
    do = ProductSalesDo.objects.get(id=value)
    project = do.product_sales
    quotation = project.quotation
    doitems = ProductSalesDoItem.objects.filter(do_id=value)
    domain = request.META['HTTP_HOST']
    logo = Image('http://' + domain + '/static/assets/images/printlogo.png', hAlign='LEFT')
    response = HttpResponse(content_type='application/pdf')
    currentdate = datetime.date.today().strftime("%d-%m-%Y")
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
                            topMargin=3.2 * inch, bottomMargin=0.25 * inch, title=pdfname)
    styleSheet = getSampleStyleSheet()
    if doitems.exists():
        index = 1
        for doitem in doitems:
            temp_data = []
            description = '''
                <para align=center>
                    %s
                </para>
            ''' % (str(doitem.description))
            pddes = Paragraph(description, styleSheet["BodyText"])
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
    remark_data = [[Paragraph('''<para><font size=10><b>Remarks: </b></font></para>'''),
                    Paragraph('''<para><font size=9>%s</font></para>''' % (str(remarks).replace('\n', '<br />\n')))]]
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

    doc.build(story, canvasmaker=NumberedCanvas, onFirstPage=partial(header_do, do=do, value=value, domain=domain),
              onLaterPages=partial(header_do, do=do, value=value, domain=domain), )

    response.write(buff.getvalue())
    buff.close()
    return response


def exportQuotationPDF(request, value):
    quotation = Quotation.objects.get(id=value)
    quotationitems = Scope.objects.filter(quotation_id=value).order_by('sn')
    domain = request.META['HTTP_HOST']
    logo = Image('http://' + domain + '/static/assets/images/printlogo.png', hAlign='LEFT')
    response = HttpResponse(content_type='application/pdf')
    currentdate = date.today()
    pdfname = quotation.qtt_id + ".pdf"
    response['Content-Disposition'] = 'attachment; filename="{}"'.format(pdfname)

    story = []
    data = [
        [Paragraph('''<para align=left><font size=10><b>S/N</b></font></para>'''),
         Paragraph('''<para align=left><font size=10><b>Description</b></font></para>'''),
         Paragraph('''<para align=left><font size=10><b>UOM</b></font></para>'''),
         Paragraph('''<para align=left><font size=10><b>QTY</b></font></para>'''),
         Paragraph('''<para align=left><font size=10><b>U/Price(S$)</b></font></para>'''),
         Paragraph('''<para align=left><font size=10><b>Amount(S$)</b></font></para>''')],
    ]
    buff = BytesIO()
    doc = SimpleDocTemplate(buff, pagesize=portrait(A4), rightMargin=0.25 * inch, leftMargin=0.25 * inch,
                            topMargin=4.1 * inch, bottomMargin=0.5 * inch, title=pdfname)
    styleSheet = getSampleStyleSheet()

    if quotation.material_leadtime:
        qmaterial_leadtime = quotation.material_leadtime
    else:
        qmaterial_leadtime = " "
    if quotation.validity:
        qvalidity = quotation.validity
    else:
        qvalidity = " "
    if quotation.terms:
        qterms = quotation.terms
    else:
        qterms = " "

    if quotation.company_nameid.country:
        country = quotation.company_nameid.country.name
    else:
        country = " "
    if quotation.company_nameid.unit:
        qunit = quotation.company_nameid.unit
    else:
        qunit = " "
    if quotation.company_nameid.postal_code != "":
        postalcode = quotation.company_nameid.postal_code
    else:
        postalcode = " "

    index = 1
    temp_subject = ""
    for quotationitem in quotationitems:
        if quotationitem.subject is not None:
            parent_subject = quotationitem.subject.subject
            if temp_subject != parent_subject:
                temp_subject = parent_subject
                temp_data = []
                description = '''
                                <para align=left>
                                    <b>
                                        %s
                                    </b>
                                </para>
                            ''' % (str(parent_subject).replace('\n', '<br />\n'))
                # ''' % (str(parent_subject))

                pdes = Paragraph(description, styleSheet["BodyText"])
                temp_data.append("")
                temp_data.append(pdes)
                data.append(temp_data)
            temp_data = []
            description = '''
                <para align=left>
                    %s
                </para>
            ''' % (str(quotationitem.description).replace('\n', '<br />\n'))

            pdes = Paragraph(description, styleSheet["BodyText"])
            temp_data.append(str(quotationitem.sn))
            temp_data.append(pdes)
            temp_data.append(str(quotationitem.uom))
            temp_data.append(str(quotationitem.qty))
            if quotationitem.unitprice != 0:
                temp_data.append(str(quotationitem.unitprice))
            else:
                temp_data.append("")
            if quotationitem.amount != 0:
                temp_data.append(str(f'{quotationitem.amount:,}'))
            else:
                temp_data.append("")
            data.append(temp_data)
            index += 1
    if Scope.objects.filter(quotation_id=value, parent=None).exists():
        statistic = []
        subtotal = Scope.objects.filter(quotation_id=value, parent=None).aggregate(Sum('amount'))['amount__sum']
        gst = (float(subtotal) - float(quotation.discount)) * 0.09
        statistic.append("")
        statistic.append("")
        statistic.append("")
        statistic.append("")

        statistic.append(Paragraph('''<para align=left><font size=9><b>TOTAL</b></font></para>'''))
        statistic.append('{:,.2f}'.format(subtotal))
        data.append(statistic)

        if Quotation.objects.filter(id=value, discount__gt=0).exists():
            discount = Quotation.objects.get(id=value, discount__gt=0).discount
            statistic = []
            statistic.append("")
            statistic.append("")
            statistic.append("")
            statistic.append("")

            statistic.append(Paragraph('''<para align=left><font size=9><b>DISCOUNT</b></font></para>'''))
            statistic.append('{:,.2f}'.format(discount))
            data.append(statistic)
        statistic = []
        statistic.append("")
        statistic.append("")
        statistic.append("")
        statistic.append("")
        statistic.append(Paragraph('''<para align=left><font size=9><b>ADD GST 9%</b></font></para>'''))
        statistic.append('{:,.2f}'.format(gst))
        data.append(statistic)
        statistic = []
        statistic.append("")
        statistic.append("")
        statistic.append("")
        statistic.append("")
        statistic.append(Paragraph('''<para align=left><font size=9><b>FINAL TOTAL</b></font></para>'''))
        statistic.append('{:,.2f}'.format(float(subtotal) + gst))
        data.append(statistic)

        exportD = Table(
            data,
            style=[
                ('BACKGROUND', (0, 0), (5, 0), "#5a9bd5"),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                # ('SPAN',(1,-5),(-1,-5)),
                # ('SPAN',(1,-4),(-1,-4)),
                ('VALIGN', (0, 0), (-1, -1), "TOP"),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (0, 0), (1, -1), 'CENTER'),
            ],
        )
    else:
        data.append(["No data available in table", "", "", "", "", "", ])
        exportD = Table(
            data,
            style=[
                ('BACKGROUND', (0, 0), (5, 0), "#5a9bd5"),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('SPAN', (1, 2), (-1, 2)),
                ('VALIGN', (0, 0), (-1, -1), "MIDDLE"),
                ('ALIGN', (1, 2), (-1, 2), "CENTER"),
                ('SPAN', (0, 1), (-1, 1)),
                ('ALIGN', (0, 1), (-1, 1), "CENTER"),
                ('SPAN', (1, 3), (-1, 3)),
                ('ALIGN', (1, 3), (-1, 3), "CENTER"),
            ],
        )
    exportD._argW[0] = 0.40 * inch
    exportD._argW[1] = 3.59 * inch
    exportD._argW[2] = 0.732 * inch
    exportD._argW[3] = 0.732 * inch
    exportD._argW[4] = 1.0 * inch
    exportD._argW[5] = 1.0 * inch
    story.append(exportD)

    story.append(Spacer(1, 15))
    if quotation.note:
        note_content = quotation.note
    else:
        note_content = ""
    style_note = ParagraphStyle(name='note', parent=styleSheet['Normal'], leftIndent=10)
    story.append(
        Paragraph(
            '''<para align=left><font size=9><u><b><i>NOTE: </i></b></u><br/>%s</font></para>''' % note_content.replace(
                "\n", "<br />"),
            style_note))

    # if len(quotationitems)>=4:
    story.append(PageBreak())
    style_term = ParagraphStyle(name='right', fontSize=14, parent=styleSheet['Normal'], leftIndent=10)

    story.append(
        Paragraph('''<para align=left><font><u><i><b>Terms & Conditions</b></i></u></font></para>''', style_term))
    story.append(Spacer(1, 15))
    style_condition = ParagraphStyle(name='right', fontSize=9, parent=styleSheet['Normal'], leftIndent=20, leading=15)
    story.append(
        Paragraph('''<para align=left><font>● Validity : %s days </font></para>''' % (qvalidity), style_condition))
    story.append(Paragraph('''<para align=left><font>● Payment : %s </font></para>''' % (qterms), style_condition))
    story.append(Paragraph('''<para align=left><font>● Material Leadtime : %s </font></para>''' % (qmaterial_leadtime),
                           style_condition))
    story.append(Paragraph("● Note : Price quoted for normal working hours unless stated", style_condition))
    story.append(Paragraph(
        "● Note : CNI Technology Pte Ltd reserve the right to revise the prices should the quantity ordered and/or called up differ from the above.",
        style_condition))
    story.append(Paragraph(
        "● Note : Additional Services & Material not listed in the above quotation will be considered variation order and will be quoted separately upon request.",
        style_condition))
    story.append(Paragraph(
        "● Note : Please be informed that unless payment is received in full, CNI Technology Pte Ltd will remain as the rightful owner of the delivered equipment(s)/material(s) on site.",
        style_condition))
    story.append(Paragraph(
        "● Note : All cancellation of order after receiving of Purchase Order or Confirmation will be subjected to 40% charge of the contract sum.",
        style_condition))
    story.append(Spacer(1, 10))
    style_sign_des = ParagraphStyle(name='right', fontSize=10, parent=styleSheet['Normal'])
    quotation_signname = '''
        <para align=left>
            <font size=10><b>Authorised Name:</b>  %s</font>
        </para>
    ''' % (request.user.username)
    currentdate = date.today().strftime("%d-%m-%Y")
    quotation_date = '''
        <para align=left>
            <font size=10><b>Date:</b>  %s</font>
        </para>
    ''' % (currentdate)
    style_sign = ParagraphStyle(name='right', fontSize=10, parent=styleSheet['Normal'])
    sign_title = '''
        <para align=left>
            <font size=10><b>Authorised  Signature: </b></font>
        </para>
    '''
    if request.user.signature:
        sign_logo = Image('http://' + domain + request.user.signature.url, width=0.8 * inch, height=0.8 * inch,
                          hAlign='LEFT')
    else:
        sign_logo = Image('http://' + domain + '/static/assets/images/printlogo.png', hAlign='LEFT')

    # story.append(PageBreak())
    # story.append(Spacer(1, 16))

    approvalD = Table(
        [
            [Paragraph('''<para align=left><font size=13><i><b>Customer's Approval</b></i></font></para>''')],
            [Paragraph("We confirm and accept your above quotation. Kindly proceed with our order.", style_sign_des)],
            # [Paragraph(quotation_signname, style_sign),"", Paragraph(quotation_date, style_sign)],
            # [Paragraph(sign_title, style_sign), sign_logo]
            [Paragraph('''<para align=left><font size=10><b>Authorised Name:</b></font></para>''', style_sign), "",
             Paragraph('''<para align=left><font size=10><b>Date:</b></font></para>''', style_sign)],
            [Paragraph('''<para align=left><font size=10><b>Authorised  Signature:</b></font></para>''', style_sign),
             "", Paragraph("", style_sign)],
            ["", "", ""],
            ["", "", ""],
            ["", "", ""],
        ],
        style=[
            ('BACKGROUND', (0, 0), (0, 0), "#5a9bd5"),
            ('BOX', (0, 0), (2, -1), 0.5, colors.black),
            ('SPAN', (0, 0), (2, 0)),
            ('SPAN', (0, 1), (2, 1)),
            ('VALIGN', (0, -1), (0, -1), 'TOP'),
            ('VALIGN', (0, 0), (0, 0), 'TOP'),
            ('LINEABOVE', (0, 1), (2, 1), 0.5, colors.black),
            ('SPAN', (1, 1), (-1, 1)),
        ],
    )
    approvalD._argW[0] = 1.8 * inch
    approvalD._argW[1] = 1.8 * inch
    approvalD._argW[2] = 3.72 * inch
    approvalD._argH[0] = 0.32 * inch
    approvalD._argH[1] = 0.32 * inch
    approvalD._argH[2] = 0.32 * inch
    # if quotationitems.exists():
    #     story.append(PageBreak())
    #     story.append(Spacer(1, 16))

    story.append(approvalD)
    doc.build(story, canvasmaker=NumberedCanvas, onFirstPage=partial(header, quotation=quotation),
              onLaterPages=partial(header, quotation=quotation))

    response.write(buff.getvalue())
    buff.close()
    return response


def exportExcelQuotation(request, value):
    response = HttpResponse(content_type='application/ms-excel')
    currentdate = date.today()
    excelname = "ERP-SOLUTION-Quotation-" + currentdate.strftime("%d-%m-%Y") + ".xls"
    response['Content-Disposition'] = 'attachment; filename={}'.format(excelname)
    wb = xlwt.Workbook(encoding='utf-8')
    ws = wb.add_sheet('Quotation')
    row_num = 0

    font_style = xlwt.XFStyle()
    font_style.font.bold = True
    columns = ['Quotation No', 'Company name', 'Contact Person', 'Email', 'Tel', 'Fax', 'RE', 'Sale Type',
               'Sale Person', 'Date', 'Status']
    for col_num in range(len(columns)):
        ws.write(row_num, col_num, columns[col_num], font_style)
    # Sheet body, remaining rows
    font_style = xlwt.XFStyle()
    rows = Quotation.objects.filter(id=value).values_list('qtt_id', 'company_nameid', 'contact_person', 'email', 'tel',
                                                          'fax', 'note', 'sale_type', 'sale_person', 'date',
                                                          'qtt_status')
    for row in rows:
        row_num += 1
        for col_num in range(len(row)):
            if isinstance(row[col_num], datetime.date) == True:
                temp = list(row)
                temp[col_num] = temp[col_num].strftime('%d %b, %Y')
                row = tuple(temp)
            ws.write(row_num, col_num, row[col_num], font_style)

    wb.save(response)
    return response
