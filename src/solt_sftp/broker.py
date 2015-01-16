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
        self.ids_to_users = {}
        
        self.sftp_user_ids = self.redis_conn.smembers('solt_sftp:users')
        if self.sftp_user_ids:
            for user_id in self.sftp_user_ids:
                self.on_channel_user_handle({'data':user_id})
        else:
            self.sftp_user_ids = []
        
        self.subscriber = self.redis_conn.pubsub()
        self.subscriber_greenlet = gevent.spawn(self.listener)
    
    def on_channel_user_handle(self, message):
        user_id = message.get('data')
        user_key = 'solt_sftp:user:%s' % user_id
        user_ssh_key = user_key+':keys'
        user_obj = self.redis_conn.hgetall(user_key)
        
        if user_obj:
            if self.ids_to_users.get(user_id,False) and \
                    self.authorized_keys.get(user_obj.get('name'), False) and \
                    self.authorized_keys.get(user_obj.get('name')).get('id') != user_id: 
                existing_user = self.ids_to_users.get(self.authorized_keys.get(user_obj.get('name')).get('id'), False) #username of mapped id
                if existing_user and existing_user != user_obj.get('name'):
                    _logger.error("Already existing username with different ID - actual: (id,%s => user,%s) new: (user,%s => id,%s) -", user_id, self.ids_to_users[user_id], user_obj.get('name'), self.authorized_keys[user_obj.get('name')].get('id'))
                    return
            else:
                if self.ids_to_users.get(user_id,False):
                    self.ids_to_users[user_id] = user_obj.get('name')
            if user_obj.get('folder', False):
                folder = user_obj.get('folder')
            else:
                folder = uuid.uuid4().hex
                self.redis_conn.hset(user_key, 'folder', folder)
            real_path = '%s/%s'%(self.root_folder,folder)
            if not os.path.exists(real_path):
                os.makedirs(real_path)
            user_ssh = self.redis_conn.smembers(user_ssh_key)
            self.authorized_keys[user_obj.get('name')] = {
                'id': user_id,
                'name': user_obj.get('name'),
                'ssh-keys': tuple(user_ssh),
                'active': user_obj.get('active'),
                'folder': folder,
            }
        elif self.ids_to_users.get(user_id,False):
            self.authorized_keys.pop(self.ids_to_users.get(user_id), False)
            self.ids_to_users.pop(user_id, False)

    def listener(self):
        self.subscriber.subscribe(self.channel)
        try:
            try:
                while True:
                    for msg in self.subscriber.listen():
                        self.on_channel_user_handle(msg)
            except redis.ConnectionError, e:
                if e.message not in EXPECTED_CONNECTION_ERRORS:
                    _logger.info('Caught `%s`, will quit now', e.message)
                    raise
        except KeyboardInterrupt:
            pass
        
    def channel_users_update(self):
        user_ids = self.redis_conn.smembers('solt_sftp:users')
        if user_ids:
            user_list = [{'data':user} for user in user_ids if user not in self.ids_to_users]
            if user_list:
                for user_data in user_list:
                    self.on_channel_user_handle(user_data)