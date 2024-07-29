local key = KEYS[1]
local min = tonumber(ARGV[1])
local max = tonumber(ARGV[2])

assert(min ~= nil and max ~= nil and min < max)

local data = redis.call("get", key)
if not data then
    redis.call("set", key, min)
    redis.call("incr", key)
    return min
end

local now_id = tonumber(data)
if now_id == nil then
    redis.call("set", key, min)
    redis.call("incr", key)
    return min
end

if now_id > max then
    redis.call("set", key, min + 1)
    return min
end

redis.call("incr", key)

return now_id
