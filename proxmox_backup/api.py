from django.urls import path
from proxmox_backup_app.views import login, index, clone

urls = [
    path('login/', login, name='login'),
    path('index/', index, name='index'),
    path('clone/', clone, name='clone'),
]