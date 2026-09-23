-- Neovim theme rendered from theme.toml

local M = {}

M.name = "a70"
M.display_name = "A70"

M.colors = {
    base00 = "#0d0d0d",
    base01 = "#1a1a1a",
    base02 = "#2a2a2a",
    base03 = "#3a3a3a",
    base04 = "#cccccc",
    base05 = "#ffffff",
    base06 = "#ffffff",
    base07 = "#ffffff",
    base08 = "#ff6b6b",
    base09 = "#ff9f43",
    base0A = "#ffe66d",
    base0B = "#69db7c",
    base0C = "#5fe4ff",
    base0D = "#74b9ff",
    base0E = "#a29bfe",
    base0F = "#ff7675",
}

M.groups = {
    Normal = { fg = M.colors.base05, bg = M.colors.base00 },
    NormalFloat = { fg = M.colors.base05, bg = M.colors.base01 },
    Cursor = { fg = M.colors.base00, bg = M.colors.base05 },
    Visual = { bg = M.colors.base02 },
    Comment = { fg = M.colors.base03, italic = true },
    Constant = { fg = M.colors.base0C },
    String = { fg = M.colors.base0B },
    Character = { fg = M.colors.base0B },
    Number = { fg = M.colors.base0E },
    Boolean = { fg = M.colors.base0E },
    Identifier = { fg = M.colors.base08 },
    Function = { fg = M.colors.base0D },
    Statement = { fg = M.colors.base0E },
    Keyword = { fg = M.colors.base0E },
    Operator = { fg = M.colors.base0F },
    Type = { fg = M.colors.base0A },
    Special = { fg = M.colors.base0C },
    Underlined = { fg = M.colors.base0D, underline = true },
    Error = { fg = M.colors.base00, bg = M.colors.base08 },
    ErrorMsg = { fg = M.colors.base08 },
    WarningMsg = { fg = M.colors.base0A },
    LineNr = { fg = M.colors.base03 },
    CursorLineNr = { fg = M.colors.base0D, bold = true },
    SignColumn = { fg = M.colors.base03 },
    Folded = { fg = M.colors.base04, bg = M.colors.base01 },
    FoldColumn = { fg = M.colors.base03 },
    MatchParen = { bg = M.colors.base02, bold = true },
    StatusLine = { fg = M.colors.base04, bg = M.colors.base01 },
    StatusLineNC = { fg = M.colors.base03, bg = M.colors.base01 },
    TabLine = { fg = M.colors.base03, bg = M.colors.base00 },
    TabLineFill = { bg = M.colors.base00 },
    TabLineSel = { fg = M.colors.base0D, bg = M.colors.base01 },
    WinSeparator = { fg = M.colors.base03 },
    Pmenu = { fg = M.colors.base05, bg = M.colors.base01 },
    PmenuSel = { fg = M.colors.base00, bg = M.colors.base0D },
    Directory = { fg = M.colors.base0D },
    Title = { fg = M.colors.base0D, bold = true },
}

function M.setup()
    vim.o.background = "dark"
    vim.o.termguicolors = true
    vim.g.colors_name = M.name

    for group, opts in pairs(M.groups) do
        vim.api.nvim_set_hl(0, group, opts)
    end
end

return M
