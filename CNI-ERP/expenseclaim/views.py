import datetime
import os
from functools import partial
from django.conf import settings
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.views.generic.list import ListView
from accounts.models import User, NotificationPrivilege, UserStatus
from expenseclaim.models import ExpensesClaim, ExpensesClaimDetail, ExpensesClaimRecipt, InvoiceSummary, InvoiceDetail
from sales.models import Company, GST
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
from accounts.email import send_mail
import numpy as np
import cv2
import pytesseract
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'




def resize_image(image, resize_width):
    height, width, channels = image.shape
    target_width = resize_width
    target_height=int(target_width*height/width)
    image = cv2.resize(image, (target_width, target_height), interpolation=cv2.INTER_LANCZOS4)
    return image

def get_highlighted_area(img, original_mask, resize_width):
    kernel = np.ones((7, 7), np.uint8)  # Adjust the size for larger/smaller gaps
    # Apply closing to fill the gaps
    mask = cv2.morphologyEx(original_mask, cv2.MORPH_CLOSE, kernel)
    # Find contours in the masked image
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    h_areas=[]

    # Iterate over contours and filter by rectangular shape
    for contour in contours:
        # Approximate the contour to a polygon
        epsilon = 0.02 * cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, epsilon, True)
        min_contour_area = 500  # You can adjust this value as needed
        # Check if the polygon has 4 vertices (rectangle)
        if cv2.contourArea(contour) > min_contour_area and len(approx) == 4:
            # Get the bounding box of the rectangle
            x, y, w, h = cv2.boundingRect(approx) 
            roi = img[y:y+h, x:x+w]
            roi=resize_image(roi, resize_width)

            # Create a kernel
            kernel_size=int(resize_width)
            h_kernel = np.ones((1, kernel_size), np.uint8)
            h_mask = cv2.morphologyEx(roi, cv2.MORPH_CLOSE, h_kernel)
            h_mask = cv2.cvtColor(h_mask, cv2.COLOR_BGR2GRAY)

            v_kernel = np.ones((kernel_size, 1), np.uint8)
            v_mask = cv2.morphologyEx(roi, cv2.MORPH_CLOSE, v_kernel)
            v_mask = cv2.cvtColor(v_mask, cv2.COLOR_BGR2GRAY)
            # Subtract the closed image from the original to remove the lines
            roi[h_mask <240] = [255, 255, 255]  # Set to white (BGR format)
            roi[v_mask <240] = [255, 255, 255]  # Set to white (BGR format)
            
            gray_roi=cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            # Apply Gaussian blur to smooth the image
            blurred = cv2.GaussianBlur(gray_roi, (5, 5), 0)
            h_areas.append(blurred)
    return h_areas

def parse_text(img):
    
    hsv_img = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)    
    string_config = r'--oem 3 --psm 6' 
    digit_config = r'--oem 3 --psm 6 outputbase digits'
    # ------------For Price----------------
    lower_price = np.array([70, 50, 150])
    upper_price = np.array([120, 255, 255])    
    price_mask = cv2.inRange(hsv_img, lower_price, upper_price)
    price_areas=get_highlighted_area(img, price_mask, 256)
    
    # ------------For Qty----------------            
    lower_qty = np.array([20, 50, 150])
    upper_qty = np.array([35, 255, 255])
    qty_mask = cv2.inRange(hsv_img, lower_qty, upper_qty)
    qty_areas= get_highlighted_area(img, qty_mask, 128)

    # ------------For Description----------------            
    lower_description = np.array([150, 50, 150])
    upper_description = np.array([170, 255, 255])   
    description_mask = cv2.inRange(hsv_img, lower_description, upper_description)
    description_areas= get_highlighted_area(img, description_mask, 1024)

    prices=[]
    qtys=[]
    descriptions=[]

    if len(price_areas)>=2:
        for i, price_area in enumerate(price_areas):
            price_text = pytesseract.image_to_string(price_areas[i], config=digit_config).strip()
            qty_text = pytesseract.image_to_string(qty_areas[i], config=digit_config).strip()
            description_text = pytesseract.image_to_string(description_areas[i], config=string_config).strip()
            prices.append(price_text)
            qtys.append(qty_text)
            descriptions.append(description_text)
    else:
        price_data = pytesseract.image_to_data(price_areas[0], config=digit_config, output_type=pytesseract.Output.DICT)
        n_boxes = len(price_data['level'])
        y_qty_positions=[]        
        y_desc_positions=[]        
        h_price, w_price=price_areas[0].shape
        h_qty, w_qty =qty_areas[0].shape
        h_desc, w_desc=description_areas[0].shape

        # For price & set y_positions
        for i in range(n_boxes):
            if price_data['text'][i].strip():  # Check if the line contains text
                y_price=price_data['top'][i]
                y_qty_positions.append(max(0, int(y_price*h_qty/h_price)-20))
                y_desc_positions.append(max(0, int(y_price*h_desc/h_price)-20))

                prices.append(price_data['text'][i])
        
        # For qty
        # qty_data = pytesseract.image_to_data(qty_areas[0], config=digit_config, output_type=pytesseract.Output.DICT)
        # n_boxes = len(qty_data['level'])        
        # for i in range(n_boxes):
        #     if price_data['text'][i].strip():
        #         qtys.append(qty_data['text'][i])

        for index, y_position in enumerate(y_qty_positions):
            if index>=len(y_qty_positions)-1:
                height=y_position-y_qty_positions[index-1]
            else:
                height= y_qty_positions[index+1]-y_position
            qty_snap = qty_areas[0][y_position:y_position+height, 0:w_qty]
            text = pytesseract.image_to_string(qty_snap, config=digit_config).strip()
            text=text.replace('\n', ' ')
            qtys.append(text)

        # For descriptions
        for index, y_position in enumerate(y_desc_positions):
            if index>=len(y_desc_positions)-1:
                height=h_desc-y_position
            else:
                height= y_desc_positions[index+1]-y_position
            description_snap = description_areas[0][y_position:y_position+height, 0:w_desc]
            text = pytesseract.image_to_string(description_snap, config=string_config).strip()
            text=text.replace('\n', ' ')
            descriptions.append(text)

    return prices, qtys, descriptions













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
        context['expensesclaims'] = expensesclaims
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
        gst_default=GST.objects.last()
        if gst_default:
            gst_default=float(gst_default.gst)
        else:
            gst_default=0.09
        context['gst_default']=gst_default*100
        for claim_detail in expensesclaim_details:
            proj=Project.objects.get(id=int(claim_detail.proj_id))
            claim_detail.proj_id=proj.proj_id
        if ExpensesClaimDetail.objects.filter(expensesclaim_id=content_pk).exists():
            subtotal = ExpensesClaimDetail.objects.filter(expensesclaim_id=content_pk).aggregate(Sum('amount'))['amount__sum']
            gst_sum = 0
            for gstrow in expensesclaim_details:
                if gstrow.gst:
                    gst_sum += float('{0:.2f}'.format(gstrow.amount * gst_default))
                    gstrow.gstamount = '{0:.2f}'.format(gstrow.amount * gst_default)
            context['subtotal'] = subtotal
            context['gst'] = gst_sum
            context['total_detail'] = subtotal + gst_sum
        context['expensesclaim_files'] = ExpensesClaimRecipt.objects.filter(emp_id_id=content_pk)
        return context
 

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
def invoiceItemdelete(request):
    if request.method == "POST":
        itemdetailid = request.POST.get('itemdetailid')
        invoiceitem = InvoiceDetail.objects.get(id=itemdetailid)
        invoiceitem.delete()
        if InvoiceDetail.objects.filter(invoicesummary_id=invoiceitem.invoicesummary_id).exists():
            subtotal = InvoiceDetail.objects.filter(invoicesummary_id=invoiceitem.invoicesummary_id).aggregate(Sum('amount'))['amount__sum']
            gst_sum = 0
            for gstrow in InvoiceDetail.objects.filter(invoicesummary_id=invoiceitem.invoicesummary_id):
                if gstrow.gst:                    
                    gst_default=GST.objects.last()
                    if gst_default:
                        gst_default=float(gst_default.gst)
                    else:
                        gst_default=0.09
                    gst_sum += gstrow.amount * gst_default
            
            if InvoiceSummary.objects.filter(id=invoiceitem.invoicesummary_id):
                invoice_summary=InvoiceSummary.objects.get(id=invoiceitem.invoicesummary_id)
                invoice_summary.total = subtotal + gst_sum
                invoice_summary.gstamount = gst_sum
                invoice_summary.save()
            if ExpensesClaim.objects.filter(id=invoiceitem.invoicesummary.expensesclaim_id):
                expense_amount = ExpensesClaim.objects.get(id=invoiceitem.invoicesummary.expensesclaim_id)
                subtotal = InvoiceSummary.objects.filter(expensesclaim_id=invoiceitem.invoicesummary.expensesclaim_id).aggregate(Sum('total'))['total__sum']
                expense_amount.total = subtotal
                expense_amount.save()
        else:
            if InvoiceSummary.objects.filter(id=invoiceitem.invoicesummary_id):
                invoice_summary=InvoiceSummary.objects.get(id=invoiceitem.invoicesummary_id)
                invoice_summary.total = 0
                invoice_summary.gstamount = 0
                invoice_summary.save()
            if ExpensesClaim.objects.filter(id=invoiceitem.invoicesummary.expensesclaim_id):
                expense_amount = ExpensesClaim.objects.get(id=invoiceitem.invoicesummary.expensesclaim_id)
                expense_amount.total = 0
                expense_amount.save()
        

        return JsonResponse({'status': 'ok'})

@ajax_login_required
def expenseClaimItemdelete(request):
    if request.method == "POST":
        itemdetailid = request.POST.get('itemdetailid')
        invoicesummary = InvoiceSummary.objects.get(id=itemdetailid)
        invoicesummary.delete()
        if InvoiceSummary.objects.filter(expensesclaim_id=invoicesummary.expensesclaim_id).exists():
            subtotal = InvoiceSummary.objects.filter(expensesclaim_id=invoicesummary.expensesclaim_id).aggregate(Sum('total'))['total__sum']
            
            if ExpensesClaim.objects.filter(id=invoicesummary.expensesclaim_id):
                expense_amount = ExpensesClaim.objects.get(id=invoicesummary.expensesclaim_id)
                expense_amount.total = subtotal
                expense_amount.save()
        else:
            if ExpensesClaim.objects.filter(id=invoicesummary.expensesclaim_id):
                expense_amount = ExpensesClaim.objects.get(id=invoicesummary.expensesclaim_id)
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
        data = {
            'submission_date': expenses.submission_date.strftime('%d %b, %Y'),
            'emp_id': result_empid,
            'total': expenses.total,
            'claim_no': expenses.ec_id,
        }
        return JsonResponse(json.dumps(data), safe=False)

@method_decorator(login_required, name='dispatch')
class ExpenseInvoiceDetailView(DetailView):
    model = InvoiceSummary
    template_name="userprofile/expenses-invoice-detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        content_pk = self.kwargs.get('pk')
        context['invoice_summary_id'] = content_pk
        context['projects'] = Project.objects.filter(proj_status__in=["On-going", "Completed"])
        context['invoice_summary']= InvoiceSummary.objects.get(id=content_pk)
        context['expenseclaim'] = InvoiceSummary.objects.get(id=content_pk).expensesclaim
        invoice_details = InvoiceDetail.objects.filter(invoicesummary_id=content_pk)

        gst_default=GST.objects.last()
        if gst_default:
            gst_default=float(gst_default.gst)
        else:
            gst_default=0.09
        context['gst_default']=gst_default*100

        if InvoiceDetail.objects.filter(invoicesummary_id=content_pk).exists():
            subtotal = InvoiceDetail.objects.filter(invoicesummary_id=content_pk).aggregate(Sum('amount'))['amount__sum']
            gst_sum = 0
            for invoice_detail in invoice_details:
                proj=Project.objects.get(id=int(invoice_detail.proj_id))
                invoice_detail.proj_id=proj.proj_id            
                if invoice_detail.gst:
                    gst_sum += invoice_detail.amount * gst_default
                    invoice_detail.gstamount = '{0:.2f}'.format(invoice_detail.amount * gst_default)
            
            context['subtotal'] = subtotal
            context['gst'] = gst_sum
            context['total_detail'] = subtotal + gst_sum
        context['invoice_details'] = invoice_details
        return context

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
        invoice_summaries = InvoiceSummary.objects.filter(expensesclaim_id=content_pk)
        context['invoice_summaries'] = invoice_summaries
        context['expensesclaim_files'] = ExpensesClaimRecipt.objects.filter(emp_id_id=content_pk)
        context['vendors']=Company.objects.order_by('name').values('name').distinct()
        gst_default=GST.objects.last()
        if gst_default:
            gst_default=float(gst_default.gst)
        else:
            gst_default=0.09
        context['gst_default']=gst_default*100
        return context


# @method_decorator(login_required, name='dispatch')
# class ExpenseClaimDetailView(DetailView):
#     model = ExpensesClaim
#     template_name="userprofile/expenses-claim-detail.html"

#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#         content_pk = self.kwargs.get('pk')
#         context['projects'] = Project.objects.filter(proj_status__in=["On-going", "Completed"])
#         expenseclaim= ExpensesClaim.objects.get(id=content_pk)
#         context['expenseclaim'] = expenseclaim
#         context['submitedUser'] = User.objects.get(empid=expenseclaim.emp_id)
#         context['managerusers'] = User.objects.filter(role__exact="Managers")
#         context['admin_manager_users'] = User.objects.filter(role__in=["Managers", "Admins"])
#         context['expense_claim_pk'] = content_pk
#         expensesclaim_details = ExpensesClaimDetail.objects.filter(expensesclaim_id=content_pk)
#         for claim_detail in expensesclaim_details:
#             proj=Project.objects.get(id=int(claim_detail.proj_id))
#             claim_detail.proj_id=proj.proj_id

#         if ExpensesClaimDetail.objects.filter(expensesclaim_id=content_pk).exists():
#             subtotal = ExpensesClaimDetail.objects.filter(expensesclaim_id=content_pk).aggregate(Sum('amount'))['amount__sum']
#             gst_sum = 0
#             for gstrow in expensesclaim_details:
#                 if gstrow.gst:
#                     gst_sum += gstrow.amount * 0.09
#                     gstrow.gstamount = '{0:.2f}'.format(gstrow.amount * 0.09)
            
#             context['subtotal'] = subtotal
#             context['gst'] = gst_sum
#             context['total_detail'] = subtotal + gst_sum
#         context['expensesclaim_details'] = expensesclaim_details
#         context['expensesclaim_files'] = ExpensesClaimRecipt.objects.filter(emp_id_id=content_pk)
#         return context


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
                user_status=UserStatus.objects.get(status='resigned')
                for receiver in User.objects.exclude(status=user_status).filter(role__in=['Managers', 'Admins']):
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
def expensesinvoicedetailsadd(request):
    if request.method == "POST":
        proj_id = request.POST.get('proj_id')
        description = request.POST.get('description')
        remark = request.POST.get('remark')
        detail_qty = request.POST.get('detail_qty')
        detail_unitprice = request.POST.get('detail_unitprice')
        gstst = request.POST.get('detail_gst')
        detailid = request.POST.get('detailid')
        invoice_summary_id = request.POST.get('invoice_summary_id')
        if gstst == "true":
            gststatus = True
        else:
            gststatus = False
        
        gst_default=GST.objects.last()
        if gst_default:
            gst_default=float(gst_default.gst)
        else:
            gst_default=0.09

        if detailid == "-1":
            try:
                InvoiceDetail.objects.create(
                    proj_id=proj_id,
                    description=description,
                    remark=remark,
                    qty=detail_qty,
                    unit_price=detail_unitprice,
                    amount=float(detail_qty)*float(detail_unitprice),
                    gst=gststatus,
                    invoicesummary_id=invoice_summary_id
                )
                if InvoiceDetail.objects.filter(invoicesummary_id=invoice_summary_id).exists():
                    subtotal = InvoiceDetail.objects.filter(invoicesummary_id=invoice_summary_id).aggregate(Sum('amount'))['amount__sum']
                    gst_sum = 0
                    for gstrow in InvoiceDetail.objects.filter(invoicesummary_id=invoice_summary_id):
                        if gstrow.gst:
                            gst_sum += gstrow.amount * gst_default
                    gst_sum = float('{0:.2f}'.format(gst_sum))
                    expenseid=-1
                    if InvoiceSummary.objects.filter(id=invoice_summary_id):
                        invoice_summary=InvoiceSummary.objects.get(id=invoice_summary_id)
                        invoice_summary.total = subtotal + gst_sum
                        invoice_summary.gstamount = gst_sum
                        invoice_summary.save()
                        expenseid=invoice_summary.expensesclaim_id
                    
                    subtotal = InvoiceSummary.objects.filter(expensesclaim_id=expenseid).aggregate(Sum('total'))['total__sum']
                    if ExpensesClaim.objects.filter(id=expenseid):
                        expense_amount = ExpensesClaim.objects.get(id=expenseid)
                        expense_amount.total = subtotal
                        expense_amount.save()
                return JsonResponse({
                    "status": "Success",
                    "messages": "Invoice Detail information added!"
                })
            except IntegrityError as e: 
                return JsonResponse({
                    "status": "Error",
                    "messages": "Error is existed!"
                })
        else:
            try:
                invoicedetail = InvoiceDetail.objects.get(id=detailid)
                invoicedetail.proj_id=proj_id
                invoicedetail.description=description
                invoicedetail.remark=remark
                invoicedetail.qty=detail_qty
                invoicedetail.unit_price=detail_unitprice
                invoicedetail.amount=float(detail_qty)*float(detail_unitprice)
                invoicedetail.gst=gststatus
                invoicedetail.invoicesummary_id=invoice_summary_id
                invoicedetail.save()
                
                if InvoiceDetail.objects.filter(invoicesummary_id=invoice_summary_id).exists():
                    subtotal = InvoiceDetail.objects.filter(invoicesummary_id=invoice_summary_id).aggregate(Sum('amount'))['amount__sum']
                    gst = 0
                    for gstrow in InvoiceDetail.objects.filter(invoicesummary_id=invoice_summary_id):
                        if gstrow.gst:
                            gst += gstrow.amount * gst_default
                    gst = float('{0:.2f}'.format(gst))
                    expenseid=-1
                    if InvoiceSummary.objects.filter(id=invoice_summary_id):
                        invoice_summary=InvoiceSummary.objects.get(id=invoice_summary_id)
                        invoice_summary.total = subtotal + gst                        
                        invoice_summary.gstamount = gst
                        invoice_summary.save()
                        expenseid=invoice_summary.expensesclaim_id
                    subtotal = InvoiceSummary.objects.filter(expensesclaim_id=expenseid).aggregate(Sum('total'))['total__sum']
                    if ExpensesClaim.objects.filter(id=expenseid):
                        expense_amount = ExpensesClaim.objects.get(id=expenseid)
                        expense_amount.total = subtotal
                        expense_amount.save()
                return JsonResponse({
                    "status": "Success",
                    "messages": "Invoice Detail information Updated!"
                })
            except IntegrityError as e: 
                return JsonResponse({
                    "status": "Error",
                    "messages": "Error is existed!"
                })

@ajax_login_required
def expensesclaimdetailsadd(request):
    if request.method == "POST":
        vendor = request.POST.get('vendor')
        invoice_no = request.POST.get('invoice_no')
        detail_date = request.POST.get('detail_date')
        detailid = request.POST.get('detailid')
        
        expenseid = request.POST.get('expenseid')
        if detailid == "-1":
            try:
                InvoiceSummary.objects.create(
                    vendor=vendor,
                    invoice_no=invoice_no,
                    total=0,
                    date=detail_date,
                    expensesclaim_id=expenseid
                )
                if InvoiceSummary.objects.filter(expensesclaim_id=expenseid).exists():
                    subtotal = InvoiceSummary.objects.filter(expensesclaim_id=expenseid).aggregate(Sum('total'))['total__sum']                    
                    if ExpensesClaim.objects.filter(id=expenseid):
                        expense_amount = ExpensesClaim.objects.get(id=expenseid)
                        expense_amount.total = subtotal
                        expense_amount.save()
                return JsonResponse({
                    "status": "Success",
                    "messages": "Invoice summary information added!"
                })
            except IntegrityError as e: 
                return JsonResponse({
                    "status": "Error",
                    "messages": "Error is existed!"
                })
        else:
            try:
                i_summary = InvoiceSummary.objects.get(id=detailid)
                i_summary.vendor=vendor
                i_summary.invoice_no=invoice_no
                i_summary.date=detail_date
                i_summary.expensesclaim_id=expenseid
                i_summary.save()
                
                if InvoiceSummary.objects.filter(expensesclaim_id=expenseid).exists():
                    subtotal = InvoiceSummary.objects.filter(expensesclaim_id=expenseid).aggregate(Sum('total'))['total__sum']                    
                    if ExpensesClaim.objects.filter(id=expenseid):
                        expense_amount = ExpensesClaim.objects.get(id=expenseid)
                        expense_amount.total = subtotal
                        expense_amount.save()
                return JsonResponse({
                    "status": "Success",
                    "messages": "Invoice summary information Updated!"
                })
            except IntegrityError as e: 
                return JsonResponse({
                    "status": "Error",
                    "messages": "Error is existed!"
                })


# @ajax_login_required
# def expensesclaimdetailsadd(request):
#     if request.method == "POST":
#         proj_id = request.POST.get('proj_id')
#         vendor = request.POST.get('vendor')
#         description = request.POST.get('description')
#         detail_amount = request.POST.get('detail_amount')
#         detail_date = request.POST.get('detail_date')
#         remark = request.POST.get('remark')
#         gstst = request.POST.get('detail_gst')
#         detailid = request.POST.get('detailid')
#         if gstst == "true":
#             gststatus = True
#         else:
#             gststatus = False
        
#         expenseid = request.POST.get('expenseid')
#         if detailid == "-1":
#             try:
#                 ExpensesClaimDetail.objects.create(
#                     proj_id=proj_id,
#                     vendor=vendor,
#                     description=description,
#                     amount=detail_amount,
#                     date=detail_date,
#                     gst=gststatus,
#                     remark=remark,
#                     expensesclaim_id=expenseid
#                 )
#                 if ExpensesClaimDetail.objects.filter(expensesclaim_id=expenseid).exists():
#                     subtotal = ExpensesClaimDetail.objects.filter(expensesclaim_id=expenseid).aggregate(Sum('amount'))['amount__sum']
#                     gst_sum = 0
#                     for gstrow in ExpensesClaimDetail.objects.filter(expensesclaim_id=expenseid):
#                         if gstrow.gst:
#                             gst_sum += gstrow.amount * 0.09
#                             gstrow.gstval = gstrow.amount * 0.09
                    
#                     if ExpensesClaim.objects.filter(id=expenseid):
#                         expense_amount = ExpensesClaim.objects.get(id=expenseid)
#                         expense_amount.total = subtotal + gst_sum
#                         expense_amount.save()
#                 return JsonResponse({
#                     "status": "Success",
#                     "messages": "Expenses Claim Detail information added!"
#                 })
#             except IntegrityError as e: 
#                 return JsonResponse({
#                     "status": "Error",
#                     "messages": "Error is existed!"
#                 })
#         else:
#             try:
#                 expensedetail = ExpensesClaimDetail.objects.get(id=detailid)
#                 expensedetail.proj_id=proj_id
#                 expensedetail.vendor=vendor
#                 expensedetail.description=description
#                 expensedetail.amount=detail_amount
#                 expensedetail.date=detail_date
#                 expensedetail.gst=gststatus
#                 expensedetail.remark=remark
#                 expensedetail.expensesclaim_id=expenseid
#                 expensedetail.save()
                
#                 if ExpensesClaimDetail.objects.filter(expensesclaim_id=expenseid).exists():
#                     subtotal = ExpensesClaimDetail.objects.filter(expensesclaim_id=expenseid).aggregate(Sum('amount'))['amount__sum']
#                     gst = subtotal * 0.09
                    
#                     if ExpensesClaim.objects.filter(id=expenseid):
#                         expense_amount = ExpensesClaim.objects.get(id=expenseid)
#                         expense_amount.total = subtotal + gst
#                         expense_amount.save()
#                 return JsonResponse({
#                     "status": "Success",
#                     "messages": "Expenses Claim Detail information Updated!"
#                 })
#             except IntegrityError as e: 
#                 return JsonResponse({
#                     "status": "Error",
#                     "messages": "Error is existed!"
#                 })
     

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
                 
@ajax_login_required
def expensesclaiminvoicefilesadd(request):
    if request.method == "POST":
        projid = request.POST.get('projid')
        fileid = request.POST.get('fileid')
        invoicefile=request.FILES.get('receipt_file')
        expenseid = request.POST.get('expenseid')
        invoice_summary_id = request.POST.get('invoice_summary_id')
        if fileid == "-1":
            # Convert the binary data to a NumPy array (uint8)
            nparr = np.frombuffer(invoicefile.read(), np.uint8)
            # Decode the image from the NumPy array
            try:
                image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                prices, qtys, descriptions=parse_text(image)
                if len(prices)==0:
                    return JsonResponse({
                            "status": "Error",
                            "messages": "Cannot detect in OCR. Need to input manually!"
                        })
                for index, description in enumerate(descriptions):
                    try:
                        price=float(prices[index])
                        qty=float(qtys[index])
                        amount=price*qty
                    except ValueError as e:
                        price=0.0
                        qty=0.0
                        amount=0.0
                    try:
                        InvoiceDetail.objects.create(
                            proj_id=projid,
                            description=description,
                            remark="",
                            qty=qty,
                            unit_price=price,
                            amount=amount,
                            gst=True,
                            invoicesummary_id=invoice_summary_id
                        )

                        gst_default=GST.objects.last()
                        if gst_default:
                            gst_default=float(gst_default.gst)
                        else:
                            gst_default=0.09
                        if InvoiceDetail.objects.filter(invoicesummary_id=invoice_summary_id).exists():
                            subtotal = InvoiceDetail.objects.filter(invoicesummary_id=invoice_summary_id).aggregate(Sum('amount'))['amount__sum']
                            gst_sum = 0
                            for gstrow in InvoiceDetail.objects.filter(invoicesummary_id=invoice_summary_id):
                                if gstrow.gst:
                                    gst_sum += gstrow.amount * gst_default
                            expenseid=-1
                            if InvoiceSummary.objects.filter(id=invoice_summary_id):
                                invoice_summary=InvoiceSummary.objects.get(id=invoice_summary_id)
                                invoice_summary.total = subtotal + gst_sum
                                invoice_summary.gstamount = gst_sum
                                invoice_summary.save()
                                expenseid=invoice_summary.expensesclaim_id
                            subtotal = InvoiceSummary.objects.filter(expensesclaim_id=expenseid).aggregate(Sum('total'))['total__sum']
                            if ExpensesClaim.objects.filter(id=expenseid):
                                expense_amount = ExpensesClaim.objects.get(id=expenseid)
                                expense_amount.total = subtotal
                                expense_amount.save()
                        
                    except IntegrityError as e:
                        return JsonResponse({
                            "status": "Error",
                            "messages": "Cannot detect in OCR. Need to input manually!"
                        })
            except AttributeError as e:
                return JsonResponse({
                    "status": "Error",
                    "messages": "Cannot detect in OCR. Need to input manually!"
                })
            return JsonResponse({
                "status": "Success",
                "messages": "Invoice detail information added!"
            })
            
def exportClaimPDF(request, value):
    ecm = ExpensesClaim.objects.get(id=value)    
    domain = os.getenv("DOMAIN")
    logo = Image('http://' + domain + '/static/assets/images/printlogo.png', hAlign='LEFT')
    response = HttpResponse(content_type='application/pdf')
    currentdate = datetime.date.today().strftime("%d-%m-%Y")
    pdfname = ecm.ec_id + ".pdf"
    response['Content-Disposition'] = 'attachment; filename="{}"'.format(pdfname)    
    gst_default=GST.objects.last()
    if gst_default:
        gst_default=float(gst_default.gst)
    else:
        gst_default=0.09
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
         Paragraph('''<para align=center><font size=10><b>GST '''+gst_default*100+'''%</b></font></para>'''),
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
                
                gstval = '{0:.2f}'.format(ecmitem.amount * gst_default)
                total_gst += ecmitem.amount * gst_default
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
        self.drawRightString(self.PAGE_WIDTH/2.0 + 10, 0.35 * inch,
            "Page %d of %d" % (self._pageNumber, page_count))

@ajax_login_required
def getInvoiceItem(request):
    if request.method == "POST":
        invoicedetailid = request.POST.get('invoicedetailid')
        invoicedetail = InvoiceDetail.objects.get(id=invoicedetailid)
        data = {
            'proj_id': invoicedetail.proj_id,
            'description': invoicedetail.description,
            'remark': invoicedetail.remark,
            'qty': invoicedetail.qty,
            'unit_price': invoicedetail.unit_price,
            'gst': invoicedetail.gst,
        }
        return JsonResponse(json.dumps(data), safe=False)

@ajax_login_required
def getExpenseItem(request):
    if request.method == "POST":
        exidetailid = request.POST.get('exidetailid')
        expitem = InvoiceSummary.objects.get(id=exidetailid)
        data = {
            'date': expitem.date.strftime('%d %b, %Y'),
            'vendor': expitem.vendor,
            'invoice_no': expitem.invoice_no,
            'amount': expitem.total,
            'gst': expitem.gstamount,

        }
        return JsonResponse(json.dumps(data), safe=False)


# @ajax_login_required
# def getExpenseItem(request):
#     if request.method == "POST":
#         exidetailid = request.POST.get('exidetailid')
#         expitem = ExpensesClaimDetail.objects.get(id=exidetailid)
#         data = {
#             'date': expitem.date.strftime('%d %b, %Y'),
#             'proj_id': expitem.proj_id,
#             'vendor': expitem.vendor,
#             'description': expitem.description,
#             'amount': expitem.amount,
#             'remark': expitem.remark,
#             'gst': expitem.gst,

#         }
#         return JsonResponse(json.dumps(data), safe=False)


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

