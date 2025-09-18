from tkinter import *
import subprocess
import sys, json
import requests

def get_userDetails():
    product_key = prod_key_entry.get().strip()
    url = f"https://secure-wipe-2gyy.onrender.com/api/key/key-verify/{product_key}"
    try:
    # Send GET request
        response = requests.get(url, timeout=10)
        print(response)
        if response.json().get("valid"):
            root.destroy()  # Close the login window
            process = subprocess.Popen([sys.executable, "securewipeUI.py", "--product_key", product_key])
            process.wait()
        else:
            l1.config(text="❌ Invalid Email or Product Key. Try again.", fg="red")
            prod_key_entry.delete(0, END)  # Clear the entry field

    except requests.exceptions.RequestException as e:
        l1.config(text="❌ Network error. Please try again later.", fg="red")


# ---------------- Validation Function ----------------
def validate_inputs(*args):
    product_key = prod_key_entry.get().strip()
    
    # Product key length check
    is_valid_key = 8 < len(product_key) < 50

    # Enable button only if both valid
    if is_valid_key:
        submit_btn.config(state=NORMAL, bg="green", fg="white")
    else:
        submit_btn.config(state=DISABLED, bg="grey", fg="black")


BANNER = [
    "███████╗ ███████╗  ██████╗ ██╗   ██╗ ██████╗   ███████╗",
    "██╔════╝ ██╔════╝ ██╔════╝ ██║   ██║ ██╔══██╗  ██╔════╝",
    "███████╗ █████╗   ██║      ██║   ██║ ██████╔╝  █████╗  ",
    "╚════██║ ██╔══╝   ██║      ██║   ██║ ██╔══██╗  ██╔══╝  ",
    "███████║ ███████╗ ╚██████╗ ╚██████╔╝ ██║   ██║ ███████╗",
    "╚══════╝ ╚══════╝  ╚═════╝  ╚═════╝  ╚═╝   ╚═╝ ╚══════╝",
    "▒▒▒▒▒▒▒▒▒ S E C U R E    W I P E    L o g i n ▒▒▒▒▒▒▒▒▒",
    "  ██╗    ██╗ ██╗ ██████╗  ███████╗",
    "  ██║    ██║ ██║ ██╔══██╗ ██╔════╝",
    "  ██║ █╗ ██║ ██║ ██████╔╝ █████╗  ",
    "  ██║███╗██║ ██║ ██╔═══╝  ██╔══╝  ",
    "  ╚███╔███╔╝ ██║ ██║      ███████╗",
    "   ╚══╝╚══╝  ╚═╝ ╚═╝      ╚══════╝",
]

root = Tk()
root.title("Secure Wipe - Login")
root.geometry("930x600")
root.resizable(False, False)
root.configure(bg="white") 

mainFrame = Frame(root, bg="#72787C", height=540)
mainFrame.pack(padx=20, fill=BOTH, pady=20)
mainFrame.pack_propagate(False)


# Configure grid
mainFrame.grid_rowconfigure(0, weight=0)
mainFrame.grid_rowconfigure(1, weight=0)
mainFrame.grid_columnconfigure(0, weight=1)

# === Banner Frame (row 0) ===
bannerFrame = Frame(mainFrame, bg="#72787C", height=280)
bannerFrame.grid(row=0, column=0, sticky="nsew", pady=40, padx=20)
bannerFrame.grid_propagate(False)

text_widget = Text(
    bannerFrame,
    font=("Courier", 14, "bold"),
    bg="#72787C",
    fg="#44D837",
    bd=0,
    height=len(BANNER),
    width=80
)
text_widget.grid(row=0, column=0)

# Insert banner centered
text_widget.tag_configure("center", justify="center")
for line in BANNER:
    text_widget.insert(END, line + "\n", "center")
text_widget.config(state=DISABLED)

# === Login Frame (row 1) ===
loginFrame = Frame(mainFrame, bg="#72787C")
loginFrame.grid(row=1, column=0, sticky="ew", pady=15, padx=50)
loginFrame.grid_columnconfigure(1, weight=1)

# Product Key Label and Entry
Prod_key_label = Label(loginFrame, text="Product Key :", bg="#777B7E", fg="black", font=("Arial", 12))
Prod_key_label.grid(row=2, column=0, padx=10, pady=15, sticky="w")

prod_key_entry = Entry(loginFrame, font=("Arial", 12), width=30, bg="white", fg="black", show="*")
prod_key_entry.grid(row=2, column=1, padx=5, pady=15, sticky="ew")
prod_key_entry.bind("<KeyRelease>", validate_inputs)


l1 = Label(loginFrame, text="*** enter valid Email id and Product Key. ***", fg="yellow", bg="#777B7E", font=("Arial", 10))
l1.grid(row=3, column=1, columnspan=3, pady=5)

# Submit Button
submit_btn = Button( loginFrame, text="Submit", font=("Arial", 14, "bold"), bg="#272A29", fg="black", 
                    activebackground="#00CC66", activeforeground="white", relief="groove", 
                    bd=3, padx=25, pady=10, cursor="hand2", highlightthickness=0, state=DISABLED, 
                    command=get_userDetails)
submit_btn.grid(row=4, column=1, padx=10, pady=10)

root.mainloop()
