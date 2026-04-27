from tkinter import *
import sys, json
import os
import atexit
from datetime import datetime
import requests
import ui.main_window
import traceback


def _runtime_diag_enabled():
    value = os.environ.get('SECUREWIPE_RUNTIME_DIAG', '').strip().lower()
    return value in ('1', 'true', 'yes', 'on')


def _runtime_log_path():
    try:
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_dir, 'securewipe_runtime.log')
    except Exception:
        return os.path.join(os.getcwd(), 'securewipe_runtime.log')


def runtime_log(event, **fields):
    if not _runtime_diag_enabled():
        return
    try:
        ts = datetime.now().isoformat(timespec='seconds')
        safe_fields = []
        for key, value in fields.items():
            safe_value = str(value).replace('\n', '\\n').replace('\r', '\\r')
            safe_fields.append(f"{key}={safe_value}")
        line = f"{ts} | loginUI | pid={os.getpid()} | event={event}"
        if safe_fields:
            line += " | " + " | ".join(safe_fields)
        with open(_runtime_log_path(), 'a', encoding='utf-8') as log_file:
            log_file.write(line + "\n")
    except Exception:
        pass


def _register_runtime_exit_logging():
    if not _runtime_diag_enabled():
        return

    def _on_exit():
        runtime_log('process_exit')

    atexit.register(_on_exit)


_register_runtime_exit_logging()

# Temporary local key map for backend-bypass testing.
LOCAL_PRODUCT_KEYS = {
    "SWIPE-LOCAL-2026-7F3D2A9B": {
        "license_holder": "Test Operator",
        "company": "Lab Recovery Systems",
        "plan": "Internal QA",
        "issued_on": "2026-03-16",
    }
}

def get_userDetails():
    try:
        product_key = prod_key_entry.get().strip()
        runtime_log('submit_clicked', key_length=len(product_key))
        if not product_key:
            l1.config(text="❌ Please enter a product key.", fg="red")
            return

        local_key_details = LOCAL_PRODUCT_KEYS.get(product_key)
        if local_key_details:
            print(f"Local product key accepted: {local_key_details}")
            runtime_log('local_key_accepted')
            root.destroy()  # Close the login window
            runtime_log('launch_securewipe_ui', source='local_key')
            ui.main_window.start_ui(product_key)
            return
            
        url = f"https://secure-wipe-2gyy.onrender.com/api/key/key-verify/{product_key}"
        try:
            # Send GET request
            response = requests.get(url, timeout=10)
            print(response)
            runtime_log('key_verification_response', status_code=response.status_code)
            if response.json().get("valid"):
                runtime_log('remote_key_accepted')
                root.destroy()  # Close the login window
                runtime_log('launch_securewipe_ui', source='remote_key')
                ui.main_window.start_ui(product_key)
            else:
                runtime_log('remote_key_rejected')
                l1.config(text="❌ Invalid Email or Product Key. Try again.", fg="red")
                prod_key_entry.delete(0, END)  # Clear the entry field

        except requests.exceptions.RequestException as e:
            runtime_log('network_error', error=e)
            l1.config(text="❌ Network error. Please try again later.", fg="red")
        except json.JSONDecodeError as e:
            runtime_log('json_decode_error', error=e)
            l1.config(text="❌ Invalid response from server. Please try again.", fg="red")
        except Exception as e:
            runtime_log('unexpected_get_user_details_error', error=e)
            l1.config(text="❌ An unexpected error occurred. Please try again.", fg="red")
            print(f"Unexpected error in get_userDetails: {e}")
            traceback.print_exc()
    except Exception as e:
        runtime_log('critical_get_user_details_error', error=e)
        print(f"Critical error in get_userDetails: {e}")
        traceback.print_exc()
        l1.config(text="❌ A critical error occurred. Please restart the application.", fg="red")


# ---------------- Validation Function ----------------
def validate_inputs(*args):
    try:
        product_key = prod_key_entry.get().strip()
        
        # Product key length check
        is_valid_key = 8 < len(product_key) < 50

        # Enable button only if both valid
        if is_valid_key:
            submit_btn.config(state=NORMAL, bg="green", fg="white")
        else:
            submit_btn.config(state=DISABLED, bg="grey", fg="black")
    except Exception as e:
        print(f"Error in validate_inputs: {e}")
        traceback.print_exc()


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

try:
    runtime_log('tk_root_create_begin')
    root = Tk()
    root.title("Secure Wipe - Login")
    root.geometry("930x600")
    root.resizable(False, False)
    root.configure(bg="white") 

    mainFrame = Frame(root, bg="#72787C", height=540)
    mainFrame.pack(padx=20, fill=BOTH, pady=20)
    mainFrame.pack_propagate(False)
    runtime_log('tk_root_create_success')
except Exception as e:
    runtime_log('tk_root_create_error', error=e)
    print(f"Error initializing main window: {e}")
    traceback.print_exc()
    sys.exit(1)


def on_login_window_close():
    runtime_log('login_window_close_request')
    root.destroy()


root.protocol("WM_DELETE_WINDOW", on_login_window_close)


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


l1 = Label(loginFrame, text="***   enter valid Product Key.   ***", fg="yellow", bg="#777B7E", font=("Arial", 10))
l1.grid(row=3, column=1, columnspan=3, pady=5)

# Submit Button
submit_btn = Button( loginFrame, text="Submit", font=("Arial", 14, "bold"), bg="#272A29", fg="black", 
                    activebackground="#00CC66", activeforeground="white", relief="groove", 
                    bd=3, padx=25, pady=10, cursor="hand2", highlightthickness=0, state=DISABLED, 
                    command=get_userDetails)
submit_btn.grid(row=4, column=1, padx=10, pady=10)

def main():
    """Main entry point with proper exception handling"""
    try:
        runtime_log('login_mainloop_enter')
        root.mainloop()
        runtime_log('login_mainloop_return')
    except Exception as e:
        runtime_log('login_mainloop_error', error=e)
        print(f"Error in main loop: {e}")
        traceback.print_exc()
    finally:
        try:
            runtime_log('login_mainloop_finally_destroy')
            root.destroy()
        except:
            pass

if __name__ == "__main__":
    try:
        runtime_log('login_program_start')
        main()
    except Exception as e:
        runtime_log('login_program_critical_error', error=e)
        print(f"Critical error in main: {e}")
        traceback.print_exc()
        try:
            import tkinter.messagebox as mb
            mb.showerror("Critical Error", f"Application failed to start: {e}")
        except:
            pass
