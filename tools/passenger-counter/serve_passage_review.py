"""Local-only source-frame review; does not run a detector or change its truth."""
import argparse
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import parse_qs,urlsplit
from passage_review import ReviewSession


def serve(session,port):
    page=Path(__file__).with_name('passage_review.html').read_bytes()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def send(self,status,data,kind='application/json; charset=utf-8'):
            if isinstance(data,dict):data=json.dumps(data,ensure_ascii=False).encode('utf-8')
            self.send_response(status);self.send_header('Content-Type',kind)
            self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(data)
        def do_GET(self):
            try:
                if self.headers.get('Host') not in (f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'):
                    return self.send(403,dict(error='Local review host required'))
                url=urlsplit(self.path)
                if url.path=='/':return self.send(200,page,'text/html; charset=utf-8')
                if url.path=='/manifest':return self.send(200,session.manifest)
                if url.path=='/frame':
                    values=parse_qs(url.query).get('index',[])
                    if len(values)!=1:raise ValueError('One frame index required')
                    return self.send(200,session.frame(int(values[0])),'image/jpeg')
                return self.send(404,dict(error='Unknown route'))
            except (ValueError,TypeError) as error:self.send(400,dict(error=str(error)))
        def do_POST(self):
            try:
                if self.headers.get('Host') not in (f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'):
                    return self.send(403,dict(error='Local review host required'))
                if self.path!='/save':return self.send(404,dict(error='Unknown route'))
                if self.headers.get('Content-Type','').split(';')[0]!='application/json':
                    return self.send(415,dict(error='JSON review required'))
                origin=self.headers.get('Origin')
                if origin is not None and origin not in (f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}'):
                    return self.send(403,dict(error='Local review origin required'))
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=131072:raise ValueError('Invalid review request length')
                return self.send(200,session.save(json.loads(self.rfile.read(size))))
            except (ValueError,TypeError) as error:self.send(400,dict(error=str(error)))
    return ThreadingHTTPServer(('127.0.0.1',port),Handler)


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--port',type=int,default=8872)
    a=p.parse_args();session=ReviewSession(a.source,a.output);server=serve(session,a.port)
    print(f'http://127.0.0.1:{a.port} source_frames={session.manifest["frames"]}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()


if __name__=='__main__':main()
