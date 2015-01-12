'''
Created on Jan 11, 2015

@author: aek
'''
import redis
redis_conn = redis.Redis('localhost',6379, 1, None)
redis_conn.sadd('solt.sftp.users', 2)
redis_conn.hmset('solt.sftp.user.2', {'name': 'test','active': True,})
redis_conn.sadd('solt.sftp.user.2.keys', 'AAAAB3NzaC1yc2EAAAADAQABAAABAQDq5t4e2WXHMzC2q0tOnl3c+UTj/LJoE9lMJubYED95GbvIxOIBa+dDpd/wFhMiDxz7vNpb5JH2rrJFzisHmW+2fb5tkTZhoXMtaU2Z3ble61DvyBS2mtBE/uc2e5XCNdNSx17fuPRIHFT0o1kJJcibY+fXz81XYZGzSTXfHO7fX99M1oWD2SCU6Yv/kOsD9YBsop+MPc7czMwDX9sftevZ2G0f3+gN/1tC3iQUUHxaemPqin9dsdiqTVk/0gAiq1T5PE6vb0vo1g64UZElvmhtN2nBsteMhQiblVoMJzusmMwMiD1dMSp2VA2a8NcYx+hUMdPODqGDBSowmTQ/7n/7')

redis_conn.publish('sftp_users', '2')

print 'publicado'
