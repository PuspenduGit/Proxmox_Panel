from proxmoxer import ProxmoxAPI
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse, HttpResponseRedirect
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_protect
from django.middleware.csrf import get_token
import time
# from proxmox_backup.middleware import ProxmoxMiddleware


def _init_proxmox(server_ip, username, password, read_timeout):
    proxmox_api = ProxmoxAPI(
        server_ip, user=username, password=password, verify_ssl=False, timeout=read_timeout)
    return proxmox_api


@ensure_csrf_cookie
def login(request):
    if request.method == 'POST':
        server_ip = request.POST.get('server_ip')
        password = request.POST.get('password')
        if not server_ip or not password:
            return render(request, 'login.html', {'error_message': 'Username and password are required.'})
        username = 'root@pam'
        resource = {
            'server_ip': server_ip,
            'username': username,
            'password': password,
        }
        csrf_token = get_token(request)
        request.session['resource'] = resource
        request.session['csrf_token'] = csrf_token
        return HttpResponseRedirect('/proxmox/clone/')
    return render(request, 'login.html')


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


@csrf_protect
def clone(request):
    if request.method == 'POST':
        if not request.session.get('csrf_token') or not request.session.get('resource'):
            return HttpResponseRedirect('/proxmox/login/')

        resource = request.session['resource']

        server_ip = resource['server_ip']
        username = resource['username']
        password = resource['password']

        # return JsonResponse({
        #     'server_ip': server_ip,
        #     'username': username,
        #     'password': password
        # })

        proxmox = _init_proxmox(server_ip, username, password, 3600)
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
            time.sleep(20)

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
        # server_ip = username = password = None
        # request.session['resource'] = None
        # request.session['csrf_token'] = None
        return JsonResponse({'message': 'Cloning initiated'})
    return render(request, 'bulk_clone.html')
