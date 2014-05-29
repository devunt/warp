#!/usr/bin/python
# -*- coding: utf-8 -*-

VERSION = "v0.1.1 (poc code)"

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

import sys
if sys.hexversion < 0x3040000:
    print('Error: You need python 3.4.0 or above. exit.')
    exit(1)

from argparse import ArgumentParser
from socket import TCP_NODELAY
from time import time
from traceback import print_exc
import asyncio
import logging
import random
import re


REGEX_HOST = re.compile(r'(.+?):([0-9]{1,5})')
REGEX_CONTENT_LENGTH = re.compile(r'\r\nContent-Length: ([0-9]+)\r\n')
REGEX_PROXY_CONNECTION = re.compile(r'\r\nProxy-Connection: (.+)\r\n')
REGEX_CONNECTION = re.compile(r'\r\nConnection: (.+)\r\n')
REGEX_USER_AGENTS_WITHOUT_PROXY_CONNECTION_HEADER = re.compile(r'\r\nUser-Agent: .*(Firefox|Opera).+\r\n')

clients = {}

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] {%(levelname)s} %(message)s')
logging.getLogger('asyncio').setLevel(logging.CRITICAL)
logger = logging.getLogger('warp')
verbose = 0


def accept_client(client_reader, client_writer):
    ident = hex(id(client_reader))[-6:]
    task = asyncio.Task(process_warp(client_reader, client_writer))
    clients[task] = (client_reader, client_writer)
    started_time = time()

    def client_done(task):
        del clients[task]
        client_writer.close()
        logger.debug('[%s] Connection closed (took %.5f seconds)' % (ident, time() - started_time))

    logger.debug('[%s] Connection started' % ident)
    task.add_done_callback(client_done)


@asyncio.coroutine
def process_warp(client_reader, client_writer):
    ident = str(hex(id(client_reader)))[-6:]
    header = ''
    payload = b''
    try:
        RECV_MAX_RETRY = 3
        recvRetry = 0
        while True:
            line = yield from client_reader.readline()
            if not line:
                if len(header) == 0 and recvRetry < RECV_MAX_RETRY:
                    # handle the case when the client make connection but sending data is delayed for some reasons
                    recvRetry += 1
                    yield from asyncio.sleep(0.2)
                    continue
                else:
                    break
            if line == b'\r\n':
                break
            if line != b'':
                header += line.decode('utf-8')

        m = REGEX_CONTENT_LENGTH.search(header)
        if m:
            cl = int(m.group(1))
            while (len(payload) < cl):
                payload += yield from client_reader.read(1024)
    except:
        print_exc()

    if len(header) == 0:
        logger.debug('[%s] !!! Task reject (empty request)' % ident)
        return

    m1 = REGEX_PROXY_CONNECTION.search(header)
    m2 = REGEX_USER_AGENTS_WITHOUT_PROXY_CONNECTION_HEADER.search(header)
    if not m1 and not m2:
        logger.debug('[%s] !!! Task reject (no Proxy-Connection header)' % ident)
        return

    req = header.split('\r\n')[:-1]
    if len(req) < 4:
        logger.debug('[%s] !!! Task reject (invalid request)' % ident)
        return
    head = req[0].split(' ')
    if head[0] == 'CONNECT': # https proxy
        try:
            logger.info('%sBYPASSING <%s %s> (SSL connection)' % ('[%s] ' % ident if verbose >= 1 else '', head[0], head[1]))
            m = REGEX_HOST.search(head[1])
            host = m.group(1)
            port = int(m.group(2))
            req_reader, req_writer = yield from asyncio.open_connection(host, port, ssl=False)
            client_writer.write(b'HTTP/1.1 200 Connection established\r\n\r\n')
            @asyncio.coroutine
            def relay_stream(reader, writer):
                try:
                    while True:
                        line = yield from reader.read(1024)
                        if len(line) == 0:
                            break
                        writer.write(line)
                except:
                    print_exc()
            tasks = [
                asyncio.Task(relay_stream(client_reader, req_writer)),
                asyncio.Task(relay_stream(req_reader, client_writer)),
            ]
            yield from asyncio.wait(tasks)
        except:
            print_exc()
        finally:
            return
    phost = False
    sreq = []
    sreqHeaderEndIndex = 0
    for line in req[1:]:
        headerNameAndValue = line.split(': ', 1)
        if len(headerNameAndValue) == 2:
            headerName, headerValue = headerNameAndValue
        else:
            headerName, headerValue = headerNameAndValue[0], None

        if headerName == "Host":
            phost = headerValue
        elif headerName == "Connection":
            if headerValue.lower() in ('keep-alive', 'persist'):
                sreq.append("Connection: close")    # current version of this program does not support the HTTP keep-alive feature
            else:
                sreq.append(line)
        elif headerName != 'Proxy-Connection':
            sreq.append(line)
            if len(line) == 0 and sreqHeaderEndIndex == 0:
                sreqHeaderEndIndex = len(sreq) - 1
    if sreqHeaderEndIndex == 0:
        sreqHeaderEndIndex = len(sreq)

    m = REGEX_CONNECTION.search(header)
    if not m:
        sreq.insert(sreqHeaderEndIndex, "Connection: close")

    if not phost:
        phost = '127.0.0.1'
    path = head[1][len(phost)+7:]

    logger.info('%sWARPING <%s %s>' % ('[%s] ' % ident if verbose >= 1 else '', head[0], head[1]))

    new_head = ' '.join([head[0], path, head[2]])

    m = REGEX_HOST.search(phost)
    if m:
        host = m.group(1)
        port = int(m.group(2))
    else:
        host = phost
        port = 80

    try:
        req_reader, req_writer = yield from asyncio.open_connection(host, port, flags=TCP_NODELAY)
        req_writer.write(('%s\r\n' % new_head).encode('utf-8'))
        yield from req_writer.drain()
        yield from asyncio.sleep(0.2)

        def generate_dummyheaders():
            def generate_rndstrs(strings, length):
                return ''.join(random.choice(strings) for _ in range(length))
            import string
            return ['X-%s: %s\r\n' % (generate_rndstrs(string.ascii_uppercase, 16), generate_rndstrs(string.ascii_letters + string.digits, 128))
                    for _ in range(32)]

        req_writer.writelines(list(map(lambda x: x.encode('utf-8'), generate_dummyheaders())))
        yield from req_writer.drain()

        req_writer.write(b'Host: ')
        yield from req_writer.drain()
        def feed_phost(phost):
            i = 1
            while phost:
                yield random.randrange(2, 4), phost[:i]
                phost = phost[i:]
                i = random.randrange(2, 5)
        for delay, c in feed_phost(phost):
            yield from asyncio.sleep(delay/10.0)
            req_writer.write(c.encode('utf-8'))
            yield from req_writer.drain()
        req_writer.write(b'\r\n')
        req_writer.writelines(list(map(lambda x: (x + '\r\n').encode('utf-8'), sreq)))
        req_writer.write(b'\r\n')
        if payload != b'':
            req_writer.write(payload)
            req_writer.write(b'\r\n')
        yield from req_writer.drain()

        try:
            while True:
                buf = yield from req_reader.read(1024)
                if len(buf) == 0:
                    break
                client_writer.write(buf)
        except:
            print_exc()

    except:
        print_exc()

    client_writer.close()


@asyncio.coroutine
def start_warp_server(host, port):
    try:
        yield from asyncio.start_server(accept_client, host=host, port=port)
    except error as e:
        logger.critical('!!! Fail to bind server at [%s:%d]: %s' % (host, port, e.args[1]))
        return 1
    logger.info('Server bound at [%s:%d].' % (host, port))


def main():
    """CLI frontend function.  It takes command line options e.g. host,
    port and provides `--help` message.

    """
    parser = ArgumentParser(description='Simple HTTP transparent proxy')
    parser.add_argument('-H', '--host', default='127.0.0.1',
                      help='Host to listen [default: %(default)s]')
    parser.add_argument('-p', '--port', type=int, default=8800,
                      help='Port to listen [default: %(default)d]')
    parser.add_argument('-v', '--verbose', action='count', default=0,
                      help='Print verbose')
    args = parser.parse_args()
    if not (1 <= args.port <= 65535):
        parser.error('port must be 1-65535')
    if args.verbose >= 3:
        parser.error('verbose level must be 1-2')
    if args.verbose >= 1:
        logger.setLevel(logging.DEBUG)
    if args.verbose >= 2:
        logging.getLogger('warp').setLevel(logging.DEBUG)
        logging.getLogger('asyncio').setLevel(logging.DEBUG)
    global verbose
    verbose = args.verbose
    loop = asyncio.get_event_loop()
    try:
        asyncio.async(start_warp_server(args.host, args.port))
        loop.run_forever()
    except KeyboardInterrupt:
        print('bye')
    finally:
        loop.close()


if __name__ == '__main__':
    exit(main())
