# coding:utf-8

from copy import deepcopy

from base import const
from base.base_player import BasePlayer
from games.cddhd import zi_pai, flow
from games.cddhd.rule_base import RuleBase
from models import logs_model, floor_model, club_model
from models import onlines_model
from models import players_model
from utils import earth_position
from utils import utils
from decimal import Decimal

# 玩家状态标志
IN_IDLE = 0  # 空闲中
IN_WAITING = 1  # 等待中(新玩家加入后等待中)
IN_PLAYING = 2  # 游戏中

DEFAULT_SCORE = 0


class Player(BasePlayer):
    def __init__(self, uid):
        BasePlayer.__init__(self, uid)
        self.__cards = []  # 手牌
        self.__chu_cards = []  # 出牌记录 出成功的牌
        self.__win_score = 0

        self.__zhuang_count = 0
        self.__win_count = 0
        self.__lose_count = 0

        self.__zhuo_pai = []  # 玩家桌牌
        self.__chou_peng_pai = set()  # 臭碰牌
        self.__chou_chi_pai = set()  # 臭吃牌
        self.__operates = []  # 能做的操作
        self.__zi_mo_count = 0
        self.__ming_tang_count = 0
        self.__ren_pai_times = 0  # 忍牌次数
        self.__has_qi_shou_ti = False  # 有没有起手提
        self.__max_round_score = Decimal(0)  # 单局最高得分
        self.__ming_tang_dict = dict()
        self.__qi_shou_ti_cards = []  # 起手提的牌
        self.__chu_pai_list = []  # 出牌记录 全部出牌
        self.__operator_out_time = None  # 用户操作超时定时器对象
        self.__last_offline_time = 0
        self.__last_hu_xi = 0

        self.__tuo_guan = 0

    @property
    def tuo_guan(self):
        return self.__tuo_guan

    @tuo_guan.setter
    def tuo_guan(self, tuo_guan):
        self.__tuo_guan = tuo_guan

    @property
    def last_hu_xi(self):
        return self.__last_hu_xi

    @last_hu_xi.setter
    def last_hu_xi(self, hu_xi):
        self.__last_hu_xi = hu_xi

    @property
    def last_offline_time(self):
        return self.__last_offline_time

    @last_offline_time.setter
    def last_offline_time(self, time):
        self.__last_offline_time = time

    @property
    def operator_out_time(self):
        return self.__operator_out_time

    @operator_out_time.setter
    def operator_out_time(self, delay):
        self.__operator_out_time = delay

    @property
    def win_score(self):
        return self.__win_score

    # 接收牌
    def receive_card(self, card):
        self.__cards.append(card)

    def __clear_cards(self):
        """ 清除所有牌 """
        self.__cards.clear()
        self.__chu_cards.clear()
        self.__zhuo_pai.clear()
        self.__chou_peng_pai.clear()
        self.__chou_chi_pai.clear()
        self.__qi_shou_ti_cards.clear()
        self.__chu_pai_list.clear()

    # 获取玩家的扑克牌
    @property
    def cards(self):
        return deepcopy(self.__cards)

    @cards.setter
    def cards(self, cards):
        self.__cards = cards

    @property
    def zhuo_pai(self):
        return deepcopy(self.__zhuo_pai)

    @property
    def operates(self):
        return deepcopy(self.__operates)

    @operates.setter
    def operates(self, opts):
        self.__operates.clear()
        self.__operates.extend(opts)

    def is_chou_pai(self, card):
        if card in self.__chou_chi_pai:
            return True
        if card in self.__chou_peng_pai:
            return True
        return False

    def match_data(self, club_id, match_type):
        if club_id == -1 or match_type == 0:
            match_score = 0
        else:
            data = club_model.get_player_money_by_club_id(club_id, self.uid)
            if data and 'score' in data:
                match_score = data['score'] + data['lock_score']
            else:
                match_score = 0
        return {"seatID": self.seat_id, "matchScore": match_score}

    @property
    def qi_shou_ti_cards(self):
        return deepcopy(self.__qi_shou_ti_cards)

    @property
    def game_over_data(self):
        return {
            "seatID": self.seat_id,
            "totalScore": self.score,
            "tagUid": self.tag_uid,
            "zhuangCount": self.__zhuang_count,  # TODO: remove it
            "winCount": self.__win_count,
            "loseCount": self.__lose_count,  # TODO: remove it
            "ziMoCount": self.__zi_mo_count,  # TODO: remove it
            "mingTangCount": self.__ming_tang_count,
            "roundMaxScore": self.__max_round_score,
            "mingTangList": self.__get_ming_tang_stat(),
            "isTuoGuan": self.__tuo_guan,
        }

    def __get_ming_tang_stat(self):
        result = []
        values = self.__ming_tang_dict.values()
        values = sorted(values, reverse=True)
        for i in range(2):
            if i >= len(values):
                break
            for k, v in list(self.__ming_tang_dict.items()):
                if values[i] != v:
                    continue
                result.append([k, v])
        return result[0:2]

    @property
    def in_playing(self):
        return self.status == IN_PLAYING

    def __get_public_pai(self):
        result = []
        for item in self.__zhuo_pai:
            if item[0] == zi_pai.CARD_TYPE_WEI:
                result.append([item[0], 0, 0, 0])
                continue
            result.append(deepcopy(item))
        return result

    def get_all_public_data(self, judge_status):
        result = BasePlayer.get_all_public_data(self)
        result["score"] = self.score + self.lock_score
        result['lastOfflineTime'] = self.last_offline_time

        if self.in_playing:
            if judge_status == const.T_PLAYING:
                result["zhuoPai"] = self.__get_public_pai()
                result["chuPai"] = deepcopy(self.__chu_cards)
            else:
                result["zhuoPai"] = []
                result["chuPai"] = []
            result["isTuoGuan"] = self.__tuo_guan
        return result

    def get_all_data(self, judge_status):
        result = self.get_all_public_data(judge_status)
        if self.in_playing:
            result['shouPai'] = deepcopy(self.__cards)
            result["zhuoPai"] = deepcopy(self.__zhuo_pai)
            result["operates"] = self.operates
            result["isTuoGuan"] = self.__tuo_guan
        return result

    def add_chou_peng_pai(self, card):
        self.__chou_peng_pai.add(card)

    def add_chou_chi_pai(self, card):
        self.__chou_chi_pai.add(card)

    def chu_pai(self, card):  # 玩家出牌
        self.add_chou_peng_pai(card)
        self.add_chou_chi_pai(card)
        self.__remove_cards([card])
        self.__chu_pai_list.append(card)

    def is_ting_hu(self, isdealer):
        max_chu_pai = 0
        if isdealer:
            max_chu_pai = 1

        if len(self.__chu_pai_list) > max_chu_pai:
            return False

        # for zhuo_pai_cell in self.__zhuo_pai:
        #     if zhuo_pai_cell[0] != zi_pai.CARD_TYPE_TI:
        #         return False

        return True

    def __set_score(self, score, is_add):
        """ 设置玩家积分，只修改内存中的数据，不改数据库 """
        assert score >= 0
        if is_add:
            self.__max_round_score = max(score, self.__max_round_score)
            self.score += score
            self.__win_score = score
        else:
            self.score -= score
            self.__win_score = -score

    def on_stand_up(self):
        """ 玩家站起响应 """
        BasePlayer.on_stand_up(self)

        self.lock_score = 0

        self.seat_id = -1
        self.status = IN_IDLE
        self.__last_offline_time = 0
        self.score = Decimal(0)

    def on_sit_down(self, tid, seat_id):
        """ 玩家坐下响应 """
        self.tid = tid
        if self.status != IN_PLAYING:
            self.__clear_cards()
            self.status = IN_WAITING
        self.offline = False
        self.seat_id = seat_id
        onlines_model.set_tid(self.uid, tid)

    def on_game_start(self, match_score):
        """ 房间开始前的清理 """
        self.__clear_game_data()

    def on_game_over(self, club_id):
        self.__clear_round_data()
        self.__clear_game_data()
        self.on_stand_up()
        BasePlayer.on_game_over(self, club_id)

    def __clear_game_data(self):
        self.__win_count = self.__lose_count = 0
        self.__zhuang_count = 0
        self.__ming_tang_count = 0
        self.__zi_mo_count = 0
        self.__max_round_score = 0
        self.__tuo_guan = 0
        self.__ming_tang_dict.clear()

    def __clear_round_data(self):
        self.__clear_cards()
        self.__ren_pai_times = 0
        self.__last_hu_xi = 0
        self.__operates.clear()
        self.__has_qi_shou_ti = False

    def on_round_start(self):
        """ 开局前的清理 """
        self.__clear_round_data()
        self.status = IN_PLAYING

    def on_round_over(self, score, is_win, is_zhuang, is_zi_mo, ming_tang_list, fan_list):
        """ 一局结束结算 """
        self.__set_score(score, is_win)
        self.is_ready = False  # 一局结束后取消准备
        self.__stat_data(is_win, is_zhuang, is_zi_mo, ming_tang_list, fan_list)
        self.__operates.clear()
        self.__has_qi_shou_ti = False

    def __stat_data(self, is_win, is_zhuang, is_zi_mo, ming_tang_list, fan_list):
        if is_win:
            self.__win_count += 1
        else:
            self.__lose_count += 1
        if is_zhuang:
            self.__zhuang_count += 1
        if is_zi_mo:
            self.__zi_mo_count += 1
        self.__ming_tang_count += len(ming_tang_list)
        for i in range(len(ming_tang_list)):
            ming_tang = ming_tang_list[i]
            count = fan_list[i]
            self.__ming_tang_dict[ming_tang] = max(self.__ming_tang_dict.get(ming_tang, 0), count)

    def __remove_cards(self, cards):
        for card in cards:
            if card in self.__cards:
                self.__cards.remove(card)

    def __add_zhuo_pai(self, card_type, cards):
        cards = deepcopy(cards)
        cards.insert(0, card_type)
        self.__zhuo_pai.append(cards)

    def qi_shou_ti(self):
        if self.__has_qi_shou_ti:
            return
        self.__qi_shou_ti_cards.clear()
        stat = RuleBase.stat_cards(self.__cards)
        for card, count in list(stat.items()):
            if 4 != count:
                continue
            cards = [card, card, card, card]
            self.__remove_cards(cards)
            self.__add_zhuo_pai(zi_pai.CARD_TYPE_TI, cards)
            self.__qi_shou_ti_cards.append(card)
        if self.__qi_shou_ti_cards:
            self.__ren_pai_times = len(self.__qi_shou_ti_cards) - 1
        self.__has_qi_shou_ti = True
        return self.qi_shou_ti_cards

    def can_pao(self, card, is_mo_pai):
        if self.__cards.count(card) == 3:
            return True
        for item in self.__zhuo_pai:
            if not item:
                continue
            card_type = item[0]
            check_card = item[1]
            if check_card != card:
                continue
            if card_type == zi_pai.CARD_TYPE_WEI:
                return True
            elif card_type == zi_pai.CARD_TYPE_PENG and is_mo_pai:
                return True
        return False

    def pao_qi(self, card, is_mo_pai):  # 跑起，分手牌跑起和桌牌跑起
        flag, index = self.__shou_pai_pao(card)
        if flag:
            return flag, index
        return self.__zhuo_pai_pao(card, is_mo_pai)

    def __zhuo_pai_pao(self, card, is_mo_pai):
        for i in range(len(self.__zhuo_pai)):
            card_type = self.__zhuo_pai[i][0]
            check_card = self.__zhuo_pai[i][1]
            pao_qi = False
            if check_card != card:
                continue
            if card_type == zi_pai.CARD_TYPE_WEI:
                pao_qi = True
            elif card_type == zi_pai.CARD_TYPE_PENG and is_mo_pai:
                pao_qi = True
            if not pao_qi:
                continue
            self.__zhuo_pai[i] = [zi_pai.CARD_TYPE_PAO, card, card, card, card]
            return True, i + 1
        return False, 0

    def __shou_pai_pao(self, card):  # 手牌跑起
        if self.__cards.count(card) != 3:
            return False, 0
        cards = [card] * 3
        self.__remove_cards(cards)
        self.__add_zhuo_pai(zi_pai.CARD_TYPE_PAO, [card] * 4)
        return True, len(self.__zhuo_pai)

    def can_chi(self, card, rule):
        """ 判断能不能吃得起某牌，当吃得起并且比得出的时候返回true"""
        if card in self.__chou_chi_pai:
            return False
        if len(self.__zhuo_pai) >= 6:
            return False
        return rule.can_chi(self.cards, card)

    def can_peng(self, card, rule):
        """ 1. 手牌有两张相同 2. 臭牌不能碰 3. 不能七坎下地 4. 碰牌之后还要有牌可以打出 """
        if card in self.__chou_peng_pai:
            return False
        if len(self.__zhuo_pai) >= 6:
            return False
        return rule.can_peng(self.cards, card)

    def can_ti(self, card):
        if 3 == self.__cards.count(card):
            return True
        for i in range(len(self.__zhuo_pai)):
            card_type = self.__zhuo_pai[i][0]
            first_card = self.__zhuo_pai[i][1]
            if card_type not in (zi_pai.CARD_TYPE_WEI, ):
                continue
            if first_card != card:
                continue
            return True
        return False

    def can_wei(self, card):
        return 2 == self.__cards.count(card)

    def __wei_ti(self, card):  # 用偎牌来提
        for i in range(len(self.__zhuo_pai)):
            card_type = self.__zhuo_pai[i][0]
            first_card = self.__zhuo_pai[i][1]
            if card_type not in (zi_pai.CARD_TYPE_WEI, ):
                continue
            if first_card != card:
                continue
            self.__zhuo_pai[i] = [zi_pai.CARD_TYPE_TI, card, card, card, card]
            return True, i + 1
        return False, 0

    def __shou_ti(self, card):  # 用手牌来提
        if 3 != self.__cards.count(card):
            return False, 0
        cards = [card, card, card, card]
        self.__remove_cards([card] * 3)
        self.__add_zhuo_pai(zi_pai.CARD_TYPE_TI, cards)
        return True, len(self.__zhuo_pai)

    def ti(self, card):
        if 3 == self.__cards.count(card):
            return self.__shou_ti(card)
        return self.__wei_ti(card)

    def wei(self, card, is_chou):
        if 2 != self.__cards.count(card):
            return False
        cards = [card, card, card]
        self.__remove_cards([card] * 2)
        card_type = zi_pai.CARD_TYPE_CHOU_WEI if is_chou else zi_pai.CARD_TYPE_WEI
        self.__add_zhuo_pai(card_type, cards)
        return True

    def chi(self, card, chi_pai, bi_pai, rule):
        bi_pai = bi_pai or []
        flag = rule.is_chi_legal(self.cards, card, chi_pai, bi_pai)

        if not flag:
            return False

        self.__remove_cards(chi_pai)
        for item in bi_pai:
            self.__remove_cards(item)
            item.remove(card)
            item.insert(0, card)

        chi_pai.insert(0, card)
        chi_path = deepcopy(bi_pai)
        chi_path.insert(0, deepcopy(chi_pai))
        for item in chi_path:
            card_type = rule.get_card_type_of_three(item)
            item.remove(card)
            item.insert(0, card)
            self.__add_zhuo_pai(card_type, item)
        return True

    def add_chu_pai(self, card):
        self.__chu_cards.append(card)

    def peng(self, card):
        if 2 != self.__cards.count(card):
            return False
        cards = [card, card, card]
        self.__remove_cards([card] * 2)
        self.__add_zhuo_pai(zi_pai.CARD_TYPE_PENG, cards)
        return True

    def clear_cards(self):
        self.__clear_cards()

    @property
    def round_over_data(self):
        ret = {
            "seatID": self.seat_id,
            "handCards": self.cards,
            "tableCards": deepcopy(self.__zhuo_pai),
            "chuCards": deepcopy(self.__chu_cards),
            "score": self.__win_score,
            "totalScore": self.score + self.lock_score,
        }
        return ret

    def chi_de_qi(self):
        return flow.OPERATE_CHI in self.__operates

    def peng_de_qi(self):
        return flow.OPERATE_PENG in self.__operates

    def hu_de_qi(self):
        return flow.OPERATE_HU in self.__operates

    @property
    def is_xiang_gong(self):
        if not self.__cards:
            return True
        stat = RuleBase.stat_cards(self.__cards)
        for k, v in list(stat.items()):
            if 0 < v < 3:
                return False
        return True

    def ren_pai(self):
        """ 忍牌的操作 """
        if 0 >= self.__ren_pai_times:
            return False
        self.__ren_pai_times -= 1
        return True

    def is_chong_pao(self):  # 判断是否重跑
        count = 0
        for item in self.__zhuo_pai:
            if not item:
                continue
            if item[0] in (zi_pai.CARD_TYPE_TI, zi_pai.CARD_TYPE_PAO):
                count += 1
        return count >= 2

    def return_score(self, club_id):
        floor_model.update_club_user_score_by_lock_score(self.uid, club_id)
