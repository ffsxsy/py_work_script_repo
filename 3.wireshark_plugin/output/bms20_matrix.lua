-- LAN Matrix multi-version loader (Message ID map + parse_config + payload defs)

bms20_active_matrix_version = bms20_active_matrix_version or nil
BMS20_MATRIX_VERSION = BMS20_MATRIX_VERSION or nil
bms20_matrix_last_error = bms20_matrix_last_error or nil

local function matrix_plugin_dir()
    local src = debug.getinfo(1, "S").source
    if src:sub(1, 1) == "@" then
        src = src:sub(2)
    end
    return src:match("^(.*[/\\])") or ""
end

local function matrix_log(msg)
    bms20_matrix_last_error = msg
    print("BMS2.0 matrix: " .. msg)
end

local function dofile_reported(path, label)
    local ok, err = pcall(dofile, path)
    if not ok then
        matrix_log(string.format("%s load failed (%s): %s", label, path, tostring(err)))
        return false
    end
    return true
end

local function ensure_registry()
    if type(bms20_matrix_versions) == "table" and type(bms20_matrix_dir_slug) == "table" then
        return true
    end
    local dir = matrix_plugin_dir()
    local path = dir .. "bms20_matrix_registry.lua"
    if not dofile_reported(path, "registry") then
        return false
    end
    if type(bms20_matrix_versions) ~= "table" then
        matrix_log("registry loaded but bms20_matrix_versions missing")
        return false
    end
    return true
end

local function version_is_supported(version)
    if not ensure_registry() then
        return false
    end
    for _, entry in ipairs(bms20_matrix_versions) do
        if entry == version then
            return true
        end
    end
    return false
end

local function version_from_pref(selected)
    -- Pref.enum (Wireshark 4.6) returns the numeric `value` field (0-based index)
    if type(selected) == "number" and ensure_registry() then
        local by_value = bms20_matrix_versions[selected + 1]
        if by_value ~= nil then
            return by_value
        end
    end
    if type(selected) == "string" then
        local trimmed = selected:match("^%s*(.-)%s*$") or ""
        if version_is_supported(trimmed) then
            return trimmed
        end
    end
    return nil
end

function bms20_matrix_version_from_prefs(proto)
    if proto ~= nil and proto.prefs ~= nil and proto.prefs.matrix_version ~= nil then
        local resolved = version_from_pref(proto.prefs.matrix_version)
        if resolved ~= nil then
            return resolved
        end
    end
    if ensure_registry() then
        return bms20_matrix_default or bms20_matrix_versions[#bms20_matrix_versions]
    end
    return "V1.0.57"
end

local function matrix_package_path(version)
    if not ensure_registry() then
        return nil
    end
    local slug = bms20_matrix_dir_slug[version]
    if slug == nil then
        return nil
    end
    return matrix_plugin_dir() .. "matrix_" .. slug .. "/"
end

function bms20_load_matrix_package(version, _proto)
    bms20_matrix_last_error = nil
    if not ensure_registry() then
        return false, "matrix registry missing (copy bms20_matrix_registry.lua + matrix_v1_0_* dirs)"
    end
    local resolved = version
    if not version_is_supported(resolved) then
        resolved = bms20_matrix_default or bms20_matrix_versions[1]
    end

    local pkg_dir = matrix_package_path(resolved)
    if pkg_dir == nil then
        local err = string.format("unknown matrix version %s", tostring(version))
        matrix_log(err)
        return false, err
    end

    if not dofile_reported(pkg_dir .. "bms20_msg_map.lua", "msg_map " .. resolved) then
        return false, "msg_map load failed: " .. pkg_dir
    end

    bms20_payload_defs = {}
    bms20_payload_by_segment = nil
    bms20_parse_segments = nil

    if not dofile_reported(pkg_dir .. "bms20_parse_config.lua", "parse_config " .. resolved) then
        return false, "parse_config load failed: " .. pkg_dir
    end

    local manifest_ok, manifest = pcall(dofile, pkg_dir .. "bms20_payload_manifest.lua")
    if not manifest_ok then
        matrix_log(string.format(
            "payload_manifest load failed (%s): %s",
            pkg_dir .. "bms20_payload_manifest.lua", tostring(manifest)))
        return false, "payload_manifest load failed"
    end
    if type(manifest) ~= "table" then
        matrix_log("payload_manifest did not return a table: " .. pkg_dir)
        return false, "payload_manifest invalid"
    end

    local failed = {}
    for _, fname in ipairs(manifest) do
        local path = pkg_dir .. fname
        local ok, err = pcall(dofile, path)
        if not ok then
            failed[#failed + 1] = fname
            matrix_log(string.format("payload def load failed (%s): %s", path, tostring(err)))
        end
    end
    if #failed > 0 then
        matrix_log(string.format(
            "%s: %u/%u payload files failed (%s)",
            resolved, #failed, #manifest, table.concat(failed, ", ")))
        -- Continue with partial defs; Message Name still works from msg_map.
    end

    bms20_active_matrix_version = resolved
    BMS20_MATRIX_VERSION = resolved

    if type(bms20_on_matrix_package_loaded) == "function" then
        bms20_on_matrix_package_loaded(_proto, resolved)
    end

    print(string.format(
        "BMS2.0 matrix: loaded %s (%u payload files, %u failed)",
        resolved, #manifest, #failed))
    return true, resolved
end

function bms20_ensure_matrix_package(proto)
    local want = bms20_matrix_version_from_prefs(proto)
    if bms20_active_matrix_version == want and type(bms20_msg_map) == "table" then
        return true, want
    end
    local ok, detail = bms20_load_matrix_package(want, proto)
    if not ok then
        matrix_log(string.format(
            "ensure failed for %s: %s (install output/matrix_v1_0_* next to bms20_matrix.lua)",
            tostring(want), tostring(detail)))
    end
    return ok, detail
end
