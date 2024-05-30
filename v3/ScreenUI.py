import tkinter as tk
import random
import os
os.environ['DISPLAY'] = ':0'

class ScreenUI:
    def __init__(self, root):
        self.root = root
        root.attributes('-fullscreen', True)
        self.root.title("Screen UI")
        self.root.geometry("800x480")
        self.root.configure(bg='white')  # Set the background color of the window to white
        
        # Vertical line in the center
        self.center_line = tk.Canvas(root, width=4, height=480, bg='black', highlightthickness=0, bd=0)
        self.center_line.place(x=398, y=0)
        
        # Large text box in the top right half with the text "69"
        self.text_box = tk.Text(root, wrap=tk.WORD, font=('Helvetica', 100), bg='white', fg='black', bd=0, highlightthickness=0)
        self.text_box.place(x=0, y=0, width=398, height=240)
        self.text_box.tag_configure("center", justify='center')
        self.text_box.insert(tk.END, "69\n", "center")
        
        # Small text "MPH" under "69"
        self.mph_label = tk.Label(root, text="MPH", font=('Helvetica', 20), bg='white', fg='black')
        self.mph_label.place(x=0, y=140)  # Adjust x and y to position correctly under "69"
        root.update_idletasks()
        width = self.mph_label.winfo_width()    
        self.mph_label.place(x=200 - (width / 2), y=120)

        # Left side lines
        self.left_power_border = tk.Canvas(root, width=4, height=200, bg='lightgrey', highlightthickness=0, bd=0)
        self.left_power_border.place(x=20, y=140)
        self.left_power_green = tk.Canvas(root, width=4, height=20, bg='green', highlightthickness=0, bd=0)
        self.left_power_green.place(x=20, y=180)
        
        self.right_power_border = tk.Canvas(root, width=4, height=200, bg='lightgrey', highlightthickness=0, bd=0)
        self.right_power_border.place(x=374, y=140)
        self.right_power_green = tk.Canvas(root, width=4, height=20, bg='green', highlightthickness=0, bd=0)
        self.right_power_green.place(x=374, y=180)
        
        # Small text "ODO: 420 miles" at the bottom of the left half, centered
        self.odo_label = tk.Label(root, text="ODO: 420 miles", font=('Helvetica', 20), bg='white', fg='black')
        self.odo_label.place(x=100, y=440)  # Adjust x and y to center it in the bottom left half

        # Call the update function every 200 milliseconds (5 times per second)
        # self.update_ui()

        #Debug info
        self.debug_label = tk.Label(root, text="Debug info", font=('Helvetica', 20), bg='white', fg='black')
        self.debug_label.place(x=400, y=0)
        self.debug_info = tk.Label(root, text="Debug info", font=('Helvetica', 20), bg='white', fg='black')
        self.debug_info.place(x=400, y=40)

    def update_ui(self, speed, odo, left_power, right_power, debug_info): 
        # Generate random values for demonstration
        self.text_box.delete("1.0", tk.END)
        self.text_box.insert(tk.END, str(speed) + "\n", "center")

        self.left_power_green.place(height=left_power, y = 260 - left_power) # fixes the top, changes the bottom
        self.right_power_green.place(height=right_power, y = 260 - right_power)

        self.odo_label.config(text="ODO: " + str(odo) + " miles")

        self.debug_info.config(text=debug_info)

if __name__ == "__main__":
    root = tk.Tk()
    app = ScreenUI(root)
    root.mainloop()
