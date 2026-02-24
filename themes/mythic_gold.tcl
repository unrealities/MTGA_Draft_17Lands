# ==============================================================================
# MTGA Draft Tool - Custom Theme Example: "Mythic Gold"
# ==============================================================================
# This file creates a fully isolated, custom TTK theme. It acts as a comprehensive
# cheat-sheet for everything you can customize in the MTGA Draft Tool.
#
# HOW TO CUSTOMIZE:
# Change the hex codes in the "1. DEFINE COLORS" section below, or alter the 
# font families in the "2. FONTS" section!
# ==============================================================================

# SAFEGUARD: Only create the theme if it doesn't already exist in memory
if {[lsearch [ttk::style theme names] mythic_gold] == -1} {

    ttk::style theme create mythic_gold -parent clam -settings {

        # --- 1. DEFINE COLORS ---
        set bg          "#1a0b2e"  ;# Main Background (Deep Indigo/Purple)
        set fg          "#f0f0f5"  ;# Main Text (Crisp off-white)
        set fieldbg     "#25143d"  ;# Input/Table Background (Slightly lighter indigo)
        set selectbg    "#d4af37"  ;# Selected Background (Mythic Gold!)
        set selectfg    "#000000"  ;# Selected Text (Black for high contrast)
        set disabledbg  "#2a1b3d"  ;# Disabled Background (Muted)
        set disabledfg  "#6b5b82"  ;# Disabled Text (Muted)
        set bordercol   "#3a2a5c"  ;# Standard border color
        
        # --- 2. FONTS ---
        # Fonts defined here will apply globally! 
        # (If a font family doesn't exist on your OS, Tkinter falls back to default)
        font create MythicTitleFont -family "Times New Roman" -size 11 -weight bold
        font create MythicStandardFont -family "Helvetica" -size 10
        font create MythicSmallFont -family "Helvetica" -size 9
        
        # --- 3. GLOBAL DEFAULTS (.) ---
        ttk::style configure . \
            -background $bg \
            -foreground $fg \
            -fieldbackground $fieldbg \
            -troughcolor $bg \
            -selectbackground $selectbg \
            -selectforeground $selectfg \
            -insertcolor $fg \
            -font MythicStandardFont \
            -borderwidth 1 \
            -bordercolor $bordercol
            
        ttk::style map . \
            -foreground [list disabled $disabledfg] \
            -background [list disabled $disabledbg]
            
        # --- 4. SPECIFIC WIDGET OVERRIDES ---
        
        # Frames (Layouts & Panels)
        ttk::style configure TFrame -background $bg
        ttk::style configure Card.TFrame -background $fieldbg -relief solid -borderwidth 1 -bordercolor $bordercol
        
        # Labels (Text)
        ttk::style configure TLabel -background $bg -foreground $fg
        ttk::style configure Muted.TLabel -foreground $disabledfg -font MythicSmallFont
        
        # Buttons
        ttk::style configure TButton -padding {8 4} -relief flat -background $fieldbg -foreground $fg
        ttk::style map TButton \
            -background [list active $selectbg disabled $disabledbg] \
            -foreground [list active $selectfg disabled $disabledfg]
            
        # Checkbuttons (Toggle boxes in Settings)
        ttk::style configure TCheckbutton -background $bg -foreground $fg -indicatorcolor $fieldbg
        ttk::style map TCheckbutton \
            -background [list active $bg] \
            -indicatorcolor [list selected $selectbg active $disabledbg] \
            -foreground [list active $selectbg]

        # Menubuttons (The Dropdowns used for Deck Filter, Events, etc.)
        ttk::style configure TMenubutton -background $fieldbg -foreground $fg -padding {5 2} -relief solid -bordercolor $bordercol
        ttk::style map TMenubutton \
            -background [list active $selectbg disabled $disabledbg] \
            -foreground [list active $selectfg disabled $disabledfg]
            
        # Search Bars & Comboboxes
        ttk::style configure TEntry -fieldbackground $fieldbg -foreground $fg -padding 4
        ttk::style configure TCombobox -fieldbackground $fieldbg -background $bg -foreground $fg -arrowcolor $selectbg
        ttk::style map TCombobox \
            -fieldbackground [list active $fieldbg focus $fieldbg] \
            -selectbackground [list active $selectbg focus $selectbg] \
            -selectforeground [list active $selectfg focus $selectfg]
            
        # Treeview (The Main Data Tables)
        ttk::style configure Treeview -background $fieldbg -fieldbackground $fieldbg -foreground $fg -borderwidth 0 -font MythicStandardFont
        ttk::style map Treeview \
            -background [list selected $selectbg] \
            -foreground [list selected $selectfg]
            
        # Treeview Headers (Column Titles)
        ttk::style configure Treeview.Heading -background $bg -foreground $selectbg -font MythicTitleFont -relief flat -padding 5
        ttk::style map Treeview.Heading \
            -background [list active $fieldbg] \
            -foreground [list active $fg]
        
        # Notebook (The Top Navigation Tabs)
        ttk::style configure TNotebook -background $bg -tabmargins {0 0 0 0}
        ttk::style configure TNotebook.Tab -background $bg -foreground $fg -padding {12 6} -font MythicTitleFont -borderwidth 0
        ttk::style map TNotebook.Tab \
            -background [list selected $fieldbg active $disabledbg] \
            -foreground [list selected $selectbg active $fg]
            
        # Progress Bar (Data Download screens)
        ttk::style configure TProgressbar -background $selectbg -troughcolor $fieldbg -borderwidth 0
        
        # Scrollbars
        ttk::style configure TScrollbar -background $fieldbg -troughcolor $bg -arrowcolor $selectbg -relief flat
        ttk::style map TScrollbar -background [list active $selectbg]

        # Panedwindow (The Draggable splitters between dashboard panels)
        ttk::style configure TPanedwindow -background $bg
        ttk::style configure Sash -background $fieldbg -bordercolor $bordercol -sashthickness 4
    }
}

# --- 5. NATIVE OS MENU OVERRIDES ---
# These commands style the standard Right-Click Context Menus and the Top Menu Bar
# Since menus are native to the OS and not part of TTK, we use standard Tk options.
option add *Menu.background "#25143d"
option add *Menu.foreground "#f0f0f5"
option add *Menu.activeBackground "#d4af37"
option add *Menu.activeForeground "#000000"
option add *Menu.selectcolor "#d4af37"
option add *Menu.font "Helvetica 10"

# --- 6. ACTIVATE THE THEME ---
ttk::style theme use mythic_gold
