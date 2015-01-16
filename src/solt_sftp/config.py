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

import ConfigParser
import logging
import optparse
import os
import sys


class config_parser(object):
    def __init__(self, fname=None):
        self.misc = {}
        self.casts = {}
        self.options = {}
        
        self.parser = parser = optparse.OptionParser()
        
        # Server startup config
        group = optparse.OptionGroup(parser, "Common options")
        group.add_option("-c", "--config", dest="config", help="specify alternate config file")
        group.add_option("--pidfile", dest="pidfile", default=False, help="file where the server pid will be stored")
        group.add_option("--sftp-path", dest="sftp_path", help="where the sftp server files will be stored")
        group.add_option("--sftp-key", dest="sftp_key", help="where is the sftp server private key")
        group.add_option("--sftp-port", dest="sftp_port", type="int", default=220, help="in what port the sftp server will be listen")
        parser.add_option_group(group)

        # Logging Group
        group = optparse.OptionGroup(parser, "Logging Configuration")
        group.add_option("--logfile", dest="logfile", default=False, help="file where the server log will be stored")
        group.add_option("--no-logrotate", dest="logrotate", action="store_false", default=True, help="do not rotate the logfile")
        
        levels = ['info', 'warn', 'critical', 'error', 'debug', ]
        group.add_option('--log-level', dest='log_level', type='choice', choices=levels,
            default='info', help='specify the level of the logging. Accepted values: ' + str(levels))
        parser.add_option_group(group)

        group = optparse.OptionGroup(parser, "Database Configuration")
        group.add_option("--redis_channel", dest="redis_channel", default='sftp_users',
                         help="")
        group.add_option("--redis_pass", dest="redis_pass", default=False,
                         help="specify the redis database password")
        group.add_option("--redis_host", dest="redis_host", default=False,
                         help="specify the database host")
        group.add_option("--redis_port", dest="redis_port", default=False,
                         help="specify the database port", type="int")
        group.add_option("--redis_dbindex", dest="redis_dbindex", type='int', default=1,
                         help="specify the redis database index")
        parser.add_option_group(group)

        # Advanced options
        group = optparse.OptionGroup(parser, "Multiprocessing options")
        # TODO sensible default for the three following limits.
        group.add_option("--workers", dest="workers", default=2,
                         help="Specify the number of workers, 0 disable prefork mode.",
                         type="int")
        group.add_option("--limit-memory-soft", dest="limit_memory_soft", default=640 * 1024 * 1024,
                         help="Maximum allowed virtual memory per worker, when reached the worker be reset after the current request (default 671088640 aka 640MB).",
                         type="int")
        group.add_option("--limit-memory-hard", dest="limit_memory_hard", default=768 * 1024 * 1024,
                         help="Maximum allowed virtual memory per worker, when reached, any memory allocation will fail (default 805306368 aka 768MB).",
                         type="int")
        group.add_option("--limit-time-cpu", dest="limit_time_cpu", default=60,
                         help="Maximum allowed CPU time per request (default 60).",
                         type="int")
        group.add_option("--limit-time-real", dest="limit_time_real", default=120,
                         help="Maximum allowed Real time per request (default 120).",
                         type="int")
        group.add_option("--limit-request", dest="limit_request", default=8192,
                         help="Maximum number of request to be processed per worker (default 8192).",
                         type="int")
        parser.add_option_group(group)

        # Copy all optparse options (i.e. MyOption) into self.options.
        no_default = ('NO', 'DEFAULT')
        for group in parser.option_groups:
            for option in group.option_list:
                if option.default != no_default:
                    self.options[option.dest] = option.default
                self.casts[option.dest] = option

    def parse_config(self, args=None):
        """ Parse the configuration file (if any) and the command-line
        arguments.
        """
        if args is None:
            args = []
        opt, args = self.parser.parse_args(args)
    
        def die(cond, msg):
            if cond:
                self.parser.error(msg)
    
        # Ensures no illegitimate argument is silently discarded (avoids insidious "hyphen to dash" problem)
        die(args, "unrecognized parameters: '%s'" % " ".join(args))
        self.config_file = os.path.abspath(opt.config)
        self.load()
    
        # Verify that we want to log or not, if not the output will go to stdout
        if self.options['logfile'] in ('None', 'False'):
            self.options['logfile'] = False
        # the same for the pidfile
        if self.options['pidfile'] in ('None', 'False'):
            self.options['pidfile'] = False
    
        # if defined dont take the configfile value even if the defined value is None
        keys = ['redis_dbindex', 'redis_pass', 'redis_host',
                'redis_port', 'logfile', 'pidfile', 'sftp_path',
        ]
    
        for arg in keys:
            # Copy the command-line argument (except the special case for log_handler, due to
            # action=append requiring a real default, so we cannot use the my_default workaround)
            if getattr(opt, arg):
                self.options[arg] = getattr(opt, arg)
            # ... or keep, but cast, the config file value.
            elif isinstance(self.options[arg], basestring) and self.casts[arg].type in optparse.Option.TYPE_CHECKER:
                self.options[arg] = optparse.Option.TYPE_CHECKER[self.casts[arg].type](self.casts[arg], arg, self.options[arg])
        
        # if defined but None take the configfile value
        keys = [
            'workers', 'limit_memory_hard', 'limit_memory_soft', 'limit_time_cpu', 'limit_time_real', 'limit_request'
        ]
    
        for arg in keys:
            # Copy the command-line argument...
            if getattr(opt, arg) is not None:
                self.options[arg] = getattr(opt, arg)
            # ... or keep, but cast, the config file value.
            elif isinstance(self.options[arg], basestring) and self.casts[arg].type in optparse.Option.TYPE_CHECKER:
                self.options[arg] = optparse.Option.TYPE_CHECKER[self.casts[arg].type](self.casts[arg], arg, self.options[arg])
    
    def load(self):
        p = ConfigParser.ConfigParser()
        try:
            p.read([self.config_file])
            for (name,value) in p.items('options'):
                if value=='True' or value=='true':
                    value = True
                if value=='False' or value=='false':
                    value = False
                self.options[name] = value
            #parse the other sections, as well
            for sec in p.sections():
                if sec == 'options':
                    continue
                if not self.misc.has_key(sec):
                    self.misc[sec]= {}
                for (name, value) in p.items(sec):
                    if value=='True' or value=='true':
                        value = True
                    if value=='False' or value=='false':
                        value = False
                    self.misc[sec][name] = value
        except IOError:
            pass
        except ConfigParser.NoSectionError:
            pass
    
    def get(self, key, default=None):
        return self.options.get(key, default)

    def get_misc(self, sect, key, default=None):
        return self.misc.get(sect,{}).get(key, default)

    def __setitem__(self, key, value):
        self.options[key] = value
        if key in self.options and isinstance(self.options[key], basestring) and \
                key in self.casts and self.casts[key].type in optparse.Option.TYPE_CHECKER:
            self.options[key] = optparse.Option.TYPE_CHECKER[self.casts[key].type](self.casts[key], key, self.options[key])

    def __getitem__(self, key):
        return self.options[key]
    
config = config_parser()