echo "开始kill服务器...."
./stop.sh

sleep 2
echo "kill结束"

echo "开始启动服务器...."
./start.sh

sleep 1
echo "启动结束"
