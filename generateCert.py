from tkinter import *
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from textwrap import wrap
from datetime import datetime
import qrcode
from PIL import Image, ImageTk
import os
from tkinter import filedialog, messagebox

TODAY = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
# Certificate data (demo)   ----> In real use, populate dynamically from Secure wipeUI after wipe
cert_id = "54d978a9-caf2-4e80-8e73-9014eb2542c0"
device_model = "USB DISK 2.0 USB Device"
device_SNO = "9F09080590B0"
wipe_method = "DoD 5220.22-M (3-pass)"
wipe_timestamp = TODAY
digital_signature = "sha256:abc2cd3e98f67890123456789002345678900abcdef1234567890abcdef123456"


def generate_qr_code():
    """Generate QR code containing certificate data as JSON"""
    cert_data = {
        "cert_id": cert_id,
        "device_model": device_model,
        "device_SNO": device_SNO,
        "wipe_method": wipe_method,
        "wipe_timestamp": wipe_timestamp,
        "digital_signature": digital_signature,
        "issuer": "Secure Wipe - The Firmware",
        "certificate_type": "Data Wiping Certificate"
    }
    
    """Generate a QR code from the given data (string) and save as an image file."""
    qr = qrcode.QRCode(
        version=1,  # auto size if None
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(cert_data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    return img



def generate_pdf():
    file_path = filedialog.asksaveasfilename(
        title="Save Certificate As",
        defaultextension=".pdf",
        initialfile=f"Demo_Certificate({cert_id}).pdf",
        filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
    )
    if not file_path:  # if user cancels
        return
    
    # Custom page size
    custom_pagesize = (595.2755905511812, 741.8897637795277)
    c = canvas.Canvas(file_path, pagesize=custom_pagesize)
    width, height = custom_pagesize

    # Border (like Tkinter canvas border)
    c.setLineWidth(2)
    c.rect(30, 30, width - 60, height - 60)

    # Header
    c.setFont("Times-Bold", 24)
    c.drawCentredString(width / 2, height - 80, "Secure Wipe - The Firmware")

    # Separator line
    c.setLineWidth(2)
    c.line(50, height - 95, width - 50, height - 95)

    # Title
    c.setFont("Helvetica", 20)
    c.drawCentredString(width / 2, height - 130, "Certificate of Data destruction")

    # Subtitle (2 lines)
    c.setFont("Helvetica", 11)
    c.drawCentredString(width / 2, height - 165,
                        "This certifies that the data on the following device has been securely")
    c.drawCentredString(width / 2, height - 185,
                        "and permanently wiped.")

    # Certificate details (match Tkinter layout)
    left_x = 60
    right_x = width / 2 + 30

    # Certificate ID
    c.setFont("Helvetica-Bold", 10)
    c.drawString(left_x, height - 230, "Certificate ID")
    c.setFont("Helvetica", 12)
    c.drawString(left_x, height - 245, cert_id)

    # Device info
    c.setFont("Helvetica-Bold", 10)
    c.drawString(left_x, height - 270, "Device Model")
    c.setFont("Helvetica", 12)
    c.drawString(left_x, height - 285, f"{device_model}(SNO. - {device_SNO})")

    # Wipe Method
    c.setFont("Helvetica-Bold", 10)
    c.drawString(left_x, height - 310, "Wipe Method")
    c.setFont("Helvetica", 12)
    c.drawString(left_x, height - 325, wipe_method)

    # Timestamp
    c.setFont("Helvetica-Bold", 10)
    c.drawString(right_x, height - 310, "Timestamp")
    c.setFont("Helvetica", 12)
    c.drawString(right_x, height - 325, wipe_timestamp)

    # Digital signature section
    c.setFont("Helvetica-Bold", 10)
    c.drawString(left_x, height - 360, "Digital Signature")
    c.setFont("Helvetica", 8)

    max_text_width = int((width - 2 * left_x) / 6)  # wrap text like Tkinter width=500
    for i, line in enumerate(wrap(digital_signature, max_text_width)):
        c.drawString(left_x, height - 375 - (i * 12), line)

    # QR code centered
    qr_img = generate_qr_code()
    qr_img.save("temp_qr.png")
    qr_w, qr_h = 200, 200
    c.drawImage("temp_qr.png", (width - qr_w) / 2, 160, width=qr_w, height=qr_h,
                preserveAspectRatio=True, mask='auto')

    c.setFont("Helvetica-Oblique", 9)
    c.drawCentredString(width / 2, 150, "(Scan QR code for certificate data)")

    # Footer
    c.setFont("Helvetica-Oblique", 9)
    c.drawCentredString(width / 2, 100, "This is a system-generated certificate")

    c.save()

    if os.path.exists("temp_qr.png"):
        os.remove("temp_qr.png")


# ---------------- Tkinter UI ----------------
root = Tk()
root.title("Certificate Preview")
root.geometry("600x750")

# Canvas to preview certificate
cert_canvas = Canvas(root, width=550, height=670, bg="#CBCCCE", highlightthickness=2, highlightbackground="black")
cert_canvas.pack(pady=20)

# Draw border
cert_canvas.create_rectangle(10, 10, 540, 650, width=2)

# Header
cert_canvas.create_text(275, 60, text="Secure Wipe - The Firmware", font=("Times-Roman", 24, "bold"))

# Separator line
cert_canvas.create_line(30, 93, 530, 93, width=2)

# Title
cert_canvas.create_text(275, 120, text="Certificate of Data destruction", font=("Helvetica", 20))

# Subtitle
cert_canvas.create_text(275, 155, text="This certifies that the data on the following device has been securely ", font=("Arial", 11))
cert_canvas.create_text(275, 175, text="and permanently wiped.", font=("Arial", 11))


# Certificate details in 2x2 grid
#------------------------------------------------------------------------

# Top row
cert_canvas.create_text(40, 210, text="Certificate ID", font=("Arial", 10, "bold"), anchor="w")
cert_canvas.create_text(40, 228, text=cert_id, font=("Arial", 12), anchor="w")

cert_canvas.create_text(40, 250, text="Device info", font=("Arial", 10, "bold"), anchor="w")
cert_canvas.create_text(40, 268, text=f"{device_model} (SNO. - {device_SNO})", font=("Arial", 12), anchor="w")

# Bottom row
cert_canvas.create_text(40, 290, text="Wipe Method", font=("Arial", 10, "bold"), anchor="w")
cert_canvas.create_text(40, 308, text=wipe_method, font=("Arial", 12), anchor="w")

cert_canvas.create_text(300, 290, text="Timestamp", font=("Arial", 10, "bold"), anchor="w")
cert_canvas.create_text(300, 308, text=wipe_timestamp, font=("Arial", 12), anchor="w")

# Digital Signature (spans full width below grid)
cert_canvas.create_text(40, 335, text="Digital Signature", font=("Arial", 10, "bold"), anchor="w")
cert_canvas.create_text(40, 353, text=digital_signature, font=("Arial", 8), width=500, anchor="w")


#------------------------------------------------------------------------

# Generate and display QR code in the UI
def display_qr_code():
    """Display QR code on the canvas"""
    qr_img = generate_qr_code()
    
    # Resize QR code for display
    qr_img = qr_img.resize((200, 200), Image.Resampling.LANCZOS)
    
    # Convert to PhotoImage for tkinter
    qr_photo = ImageTk.PhotoImage(qr_img)
    
    # Store reference to prevent garbage collection
    cert_canvas.qr_photo = qr_photo
    
    # Display QR code on canvas
    cert_canvas.create_image(275, 480, image=qr_photo)
    
    # Add QR code label
    cert_canvas.create_text(275, 590, text="(Scan QR code for certificate data)", font=("Arial", 9, "italic"))

# Display the QR code
display_qr_code()

#------------------------------------------------------------------------

# Footer moved down to accommodate new content
cert_canvas.create_text(275, 630, text="This is a system-generated certificate", font=("Helvetica", 9, "italic"))

# Generate PDF Button
Button(root, text="Download PDF", command=generate_pdf).pack(pady=0)

root.mainloop()
