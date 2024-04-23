import requests
import asyncio
from proxmoxer import ProxmoxAPI
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse, HttpResponseRedirect
from django.views.decorators.csrf import csrf_exempt
import time
import json
# from proxmox_backup.middleware import ProxmoxMiddleware

def _init_proxmox(username, password, read_timeout):
    proxmox_api = ProxmoxAPI('75.102.6.66', user=username, password=password, verify_ssl=False, timeout=read_timeout)
    return proxmox_api
    
def login(request):
    if request.method == 'GET':
        return render(request, 'login.html')
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        if not username or not password:
            return render(request, 'login.html', {'error_message': 'Username and password are required.'})
        username += '@pam'
        # proxmox = _init_proxmox(username, password, 3600)
        return HttpResponseRedirect('/proxmox/clone/')
    return render(request, 'login.html')
        # if(request.proxmox_api):
        #     return HttpResponseRedirect('/proxmox/clone/')
        # print("Login view: POST request received")
        # Retrieve username and password from the form
        # username = request.POST.get('username')
        # password = request.POST.get('password')
        # if not username or not password:
        #     error_message = "Username and password are required."
        #     return render(request, 'login.html', {'error_message': error_message})
        
        # username += '@pam'
        # data = {'username': username, 'password': password}
        # Initialize Proxmox connection
        # Check if the authentication is successful
        # try:    
        #     proxmox_api = request.proxmox_api
        #     print(proxmox_api.nodes.get())
        #     nodes = proxmox_api.nodes.get()
        #     # if nodes is not None:
        #     HttpResponseRedirect('/proxmox/clone/')
        # except Exception as e:
        #     error_message = "Invalid username or password. Please try again."
        #     return render(request, 'login.html', {'error_message': error_message})
        # HttpResponseRedirect('/proxmox/clone/')
        # print("Login view: POST request received")

def index(request):
    if request.method == 'GET':
        token = request.COOKIES['csrftoken']
        # print(token)
        if not token:
            return HttpResponseRedirect('/proxmox/login/')
    if request.method == 'POST':
        ip_octets = request.POST.get('ip_octets')
        vmids = request.POST.get('vmids')
        vmids_processed = []
        for part in vmids.split(','):
            if '-' in part:
                start, end = map(int, part.split('-'))
                vmids_processed.extend(range(start, end + 1))
            else:
                vmids_processed.append(int(part))
        vmids_str = " ".join(map(str, vmids_processed))

        command = f"./backup.sh {ip_octets} {vmids_str}"
        process = Popen(command, shell=True, stdout=PIPE, stderr=PIPE)
        stdout, stderr = process.communicate()

        return render(request, 'result.html', {'message': f"Backup initiated for VMIDs: {vmids} with IPs starting with {ip_octets}",
                                               'stdout': stdout.decode('utf-8'),
                                               'stderr': stderr.decode('utf-8')})
    return render(request, 'index.html')

def clone(request):
    # if not proxmox_api:
    #     return HttpResponseRedirect('/proxmox/login/')
    
    if request.method == 'GET':
        return render(request, 'bulk_clone.html')
    if request.method == 'POST':
        proxmox = _init_proxmox('root@pam', 'AB@12345bs', 3600)
        node = proxmox.nodes().get()[0]['node']
        source_vm = request.POST.get('source_vm')
        no_of_clones = request.POST.get('num_clones')
        starting_vm = request.POST.get('new_first_vm')
        ip_sub = request.POST.get('ip_sub')
        ip_gw = request.POST.get('ip_gw')
        
        if not source_vm or not no_of_clones or not starting_vm:
            return JsonResponse({'message': 'All fields are required'}, status=400)
        
        # print(f"source_vm: {source_vm}, no_of_clones: {no_of_clones}, starting_vm: {starting_vm}, ip_sub: {ip_sub}, ip_gw: {ip_gw}")
        
        ip_octets = ip_sub.split('.')
        last_octet = ip_octets[3]
        ip_octets = ip_octets[:3]
        for i in range(int(no_of_clones)):
            new_vm_id = int(starting_vm) + i
            start_ip_list = ip_octets + [str(int(last_octet) + i)]
            start_ip = '.'.join(start_ip_list)
            # print(f"start_ip: {start_ip}, ip_gw: {ip_gw}")
            
            proxmox.nodes(node).qemu(source_vm).clone.create(
                newid=new_vm_id,
                name=f"{new_vm_id}",
                full='1'  # Set to '1' to perform a full clone (clones disks)
            )
            time.sleep(25)
            
            # Construct the ipconfig0 value with proper formatting
            ipconfig_data = {
                "ipconfig0": "ip={}/26,gw={},ip6=dhcp".format(start_ip, ip_gw)
            }
            
            # Print the ipconfig_data
            # print(ipconfig_data)
            
            proxmox.nodes(node).qemu(new_vm_id).config.post(**ipconfig_data)
            time.sleep(5)
            proxmox.nodes(node).qemu(new_vm_id).cloudinit.get()
            time.sleep(5)
            proxmox.nodes(node).qemu(new_vm_id).status.start.post()
            time.sleep(5)
            # self.end_headers()
            # proxmox.nodes(node).qemu(1001).clone.create(
            #     newid=700,
            #     name="chk",
            #     full='1'  # Set to '1' to perform a full clone (clones disks)
            # )
            
            # ipconfig_data = {
            #     "ipconfig0": "ip=65.87.10.125/26,gw=65.87.10.65,ip6=dhcp",
            # }
            # proxmox.nodes(node).qemu(700).config.post(**ipconfig_data)
            
            # proxmox.nodes(node).qemu(700).cloudinit.get()
            # proxmox.nodes(node).qemu(700).status.reboot.post()
            # proxmox.nodes("<node_name>").qemu(clone_vm_id).status.start()
        return JsonResponse({'message': 'Cloning initiated'})
    return render(request, 'bulk_clone.html')
