from tkinter import *
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from datetime import datetime
import qrcode
import json
from PIL import Image, ImageTk
import io

TODAY = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
# Certificate data (demo)   ----> In real use, populate dynamically from dwipeUI after wipe
cert_id = "CERT-4646"
device_name = "LAPTOP-DEV-001"
wipe_method = "DoD 5220.22-M (3-pass)"
wipe_timestamp = TODAY
digital_signature = "sha256:abc2cd3e98f67890123456789002345678900abcdef1234567890abcdef123456"


def generate_qr_code():
    """Generate QR code containing certificate data as JSON"""
    cert_data = {
        "cert_id": cert_id,
        "device_name": device_name,
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
    file_name = f"Demo_Certificate({cert_id}).pdf"
    c = canvas.Canvas(file_name, pagesize=A4)
    width, height = A4

    # Border (match UI look)
    c.setLineWidth(2)
    c.rect(20, 20, width - 40, height - 40)

    # Header
    c.setFont("Times-Roman", 24)
    c.drawCentredString(width / 2, height - 60, "Secure Wipe - The Firmware")
    c.setLineWidth(2)
    c.line(40, height - 75, width - 40, height - 75)

    # Title
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(width / 2, height - 110, "Certificate of Data destruction")

    # Subtitle (two lines like UI)
    c.setFont("Helvetica", 11)
    c.drawCentredString(width / 2, height - 135, "This certifies that the data on the following device has been securely")
    c.drawCentredString(width / 2, height - 152, "and permanently wiped.")

    # Details grid (2x2)
    left_x = 70
    right_x = width / 2 + 10
    row1_y_label = height - 210
    row1_y_value = height - 225
    row2_y_label = height - 260
    row2_y_value = height - 275

    c.setFont("Helvetica-Bold", 10)
    c.drawString(left_x, row1_y_label, "Certificate ID")
    c.drawString(right_x, row1_y_label, "Device Name")
    c.drawString(left_x, row2_y_label, "Wipe Method")
    c.drawString(right_x, row2_y_label, "Timestamp")

    c.setFont("Helvetica", 12)
    c.drawString(left_x, row1_y_value, cert_id)
    c.drawString(right_x, row1_y_value, device_name)
    c.drawString(left_x, row2_y_value, wipe_method)
    c.drawString(right_x, row2_y_value, wipe_timestamp)

    # Digital signature
    sig_label_y = height - 330
    sig_value_y = height - 345
    c.setFont("Helvetica-Bold", 10)
    c.drawString(left_x, sig_label_y, "Digital Signature")
    c.setFont("Helvetica", 8)
    # Wrap signature across the printable width
    from textwrap import wrap
    max_text_width = int((width - 2 * left_x) / 6)  # approximate char width
    for i, line in enumerate(wrap(digital_signature, max_text_width)):
        c.drawString(left_x, sig_value_y - (i * 12), line)

    # QR code centered near bottom
    qr_img = generate_qr_code()
    qr_img.save("temp_qr.png")
    qr_w = 120
    qr_h = 120
    c.drawImage("temp_qr.png", (width - qr_w) / 2, 80, width=qr_w, height=qr_h, preserveAspectRatio=True, mask='auto')
    c.setFont("Helvetica-Oblique", 9)
    c.drawCentredString(width / 2, 70, "Scan QR code for certificate data")

    # Footer
    c.setFont("Helvetica-Oblique", 10)
    c.drawCentredString(width / 2, 50, "This is a system-generated certificate")

    c.save()
    print(f"✅ Certificate saved as {file_name}")
    
    # Clean up temporary QR code file
    import os
    if os.path.exists("temp_qr.png"):
        os.remove("temp_qr.png")

# ---------------- Tkinter UI ----------------
root = Tk()
root.title("Certificate Preview")
root.geometry("600x750")

# Canvas to preview certificate
cert_canvas = Canvas(root, width=550, height=670, bg="white", highlightthickness=2, highlightbackground="black")
cert_canvas.pack(pady=20)

# Draw border
cert_canvas.create_rectangle(10, 10, 540, 650, width=2)

# Header
cert_canvas.create_text(275, 40, text="Secure Wipe - The Firmware", font=("Times New Roman", 24, "bold"))

# Separator line
cert_canvas.create_line(30, 63, 530, 63, width=2)

# Title
cert_canvas.create_text(275, 90, text="Certificate of Data destruction", font=("Georgia", 20))

# Subtitle
cert_canvas.create_text(275, 125, text="This certifies that the data on the following device has been securely ", font=("Arial", 11))
cert_canvas.create_text(275, 145, text="and permanently wiped.", font=("Arial", 11))


# Certificate details in 2x2 grid
#------------------------------------------------------------------------

# Top row
cert_canvas.create_text(40, 200, text="Certificate ID", font=("Arial", 10, "bold"), anchor="w")
cert_canvas.create_text(40, 215, text=cert_id, font=("Arial", 12), anchor="w")

cert_canvas.create_text(300, 200, text="Device Name", font=("Arial", 10, "bold"), anchor="w")
cert_canvas.create_text(300, 215, text=device_name, font=("Arial", 12), anchor="w")

# Bottom row
cert_canvas.create_text(40, 280, text="Wipe Method", font=("Arial", 10, "bold"), anchor="w")
cert_canvas.create_text(40, 295, text=wipe_method, font=("Arial", 12), anchor="w")

cert_canvas.create_text(300, 280, text="Timestamp", font=("Arial", 10, "bold"), anchor="w")
cert_canvas.create_text(300, 295, text=wipe_timestamp, font=("Arial", 12), anchor="w")

# Digital Signature (spans full width below grid)
cert_canvas.create_text(40, 360, text="Digital Signature", font=("Arial", 10, "bold"), anchor="w")
cert_canvas.create_text(40, 375, text=digital_signature, font=("Arial", 8), width=500, anchor="w")


#------------------------------------------------------------------------

# # Generate and display QR code in the UI
# def display_qr_code():
#     """Display QR code on the canvas"""
#     qr_img = generate_qr_code()
    
#     # Resize QR code for display
#     qr_img = qr_img.resize((120, 120), Image.Resampling.LANCZOS)
    
#     # Convert to PhotoImage for tkinter
#     qr_photo = ImageTk.PhotoImage(qr_img)
    
#     # Store reference to prevent garbage collection
#     cert_canvas.qr_photo = qr_photo
    
#     # Display QR code on canvas
#     cert_canvas.create_image(275, 480, image=qr_photo)
    
#     # Add QR code label
#     cert_canvas.create_text(275, 550, text="Scan QR code for certificate data", font=("Arial", 9, "italic"))

# # Display the QR code
# display_qr_code()

#------------------------------------------------------------------------

# Footer moved down to accommodate new content
cert_canvas.create_text(275, 620, text="This is a system-generated certificate", font=("Helvetica", 9, "italic"))

# Generate PDF Button
Button(root, text="Generate PDF", command=generate_pdf).pack(pady=0)

root.mainloop()
