option add *tearOff 0

array set colors {
    -fg             "#2c2825"
    -bg             "#f8f6f1"
    -disabledfg     "#a0a0a0"
    -disabledbg     "#fcfbf9"
    -selectfg       "#2c2825"
    -selectbg       "#f0e6bc"
}

ttk::style configure . \
    -background $colors(-bg) \
    -foreground $colors(-fg) \
    -troughcolor $colors(-bg) \
    -focuscolor $colors(-selectbg) \
    -selectbackground $colors(-selectbg) \
    -selectforeground $colors(-selectfg) \
    -insertcolor $colors(-fg) \
    -insertwidth 1 \
    -fieldbackground $colors(-bg) \
    -borderwidth 1 \
    -relief flat

tk_setPalette background $colors(-bg) \
    foreground $colors(-fg) \
    highlightColor $colors(-selectbg) \
    selectBackground $colors(-selectbg) \
    selectForeground $colors(-selectfg) \
    activeBackground $colors(-bg) \
    activeForeground $colors(-fg)

ttk::style configure Card.TFrame -background "#fcfbf9"
ttk::style configure Header.TLabel -foreground "#d4af37" -font {Segoe UI 14 bold}
ttk::style configure SubHeader.TLabel -font {Segoe UI 12 bold}
ttk::style configure Muted.TLabel -foreground "#8a8580"

ttk::style map Treeview \
    -background [list selected $colors(-selectbg) {!focus selected} $colors(-selectbg)] \
    -foreground [list selected $colors(-selectfg) {!focus selected} $colors(-selectfg)]
