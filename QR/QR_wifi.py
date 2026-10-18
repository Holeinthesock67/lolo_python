import qrcode

# Informations du réseau WiFi
# Informations du réseau WiFi
ssid = "SSID"  # Remplacez par le nom de votre réseau WiFi
password = "PASSWORD"  # Remplacez par votre mot de passe WiFi
encryption = "WPA2"  # Type de cryptage (WPA, WPA2, ou 'nopass' pour les réseaux ouverts)

# Format du contenu pour le QR code WiFi
wifi_config = f"WIFI:T:{encryption};S:{ssid};P:{password};;"

# Générer le QR code
qr = qrcode.QRCode(
    version=1,  # Taille du QR code
    error_correction=qrcode.constants.ERROR_CORRECT_L,  # Correction d'erreur
    box_size=10,  # Taille des pixels
    border=4,  # Bordure
)
qr.add_data(wifi_config)
qr.make(fit=True)

# Sauvegarder le QR code en image
img = qr.make_image(fill_color="black", back_color="white")
img.save("wifi_qrcode.png")

print("QR code WiFi généré et enregistré sous 'wifi_qrcode.png'")
