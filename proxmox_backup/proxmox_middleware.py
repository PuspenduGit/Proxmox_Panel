from proxmoxer import ProxmoxAPI

class ProxmoxMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Process the request
        response = self.get_response(request)
        return response

    def process_request(self, request):
        # Initialize Proxmox API object if it doesn't exist in the session
        if 'proxmox_api_credentials' not in request.session:
            request.session['proxmox_api_credentials'] = {
                'username': 'root@pam',
                'password': '2$cre@mr011'
            }
        return None

    def _init_proxmox(self, username, password):
        proxmox_api = ProxmoxAPI('136.175.10.63', user=username, password=password, verify_ssl=False)
        return proxmox_api
