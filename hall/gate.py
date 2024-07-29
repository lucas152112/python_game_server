# coding:utf-8
from twisted.internet import reactor
from twisted.internet import endpoints

from base import const
from configs import config
from base.base_service import BaseService
from protocol.route_client import PubClientFactory
from utils import utils



class Gate(BaseService):

    def __init__(self):
        BaseService.__init__(self, const.SERVICE_GATE)
        self.__port = config.get_item("service_port") or 9995  # 端口
        utils.log("self.__port:" + str(self.__port), "gate.log")


    def on_signal_stop(self):  # 收到结束的信号
        utils.log("on_signal_stop", "gate.log")
        return self.__close_server()

    def __close_server(self):
        self.logger.info("start close pubsub server %d ", self.server_id)
        self.logger.info("stop listen channel %d ", self.server_id)
        utils.log("__close_server", "gate.log")

    def start_service(self):  # 启动服务
        utils.log("start_service-start", "gate.log")
        endpoints.serverFromString(reactor, "tcp:{0}".format(self.__port)).listen(PubClientFactory())
        self.logger.info('Starting listening on port %d', self.__port)
        reactor.addSystemEventTrigger('before', 'shutdown', self.on_signal_stop)
        reactor.run()
        utils.log("start_service-end", "gate.log")

    @staticmethod
    def share_server():
        return Gate()
