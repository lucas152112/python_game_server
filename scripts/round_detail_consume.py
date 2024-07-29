import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from configs import redis_key
from models import logs_model
from scripts.consume_loop_main import loop_func, get_logger, DealDataError
from utils import utils
from utils import oss_upload
from configs import config
import time
import argparse

parser = argparse.ArgumentParser(description="日志上传消费者")

parser.add_argument("id", help="consume id: .", nargs="?", type=int, default=1)
group = parser.add_mutually_exclusive_group()

group.add_argument("-t", "--tag", help="read message tag: >", default=">")

args = parser.parse_args()

GROUP = f"{redis_key.STREAM_ROUND_DETAILS_INFO}_consumers"

incr_id = args.id

print(f"init consume {GROUP}{incr_id}")
""" 处理任务有桌子日志。每局详细分数。消费数据。 """

oss_conf = config.get_item("oss_conf")


def _msg_call(msg):
    if not msg:
        return True, ""

    try:
        data = utils.json_decode(msg.get(b"round_info"), True)
    except Exception as e:
        return False, str(e)

    # 此处上传到对象存储
    time_local = time.localtime(data["timestamp"])
    cloud_path = os.path.join(oss_conf["prefix"], str(time_local.tm_year), str(time_local.tm_mon),
                              str(time_local.tm_mday), data["record_id"],
                              str(data["record_id"]) + "_" + str(data["seq"]) + ".json")

    path = oss_upload.upload_record_str(data["round_detail"], cloud_path)

    count = logs_model.set_resource_path_of_round_details(data["record_id"], data["seq"], path)
    if count == 0:
        return True, "update sql fail"

    get_logger().info("save success %s, %s", str(data["record_id"]), str(data["seq"]))

    return True, ""


loop_func(_msg_call, redis_key.STREAM_ROUND_DETAILS_INFO, GROUP, incr_id, __file__[0:-3], args.tag)
