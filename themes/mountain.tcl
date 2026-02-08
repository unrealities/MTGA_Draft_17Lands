option add *tearOff 0

array set colors {
    -fg             "#3b1612"
    -bg             "#f4d6cf"
    -disabledfg     "#9e7d78"
    -disabledbg     "#f9e8e3"
    -selectfg       "#ffffff"
    -selectbg       "#d35400"
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

ttk::style configure Card.TFrame -background "#f9e8e3"
ttk::style configure Header.TLabel -foreground "#c0392b" -font {Segoe UI 14 bold}
ttk::style configure SubHeader.TLabel -font {Segoe UI 12 bold}
ttk::style configure Muted.TLabel -foreground "#8a504a"

ttk::style map Treeview \
    -background [list selected $colors(-selectbg) {!focus selected} $colors(-selectbg)] \
    -foreground [list selected $colors(-selectfg) {!focus selected} $colors(-selectfg)]
