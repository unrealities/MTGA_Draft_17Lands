# MTGA_Draft_17Lands

Magic: The Gathering Arena draft tool that utilizes 17Lands data.

**This application will automatically support new sets as soon as the sets are released on Arena _and_ the data is available on the [17Lands card ratings](https://www.17lands.com/card_ratings) page.**

**Supported Events:** Premier Draft, Traditional Draft, Quick Draft, Sealed, and Traditional Sealed

## Table of Contents

- [MTGA_Draft_17Lands](#mtga_draft_17lands)
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

## Security, Verification & macOS Gatekeeper

Because this is a free, open-source community project, the application is not signed with a paid Apple Developer Certificate ($100/year). As a result, macOS and Windows SmartScreen will flag the application as an "Unidentified Developer."

To guarantee the integrity of your download, our GitHub Actions pipeline automatically generates a **SHA-256 Checksum** for every release. You can compare the hash of your downloaded file against the `.sha256` file listed on the [Releases page](https://github.com/unrealities/MTGA_Draft_17Lands/releases) to verify it has not been modified.

**Mac Users: Bypassing the "App is Damaged" or "Malware" prompt**
macOS actively quarantines unsigned apps downloaded from the internet. To run the app safely:

1. Open **Terminal** (Command + Space -> "Terminal").
2. Type `xattr -cr ` (make sure to include the space at the end!).
3. Drag and drop the `MTGA_Draft_Tool.app` from your Applications folder directly into the Terminal window.
4. Press **Enter**. You can now double-click the app to open it normally.

---

## Run Steps: Standalone App (Windows / macOS / Linux)

- **Step 1:** Download the latest release for your operating system from the [releases page](https://github.com/unrealities/MTGA_Draft_17Lands/releases).

- **Step 2:** Install/Extract the application:
  - **Windows:** Unzip and double-click the installer executable. _(Run as administrator if installing to restricted folders like Program Files)._
  - **macOS:** Unzip the downloaded file and drag `MTGA_Draft_Tool.app` to your Applications folder. _(See the Security section above if macOS blocks the app from running)_
  - **Linux:** Extract the `.tar.gz` file and run the executable.
- **Step 3:** In Arena, go to Adjust Options, Account, and check the Detailed Logs (Plugin Support) check box.
- **Step 4:** Launch the `MTGA_Draft_Tool` application.
- **Step 5:** Click the **Datasets** tab to download the 17Lands data for the sets you plan to play.
  - _Note: If MTG Arena is installed on a secondary drive/custom folder and dataset downloads fail, click `File -> Locate MTGA Data Folder...` so the app can find your local card database._
- **Step 6:** Configure the tool through `File -> Preferences...`.
- **Step 7:** Start the draft in Arena.

## Run Steps: Python (Windows/Mac/Linux)

- **Step 1:** [Download](https://github.com/unrealities/MTGA_Draft_17Lands/archive/refs/heads/main.zip) and unzip the repository.
- **Step 2:** Download and install Python 3.12.
- **Step 3:** Confirm that you're running Python 3.12 by opening the terminal, entering `python --version`.
- **Step 4:** Install the Python package installer Pip by entering `python -m ensurepip --upgrade`.
- **Step 5:** The app will automatically download the 17Lands data for currently active sets in the background. You can also click the **Datasets** tab to manually download historical sets or custom date ranges.
- **Step 6:**
  - (Mac Only) Install web certificates by going to `/Applications/Python 3.##/` and double-clicking the file `Install Certificates.command`.
  - (Linux only) [Install Tk](https://tkdocs.com/tutorial/install.html#installlinux)
- **Step 7:** In Arena, go to Adjust Options, Account, and then check the Detailed Logs (Plugin Support) check box.
- **Step 8:** Start the application by opening the terminal and entering `python main.py`.
- **Step 9:** If the application asks you for the location of the Arena player log, then click `File -> Read Player.log` and select the log file.
- **Step 10:** Click the **Datasets** tab to download the sets you plan to use.
- **Step 11:** Start the draft in Arena.

## Marquee Features

- **Tactical Advisor ("The Brain"):** A custom formulaic engine that calculates a 0-100 `VALUE` score for cards in your pack. It dynamically weighs raw Z-Score power, color commitment (Alien Gold protection), curve needs, and relative wheel probability to suggest optimal picks. Look for the ⭐ symbol for elite "Bomb" picks. You can also click directly on the suggested card names to view their full tooltips.
- **Right-Click Context Menus:** Right-click on any card in the data tables to instantly send it to the Comparisons tab, copy its name to your clipboard, or view its rulings on Scryfall.
- **Visual Pick Confirmation:** The Live Pack table highlights the specific card you just picked in green, providing instant visual confirmation. The app also keeps the previous pack cleanly displayed on screen until the next one physically arrives, eliminating awkward blank screens between picks.
- **Mini Mode:** Click the `Mini Mode` button to hide the main dashboard and display a compact, draggable, always-on-top window. Perfect for single-monitor setups or playing seamlessly over the Arena client.
- **Dynamic Columns:** You can customize the columns displayed in any table (Pack, Missing, Card Pool, Compare) by **Right-Clicking the column header**. Add specific 17Lands stats or remove ones you don't need. The app remembers your layout.
- **Themes & Mana Flairs:** Under the `Theme` menu, you can select custom "Mana Flairs" (Forest, Island, Swamp, Mountain, Plains, Wastes) or fall back to your Native OS System theme.
- **Automated Cloud Datasets:** The application uses a custom Cloud ETL Pipeline that compiles and distributes the latest 17Lands telemetry every day. When you open the app, it instantly syncs the data for active Arena events in the background, meaning you never have to manually scrape data before a draft again. You can also browse the pipeline schedule and manually download historical datasets directly from our [Data Warehouse website](https://unrealities.github.io/MTGA_Draft_17Lands/).
- **Sealed Studio:** A fully interactive drag-and-drop workspace specifically tailored for Sealed deckbuilding. Automatically generates the top 3 mathematically optimal deck shells for your specific pool.

## UI Navigation & Tabs

The application is structured into a collapsible Live Dashboard and functional tabs:

### Live Dashboard

- **Advisor Recommendations:** Explains the reasoning behind the top 3 cards in the current pack.
- **Live Pack:** Displays the cards currently offered to you.
- **Seen Cards (Wheel Tracker):** Tracks cards you passed previously in the draft.
- **Sidebar:** Contains visual "Open Lane" Signal detection, your current Mana Curve, and your Pool Balance (Creatures/Spells/Lands). You can click on the headers of these panels to collapse them.

### Application Tabs

- **Datasets:** Manage, download, and update 17Lands card data locally. Provides detailed download summaries, including exactly how many MTGA cards were successfully matched with 17Lands telemetry data.
- **Card Pool:** View the cards you have drafted. Features a **"Switch to Visual View"** button to stack your cards into mana curve columns exactly like MTG Arena does.
- **Deck Builder:** A fully interactive deck construction environment. Generates automated baseline archetypes from your pool, which you can then customize via **Drag & Drop** or instant "Quick Clicks". Features a 1-click **Auto-Lands** button, a sleek basics toolbar, and live deck size validation. Jump into the Simulation tab to view detailed stat breakdowns, generate a visual **Sample Hand**, or run the on-demand **AI Auto-Optimizer** to mathematically perfect your 40-card configuration.
- **Comparisons:** Search and add multiple cards to directly compare their stats side-by-side.
- **Tier Lists:** Import and manage custom tier lists from the 17Lands API.

## Settings & Preferences

Access Settings via `File -> Preferences...`

- **Win Rate Format:** Switch the results for win rate fields (GIHWR, OHWR) between a Percentage, a 5-point Rating scale, or Grades (A+ to F).
- **Deck Filter Format:** Switch the Deck Filter dropdown to display either color permutations (e.g., UB, BG) or guild/shard names (e.g., Dimir, Golgari).
- **UI Scale:** Increase or decrease the application text and image sizes globally (from 40% up to 250%). Perfect for smaller laptop displays or massive 4k monitors.
- **Highlight Row by Mana Cost:** Colors the background of table rows based on the card's color identity.
- **Auto-Switch Deck Filter to Best Colors:** When the filter is set to "Auto", the app tracks your picks and will automatically switch to displaying data for your confirmed color pair once your lane is identified.
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

The application features robust crash-recovery and state persistence. If you close the app mid-draft (or MTG Arena crashes), simply reopening the app will instantly resume your draft exactly where you left off.

If the log file ever severely desyncs, click the **Reload** button in the main dashboard. This will wipe the application's current memory, rapidly re-read the entire log file from the beginning, and cleanly reconstruct your draft state.

### Arena Log Issues

If the application cannot detect an active event, click `File -> Read Player.log` and ensure the proper file is selected.

### Custom Installation Folders (Unable to access local Arena Data)

If MTG Arena is installed in a non-standard directory (e.g., a secondary Steam library drive), the application might fail to automatically locate the local MTGA card database, causing dataset downloads to fail. To fix this, click `File -> Locate MTGA Data Folder...` in the top menu bar and select your custom `MTGA_Data` folder.

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
   ```

### Running Tests

This project uses `pytest` for unit testing.

```bash
python -m pytest tests/
```

### Automated Releases & Version Management

This project uses a fully automated CI/CD pipeline via GitHub Actions. Creating a new public release is entirely frictionless.

The pipeline triggers **automatically whenever code is merged into the `master` branch.** It reads the version number from `src/constants.py`, generates the git tag, builds the macOS/Linux/Windows executables, and publishes them to the Releases page.

**The Workflow:**

1. On your feature branch, run the bump script:
   - **Patch Bump (+0.01):** `python bump_version.py`
   - **Major Bump (+1.0):** `python bump_version.py major`
   - **Manual Set:** `python bump_version.py --set 4.50`
2. The script will update your config files and ask: `Would you like to automatically commit and push these changes to your branch? (y/N)`
3. Type `y` and press **Enter**.
4. Go to GitHub and merge your Pull Request into `master`. The release will build and publish automatically.

_(Note: If you merge code into master without bumping the version number, the pipeline will simply rebuild and update the executables on the existing release—perfect for hotfixes)_

### Building Locally

If you need to test builds locally on your own machine instead of using GitHub Actions:

- **macOS/Linux:** `python -m PyInstaller main.spec --clean`
- **Windows:** Compile `main.spec` with PyInstaller, then open `builder/Installer.iss` with [Inno Setup](https://jrsoftware.org/isdl.php#stable) and click **Build -> Compile**.
