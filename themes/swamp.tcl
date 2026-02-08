option add *tearOff 0

array set colors {
    -fg             "#e0d8e0"
    -bg             "#2a272a"
    -disabledfg     "#6e666e"
    -disabledbg     "#3e3b3e"
    -selectfg       "#ffffff"
    -selectbg       "#5d405d"
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

ttk::style configure Card.TFrame -background "#3e3b3e"
ttk::style configure Header.TLabel -foreground "#c084fc" -font {Segoe UI 14 bold}
ttk::style configure SubHeader.TLabel -font {Segoe UI 12 bold}
ttk::style configure Muted.TLabel -foreground "#a090a0"

ttk::style map Treeview \
    -background [list selected $colors(-selectbg) {!focus selected} $colors(-selectbg)] \
    -foreground [list selected $colors(-selectfg) {!focus selected} $colors(-selectfg)]
