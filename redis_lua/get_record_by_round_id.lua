local json = cjson

local key = KEYS[1]
local round_id = tonumber(ARGV[1])

assert(round_id ~= nil and round_id ~= "")

local ret = redis.call("lrange", key, 0, -1)
for _, v in ipairs(ret) do
    local data = json.decode(v)
    if data.round_id == round_id then
        return v
    end
end

return nil
