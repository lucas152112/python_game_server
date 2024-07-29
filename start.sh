curpath=$(cd `dirname $0`; pwd)

#启动 gate服务器
#python $curpath/gate.py 1 daemon

#sleep 1

#启动 router服务器
python $curpath/router.py 1 daemon

sleep 1

#循环遍历启动 所有游戏服务器
for file in `ls -a | grep gameserver_`
do
    sleep 1
    python $curpath/"$file" 1 daemon
done
