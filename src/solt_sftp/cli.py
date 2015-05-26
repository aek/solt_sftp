# -*- coding: utf-8 -*-
"""
The MIT License (MIT)

Copyright (c) 2015 Axel Mendoza <aekroft@gmail.com>

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

from paramiko.rsakey import RSAKey

import os
import sys
import logging

from config import config
from logger import init_logger

import SocketServer

_logger = logging.getLogger(__name__)

dsn_template = '{db_driver}://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}'

commands = {}

def check_root_user():
    """ Exit if the process's user is 'root' (on POSIX system)."""
    if os.name == 'posix':
        import pwd
        if pwd.getpwuid(os.getuid())[0] == 'root' :
            sys.stderr.write("Running as user 'root' is a security risk, aborting.\n")
            sys.exit(1)

def setup_pid_file():
    """ Create a file with the process id written in it.

    This function assumes the configuration has been initialized.
    """
    if config['pidfile']:
        _logger.info(config['pidfile'])
        fd = open(config['pidfile'], 'w')
        pidtext = "%d" % (os.getpid())
        fd.write(pidtext)
        fd.close()
        

def main():
    args = sys.argv[1:]
    config.parse_config(args)
    
    check_root_user()
    init_logger()
    setup_pid_file()

    from server import handle_sftp_session
    class solt_tcp_handler(SocketServer.BaseRequestHandler):
    
        def handle(self):
            handle_sftp_session(self.request, self.client_address)
    
    server = SocketServer.ThreadingTCPServer(('0.0.0.0', int(config.options.get('sftp_port',2200))), solt_tcp_handler)
    _logger.info('Solt SFTP server is running and waiting for connections...')
    try:
        server.serve_forever()
    except (SystemExit,KeyboardInterrupt):
        server.close()
        
# def create_database():
#     models.Base.metadata.create_all(engine)

def create_new_key():
    key = RSAKey.generate(2048)
    key.write_private_key_file('solt_sftp.key')
