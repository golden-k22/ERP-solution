from django.contrib.auth.decorators import login_required
from django.http.response import HttpResponse
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView
from django.shortcuts import render, redirect
from accounts.models import User, UserStatus
from notifications.signals import notify

# Create your views here.
@method_decorator(login_required, name='dispatch')
class Dashboard(TemplateView):
    template_name = "dashboard/dashboard.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        not_resigned_status=UserStatus.objects.get(status="resigned").id
        # Construct the SQL query with the retrieved status ID
        sql_query = """
            SELECT  
                tu.id,
                tu.username,
                tu.empid,
                tw.latest_checkin_time,
                tp.id as w_proj_id,
                tp.proj_name,
                tsu.project_id as s_proj_id,
                CASE 
                    WHEN tw.projectcode IS NOT NULL THEN 1 
                    ELSE 0 
                END AS is_checkin_today  
            FROM 
                tb_user AS tu
            LEFT JOIN 
                (
                    SELECT 
                        emp_no,
                        projectcode,
                        MAX(checkin_time) AS latest_checkin_time
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
            WHERE
                (tu.status_id != {} OR tu.status_id IS NULL)
                AND tu.role IN ('Supervisors', 'Workers');

        """.format(not_resigned_status)
        context['users'] = User.objects.raw(sql_query)
        return context

def handler404(request, exception):
    return render(request, '404.html', status=404)

def handler500(request):
    return render(request, '500.html', status=500)

def message(request):
    try:
        if request.method == 'POST':
            sender = User.objects.get(username=request.user)
            receiver = User.objects.get(id=request.POST.get('user_id'))
            user_status=UserStatus.objects.get(status='resigned')
            for receiver in User.objects.exclude(status=user_status).all():
                notify.send(sender, recipient=receiver, verb='Message', description=request.POST.get('message'))
            return redirect('/')
        else:
            return HttpResponse("Invalid request")
    except Exception as e:
        print(e)
        return HttpResponse("Please login from admin site for sending messages")

def schedule_cron_job():
    print("cron job starting")
