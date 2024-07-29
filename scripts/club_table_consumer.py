import os
import sys
import redis

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from configs import redis_key
from models import logs_model
from scripts.consume_loop_main import loop_func, get_logger, DealDataError
from utils import utils
from configs import config
import pydash
import argparse
from mongo_models import mongo
from models import club_model, database
from datetime import datetime, timedelta

parser = argparse.ArgumentParser(description="mongo记录游戏数据消费者")

parser.add_argument("id", help="consume id: .", nargs="?", type=int, default=1)
group = parser.add_mutually_exclusive_group()

group.add_argument("-t", "--tag", help="read message tag: >", default=">")

args = parser.parse_args()

GROUP = f"{redis_key.STREAM_GAME_OVER_INFO}_consumers"

incr_id = args.id

print(f"init consume {GROUP}{incr_id}")
""" 处理任务有桌子日志。每局详细分数。消费数据。 """

oss_conf = config.get_item("oss_conf")


def _msg_call(msg):
    try:
        data = utils.json_decode(msg.get(b"game_over_info"), True)
    except Exception as e:
        return False, str(e)

    # 此处上传到对象存储

    room_log = logs_model.insert_room_log_mongo(record_id=data["record_id"],
                                                club_id=data["club_id"],
                                                game_type=data["game_type"],
                                                owner_id=data["owner_id"],
                                                rules=data["rules"],
                                                room_id=data["room_id"],
                                                floor=data["floor"],
                                                sub_floor=data["sub_floor"],
                                                round_count=data["round_count"],
                                                finish_time=data["finish_time"],
                                                round_info_list=data["round_logs"],
                                                player_info_list=data["player_logs"],
                                                finish_data=data["finish_data"],)

    for index, seat in enumerate(data["player_logs"]):
        if seat is None:
            continue

        try:
            database.zadd_club_and_sub_floor(seat["uid"], data["club_id"], data["sub_floor"], data["finish_time"])
        except Exception as e:
            print(e, file=sys.stderr)

    # max_player = pydash.max_by(data["player_logs"], "score")
    # min_player = pydash.min_by(data["player_logs"], "score")
    #
    # start_time = datetime.fromtimestamp(data["finish_time"]).replace(minute=0, second=0, microsecond=0)
    # ended_time = start_time + timedelta(hours=1)
    #
    # for index, seat in enumerate(data["player_logs"]):
    #     if seat is None:
    #         continue
    #
    #     parent_id = -1
    #     if data["club_id"] > 0:
    #         club_relationship = club_model.get_club_by_uid_and_club_id(database.share_db(), data["club_id"],
    #                                                                    seat["uid"])
    #         if club_relationship and club_relationship["tag_uid"]:
    #             parent_id = club_relationship["tag_uid"]
    #
    #     update_key = {}
    #
    #     if seat["score"] != 0:
    #         if max_player["uid"] == seat["uid"]:
    #             update_key["push__max_score_list"] = seat["score"]
    #
    #         if min_player["uid"] == seat["uid"]:
    #             update_key["push__min_score_list"] = seat["score"]
    #
    #     update_key["push__score_list"] = seat["score"]
    #     update_key["push__room_log_list"] = room_log
    #
    #     mongo.ClubStaticLogs.objects(
    #         mongo.Q(uid=seat["uid"]) & mongo.Q(club_id=data["club_id"]) & mongo.Q(start_time=start_time) & mongo.Q(
    #             ended_time=ended_time) & mongo.Q(parent_id=parent_id) & mongo.Q(
    #             game_type=data["game_type"])).update_one(**update_key, upsert=True)

    get_logger().info("save success %s", str(data["record_id"]))

    return True, ""


loop_func(_msg_call, redis_key.STREAM_GAME_OVER_INFO, GROUP, incr_id, __file__[0:-3], args.tag)
