# MTGA_Draft_17Lands

Magic: The Gathering Arena draft tool that utilizes 17Lands data.

**This application will automatically support new sets as soon as the sets are released on Arena _and_ the data is available on the [17Lands card ratings](https://www.17lands.com/card_ratings) page.**

**Supported Events:** Premier Draft, Traditional Draft, Quick Draft, Sealed, and Traditional Sealed
  
![Premier_Draft](https://github.com/unrealities/MTGA_Draft_17Lands/blob/main/assets/96687942/9d7283ff-cb8b-46f9-8d72-7bf531d707b1.png)

## Table of Contents

- [MTGA\_Draft\_17Lands](#mtga_draft_17lands)
  - [Table of Contents](#table-of-contents)
  - [Run Steps: Windows Executable (Windows Only)](#run-steps-windows-executable-windows-only)
  - [Run Steps: Python (Windows/Mac/Linux)](#run-steps-python-windowsmaclinux)
  - [Build Steps: setup.exe (Windows Only)](#build-steps-setupexe-windows-only)
  - [UI Features](#ui-features)
  - [Menu Features](#menu-features)
  - [Additional Features](#additional-features)
  - [Settings](#settings)
  - [Card Logic](#card-logic)
  - [The P1P1 Solution](#the-p1p1-solution)
    - [The Problem](#the-problem)
    - [The Solution](#the-solution)
    - [Future Considerations](#future-considerations)
  - [Troubleshooting](#troubleshooting)

## Run Steps: Windows Executable (Windows Only)

- **Step 1:** Download the latest zip file from the [releases page](https://github.com/unrealities/MTGA_Draft_17Lands/releases).
- **Step 2:** Unzip and double-click the exe file to start the installation.
- **Step 3:** (Optional) Go to the installed folder and right-click the executable (`MTGA_Draft_Tool.exe`), click properties, compatibility tab, and check Run this program as an administrator.
  - This step is only required if the application is installed in a directory with write restrictions (i.e., `Program Files` and `Program Files (x86)`).
  - This step isn't necessary if the application is installed in the main directory of a drive (i.e., `C:/` or `D:/`) or the `Users/<Username>/` directory

- **Step 4:** In Arena, go to Adjust Options, Account, and then check the Detailed Logs (Plugin Support) check box.
- **Step 5:** Double-click `MTGA_Draft_Tool.exe` to start the program.
- **Step 6:** Download the sets that you plan on using (`Data->Add Sets`).
  - Event datasets can be used for different events (e.g., you can use the premier draft dataset for a sealed event).
  - Quick draft players should consider using the premier draft dataset when quick draft initially becomes available.
- **Step 7:** Configure the tool through the [Settings window](#settings).
  - Users that are new to 17Lands might find the [Win Rate Grades](#card-logic) (`Win Rate Format: Grade`) more useful than the win rate percentages.
  - The [UI Size](#settings) setting can be used to adjust the image and text size.
- **Step 8:** Start the draft in Arena.
  - The Arena log doesn't list P1P1 for premier and traditional drafts until after P1P2.
    - **New 3.19** Pressing the `Refresh` button will use OCR to identify the cards your first pack. See [The P1P1 Solution](#the-p1p1-solution) for more information on this feature.
    - The [Card Compare](#menu-features) feature can also be used as a substitute for P1P1.
  - The sealed card pool can be found in the [Taken Cards window](#menu-features).

## Run Steps: Python (Windows/Mac/Linux)

- **Step 1:** [Download](https://github.com/unrealities/MTGA_Draft_17Lands/archive/refs/heads/main.zip) and unzip the `MTGA_Draft_17Lands-main.zip` file or clone the repository.
  - Some recent Python-related bug fixes have been made since the 3.10 release. Please download the code from the [main branch](https://github.com/unrealities/MTGA_Draft_17Lands/archive/refs/heads/main.zip) instead of the 3.10 release.

- **Step 2:** Download and install Python 3.12.
  - [Windows](https://www.python.org/downloads/windows/).
  - [Mac](https://www.python.org/downloads/macos/).
  - [Linux](https://wiki.python.org/moin/BeginnersGuide/Download#Linux).

- **Step 3:** Confirm that you're running Python 3.12 by opening the terminal, entering ```python --version```, and checking for a ```Python 3.12.*``` result.

- **Step 4:** Install the Python package installer Pip by entering ```python -m ensurepip --upgrade```.

- **Step 5:** Open the terminal and install the Python dependencies by entering ```pip install -r requirements.txt```.

- **Step 6:**
  - (Mac Only) Install web certificates by going to `/Applications/Python 3.##/` and double-clicking the file `Install Certificates.command`.
  - (Linux only) [Install Tk](https://tkdocs.com/tutorial/install.html#installlinux)

- **Step 7:** In Arena, go to Adjust Options, Account, and then check the Detailed Logs (Plugin Support) check box.

- **Step 8:** Start the application by opening the terminal and entering ```python main.py```.

- **Step 9:** If the application asks you for the location of the Arena player log, then click `File->Open` and select the log file from one of the following locations:
  - **Windows:** {drive}/Users/{username}/AppData/LocalLow/Wizards Of The Coast/MTGA/Player.log
  - **Mac:** {username}/Library/Logs/Wizards Of The Coast/MTGA/Player.log
  - **Bottles (Linux):** /home/{username}/.var/app/com.usebottles.bottles/data/bottles/bottles/MTG-Arena/drive_c/users/{username}/AppData/LocalLow/Wizards Of The Coast/MTGA/Player.log
  - **Lutris (Linux):** /home/{username}/Games/magic-the-gathering-arena/drive_c/users/{username}/AppData/LocalLow/Wizards Of The Coast/MTGA/Player.log

- **Step 10:** (Mac Only) Set Arena to window mode.

- **Step 11:** Download the sets that you plan on using (`Data->Add Sets`).
  - Event datasets can be used for different events (e.g., you can use the premier draft dataset for a sealed event).
  - Select `Arena Cube` and adjust the start date to download the data from the most recent Arena Cube event.
  - Quick draft players should consider using the premier draft dataset when quick draft initially becomes available.
  
- **Step 12:** Configure the tool through the [Settings window](#settings).
  - Users that are new to 17Lands might find the [Win Rate Grades](#card-logic) (`Win Rate Format: Grade`) more useful than the win rate percentages.
  - The [UI Size](#settings) setting can be used to adjust the image and text size.

- **Step 13:** Start the draft in Arena.
  - The Arena log doesn't list P1P1 for premier and traditional drafts until after P1P2.
    - **New 3.19** Pressing the `Refresh` button will use OCR to identify the cards your first pack. See [The P1P1 Solution](#the-p1p1-solution) for more information on this feature.
  - The [Card Compare](#menu-features) feature can be used as a substitute for P1P1.
  - The sealed card pool can be found in the [Taken Cards window](#menu-features).

## Build Steps: setup.exe (Windows Only)

- **Step 1:** Download and install Python 3.12.
- **Step 2:** Install the Python package installer Pip by opening the terminal and entering ```python -m ensurepip --upgrade```.
- **Step 3:** Open the terminal and enter ```pip install -r requirements.txt```.
- **Step 4:** [Download Inno Setup](https://jrsoftware.org/isdl.php#stable)
- **Step 5:** Build MTGA_Draft_Tool.exe by opening the terminal and entering ```python -m PyInstaller  main.py --onefile --noconsole -n MTGA_Draft_Tool --clean```
  - If this fails to build, you probably need to add an exclusion in your Windows virus & threat protection.
- **Step 6:** Open `Installer.iss` in Inno Setup and click Build->Compile.
  - In the `{app}` folder, rename the mysetup.exe file to `setup.exe` and move the file to the main `MTGA_Draft_17Lands` folder.

## UI Features

- **Current Draft:** Lists the current draft type (i.e., Premier, Quick, or Traditional) that the application has identified.
  - In the Arena logs, P1P1 doesn't appear for Premier and Traditional drafts until after P1P2.
  - You can hide this feature by deselecting `Enable Current Draft Display` in the [Settings window](#settings)
- **Data Source:** Lists the current draft type (i.e., Premier, Quick, or Traditional) from which the application is pulling the card data.
  - The application will attempt to pull data for the current draft type and set (e.g., data from NEO_PremierDraft_Data.json for a Premier Draft). If the user hasn't downloaded the data file for the current draft type and set, then the application will attempt to use a different data file from the same set (e.g., NEO_QuickDraft_Data.json if NEO_PremierDraft_Data.json isn't available).
  - This field will display "None" if the application is unable to find a valid data file for the current draft type and set.
  - You can hide this feature by deselecting `Enable Data Source Options` in the [Settings window](#settings)
  - **New 3.18** You can select a given user group. 17lands provides data from "Top", "Bottom" and "Middle" users. This data needs to be fetched when you add set data, the default option remains "All" [Definitions of user groups](https://www.17lands.com/metrics_definitions).
- **Deck Filter:** A drop-down that lists all of the available deck color permutations that you can use to filter the deck card ratings.
  - The percentage next to the number represents the win rate for that color combination. These percentage values are collected from the [color ratings page on 17Lands](https://www.17lands.com/color_ratings). If there are no values, then that means the sample size was too small to determine the win rate (unpopular deck combination).
  - The `All Decks` option lists the combined rating across all of the deck color combinations
    - The `Auto` option will keep the filter at `All Decks` for the first 15 picks and then switch over to the filter that best matches your taken cards. See the Auto Highest Rating note in the Card Logic section.
  - You can hide this feature by deselecting `Enable Deck Filter Options` in the [Settings window](#settings)
- **Refresh Button:** Trigger a log read.
  - Can find cards for P1P1 using [The P1P1 Solution](#the-p1p1-solution)
  - The application will automatically read new log entries, so this button is not required unless you are using an outdated operating system (Windows 7 or 8).
  - You can hide this feature by deselecting `Enable Refresh Button` in the [Settings window](#settings)
- **Pack / Pick Table:** This table displays the cards included in the current pack.  
  - If a dataset is missing `Data Source: None` or an unrecognized card is listed, this table will show a number under the name column.
- **Missing Cards Table:** This table displays the cards missing from a pack that has already been seen.
  - The user's chosen card will have an asterisk next to the name.
  - You can hide this feature by deselecting `Enable Missing Cards` in the [Settings window](#settings)
- **Draft Stats Table:** This table lists the card distribution and total for creatures, noncreatures, and all cards that were taken during the draft.
  - The numbered columns represent the cost of the card (cmc).
  - You can hide this feature by deselecting `Enable Draft Stats` in the [Settings window](#settings)

## Menu Features

![Settings_Dark](https://github.com/unrealities/MTGA_Draft_17Lands/blob/main/assets/96687942/642a0795-e407-410e-b8d6-6332f3083ac7.png)
![Settings_Colors](https://github.com/unrealities/MTGA_Draft_17Lands/blob/main/assets/96687942/90c6b3df-0ade-4f32-a1be-b2ef40cedc32.png)

- **Read Draft Logs:** Read the log file from a draft by selecting `File->Open`. Select a file that has the following naming scheme `DraftLog_<Set>_<Draft Type>_<Draft_ID>.log` file to read the file.
- **Download Set Data:** Get to the Add Sets window by selecting `Data->Add Sets`. Enter the set information and click on the ADD SET button to begin downloading the set data.
  - The download can take several minutes.
  - 17Lands will timeout the request if too many requests are made within a short period of time.
- **List Taken Cards:** Get to the Taken Cards window by selecting `Cards->Taken Cards`.
  - This table lists the cards that were taken by the user throughout the draft.
- **List Suggested Decks:** Get to the Suggested Decks window by selecting `Cards->Suggest Decks`.
  - This table displays a 40-card deck created by the application using the cards you have obtained during the event. In certain cases, multiple decks may be shown if the application is able to create them.
  - It is possible for the application to be unable to generate any decks if this option is selected before the event concludes or if an insufficient number of creatures were chosen.
    - The application constructs decks according to various criteria, including the Games in Hand Win Rate of each card. The rating indicated represents the combined Games in Hand Win Rate of all cards in the deck.
- **Card Compare:** Get to the Card Compare window by selecting `Cards->Compare Cards`. You will be able to compare the cards you have entered using this window.
  - This feature can be used to quickly compare cards for P1P1 of the Premier and Traditional drafts.

## Additional Features

- **Hotkey:** The user can use the hotkey `CTRL+G` to toggle between minimizing and maximizing the main application window.
  - This feature doesn't work on Mac.
  - You need to run the executable as an administrator for this feature to work in Arena.
- **Top-Level Window:** The main application window, and subsequent windows, will act as an overlay and remain above all other windows, including the Arena screen.
- **Tier List:** A tier list can be added to the drop-downs by following the instructions in [tier list README](https://github.com/unrealities/MTGA_Draft_17Lands/tree/main/Tools/TierScraper17Lands#tier-list-download-extension).
- **Card Tooltips:** Clicking on any card row will display a tooltip that contains the card images (back and front) and the 17Lands data.

## Settings

- **Columns 2-7:** Set the field for columns 2-7 of the pack table, missing table, and compare table.
- **Deck Filter Format:** Switch the Deck Filter to either the color permutations (i.e., UB, BG, WUG, etc.) or the guild/shard/clan names (i.e., Dimir, Golgari, Bant, etc.).
- **Win Rate Format:** Switch the results for the win rate fields (such as GIHWR, OHWR, GPWR, etc.) to percentage (17Lands values), ratings (5-point rating scale) or grades (A+ to F). See the Win Rate Ratings section for more details.
- **Enable Current Draft Display:** Toggle the visibility of the Current Draft indicator in the main window.
- **Enable Data Source Options:** Toggle the visibility of the Data Source drop-down in the main window.
- **Enable Deck Filter Options:** Toggle the visibility of the Deck Filter drop-down in the main window.
- **Enable Refresh Button:** Toggle the visibility of the Refresh button drop-down in the main window.
- **Enable Row Colors:** Sets the row color to the card color.
- **Enable Color Identity:** Once activated, the Colors field will showcase the mana symbols representing both the mana cost and abilities of a card, such as kicker, activated abilities, and more.
- **Enable Draft Stats:** Displays the draft stats table and drop-down in the main window.
- **Enable Missing Cards:** Displays the missing cards table in the main window.
- **Enable Highest Rated:** Enables the highest rated card logic for the `Auto` filter. See the auto highest rating note in the [Card Logic](#card-logic) section.
- **Enable Bayesian Average:** Enables the Bayesian average logic for all win rate fields. See the Bayesian average note in the [Card Logic](#card-logic) section.
  - **As of September 2023, this feature has become obsolete. The 17Lands endpoint no longer provides win rate data for cards with fewer than 500 samples.**
- **Enable Draft Log:** Records the draft in a log file within the `./Logs` folder.
- **UI Size:** Increase or decrease the size of the application text and images.

## Card Logic

- **Win Rate Grades:** The application will calculate the mean and standard deviation for all of the win rate fields (GIHWR, OHWR, GPWR, GDWR, etc.). Based on the number of standard deviations from the mean, it will then assign a letter grade.
  - Example: If the mean OHWR for the set is 56.8% and the standard deviation is 4.68, then a card with an OHWR of 62% will have a letter grade of B+ since it's between 1 standard deviation (`56.8 + 1 * 4.68 = 61.48%`) and 1.33 standard deviations (`56.8 + 1.33 * 4.68 = 63.02%`) from the mean (see the table below).

| Letter Grade     | Standard Deviations|
|:----------------:|:------------------:|
| A+               | >= 2.00            |
| A                | >= 1.67            |
| A-               | >= 1.33            |
| B+               | >= 1.00            |
| B                | >= 0.67            |
| B-               | >= 0.33            |
| C+               | >= 0               |
| C                | >= -0.33           |
| C-               | >= -0.67           |
| D+               | >= -1.00           |
| D                | >= -1.33           |
| D-               | >= -1.67           |
| F                | <  -1.67           |

- **Win Rate Ratings:** The application will calculate the mean and standard deviation to identify an upper and lower limit (-1.67 to 2.00 standard deviations from the mean) and perform the following calculation to determine a card's rating: `((card_gihwr - lower_limit) / (upper_limit - lower_limit)) * 5.0`
  - Example: If the calculated mean and standard deviation for a set are 56.8% and 4.68, then the upper limit will be `56.8 + 2.00 * 4.68 = 66.16%`, the lower limit will be `56.8 - 1.67 * 4.68 = 48.98%`, and the resulting rating for a card with a win rate of 62% will be `(((62 - 48.98) / (66.16 - 48.98)) * 5.0 = 3.7)`

- **Bayesian Average:** When this feature is activated, the win rate data is subjected to a Bayesian average calculation that takes into account specific assumptions  (e.g., an anticipated range of 40-60% with a mean of 50%). This Bayesian average considers both prior assumptions and observed data, providing a more reliable estimation of the win rate, particularly in cases where sample sizes are small (less than 200 samples) or data availability is limited. A comprehensive explanation can be found [here](https://github.com/unrealities/MTGA_Draft_17Lands/issues/5#issuecomment-1075193138).
  - Enabled: The application will apply this calculation to all win rate data. However, the adjustment made by the calculation will gradually diminish as the sample count, such as the number of games in hand for the Games in Hand Win Rate, reaches 200. As the sample size increases, the Bayesian average will be more influenced by the observed data rather than the prior assumptions, resulting in a more reliable estimation of the win rate.
  - Disabled: The application will not apply this calculation to the win rate data.
  - **As of September 2023, this feature has become obsolete. The 17Lands endpoint no longer provides win rate data for cards with fewer than 500 samples.**

- **Auto Highest Rating:** If the `Auto` filter is set, and the user has taken at least 16 cards, then the application will try and determine the leading color combination from the taken cards. If the tool is unable to identify a definitive leading color pair, then it will display the highest win rate of the top two color combinations for each win rate field (e.g., GIHWR, OHWR, etc.). The filter label will display both color combinations separated by a slash (e.g., `Auto (WB/UBG)`).
  - Example: If the user has taken primarily black, blue, and green cards, and Generous Visitor has a BG win rate of 66% and a UB rating of 15%, then the displayed win rate will be 66%.

- **Deck Suggester:** The deck suggester will create multiple decks (Aggro, Mid, and Control) for each viable color combination using a pool of cards with the highest win rates. It will follow generic deck building requirements. The suggester will assess and rate each deck, selecting the highest-rated one for each viable color combination. The deck suggester will NOT identify card synergies and build an intentionally synergistic deck.
  - Deck Building Requirements:
    - Aggro Deck:
      - The deck must have a minimum of 9 creatures and should have no less than 17 creatures.
      - The deck should include a minimum of two 1-drops, five 2-drops, and three 3-drops.
      - The average CMC (Converted Mana Cost)  of all of the creatures must be 2.40 or less.
      - The deck has 16 lands.
    - Mid Deck:
      - The deck must have a minimum of 9 creatures and should have no less than 15 creatures.
      - The deck should include a minimum of four 2-drops, three 3-drops, two 4-drops, and one 5-drop.
      - The average CMC of all of the creatures must be 3.04 or less.
      - The deck has 17 lands.
    - Control Deck:
      - The deck must have a minimum of 9 creatures and should have no less than 10 creatures.
      - The deck should include a minimum of three 2-drops, two 3-drops, two 4-drops, and one 5-drop.
      - The average CMC of all of the creatures must be 3.68 or less.
      - The deck has 18 lands.
  - Notes:
    - The CMC average and land requirements were derived from this [article](https://www.channelfireball.com/article/How-Many-Lands-Do-You-Need-in-Your-Deck-An-Updated-Analysis/cd1c1a24-d439-4a8e-b369-b936edb0b38a/).
    - The deck distribution and CMC requirements may occasionally lead to the inclusion of cards that have lower performance or are considered less effective.
      - Example: If the user possesses a pool of white and blue cards and the available 3-drops are Acquisition Octopus (53.7% win rate for WU) and Guardians of Oboro (50.7% win rate for WU), the deck suggester will include both of these cards to meet the 3-drop requirement for each deck archetype.
    - The rating is determined by calculating the combined GIHWR of all the cards and then subtracting penalties for not meeting the deck requirements.
    - The NEO creature sagas count as creatures.

- **Wheel:** The "WHEEL" option intention is to show you the percentage likelihood of a specific card in a pack to be available the second time you see the pack (on the wheel).
  - The logic in the code already existed and I do not know if a bug was found and it was not implemented, or if the creator wanted to simply improve upon it before releasing it.
  - Only the first six packs are considered and cards with ALSA of <2 are automatically excluded.
  - The math appears to follow closely what Sierkovitz published in this [article](https://mtgazone.com/how-to-wheel-in-drafts/)

## The P1P1 Solution

### The Problem

MTGA_Draft_17Lands, like many other platforms, relies on MTG Arena's detailed logs to function. Pack and pick data is read from these logs to determine what cards to display 17 Lands data for. However, we understand the frustration that MTG Arena does not show the pack data for the very first pack of drafts, which can be a significant drawback.

### The Solution

We implemented the following solution in v3.19. **This only works for P1P1. After you have selected a card, only Arena logs are used**:

- A screenshot is taken when you press the `Refresh` button. The application converts the image to a base64 string.
- The string and a list of possible card names are sent to a Google Cloud Function (GCF).
- The GCF uses Google Vision API for Optical Character Recognition (OCR). This API returns all text detected in the image.
- The Google Vision results are compared to the possible card names sent via [TheFuzz](https://github.com/seatgeek/thefuzz).
- All possible matches are P1P1 cards; no data persists locally or via GCF.

### Future Considerations

- The Google Cloud Function has a cost, and only 1000 requests each month are free. If used excessively, the endpoint may need to be deactivated.
- There is currently no way to turn this functionality off. It does need to be triggered, however. Our application will never take screenshots unless you hit `Refresh` on P1P1.
- Since image data does not persist, you do not know what Google received. We may implement an option to persist screenshots locally for full transparency.

## Troubleshooting

- **Some cards are missing from the Taken Cards window:** Due to Arena creating a new player log after every restart, the application cannot track cards that were picked and seen prior to a restart. However, players who engage in drafting sessions spanning multiple days or sessions can still utilize this tool to access the current pack data. It should be noted that this application may not have access to information regarding previous packs and picks, resulting in some missing data.

- **The application can't generate set or debug files:** Windows users might need to run the application as an administrator if the application is installed in directory with restricted write access.

- **My sealed card pool is missing after restarting Arena:** Arena creates a new player log after every restart, so you will need to open up your sealed event session log by clicking `File->Open` and selecting the `DraftLog_<Set>_Sealed` file if you want to see your sealed card pool. Keep in mind that opening a log file will prevent the application from reading the Arena player log. Therefore, if you wish to initiate a new Arena event, you'll need to restart the application.

- **The tables are displaying a win rate of 0% or NA:** The application will display a card win rate value of 0% or NA if that win rate field has fewer than 500 samples (e.g., GIHWR will be 0% or NA if the number of games in hand is less than 500). Users should consider using the premier draft dataset or downloading a [tier list](https://github.com/unrealities/MTGA_Draft_17Lands/tree/main/Tools/TierScraper17Lands#tier-list-download-extension) for events that have a low player count.
  - ***As of September 2023, the 17Lands endpoint no longer provides win rate data for cards with fewer than 500 samples.**

- **CTRL+G doesn't do anything:** If you're a Mac user, then this shortcut isn't available. If you're a Windows user, then you need to run the application as an administrator.

- **The set download process is taking 5+ minutes and I'm seeing _Collecting 17Lands Data - Request Failed_ multiple times:** If you attempt to download too many sets within a short period of time, 17Lands will impose rate-limiting on your connection. Therefore, when downloading multiple sets, it is advisable to wait at least 10 minutes between each set.

- **SSL errors in log on MacOS: `ERROR - limited_sets.retrieve_scryfall_sets - <urlopen error [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1000)`** Install SSL certificates via /Applications/Python 3.12/Install Certificates.command
