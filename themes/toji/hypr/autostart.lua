-- HyprAesthetic autostart — shared across all themes.
-- ha-theme session-start is idempotent (once per login via ~/.cache/HyprAesthetic/session-*.flag).

---@module 'hl'

hl.on("hyprland.start", function()
    hl.exec_cmd(os.getenv("HOME") .. "/.local/bin/ha-theme session-start")
end)
