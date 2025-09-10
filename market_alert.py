import os
import requests
import json
import time
from datetime import datetime, timedelta

# --- CONFIGURAZIONE ---
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
SORARE_API_KEY = os.environ.get("SORARE_API_KEY")
API_URL = "https://api.sorare.com/graphql"
STATE_FILE = "sent_notifications.json"
NOTIFICATION_COOLDOWN_HOURS = 1 # Non inviare notifiche per lo stesso alert per 6 ore

# --- QUERY (invariata) ---
LOWEST_PRICE_QUERY = "..." # (La query lunga può rimanere qui, non c'è bisogno di incollarla di nuovo)

# ... (le funzioni get_eth_to_eur_rate e send_discord_notification rimangono identiche) ...

def load_sent_notifications():
    """Carica lo stato delle notifiche inviate dal file JSON."""
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # Se il file non esiste o è corrotto, inizia con uno stato vuoto
        return {}

def save_sent_notifications(state_data):
    """Salva lo stato aggiornato delle notifiche nel file JSON."""
    with open(STATE_FILE, "w") as f:
        json.dump(state_data, f, indent=2)

def check_single_player_price(target, eth_rate, sent_notifications):
    """Controlla il prezzo e decide se inviare una notifica basandosi sullo stato."""
    player_slug = target['slug']
    target_price = float(target['price'])
    rarity = target['rarity']
    season_preference = target.get('season', 'classic')
    is_in_season = (season_preference == "in_season")
    season_text = "In Season" if is_in_season else "Classic"

    # Crea una chiave unica per questo specifico alert
    alert_key = f"{player_slug}_{rarity}_{season_preference}"
    
    # --- LOGICA ANTI-SPAM ---
    last_notified_str = sent_notifications.get(alert_key)
    if last_notified_str:
        last_notified_time = datetime.fromisoformat(last_notified_str)
        if datetime.utcnow() < last_notified_time + timedelta(hours=NOTIFICATION_COOLDOWN_HOURS):
            print(f"\n--- Saltando {player_slug} ({rarity}, {season_text}): notifica già inviata di recente. ---")
            return False # Nessuna modifica allo stato

    print(f"\n--- Controllando {player_slug} ({rarity}, {season_text}) con obiettivo <= {target_price}€ ---")
    
    # ... (il resto della logica di chiamata API rimane identico) ...
    # ... se la condizione è soddisfatta e si invia la notifica ...
            if current_price <= target_price:
                # ... (costruisci il messaggio e invia con send_discord_notification)
                
                # AGGIORNA LO STATO!
                sent_notifications[alert_key] = datetime.utcnow().isoformat()
                return True # Lo stato è stato modificato

    return False # Nessuna modifica allo stato

def main():
    # ... (caricamento della lista dei giocatori da players_list.json) ...

    sent_notifications = load_sent_notifications()
    eth_to_eur_rate = get_eth_to_eur_rate()
    
    state_was_modified = False
    for target in targets:
        # Passiamo lo stato alla funzione e riceviamo un feedback se è stato modificato
        if check_single_player_price(target, eth_to_eur_rate, sent_notifications):
            state_was_modified = True
        time.sleep(1) 
    
    # Salviamo il file di stato solo se sono state inviate nuove notifiche
    if state_was_modified:
        print("\nSalvataggio dello stato delle notifiche aggiornato...")
        save_sent_notifications(sent_notifications)
    
    print("\n--- Controllo completato. ---")

if __name__ == "__main__":
    main()
