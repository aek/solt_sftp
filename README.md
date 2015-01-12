# solt_sftp
Gevent SFTP server based on Paramiko

The idea behind solt_sftp is to provide an SFTP server implementation that can be used to solve those situation where OpenSSH is not a solution.
This SFTP implementation is based on Paramiko but taken the idea and functional code to bring up a solution based on gevent coroutines instead of threads.

This SFTP implementation supports only publickey authentication, even when add the rest of security options is a matter of code a little more.
Redis is used to store the users configuration and Redis PubSub channels used to notify for changes in the user config to reload the changed data without restarting the server.
The user data in Redis is stored under the keys:
```
'solt.sftp.users': a Redis Set DataType to hold the users ids typically integers used to retrieve the user data.
'solt.sftp.user.#': a Redis Hash DataType to store the user fields data ('name', 'folder', 'active'). The # in the keys refers to the id of the user that the data belong.
'solt.sftp.user.#.keys': a Redis Set DataType to hold the user ssh-keys used to authenticate the ssh sessions. The # in the keys refers to the id of the user that the ssh-keys belong.
```

At startup the server load the user data from Redis and also get subscribed to a channel in Redis listening for message notifications to dinamically update the user config. The message expected is simply the id of the user whoom data has changed. The responsability of update the user data in Redis is external to the server.

Here is a simply python script that add a new user to Redis an notify about the new user created:
```
import redis
redis_conn = redis.Redis('localhost',6379, 1, None)
next_user_id = redis_conn.scard('solt.sftp.users') + 1
redis_conn.sadd('solt.sftp.users', next_user_id)
redis_conn.hmset('solt.sftp.user.%s'% next_user_id, {'name': 'test','active': True,})
redis_conn.sadd('solt.sftp.user.%s.keys'% next_user_id, 'AAVGB3NzaC1yc2EAFSADAQABAAABAQDq5t4e2WSKMzC2q0tOnl3c+UTj/LJoE9lMJubYGY95GbvIxOIBa+dDpd/wFhMiDxz7vNpb5JH2rrJFzisHmW+2fb5tkTZhoXMtaU2Z3ble61DvyBS2mtBE/uc2e5XCNdNSx17fuPRIHFT0o1kJJcibY+fXz81XYZGzSTXfHO7fX99M1oWD2SCU6Yv/kOsD9YBsop+MPc7czMwDX9sftevZ2G0f3+gN/1tC3iQUUHxaemPqin9dsdiqTVk/0gAiq1T5PE6vb0vo1g64UZElvmhtN2nBsteMhQiblVoMJzusmMwMiD1dMSp2VA2a8NcYx+hUMdPODqGDBSowmTQ/7n/7')
redis_conn.publish('sftp_users', str(next_user_id))
```
You could use the Redis publish to the channel method to update or create users or simply restart the server.

When a user without an existing folder in the OS is detected, a new folder is created and setted to the user in Redis and the server users config.

There are some options that you can configure at the moment. Here is a sample configuration file of the options with their default values:
```
[options]
sftp_port=2200
sftp_path=/opt/solt_sftp/files
log_level=info
logfile=False
redis_host=localhost
redis_port=6379
redis_dbindex=1
redis_pass=None
redis_channel=sftp_users
```

You can specify those options in a config file or directly in the commandline with the prefix --. The config file can be passed using --config option in the commandline

To startup the server you could simply do:
```
python solt_sftp.py --config solt_sftp.conf
```

Bugs reports, feedbacks and contributions are wellcome. Enjoy it
