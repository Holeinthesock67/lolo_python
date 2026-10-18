#https://pypi.org/project/qrcode/

import qrcode
from qrcode.image.svg import SvgImage

# Informations du réseau WiFi
ssid = "SSID"  # Remplacez par le nom de votre réseau WiFi
password = "PASSWORD"  # Remplacez par votre mot de passe WiFi
encryption = "WPA2"  # Type de cryptage (WPA, WPA2, ou 'nopass' pour les réseaux ouverts)

# Format du contenu pour le QR code WiFi
wifi_config = f"WIFI:T:{encryption};S:{ssid};P:{password};;"
data = wifi_config


# Données pour le QR Code
#data = "https://example.com"

# Créer un QR Code
qr = qrcode.QRCode(
    version=1,  # Taille du QR code (1 = plus petit, jusqu'à 40 = très grand)
    error_correction=qrcode.constants.ERROR_CORRECT_M,  #Niveau de correction M = About 15% or less errors can be corrected.
    box_size=10,  # Taille des "pixels" dans le QR code
    border=4,  # Bordure (en nombre de cases)
)
qr.add_data(data)
qr.make(fit=True)

# Générer une image SVG
svg_image = qr.make_image(image_factory=SvgImage)

# Enregistrer dans un fichier .svg
with open("qrcode.svg", "wb") as f:
    svg_image.save(f)

print("QR Code SVG généré et enregistré sous 'qrcode.svg'")
