import time
import os

# Put an old, complete Player.log from a previous draft in a folder named 'test_logs'
SOURCE_LOG = "test_logs/Player_Old_Draft.log"
TARGET_LOG = "Player.log"


def simulate_draft():
    print("Starting Draft Simulator... Open the MTGA Draft Tool!")

    with open(TARGET_LOG, "w") as f:
        f.write("MTG Arena Simulator Started\n")

    time.sleep(2)

    with open(SOURCE_LOG, "r") as source:
        with open(TARGET_LOG, "a") as target:
            for line in source:
                # Only copy lines that your app actually cares about to speed it up
                if any(
                    keyword in line
                    for keyword in [
                        "Event_Join",
                        "CardsInPack",
                        "Draft.Notify",
                        "Event_PlayerDraftMakePick",
                        "BotDraft",
                    ]
                ):
                    print(f"Sending Event -> {line[:60]}...")
                    target.write(line)
                    target.flush()  # Force OS to write so your app sees it

                    # Pause for 3 seconds between actions so you can watch the UI update
                    time.sleep(3)


if __name__ == "__main__":
    simulate_draft()
