import os
import sys
import redis

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from configs import redis_key
from models import logs_model
from scripts.consume_loop_main import loop_func, get_logger
from utils import utils
import argparse
import datetime

parser = argparse.ArgumentParser(description="mongo gate游戏记录")

parser.add_argument("id", help="consume id: .", nargs="?", type=int, default=1)
group = parser.add_mutually_exclusive_group()

group.add_argument("-t", "--tag", help="read message tag: >", default=">")

args = parser.parse_args()

GROUP = f"{redis_key.STREAM_GATE_LOGS_INFO}_consumers"

incr_id = args.id

print(f"init consume {GROUP}{incr_id}")


def _msg_call(msg):
    try:
        data = utils.json_decode(msg.get(b"gate_logs"), True)
    except Exception as e:
        return False, str(e)

    logs_model.insert_gate_logs(uid=data["uid"],
                                content=data["content"],
                                cmd=data["cmd"],
                                service=data["service"],
                                level=data["level"],
                                send_receive=data["type"],
                                time=datetime.datetime.fromtimestamp(data["time"]))

    get_logger().info("save success %s,%s", str(data["uid"]), str(data["service"]))

    return True, ""


loop_func(_msg_call, redis_key.STREAM_GATE_LOGS_INFO, GROUP, incr_id, __file__[0:-3], args.tag)
