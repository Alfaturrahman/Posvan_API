from django.http import JsonResponse
import json
import inspect

COLORS = {
    "header": "\033[95m",
    "error": "\033[91m", 
    "function": "\033[94m",
    "path": "\033[92m",  
    "message": "\033[93m",
    "highlight": "\033[1m",
    "underline": "\033[4m",
    "end": "\033[0m",    
}

TECHFUSION_LOGO = f"""
{COLORS['header']}
___________           .__    ___________           .__               
\__    ___/___   ____ |  |__ \_   _____/_ __  _____|__| ____   ____  
  |    |_/ __ \_/ ___\|  |  \ |    __)|  |  \/  ___/  |/  _ \ /    \ 
  |    |\  ___/\  \___|   Y  \|     \ |  |  /\___ \|  (  <_> )   |  \ 
  |____| \___  >\___  >___|  /\___  / |____//____  >__|\____/|___|  /
             \/     \/     \/     \/             \/               \/ 
{COLORS['end']}
"""

class Response:
    def base(self, request=None, data=None, message="", messagetype="", status=200):
        if data is None:
            data = []

        return JsonResponse({
            'status_code': status,
            'message': message,
            'messagetype': messagetype,
            'data': data,
        }, status=status)

    @staticmethod
    def ok(data=None, message="", messagetype=""):
        return Response().base(data=data, message=message, messagetype=messagetype, status=200)

    @staticmethod
    def badRequest(request=None, data=None, message="", messagetype="", status=400):
        function_name = inspect.stack()[1].function
        function_path = request.build_absolute_uri()
        
        if data == None:
            data = []
        
        print(f"{COLORS['header']}{COLORS['highlight']}═" * 70 + f"{COLORS['end']}")
        print(f"{COLORS['header']}{TECHFUSION_LOGO}{COLORS['end']}")
        print(f"{COLORS['header']}{COLORS['highlight']}═" * 70 + f"{COLORS['end']}")
        
        print(f"{COLORS['highlight']}{COLORS['underline']}LOGGING DETAILS{COLORS['end']}")
        print(f"{COLORS['header']}{COLORS['highlight']}═" * 70 + f"{COLORS['end']}")
        
        print(f"{COLORS['function']}🚀 {COLORS['highlight']}Function Name:{COLORS['end']} {function_name}")
        print(f"{COLORS['path']}🌍 {COLORS['highlight']}Path:{COLORS['end']} {function_path}")
        
        print(f"{COLORS['error']}⚠️ {COLORS['highlight']} Error:{COLORS['end']} {data}")
        print(f"{COLORS['message']}💬 {COLORS['highlight']}Message:{COLORS['end']} {message}")
        
        print(f"{COLORS['header']}{COLORS['highlight']}═" * 70 + f"{COLORS['end']}")
        
        return Response().base(data=data, message=message, messagetype=messagetype, status=status)