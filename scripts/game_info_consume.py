import os
import sys
import redis

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from base import const
from configs import redis_key
from models import logs_model
from scripts.consume_loop_main import loop_func, get_logger, DealDataError
from utils import utils
from configs import config
import pydash
import argparse
import traceback
from mongo_models import mongo
from models import club_model, database, club_user_game_model, players_model
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


def save_data(room_item):
    """
    保存游戏 每个玩家的 分数数据 数据
    :param room_item:
    :return:
    """
    club_id = room_item["club_id"]
    finish_time = room_item["finish_time"]
    room_id = room_item["room_id"]
    record_id = room_item["record_id"]
    floor = room_item["floor"]
    sub_floor = room_item["sub_floor"]
    game_type = room_item["game_type"]
    match_type = room_item.get("match_type", const.DIAMOND_ROOM)

    max_index = -1
    max_score = 0
    min_index = -1
    min_score = 0

    for i, seat in enumerate(room_item["player_logs"]):
        index = str(i + 1)
        score = seat["score"]

        if score < min_score:
            min_score = score
            min_index = index
        if score > max_score:
            max_score = score
            max_index = index

    for i, seat in enumerate(room_item["player_logs"]):
        index = str(i + 1)
        uid = seat["uid"]
        score = seat["score"]
        hierarchical = seat["hierarchical"]
        tag_uid = seat["tag_uid"]

        player_status = 0
        if min_index == index:
            player_status = -1
        elif max_index == index:
            player_status = 1

        if uid == 0:
            continue

        try:
            print(
                logs_model.insert_player_game_log(uid, club_id, room_id, finish_time, record_id, floor, sub_floor,
                                                  game_type, score, player_status, match_type, tag_uid, hierarchical))
        except Exception as error:
            pass
            # s = traceback.format_exc()
            # print(str(error) + s)

    return


def calc_two_same_table_players_count(data):
    """计算同桌数据"""

    club_id = data["club_id"]
    if data["club_id"] == -1 or len(data["player_logs"]) not in (
            3,
            4,
    ) or len(data["round_logs"]) == 0:
        return

    game_type = data["game_type"]

    # if game_type not in (const.SERVICE_FENG_HUANG_HONG_ZHONG,
    #                      const.SERVICE_FENG_HUANG_HUA_SHUI,
    #                      const.SERVICE_ZLMZ):
    #     return

    ids = []
    for seat in data["player_logs"]:
        current_uid = seat["uid"]
        ids.append(str(current_uid))
        ref_ids = []
        for now_seat in data["player_logs"]:
            if now_seat["uid"] == current_uid:
                continue
            ref_ids.append(str(now_seat["uid"]))
            club_user_game_model.insert_or_update_same_player_game_count(club_id, current_uid, now_seat["uid"])
        # 将此玩家与其他人的场数清空
        club_user_game_model.remove_same_player_game_count(club_id, current_uid, ",".join(ref_ids))

    join_ids = ",".join(ids)
    club_user_game_model.remove_same_player_game_count_by_uid(club_id, join_ids, join_ids)

    same_table_count = 30

    if game_type in (const.SERVICE_FENG_HUANG_HONG_ZHONG, const.SERVICE_FENG_HUANG_HUA_SHUI, const.SERVICE_ZLMZ):
        same_table_count = 5

    data = club_user_game_model.query_same_table_player(club_id, join_ids, same_table_count)

    filter_data = []
    keys = {}
    for i in data:
        if i['uid'] not in keys:
            keys[i['uid']] = []

        if i['ref_uid'] in keys and i['uid'] not in keys[i['ref_uid']]:
            keys[i['uid']].append(i['ref_uid'])
            filter_data.append(i)

    for i in filter_data:
        p1 = players_model.get(i['uid'])
        p2 = players_model.get(i['ref_uid'])
        club_user_game_model.insert_same_player_game_logs(p1.uid, p2.uid, p1.nick_name, p2.nick_name, p1.avatar,
                                                          p2.avatar, club_id, i['count'])


def _msg_call(msg):
    if not msg:
        return True, ""

    try:
        data = utils.json_decode(msg.get(b"game_over_info"), True, True)
    except Exception as e:
        get_logger().error(str(traceback.format_exc()) + str(e), exc_info=True)
        return False, str(e)

    save_data(data)

    try:
        calc_two_same_table_players_count(data)
    except Exception as e:
        get_logger().error(str(traceback.format_exc()) + str(e), exc_info=True)

    score_rate = data.get("score_rate", 1)
    match_type = data.get("match_type", const.DIAMOND_ROOM)

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
                                                finish_data=data["finish_data"],
                                                score_rate=score_rate,
                                                match_type=match_type)

    for index, seat in enumerate(data["player_logs"]):
        if seat is None:
            continue

        try:
            get_logger().info("sort success %d, %d, %d", seat["uid"], data["club_id"], data["sub_floor"])
            database.zadd_club_and_sub_floor(seat["uid"], data["club_id"], data["sub_floor"], data["finish_time"])
        except Exception as e:
            s = traceback.format_exc()
            print(str(e) + s)

    get_logger().info("save success %s", str(data["record_id"]))

    return True, ""


loop_func(_msg_call, redis_key.STREAM_GAME_OVER_INFO, GROUP, incr_id, __file__[0:-3], args.tag)
