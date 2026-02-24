# MTGA_Draft_17Lands

Magic: The Gathering Arena draft tool that utilizes 17Lands data.

**This application will automatically support new sets as soon as the sets are released on Arena _and_ the data is available on the [17Lands card ratings](https://www.17lands.com/card_ratings) page.**

**Supported Events:** Premier Draft, Traditional Draft, Quick Draft, Sealed, and Traditional Sealed

## Table of Contents

- [MTGA\_Draft\_17Lands](#mtga_draft_17lands)
  - [Table of Contents](#table-of-contents)
  - [Run Steps: Windows Executable (Windows Only)](#run-steps-windows-executable-windows-only)
  - [Run Steps: Python (Windows/Mac/Linux)](#run-steps-python-windowsmaclinux)
  - [Marquee Features](#marquee-features)
  - [UI Navigation \& Tabs](#ui-navigation--tabs)
    - [Live Dashboard](#live-dashboard)
    - [Application Tabs](#application-tabs)
  - [Settings \& Preferences](#settings--preferences)
  - [File Locations](#file-locations)
    - [Configuration (`config.json`)](#configuration-configjson)
    - [Datasets \& Logs](#datasets--logs)
  - [The P1P1 Solution](#the-p1p1-solution)
    - [The Problem](#the-problem)
    - [The Solution](#the-solution)
  - [Tier List (API-Based)](#tier-list-api-based)
  - [Signal Detection (Beta)](#signal-detection-beta)
  - [Dataset Notifications](#dataset-notifications)
  - [Troubleshooting](#troubleshooting)
    - [Known Issues](#known-issues)
    - [Desyncs & Missed Picks](#desyncs--missed-picks)
    - [Arena Log Issues](#arena-log-issues)
  - [Development \& Documentation](#development--documentation)
    - [Environment Setup](#environment-setup)
    - [Version Management](#version-management)
    - [Building the Executable](#building-the-executable)

## Run Steps: Windows Executable (Windows Only)

- **Step 1:** Download the latest zip file from the [releases page](https://github.com/unrealities/MTGA_Draft_17Lands/releases).
- **Step 2:** Unzip and double-click the exe file to start the installation.
- **Step 3:** (Optional) Go to the installed folder and right-click the executable (`MTGA_Draft_Tool.exe`), click properties, compatibility tab, and check "Run this program as an administrator."
  - This step is only required if the application is installed in a directory with write restrictions (i.e., `Program Files` and `Program Files (x86)`).
- **Step 4:** In Arena, go to Adjust Options, Account, and then check the Detailed Logs (Plugin Support) check box.
- **Step 5:** Double-click `MTGA_Draft_Tool.exe` to start the program.
- **Step 6:** Click the **Datasets** tab to download the sets you plan to use.
- **Step 7:** Configure the tool through `File -> Preferences...`.
- **Step 8:** Start the draft in Arena.
  - The Arena log doesn't list P1P1 for premier and traditional drafts until after P1P2. Pressing the `P1P1` button will help OCR identify the cards in your first pack.

## Run Steps: Python (Windows/Mac/Linux)

- **Step 1:** [Download](https://github.com/unrealities/MTGA_Draft_17Lands/archive/refs/heads/main.zip) and unzip the repository.
- **Step 2:** Download and install Python 3.12.
- **Step 3:** Confirm that you're running Python 3.12 by opening the terminal, entering `python --version`.
- **Step 4:** Install the Python package installer Pip by entering `python -m ensurepip --upgrade`.
- **Step 5:** Open the terminal and install the Python dependencies by entering `pip install -r requirements.txt`.
- **Step 6:**
  - (Mac Only) Install web certificates by going to `/Applications/Python 3.##/` and double-clicking the file `Install Certificates.command`.
  - (Linux only) [Install Tk](https://tkdocs.com/tutorial/install.html#installlinux)
- **Step 7:** In Arena, go to Adjust Options, Account, and then check the Detailed Logs (Plugin Support) check box.
- **Step 8:** Start the application by opening the terminal and entering `python main.py`.
- **Step 9:** If the application asks you for the location of the Arena player log, then click `File -> Read Player.log` and select the log file.
- **Step 10:** Click the **Datasets** tab to download the sets you plan to use.
- **Step 11:** Start the draft in Arena.

## Marquee Features

- **Tactical Advisor ("The Brain"):** A custom formulaic engine that calculates a 0-100 `VALUE` score for cards in your pack. It dynamically weighs raw Z-Score power, color commitment (Alien Gold protection), curve needs, and relative wheel probability to suggest optimal picks. Look for the ⭐ symbol for elite "Bomb" picks.
- **Overlay Mode:** Click the `Overlay Mode` button to hide the main dashboard and display a compact, draggable, always-on-top window. Perfect for single-monitor setups or playing seamlessly over the Arena client.
- **Dynamic Columns:** You can customize the columns displayed in any table (Pack, Missing, Card Pool, Compare) by **Right-Clicking the column header**. Add specific 17Lands stats or remove ones you don't need. The app remembers your layout.
- **Themes & Mana Flairs:** Under the `Theme` menu, you can select custom "Mana Flairs" (Forest, Island, Swamp, Mountain, Plains, Wastes) or fall back to your Native OS System theme.
- **Card Tooltips:** Clicking on any card row will display a tooltip containing the card images (back and front), detailed 17Lands data, and archetype breakdown.

## UI Navigation & Tabs

The application is structured into a collapsible Live Dashboard and functional tabs:

### Live Dashboard

- **Advisor Recommendations:** Explains the reasoning behind the top 3 cards in the current pack.
- **Live Pack:** Displays the cards currently offered to you.
- **Seen Cards (Wheel Tracker):** Tracks cards you passed previously in the draft.
- **Sidebar:** Contains visual "Open Lane" Signal detection, your current Mana Curve, and your Pool Balance (Creatures/Spells/Lands). You can click on the headers of these panels to collapse them.

### Application Tabs

- **Datasets:** Manage, download, and update 17Lands card data locally.
- **Card Pool:** View the cards you have drafted. Features a **"Switch to Visual View"** button to stack your cards into mana curve columns exactly like MTG Arena does.
- **Deck Builder:** Generates multiple deck variants (Midrange, Aggro, Bomb Splash) from your drafted pool, utilizing Frank Karsten's mana base math. Allows you to copy the deck to your clipboard.
- **Comparisons:** Search and add multiple cards to directly compare their stats side-by-side.
- **Tier Lists:** Import and manage custom tier lists from the 17Lands API.

## Settings & Preferences

Access Settings via `File -> Preferences...`

- **Win Rate Format:** Switch the results for win rate fields (GIHWR, OHWR) between a Percentage, a 5-point Rating scale, or Grades (A+ to F).
- **Deck Filter Format:** Switch the Deck Filter dropdown to display either color permutations (e.g., UB, BG) or guild/shard names (e.g., Dimir, Golgari).
- **UI Scale:** Increase or decrease the application text and image sizes globally.
- **Highlight Row by Mana Cost:** Colors the background of table rows based on the card's color identity.
- **Auto-Switch Deck Filter to Best Colors:** When the filter is set to "Auto", the app tracks your picks and will automatically switch to displaying data for your confirmed color pair once your lane is identified.
- **Enable P1P1 OCR:** Enables [The P1P1 Solution](#the-p1p1-solution). Turning this off removes the `P1P1` button from the UI.
- **Save P1P1 Screenshots:** Saves the image taken during P1P1 OCR locally to `./Screenshots` for troubleshooting.
- **Check for Dataset Updates:** Prompts you if a newer version of your currently loaded 17Lands dataset is available (checked once every 24 hours).
- **Alert on Missing Datasets:** Automatically prompts you to open the Dataset manager if you join a draft event that you don't have data downloaded for.
- **Enable Draft Log Creation:** Records the draft step-by-step in a readable log file within the `./Logs` folder.

## File Locations

The application stores your settings and data in specific locations to ensure they persist across updates.

### Configuration (`config.json`)

The application looks for the configuration file in the following order:

1. **Local Folder:** If `config.json` exists in the same folder as the application, it is used (Portable Mode).
2. **System User Folder:**
   - **Windows:** `%APPDATA%\MTGA_Draft_Tool\config.json`
   - **Mac:** `~/Library/Application Support/MTGA_Draft_Tool/config.json`
   - **Linux:** `~/.config/MTGA_Draft_Tool/config.json`

### Datasets & Logs

- Downloaded card data is stored in the `Sets` folder.
- Custom Tier lists are stored in the `Tier` folder.
- Application debug logs are stored in the `Debug` folder, and draft logs are in the `Logs` folder.

## The P1P1 Solution

### The Problem

MTG Arena does not show the pack data in the log files for the very first pack of Premier and Traditional drafts until after you have made your pick.

### The Solution

- Click the `P1P1` button in the top menu when you see your first pack.
- A screenshot is taken and converted to a base64 string.
- The string and a list of possible card names are sent to a Google Cloud Function (GCF) for OCR.
- All possible matches are returned as P1P1 cards, populating your UI instantly; no data persists locally or via GCF unless you explicitly enable `Save P1P1 Screenshots`.

## Tier List (API-Based)

MTGA_Draft_17Lands features integrated support for downloading and using 17Lands tier lists directly within the application.

1. Go to the **Tier Lists** tab in the application.
2. Enter the 17Lands tier list URL and a custom label, then click Download.
3. Once downloaded, **Right-Click** the header of any table (like the Live Pack table), go to `Add Column`, and select your new tier list!

## Signal Detection (Beta)

This feature attempts to identify "Open Lanes" by analyzing the cards passed to you during the draft.

- **How it works:** The tool scans every pack you see in **Pack 1** and **Pack 3**. It calculates a "Signal Score" for every card based on its quality (GIHWR) and how late you are seeing it compared to its Average Taken At (ATA).
- **The Table:** The "Open Lanes" bar chart in the sidebar sums up these scores. A High Score (20+) typically suggests a very open lane, meaning your neighbors are not drafting that color.

## Dataset Notifications

The application includes notifications to ensure datasets are always up-to-date. These features alert users about missing datasets and prompt downloads. You can disable them via the Settings menu.

## Troubleshooting

### Known Issues

- **SSL errors on MacOS:** Install SSL certificates via `/Applications/Python 3.12/Install Certificates.command`
- **Missing cards after restarting Arena:** Arena creates a new log after every restart. The application cannot track cards picked prior to an Arena restart.

### Desyncs & Missed Picks
If you disconnect from MTG Arena, or the application misses a pick, click the **Reload** button in the main dashboard. This will wipe the application's current memory, instantly re-read the entire log file from the beginning, and reconstruct your exact draft state.

### Arena Log Issues

If the application cannot detect an active event, click `File -> Read Player.log` and ensure the proper file is selected.

## Development & Documentation

For developers looking to contribute, fork, or understand the architecture of this application, please refer to the markdown specifications located in the `/docs` directory of this repository:

- `00-system-overview.md`
- `01-domain-models.md`
- `02-log-parsing-rules.md`
- `03-business-logic.md`
- `04-external-integrations.md`

### Environment Setup

1. **Install Python 3.12**
2. **Install Dependencies:**

   ```bash
   pip install -r requirements.txt

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
