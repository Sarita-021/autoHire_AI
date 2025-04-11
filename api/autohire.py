# api/autohire.py

from http.server import BaseHTTPRequestHandler
import json

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type','application/json')
        self.end_headers()
        message = {"message": "Hello from Python!"}
        self.wfile.write(bytes(json.dumps(message), "utf8"))
        return