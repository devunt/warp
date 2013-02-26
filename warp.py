#!/usr/bin/python
# -*- coding: utf-8 -*-

VERSION = "v0.1 (prototype)"

"""
Copyright (c) 2013 devunt

Permission is hereby granted, free of charge, to any person
obtaining a copy of this software and associated documentation
files (the "Software"), to deal in the Software without
restriction, including without limitation the rights to use,
copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following
conditions:

The above copyright notice and this permission notice shall be
included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
OTHER DEALINGS IN THE SOFTWARE.
"""

from threading import Thread
from Queue import Queue
from socket import (AF_INET, IPPROTO_TCP, SO_REUSEADDR, SOCK_STREAM,
                    SOL_SOCKET, TCP_NODELAY, socket)
from re import compile
from time import sleep

REGEX_HOST = compile(r'(^:+):([0-9]{1,5})')
REGEX_CONTENT_LENGTH = compile(r'$Content-Length: ([0-9]+)^')
REGEX_PROXY_CONNECTION = compile(r'$Proxy-Connection: (.+)^')
REGEX_PROXY_CONNECTION = compile(r'\r\nProxy-Connection: (.+)\r\n')
REGEX_CONNECTION = compile(r'$Connection: (.+)^')

class WorkerThread(Thread):
    def __init__(self, n, q):
        self.n = n
        self.q = q
        Thread.__init__(self)
        print 'Worker #%d init' % n

    def run(self):
        print 'Worker #%d started' % self.n
        while True:
            conn, addr = self.q.get(block=True)
            print 'Worker #%d: Accept new task' % self.n
            cont = ''
            try:
                while True:
                    data = conn.recv(1024)
                    if not data:
                        break
                    cont += data
                    if data.find('\r\n\r\n') != -1:
                        break
                m = REGEX_CONTENT_LENGTH.search(cont)
                if m:
                    cl = int(m.group(1))
                    ct = cont.split('\r\n\r\n')[1]
                    while (len(ct) != cl):
                        data = conn.recv(1024)
                        ct += data
                    cont = cont.split('\r\n\r\n')[0] + '\r\n\r\n' + ct
            except:
                pass


            m = REGEX_PROXY_CONNECTION.search(cont)
            if not m:
                self.q.task_done()
                print '!!! Worker #%d: Task reject' % self.n
                return

            req = cont.split('\r\n')
            if len(req) < 4:
                self.q.task_done()
                print '!!! Worker #%d: Task reject' % self.n
                return
            head = req[0].split(' ')
            phost = False
            sreq = []
            for line in req[1:]:
                if "Host: " in line:
                    phost = line[6:]
                elif not 'Proxy-Connection' in line:
                    sreq.append(line)
            m = REGEX_CONNECTION.search(cont)
            if m:
                sreq.append("Connection: %s" % m.group(1))
            else:
                sreq.append("Connection: close")

            if not phost:
                phost = '127.0.0.1'
            path = head[1][len(phost)+7:]

            print 'Worker #%d: Process - %s' % (self.n, req[0])

            new_head = ' '.join([head[0], path, head[2]])

            m = REGEX_HOST.search(phost)
            if m:
                host = m.group(1)
                port = int(m.group(2))
            else:
                host = phost
                port = 80

            try:
                req_sc = socket(AF_INET, SOCK_STREAM)
                req_sc.setsockopt(IPPROTO_TCP, TCP_NODELAY, 1)
                req_sc.connect((host, port))
                req_sc.send('%s\r\n' % new_head)

                req_sc.send('Host: ')
                for c in phost:
                    req_sc.send(c)
                req_sc.send('\r\n')

                req_sc.send('\r\n'.join(sreq))
                req_sc.send('\r\n\r\n')

            except:
                pass

            while True:
                try:
                    buf = req_sc.recv(1024)
                    if len(buf) == 0:
                        break
                    conn.send(buf)
                except:
                    pass

            req_sc.close()
            conn.close()

            print 'Worker #%d: Task done' % self.n
            self.q.task_done()


class Server(object):
    def __init__(self, hostname, port):
        self.hostname = hostname
        self.port = port
        self.q = Queue()

    def start(self):
        for i in range(1, 65):
            th = WorkerThread(i, self.q)
            th.daemon = True
            th.start()
            sleep(0.01)
        self.sc = socket(AF_INET, SOCK_STREAM)
        self.sc.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        self.sc.bind((self.hostname, self.port))
        self.sc.listen(10)

        while True:
            self.q.put(self.sc.accept())

if __name__ == '__main__':
    server = Server('127.0.0.1', 8800)
    try:
        server.start()
    except KeyboardInterrupt:
        print 'bye'
