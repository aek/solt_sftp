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

from gevent.event import Event

#monkey.patch_all()

from binascii import hexlify
import os
import sys

import paramiko
from paramiko.py3compat import u

from wrapper import sftp_wrapper
from broker import solt_broker

from config import config

solt_sftp_key = paramiko.RSAKey.from_private_key_file(config.get('sftp_key', 'solt_sftp.key'))

redis_broker = solt_broker()

class solt_interface(paramiko.ServerInterface):
    def __init__(self, *largs, **kwargs):
        self.shell = Event()
        self.broker = kwargs.get('broker', None)
        self.wrapper = kwargs.get('wrapper', None)

    def check_channel_request(self, kind, chanid):
        if kind == 'session':
            return paramiko.OPEN_SUCCEEDED
        return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def check_auth_password(self, username, password):
        return paramiko.AUTH_FAILED

    def check_auth_publickey(self, username, key):
        print('Auth attempt for '+username+' with key: ' + u(hexlify(key.get_fingerprint())))
        user_cfg = self.broker.authorized_keys.get(username, False)
        if not user_cfg:
            self.broker.channel_users_update()
            user_cfg = self.broker.authorized_keys.get(username, False)
        if user_cfg and user_cfg.get('active', False) == 'True' and key.get_base64() in user_cfg.get('ssh-keys',[]):
            return paramiko.AUTH_SUCCESSFUL
        return paramiko.AUTH_FAILED
    
    def check_auth_gssapi_with_mic(self, username,
                                   gss_authenticated=paramiko.AUTH_FAILED,
                                   cc_file=None):
        return paramiko.AUTH_FAILED

    def check_auth_gssapi_keyex(self, username,
                                gss_authenticated=paramiko.AUTH_FAILED,
                                cc_file=None):
        return paramiko.AUTH_FAILED

    def enable_auth_gssapi(self):
        return False

    def get_allowed_auths(self, username):
        return 'publickey'

    def check_channel_shell_request(self, channel):
        self.shell.set()
        return True
    
    def check_channel_pty_request(self, channel, term, width, height, pixelwidth,
                                  pixelheight, modes):
        return True
    
    def get_fs_path(self, sftp_path):
        username = self.wrapper.get_username()
        folder = self.broker.authorized_keys.get(username).get('folder')
        real_path = "%s/%s/%s" % (self.broker.root_folder,folder,sftp_path)
        real_path = real_path.replace('//', '/')
        
        if not os.path.realpath(real_path).startswith(self.broker.root_folder):
            raise Exception("Invalid path")

        return real_path

    def open(self, path, flags, attr):
        return True

    def list_folder(self, path):
        real_path = self.get_fs_path(path)
        rc = []
        for filename in os.listdir(real_path):
            full_name = ("%s/%s" % (real_path, filename)).replace("//", "/")
            rc.append(paramiko.SFTPAttributes.from_stat(os.stat(full_name), filename.replace(self.broker.root_folder, '')))
        return rc
 
    def stat(self, path):
        real_path = self.get_fs_path(path)
        return paramiko.SFTPAttributes.from_stat(os.stat(real_path), path)

    def lstat(self, path):
        return self.stat(path)

    def remove(self, path):
        real_path = self.get_fs_path(path)
        os.remove(real_path)
        paramiko.SFTP_OK

    def rename(self, oldpath, newpath):
        real_oldpath = self.get_fs_path(oldpath)
        real_newpath = self.get_fs_path(newpath)
        os.rename(real_oldpath, real_newpath)
        return paramiko.SFTP_OK

    def mkdir(self, path, attr):
        real_path = self.get_fs_path(path)
        os.makedirs(real_path)
        return paramiko.SFTP_OK

    def rmdir(self, path):
        real_path = self.get_fs_path(path)
        os.rmdir(real_path)
        return paramiko.SFTP_OK

    def chattr(self, path, attr):
        return paramiko.SFTP_OK

    def canonicalize(self, path):
        real_path = self.get_fs_path(path)
        if os.path.isabs(real_path):
            out = os.path.normpath(real_path)
        else:
            out = os.path.normpath('/' + real_path)
        if sys.platform == 'win32':
            # on windows, normalize backslashes to sftp/posix format
            out = out.replace('\\', '/')
        return out

    def readlink(self, path):
        return paramiko.SFTP_OP_UNSUPPORTED

    def symlink(self, path):
        return paramiko.SFTP_OP_UNSUPPORTED
    
    def session_started(self):
        pass

try:
    sftp_wrapper.load_server_moduli()
except:
    print('(Failed to load moduli -- gex will be unsupported.)')
    raise

def handle_sftp_session(sock, address):
    server_interface = solt_interface(broker=redis_broker)
    session = sftp_wrapper(sock, server_mode = True, server_object=server_interface, active=True)
    session.set_subsystem_handler('sftp', paramiko.SFTPServer, sftp_si=solt_interface, broker=redis_broker, wrapper=session)
    
    session.add_server_key(solt_sftp_key)
    
    session.run()
