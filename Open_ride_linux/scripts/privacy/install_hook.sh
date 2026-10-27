#!/usr/bin/env bash
# Installe le crochet pre-commit du scanner de confidentialité (lot X23) dans le clone courant.
# Chaque commit est refusé si un fichier indexé contient un mot interdit, une coordonnée
# dans une zone privée, une adresse Bluetooth réelle, une clé ou un fichier d'activité.
# Contournement exceptionnel : git commit --no-verify.
set -euo pipefail
root="$(git rev-parse --show-toplevel)"
hook="$(git rev-parse --git-path hooks)/pre-commit"
mkdir -p "$(dirname "$hook")"
if [[ -e "$hook" ]] && ! grep -q "privacy_scan.py" "$hook"; then
    echo "Un crochet pre-commit existe déjà : $hook (non modifié). Ajoute-y :" >&2
    echo "  python3 \"$root/Open_ride_linux/scripts/privacy/privacy_scan.py\" --staged" >&2
    exit 1
fi
cat > "$hook" <<HOOK
#!/usr/bin/env bash
# Crochet installé par Open_ride_linux/scripts/privacy/install_hook.sh (lot X23).
exec python3 "\$(git rev-parse --show-toplevel)/Open_ride_linux/scripts/privacy/privacy_scan.py" --staged
HOOK
chmod +x "$hook"
echo "Crochet installé : $hook"
if [[ ! -f "$HOME/OpenRide/privacy_denylist.txt" ]]; then
    echo "Pense à créer ~/OpenRide/privacy_denylist.txt (modèle : privacy_denylist.example.txt)."
fi
