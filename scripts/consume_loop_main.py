import os
import redis
import sys

from base import const
from models import database
import time
import signal

import logging
import logging.handlers
import traceback
import pysnooper

_format = '%(asctime)s - %(process)d:%(filename)s:%(lineno)s:%(levelname)s - %(message)s'
_max_bytes = 1024 * 1024
_back_up_count = 50

_consume_file_name = "__consume__"
_log_level = logging.INFO

is_sigint_up = False


class DealDataError(Exception):

    def __str__(self):
        return "deal data error"


def sigint_handler(signum, frame):
    global is_sigint_up
    is_sigint_up = True
    get_logger().info('catched interrupt signal!')


signal.signal(signal.SIGINT, sigint_handler)
signal.signal(signal.SIGHUP, sigint_handler)
signal.signal(signal.SIGTERM, sigint_handler)


def read_msg(msg_call, stream_key, group_id, consume_id, tag=">"):
    logger = get_logger()
    data_list = database.share_redis_game().xreadgroup(groupname=group_id,
                                                       streams={stream_key: tag},
                                                       consumername=group_id + str(consume_id),
                                                       block=1000)

    for data in data_list:
        for read_data_info in data[1]:
            message_id = read_data_info[0]
            message_info = read_data_info[1]

            logger.debug(read_data_info)

            if message_info == {b'null': b'null'}:
                logger.info("check is ok")
                database.share_redis_game().xack(stream_key, group_id, message_id)
            else:
                try:
                    is_ok, error = msg_call(message_info)
                except Exception as e:
                    is_ok, error = False, str(e)

                if is_ok:
                    database.share_redis_game().xack(stream_key, group_id, message_id)
                else:
                    error_stack = traceback.format_exc()
                    logger.error(error_stack + error + str(message_info))


def get_logger():
    logger = logging.getLogger(_consume_file_name)
    return logger


def init_logger(file_path):
    logger = get_logger()

    logger.setLevel(_log_level)
    handler = logging.handlers.RotatingFileHandler(file_path,
                                                   mode="aw+",
                                                   maxBytes=_max_bytes,
                                                   backupCount=_back_up_count)
    formatter = logging.Formatter(_format)  # 实例化formatter
    handler.setFormatter(formatter)  # 为handler添加formatter
    logger.addHandler(handler)


def loop_func(msg_call, stream_key, group_key, consume_id, consume_name, tag=">", interval=0.01):
    global is_sigint_up

    consume_name = consume_name.split("/")[-1]
    consume_name = consume_name.split(".")[0]

    os.makedirs(const.OUTPUT_PATH + "scripts/logs/" + consume_name, exist_ok=True)

    pid_file = const.OUTPUT_PATH + "scripts/" + consume_name + ".pid" + str(consume_id)
    core_dump_file = const.OUTPUT_PATH + "scripts/logs/" + consume_name + "/" + consume_name + str(consume_id) + ".log"
    init_logger(core_dump_file)

    # if os.path.exists(pid_file):
    #     raise RuntimeError('Already running')

    # with open(pid_file, 'w') as f:
    #     print(os.getpid(), file=f)

    try:
        database.share_redis_game().xadd(stream_key, {"null": "null"})
        database.share_redis_game().xgroup_create(stream_key, group_key)
    except redis.exceptions.ResponseError as e:
        get_logger().info(e)

    while True:
        try:
            read_msg(msg_call, stream_key, group_key, consume_id, tag)
        except Exception as e:
            get_logger().error(e)
            print(e, file=sys.stderr)
            time.sleep(interval * 1000)
        else:
            time.sleep(interval)
        if is_sigint_up:
            # os.remove(pid_file)
            break
