option add *tearOff 0

array set colors {
    -fg             "#2b2b2b"
    -bg             "#d6d4d4"
    -disabledfg     "#999999"
    -disabledbg     "#e8e8e8"
    -selectfg       "#ffffff"
    -selectbg       "#607d8b"
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

ttk::style configure Card.TFrame -background "#e8e8e8"
ttk::style configure Header.TLabel -foreground "#455a64" -font {Segoe UI 14 bold}
ttk::style configure SubHeader.TLabel -font {Segoe UI 12 bold}
ttk::style configure Muted.TLabel -foreground "#757575"

ttk::style map Treeview \
    -background [list selected $colors(-selectbg) {!focus selected} $colors(-selectbg)] \
    -foreground [list selected $colors(-selectfg) {!focus selected} $colors(-selectfg)]
