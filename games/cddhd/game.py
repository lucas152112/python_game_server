# coding:utf-8
from base import const, error
from base.base_game import BaseGame
from games.cddhd import commands_game, flow
from games.cddhd.judge import Judge
from games.cddhd.player import Player
from models import tables_model, database, club_model, onlines_model
from protocol import channel_protocol
from utils import utils


class GameServer(BaseGame):
    def __init__(self):
        BaseGame.__init__(self)
        self._add_handlers({
            commands_game.ENTER_ROOM: self.__on_player_join,
            commands_game.CLUB_FORCE_DISMISS: self.__club_force_dismiss,
            commands_game.ADD_ROOM: self.__add_room,
            commands_game.ROOM_LIST: self.__on_room_list,
            commands_game.PLAY_CONFIG_CHANGE: self.__on_play_config_change,
        })

        self._add_handlers_and_check_judge({
            commands_game.EXIT_ROOM: self.__on_exit_room,
            commands_game.OWNER_DISMISS: self.__on_owner_dismiss,
            commands_game.PLAYER_CHU_PAI: self.__on_player_chu_pai,
            commands_game.PLAYER_PASS: self.__on_player_pass,
            commands_game.CONFIRM_PLAYER_PASS: self.__on_confirm_player_pass,
            commands_game.READY: self.__on_player_ready,
            commands_game.REQUEST_DISMISS: self.__on_request_dismiss,
            commands_game.CLIENT_BROAD_CAST: self.__on_client_broad_cast,
            commands_game.PLAYER_PENG: self.__on_player_peng,
            commands_game.PLAYER_HU_PAI: self.__on_player_hu,
            commands_game.PLAYER_CHI: self.__on_player_chi,
            commands_game.DEBUG_SET_CARDS: self.__on_set_cards,
            commands_game.REQUEST_POSITION: self.__on_request_position,
            commands_game.FORCE_DISMISS: self.__on_force_dismiss,
            commands_game.CLOSE_TUO_GUAN: self.__on_close_tuo_guan,
        })

    def __on_play_config_change(self, uid, data):
        if uid is not 1:
            return
        if 'clubID' not in data or 'type' not in data or 'floor' not in data:
            return
        change_type = data['type']
        club_id = data['clubID']
        floor = data['floor']

        tables = []
        if change_type in (
                const.MODIFY_FLOOR,
                const.DEL_FLOOR,
        ):
            tables = tables_model.query_table_with_not_start_and_floor(floor)
        elif change_type in (
                const.DEL_SUB_FLOOR,
                const.MODIFY_SUB_FLOOR,
        ):
            tables = tables_model.query_table_with_not_start_and_sub_floor(floor)

        for t in tables:
            tables_model.remove(t['tid'])
            judge = self.get_judge(t['tid'])
            if judge:
                judge.change_config = True
                self.do_owner_dismiss(judge, 0)
        self.club_auto_create_table_by_count(floor, False)
        self.club_room_change_broad_cast(club_id)
        return

    def __broad_cast(self, cmd, body, service_type):
        for k, p in list(self.players.items()):
            if not p:
                continue
            self.send_body_to_player(p.uid, cmd, body, service_type)

    def __on_client_broad_cast(self, uid, data):
        check_pass, p, judge = self.check_in_table(uid, commands_game.CLIENT_BROAD_CAST)
        if not check_pass:
            return
        if not data or not data.get('data'):
            return judge.inner_send_error(p, commands_game.CLIENT_BROAD_CAST, error.DATA_BROKEN)
        # detail = data.get('data')
        # if detail.get('action') == 'chat' and detail.get('faceID') and detail.get('toSeatID'):
        #     judge.emotion_stat(p.uid, detail)
        result = channel_protocol.packet_client_body({"uid": p.uid, "data": data['data']}, error.OK)
        judge.broad_cast(commands_game.CLIENT_BROAD_CAST, result)

    def __on_player_ready(self, uid, _):
        check_pass, p, judge = self.check_in_table(uid, commands_game.READY)
        if not check_pass:
            return
        flag = judge.player_ready(p)
        if not flag:
            return
        data = {"seatID": p.seat_id, "isPrepare": p.is_ready}
        body = channel_protocol.packet_client_body(data, error.OK)
        judge.broad_cast(commands_game.READY, body)
        return judge.try_start_game()

    def __on_player_chu_pai(self, uid, data):
        check_pass, p, judge = self.check_in_table(uid, commands_game.PLAYER_CHU_PAI)

        if not check_pass:
            return
        if p.tuo_guan == 1:
            return error.TUO_GUAN_NOT_ALLOWED

        if judge.curr_seat_id != p.seat_id:
            return judge.inner_send_error(p, commands_game.PLAYER_CHU_PAI, error.NOT_YOUR_TURN)

        card = data.get('cards')
        if not card or not (type(card) is int):
            return judge.inner_send_error(p, commands_game.PLAYER_CHU_PAI, error.DATA_BROKEN)

        code = judge.player_chu_pai(p, card)
        if code != error.OK:
            return judge.inner_send_error(p, commands_game.PLAYER_CHU_PAI, code)
        judge.start_chu_pai_call()

    def __on_player_hu(self, uid, data):
        check_pass, p, judge = self.check_in_table(uid, commands_game.PLAYER_HU_PAI)
        if not check_pass:
            return
        if p.tuo_guan == 1:
            return error.TUO_GUAN_NOT_ALLOWED

        opr_id = data.get('oprID')

        code = judge.player_hu(p, opr_id)
        if code != error.OK:
            return judge.inner_send_error(p, commands_game.PLAYER_HU_PAI, code)
        judge.check_action_end()

    def __on_player_peng(self, uid, data):
        check_pass, p, judge = self.check_in_table(uid, commands_game.PLAYER_PENG)
        if not check_pass:
            return
        if p.tuo_guan == 1:
            return error.TUO_GUAN_NOT_ALLOWED

        opr_id = data.get('oprID')

        code = judge.player_peng(p, opr_id)
        if code != error.OK:
            return judge.inner_send_error(p, commands_game.PLAYER_PENG, code)
        judge.check_action_end()

    def __on_player_pass(self, uid, data):
        check_pass, p, judge = self.check_in_table(uid, commands_game.PLAYER_PASS)
        if not check_pass:
            return

        opr_id = data.get('oprID')

        code = judge.player_pass(p, opr_id)
        if code != error.OK:
            return self.response_fail(uid, commands_game.PLAYER_PASS, code)
        judge.check_action_end()

    def __on_confirm_player_pass(self, uid, _):
        check_pass, p, judge = self.check_in_table(uid, commands_game.CONFIRM_PLAYER_PASS)
        if not check_pass:
            return

        code = judge.confirm_player_pass(p)
        if code != error.OK:
            return judge.inner_send_error(p, commands_game.CONFIRM_PLAYER_PASS, code)
        judge.check_action_end()

    def __on_player_chi(self, uid, data):
        check_pass, p, judge = self.check_in_table(uid, commands_game.PLAYER_CHI)
        if not check_pass:
            return
        if p.tuo_guan == 1:
            return error.TUO_GUAN_NOT_ALLOWED

        if type(data) is not dict:
            return judge.inner_send_error(p, commands_game.PLAYER_CHI, error.DATA_BROKEN)

        chi_pai = data.get('chiPai')
        bi_pai = data.get('biPai')
        if not chi_pai or type(chi_pai) is not list or 2 != len(chi_pai):
            return judge.inner_send_error(p, commands_game.PLAYER_CHI, error.DATA_BROKEN)

        opr_id = data.get('oprID')

        code = judge.player_chi(p, chi_pai, bi_pai, opr_id)
        if code != error.OK:
            return judge.inner_send_error(p, commands_game.PLAYER_CHI, error.DATA_BROKEN)
        judge.check_action_end()

    def __on_owner_dismiss(self, uid, data):
        if not data or "roomID" not in data:
            check_pass, p, judge = self.check_in_table(uid, commands_game.OWNER_DISMISS)
            if not check_pass:
                return
        else:
            room_id = data["roomID"]
            if not room_id:
                return self.response_fail(uid, commands_game.OWNER_DISMISS, error.DATA_BROKEN)

            judge = self.fetch_judge(Judge, Player, room_id)
            if not judge:
                return self.response_fail(uid, commands_game.OWNER_DISMISS, error.TABLE_NOT_EXIST)

        if judge.owner != uid:
            return self.response_fail(uid, commands_game.OWNER_DISMISS, error.NOT_YOUR_ROOM)

        code = self.do_owner_dismiss(judge, 0)
        if code != error.OK:
            return self.response_fail(uid, commands_game.OWNER_DISMISS, code)

        return self.response_ok(uid, commands_game.OWNER_DISMISS, {"roomID": judge.tid})

    def __on_force_dismiss(self, uid, data):
        room_id = data.get('roomID')
        if not room_id:
            return self.response_fail(uid, commands_game.FORCE_DISMISS, error.DATA_BROKEN)

        judge = self.get_judge(room_id)
        if not judge:
            return self.response_fail(uid, commands_game.FORCE_DISMISS, error.TABLE_NOT_EXIST)

        if judge.owner != uid:
            return self.response_fail(uid, commands_game.FORCE_DISMISS, error.NOT_YOUR_ROOM)

        judge.force_dismiss()
        return self.response_ok(uid, commands_game.FORCE_DISMISS, {"roomID": judge.tid})

    def __on_room_list(self, uid, _):
        tables = tables_model.get_all_by_owner(uid)
        table_data = []
        for table in tables:
            tid = table.get('tid')
            game_table = self.get_judge(tid)
            cache_data = tables_model.get_table_info(tid) or {
                "player_list": [],
                "round_index": 1,
                "table_status": flow.T_IDLE
            }
            if not cache_data and not game_table:
                continue
            table.update(cache_data)
            table_data.append(table)

        return self.response_ok(uid, commands_game.ROOM_LIST, {"tables": table_data})

    def __add_room(self, uid, data):
        if not data:
            return self.response_fail(uid, commands_game.ADD_ROOM, error.DATA_BROKEN)

        room_id = data["roomID"]
        if not room_id:
            return self.response_fail(uid, commands_game.ADD_ROOM, error.DATA_BROKEN)

        table = tables_model.get(room_id)
        if not table:
            return self.response_fail(uid, commands_game.ADD_ROOM, error.TABLE_NOT_EXIST)

        cache_data = tables_model.get_table_info(room_id) or {
            "is_del": 0,
            "player_list": [],
            "round_index": 1,
            "table_status": flow.T_IDLE
        }

        table.update(cache_data)

        return self.response_ok(uid, commands_game.ADD_ROOM, {"tables": {room_id: table}})

    def __on_request_dismiss(self, uid, data):
        check_pass, p, judge = self.check_in_table(uid, commands_game.REQUEST_DISMISS)
        if not check_pass:
            return
        is_agree = bool(data.get('agree'))
        judge.player_request_dismiss(p, is_agree)

    def __on_request_position(self, uid, _):
        check_pass, p, judge = self.check_in_table(uid, commands_game.REQUEST_POSITION)
        if not check_pass:
            return
        data = judge.get_all_distances()
        self.response(uid, commands_game.REQUEST_POSITION, {"distances": data})

    def check_in_table(self, uid, cmd, with_notify=False) -> (int, Player, Judge):
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

    def __on_player_join(self, uid, data):  # 处理玩家进入房间
        utils.log("__on_player_join start", "room.log")
        if not data or not data.get("_client"):
            return
        session = utils.ObjectDict(data.get("_client"))
        if not session.verified:
            return self.response_fail(uid, commands_game.ENTER_ROOM, error.DATA_BROKEN)

        tid = int(data.get('roomID'))
        if not tid or 0 >= tid:  # 玩家没有待处理的进入操作
            return self.response_fail(uid, commands_game.ENTER_ROOM, error.DATA_BROKEN)

        online = onlines_model.get_by_uid(uid)
        if online and online['tid'] != 0 and online['tid'] != tid:
            return self.response_fail(uid, commands_game.ENTER_ROOM, error.IN_OTHER_ROOM)

        info = tables_model.get_by_server(self.server_id, tid)
        if not info:
            return

        p = self.get_player(uid)
        re_connect = False
        if not p:
            p = Player(uid)
            self.save_player(p)
        else:
            re_connect = True
        p.session = session
        p.static_data = data.get('data')
        p.set_position(data.get('x'), data.get('y'))
        is_re_enter_room = p.tid > 0 and p.tid == tid

        if not is_re_enter_room and info['club_id'] != -1:
            data = club_model.get_club_by_uid_and_club_id(database.share_db(), info['club_id'], uid)
            if not data:
                return self.response_fail(uid, commands_game.ENTER_ROOM, error.NOT_CLUB_MEMBER)

            club = club_model.get_club(database.share_db(), info['club_id'])
            if club and club['lock_status'] is 1:
                return self.response_fail(uid, commands_game.ENTER_ROOM, error.SYSTEM_ERROR)

        if p.tid > 0 and p.tid != tid:  # 玩家已经在其它房间中
            return self.response_fail(uid, commands_game.ENTER_ROOM, error.IN_OTHER_ROOM)

        judge = self.fetch_judge(Judge, Player, tid)
        if not judge:
            return self.response_fail(uid, commands_game.ENTER_ROOM, error.TABLE_NOT_EXIST)

        if info['club_id'] != -1 and info['match_type'] == 1:
            code = judge.enter_match_score(p, info['club_id'])
            if code is not error.OK:
                return self.response_fail(uid, commands_game.ENTER_ROOM, code)

        self.__do_join_room(judge, p, uid, re_connect, is_re_enter_room)
        utils.log("__on_player_join end", "room.log")

    def __do_join_room(self, judge: Judge, p: Player, uid, re_connect, is_re_enter_room):
        utils.log("__do_join_room start", "room.log")
        offline = p.offline
        code, result = judge.player_join(p, is_re_enter_room)
        re_connect_line = re_connect and offline != p.offline
        self.response(uid, commands_game.ENTER_ROOM, result, code)
        if code != error.OK:
            self.del_player(p)
            return
        self.__notify_room_info(judge, p, uid, code, is_re_enter_room)
        if re_connect_line:
            judge.player_connect_changed(p)
        if code != error.OK:
            return
        judge.notify_distance()
        return judge.try_start_game()

    def __notify_room_info(self, judge, player, uid, code, is_re_enter_room):
        if code != error.OK:
            return

        self.response(uid, commands_game.ROOM_CONFIG, judge.get_info())

        self.response(uid, commands_game.PLAYER_ENTER_ROOM, player.get_all_data(judge.status))
        items = judge.get_all_player_info()
        for item in items:  # 发送所有房间内的其它玩家数据给当前玩家
            if uid == item.get('uid'):
                continue
            self.response(uid, commands_game.PLAYER_ENTER_ROOM, item)

        data = player.get_all_public_data(judge.status)
        body = channel_protocol.packet_client_body(data, error.OK)
        if not is_re_enter_room:
            judge.broad_cast(commands_game.PLAYER_ENTER_ROOM, body, uid)

        if judge.in_dismiss:
            self.response(uid, commands_game.REQUEST_DISMISS, judge.make_dismiss_data())

    def __on_exit_room(self, uid, _):
        # 玩家退出当前桌
        check_pass, p, judge = self.check_in_table(uid, commands_game.EXIT_ROOM)
        if not check_pass:
            return

        code, result = judge.player_quit(p, const.QUIT_NORMAL)

        judge.broad_cast(commands_game.EXIT_ROOM, result)
        self.send_data_to_player(p.uid, commands_game.EXIT_ROOM, result, code)  # 玩家退出桌子之后广播无法到达玩家，所以这里直接用玩家发送一次
        if code == error.OK:
            self.clear_player(p)

    @staticmethod
    def do_owner_dismiss(judge, reason):
        if judge.status != flow.T_IDLE:  # 只有空闲中的桌子才允许直接解散
            return error.COMMAND_DENNY
        judge.broad_cast(commands_game.OWNER_DISMISS, {"reason": reason, "code": error.OK})
        judge.owner_dismiss()
        return error.OK

    def on_player_connection_change(self, uid, offline):
        """ 玩家断线时的响应 """
        if not uid:
            return
        p = self.get_player(uid)
        if not p:
            return
        if p.tid <= 0:
            self.del_player(p)
        is_offline = offline == 1
        if p.offline == is_offline:
            return
        p.offline = is_offline
        if p.offline:
            p.last_offline_time = utils.timestamp()
        judge = self.get_judge(p.tid)
        if not judge:
            return
        judge.player_connect_changed(p)

    def __on_set_cards(self, uid, data):
        check_pass, p, judge = self.check_in_table(uid, commands_game.EXIT_ROOM)
        if not check_pass:
            return
        code = judge.set_cards_in_debug(data.get("cards"), data.get("dealer", 0))
        self.response(uid, commands_game.DEBUG_SET_CARDS, None, code)

    def __club_force_dismiss(self, uid, data):
        room_id = data["roomID"]
        if not room_id:
            return self.response_fail(uid, commands_game.CLUB_FORCE_DISMISS, error.DATA_BROKEN)

        judge = self.fetch_judge(Judge, Player, room_id)
        if not judge:
            return self.response_fail(uid, commands_game.CLUB_FORCE_DISMISS, error.TABLE_NOT_EXIST)

        if judge.club_id == -1:
            return self.response_fail(uid, commands_game.CLUB_FORCE_DISMISS, error.NOT_YOUR_ROOM)

        user_data = club_model.get_club_by_uid_and_club_id(database.share_db(), judge.club_id, uid)
        if not user_data or user_data['permission'] not in (
                0,
                1,
        ):
            return self.response_fail(uid, commands_game.CLUB_FORCE_DISMISS, error.NOT_YOUR_ROOM)

        judge.agree_uids.insert(0, uid)

        judge.force_dismiss()
        return self.response_ok(uid, commands_game.CLUB_FORCE_DISMISS, {"roomID": judge.tid})

    def __on_close_tuo_guan(self, uid, _):
        check_pass, p, judge = self.check_in_table(uid, commands_game.CLOSE_TUO_GUAN)
        if p.tuo_guan != 1:
            return self.response_fail(uid, commands_game.CLOSE_TUO_GUAN, error.FLOW_ERROR)
        judge.tuo_guan_close(p)
        return self.response_ok(uid, commands_game.CLOSE_TUO_GUAN, {"seatID": p.seat_id})

    @staticmethod
    def share_server():
        return GameServer()
