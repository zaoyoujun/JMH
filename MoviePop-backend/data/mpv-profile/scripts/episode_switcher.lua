local utils = require 'mp.utils'

mp.msg.info("episode_switcher.lua loaded!")

local CACHE_FILE = mp.command_native({"path-substitute", "~~/../episode_cache.json"})
if not CACHE_FILE or CACHE_FILE == "~~/../episode_cache.json" then
    CACHE_FILE = os.getenv("APPDATA") .. "/mpv/episode_cache.json"
end

local episode_cache = {}

local function load_cache()
    local f = io.open(CACHE_FILE, "r")
    if f then
        local content = f:read("*all")
        f:close()
        if content and #content > 0 then
            local success, data = pcall(utils.parse_json, content)
            if success and data then
                episode_cache = data
                mp.msg.info("Loaded cache with " .. #episode_cache .. " entries")
            end
        end
    end
end

local function save_cache()
    local f = io.open(CACHE_FILE, "w")
    if f then
        local success, json = pcall(utils.format_json, episode_cache)
        if success and json then
            f:write(json)
            mp.msg.info("Cache saved to " .. CACHE_FILE)
        end
        f:close()
    else
        mp.msg.error("Failed to open cache file for writing: " .. CACHE_FILE)
    end
end

load_cache()

local function url_encode(s)
    return s:gsub("[^a-zA-Z0-9]", function(c) return string.format("%%%02X", string.byte(c)) end)
end

local function url_decode(s)
    s = s:gsub("+", " ")
    s = s:gsub("%%(%x%x)", function(h) return string.char(tonumber(h, 16)) end)
    return s
end

local function get_local_path_from_url(url)
    if not url then return nil end
    local movie_path = url:match("movie_path=([^&]+)")
    if movie_path then
        return url_decode(movie_path)
    end
    return nil
end

local function get_directory_path(file_path)
    if not file_path then return nil end
    return file_path:match("^(.+)[/\\][^/\\]+$")
end

local function natural_sort(a, b)
    local function get_nums(s)
        local nums = {}
        for num in s:gmatch("%d+") do table.insert(nums, tonumber(num)) end
        return nums
    end
    local a_nums, b_nums = get_nums(a), get_nums(b)
    for i = 1, math.max(#a_nums, #b_nums) do
        if i > #a_nums then return true end
        if i > #b_nums then return false end
        if a_nums[i] ~= b_nums[i] then
            return a_nums[i] < b_nums[i]
        end
    end
    return a < b
end

local function get_episode_files(movie_path)
    if not movie_path then
        mp.msg.info("movie_path is nil")
        return {}
    end

    local encoded_path = url_encode(movie_path)
    local url = "http://127.0.0.1:8765/api/movies/item?movie_path=" .. encoded_path
    mp.msg.info("API request path: " .. encoded_path)

    local cmd = {"curl", "-s", url}
    local result = utils.subprocess({args = cmd, cancellable = false})

    if not result.error and result.status == 0 then
        mp.msg.info("API response length: " .. #result.stdout)

        local success, data = pcall(utils.parse_json, result.stdout)
        if success and data then
            mp.msg.info("JSON parsed successfully")
            
            if data.movie then
                mp.msg.info("Found movie object")
                
                if data.movie.is_series then
                    mp.msg.info("is_series: true")
                    
                    if data.movie.episode_files and type(data.movie.episode_files) == "table" then
                        local episode_files = {}
                        for i, path in ipairs(data.movie.episode_files) do
                            mp.msg.info("episode[" .. i .. "]: " .. path)
                            table.insert(episode_files, path)
                        end
                        mp.msg.info("found " .. #episode_files .. " episode files")
                        return episode_files
                    else
                        mp.msg.info("episode_files is nil or not an array")
                    end
                else
                    mp.msg.info("is_series: false")
                end
            else
                mp.msg.info("no movie object found in response")
            end
        else
            mp.msg.error("Failed to parse JSON: " .. tostring(data))
            mp.msg.info("Raw response: " .. string.sub(result.stdout, 1, 300))
        end
        return {}
    else
        mp.msg.error("API call failed: " .. tostring(result.error) .. " status: " .. tostring(result.status))
        return {}
    end
end

local function build_stream_url(file_path)
    local dir, filename = utils.split_path(file_path)
    if not filename then
        filename = file_path:match("[^/\\]*$")
        if not filename or filename == "" then
            filename = "unknown"
        end
    end
    local encoded_filename = url_encode(filename)
    local encoded_path = url_encode(file_path)
    return "http://127.0.0.1:8765/api/stream/media/" .. encoded_filename .. "?movie_path=" .. encoded_path .. "&provider=openlist"
end

local function switch_to_episode(local_path, direction)
    mp.msg.info("switch_to_episode called with local_path: " .. tostring(local_path) .. " direction: " .. direction)

    local dir_path = get_directory_path(local_path)
    mp.msg.info("directory path: " .. tostring(dir_path))

    local episode_files = nil

    if dir_path and episode_cache[dir_path] then
        mp.msg.info("Using cached episode list for directory: " .. dir_path)
        episode_files = episode_cache[dir_path]
    else
        episode_files = get_episode_files(local_path)
        if dir_path and #episode_files > 0 then
            episode_cache[dir_path] = episode_files
            mp.msg.info("Cached episode list for directory: " .. dir_path)
            save_cache()
        end
    end

    mp.msg.info("got " .. #episode_files .. " episode files")

    if #episode_files == 0 then
        mp.osd_message("无法获取剧集列表", 2)
        return
    end

    table.sort(episode_files, natural_sort)

    for i, f in ipairs(episode_files) do
        mp.msg.info("sorted[" .. i .. "]: " .. f)
    end

    local current_index = nil
    for i, f in ipairs(episode_files) do
        mp.msg.info("comparing: [" .. i .. "] " .. f)
        mp.msg.info("with local_path: " .. tostring(local_path))
        if f == local_path then
            mp.msg.info("exact match found at index " .. i)
            current_index = i
            break
        end
    end

    if not current_index then
        mp.msg.info("current path not found in episode list, trying partial match")
        for i, f in ipairs(episode_files) do
            if f:find(local_path:match("[^/\\]+$")) then
                current_index = i
                mp.msg.info("found partial match at index " .. i)
                break
            end
        end
    end

    if not current_index then
        mp.msg.info("current path not found in episode list")
        mp.osd_message("当前文件不在列表中", 2)
        return
    end

    mp.msg.info("found at index " .. current_index)

    local function switch_episode(next_file, next_url)
        mp.commandv("loadfile", next_url, "replace")
    end

    if direction == 1 and current_index < #episode_files then
        local next_file = episode_files[current_index + 1]
        local next_url = build_stream_url(next_file)
        mp.msg.info("loading next: " .. next_file)
        mp.msg.info("stream url: " .. next_url)
        mp.osd_message("下一集: " .. next_file:match("([^/\\]+)$"), 2)
        switch_episode(next_file, next_url)
    elseif direction == -1 and current_index > 1 then
        local prev_file = episode_files[current_index - 1]
        local prev_url = build_stream_url(prev_file)
        mp.msg.info("loading prev: " .. prev_file)
        mp.msg.info("stream url: " .. prev_url)
        mp.osd_message("上一集: " .. prev_file:match("([^/\\]+)$"), 2)
        switch_episode(prev_file, prev_url)
    else
        if direction == 1 then
            mp.osd_message("已经是最后一集", 2)
        else
            mp.osd_message("已经是第一集", 2)
        end
    end
end

mp.register_script_message("next-episode", function()
    local url = mp.get_property("path")
    local local_path = get_local_path_from_url(url)
    mp.msg.info("=== next-episode triggered ===")
    mp.msg.info("url: " .. tostring(url))
    mp.msg.info("local_path: " .. tostring(local_path))
    if local_path then
        switch_to_episode(local_path, 1)
    else
        mp.msg.error("Failed to extract local path from URL")
        mp.osd_message("无法获取本地路径", 2)
    end
end)

mp.register_script_message("prev-episode", function()
    local url = mp.get_property("path")
    local local_path = get_local_path_from_url(url)
    mp.msg.info("=== prev-episode triggered ===")
    mp.msg.info("url: " .. tostring(url))
    mp.msg.info("local_path: " .. tostring(local_path))
    if local_path then
        switch_to_episode(local_path, -1)
    else
        mp.msg.error("Failed to extract local path from URL")
        mp.osd_message("无法获取本地路径", 2)
    end
end)
