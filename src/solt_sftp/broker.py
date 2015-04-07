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

import logging
import gevent

import redis
import uuid
import os
redis.connection.socket = gevent.socket

from config import config

REMOTE_END_CLOSED_SOCKET = 'Socket closed on remote end'
FILE_DESCR_CLOSED_IN_ANOTHER_GREENLET = "Error while reading from socket: (9, 'File descriptor was closed in another greenlet')"

EXPECTED_CONNECTION_ERRORS = [REMOTE_END_CLOSED_SOCKET, FILE_DESCR_CLOSED_IN_ANOTHER_GREENLET]

_logger = logging.getLogger(__name__)

class solt_broker(object):
    
    def __init__(self, *args, **kwargs):
        self.redis_conn = redis.Redis(config.get('redis_host', 'localhost'),
                                 int(config.get('redis_port', 6379)), 
                                 int(config.get('redis_dbindex', 1)), 
                                 password=config.get('redis_pass', None))
        self.channel = config.get('redis_channel', 'solt_sftp')
        self.root_folder = config.get('sftp_path','/opt/solt_sftp/files')
        
        self.authorized_keys = {}
        
        self.sftp_user_ids = self.redis_conn.hgetall('solt_sftp:user')
        if self.sftp_user_ids:
            for user_name in self.sftp_user_ids:
                self.on_channel_user_handle({'data':user_name})
        else:
            self.sftp_user_ids = []
        
        self.subscriber = self.redis_conn.pubsub()
        self.subscriber_greenlet = gevent.spawn(self.listener)
    
    def on_channel_user_handle(self, message):
        user_name = message.get('data')
        user_id = self.sftp_user_ids[user_name]
        user_key = 'solt_sftp:user:%s:data' % user_id
        user_ssh_key = 'solt_sftp:user:%s:keys' % user_id
        user_data = self.redis_conn.hgetall(user_key)
        
        if user_data:
            if user_data.get('folder', False):
                folder = user_data.get('folder')
            else:
                folder = uuid.uuid4().hex
                self.redis_conn.hset(user_key, 'folder', folder)
            real_path = '%s/%s'%(self.root_folder,folder)
            if not os.path.exists(real_path):
                os.makedirs(real_path)
            user_ssh = self.redis_conn.smembers(user_ssh_key)
            
            _logger.info("Add user %s", user_data.get('name'))
            self.authorized_keys[user_name] = {
                'id': user_id,
                'name': user_data.get('name'),
                'ssh-keys': tuple(user_ssh),
                'active': user_data.get('active'),
                'folder': folder,
            }
        
    def listener(self):
        self.subscriber.subscribe(self.channel)
        try:
            try:
                while True:
                    for msg in self.subscriber.listen():
                        _logger.info('Message received in Redis channel for user management: %s', msg)
                        self.on_channel_user_handle(msg)
            except redis.ConnectionError, e:
                if e.message not in EXPECTED_CONNECTION_ERRORS:
                    _logger.info('Caught `%s`, will quit now', e.message)
                    raise
        except KeyboardInterrupt:
            pass
        
    def channel_user_update(self, user_name):
        user_id = self.redis_conn.hget('solt_sftp:user', user_name)
        if user_id:
            self.on_channel_user_handle({'data':user_name})