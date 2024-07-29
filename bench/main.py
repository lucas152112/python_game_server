from gevent import monkey

monkey.patch_all()

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import gevent

from bench.player import Player

is_break = False


def new_player_and_bench(index):
    global is_break
    p = Player(index)
    p.login()

    # is_break = True
    # while True:
    for _ in range(99):
        p.start_bench()
        gevent.sleep(0.01)

        if is_break:
            break


def main(argv):
    global is_break
    if not argv:
        argv.append(1)
    prefix = int(argv[0]) * (10**5)
    for i in range(100):
        gevent.spawn_later(i / 100, new_player_and_bench, prefix + i)

    # gevent.spawn_later(10, sys.exit, -2)

    try:
        gevent.wait()
    except KeyboardInterrupt:
        is_break = True
        try:
            gevent.wait()
        except KeyboardInterrupt:
            print(Player.all_time)


if __name__ == '__main__':
    main(sys.argv[1:])
