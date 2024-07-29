import os
import sys
import redis

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from configs import redis_key
from models import players_model
from scripts.consume_loop_main import loop_func, get_logger, DealDataError
from utils import utils
from utils import oss_upload
from configs import config
import time
import argparse

parser = argparse.ArgumentParser(description="mongo记录游戏玩家消耗")

parser.add_argument("id", help="consume id: .", nargs="?", type=int, default=1)
group = parser.add_mutually_exclusive_group()

group.add_argument("-t", "--tag", help="read message tag: >", default=">")

args = parser.parse_args()

GROUP = f"{redis_key.STREAM_COIN_LOGS_INFO}_consumers"

incr_id = args.id

print(f"init consume {GROUP}{incr_id}")
""" 处理任务有桌子日志。每局详细分数。消费数据。 """

oss_conf = config.get_item("oss_conf")


def _msg_call(msg):
    if not msg:
        return True, ""

    try:
        data = utils.json_decode(msg.get(b"coin_logs"), True)
    except Exception as e:
        return False, str(e)

    players_model.write_coin_logs(**data)

    get_logger().info("save success %s,%s,%s", str(data["uid"]), str(data["comment"]), str(data["record_id"]))

    return True, ""


loop_func(_msg_call, redis_key.STREAM_COIN_LOGS_INFO, GROUP, incr_id, __file__[0:-3], args.tag)
