import os, sys, http.server, socketserver

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "out"))
port = int(sys.argv[1]) if len(sys.argv) > 1 else 3000

handler = http.server.SimpleHTTPRequestHandler
with socketserver.TCPServer(("", port), handler) as httpd:
    print(f"Serving on http://localhost:{port}")
    httpd.serve_forever()
