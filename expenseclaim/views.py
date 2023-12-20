import datetime
import os
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate
from functools import partial

from django.conf import settings
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.views.generic.list import ListView
from accounts.models import User, NotificationPrivilege
from expenseclaim.models import ExpensesClaim, ExpensesClaimDetail, ExpensesClaimRecipt
from project.models import Project
from sales.decorater import ajax_login_required
from django.db import IntegrityError
from django.http import HttpResponse, JsonResponse
import json
from django.views.generic.detail import DetailView
from django.db.models import Sum
from notifications.signals import notify
from reportlab.platypus import SimpleDocTemplate, Table, Image, Spacer, TableStyle, PageBreak, Paragraph
from reportlab.lib import colors
from reportlab.lib.units import inch, cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from io import BytesIO
from reportlab.lib.pagesizes import A4, landscape, portrait
from reportlab.pdfgen import canvas
from reportlab.rl_config import defaultPageSize
from reportlab.lib.utils import ImageReader

# Create your views here.
@method_decorator(login_required, name='dispatch')
class ExpenseClaimView(ListView):
    model = ExpensesClaim
    template_name = "userprofile/expensesclaim-list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        expensesclaims = ExpensesClaim.objects.filter(emp_id=self.request.user.empid)
        for expensesclaim in expensesclaims:
            emp_id=expensesclaim.emp_id
            emp_user=User.objects.get(empid=emp_id)
            result_str=str(emp_id)+"-"+emp_user.first_name
            expensesclaim.emp_id=result_str
        context['expensesclaims'] =expensesclaims
        return context

@method_decorator(login_required, name='dispatch')
class ExpenseAdminClaimView(ListView):
    model = ExpensesClaim
    template_name = "accounts/all-expensesclaim-list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        expensesclaims = ExpensesClaim.objects.filter(status__in=["Pending", "Verified", "Approved", "Rejected"])
        for expensesclaim in expensesclaims:
            emp_id=expensesclaim.emp_id
            emp_user=User.objects.get(empid=emp_id)
            result_str=str(emp_id)+"-"+emp_user.first_name
            expensesclaim.emp_id=result_str
        context['expensesclaims'] =expensesclaims
        return context

@method_decorator(login_required, name='dispatch')
class ExpenseAdminClaimDetailView(DetailView):
    model = ExpensesClaim
    template_name="accounts/all-expense-detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        content_pk = self.kwargs.get('pk')
        context['projects'] = Project.objects.filter(proj_status="On-going")
        context['managerusers'] = User.objects.filter(role__exact="Managers")
        context['admin_manager_users'] = User.objects.filter(role__in=["Managers", "Admins"])
        expenseclaim= ExpensesClaim.objects.get(id=content_pk)
        context['expenseclaim'] = expenseclaim
        context['submitedUser'] = User.objects.get(empid=expenseclaim.emp_id)
        context['expense_claim_pk'] = content_pk
        expensesclaim_details = ExpensesClaimDetail.objects.filter(expensesclaim_id=content_pk)
        context['expensesclaim_details'] = expensesclaim_details
        for claim_detail in expensesclaim_details:
            proj=Project.objects.get(id=int(claim_detail.proj_id))
            claim_detail.proj_id=proj.proj_id
        if ExpensesClaimDetail.objects.filter(expensesclaim_id=content_pk).exists():
            subtotal = ExpensesClaimDetail.objects.filter(expensesclaim_id=content_pk).aggregate(Sum('amount'))['amount__sum']
            gst_sum = 0
            for gstrow in expensesclaim_details:
                if gstrow.gst:
                    gst_sum += float('{0:.2f}'.format(gstrow.amount * 0.08))
                    gstrow.gstamount = '{0:.2f}'.format(gstrow.amount * 0.08)
            context['subtotal'] = subtotal
            context['gst'] = gst_sum
            context['total_detail'] = subtotal + gst_sum
        context['expensesclaim_files'] = ExpensesClaimRecipt.objects.filter(emp_id_id=content_pk)
        return context

def send_mail(to_email, subject, message):
    # For Gmail
    SMTP_SERVER = "smtp.gmail.com"
    SMTP_PORT = 587
    my_email = os.getenv("DJANGO_DEFAULT_EMAIL")
    my_password=os.getenv("DJANGO_EMAIL_HOST_PASSWORD")
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
def expensesclaimadd(request):
    if request.method == "POST":
        claim_no = request.POST.get('claim_no')
        submission_date = request.POST.get('submission_date')
        emp_id = request.POST.get('emp_id')
        status=request.POST.get('exp_status')
        amount = request.POST.get('amount')
        expense_name = request.POST.get("expense_name")
        
        expensesid = request.POST.get('expensesid')
        if expensesid == "-1":
            if ExpensesClaim.objects.filter(ec_id=claim_no).exists():
                return JsonResponse({
                    "status": "Error",
                    "messages": "This id has been taken by others, please close current window and create again.",
                })
            else:
                try:
                    expenseclaim = ExpensesClaim.objects.create(
                        submission_date=submission_date,
                        emp_id=emp_id,
                        status="Open",
                        #total=total,
                        ec_id=claim_no,
                        expenses_name=expense_name
                    )
                    return JsonResponse({
                        "status": "Success",
                        "messages": "Expenses Claim created!",
                        "expenseclaimid": expenseclaim.id,
                    })
                except IntegrityError as e:
                    return JsonResponse({
                        "status": "Error",
                        "messages": "Error is existed!"
                    })
        else:
            try:
                expenses = ExpensesClaim.objects.get(id=expensesid)
                expenses.submission_date = submission_date
                expenses.emp_id = emp_id
                expenses.status=status
                expenses.total = amount

                expenses.ec_id = claim_no
                expenses.expenses_name= expense_name
                expenses.save()

                return JsonResponse({
                    "status": "Success",
                    "messages": "Expenses Claim information updated!"
                })

            except IntegrityError as e: 
                return JsonResponse({
                    "status": "Error",
                    "messages": "Error is existed!"
                })

@ajax_login_required
def expenseClaimdelete(request):
    if request.method == "POST":
        expensesid = request.POST.get('expensesid')
        expenses = ExpensesClaim.objects.get(id=expensesid)
        expensesDetail = ExpensesClaimDetail.objects.filter(expensesclaim=expensesid)
        expensesFile = ExpensesClaimRecipt.objects.filter(emp_id=expensesid)
        expensesFile.delete()
        expensesDetail.delete()
        expenses.delete()

        return JsonResponse({'status': 'ok'})

@ajax_login_required
def expenseClaimItemdelete(request):
    if request.method == "POST":
        itemdetailid = request.POST.get('itemdetailid')
        expensesitem = ExpensesClaimDetail.objects.get(id=itemdetailid)
        expensesitem.delete()
        if ExpensesClaimDetail.objects.filter(expensesclaim_id=expensesitem.expensesclaim_id).exists():
            subtotal = ExpensesClaimDetail.objects.filter(expensesclaim_id=expensesitem.expensesclaim_id).aggregate(Sum('amount'))['amount__sum']
            gst_sum = 0
            for gstrow in ExpensesClaimDetail.objects.filter(id=expensesitem.expensesclaim_id):
                if gstrow.gst:
                    gst_sum += gstrow.amount * 0.08
            if ExpensesClaim.objects.filter(id=expensesitem.expensesclaim_id):
                expense_amount = ExpensesClaim.objects.get(id=expensesitem.expensesclaim_id)
                expense_amount.total = subtotal + gst_sum
                expense_amount.save()
        else:
            if ExpensesClaim.objects.filter(id=expensesitem.expensesclaim_id):
                expense_amount = ExpensesClaim.objects.get(id=expensesitem.expensesclaim_id)
                expense_amount.total = 0
                expense_amount.save()
        

        return JsonResponse({'status': 'ok'})

@ajax_login_required
def expenseClaimFiledelete(request):
    if request.method == "POST":
        fileid = request.POST.get('fileid')
        expenses = ExpensesClaimRecipt.objects.get(id=fileid)
        expenses.delete()

        return JsonResponse({'status': 'ok'})

@ajax_login_required
def getExpensesClaim(request):
    if request.method == "POST":
        expensesid = request.POST.get('expensesid')
        expenses = ExpensesClaim.objects.get(id=expensesid)
        emp_user = User.objects.get(empid=expenses.emp_id)
        result_empid = str(expenses.emp_id) + "-" + emp_user.first_name
        context['expensesclaims'] =expensesclaims
        data = {
            'submission_date': expenses.submission_date.strftime('%d %b, %Y'),
            'emp_id': result_empid,
            'total': expenses.total,
            'claim_no': expenses.ec_id,
        }
        return JsonResponse(json.dumps(data), safe=False)

@method_decorator(login_required, name='dispatch')
class ExpenseClaimDetailView(DetailView):
    model = ExpensesClaim
    template_name="userprofile/expenses-claim-detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        content_pk = self.kwargs.get('pk')
        context['projects'] = Project.objects.filter(proj_status__in=["On-going", "Completed"])
        expenseclaim= ExpensesClaim.objects.get(id=content_pk)
        context['expenseclaim'] = expenseclaim
        context['submitedUser'] = User.objects.get(empid=expenseclaim.emp_id)
        context['managerusers'] = User.objects.filter(role__exact="Managers")
        context['admin_manager_users'] = User.objects.filter(role__in=["Managers", "Admins"])
        context['expense_claim_pk'] = content_pk
        expensesclaim_details = ExpensesClaimDetail.objects.filter(expensesclaim_id=content_pk)
        for claim_detail in expensesclaim_details:
            proj=Project.objects.get(id=int(claim_detail.proj_id))
            claim_detail.proj_id=proj.proj_id

        if ExpensesClaimDetail.objects.filter(expensesclaim_id=content_pk).exists():
            subtotal = ExpensesClaimDetail.objects.filter(expensesclaim_id=content_pk).aggregate(Sum('amount'))['amount__sum']
            gst_sum = 0
            for gstrow in expensesclaim_details:
                if gstrow.gst:
                    gst_sum += gstrow.amount * 0.08
                    gstrow.gstamount = '{0:.2f}'.format(gstrow.amount * 0.08)
            
            context['subtotal'] = subtotal
            context['gst'] = gst_sum
            context['total_detail'] = subtotal + gst_sum
        context['expensesclaim_details'] = expensesclaim_details
        context['expensesclaim_files'] = ExpensesClaimRecipt.objects.filter(emp_id_id=content_pk)
        return context

@ajax_login_required
def check_expenses_number(request):
    if request.method == "POST":
        if ExpensesClaim.objects.all().exists():
            expenses= ExpensesClaim.objects.all().order_by('-ec_id')[0]
            data = {
                "status": "exist",
                "expenses": expenses.ec_id
            }
        
            return JsonResponse(data)
        else:
            data = {
                "status": "no exist"
            }
        
            return JsonResponse(data)

@ajax_login_required
def UpdateExpenses(request):
    if request.method == "POST":
        emp_id = request.POST.get('emp_id')
        expense_name = request.POST.get('expense_name')
        submission_date = request.POST.get('submission_date')
        exp_status = request.POST.get('exp_status')
        approveby = request.POST.get('approveby')
        verifiedby = request.POST.get('verifiedby')
        total=request.POST.get('amount')
        ec_id = request.POST.get('ec_id')
        if total=="":
            total=0
        expenseid = request.POST.get('expenseid')

        try:
            expenses = ExpensesClaim.objects.get(id=expenseid)
            expenses.ec_id = ec_id
            expenses.approveby_id = approveby
            expenses.verifiedby_id = verifiedby
            expenses.submission_date = submission_date
            expenses.status = exp_status
            expenses.expenses_name = expense_name
            expenses.emp_id = emp_id
            expenses.total = total
            expenses.save()

            if exp_status=="Pending":
                #notification send
                sender = request.user
                is_email = NotificationPrivilege.objects.get(user_id=sender.id).is_email
                description = '<a href="/expenses-claim-detail/'+str(expenseid)+'">New Claim No : ' + ec_id +  ' was created by ' + request.user.username+'</a>'
                for receiver in User.objects.filter(role__in=['Managers', 'Admins']):
                    if receiver.notificationprivilege.claim_submitted:
                        notify.send(sender, recipient=receiver, verb='Message', level="success", description=description)
                        if is_email and receiver.email:
                            send_mail(receiver.email, "Notification for Expense Claim No ", description)
            return JsonResponse({
                "status": "Success",
                "messages": "Expenses Claim information updated!"
            })

        except IntegrityError as e: 
            print(e)
            return JsonResponse({
                "status": "Error",
                "messages": "Error is existed!"
            })

@ajax_login_required
def expensesclaimdetailsadd(request):
    if request.method == "POST":
        proj_id = request.POST.get('proj_id')
        vendor = request.POST.get('vendor')
        description = request.POST.get('description')
        detail_amount = request.POST.get('detail_amount')
        detail_date = request.POST.get('detail_date')
        remark = request.POST.get('remark')
        gstst = request.POST.get('detail_gst')
        detailid = request.POST.get('detailid')
        if gstst == "true":
            gststatus = True
        else:
            gststatus = False
        
        expenseid = request.POST.get('expenseid')
        if detailid == "-1":
            try:
                ExpensesClaimDetail.objects.create(
                    proj_id=proj_id,
                    vendor=vendor,
                    description=description,
                    amount=detail_amount,
                    date=detail_date,
                    gst=gststatus,
                    remark=remark,
                    expensesclaim_id=expenseid
                )
                if ExpensesClaimDetail.objects.filter(expensesclaim_id=expenseid).exists():
                    subtotal = ExpensesClaimDetail.objects.filter(expensesclaim_id=expenseid).aggregate(Sum('amount'))['amount__sum']
                    gst_sum = 0
                    for gstrow in ExpensesClaimDetail.objects.filter(expensesclaim_id=expenseid):
                        if gstrow.gst:
                            gst_sum += gstrow.amount * 0.08
                            gstrow.gstval = gstrow.amount * 0.08
                    
                    if ExpensesClaim.objects.filter(id=expenseid):
                        expense_amount = ExpensesClaim.objects.get(id=expenseid)
                        expense_amount.total = subtotal + gst_sum
                        expense_amount.save()
                return JsonResponse({
                    "status": "Success",
                    "messages": "Expenses Claim Detail information added!"
                })
            except IntegrityError as e: 
                return JsonResponse({
                    "status": "Error",
                    "messages": "Error is existed!"
                })
        else:
            try:
                expensedetail = ExpensesClaimDetail.objects.get(id=detailid)
                expensedetail.proj_id=proj_id
                expensedetail.vendor=vendor
                expensedetail.description=description
                expensedetail.amount=detail_amount
                expensedetail.date=detail_date
                expensedetail.gst=gststatus
                expensedetail.remark=remark
                expensedetail.expensesclaim_id=expenseid
                expensedetail.save()
                
                if ExpensesClaimDetail.objects.filter(expensesclaim_id=expenseid).exists():
                    subtotal = ExpensesClaimDetail.objects.filter(expensesclaim_id=expenseid).aggregate(Sum('amount'))['amount__sum']
                    gst = subtotal * 0.08
                    
                    if ExpensesClaim.objects.filter(id=expenseid):
                        expense_amount = ExpensesClaim.objects.get(id=expenseid)
                        expense_amount.total = subtotal + gst
                        expense_amount.save()
                return JsonResponse({
                    "status": "Success",
                    "messages": "Expenses Claim Detail information Updated!"
                })
            except IntegrityError as e: 
                return JsonResponse({
                    "status": "Error",
                    "messages": "Error is existed!"
                })
        
@ajax_login_required
def expensesclaimfilesadd(request):
    if request.method == "POST":
        receipt_no = request.POST.get('receipt_no')
        fileid = request.POST.get('fileid')
        expenseid = request.POST.get('expenseid')
        if fileid == "-1":
            try:

                ExpensesClaimRecipt.objects.create(
                    receipt_no=receipt_no,
                    receipt_file = request.FILES.get('receipt_file'),
                    receipt_name = request.FILES['receipt_file'],
                    emp_id_id=expenseid,
                    upload_by = request.user.username
                )
                return JsonResponse({
                    "status": "Success",
                    "messages": "Expenses Claim Detail information added!"
                })
            except IntegrityError as e: 
                return JsonResponse({
                    "status": "Error",
                    "messages": "Error is existed!"
                })

def exportClaimPDF(request, value):
    ecm = ExpensesClaim.objects.get(id=value)    
    domain = request.META['HTTP_HOST']
    logo = Image('http://' + domain + '/static/assets/images/printlogo.png', hAlign='LEFT')
    response = HttpResponse(content_type='application/pdf')
    currentdate = datetime.date.today().strftime("%d-%m-%Y")
    pdfname = ecm.ec_id + ".pdf"
    response['Content-Disposition'] = 'attachment; filename="{}"'.format(pdfname)
    story = []
    buff = BytesIO()
    doc = SimpleDocTemplate(buff, pagesize=landscape(A4), rightMargin=0.25*inch, leftMargin=0.45*inch, topMargin=2.5*inch, bottomMargin=0.25*inch, title=pdfname)
    styleSheet=getSampleStyleSheet()
    ecm_data = [
        [Paragraph('''<para align=center><font size=10><b>S/N</b></font></para>'''),
         Paragraph('''<para align=center><font size=10><b>Date</b></font></para>'''),
         Paragraph('''<para align=center><font size=10><b>Project No</b></font></para>'''),
         Paragraph('''<para align=center><font size=10><b>Vendor</b></font></para>'''),
         Paragraph('''<para align=center><font size=10><b>Description</b></font></para>'''),
         Paragraph('''<para align=center><font size=10><b>GST 8%</b></font></para>'''),
         Paragraph('''<para align=center><font size=10><b>Amount (w/o GST)</b></font></para>'''),
         Paragraph('''<para align=center><font size=10><b>Sub Total</b></font></para>'''),
         Paragraph('''<para align=center><font size=10><b>Remark</b></font></para>''')]
    ]
    ecmitems = ExpensesClaimDetail.objects.filter(expensesclaim_id=value)
    for claim_detail in ecmitems:
        proj = Project.objects.get(id=int(claim_detail.proj_id))
        claim_detail.proj_id = proj.proj_id
    index = 1
    if ecmitems.exists():
        total_gst = 0
        total_amount = 0
        total_subtotal = 0
        for ecmitem in ecmitems:
            temp_data = []
            description = '''
                <para align=left>
                    %s
                </para>
            ''' % (str(ecmitem.description))
            if ecmitem.remark:
                eremark = ecmitem.remark
            else:
                eremark = ""
            ecmdes = Paragraph(description, styleSheet["BodyText"])
            remark = '''
                <para align=left>
                    %s
                </para>
            ''' % (eremark)
            ecmremark = Paragraph(remark, styleSheet["BodyText"])
            temp_data.append(str(index))
            temp_data.append(ecmitem.date.strftime("%d-%m-%Y"))
            temp_data.append(ecmitem.proj_id)
            temp_data.append(Paragraph(ecmitem.vendor, styleSheet["BodyText"]))
            temp_data.append(ecmdes)
            if ecmitem.gst:
                gstval = '{0:.2f}'.format(ecmitem.amount * 0.08)
                total_gst += ecmitem.amount * 0.08
                total_amount += ecmitem.amount
                total_subtotal += ecmitem.amount * 1.08
                subtotal = '{0:.2f}'.format(ecmitem.amount * 1.08)
            else:
                gstval = "-"
                total_amount += ecmitem.amount
                total_subtotal += ecmitem.amount
                subtotal = '{0:.2f}'.format(ecmitem.amount)
            temp_data.append("$ "+gstval)
            temp_data.append("$ "+'{0:.2f}'.format(ecmitem.amount))
            temp_data.append("$ "+str(subtotal))
            temp_data.append(ecmremark)
            ecm_data.append(temp_data)
            index += 1
        ecm_data.append(["", "", "", "", "Total", "$ " + '{0:.2f}'.format(total_gst), "$ " +  '{0:.2f}'.format(total_amount), "$ " +  '{0:.2f}'.format(total_subtotal), ""])
        ecmtable = Table(
            ecm_data,
            style=[
                ('BACKGROUND', (0, 0), (-1, 0), "#5a9bd5"),
                ('GRID',(0,0),(-1,-1),0.5,colors.black),
                ('VALIGN',(0,0),(-1,-1),'TOP'),
                ('VALIGN',(0,0),(-1,0),'MIDDLE'),
                ('ALIGN',(0,0),(-1,-1),'LEFT'),
                ('ALIGN', (0, 0), (1, -1), 'CENTER'),
            ],
        )
    else:
        ecm_data.append(["No data available in table", "", "", "", "", "","", "",""])

        ecmtable = Table(
            ecm_data,
            style=[
                ('BACKGROUND', (0, 0), (-1, 0), "#5a9bd5"),
                ('GRID',(0,0),(-1,-1),0.5,colors.black),
                ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
                ('ALIGN',(0,0),(-1,-1),'CENTER'),
                ('SPAN',(0,1),(-1,-1)),
            ],
        )
    
    ecmtable._argW[0]=0.40*inch
    ecmtable._argW[1]=1.0388*inch
    ecmtable._argW[2]=1.0388*inch
    ecmtable._argW[3]=1.0388*inch
    ecmtable._argW[4]=3.73*inch
    ecmtable._argW[5]=0.732*inch
    ecmtable._argW[6]=0.832*inch
    ecmtable._argW[7]=0.832*inch
    ecmtable._argW[8]=1.0388*inch
    ecmtable._argH[0]=0.40*inch
    story.append(ecmtable)
    story.append(Spacer(1, 10))

    if len(ecmitems)>5:
        story.append(PageBreak())
    sign_title1 = '''
        <para align=left>
            <font size=10><u><b>Name/Signature </b></u></font>
        </para>
    '''
    sign_title2 = '''
        <para align=left>
            <font size=10><u><b>Name/Signature </b></u></font>
        </para>
    '''
    sign_title3 = '''
        <para align=left>
            <font size=10><u><b>Name/Signature </b></u></font>
        </para>
    '''
    submitted_by = User.objects.get(empid=ecm.emp_id)
    if request.user.signature:
        sign_logo = Image('http://' + domain + submitted_by.signature.url, width=1.2*inch, height=0.8*inch, hAlign='LEFT')
    else:
        sign_logo = ""
        # sign_logo = Image('http://' + domain + '/static/assets/images/logo.png', hAlign='LEFT')
    ecmtable1=Table(
        [
            [Paragraph('''<para align=left><font size=12><b>Submitted By: </b></font></para>'''),"",Paragraph('''<para align=left><font size=12><b>Verified By:</b></font></para>'''),"", Paragraph('''<para align=left><font size=12><b>Approved By:</b></font></para>''')],
        ],
        style=[
            ('VALIGN',(0,0),(0,-1),'TOP'),
        ],
    )
    ecmtable1._argW[0]=3.00*inch
    ecmtable1._argW[1]=1.00*inch
    ecmtable1._argW[2]=3.00*inch
    ecmtable1._argW[3]=1.00*inch
    ecmtable1._argW[4]=3.00*inch
    story.append(ecmtable1)
    if ecm.approveby:
        if ecm.approveby.signature:
            approve_logo = Image('http://' + domain + ecm.approveby.signature.url, width=1.2*inch, height=0.8*inch, hAlign='LEFT')
            approve_name = ecm.approveby.username
        else:
            approve_name = ""
            approve_logo = ""
            # approve_logo = Image('http://' + domain + '/static/assets/images/logo.png', hAlign='LEFT')
    else:
        approve_name = ""
        approve_logo = ""
        # approve_logo = Image('http://' + domain + '/static/assets/images/logo.png', hAlign='LEFT')

    if ecm.verifiedby:
        if ecm.verifiedby.signature:
            verify_logo = Image('http://' + domain + ecm.verifiedby.signature.url, width=1.2*inch, height=0.8*inch, hAlign='LEFT')
            verify_name = ecm.verifiedby.username
        else:
            verify_logo = ""
            verify_name = ""
    else:
        verify_logo = ""
        verify_name = ""
    ecmtable3=Table(
        [
            [sign_logo , "" , verify_logo, "", approve_logo],
            [Paragraph('''<para align=left><font size=9>%s</font></para>''' % (submitted_by.username)),
             "",
             Paragraph('''<para align=left><font size=9>%s</font></para>''' % (verify_name)),
             "",
             Paragraph('''<para align=left><font size=9>%s</font></para>''' % (approve_name))]
        ],
        style=[
            ('VALIGN',(0,0),(-1,-1),'TOP'),
        ],
    )
    story.append(Spacer(1, 10))
    ecmtable3._argW[0]=3.0*inch
    ecmtable3._argW[1]=1.00*inch
    ecmtable3._argW[2]=3.0*inch
    ecmtable3._argW[3]=1.00*inch
    ecmtable3._argW[4]=3.0*inch
    story.append(ecmtable3)
    ecmtable4=Table(
        [
            [Paragraph(sign_title1), "",Paragraph(sign_title3), "", Paragraph(sign_title2)],
        ],
        style=[
            ('VALIGN',(0,0),(-1,-1),'TOP'),
        ],
    )
    story.append(Spacer(1, 10))
    ecmtable4._argW[0]=3.0*inch
    ecmtable4._argW[1]=1.00*inch
    ecmtable4._argW[2]=3.0*inch
    ecmtable4._argW[3]=1.00*inch
    ecmtable4._argW[4]=3.0*inch
    story.append(ecmtable4)
    
    doc.build(story, canvasmaker=LandScapeNumberedCanvas, onFirstPage=partial(header, ecm=ecm), onLaterPages=partial(header, ecm=ecm))
    response.write(buff.getvalue())
    buff.close()

    return response

def header(canvas, doc, ecm):
    RIGHT_X = 680
    CONTENT_PADDING=10
    LEFT_X_1 = 40
    LEFT_X_2 = 120
    LEFT_X_3 = 220
    LEFT_X_4 = 250
    TOP_MARGIN = 120
    LINE_SPACE = 17

    if ecm.total:
        total = '%.2f' % float(ecm.total)
    else:
        total = '%.2f' % float(0)
    if ecm.status:
        status = ecm.status
    else:
        status = ""

    canvas.saveState()
    canvas.setFont("Helvetica-Bold", 16)
    canvas.drawString(RIGHT_X, canvas.PAGE_HEIGHT - TOP_MARGIN, "Expenses Claim")
    canvas.setFont("Helvetica-Bold", 10)
    canvas.drawString(RIGHT_X, canvas.PAGE_HEIGHT - TOP_MARGIN - LINE_SPACE, "EC No:")
    canvas.drawString(RIGHT_X, canvas.PAGE_HEIGHT - TOP_MARGIN - 2 * LINE_SPACE, "Date:")
    canvas.drawString(RIGHT_X, canvas.PAGE_HEIGHT - TOP_MARGIN - 3 * LINE_SPACE, "Status:")
    canvas.setFont("Helvetica", 10)
    canvas.drawString(RIGHT_X+6*CONTENT_PADDING, canvas.PAGE_HEIGHT - TOP_MARGIN - LINE_SPACE, "%s" % (ecm.ec_id))
    canvas.drawString(RIGHT_X+6*CONTENT_PADDING, canvas.PAGE_HEIGHT - TOP_MARGIN - 2*LINE_SPACE, "%s" % (ecm.submission_date.strftime('%d/%m/%Y')))
    canvas.drawString(RIGHT_X+6*CONTENT_PADDING, canvas.PAGE_HEIGHT - TOP_MARGIN - 3*LINE_SPACE, "%s" % (status))

    canvas.setFont("Helvetica-Bold", 10)
    canvas.drawString(LEFT_X_1, canvas.PAGE_HEIGHT - TOP_MARGIN , "Emp No:")
    canvas.drawString(LEFT_X_1, canvas.PAGE_HEIGHT - TOP_MARGIN - 1 * LINE_SPACE, "Name:")
    canvas.drawString(LEFT_X_1, canvas.PAGE_HEIGHT - TOP_MARGIN - 2 * LINE_SPACE, "Total Amount:")
    canvas.setFont("Helvetica", 10)
    canvas.drawString(LEFT_X_2, canvas.PAGE_HEIGHT - TOP_MARGIN , "%s" % (ecm.emp_id))
    canvas.drawString(LEFT_X_2, canvas.PAGE_HEIGHT - TOP_MARGIN - 1*LINE_SPACE, "%s" % (ecm.expenses_name))
    canvas.drawString(LEFT_X_2, canvas.PAGE_HEIGHT - TOP_MARGIN - 2*LINE_SPACE, "$ %s" % (total))
    canvas.restoreState()

class LandScapeNumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []
        self.PAGE_HEIGHT=defaultPageSize[0]
        self.PAGE_WIDTH=defaultPageSize[1]
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
        self.drawRightString(self.PAGE_WIDTH/2.0 + 10, 0.35 * inch,
            "Page %d of %d" % (self._pageNumber, page_count))

@ajax_login_required
def getExpenseItem(request):
    if request.method == "POST":
        exidetailid = request.POST.get('exidetailid')
        expitem = ExpensesClaimDetail.objects.get(id=exidetailid)
        data = {
            'date': expitem.date.strftime('%d %b, %Y'),
            'proj_id': expitem.proj_id,
            'vendor': expitem.vendor,
            'description': expitem.description,
            'amount': expitem.amount,
            'remark': expitem.remark,
            'gst': expitem.gst,

        }
        return JsonResponse(json.dumps(data), safe=False)


@ajax_login_required
def checkReceiptNo(request):
    if request.method == "POST":
        if ExpensesClaimRecipt.objects.all().exists():
            exp = ExpensesClaimRecipt.objects.all().order_by('-receipt_no')[0]
            data = {
                "status": "exist",
                "receipt_no": exp.receipt_no.replace('CRN', '').split()[0]
            }

            return JsonResponse(data)
        else:
            data = {
                "status": "no exist"
            }

            return JsonResponse(data)

