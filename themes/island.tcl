option add *tearOff 0

array set colors {
    -fg             "#0d1b2a"
    -bg             "#c1d7e9"
    -disabledfg     "#778da9"
    -disabledbg     "#dcf0f8"
    -selectfg       "#ffffff"
    -selectbg       "#0077b6"
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

ttk::style configure Card.TFrame -background "#dcf0f8"
ttk::style configure Header.TLabel -foreground "#005f73" -font {Segoe UI 14 bold}
ttk::style configure SubHeader.TLabel -font {Segoe UI 12 bold}
ttk::style configure Muted.TLabel -foreground "#415a77"

ttk::style map Treeview \
    -background [list selected $colors(-selectbg) {!focus selected} $colors(-selectbg)] \
    -foreground [list selected $colors(-selectfg) {!focus selected} $colors(-selectfg)]
