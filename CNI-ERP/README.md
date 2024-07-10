*** Our APP ======= ERP Solutions ***

# Technologies used for this project

We used django 3.2.8, python 3.8.5, bootstrap 5.0.1, jquery 3.5.1 in our app.


# Installation

for running our app, You have to install python or anaconda on your pc or server.


1. Install dependencies with pip. (If you are using virtual environment remember to activate it)

    pip install -r requirements.txt


2. Perform migrations: 

    python manage.py makemigrations

    Or Do the migrations separately in case the command does not fail.

    python manage.py makemigrations accounts

    python manage.py makemigrations sales

    python manage.py makemigrations project

    python manage.py makemigrations maintenance
    
    python manage.py makemigrations expenseclaim

    python manage.py makemigrations inventory

    python manage.py makemigrations siteprogress

    python manage.py makemigrations toolbox

    And finally create the database.

    python manage.py migrate


3. Run the project:


    <!-- python manage.py cities_light --force-all -->

    python3 manage.py runserver 172.16.0.86:8000

Load test data (Optional):

* In Local:

    python manage.py loaddata accounts/data/cities_light_country.json

    python manage.py loaddata accounts/data/users.json

    python manage.py loaddata accounts/data/roles.json

    python manage.py loaddata accounts/data/privileges.json

    python manage.py loaddata accounts/data/uoms.json

    python manage.py loaddata accounts/data/notification_privilege.json

    python manage.py loaddata accounts/data/assetlog.json

    python manage.py loaddata accounts/data/worklog.json
    
    python manage.py loaddata accounts/data/materialout.json

    python manage.py loaddata accounts/data/holiday.json

    python manage.py loaddata accounts/data/toolbox_objective.json

    python manage.py loaddata accounts/data/toolbox_description.json

    python manage.py loaddata accounts/data/payment.json

    python manage.py loaddata accounts/data/validity.json


* Admin information

    username: admin
    
    password: admin!@#
