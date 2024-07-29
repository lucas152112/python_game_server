import gevent
import requests
from utils import utils
import urllib.parse
from copy import deepcopy
from base import const
import socket
import time

PREFIX = "BENCH"
APP_SIGN_KEY = "2009CFD4-B5B1-4468-9ACE-60C3C6667B22"

# URL = "120.79.34.170"
URL = "localhost"
URL_PORT = 8899

GAME_ID = 10


class Player:
    all_time = 0

    def __init__(self, index):
        self.imei = PREFIX + str(index)
        self.mac = PREFIX + str(index)
        self.token = ""
        self.uid = 0
        self.http_path = URL
        self.http_port = URL_PORT
        self.server_path = ""
        self.server_port = 0

        self._sock = None
        self._sock_file = None

        self.__game_gate_time_sum = 0
        self.__client_gate_time_sum = 0
        self.__count = 1

    def login(self):
        data = self.request("guestLogin", {"imei": self.imei, "mac": self.mac})

        data = data["data"]

        self.uid = data["uid"]
        self.token = data["token"]

        server_info = data["server"]
        self.http_path = server_info["http_address"]
        self.http_port = server_info["http_port"]
        self.server_path = server_info["socket_address"]
        self.server_port = server_info["socket_port"]

        self.socket_connect()

    def socket_connect(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.connect((self.server_path, self.server_port))
        self._sock_file = self._sock.makefile(mode="rb")
        self.socket_send_data(201, {"gameId": GAME_ID, "uid": self.uid, "key": self.token})

        gevent.spawn(self.socket_receive)

    def socket_receive(self):
        while True:
            line = self._sock_file.readline()
            if not line:
                continue

            data = utils.json_decode(line)
            msg = data["msg"]
            print(msg)
            if "__game_send_time" in msg:
                msg = utils.json_decode(msg)
                Player.all_time += utils.timestamp_float() - float(msg["__game_send_time"])

            # print("receive", self.__client_gate_time_sum / self.__count, self.__game_gate_time_sum / self.__count)

            # print("receive", msg)
            # if data["cmd"] == 101:
            #
            #     Player.all_time += utils.timestamp_float() - msg["timestamp"]

            # return self.__connection_lost()

    def start_bench(self):
        self.start_heart()
        # self.start_create_room()

    def start_heart(self):
        self.socket_send_data(101, {"timestamp": utils.timestamp_float()})

    def start_create_room(self):
        room_id = self.create_hong_zhong()

        enter_room_data = {
            "x":
                "181",
            "data":
                utils.json_encode({
                    "loginTime":
                        1580872472,
                    "uid":
                        self.uid,
                    "roundCount":
                        174,
                    "sex":
                        2,
                    "nickName":
                        "Blake",
                    "avatar":
                        "http://thirdwx.qlogo.cn/mmopen/vi_32/CdR9bPIEjBCZQHEWKotibmaA6TLpNuNujXhIYnL6Y5F2sDhjklBGC4hboDWCic6gzM0ePlT36nZjwwbkffNnH14w/132",
                    "IP":
                        "219.83.188.2"
                }),
            "roomID":
                room_id,
            "_send_timestamp":
                1580872569.0698,
            "y":
                "91"
        }
        # print("enter_room_id", room_id)
        self.socket_send_data(202, enter_room_data)

        time.sleep(0.1)

        # print("dismiss_room", room_id)
        self.socket_send_data(1005, {})

    def create_hong_zhong(self):
        data = self.request("createRoom", {"gameType": const.SERVICE_HZMJ, "totalRound": 8, "ruleDetails": {}})
        return data["data"]["roomID"]

    def socket_send_data(self, cmd, params):
        if not params:
            params = dict()

        params["_send_timestamp"] = utils.timestamp_float()
        data = utils.json_encode({"cmd": cmd, "msg": params}).encode(encoding="utf-8") + b"\r\n"
        self._sock.send(data)

    def request(self, api: str, params: dict):
        fixed_params = self.get_fix_params()
        params_str = utils.json_encode(params)

        sign = self._get_sign(fixed_params, params_str, self.token)
        fixed_params["sign"] = sign

        req_url = "http://" + self.http_path + ":" + str(
            self.http_port) + "/" + api + "?" + urllib.parse.urlencode(fixed_params)

        req = requests.post(req_url, dict(params=params_str))

        if req.status_code == 200:
            return utils.json_decode(req.content)

        raise requests.HTTPError(req.status_code)

    @staticmethod
    def _get_sign(fixed_params, params_str, token=""):
        params = deepcopy(fixed_params)
        params["params"] = params_str
        keys = list(params.keys())
        keys.sort()
        values = []

        for k in keys:
            if k == "sign":
                continue
            tmp_str = str(params[k])
            values.append(k + '=' + urllib.parse.quote_plus(tmp_str))
        values.append("key={0}".format(APP_SIGN_KEY))
        if token and len(token) > 0:
            values.append("token={0}".format(token))

        sign_data = "&".join(values)
        return utils.md5(str.encode(sign_data, encoding="utf-8"))

    def get_fix_params(self):
        data = {
            'gameId': GAME_ID,
            'platform': 3,
            'ver': '1.0.0.0',
            'channelId': 3,
            'time': utils.timestamp(),
            'uid': self.uid
        }

        return data


if __name__ == '__main__':
    p = Player(1)
    p.login()

    p.start_bench()
    # p.start_bench()

    gevent.wait()
