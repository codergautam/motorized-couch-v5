import tkinter as tk
from ScreenUI import ScreenUI  # Assuming tkinter_ui.py is the file with the ScreenUI class
import time
import random
import threading

def update_ui_periodically(app):
    count = 70
    while True:
        app.update_ui(random.randint(0, 100), random.randint(0, 1000), random.randint(0, 200), random.randint(0, 200), f"Debug info {count}", random.randint(0, 3))
        count += 1
        time.sleep(0.2)  # Update 5 times a second

if __name__ == "__main__":
    print("Starting main program")
    root = tk.Tk()
    app = ScreenUI(root)

    # Use a separate thread to update the UI periodically
    update_thread = threading.Thread(target=update_ui_periodically, args=(app,))
    update_thread.daemon = True  # This will allow the thread to exit when the main program exits
    update_thread.start()

    print("Starting UI")
    root.mainloop()
    print("UI exited")