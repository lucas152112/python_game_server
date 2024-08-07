# coding:utf-8

import os
import sys

from schema import SchemaError
from twisted.internet import defer
from twisted.internet import reactor

import traceback
import pydash
from base import commands_system, commands_s2s, error, commands_base_game
from base import const
from base.base_player import BasePlayer
from base.base_server import BaseServer
from models import club_model
from models import database
from models import game_room_model
from models import room_config_model
from models import servers_model
from models import tables_model
from models.database import share_redis_game as share_connect
from protocol import channel_protocol
from protocol import protocol_utils
from utils import utils
from utils.twisted_tools import DelayCall, LoopingCall, DelayAsyncCall, defer_func

TIMEOUT_TABLE = 4 * 3600
IDLE_TIMEOUT_TABLE = 45 * 60


class BaseGame(BaseServer):
    PLAYBACK_VERSION = "1.0"

    def __init__(self):
        BaseServer.__init__(self)
        self.__defer = None
        self.__in_stop = False
        self.__stop_timer = None
        self.__players = {}  # 玩家数列列表
        self.__judges = {}  # 桌子对象列表
        self.__judge_lock = {}
        self.__stop_timestamp = float("inf")
        DelayCall(3, self.update_and_create_club_table)
        LoopingCall(5 * 60, self.__clear_timeout_tables)
        self._add_handlers({
            commands_base_game.ACK: self.update_ack_time,
            commands_base_game.PLAYER_TABLE_REMOVE: self.remove_player_table,
            commands_base_game.PLAYER_UNREADY: self.unready_player,
        })

    def _check_func(self, cmd, f):

        def wrap_func(uid, data, *args, **kwargs):
            try:
                check_pass, p, judge = self._check_in_table(uid, cmd)
                if not check_pass:
                    return

                def add_record_and_do_func():
                    judge.add_review_log(cmd, data, show=False, uid=p.uid)
                    f(uid, data, *args, **kwargs)

                judge.lock.run(add_record_and_do_func)
                # judge.add_review_log(cmd, data, show=False, uid=p.uid)
                # f(uid, data, *args, **kwargs)
            except Exception:
                error_msg = traceback.format_exc()
                print(error_msg, file=sys.stderr)
                self.logger.error(error_msg, exc_info=True)

        return wrap_func

    def _check_in_table(self, uid, cmd, with_notify=False):
        p = self.get_player(uid)
        if not p:
            if with_notify:
                self.response_fail(uid, cmd, error.USER_NOT_EXIST)
            return False, None, None
        judge = self.get_judge(p.tid)
        if not judge:
            if with_notify:
                self.response_fail(uid, cmd, error.TABLE_NOT_EXIST)
            return False, None, None
        return True, p, judge

    def _add_handlers_and_check_judge(self, cmd_handlers):
        cmd_map = pydash.map_values(cmd_handlers, lambda f, key: self._check_func(key, f))
        self._add_handlers(cmd_map)

    def update_ack_time(self, uid, _):
        servers_model.update_ack_time(self.sid, self.service_type)

    def remove_player_table(self, uid, data):
        if "uid" not in data:
            return
        uid = data["uid"]
        p = self.get_player(uid)
        if not p:
            return

    def unready_player(self, uid, _):
        check_pass, p, judge = self.check_in_table(uid, commands_base_game.PLAYER_UNREADY)
        if not check_pass:
            return
        judge.player_unready(p)

    @property
    def players(self):
        return self.__players

    @property
    def judges(self):
        return self.__judges

    @property
    def in_stop(self):
        return self.__in_stop

    def on_signal_stop(self):  # 收到结束的信号
        self.__stop_game()
        self.__defer = defer.Deferred()
        return self.__defer

    def __stop_game(self):
        servers_model.set_room_stop(self.server_id, self._service_type, os.getgid())
        self.__in_stop = True
        if not self.__stop_timer:
            self.__stop_timestamp = utils.timestamp()
            self.__stop_timer = LoopingCall(10, self.__loop_try_stop_game)
        else:
            self.__try_force_stop_game()

    def __try_force_stop_game(self):
        if utils.timestamp() - self.__stop_timestamp < 1:
            return

        for k, j in list(self.__judges.items()):
            if not j:
                continue
            j.lock.run(j.force_dismiss)

    def __loop_try_stop_game(self):
        self.__clear_empty_tables()
        self.__clear_timeout_tables()
        if len(self.players) <= 0:  # 玩家数量等于0，可直接关闭
            return DelayCall(0.1, self.close_server)
        if len(self.__judges) <= 0:  # judge数量等于0，可直接关闭了
            return DelayCall(0.1, self.close_server)

    def close_server(self):
        for k, j in list(self.__judges.items()):
            if not j:
                continue
            j.force_dismiss()
        self.logger.info("start close game server sid: %d , game: %d ", self.server_id, self.service_type)
        servers_model.set_room_shutdown(self.server_id, self.service_type)
        tables_model.close_tables_by_server(self.server_id, self.service_type)
        self._stop_listen_channel()
        self.logger.info("stop listen channel %d ", self.server_id)
        database.share_db().close()
        database.share_db_logs().close()
        database.share_redis_game().connection_pool.disconnect()
        return self.__defer.callback(1)

    def do_owner_dismiss(self, *args):
        raise Exception("need rewrite this function: do_owner_dismiss")

    def __clear_empty_tables(self):  # 清理未开始的桌子
        for k, j in list(self.__judges.items()):
            if not j:
                continue
            if j.status == const.T_IDLE:
                self.do_owner_dismiss(j, 0)

        # 获取全部空闲桌子ID(未在内存中生成的桌子)
        data = tables_model.query_all_idle_and_daikai_tables_tid(self.server_id, self.service_type)
        tables_model.delete_all_idle_and_daikai_tables(self.server_id, self.service_type)
        for i in data:
            database.zadd_table_id(i['tid'])

    def __clear_timeout_tables(self):  # 清理超时的桌子
        dismiss_tid = []
        for k, j in list(self.__judges.items()):
            if not j:
                continue
            if j.start_time == float("inf"):
                continue
            if j.status != const.T_IDLE and utils.timestamp() - j.start_time > TIMEOUT_TABLE:
                if j.tid in dismiss_tid:
                    continue

                dismiss_tid.append(j.tid)
                j.force_dismiss()

        for uid, player in self.players.items():
            if player.tid > 0 and player.join_time > 0 and utils.timestamp() - player.join_time > IDLE_TIMEOUT_TABLE:
                j = self.get_judge(player.tid)
                if j is None:
                    continue

                if j.status != const.T_IDLE:
                    continue

                if j.club_id > 0 and j.status == const.T_IDLE and j.player_count > 0:
                    if j.tid in dismiss_tid:
                        continue

                    dismiss_tid.append(j.tid)
                    j.force_dismiss()

    def update_and_create_club_table(self):
        utils.log("update_and_create_club_table","quickpdk.log")
        utils.log("self.server_id:" + str(self.server_id),"quickpdk.log")
        utils.log("self.server_type:" + str(self.server_type),"quickpdk.log")
        utils.log("club_id['id']:" + str(club_id['id']),"quickpdk.log")
        share_connect().set(f"table:{self.service_type}:{self.server_id}", "0")
        tables_model.update_all_club_table_sid(self.sid, self.service_type)
        data = tables_model.query_all_club_ids()
        for club_id in data:
            sub_floors = tables_model.query_all_sub_floor_by_club_id(club_id['id'], self.service_type)
            for sub_floor in sub_floors:
                self.club_auto_create_room(club_id['id'], -1, True, sub_floor)
            self.club_room_change_broad_cast(club_id['id'])
        utils.log("data:" + str(data),"quickpdk.log")
        return

    def club_auto_create_table_by_count(self, sub_floor_id, one=True):
        floor = tables_model.get_sub_floor_by_id(sub_floor_id)
        if not floor:
            return

        club_id = floor['club_id']
        club = club_model.get_club(database.share_db(), club_id)
        if not club or club["dismiss_time"] != 0:
            return

        floor_id = floor['floor_id']
        sub_floor_id = floor['id']

        auto_room_count = floor['auto_room']
        if auto_room_count == 0:
            return

        game_config = floor['play_config']
        if not game_config:
            return

        if not one:
            count = auto_room_count
        else:
            count = 1

        params = utils.json_decode(floor['play_config'])
        if not params or not params.get('gameType') or not params.get('totalRound'):
            return
        game_type = params.get('gameType')
        round_count = int(params.get('totalRound'))
        rules = params.get("ruleDetails")

        sid = game_room_model.get_best_server_sid(database.share_db(), database.share_redis_game(), game_type)
        if not sid:
            return

        user = self.fetch_player(None, club['uid'])
        user.update_diamonds_info()
        if not user:
            return

        game_type = params.get('gameType')

        if game_type in const.CALC_DIAMOND_WITH_PLAYER_NUM:
            diamonds = self.__calc_diamonds_with_player_count(round_count, game_type,
                                                              rules.get("totalSeat") or rules.get("playerCount"))
        elif game_type in const.CALC_DIAMOND_WITH_SPEC:
            diamonds = self.__calc_diamonds_with_spec(round_count, game_type,
                                                      rules.get("totalSeat") or rules.get("playerCount"),
                                                      rules.get("playerScore"))

        else:
            diamonds = self.__calc_diamonds(round_count, game_type)

        if diamonds == -1:
            return

        consume_type = int(params.get('consumeType', const.PAY_TYPE_CREATOR))
        if consume_type == const.PAY_TYPE_CREATOR:
            if user.diamond + user.yuan_bao + user.room_diamond < count * diamonds:
                return

        if consume_type not in (const.PAY_TYPE_CREATOR, const.PAY_TYPE_AA, const.PAY_TYPE_WINNER):
            consume_type = const.PAY_TYPE_CREATOR

        match_config = utils.json_decode(floor['match_config'])

        if 'tip' in params:
            rules['tip'] = params.get('tip')
        if 'tip1' in params:
            rules['tip1'] = params.get('tip1')
        if 'tip2' in params:
            rules['tip2'] = params.get('tip2')
        if 'tipLimit' in params:
            rules['tipLimit'] = params.get('tipLimit')
        if 'tipLimit1' in params:
            rules['tipLimit1'] = params.get('tipLimit1')
        if 'tipLimit2' in params:
            rules['tipLimit2'] = params.get('tipLimit2')

        must_location = params.get("mustLocation", 0)
        score_rate = params.get("scoreRate", 1)

        for i in range(count):
            for _ in range(10):
                tid = database.zpop_table_id() or utils.get_random_num(6)
                try:
                    tables_model.insert(sid,
                                        game_type,
                                        int(tid),
                                        club['uid'],
                                        1,
                                        round_count,
                                        diamonds,
                                        params.get("ruleType", 1),
                                        club["id"],
                                        rules,
                                        floor=floor_id,
                                        consume_type=consume_type,
                                        match_type=floor['match_type'],
                                        sub_floor=sub_floor_id,
                                        match_config=match_config,
                                        must_location=must_location,
                                        score_rate=score_rate)

                    data = {
                        "type": const.PUSH_CLUB_CREATE_ROOM,
                        "data": {
                            'roomID': int(tid),
                            "gameType": game_type,
                            "ruleDetails": rules,
                            "clubID": club["id"],
                            "floor": floor,
                            "subFloor": sub_floor_id,
                            "matchType": floor["match_type"],
                            "matchConfig": match_config,
                            "consumeType": consume_type,
                            "diamond": diamonds,
                        }
                    }
                    self.__broad_cast_club_user(club["id"], data)

                except Exception as data:
                    self.logger.warn(f"insert club table error: {club['id']} {data}")
                    continue
                break

    def club_auto_create_room(self, club_id, sub_floor_id, force=False, floor=None):
        if not floor:
            if club_id == -1 or sub_floor_id == -1:
                return
            else:
                floor = tables_model.get_sub_floor_by_id(sub_floor_id)
                if not floor:
                    return

        club_id = floor['club_id']
        club = club_model.get_club(database.share_db(), club_id)
        if not club or club["dismiss_time"] != 0:
            return

        floor_id = floor['floor_id']
        sub_floor_id = floor['id']

        auto_room_count = floor['auto_room']
        if auto_room_count == 0:
            return

        game_config = floor['play_config']
        if not game_config:
            return

        current_room_count = tables_model.get_count_by_club_id_and_sub_floor(club_id, sub_floor_id)['room_count']
        if auto_room_count <= current_room_count:
            return

        params = utils.json_decode(floor['play_config'])
        if not params or not params.get('gameType') or not params.get('totalRound'):
            return
        game_type = params.get('gameType')
        round_count = int(params.get('totalRound'))
        rules = params.get("ruleDetails")
        must_location = params.get("mustLocation", 0)

        sid = self.sid if force else game_room_model.get_best_server_sid(database.share_db(),
                                                                         database.share_redis_game(), game_type)
        if not sid:
            return

        user = self.fetch_player(None, club["uid"])

        if not user:
            return

        user.update_diamonds_info()

        diff_count = auto_room_count - current_room_count
        game_type = params.get('gameType')

        if game_type in const.CALC_DIAMOND_WITH_PLAYER_NUM:
            diamonds = self.__calc_diamonds_with_player_count(round_count, game_type,
                                                              rules.get("totalSeat") or rules.get("playerCount"))
        else:
            diamonds = self.__calc_diamonds(round_count, game_type)

        if diamonds == -1:
            return

        consume_type = int(params.get('consumeType', const.PAY_TYPE_CREATOR))
        if consume_type == const.PAY_TYPE_CREATOR:
            if user.room_diamond + user.diamond + user.yuan_bao < diff_count * diamonds:
                return
        # elif floor['match_type'] == const.MATCH_ROOM:
        #     if user.la_jiao_dou < diff_count * diamonds:
        #         return

        if consume_type not in (const.PAY_TYPE_CREATOR, const.PAY_TYPE_AA, const.PAY_TYPE_WINNER):
            consume_type = const.PAY_TYPE_CREATOR

        match_config = utils.json_decode(floor['match_config'])

        if 'tip' in params:
            rules['tip'] = params.get('tip')
        if 'tipLimit' in params:
            rules['tipLimit'] = params.get('tipLimit')
        if 'tip1' in params:
            rules['tip1'] = params.get('tip1')
        if 'tipLimit1' in params:
            rules['tipLimit1'] = params.get('tipLimit1')
        if 'tip2' in params:
            rules['tip2'] = params.get('tip2')
        if 'tipLimit2' in params:
            rules['tipLimit2'] = params.get('tipLimit2')

        for i in range(diff_count):
            while True:
                tid = database.zpop_table_id() or utils.get_random_num(6)
                try:
                    tables_model.insert(sid,
                                        game_type,
                                        int(tid),
                                        club['uid'],
                                        1,
                                        round_count,
                                        diamonds,
                                        params.get("ruleType", 1),
                                        club["id"],
                                        rules,
                                        floor=floor_id,
                                        consume_type=consume_type,
                                        match_type=floor['match_type'],
                                        sub_floor=sub_floor_id,
                                        match_config=match_config,
                                        must_location=must_location)
                except Exception as data:
                    self.logger.warn(f"insert club table error: {club['id']} {data}")
                    continue
                break

    @staticmethod
    def __calc_diamonds(round_count, game_type):
        data = room_config_model.get_room_config(game_type)
        diamonds = utils.json_decode(data['data'])
        for i in diamonds["diamondInfo"]:
            if i['count'] == round_count:
                return i['diamond']
        return -1

    @staticmethod
    def __calc_diamonds_with_player_count(round_count: int, game_type: int, player_count: int):
        data = room_config_model.get_room_config(game_type)
        diamonds = utils.json_decode(data['data'])
        for i in diamonds["diamondInfo"]:
            if i['count'] == round_count and i['playerCount'] == player_count:
                return i['diamond']
        return -1

    @staticmethod
    def __calc_diamonds_with_spec(round_count: int, game_type: int, player_count: int, player_score: int):
        data = room_config_model.get_room_config(game_type)
        diamonds = utils.json_decode(data['data'])
        for i in diamonds["diamondInfo"]:
            if i['count'] == round_count and i['playerCount'] == player_count and player_score == i["playerScore"]:
                return i['diamond']
        return -1

    def club_room_broad_cast(self, judge, status=0, is_del=False):
        if judge and judge.club_id != -1:
            data = {
                "type": const.PUSH_MESSAGE_CLUB_ROOM_CHANGE,
                "message": {
                    "tid": judge.tid,
                    "clubID": judge.club_id,
                    "roundIndex": judge.round_index,
                    "totalRound": judge.total_round,
                    "matchType": judge.match_type,
                    "matchConfig": judge.match_config,
                    "playerCount": judge.player_count,
                    "status": status,
                    "isOver": is_del,
                    "floor": judge.floor,
                    "players": judge.club_players_info
                }
            }
            self.__broad_cast_club_user(judge.club_id, data)

    def club_room_change_broad_cast(self, club_id):
        self.__broad_cast_club_user(club_id, {
            "type": const.PUSH_MESSAGE_CLUB_ROOM_CHANGE,
            "message": {
                "clubID": club_id
            }
        })

    def __broad_cast_club_user(self, club_id, data):
        user_data = club_model.query_all_uid_by_club_id_and_hour(database.share_db(), club_id, 6)
        users = []
        for i in user_data:
            users.append(i['uid'])
            if len(users) > 200:
                self.send_body_to_player(users, commands_system.PUSH_MESSAGE, data, service_type=const.SERVICE_SYSTEM)
                users.clear()

        if len(users) != 0:
            self.send_body_to_player(users, commands_system.PUSH_MESSAGE, data, service_type=const.SERVICE_SYSTEM)

    def service(self, cmd, uid, data):
        func = self._commands.get(cmd)
        if not func or not callable(func):
            print("cmd not bind: ", self.__class__.__name__, cmd)
            return

        try:
            data = self._check_in_data(cmd, data)
        except SchemaError as e:
            print("command : " + cmd + "\ndirector is: IN" + "\n" + str(e))
            self.response_fail(uid, cmd, error.DATA_BROKEN)
            return

        func(uid, data)

    def send_body_to_player(self, uid, cmd, body, service_type=None, to_all_service=False):  # 发送有错误码的数据包给玩家
        if not body:
            body = dict()

        service_type = service_type or self.service_type

        try:
            body = self._check_out_data(cmd, body)
        except SchemaError as e:
            print("command : " + cmd + "\ndirector is: OUT" + "\n" + str(e))

        body["__game_send_time"] = utils.timestamp_float()
        message = protocol_utils.pack_to_player_body(cmd, uid, body)
        to_service = 0 if to_all_service else const.SERVICE_GATE
        return self._s2s_raw_publish(0, self.sid, service_type, 0, to_service, 1, commands_s2s.S2S_SEND, message)

    def on_player_connection_change(self, uid, offline):
        raise Exception("need rewrite this function: on_player_connection_change")

    def __run_system_commands(self, cmd, uid, msg):
        if cmd == commands_system.PLAYER_SOCKET_CHANGE:
            offline = msg and not msg.get("online", 0)
            if offline:
                self.on_player_connection_change(uid, offline)

    def on_receive_message(self, from_sid, from_service, to_sid, to_service, body):
        cmd, uid, msg = protocol_utils.unpack_to_player_body(body)
        msg = utils.json_decode(msg)
        self.logger.debug("handle receive message: %s %s %s %s %s %s %s", from_sid, from_service, to_sid, to_service,
                          cmd, uid, msg)
        if not cmd:
            return

        if cmd == commands_system.SOCKET_CHANGE:
            offline = msg.get("offline")
            return self.on_player_connection_change(uid[0], offline)

        if from_service == const.SERVICE_SYSTEM:
            return self.__run_system_commands(cmd, uid[0], msg)

        return self.service(cmd, uid[0], msg)

    def get_player(self, uid: int):
        """ 查找玩家 """
        return self.players.get(uid)

    def save_player(self, p):
        """ 保存玩家 """
        self.players[p.uid] = p

    def del_player(self, p):
        # 删除玩家
        try:
            if not p.can_del():
                return

            del self.players[p.uid]
        except Exception as data:
            print(data)

    def publish_message(self, message):
        self.logger.info("room publish message: %s", str(message))
        return self._s2s_send(0, const.SERVICE_GATE, 1, message)

    def send_data_to_player(self, uid, cmd, data, code=error.OK, to_all_service=False):  # 发送未加错误码的数据给玩家
        body = protocol_utils.pack_client_body(data, code)
        message = protocol_utils.pack_to_player_body(cmd, uid, body)
        to_service = 0 if to_all_service else const.SERVICE_GATE
        return self._s2s_send(0, to_service, 1, message)

    def response(self, uid, cmd, data=None, code=error.OK, to_all_service=False):
        return self.send_data_to_player(uid, cmd, data, code, to_all_service)

    def response_ok(self, uid, cmd, data):
        return self.response(uid, cmd, data, error.OK)

    def response_fail(self, uid, cmd, code):
        return self.response(uid, cmd, None, code)

    def get_judge(self, tid: int):
        """ 查找桌子 """
        return self.__judges.get(tid)

    def del_judge(self, judge):
        """ 删除桌子 """

        if judge.club_id > 0:
            data = {"type": const.PUSH_CLUB_DEL_ROOM, "data": {'roomID': int(judge.tid), }}
            self.__broad_cast_club_user(judge.club_id, data)

        try:
            del self.__judges[judge.tid]
        except Exception as ex:
            print(ex)
        for k, v in list(self.__judges.items()):
            if v == judge or not v:
                del self.__judges[k]

    def broad_cast(self, cmd, body, service_type):
        for k, p in list(self.players.items()):
            if not p:
                continue
            self.send_body_to_player(p.uid, cmd, body, service_type)

    def check_in_table(self, uid, cmd, with_notify=False):
        p = self.get_player(uid)
        if not p:
            if with_notify:
                self.response_fail(uid, cmd, error.USER_NOT_EXIST)
            return False, None, None
        judge = self.get_judge(p.tid)
        if not judge:
            if with_notify:
                self.response_fail(uid, cmd, error.TABLE_NOT_EXIST)
            return False, None, None
        return True, p, judge

    # 玩家退出房间时清理
    def clear_player(self, p):
        if not p or not self.players.get(p.uid):
            return
        p.tid = 0  # 清除桌子数据
        p.is_ready = False
        # if p.offline:
        #     self.del_player(p)
        # 不管玩家是否离线都清理玩家的数据, 因为有可能第二次进来不是最新的数据信息
        self.del_player(p)

    def on_table_game_over(self, judge):
        self.club_room_broad_cast(judge, -1)
        self.del_judge(judge)
        if judge.first_join:
            sub_floor_count = database.decr_club_sub_floor_count(judge.club_id, judge.sub_floor_id)
            if sub_floor_count < 0:
                database.remove_club_sub_floor_count(judge.club_id, judge.sub_floor_id)
            share_connect().decr(f"table:{self.service_type}:{self.server_id}")
        database.zadd_table_id(judge.tid)
        if not judge.first_join:
            self.modify_table_count(judge.club_id, judge.sub_floor_id)
        if not judge.change_config:
            self.club_auto_create_room(judge.club_id, judge.sub_floor_id)

    def fetch_judge(self, judge, game_player, tid: int):
        if not self.get_judge(tid):
            if self.in_stop:  # 停机中不开新桌
                return None
            info = tables_model.get(tid)
            if not info or not info.game_type or info.game_type != self.service_type:
                return None
            judge = judge(info, self)
            player = self.fetch_player(game_player, info["owner"])
            judge.set_owner_player(player)
            self.judges[tid] = judge
        return self.get_judge(tid)

    def modify_table_count(self, club_id, sub_floor):
        share_connect().incr(f"table:{self.service_type}:{self.server_id}")
        if sub_floor == -1:
            return
        database.incr_club_sub_floor_count(club_id, sub_floor)
        self.club_join_create_room(club_id, sub_floor)

    def club_join_create_room(self, club_id, sub_floor):
        count = int(database.get_club_sub_floor_count(club_id, sub_floor) or 0)
        if count >= tables_model.get_count_by_club_id_and_sub_floor(club_id, sub_floor)['room_count']:
            self.club_auto_create_table_by_count(sub_floor)

    def fetch_player(self, game_player, uid: int):
        player = self.players.get(uid)
        if not player:
            if game_player is not None:
                player = game_player(uid)
                self.save_player(player)
            else:
                player = BasePlayer(uid)
        return player

    def start_service(self):
        servers_model.set_room_start(self.server_id, self.service_type, os.getpid(), utils.read_version())
        self._start_listen_channel(self.on_receive_message)
        try:
            reactor.addSystemEventTrigger('before', 'shutdown', self.on_signal_stop)
            reactor.run()
        except KeyboardInterrupt:
            self.close_server()
