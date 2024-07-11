# ERP Solutions

## Dockerizing

### project structure
```

├── .gitignore
├── CNI-ERP
│   ├── Dockerfile
│   ├── hello_django
│   │   ├── __init__.py
│   │   ├── asgi.py
│   │   ├── settings.py
│   │   ├── urls.py
│   │   └── wsgi.py
│   ├── manage.py
│   ├── requirements.txt
|   └── .env
|    ...
├── docker-compose.yml
└── nginx
    ├── Dockerfile
    └── nginx.conf
```
### Execute the docker compose
```
docker compose -f docker-compose.yml down -v
docker compose -f docker-compose.yml up -d --build
docker compose -f docker-compose.yml exec web python manage.py migrate --noinput
docker compose -f docker-compose.yml exec web python manage.py collectstatic --no-input --clear
```

### Check the docker container 
1. List Running Containers: First, list all running containers to get the container ID or name.
```
docker ps
```
2. Open a Shell in the Container: Use the container ID or name to open a shell session.
```
docker exec -it <container_id_or_name> /bin/bash
```
or if the container uses sh as the shell:
```
docker exec -it <container_id_or_name> /bin/sh
```
3. Exit from the docker bash.
```
exit
```

Refer this link for more detail about the docker, gunicorn, nginx production.

https://testdriven.io/blog/dockerizing-django-with-postgres-gunicorn-and-nginx/
https://realpython.com/django-nginx-gunicorn/

Read this to setup ERP solution in local.

https://github.com/golden-k22/ERP-solution/blob/main/CNI-ERP/README.md