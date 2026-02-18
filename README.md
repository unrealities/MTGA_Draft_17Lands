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
  - [UI Features](#ui-features)
  - [Menu Features](#menu-features)
  - [Additional Features](#additional-features)
  - [Settings](#settings)
  - [File Locations](#file-locations)
    - [Configuration (`config.json`)](#configuration-configjson)
    - [Datasets](#datasets)
    - [Logs](#logs)
  - [Card Logic](#card-logic)
  - [The P1P1 Solution](#the-p1p1-solution)
    - [The Problem](#the-problem)
    - [The Solution](#the-solution)
    - [Future Considerations](#future-considerations)
  - [Tier List (API-Based)](#tier-list-api-based)
    - [How It Works](#how-it-works)
    - [How to Use](#how-to-use)
  - [Signal Detection (Beta)](#signal-detection-beta)
  - [Dataset Notifications](#dataset-notifications)
    - [No Datasets Found](#no-datasets-found)
    - [Missing Dataset](#missing-dataset)
    - [Dataset Update Available](#dataset-update-available)
  - [Troubleshooting](#troubleshooting)
    - [Known Issues](#known-issues)
    - [Arena Log Issues](#arena-log-issues)
      - [Premier and Traditional Drafts](#premier-and-traditional-drafts)
      - [Quick Drafts](#quick-drafts)
      - [Sealed and Traditional Sealed](#sealed-and-traditional-sealed)
  - [Development](#development)
    - [Environment Setup](#environment-setup)
    - [Running Tests](#running-tests)
    - [Version Management](#version-management)
    - [Building the Executable](#building-the-executable)

## Run Steps: Windows Executable (Windows Only)

- **Step 1:** Download the latest zip file from the [releases page](https://github.com/unrealities/MTGA_Draft_17Lands/releases).
- **Step 2:** Unzip and double-click the exe file to start the installation.
- **Step 3:** (Optional) Go to the installed folder and right-click the executable (`MTGA_Draft_Tool.exe`), click properties, compatibility tab, and check "Run this program as an administrator."
  - This step is only required if the application is installed in a directory with write restrictions (i.e., `Program Files` and `Program Files (x86)`).
  - This step isn't necessary if the application is installed in the main directory of a drive (i.e., `C:/` or `D:/`) or the `Users/<Username>/` directory
- **Step 4:** In Arena, go to Adjust Options, Account, and then check the Detailed Logs (Plugin Support) check box.
- **Step 5:** Double-click `MTGA_Draft_Tool.exe` to start the program.
- **Step 6:** Download the sets you plan to use (`Data->Download Dataset`).
  Event datasets can be used for different events (e.g., the premier draft dataset can be used for a sealed event).
  - Quick draft players should consider using the premier draft dataset when quick draft initially becomes available.
- **Step 7:** Configure the tool through the [Settings window](#settings).
  - Users that are new to 17Lands might find the [Win Rate Grades](#card-logic) (`Win Rate Format: Grade`) more valuable than the win rate percentages.
  - The [UI Size](#settings) setting can adjust the image and text size.
- **Step 8:** Start the draft in Arena.
  - The Arena log doesn't list P1P1 for premier and traditional drafts until after P1P2.
  - Pressing the `Refresh` button will help OCR identify the cards in your first pack. For more information on this feature, see [The P1P1 Solution](#the-p1p1-solution).
    - The [Card Compare](#menu-features) feature can also be used as a substitute for P1P1.
  - The sealed card pool can be found in the [Taken Cards window](#menu-features).

## Run Steps: Python (Windows/Mac/Linux)

- **Step 1:** [Download](https://github.com/unrealities/MTGA_Draft_17Lands/archive/refs/heads/main.zip) and unzip the `MTGA_Draft_17Lands-main.zip` file or clone the repository.
  - Some recent Python-related bug fixes have been made since the 3.10 release. Please download the code from the [main branch](https://github.com/unrealities/MTGA_Draft_17Lands/archive/refs/heads/main.zip) instead of the 3.10 release.
- **Step 2:** Download and install Python 3.12.
  - [Windows](https://www.python.org/downloads/windows/).
  - [Mac](https://www.python.org/downloads/macos/).
  - [Linux](https://wiki.python.org/moin/BeginnersGuide/Download#Linux).
- **Step 3:** Confirm that you're running Python 3.12 by opening the terminal, entering `python --version`, and checking for a `Python 3.12.*` result.
- **Step 4:** Install the Python package installer Pip by entering `python -m ensurepip --upgrade`.
- **Step 5:** Open the terminal and install the Python dependencies by entering `pip install -r requirements.txt`.
- **Step 6:**
  - (Mac Only) Install web certificates by going to `/Applications/Python 3.##/` and double-clicking the file `Install Certificates.command`.
  - (Linux only) [Install Tk](https://tkdocs.com/tutorial/install.html#installlinux)
- **Step 7:** In Arena, go to Adjust Options, Account, and then check the Detailed Logs (Plugin Support) check box.
- **Step 8:** Start the application by opening the terminal and entering `python main.py`.
- **Step 9:** If the application asks you for the location of the Arena player log, then click `File->Read Player.log` and select the log file from one of the following locations:
  - **Windows:** {drive}/Users/{username}/AppData/LocalLow/Wizards Of The Coast/MTGA/Player.log
  - **Mac:** {username}/Library/Logs/Wizards Of The Coast/MTGA/Player.log
  - **Bottles (Linux):** /home/{username}/.var/app/com.usebottles.bottles/data/bottles/bottles/MTG-Arena/drive_c/users/{username}/AppData/LocalLow/Wizards Of The Coast/MTGA/Player.log
  - **Lutris (Linux):** /home/{username}/Games/magic-the-gathering-arena/drive_c/users/{username}/AppData/LocalLow/Wizards Of The Coast/MTGA/Player.log
- **Step 10:** (Mac Only) Set Arena to window mode.
- **Step 11:** Download the sets you plan to use (`Data->Download Dataset`).
  - Event datasets can be used for different events (e.g., the premier draft dataset can be used for a sealed event).
  - Select `Arena Cube` and adjust the start date to download the data from the most recent Arena Cube event.
  - Quick draft players should consider using the premier draft dataset when quick draft initially becomes available.
- **Step 12:** Configure the tool through the [Settings window](#settings).
  - Users that are new to 17Lands might find the [Win Rate Grades](#card-logic) (`Win Rate Format: Grade`) more valuable than the win rate percentages.
  - The [UI Size](#settings) setting can be used to adjust the size of the image and text.
- **Step 13:** Start the draft in Arena.
  - The Arena log doesn't list P1P1 for premier and traditional drafts until after P1P2.
  - Pressing the `Refresh` button will help OCR identify the cards in your first pack. For more information on this feature, see [The P1P1 Solution](#the-p1p1-solution).
  - The [Card Compare](#menu-features) feature can be used as a substitute for P1P1.
  - The sealed card pool can be found in the [Taken Cards window](#menu-features).

## UI Features

- **Current Draft:** Lists the current draft type (i.e., Premier, Quick, or Traditional) that the application has identified.
  - P1P1 doesn't appear for Premier and Traditional drafts until after P1P2 in the Arena logs.
  - You can hide this feature by deselecting `Enable Current Draft Display` in the [Settings window](#settings)
- **Data Source:** Lists the current draft type (i.e., Premier, Quick, or Traditional) from which the application pulls the card data.
  - The application will attempt to pull data for the current draft type and set (e.g., data from NEO_PremierDraft_Data.json for a Premier Draft). If the user hasn't downloaded the data file for the current draft type and set, then the application will attempt to use a different data file from the same set (e.g., NEO_QuickDraft_Data.json if NEO_PremierDraft_Data.json isn't available).
  - This field will display "None" if the application cannot find a valid data file for the current draft type and set.
  - You can hide this feature by deselecting `Enable Data Source Options` in the [Settings window](#settings)
  - You can select a given user group. 17lands provides data from "Top," "Bottom," and "Middle" users. This data needs to be fetched when you add set data; the default option remains "All" [Definitions of user groups](https://www.17lands.com/metrics_definitions).
- **Deck Filter:** A drop-down that lists all available deck color permutations that you can use to filter the deck card ratings.
  - The percentage next to the number represents the win rate for that color combination. These percentage values are collected from the [color rating page on 17Lands](https://www.17lands.com/color_ratings). If there were no values, the sample size was too small to determine the win rate (unpopular deck combination).
  - The `All Decks` option lists the combined rating across all of the deck color combinations
    - The `Auto` option will keep the filter at `All Decks` for the first 15 picks and then switch over to the filter that best matches your taken cards. See the Auto Highest Rating note in the Card Logic section.
  - You can hide this feature by deselecting `Enable Deck Filter Options` in the [Settings window](#settings)
- **Logs Button:** Triggers a manual read of the `Player.log` file.
  - Useful if the application doesn't automatically detect a new pick immediately (e.g., due to file system lag).
  - Fast operation (text parsing only).
- **P1P1 Button:** Triggers the Screen Capture + OCR process to find cards in the first pack (where logs are often delayed).
  - Use this if you are in Pack 1, Pick 1 and the list is empty.
  - See [The P1P1 Solution](#the-p1p1-solution) for details.
  - Slower operation (requires screenshot and network call).
  - You can hide these buttons by deselecting `Enable Refresh Button` in the [Settings window](#settings)- **Pack / Pick Table:** This table displays the cards included in the current pack.
  - This table will show a number under the name column if a dataset is missing `Data Source: None` or an unrecognized card is listed.
- **Missing Cards Table:** This table displays the cards missing from an already seen pack.
  - The user's chosen card will have an asterisk next to the name.
  - You can hide this feature by deselecting `Enable Missing Cards` in the [Settings window](#settings)
- **Draft Stats Table:** This table lists the card distribution and total for creatures, non-creatures, and all cards taken during the draft.
  - The numbered columns represent the cost of the card (CMC).
  - You can hide this feature by deselecting `Enable Draft Stats` in the [Settings window](#settings)
- **Signals Table:** This table displays calculated "Signal Scores" for each of the 5 colors. See [Signal Detection](#signal-detection-beta) for details.
  - You can hide this feature by deselecting `Enable Signals` in the [Settings window](#settings)

## Menu Features

![Settings_Dark](https://github.com/unrealities/MTGA_Draft_17Lands/blob/main/assets/96687942/642a0795-e407-410e-b8d6-6332f3083ac7.png)
![Settings_Colors](https://github.com/unrealities/MTGA_Draft_17Lands/blob/main/assets/96687942/90c6b3df-0ade-4f32-a1be-b2ef40cedc32.png)

- **Read Draft Logs:** Read the log file from a draft by selecting `File->Read Draft Log`. Select a file that has the following naming scheme `DraftLog_<Set>_<Draft Type>_<Draft_ID>.log` file to read the file.
- **Export Draft Data:** Export the full history of the current draft (every pack seen and pick made) to a CSV or JSON file by selecting `File->Export Draft Data`.
  - This is useful for analyzing your draft path, signals, and wheel percentages in external tools (Excel, Python, etc.).
  - The export includes card identity, 17Lands statistics, and a "Picked" flag.
- **Download Set Data:** Open the Download Dataset window by selecting `Data->Download Dataset`. Enter the set information and click the ADD SET button to begin downloading the set data.
  - The download can take several minutes.
  - 17Lands will timeout the request if too many requests are made within a short period.
  - **Min Games:** You can adjust the minimum number of games required for color ratings (default: 500). Lowering this is useful for low-population formats like Cube or Flashback drafts where data is scarce.
- **List Taken Cards:** Get to the Taken Cards window by selecting `Cards->Taken Cards`.
  - This table lists the cards that were taken by the user throughout the draft.
- **List Suggested Decks:** Get to the Suggested Decks window by selecting `Cards->Suggest Decksa`.
  - This table displays a 40-card deck created by the application using the cards you have obtained during the event. Sometimes, multiple decks may be shown if the application can make them.
  - The application may be unable to generate any decks if this option is selected before the event concludes or if an insufficient number of creatures are chosen.
  - The application constructs decks according to various criteria, including each card's Games in Hand Win Rate. The rating indicated represents the combined Games in Hand Win Rate of all cards in the deck.
- **Card Compare:** Get to the Card Compare window by selecting `Cards->Compare Cards`. You can compare the cards you have entered using this window.
  - This feature can quickly compare cards for P1P1 of the Premier and Traditional drafts.

## Additional Features

- **Hotkey:** The user can use the hotkey `CTRL+G` to toggle between minimizing and maximizing the main application window.
  - This feature doesn't work on Mac.
  - You need to run the executable as an administrator for this feature to work in Arena.
- **Tier List:** You can now add a tier list directly from the 17Lands API. Use the application's `Data > Download Tier List` menu to enter a 17Lands tier list URL and label. Once downloaded, the tier list will appear in the drop-down options during drafts. See the [Tier List (API-Based)](#tier-list-api-based) section for details.
- **Card Tooltips:** Clicking on any card row will display a tooltip that contains the card images (back and front) and the 17Lands data.

## Settings

- **Columns 2-7:** Set the field for columns 2-7 of the pack table, missing table, and compare table.
- **Deck Filter Format:** Switch the Deck Filter to either the color permutations (i.e., UB, BG, WUG, etc.) or the guild/shard/clan names (i.e., Dimir, Golgari, Bant, etc.).
- **Win Rate Format:** Switch the results for the win rate fields (such as GIHWR, OHWR, GPWR, etc.) to a percentage (17Lands values), ratings (5-point rating scale) or grades (A+ to F). See the Win Rate Ratings section for more details.
- **Enable Current Draft Display:** Toggle the visibility of the Current Draft indicator in the main window.
- **Enable Data Source Options:** Toggle the visibility of the Data Source drop-down in the main window.
- **Enable Deck Filter Options:** Toggle the visibility of the Deck Filter drop-down in the main window.
- **Enable Refresh Button:** Toggle the visibility of the Refresh button drop-down in the main window.
- **Enable Row Colors:** Sets the row color to the card color.
- **Enable Color Identity:** Once activated, the Colors field will showcase the mana symbols representing both the mana cost and abilities of a card, such as kicker, activated abilities, and more.
- **Enable Draft Stats:** Displays the draft stats table and drop-down in the main window.
- **Enable Signals:** Displays the signal detection table (Beta feature).
- **Enable Missing Cards:** Displays the missing cards table in the main window.
- **Enable Highest Rated:** Enables the highest-rated card logic for the `Auto` filter. See the auto-highest rating note in the [Card Logic](#card-logic) section.
- **Enable Bayesian Average:** Enables the Bayesian average logic for all win rate fields. See the Bayesian average note in the [Card Logic](#card-logic) section.
  - **As of September 2023, this feature has become obsolete. The 17Lands endpoint no longer provides win rate data for cards with fewer than 500 samples.**
- **Enable Draft Log:** Records the draft in a log file within the `./Logs` folder.
- **UI Size:** Increase or decrease the application text and image size.
- **Enable P1P1 OCR:** Enables [The P1P1 Solution](#the-p1p1-solution).
- **Save P1P1 Screenshots:** When using [The P1P1 Solution](#the-p1p1-solution) screenshots will be saved to the `./Screenshots` folder.

## File Locations

The application stores your settings and data in specific locations to ensure they persist across updates.

### Configuration (`config.json`)

The application looks for the configuration file in the following order:

1. **Local Folder:** If `config.json` exists in the same folder as the application, it is used. This allows for "Portable Mode" (e.g., running from a USB drive).
2. **System User Folder:** If no local file is found, the application uses the standard user data directory:
   - **Windows:** `%APPDATA%\MTGA_Draft_Tool\config.json`
   - **Mac:** `~/Library/Application Support/MTGA_Draft_Tool/config.json`
   - **Linux:** `~/.config/MTGA_Draft_Tool/config.json`

### Datasets

Downloaded card data is stored in the `Sets` folder located in the same directory as the application executable.

### Logs

Application debug logs are stored in the `Debug` folder, and draft logs are stored in the `Logs` folder, both located in the same directory as the application executable.

## Card Logic

- **Win Rate Grades:** The application calculates the mean and standard deviation for all of the win rate fields (GIHWR, OHWR, GPWR, GDWR, etc.) and assigns a letter grade based on the number of standard deviations from the mean.
- Example: If the mean OHWR for the set is 56.8% and the standard deviation is 4.68, then a card with an OHWR of 62% will have a letter grade of B+ since it's between 1 standard deviation (`56.8 + 1 * 4.68 = 61.48%`) and 1.33 standard deviations (`56.8 + 1.33 * 4.68 = 63.02%`) from the mean (see the table below).

| Letter Grade | Standard Deviations |
| :----------: | :-----------------: |
|      A+      |       >= 2.00       |
|      A       |       >= 1.67       |
|      A-      |       >= 1.33       |
|      B+      |       >= 1.00       |
|      B       |       >= 0.67       |
|      B-      |       >= 0.33       |
|      C+      |        >= 0         |
|      C       |      >= -0.33       |
|      C-      |      >= -0.67       |
|      D+      |      >= -1.00       |
|      D       |      >= -1.33       |
|      D-      |      >= -1.67       |
|      F       |       < -1.67       |

- **Win Rate Ratings:** The application will calculate the mean and standard deviation to identify an upper and lower limit (-1.67 to 2.00 standard deviations from the mean) and perform the following calculation to determine a card's rating: `((card_gihwr - lower_limit) / (upper_limit - lower_limit)) * 5.0`
  - Example: If the calculated mean and standard deviation for a set are 56.8% and 4.68, then the upper limit will be `56.8 + 2.00 * 4.68 = 66.16%`, the lower limit will be `56.8 - 1.67 * 4.68 = 48.98%`, and the resulting rating for a card with a win rate of 62% will be `(((62 - 48.98) / (66.16 - 48.98)) * 5.0 = 3.7)`

- **Bayesian Average:** When this feature is activated, the win rate data is subjected to a Bayesian average calculation that considers specific assumptions (e.g., an anticipated range of 40-60% with a mean of 50%). This Bayesian average considers prior assumptions and observed data, providing a more reliable estimation of the win rate, particularly in small sample sizes (less than 200 samples) or where data availability is limited. A comprehensive explanation can be found [here](https://github.com/unrealities/MTGA_Draft_17Lands/issues/5#issuecomment-1075193138).
  - Enabled: The application will apply this calculation to all win rate data. However, the adjustment made by the calculation will gradually diminish as the sample count, such as the number of games in hand for the Games in Hand Win Rate, reaches 200. As the sample size increases, the Bayesian average will be more influenced by the observed data rather than the prior assumptions, resulting in a more reliable estimation of the win rate.
  - Disabled: The application will not apply this calculation to the win rate data.
  - **As of September 2023, this feature has become obsolete. The 17Lands endpoint no longer provides win rate data for cards with fewer than 500 samples.**

- **Auto Highest Rating:** If the `Auto` filter is set, and the user has taken at least 16 cards, then the application will try and determine the leading color combination from the taken cards. If the tool cannot identify a definitive leading color pair, it will display the highest win rate of the top two color combinations for each win rate field (e.g., GIHWR, OHWR, etc.). The filter label will display both color combinations separated by a slash (e.g., `Auto (WB/UBG)`).
  - Example: If the user has taken primarily black, blue, and green cards, and Generous Visitor has a BG win rate of 66% and a UB rating of 15%, the displayed win rate will be 66%.

- **Deck Suggester:** The deck suggester will create multiple decks (Aggro, Mid, and Control) for each viable color combination using a pool of cards with the highest win rates. It will follow generic deck-building requirements. The suggester will assess and rate each deck, selecting the highest-rated one for each viable color combination. The deck suggester will NOT identify card synergies and build an intentionally synergistic deck.
  - Deck Building Requirements:
    - Aggro Deck:
      - The deck must have a minimum of 9 creatures and should have no less than 17 creatures.
      - The deck should include a minimum of two 1-drops, five 2-drops, and three 3-drops.
      - All creatures' average CMC (Converted Mana Cost) must be 2.40 or less.
      - The deck has 16 lands.
    - Mid Deck:
      - The deck must have a minimum of 9 creatures and should have no less than 15 creatures.
      - The deck should include a minimum of four 2-drops, three 3-drops, two 4-drops, and one 5-drop.
      - The average CMC of all creatures must be 3.04 or less.
      - The deck has 17 lands.
    - Control Deck:
      - The deck must have a minimum of 9 creatures and should have no less than 10 creatures.
      - The deck should include a minimum of three 2-drops, two 3-drops, two 4-drops, and one 5-drop.
      - The average CMC of all creatures must be 3.68 or less.
      - The deck has 18 lands.
  - Notes:
    - The CMC average and land requirements were derived from this [article](https://www.channelfireball.com/article/How-Many-Lands-Do-You-Need-in-Your-Deck-An-Updated-Analysis/cd1c1a24-d439-4a8e-b369-b936edb0b38a/).
    - The deck distribution and CMC requirements may occasionally lead to the inclusion of cards with lower performance or are considered less effective.
      - Example: If the user possesses a pool of white and blue cards and the available 3-drops are Acquisition Octopus (53.7% win rate for WU) and Guardians of Oboro (50.7% win rate for WU), the deck suggester will include both of these cards to meet the 3-drop requirement for each deck archetype.
    - The rating is determined by calculating the combined GIHWR of all the cards and then subtracting penalties for not meeting the deck requirements.
    - The NEO creature sagas count as creatures.

  - **Wheel:** The "WHEEL" option shows the percentage likelihood of a specific card in a pack being available the second time you see the pack (on the wheel).
  - The logic in the code already existed, and I do not know if a bug was found and not implemented or if the creator wanted to improve upon it before releasing it.
  - Only the first six-packs are considered, and cards with an ALSA of <2 are automatically excluded.
  - The math appears to follow what Sierkovitz published in this [article](https://mtgazone.com/how-to-wheel-in-drafts/)

## The P1P1 Solution

### The Problem

MTGA_Draft_17Lands, like many other platforms, relies on MTG Arena's detailed logs to function. Pack and pick data is read from these logs to determine what cards to display 17 Lands data for. However, we understand the frustration that MTG Arena does not show the pack data for the very first pack of drafts, which can be a significant drawback.

### The Solution

**This is a configurable setting. `Enable P1P1 OCR` is enabled by default.**

The following solution is for P1P1. After you have selected a card, only Arena logs are used:

- A screenshot is taken when you press the `Refresh` button. **enable the `Save P1P1 Screenshots` setting to store sent images.**
- The application converts the image to a base64 string.
- The string and a list of possible card names are sent to a Google Cloud Function (GCF).
- The GCF uses Google Vision API for Optical Character Recognition (OCR). This API returns all text detected in the image.
- The Google Vision results are compared to the possible card names sent via [TheFuzz](https://github.com/seatgeek/thefuzz).
- All possible matches are P1P1 cards; no data persists locally or via GCF.

### Future Considerations

- For 30 days in June/July 2024, there were 913 requests, less than 1000 free requests each month for Google Cloud Functions. I will monitor Bloomburrow's release, but the feature is currently in no jeopardy of being removed.

## Tier List (API-Based)

MTGA_Draft_17Lands now features integrated support for downloading and using 17Lands tier lists directly within the application. Previously, this functionality required a separate Chrome extension, but it is now built in—no browser extension needed.

### How It Works

- The tool connects to the 17Lands API to download a tier list from a provided URL.
- You can select a tier list during a draft to display card grades as you draft.

### How to Use

1. **Download a Tier List**

- In the application menu, go to `Data > Download Tier List`.
- Enter the 17Lands tier list URL and a label for the tier list.
- The tier list will be saved to the `Tier` folder.

1. **Use Tier Lists in Drafts**

- Make sure you have downloaded the dataset for the event from `Data > Download Dataset`. The dataset is required to identify cards in the Arena log, even if it doesn't contain card data.
- When an event is detected, available tier lists for that set will appear in the column options in the [Settings window](#settings).
- Card ratings from the selected tier list will be shown in the pack table for your current pack.

## Signal Detection (Beta)

This feature attempts to identify "Open Lanes" by analyzing the cards passed to you during the draft.

- **How it works:** The tool scans every pack you see in **Pack 1** and **Pack 3** (when cards are passed from the left). It calculates a "Signal Score" for every card based on its quality (GIHWR) and how late you are seeing it compared to its Average Taken At (ATA).
- **The Logic:** Seeing a high-win-rate card later than it is usually taken generates a positive signal score for that card's color(s).
- **The Table:** The "Signals" table sums up these scores for each of the 5 colors.
  - **High Score:** Indicates the color is flowing freely. A score of **20+** typically suggests a very open lane.
  - **Low Score (or 0):** Indicates the color is being cut by your neighbors.
- **Note:** This feature ignores Pack 2 (passed from the right) to focus on the signals that determine your rewards in Pack 3.
- **Configuration:** You can enable/disable this feature in the Settings menu (`Enable Signals`).

## Dataset Notifications

The application includes notifications to ensure datasets are always up-to-date. These features alert users about missing datasets, prompt downloads for required data, and notify about updates. Notifications can be disabled in the Settings menu.

### No Datasets Found

If no local datasets are detected, a notification will appear prompting the user to download the required datasets. This ensures that the tool has the necessary data to function properly.

<img width="408" height="197" alt="No_datasets" src="https://github.com/user-attachments/assets/2eaee3d7-ce9f-48ae-82c9-01037a76782e" />

**Behavior:**

- A dialog box will appear with the message: "No datasets detected. Would you like to download a dataset now?"
- If the user clicks `Yes`, the **Download Dataset** window will open, allowing the user to download a dataset.

**Tip:** To stop seeing this notification, open the `Settings` menu and uncheck the `Enable Missing Dataset Notifications` option.

---

### Missing Dataset

If a dataset for a detected event is missing, the application will notify the user and provide an option to download the dataset automatically.

<img width="407" height="207" alt="Missing_datasets" src="https://github.com/user-attachments/assets/90466ecf-9e26-41e3-a90e-8eba7a52cfb2" />

**Behavior:**

- A dialog box will appear with the message: "No dataset found for expansion [Set Name]. Would you like to download the dataset now?"
- If the user clicks `Yes`, the application will automatically download the dataset for the missing event.
- This feature is currently limited to Quick Drafts to avoid interfering with timed events such as Premier or Traditional Drafts.

**Tip:** To stop seeing this notification, open the `Settings` menu and uncheck the `Enable Missing Dataset Notifications` option.

---

### Dataset Update Available

Upon startup, the application checks for updates to the most recently used dataset. If an updated version is available, the user will receive a notification and be prompted to download the update.

<img width="400" height="194" alt="image" src="https://github.com/user-attachments/assets/ed5162f5-7779-49d8-9a8e-48dab464def9" />

**Behavior:**

- A dialog box will appear with the message: "New data available for [Set Name]. Would you like to update your dataset?"
- If the user clicks `Yes`, the application will download the updated dataset.
- This feature is rate-limited to once every 24 hours.

**Tip:** To disable update notifications, open the `Settings` menu and uncheck the `Enable Dataset Update Notifications` option.

---

## Troubleshooting

### Known Issues

- **Some cards are missing from the Taken Cards window:** Due to Arena creating a new player log after every restart, the application cannot track cards that were picked and seen prior to a restart. However, players in drafting sessions spanning multiple days or sessions can still use this tool to access the current pack data. It should be noted that this application may not have access to information regarding previous packs and picks, resulting in some missing data.
- **The application can't generate set or debug files:** Windows users might need to run the application as an administrator if the application is installed in a directory with restricted write access.
- **My sealed card pool is missing after restarting Arena:** Arena creates a new player log after every restart, so you will need to open up your sealed event session log by clicking `File->Read Draft Log` and selecting the `DraftLog_<Set>_Sealed` file if you want to see your sealed card pool. Remember that opening a log file will prevent the application from reading the Arena player log. Therefore, you must restart the application if you wish to initiate a new Arena event.
- **The tables are displaying a win rate of 0% or NA:** The application will display a card win rate value of 0% or NA if that win rate field has fewer than 500 samples (e.g., GIHWR will be 0% or NA if the number of games in hand is less than 500). Users should consider using the premier draft dataset or downloading a [tier list using the API-based method](#tier-list-api-based) for events that have a low player count.
  - **\*As of September 2023, the 17Lands endpoint no longer provides win rate data for cards with fewer than 500 samples.**
- **CTRL+G doesn't do anything:** If you're a Mac user, this shortcut isn't available. You must run the application as an administrator if you're a Windows user.
- **The set download process takes 5+ minutes, and I'm seeing _Collecting 17Lands Data - Request Failed_ multiple times:** If you attempt to download too many sets within a short period, 17Lands will impose rate-limiting on your connection. Therefore, when downloading multiple sets, waiting at least 10 minutes between them is advisable.
- **SSL errors in log on MacOS: `ERROR - limited_sets.retrieve_scryfall_sets - <urlopen error [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1000)`** Install SSL certificates via /Applications/Python 3.12/Install Certificates.command
- **The application displays the wrong set when joining an Arena Open or qualifier event:** The log entries for these events do not specify the set, so the application defaults to the latest released set. If the event is not for the latest set, you can open the `Temp/temp_set_list.json` file and replace `"{LATEST}"` with the correct set code, such as `"TDM"` for Tarkir: Dragonstorm

### Arena Log Issues

Arena updates may occasionally modify the log entries that this application reads. If the application cannot detect an active event, or if pack data is missing, please click `File > Open Player.log` and search for the following strings in the log file. If you find entries that contain similar strings, please create a bug report and include the log entry.

#### Premier and Traditional Drafts

- **Event Detection:** `[UnityCrossThreadLogger]==> EventJoin` or `[UnityCrossThreadLogger]==> Event_Join`, `id`, and `EventName`
- **Pack 1, Pick 1:** `CardsInPack`, `id`, `PackNumber`, and `PickNumber`
- **Packs:** `[UnityCrossThreadLogger]Draft.Notify`, `draftId`, `PackCards`, `SelfPack`, and `SelfPick`
- **Picks:** `[UnityCrossThreadLogger]==> EventPlayerDraftMakePick` or `[UnityCrossThreadLogger]==> Event_PlayerDraftMakePick`, `id`, `Pack`, `Pick`, and `GrpIds` or `GrpId`

#### Quick Drafts

- **Event Detection:** `[UnityCrossThreadLogger]==> BotDraftDraftStatus` or `[UnityCrossThreadLogger]==> BotDraft_DraftStatus`, `id`, and `EventName`
- **Packs:** `DraftPack`, `CurrentModule`, `DraftStatus`, `PickNext`, `PackNumber`, `PickNumber`, and `PickedCards`
- **Picks:** `[UnityCrossThreadLogger]==> BotDraftDraftPick` or `[UnityCrossThreadLogger]==> BotDraft_DraftPick`, `PackNumber`, `PickNumber`, and `CardIds` or `CardId`

#### Sealed and Traditional Sealed

- **Event Detection:** `[UnityCrossThreadLogger]==> EventJoin` or `[UnityCrossThreadLogger]==> Event_Join`, `id`, and `EventName`
- **Cardpool:** `InternalEventName`, `CardPool`, and `Courses` or `Course`

## Development

### Environment Setup

1. **Install Python 3.12**
2. **Install Dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

3. **(Windows Build Only) Install Build Tools:**

   ```bash
   pip install pywin32==306 pyinstaller==6.7.0
   ```

### Running Tests

This project uses `pytest` for unit testing.

```bash
python -m pytest tests/
```

### Version Management

To automate updating the version number across `src/constants.py`, `builder/Installer.iss`, and creating a new entry in `release_notes.txt`, use the included script:

- **Patch Bump (+0.01):** `python bump_version.py`
- **Major Bump (+1.0):** `python bump_version.py major`
- **Manual Set:** `python bump_version.py --set 3.50`

### Building the Executable

This project uses a [GitHub Action](https://github.com/unrealities/MTGA_Draft_17Lands/actions/workflows/build-windows-exe.yml) for official builds. To build locally on Windows:

1. **Build EXE:**

   ```bash
   python -m PyInstaller main.spec --clean
   ```

2. **Build Installer:**
   - [Download Inno Setup](https://jrsoftware.org/isdl.php#stable).
   - Open `builder/Installer.iss` with Inno Setup and click **Build -> Compile**.
