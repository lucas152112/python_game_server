local key = "zset_table_id"

local id = redis.call("zrange", key, 0, 0)
redis.call("zremrangebyrank", key, 0, 0)

return id
