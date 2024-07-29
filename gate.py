# coding:utf-8
from base import const
from base.init_gate import start_gate

if __name__ == '__main__':
    from hall.gate import Gate

    start_gate(Gate, const.SERVICE_GATE, __file__[0:-3])
