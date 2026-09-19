-- HyprAesthetic autostart — shared across all themes.
-- hyprland.start fires on every config reload; do NOT spawn processes here.
-- Login startup is handled by: exec-once = ha-theme session-start

---@module 'hl'

hl.on("hyprland.start", function()
    -- Intentionally empty. Spawning waybar/eww/hyprwave here duplicates them on theme switch.
end)
