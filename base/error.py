# coding:utf-8

# 服务端错误码列表
OK = 0  # 请求正常
DATA_BROKEN = -1  # 客户端请求数据错误，不符合即定格式
TOKEN_ERROR = -2
SYSTEM_ERROR = -3  # 系统错误
DUPLICATE_LOGIN = -4  # 客户端收到通知，账号已在别处登录
SEAT_FULL = -5  # 坐位已满
TABLE_NOT_EXIST = -6  # 桌子不存在
USER_NOT_EXIST = -7  # 玩家数据不存在
RULE_ERROR = -8  # 出牌不符合规则
NOT_YOUR_TURN = -9  # 当前循问的玩家不是你
CARD_NOT_EXIST = -10  # 所出牌不存在
IN_OTHER_ROOM = -11  # 玩家当前已在其它房间中
TABLE_FULL = -12  # 桌子已满
NOT_YOUR_ROOM = -13  # 不是你的桌子无法解散
COMMAND_DENNY = -14  # 命令不允许被执行
OPERATES_ILLEGAL = -15  # 当前玩家无此操作
OPERATES_DUPLICATE = -16  # 此玩家已操作
FLOW_ERROR = -17  # 当前流程不允许此操作
NOT_CLUB_MEMBER = -18  # 非俱乐部成员
DOU_ERROR = -19  # 豆子数量错误
AA_DIAMOND_ERROR = -22  # AA 钻石不足
GAME_ALREADY_START = -23  # 游戏已经开始
TABLE_PLAYER_BLOCK = -24  # 禁止同桌
RULE_BOMB_ERROR = -30  # 双扣出牌不符合规则
OTHER_BOMB_ERROR = -31  # 双扣出牌不符合规则
YUAN_BAO_NOT_ENOUGH = -32  # 元宝不足
DISTANCE_TOO_SHORT = -34  # 距离太近不予进入
POSTION_UNKNOWN = -35  # 位置不明不予进入
CLUB_IS_CLOSE = -36  # 俱乐部打烊中
ZHUA_PIG = -37  # 上坡
CARD_NOT_ALLOWED = -38  # 不允许出该牌
CLUB_PLAYER_FREEZE = -39  # 玩家冻结
SIGN_FAIL = -40  # 验证失败
ATTACK_NULL_ERROR = -41  # 玩家必须出牌
NEW_TURN_ERROR = -42  # 新的一轮出牌异常
TUO_GUAN_NOT_ALLOWED = -43  # 托管状态下不允许操作
CLUB_INSUFFICIENT_LEVEL = -44  # 等级不足
CLUB_SCORE_NOT_ENOUGH = -45  # 分数不足
SCORE_NOT_ZERO = -46  # 分数不为0
HU_PASS_TIME_LIMIT = -47  # 二次过胡时间未到
OPR_ID_ERROR = -48  # 二次过胡时间未到