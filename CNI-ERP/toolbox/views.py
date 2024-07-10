from django.conf import settings
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.views.generic.list import ListView
from sales.models import Quotation, Scope
from toolbox.models import ToolBox, ToolBoxAttendeesLog, ToolBoxDescription, ToolBoxItem, ToolBoxLogItem, ToolBoxObjective
from project.models import Project, Team
from django.db import IntegrityError
from django.http import HttpResponse, JsonResponse
from django.views.generic.detail import DetailView
import json
import datetime
import pytz
import base64
from django.core.files.base import ContentFile
from dateutil import parser as date_parser
from sales.decorater import ajax_login_required
from accounts.models import User, Role
from django.utils import timezone
from notifications.signals import notify
from reportlab.platypus import SimpleDocTemplate, Table, Image, Spacer, TableStyle, PageBreak, Paragraph
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from io import BytesIO
from reportlab.lib.pagesizes import A4, landscape, portrait
from reportlab.pdfgen import canvas
from reportlab.rl_config import defaultPageSize
from reportlab.lib.utils import ImageReader
# Create your views here.
@method_decorator(login_required, name='dispatch')
class ToolBoxList(ListView):
    model = ToolBox
    template_name = "toolbox/toolbox-list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tbms_no'] = ToolBox.objects.order_by('tbm_no').values('tbm_no').distinct()
        context['projects_no'] = ToolBox.objects.order_by('project_no').values('project_no','project_name').distinct()
        context['proj_nos'] = Project.objects.filter(proj_status="On-going").order_by('proj_id').values('proj_id', 'proj_name').distinct()
        context['projects'] = Project.objects.filter(proj_status="On-going").exclude(proj_name=None)
        
        return context

@ajax_login_required
def ajax_tbms(request):
    if request.method == "POST":
        #tbms = ToolBox.objects.all()
        tbms = []
        return render(request, 'toolbox/ajax-tbm.html', {'tbms': tbms})

@ajax_login_required
def ajax_tbmFilterList(request):
    if request.method == "POST":
        proj_ids = request.POST.getlist("proj_ids[]")
        tbms = ToolBox.objects.filter(project_no__in=list(proj_ids))

        return render(request, 'toolbox/ajax-tbm.html', {'tbms': tbms})

@ajax_login_required
def tbmdelete(request):
    if request.method == "POST":
        tbmid = request.POST.get('tbmid')
        tbm = ToolBox.objects.get(id=tbmid)
        tbmattend = ToolBoxAttendeesLog.objects.filter(toolbox=tbmid)
        tbmlogitem = ToolBoxLogItem.objects.filter(toolbox=tbmid)
        tbmlogitem.delete()
        tbmattend.delete()
        tbm.delete()

        return JsonResponse({'status': 'ok'})

@ajax_login_required
def tbmattenddelete(request):
    if request.method == "POST":
        tbmattendid = request.POST.get('tbmattendid')
        tbmattend = ToolBoxAttendeesLog.objects.get(id=tbmattendid)
        tbmattend.delete()

        return JsonResponse({'status': 'ok'})

@ajax_login_required
def toolboxadd(request):
    if request.method == "POST":
        project_no = request.POST.get('proj_id')
        date = request.POST.get('date')
        tbm_no = request.POST.get('tbm_no')
        tbmid = request.POST.get('tbmid')
        picture=request.FILES.get('picture')
        project = Project.objects.get(proj_id__iexact=project_no)
        if tbmid == "-1":
            if ToolBox.objects.filter(tbm_no=tbm_no).exists():
                return JsonResponse({
                    "status": "Error",
                    "messages": "This id has been taken by others, please close current window and create again.",
                })
            try:
                toolbox = ToolBox.objects.create(
                    tbm_no=tbm_no,
                    project_no=project_no,
                    project_name=project.proj_name,
                    date=date,
                    photo=picture,
                )
                tbm_items = ToolBoxItem.objects.filter(project_id=project.id)
                for tbm_item in tbm_items:
                    ToolBoxLogItem.objects.create(
                        objective=tbm_item.objective,
                        description=tbm_item.description,
                        remark=tbm_item.remark,
                        manager=tbm_item.manager,
                        project_id=project.id,
                        toolbox_id=toolbox.id
                    )

                #notification send
                sender = request.user
                description = '<a href="/toolbox-detail/'+str(toolbox.id)+'">ToolBox No : ' + toolbox.tbm_no +  ' - New ToolBox was created by ' + request.user.username + '</a>'
                for receiver in User.objects.filter(username=project.proj_incharge):
                    if receiver.notificationprivilege.tbm_no_created:
                        notify.send(sender, recipient=receiver, verb='Message', level="success", description=description)
                return JsonResponse({
                    "status": "Success",
                    "messages": "ToolBox information added!",
                    "tbmid": toolbox.id,
                    "method": "add"
                })
            except IntegrityError as e: 
                return JsonResponse({
                    "status": "Error",
                    "messages": "Error is existed!"
                })
        else:
            try:
                tbm = ToolBox.objects.get(id=tbmid)
                tbm.project_no = project_no
                tbm.date = date
                tbm.tbm_no = tbm_no
                tbm.project_name=project.proj_name
                tbm.photo=picture
                tbm.save()

                return JsonResponse({
                    "status": "Success",
                    "messages": "ToolBox information updated!",
                    "tbmid": tbm.id,
                    "method": "add"
                })

            except IntegrityError as e: 
                return JsonResponse({
                    "status": "Error",
                    "messages": "Error is existed!"
                })

@ajax_login_required
def getToolBox(request):
    if request.method == "POST":
        tbmid = request.POST.get('tbmid')
        tbm = ToolBox.objects.get(id=tbmid)
        if tbm.photo =="":
            data = {
                'project_no': tbm.project_no,
                'date': tbm.date.strftime('%d %b, %Y'),
                'tbm_no': tbm.tbm_no,
                'photo': "",
            }
        else:
            data = {
                'project_no': tbm.project_no,
                'date': tbm.date.strftime('%d %b, %Y'),
                'tbm_no': tbm.tbm_no,
                'photo': tbm.photo.url,
            }
        return JsonResponse(json.dumps(data), safe=False)

@ajax_login_required
def getToolBoxAttend(request):
    if request.method == "POST":
        tbmattedid = request.POST.get('tbmattedid')
        tbmlog = ToolBoxAttendeesLog.objects.get(id=tbmattedid)
        data = {
            'name': tbmlog.name,
            'nric': tbmlog.nric,
            'signature': tbmlog.signature
        }
        return JsonResponse(json.dumps(data), safe=False)

@ajax_login_required
def ajax_toolbox_filter(request):
    if request.method == "POST":
        search_project = request.POST.get('search_project')
        daterange = request.POST.get('daterange')
        if daterange:
            startdate = datetime.datetime.strptime(daterange.split()[0],'%Y.%m.%d').replace(tzinfo=pytz.utc)
            enddate = datetime.datetime.strptime(daterange.split()[2], '%Y.%m.%d').replace(tzinfo=pytz.utc)
        search_tbm = request.POST.get('search_tbm')
        if search_project != "" and daterange == "" and search_tbm == "":
            tbms = ToolBox.objects.filter(project_no__iexact=search_project)

        elif search_project != "" and daterange != "" and search_tbm == "":
            tbms = ToolBox.objects.filter(project_no__iexact=search_project, date__gte=startdate, date__lte=enddate)
        
        elif search_project != "" and daterange != "" and search_tbm != "":
            tbms = ToolBox.objects.filter(project_no__iexact=search_project, date__gte=startdate, date__lte=enddate, tbm_no__iexact=search_tbm)

        elif search_project == "" and daterange != "" and search_tbm == "":
            tbms = ToolBox.objects.filter(date__gte=startdate, date__lte=enddate)

        elif search_project == "" and daterange != "" and search_tbm != "":
            tbms = ToolBox.objects.filter(date__gte=startdate, date__lte=enddate, tbm_no__iexact=search_tbm)

        elif search_project == "" and daterange == "" and search_tbm != "":
            tbms = ToolBox.objects.filter(tbm_no__iexact=search_tbm)

        elif search_project != "" and daterange == "" and search_tbm != "":
            tbms = ToolBox.objects.filter(project_no__iexact=search_project,tbm_no__iexact=search_tbm)

        return render(request, 'toolbox/ajax-tbm.html', {'tbms': tbms})

@method_decorator(login_required, name='dispatch')
class ToolBoxDetailView(DetailView):
    model = ToolBox
    template_name="toolbox/toolbox-detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        content_pk = self.kwargs.get('pk')
        tbm = ToolBox.objects.get(id=content_pk)
        context['tbm'] = tbm
        project = Project.objects.get(proj_id__iexact=tbm.project_no)
        context['toolbox_pk'] = content_pk
        context['project'] = project
        # context['user_roles']=Role.objects.all()
        # context['supervisors'] = User.objects.filter(role="Supervisors")
        context['supervisors'] = User.objects.exclude(role="Worker")
        context['toolboxitems'] = ToolBoxLogItem.objects.filter(project_id=project.id, toolbox_id=content_pk)
        # quotation = Quotation.objects.filter(qtt_id__iexact=project.proj_id.replace('CPJ','').strip())
        quotation = Quotation.objects.filter(qtt_id__iexact=project.qtt_id)
        projectitemactivitys = Scope.objects.filter(quotation_id=quotation[0].id)
        context['projectitemactivitys'] = projectitemactivitys
        context['attendlogs'] = ToolBoxAttendeesLog.objects.filter(toolbox_id=content_pk)
        context['tbm_objectives'] = ToolBoxObjective.objects.all()
        context['tbm_descriptions'] = ToolBoxDescription.objects.all()
        project_no=ToolBox.objects.get(id=content_pk).project_no
        if Project.objects.filter(proj_id=project_no).exists():
            project_id=Project.objects.get(proj_id=project_no).id
            context['attend_users'] = []
            if Team.objects.filter(project_id=project_id).exists():
                team_rows=Team.objects.filter(project_id=project_id)
                for team_row in team_rows:
                    context['attend_users'].append(team_row.user)
            for active_user in User.objects.filter(is_active="1"):
                if active_user not in context['attend_users']:
                    context['attend_users'].append(active_user)
        else:
            context['attend_users']=User.objects.filter(is_active="1")
        return context
@ajax_login_required
def UpdateToolbox(request):
    if request.method == "POST":
        
        supervisor = request.POST.get('supervisor')
        project_no = request.POST.get('project_no')
        date = request.POST.get('date')
        project_name = request.POST.get('project_name')
        tbmid = request.POST.get('tbmid')
        
        try:
            toolbox = ToolBox.objects.get(id=tbmid)
            toolbox.supervisor=supervisor
            toolbox.project_no=project_no
            toolbox.date=date
            toolbox.project_name=project_name
            
            toolbox.save()
            
            return JsonResponse({
                "status": "Success",
                "messages": "ToolBox information updated!"
            })
        except IntegrityError as e: 
            print(e)
            return JsonResponse({
                "status": "Error",
                "messages": "Error is existed!"
            })

@ajax_login_required
def check_tbm_number(request):
    if request.method == "POST":
        if ToolBox.objects.all().exists():
            tbm= ToolBox.objects.all().order_by('-tbm_no')[0]
            data = {
                "status": "exist",
                "tbm_no": tbm.tbm_no.replace('CTM','').split()[0]
            }
        
            return JsonResponse(data)
        else:
            data = {
                "status": "no exist"
            }
        
            return JsonResponse(data)

@ajax_login_required
def toolboxattendadd(request):
    if request.method == "POST":
        name = request.POST.get('name')
        nric = request.POST.get('nric')
        remark = request.POST.get('remark')
        signature = request.POST.get('signature')
        tbmattedid = request.POST.get('tbmattedid')
        default_base64 = request.POST.get("default_base64")
        toolboxid = request.POST.get('toolboxid')
        
        format, imgstr = default_base64.split(';base64,')
        ext = format.split('/')[-1]
        signature_image = ContentFile(base64.b64decode(imgstr), name='attendee-' + datetime.date.today().strftime("%d-%m-%Y") + "." + ext)
        if tbmattedid == "-1":
            try:
                ToolBoxAttendeesLog.objects.create(
                    name=name,
                    nric=nric,
                    signature=signature,
                    toolbox_id=toolboxid,
                    signature_image=signature_image
                )
                return JsonResponse({
                    "status": "Success",
                    "messages": "ToolBox Attendees information added!"
                })
            except IntegrityError as e: 
                return JsonResponse({
                    "status": "Error",
                    "messages": "Error is existed!"
                })
        else:
            try:
                tbmattend = ToolBoxAttendeesLog.objects.get(id=tbmattedid)
                tbmattend.name=name
                tbmattend.nric=nric
                tbmattend.remark=remark
                tbmattend.signature=signature
                tbmattend.toolbox_id=toolboxid
                tbmattend.default_base64=default_base64
                tbmattend.save()

                return JsonResponse({
                    "status": "Success",
                    "messages": "ToolBox Attendees information updated!"
                })

            except IntegrityError as e: 
                return JsonResponse({
                    "status": "Error",
                    "messages": "Error is existed!"
                })

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []
        self.PAGE_HEIGHT=defaultPageSize[1]
        self.PAGE_WIDTH=defaultPageSize[0]
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
        self.drawString(150, self.PAGE_HEIGHT - 50, "CNI TECHNOLOGYPTE LTD")
        self.setFont("Helvetica", 10)
        self.drawString(150, self.PAGE_HEIGHT - 65, "Block 3023 Ubi Road 3, #02-15 Ubi Plex 1, Singapore 408663")
        self.drawString(150, self.PAGE_HEIGHT - 80, "Tel.6747 6169 Fax.7647 5669")
        self.drawString(150, self.PAGE_HEIGHT - 95, "RCB No.201318779M")
        self.setFont("Times-Roman", 9)
        self.drawRightString(self.PAGE_WIDTH/2.0 + 10, 0.35 * inch,
            "Page %d of %d" % (self._pageNumber, page_count))

def exportTbmPDF(request, value):
    domain = request.META['HTTP_HOST']
    response = HttpResponse(content_type='application/pdf')
    currentdate = datetime.date.today().strftime("%d-%m-%Y")
    pdfname = "ToolBox-" + str(value) + ".pdf"
    response['Content-Disposition'] = 'attachment; filename={}'.format(pdfname)
    story = []
    buff = BytesIO()
    doc = SimpleDocTemplate(buff, pagesize=portrait(A4), rightMargin=0.25*inch, leftMargin=0.25*inch, topMargin=1.4*inch, bottomMargin=0.25*inch, title=pdfname)
    styleSheet=getSampleStyleSheet()
    tbm = ToolBox.objects.get(id=value)
    project = Project.objects.get(proj_id__iexact=tbm.project_no)
    
    story.append(Spacer(1, 16))
    tbminformation = []
    if tbm.supervisor:
        supervisor = tbm.supervisor
    else:
        supervisor = ""
    tbm_detail = '''
        <para align=left>
            <font size=10>Supervisor: %s</font><br/><br/>
            <font size=10>Project Name: %s</font><br/><br/>
            <font size=10>Worksite: %s</font><br/>
        </para>
    ''' % (supervisor, tbm.project_name, project.worksite_address)
    tbm_title = '''
        <para align=left>
            <font size=16><b>TOOLBOX MEETING</b></font><br/>
            <font size=10>TBM No: %s</font><br/>
            <font size=10>Date: %s</font><br/>
            <font size=10>Project No: %s</font>
        </para>
    ''' % (tbm.tbm_no, tbm.date.strftime('%d/%m/%Y'), tbm.project_no)
    tbm_head = ParagraphStyle("justifies", leading=18)
    tbminformation.append([Paragraph(tbm_detail), Paragraph(tbm_title, tbm_head)])
    information = Table(
        tbminformation,
        style=[
            ('ALIGN',(0,0),(0,0),'LEFT'),
            ('ALIGN',(1,0),(1,0),'CENTER'),
            ('VALIGN',(0,0),(0,0),'TOP'),
            ('VALIGN',(1,0),(1,0),'TOP'),
        ]
    )
    information._argW[0]=4.9*inch
    information._argW[1]=2.42*inch
    story.append(information)
    style_diary_title = ParagraphStyle(name='left', parent=styleSheet['Normal'], leftIndent=12)
    diary_title = '''
        <para align=left>
            <font size=11><b><i>Daily Work Activities & Risk:</i></b></font>
        </para>
    '''
    story.append(Spacer(1, 10))
    story.append(Paragraph(diary_title,style_diary_title))
    story.append(Spacer(1, 10))
    diary_data = [
        [Paragraph('''<para align=center><font size=10><b>S/N</b></font></para>'''), Paragraph('''<para align=left><font size=10><b>Objectives</b></font></para>'''), Paragraph('''<para align=left><font size=10><b>Description</b></font></para>''')]
    ]
    diaryitems = ToolBoxLogItem.objects.filter(project_id=project.id, toolbox_id=value)
    if diaryitems.exists():
        index = 1
        for diaryitem in diaryitems:
            temp = []
            temp.append(index)
            #temp.append(Paragraph('''<para align=center><font size=10>%s</font></para>''' % (diaryitem.activity)))
            temp.append(Paragraph('''<para align=left><font size=10>%s</font></para>''' % (diaryitem.objective)))
            temp.append(Paragraph('''<para align=left><font size=10>%s</font></para>''' % (diaryitem.description)))
            diary_data.append(temp)
            index += 1

        diarytable = Table(
            diary_data,
            style=[
                ('BACKGROUND', (0, 0), (5, 0), colors.lavender),
                ('GRID',(0,0),(-1,-1),0.5,colors.black),
                ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
                ('ALIGN',(0,0),(-1,-1),'CENTER'),
            ],
        )
    else:
        diary_data.append(["No data available in table", "", ""]) 
        diarytable = Table(
            diary_data,
            style=[
                ('BACKGROUND', (0, 0), (-1, 0), colors.lavender),
                ('GRID',(0,0),(-1,-1),0.5,colors.black),
                ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
                ('ALIGN',(0,0),(-1,-1),'CENTER'),
                ('SPAN',(0,1),(-1,-1)),
            ],
        )
        diarytable._argH[1]=0.3*inch
    
    diarytable._argW[0]=0.40*inch
    diarytable._argW[1]=2.364*inch
    diarytable._argW[2]=4.556*inch
    story.append(diarytable)
    story.append(Spacer(1, 10))
    style_diary_title = ParagraphStyle(name='left', parent=styleSheet['Normal'], leftIndent=12)
    diary_title = '''
        <para align=left>
            <font size=11><b><i>Attendee's Signatures:</i></b></font>
        </para>
    '''
    story.append(Paragraph(diary_title,style_diary_title))
    story.append(Spacer(1, 10))
    attendee_data = [
        [Paragraph('''<para align=left><font size=10><b>S/N</b></font></para>'''), Paragraph('''<para align=center><font size=10><b>Name</b></font></para>'''), [Paragraph('''<para align=center spaceb=2><font size=10><b>Company Stamp /NRIC FIN</b></font><br/><font size=10><b>(Last 4 Digits)</b></font></para>''')], Paragraph('''<para align=center><font size=10><b>Signatures</b></font></para>''')]
    ]
    attendlogs = ToolBoxAttendeesLog.objects.filter(toolbox_id=value)
    index = 1
    if attendlogs.exists():
        for attendlog in attendlogs:
            temp = []
            signature_image = Image('http://' + domain + attendlog.signature_image.url,width=2.0*inch, height=0.4*inch, hAlign='LEFT')
            temp.append(index)
            temp.append(attendlog.name)
            temp.append(attendlog.nric)
            temp.append(signature_image)
            attendee_data.append(temp)
            index += 1
        attendeetable = Table(
            attendee_data,
            style=[
                ('BACKGROUND', (0, 0), (3, 0), colors.lavender),
                ('GRID',(0,0),(-1,-1),0.5,colors.black),
                ('ALIGN',(0,0),(-1,-1),'CENTER'),
                ('VALIGN',(3,1),(3,-1),'MIDDLE'),
                ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
            ],
        )
    else:
        attendee_data.append(["No data available in table", "", "", ""]) 
        attendeetable = Table(
            attendee_data,
            style=[
                ('BACKGROUND', (0, 0), (-1, 0), colors.lavender),
                ('GRID',(0,0),(-1,-1),0.5,colors.black),
                ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
                ('ALIGN',(0,0),(-1,-1),'CENTER'),
                ('SPAN',(0,1),(-1,-1)),
            ],
        )
        attendeetable._argH[1]=0.3*inch

    attendeetable._argW[0]=0.40*inch
    attendeetable._argW[1]=3.0*inch
    attendeetable._argW[2]=1.8*inch
    attendeetable._argW[3]=2.12*inch
    
    story.append(attendeetable)
    doc.build(story,canvasmaker=NumberedCanvas)
    response.write(buff.getvalue())
    buff.close()

    return response

@ajax_login_required
def toolboxlogitemadd(request):
    if request.method == "POST":
        description = request.POST.get('description')
        objective = request.POST.get('objective')
        remark = request.POST.get('remark')
        activity = request.POST.get('activity')
        manager = request.POST.get('manager')
        tbmpk = request.POST.get('tbmpk')
        projectid = request.POST.get('projectid')
        toolboxitemid = request.POST.get('toolboxid')
        
        if toolboxitemid == "-1":
            try:
                ToolBoxLogItem.objects.create(
                    activity=activity,
                    objective=objective,
                    remark=remark,
                    manager=manager,
                    description=description,
                    project_id=projectid,
                    toolbox_id=tbmpk
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
                tbmlogitem = ToolBoxLogItem.objects.get(id=toolboxitemid)
                tbmlogitem.activity = activity
                tbmlogitem.objective = objective
                tbmlogitem.remark = remark
                tbmlogitem.manager=manager
                tbmlogitem.description = description
                tbmlogitem.project_id = projectid
                tbmlogitem.toolbox_id=tbmpk
                tbmlogitem.save()

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
def getToolBoxLogItem(request):
    if request.method == "POST":
        toolboxid = request.POST.get('toolboxid')
        tbmlogitem = ToolBoxLogItem.objects.get(id=toolboxid)
        data = {
            'activity': tbmlogitem.activity,
            'objective': tbmlogitem.objective,
            'description': tbmlogitem.description,
            'remark': tbmlogitem.remark,
        }
        return JsonResponse(json.dumps(data), safe=False)

@ajax_login_required
def tbmilogtemdelete(request):
    if request.method == "POST":
        tbmitemid = request.POST.get('tbmitemdel_id')
        tbmlogitem = ToolBoxLogItem.objects.get(id=tbmitemid)
        tbmlogitem.delete()

        return JsonResponse({'status': 'ok'})
@ajax_login_required
def ajax_get_user_nric(request):
    if request.method == "POST":
        user_name = request.POST.get('user_name')
        if User.objects.filter(username=user_name).exists():
            nric=User.objects.get(username=user_name).nric
            if nric is not None and len(nric)>3:
                result_nric=nric[len(nric)-4:]
            else:
                result_nric=""
        else:
            result_nric=""
        return JsonResponse({'status': 'ok', 'nric':result_nric})
