from base.commands_base_game import *
""" 游戏命令列表 """
ENTER_ROOM = 1  # 进入房间
EXIT_ROOM = 2  # 退出房间
ROOM_CONFIG = 3  # 下发房间配置数据

PLAYER_ENTER_ROOM = 4  # 玩家进入
OWNER_DISMISS = 5  # 解散房间

GAME_START = 6  # 游戏开始
GAME_OVER = 7  # 游戏结束

ROUND_START = 8  # 一局开始
ROUND_OVER = 9  # 一局结束
REQUEST_DISMISS = 10  # 申请解散房间

READY = 11  # 准备消息
TURN_TO = 12  # 轮到某人出牌
PLAYER_CHU_PAI = 13  # 出牌
PLAYER_PASS = 14  # 过牌
DEAL_CARDS = 18  # 发牌

CLIENT_BROAD_CAST = 25  # 客户端广播数据

TIAN_HU_START = 15  # 天胡开始
TIAN_HU_END = 16  # 天胡结束
PLAYER_TI = 17  # 玩家提
PLAYER_WEI = 19  # 玩家偎
PLAYER_MO_PAI = 20  # 玩家摸牌
PLAYER_PAO = 21  # 玩家跑牌
PLAYER_PENG = 22  # 玩家碰
PLAYER_CHI = 23  # 玩家吃
PLAYER_HU_PAI = 26  # 玩家胡
NOTIFY_HU_PAI = 27  # 通知玩家是否胡牌
EVERYONE_PASS = 28  # 所有玩家都选择过牌
DEBUG_SET_CARDS = 29  # DEBUG模式下的设置牌
QI_SHOU_TI = 30  # 起手提牌消息

NOTIFY_POSITION = 31  # 开局通知定位
REQUEST_POSITION = 32  # 请求定位信息
CONFIRM_PLAYER_PASS = 33  # 确认过牌

CLOSE_TUO_GUAN = 40  # 取消托管
OPEN_TUO_GUAN = 41  # 开启托管

UPDATE_OPR_ID = 49  # 修改操作id

FORCE_DISMISS = 83  # 强制解散房间
ROOM_LIST = 86  # 房间列表
UPDATE_ROOM_LIST = 87  # 更新房间列表
ADD_ROOM = 88  # 创建房间
PLAY_CONFIG_CHANGE = 90  # 玩法更改

CLUB_FORCE_DISMISS = 92  # 俱乐部强制解散房间
