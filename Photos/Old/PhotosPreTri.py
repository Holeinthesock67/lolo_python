#!/usr/bin/env python3
import os
import shutil
from datetime import datetime
from PIL import Image, ExifTags
from geopy.geocoders import Nominatim
import sys # Import sys to exit if directories are invalid

# C:\Users\laure\lolo_python\Photos> python organisateur.py

def convert_to_degress(value):
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
            # Retourner 0 ou lever une exception selon la robustesse souhaitée
            # Ici, on retourne 0 pour éviter un crash, mais un log serait mieux
            print(f"Attention: Format GPS inattendu pour la valeur: {value}")
            return 0.0 # Ou lever ValueError("Format GPS inattendu")
            
    return d + (m / 60.0) + (s / 3600.0)

def extract_metadata(file_path):
    """
    Extrait la date de prise de vue et, si possible, la localisation depuis les métadonnées EXIF.
    Pour les vidéos ou en cas d'absence de métadonnées, on utilise la date de création du fichier.
    Si aucune donnée de géolocalisation n'est trouvée, le champ lieu sera une chaîne vide.
    """
    metadata = {}
    ext = os.path.splitext(file_path)[1].lower()
    image_extensions = ['.jpg', '.jpeg', '.png', '.tiff', '.heic'] # Ajout d'extensions communes
    
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
                        # Gérer les formats de date variés, y compris ceux avec des sous-secondes
                        if '.' in date_str: # Format avec sous-secondes potentiel
                            date_obj = datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S.%f")
                        else:
                            date_obj = datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
                        metadata["date"] = date_obj
                    except ValueError:
                        print(f"Avertissement: Format de date inattendu '{date_str}' pour {os.path.basename(file_path)}. Utilisation de la date de modification du fichier.")
                        # En cas d'échec du parsing, on se rabat sur la date de modification
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
                            lat = convert_to_degress(lat_data)
                            if lat_ref != "N":
                                lat = -lat
                            lon = convert_to_degress(lon_data)
                            if lon_ref != "E":
                                lon = -lon
                            
                            # Reverse géocodage pour obtenir un nom de lieu
                            geolocator = Nominatim(user_agent="photo_organizer_script_v2") # User agent mis à jour
                            try:
                                # Augmentation du timeout, ajout de addressdetails
                                location = geolocator.reverse((lat, lon), language="fr", timeout=20, addressdetails=True) 
                                if location and location.raw and "address" in location.raw:
                                    address = location.raw["address"]
                                    # Recherche plus large du lieu: ville, village, commune, comté, état
                                    lieu_orig = (address.get("city") or
                                            address.get("town") or
                                            address.get("village") or
                                            address.get("municipality") or # Ajout Commune
                                            address.get("county") or
                                            address.get("state"))
                                    if lieu_orig:
                                        # NOUVELLE LOGIQUE DE FORMATAGE DU LIEU
                                        # 1. Remplacer les tirets et les espaces par des underscores
                                        s = lieu_orig.replace('-', '_').replace(' ', '_')
                                        # 2. Garder uniquement les caractères alphanumériques et les underscores
                                        s_cleaned = "".join(char for char in s if char.isalnum() or char == '_')
                                        # 3. Normaliser les underscores multiples (ex: "Ville___Quartier" -> "Ville_Quartier")
                                        s_normalized = '_'.join(filter(None, s_cleaned.split('_')))
                                        
                                        if s_normalized:
                                            # 4. Mettre la première lettre en majuscule et le reste en minuscule
                                            metadata["lieu"] = s_normalized.capitalize()
                                        else:
                                            metadata["lieu"] = "" # Si le lieu devient vide après nettoyage
                                    else:
                                        # Si aucun des champs d'adresse n'est trouvé pour former 'lieu_orig'
                                        print(f"Info: Aucun nom de lieu pertinent (ville, village, etc.) trouvé dans l'adresse pour les coordonnées ({lat:.5f}, {lon:.5f}) de {os.path.basename(file_path)}")
                                else:
                                    # Si location.raw ou location.raw["address"] n'existe pas
                                    print(f"Info: Adresse non trouvée (structure de réponse inattendue du géocodeur) pour {os.path.basename(file_path)}")

                            except Exception as e:
                                print(f"Erreur de géolocalisation pour {os.path.basename(file_path)} ({lat:.5f}, {lon:.5f}): {e}")
                        except ValueError as ve:
                            print(f"Erreur de conversion GPS pour {os.path.basename(file_path)}: {ve}")
                        except Exception as e_conv: # Renommé pour éviter conflit avec 'e' de la géolocalisation
                             print(f"Erreur inattendue lors du traitement GPS pour {os.path.basename(file_path)}: {e_conv}")

            # Si aucune date EXIF n'est trouvée ou n'a pu être lue, utiliser la date de modification du fichier
            if "date" not in metadata:
                metadata["date"] = datetime.fromtimestamp(os.path.getmtime(file_path))

        except FileNotFoundError:
            print(f"Erreur: Le fichier {file_path} n'a pas été trouvé.")
            return None # Retourner None pour indiquer une erreur
        except UnidentifiedImageError: # Gérer explicitement les fichiers non images ou corrompus
            print(f"Erreur: Impossible d'identifier ou d'ouvrir le fichier image {os.path.basename(file_path)}. Il est peut-être corrompu ou n'est pas une image.")
            # Utiliser la date de modification comme fallback pour les fichiers non-images ou corrompus
            metadata["date"] = datetime.fromtimestamp(os.path.getmtime(file_path))
            metadata.setdefault("lieu", "") # S'assurer que 'lieu' existe
            return metadata # Renvoyer les métadonnées minimales
        except Exception as e:
            # Log l'erreur pour le débogage mais essayer de continuer avec la date de modification
            print(f"Erreur générale lors de l'extraction des métadonnées pour {os.path.basename(file_path)}: {e}. Utilisation de la date de modification.")
            metadata["date"] = datetime.fromtimestamp(os.path.getmtime(file_path))

    else:
        # Pour les vidéos ou autres formats non supportés, utiliser la date de modification
        try:
            metadata["date"] = datetime.fromtimestamp(os.path.getmtime(file_path))
        except FileNotFoundError:
            print(f"Erreur: Le fichier {file_path} n'a pas été trouvé.")
            return None

    # Si la localisation n'a pas été déterminée, initialiser à chaîne vide
    metadata.setdefault("lieu", "")
    # Assurer qu'une date est toujours présente
    if "date" not in metadata:
        # Fallback ultime si même getmtime échoue (très improbable)
        metadata["date"] = datetime.now() 
        print(f"Avertissement: Impossible de déterminer une date pour {os.path.basename(file_path)}, utilisation de la date actuelle.")

    return metadata

def generate_filename(date_obj, lieu, original_filename, counter=None):
    """
    Génère le nom de fichier au format AAAAMMJJ_HHMMSS[_Lieu][_SUFFIXE].
    Si le champ lieu est vide, il n'est pas ajouté.
    En cas de doublon, un suffixe numérique _XX est ajouté.
    """
    # MODIFIÉ: Remplacer le tiret par un underscore dans le format de la date
    date_str = date_obj.strftime("%Y%m%d_%H%M%S") 
    base_name = date_str

    # MODIFIÉ: 'lieu' est maintenant déjà formaté (Capitalized_With_Underscores)
    # Pas besoin de .upper() ni de nettoyage supplémentaire ici.
    if lieu: # lieu est déjà Capitalized et utilise des underscores
        base_name += f"_{lieu}" 

    if counter is not None:
        base_name += f"_{counter:02d}" # Utiliser underscore pour le compteur

    return base_name

def organize_file(file_path, dest_dir):
    """
    Organise un fichier en créant la hiérarchie suivante sous le dossier de destination :
      - Niveau 1 : dossier AAAA (année)
      - Niveau 2 : dossier AAAA_MM (année_mois)
      - Niveau 3 (peut inclure le lieu si disponible) : dossier AAAA_MM_Lieu
    Le fichier est copié (avec ses métadonnées) dans le dossier cible approprié.
    Retourne le chemin du fichier copié ou None si échec.
    """
    print(f"Traitement de : {os.path.basename(file_path)}") # Log fichier en cours
    metadata = extract_metadata(file_path)
    
    # Si extract_metadata retourne None (erreur fichier non trouvé), on arrête pour ce fichier
    if metadata is None:
        return None 
            
    date_obj = metadata["date"]
    lieu = metadata["lieu"] # 'lieu' est maintenant déjà formaté (Ex: Paris_centre, New_york)
    year = date_obj.strftime("%Y")
    month = date_obj.strftime("%m")
    
    # Création de la hiérarchie de dossiers de base Année/Mois
    folder_year = os.path.join(dest_dir, year)
    
    # MODIFIÉ: Nom du dossier mois avec underscore
    folder_month_base_name = f"{year}_{month}" # Ex: 2023_05
    folder_month_path = os.path.join(folder_year, folder_month_base_name) # Ex: DEST_DIR/2023/2023_05
    
    # MODIFIÉ: Déterminer le dossier cible final avec le nouveau formatage
    # Le lieu est déjà formaté (Capitalized_Avec_Underscores)
    if lieu:
        # Le nom du dossier de destination inclura le nom de base du dossier mois et le lieu
        # Ex: AAAA_MM_Lieu (Lieu étant déjà formaté: Premiere_lettre_majuscule_le_reste_minuscule)
        final_subfolder_name = f"{folder_month_base_name}_{lieu}" # Ex: 2023_05_Paris_centre
        folder_target = os.path.join(folder_month_path, final_subfolder_name) # Ex: DEST_DIR/2023/2023_05/2023_05_Paris_centre
    else:
        # Si pas de lieu, les photos vont directement dans AAAA_MM
        folder_target = folder_month_path

    # Créer les dossiers s'ils n'existent pas
    try:
        os.makedirs(folder_target, exist_ok=True)
    except OSError as e:
        print(f"Erreur critique: Impossible de créer le dossier {folder_target}: {e}")
        return None # Arrêter si on ne peut pas créer le dossier

    # Génération du nouveau nom de fichier
    original_filename = os.path.basename(file_path)
    extension = os.path.splitext(original_filename)[1].lower()
    
    # S'assurer que l'extension commence par un point
    if not extension.startswith('.'):
        extension = '.' + extension

    # generate_filename utilise maintenant le lieu formaté et les underscores pour la date
    filename_base = generate_filename(date_obj, lieu, original_filename)
    new_file_path = os.path.join(folder_target, filename_base + extension)
    
    # Gestion des doublons en ajoutant un suffixe numérique
    counter = 1
    # Le nom de fichier de base (sans compteur) pour le message d'avertissement
    initial_filename_attempt = filename_base 
    while os.path.exists(new_file_path):
        # generate_filename utilise le lieu formaté
        filename_with_counter = generate_filename(date_obj, lieu, original_filename, counter)
        new_file_path = os.path.join(folder_target, filename_with_counter + extension)
        counter += 1
        if counter > 99: # Limite pour éviter boucle infinie
            print(f"Avertissement: Trop de fichiers avec le même nom de base pour {initial_filename_attempt} dans {folder_target}. Arrêt de la tentative.")
            return None # Éviter boucle infinie

    # Copier le fichier (copy2 permet de conserver les métadonnées si possible)
    try:
        shutil.copy2(file_path, new_file_path)
        print(f"Copié {os.path.basename(file_path)} vers {os.path.relpath(new_file_path, dest_dir)}")
        return new_file_path # Retourne le chemin du fichier copié
    except Exception as e:
        print(f"Erreur lors de la copie de {os.path.basename(file_path)} vers {new_file_path}: {e}")
        # Essayer copy au lieu de copy2 si copy2 échoue (peut arriver avec certains systèmes de fichiers/permissions)
        try:
            shutil.copy(file_path, new_file_path)
            print(f"Copié (sans métadonnées) {os.path.basename(file_path)} vers {os.path.relpath(new_file_path, dest_dir)}")
            return new_file_path
        except Exception as e2:
            print(f"Échec de la copie simple également pour {os.path.basename(file_path)}: {e2}")
            return None # Retourne None si la copie échoue

def main():
    print("--- Organisateur de Photos et Vidéos ---")

    # Boucle pour demander un dossier source valide
    while True:
        source_dir = input("Entrez le chemin complet du dossier source à trier: ")
        if os.path.isdir(source_dir):
            print(f"Dossier source trouvé: {source_dir}")
            break
        else:
            print(f"Erreur: Le dossier source '{source_dir}' n'existe pas ou n'est pas un dossier valide. Veuillez réessayer.")

    # Boucle pour demander un dossier destination (peut être créé)
    while True:
        dest_dir = input("Entrez le chemin complet du dossier de destination pour les photos triées: ")
        if not dest_dir.strip(): # Vérifie si l'entrée est vide ou juste des espaces
            print("Erreur: Le chemin du dossier de destination ne peut pas être vide. Veuillez entrer un chemin valide.")
            continue

        # Vérifier si le chemin parent existe pour pouvoir créer le dossier final
        parent_dest = os.path.dirname(os.path.abspath(dest_dir)) # os.path.abspath pour gérer chemins relatifs
        if not os.path.isdir(parent_dest):
            print(f"Erreur: Le dossier parent '{parent_dest}' pour la destination n'existe pas. Veuillez créer les dossiers parents nécessaires ou choisir un autre emplacement.")
        else:
            # Si le dossier destination n'existe pas, demander confirmation pour le créer
            if not os.path.exists(dest_dir):
                create_conf = input(f"Le dossier destination '{dest_dir}' n'existe pas. Voulez-vous le créer? (o/n): ").lower()
                if create_conf == 'o':
                    try:
                        os.makedirs(dest_dir, exist_ok=True) # exist_ok=True au cas où il serait créé entre temps
                        print(f"Dossier destination créé: {dest_dir}")
                        break
                    except OSError as e:
                        print(f"Erreur: Impossible de créer le dossier destination '{dest_dir}': {e}. Vérifiez les permissions.")
                else:
                    print("Création annulée. Veuillez entrer un autre chemin de destination.")
            # Si le dossier existe déjà et est bien un dossier
            elif os.path.isdir(dest_dir):
                print(f"Dossier destination trouvé: {dest_dir}")
                break
            # Si le chemin existe mais n'est pas un dossier (c'est un fichier)
            else:
                print(f"Erreur: Le chemin de destination '{dest_dir}' existe déjà mais n'est pas un dossier. Veuillez choisir un autre nom.")
                
    # --- Début du traitement ---
    print("\nDébut du tri...")
    processed_count = 0
    copied_count = 0
    error_count = 0
    
    # Parcours récursif des fichiers dans le dossier source
    for root, dirs, files in os.walk(source_dir):
        # Ignorer les dossiers cachés (commençant par '.') s'il y en a
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        files = [f for f in files if not f.startswith('.')] # Ignorer fichiers cachés

        for file in files:
            file_path = os.path.join(root, file)
            # Vérifier si c'est bien un fichier (évite les liens symboliques cassés etc.)
            if os.path.isfile(file_path):
                processed_count += 1
                try:
                    # organize_file retourne le chemin si succès, None si échec
                    result_path = organize_file(file_path, dest_dir) 
                    if result_path:
                        copied_count += 1
                    else:
                        error_count += 1 # Compter comme erreur si la copie a échoué
                except Exception as e:
                    # Capture les erreurs inattendues dans organize_file lui-même (ne devrait pas arriver si organize_file gère bien ses erreurs)
                    print(f"Erreur majeure lors de l'organisation du fichier {os.path.basename(file_path)}: {e}")
                    error_count += 1
            else:
                print(f"Info: Ignoré {file_path} car ce n'est pas un fichier régulier.")

    
    # --- Rapport final ---
    print("\n=== Rapport Final ===")
    print(f"Nombre total d'éléments trouvés dans '{os.path.basename(source_dir)}': {processed_count}")
    print(f"Nombre de fichiers copiés avec succès dans '{os.path.basename(dest_dir)}': {copied_count}")
    print(f"Nombre de fichiers non copiés (erreurs ou doublons excessifs): {error_count}")
    
    if processed_count == copied_count + error_count:
        print("Traitement terminé.")
    else:
        # Cette situation peut arriver si des éléments n'étaient pas des fichiers (comptés dans processed mais pas copiés/erreur)
        print("Traitement terminé, mais le compte total ne correspond pas parfaitement (cela peut être dû à des éléments ignorés comme des dossiers vides ou des liens symboliques).")


if __name__ == "__main__":
    # Import pour gérer les erreurs d'image non identifiée (nécessite Pillow >= 6.0)
    try:
        from PIL import UnidentifiedImageError
    except ImportError:
        # Pour compatibilité avec d'anciennes versions de Pillow, créer une classe factice
        class UnidentifiedImageError(Exception):
            pass
            
    main()