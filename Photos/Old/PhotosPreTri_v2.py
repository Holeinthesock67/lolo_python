#!/usr/bin/env python3
import os
import shutil
import time  # 1. Ajout de time pour la pause
from datetime import datetime
from PIL import Image, ExifTags
from geopy.geocoders import Nominatim
import sys

# 2. Déplacement de la gestion de l'import d'erreur en haut du fichier pour éviter les plantages
try:
    from PIL import UnidentifiedImageError
except ImportError:
    # Pour compatibilité avec d'anciennes versions de Pillow
    class UnidentifiedImageError(Exception):
        pass

def convert_to_degrees(value): # Correction typo: degress -> degrees
    """
    Convertit les coordonnées GPS stockées au format rationnel en degrés décimaux.
    Si les éléments sont des tuples (numérateur, dénominateur), on les convertit en float.
    Sinon, on tente une conversion directe.
    """
    # Si le premier élément est un tuple, on suppose que chaque valeur est du type (num, den)
    if isinstance(value[0], tuple):
        d = value[0][0] / value[0][1]
        m = value[1][0] / value[1][1]
        s = value[2][0] / value[2][1]
    else:
        # Gestion si les valeurs ne sont pas des tuples (parfois juste des entiers/flottants)
        # S'assurer qu'il y a bien 3 éléments pour degrés, minutes, secondes
        if len(value) == 3:
            d = float(value[0])
            m = float(value[1])
            s = float(value[2])
        else:
            # Gérer le cas où le format n'est pas celui attendu
            print(f"Attention: Format GPS inattendu pour la valeur: {value}")
            return 0.0
            
    return d + (m / 60.0) + (s / 3600.0)

def extract_metadata(file_path):
    """
    Extrait la date de prise de vue et, si possible, la localisation depuis les métadonnées EXIF.
    Pour les vidéos ou en cas d'absence de métadonnées, on utilise la date de création du fichier.
    Si aucune donnée de géolocalisation n'est trouvée, le champ lieu sera une chaîne vide.
    """
    metadata = {}
    ext = os.path.splitext(file_path)[1].lower()
    image_extensions = ['.jpg', '.jpeg', '.png', '.tiff', '.heic']
    
    if ext in image_extensions:
        try:
            image = Image.open(file_path)
            # Tenter de lire les données EXIF
            exif_data = image._getexif()

            if exif_data is not None:
                exif = {ExifTags.TAGS.get(tag, tag): value for tag, value in exif_data.items()}

                # Extraction de la date (Prioriser DateTimeOriginal)
                date_str = exif.get("DateTimeOriginal") or exif.get("DateTime")
                if date_str:
                    try:
                        if '.' in date_str:
                            date_obj = datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S.%f")
                        else:
                            date_obj = datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
                        metadata["date"] = date_obj
                    except ValueError:
                        print(f"Avertissement: Format de date inattendu '{date_str}' pour {os.path.basename(file_path)}. Utilisation de la date de modification du fichier.")
                        metadata["date"] = datetime.fromtimestamp(os.path.getmtime(file_path))


                # Extraction de la localisation via les données GPS
                gps_info_raw = exif.get("GPSInfo")
                if gps_info_raw:
                    gps_data = {ExifTags.GPSTAGS.get(key, key): gps_info_raw[key] for key in gps_info_raw.keys()}
                    
                    lat_data = gps_data.get("GPSLatitude")
                    lat_ref = gps_data.get("GPSLatitudeRef")
                    lon_data = gps_data.get("GPSLongitude")
                    lon_ref = gps_data.get("GPSLongitudeRef")

                    if lat_data and lat_ref and lon_data and lon_ref:
                        try:
                            lat = convert_to_degrees(lat_data)
                            if lat_ref != "N":
                                lat = -lat
                            lon = convert_to_degrees(lon_data)
                            if lon_ref != "E":
                                lon = -lon
                            
                            # Reverse géocodage pour obtenir un nom de lieu
                            geolocator = Nominatim(user_agent="photo_organizer_script_v2_safe")
                            try:
                                # 3. PAUSE AJOUTÉE ICI
                                # Nominatim demande max 1 requête par seconde. On met 1.1s pour être sûr.
                                print(f"Pause de 1.1s avant géolocalisation pour {os.path.basename(file_path)}...")
                                time.sleep(1.1)

                                location = geolocator.reverse((lat, lon), language="fr", timeout=20, addressdetails=True) 
                                if location and location.raw and "address" in location.raw:
                                    address = location.raw["address"]
                                    lieu_orig = (address.get("city") or
                                            address.get("town") or
                                            address.get("village") or
                                            address.get("municipality") or
                                            address.get("county") or
                                            address.get("state"))
                                    if lieu_orig:
                                        s = lieu_orig.replace('-', '_').replace(' ', '_')
                                        s_cleaned = "".join(char for char in s if char.isalnum() or char == '_')
                                        s_normalized = '_'.join(filter(None, s_cleaned.split('_')))
                                        
                                        if s_normalized:
                                            metadata["lieu"] = s_normalized.capitalize()
                                        else:
                                            metadata["lieu"] = ""
                                    else:
                                        print(f"Info: Aucun nom de lieu pertinent trouvé pour les coordonnées ({lat:.5f}, {lon:.5f})")
                                else:
                                    print(f"Info: Adresse non trouvée pour {os.path.basename(file_path)}")

                            except Exception as e:
                                print(f"Erreur de géolocalisation pour {os.path.basename(file_path)}: {e}")
                        except ValueError as ve:
                            print(f"Erreur de conversion GPS pour {os.path.basename(file_path)}: {ve}")
                        except Exception as e_conv:
                             print(f"Erreur inattendue lors du traitement GPS pour {os.path.basename(file_path)}: {e_conv}")

            if "date" not in metadata:
                metadata["date"] = datetime.fromtimestamp(os.path.getmtime(file_path))

        except FileNotFoundError:
            print(f"Erreur: Le fichier {file_path} n'a pas été trouvé.")
            return None
        except UnidentifiedImageError:
            print(f"Erreur: Impossible d'identifier l'image {os.path.basename(file_path)}.")
            metadata["date"] = datetime.fromtimestamp(os.path.getmtime(file_path))
            metadata.setdefault("lieu", "")
            return metadata
        except Exception as e:
            print(f"Erreur générale pour {os.path.basename(file_path)}: {e}. Utilisation de la date de modification.")
            metadata["date"] = datetime.fromtimestamp(os.path.getmtime(file_path))

    else:
        try:
            metadata["date"] = datetime.fromtimestamp(os.path.getmtime(file_path))
        except FileNotFoundError:
            print(f"Erreur: Le fichier {file_path} n'a pas été trouvé.")
            return None

    metadata.setdefault("lieu", "")
    if "date" not in metadata:
        metadata["date"] = datetime.now() 
        print(f"Avertissement: Date inconnue pour {os.path.basename(file_path)}, utilisation de la date actuelle.")

    return metadata

def generate_filename(date_obj, lieu, original_filename, counter=None):
    """
    Génère le nom de fichier au format AAAAMMJJ_HHMMSS[_Lieu][_SUFFIXE].
    """
    date_str = date_obj.strftime("%Y%m%d_%H%M%S") 
    base_name = date_str

    if lieu:
        base_name += f"_{lieu}" 

    if counter is not None:
        base_name += f"_{counter:02d}"

    return base_name

def organize_file(file_path, dest_dir):
    """
    Organise un fichier en créant la hiérarchie de dossiers.
    """
    print(f"Traitement de : {os.path.basename(file_path)}")
    metadata = extract_metadata(file_path)
    
    if metadata is None:
        return None 
            
    date_obj = metadata["date"]
    lieu = metadata["lieu"]
    year = date_obj.strftime("%Y")
    month = date_obj.strftime("%m")
    
    folder_year = os.path.join(dest_dir, year)
    folder_month_base_name = f"{year}_{month}"
    folder_month_path = os.path.join(folder_year, folder_month_base_name)
    
    if lieu:
        final_subfolder_name = f"{folder_month_base_name}_{lieu}"
        folder_target = os.path.join(folder_month_path, final_subfolder_name)
    else:
        folder_target = folder_month_path

    try:
        os.makedirs(folder_target, exist_ok=True)
    except OSError as e:
        print(f"Erreur critique: Impossible de créer le dossier {folder_target}: {e}")
        return None

    original_filename = os.path.basename(file_path)
    extension = os.path.splitext(original_filename)[1].lower()
    
    if not extension.startswith('.'):
        extension = '.' + extension

    filename_base = generate_filename(date_obj, lieu, original_filename)
    new_file_path = os.path.join(folder_target, filename_base + extension)
    
    counter = 1
    initial_filename_attempt = filename_base 
    while os.path.exists(new_file_path):
        filename_with_counter = generate_filename(date_obj, lieu, original_filename, counter)
        new_file_path = os.path.join(folder_target, filename_with_counter + extension)
        counter += 1
        if counter > 99:
            print(f"Avertissement: Trop de doublons pour {initial_filename_attempt}. Arrêt.")
            return None

    try:
        shutil.copy2(file_path, new_file_path)
        print(f"Copié {os.path.basename(file_path)} vers {os.path.relpath(new_file_path, dest_dir)}")
        return new_file_path
    except Exception as e:
        print(f"Erreur copy2: {e}")
        try:
            shutil.copy(file_path, new_file_path)
            print(f"Copié (fallback) {os.path.basename(file_path)}")
            return new_file_path
        except Exception as e2:
            print(f"Échec total copie pour {os.path.basename(file_path)}: {e2}")
            return None

def main():
    print("--- Organisateur de Photos et Vidéos (Version avec Pause GPS) ---")

    while True:
        source_dir = input("Dossier source: ")
        if os.path.isdir(source_dir):
            print(f"Source: {source_dir}")
            break
        else:
            print("Dossier invalide.")

    while True:
        dest_dir = input("Dossier destination: ")
        if not dest_dir.strip():
            continue

        parent_dest = os.path.dirname(os.path.abspath(dest_dir))
        if not os.path.isdir(parent_dest):
            print(f"Erreur: Dossier parent '{parent_dest}' inexistant.")
        else:
            if not os.path.exists(dest_dir):
                create_conf = input(f"Créer '{dest_dir}'? (o/n): ").lower()
                if create_conf == 'o':
                    try:
                        os.makedirs(dest_dir, exist_ok=True)
                        break
                    except OSError:
                        print("Erreur création dossier.")
                else:
                    print("Annulé.")
            elif os.path.isdir(dest_dir):
                break
            else:
                print("Le chemin existe mais n'est pas un dossier.")
                
    print("\nDébut du tri...")
    processed_count = 0
    copied_count = 0
    error_count = 0
    
    for root, dirs, files in os.walk(source_dir):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        files = [f for f in files if not f.startswith('.')]

        for file in files:
            file_path = os.path.join(root, file)
            if os.path.isfile(file_path):
                processed_count += 1
                try:
                    result_path = organize_file(file_path, dest_dir) 
                    if result_path:
                        copied_count += 1
                    else:
                        error_count += 1
                except Exception as e:
                    print(f"Erreur majeure: {e}")
                    error_count += 1
            else:
                print(f"Ignoré (non fichier): {file_path}")

    print("\n=== Rapport Final ===")
    print(f"Trouvés: {processed_count}")
    print(f"Copiés: {copied_count}")
    print(f"Erreurs/Non copiés: {error_count}")
    print("Terminé.")

if __name__ == "__main__":
    main()
