# coding:utf-8

import os
import sys

from base import const
from base.logs import main_logger
from models import servers_model
from utils.daemon import daemonize
from base.base_server import BaseServer
from sys import platform


def _run_server(server_class, server_id, service_type, server_name, server_info):
    main_logger.info('start %s with pid %d', server_name, os.getpid())
    #print('server_id:' + str(server_id))
    server_class.share_server().setup(server_id, service_type, server_name, server_info)
    server_class.share_server().start_service()


def _do_start(server_class, server_id, service_type, server_name, is_gate):
    assert server_id
    assert service_type
    if is_gate:
        server_info = servers_model.get(server_id)
    else:
        server_info = servers_model.get_idle_room(server_id, service_type)

    if not server_info:
        text = f"[Error] {server_name} - [{service_type}] - {server_id} isn't idle server!"
        print(text)
        main_logger.fatal(text)
        sys.exit(0)

    _run_server(server_class, server_id, service_type, server_name, server_info)


def _check_daemon(server_class, server_name, service_type=-1, is_gate=False):
    if not issubclass(server_class, BaseServer):
        return
    #print('server_class:' + str(server_class))
    #print('server_type:' + str(service_type))
    server_id = servers_model.choose_idle_server(service_type) if not is_gate else servers_model.pick_one_idle_gateway()
    #print('server_id_check_daemon:' + str(server_id))
    if not server_id:
        if service_type == const.SERVICE_PUB_SUB:
            server_id = 1
        else:
            return -1, False
    print(f"[{server_name}] is running in server [{server_id}] -"
          f" PID:[{os.getpid()}]")

    is_daemon = False
    if len(sys.argv) >= 2 and sys.argv[1] == 'daemon':
        is_daemon = True

    return server_id, is_daemon


def _init_daemon(server_class, server_name, server_id, is_daemon):

    def on_exit(*args):
        server_class.share_server().on_signal_stop(*args)

    if is_daemon:
        pid_file = const.OUTPUT_PATH + server_name + ".pid" + str(server_id)
        core_dump_file = const.OUTPUT_PATH + server_name + ".log"
        daemonize(pid_file, stderr=core_dump_file, on_exit=on_exit)


def start(server_class, service_type, server_name, is_gate=False):
    assert server_class
    assert server_name
    assert service_type
    
    print(f"Usage: python3 %s.py [daemon] [force]!" % (server_name,))
    if platform in ("darwin", "win32"):
        if 'force' in sys.argv:
            print(f"[Set all server idle...]")
            servers_model.all_gate_shutdown()
            servers_model.all_server_shutdown()

    server_name = server_name.split("/")[-1]
    #print('server_name:' + server_name)
    server_id, is_daemon = _check_daemon(server_class, server_name, service_type, is_gate)
    #print('server_id_2:' + str(server_id))
    _init_daemon(server_class, server_name, server_id, is_daemon)
    _do_start(server_class, server_id, service_type, server_name, is_gate)


def start_router(server_class, service_type, server_name):
    server_name = server_name.split("/")[-1]
    server_id, is_daemon = _check_daemon(server_class, server_name, service_type)
    _init_daemon(server_class, server_name, server_id, is_daemon)
    _run_server(server_class, server_id, service_type, server_name, {})
