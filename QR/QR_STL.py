import qrcode
import numpy as np
import trimesh

def generate_qr_code_stl(data, size_cm, height_cm, base_thickness_cm, base_margin_cm, output_file="qrcode.stl"):
    """
    Génère un QR code en STL avec une taille paramétrable en centimètres et un socle.

    :param data: Données à encoder dans le QR code (string)
    :param size_cm: Taille totale du QR code en centimètres (largeur et hauteur)
    :param height_cm: Hauteur des pixels du QR code en centimètres (relief 3D)
    :param base_thickness_cm: Épaisseur du socle en centimètres
    :param base_margin_cm: Marge autour du QR code pour le socle en centimètres
    :param output_file: Nom du fichier STL à sauvegarder
    """
    # Générer le QR Code
    qr = qrcode.QRCode(
        version=1,  # Taille du QR code
        error_correction=qrcode.constants.ERROR_CORRECT_M,  # Niveau de correction M
        box_size=10,  # Taille initiale des "pixels" (sera redimensionné)
        border=4,  # Bordure (en nombre de cases)
    )
    qr.add_data(data)
    qr.make(fit=True)

    # Récupérer la matrice du QR code
    qr_matrix = qr.modules
    qr_size = len(qr_matrix)  # Taille en nombre de cases (pixels)

    # Calculer la taille d'un pixel en fonction de la taille totale désirée
    pixel_size = size_cm / qr_size

    # Création des cubes pour les cases noires
    meshes = []
    for y, row in enumerate(qr_matrix):
        for x, value in enumerate(row):
            if value:  # Si la case est noire
                cube = trimesh.creation.box(
                    extents=(pixel_size, pixel_size, height_cm),
                    transform=trimesh.transformations.translation_matrix(
                        [
                            x * pixel_size - size_cm / 2 + pixel_size / 2,  # Centrer le QR code sur X
                            -y * pixel_size + size_cm / 2 - pixel_size / 2,  # Centrer le QR code sur Y
                            base_thickness_cm  # Positionner chaque cube sur le socle
                        ]
                    ),
                )
                meshes.append(cube)

    # Création du socle
    base_width = size_cm + 2 * base_margin_cm
    base_height = size_cm + 2 * base_margin_cm
    base = trimesh.creation.box(
        extents=(base_width, base_height, base_thickness_cm),
        transform=trimesh.transformations.translation_matrix(
            [0, 0, 0]  # Le socle est centré sur l'origine
        ),
    )
    meshes.append(base)

    # Combiner toutes les pièces en un seul objet 3D
    qr_mesh = trimesh.util.concatenate(meshes)

    # Sauvegarder en STL
    qr_mesh.export(output_file)
    print(f"QR Code STL avec socle généré et enregistré sous '{output_file}'")



# Informations du réseau WiFi
ssid = "Livebox-9710"  # Remplacez par le nom de votre réseau WiFi
password = "5q2fwJCzTbSHRZad5c"  # Remplacez par votre mot de passe WiFi
encryption = "WPA2"  # Type de cryptage (WPA, WPA2, ou 'nopass' pour les réseaux ouverts)

# Format du contenu pour le QR code WiFi
wifi_config = f"WIFI:T:{encryption};S:{ssid};P:{password};;"
DATA = wifi_config

# Paramètres
#DATA = "https://example.com"  # URL ou texte à encoder
SIZE_CM = 10  # Taille totale du QR code en cm
HEIGHT_CM = 0.5  # Hauteur des pixels (relief) en cm
BASE_THICKNESS_CM = 0.5  # Épaisseur du socle en cm
BASE_MARGIN_CM = 1.0  # Marge autour du QR code pour le socle en cm
OUTPUT_FILE = "qrcode_with_base.stl"  # Nom du fichier STL

# Générer le QR code en STL avec socle
generate_qr_code_stl(DATA, SIZE_CM, HEIGHT_CM, BASE_THICKNESS_CM, BASE_MARGIN_CM, OUTPUT_FILE)
