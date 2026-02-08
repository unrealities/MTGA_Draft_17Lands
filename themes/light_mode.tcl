option add *tearOff 0

array set colors {
    -fg             "#000000"
    -bg             "#ffffff"
    -disabledfg     "#999999"
    -disabledbg     "#f0f0f0"
    -selectfg       "#ffffff"
    -selectbg       "#007fff"
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

ttk::style map . -foreground [list disabled $colors(-disabledfg)]
option add *Menu.selectcolor $colors(-fg)

# Custom Styles
ttk::style configure Card.TFrame -background "#f0f0f0"
ttk::style configure Header.TLabel -foreground $colors(-selectbg) -font {Segoe UI 14 bold}
ttk::style configure SubHeader.TLabel -font {Segoe UI 12 bold}
ttk::style configure Muted.TLabel -foreground "#666666"
