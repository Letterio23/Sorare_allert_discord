import os
import requests
import json
import time
from datetime import datetime, timedelta
import gspread

# --- CONFIGURAZIONE ---
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
SORARE_API_KEY = os.environ.get("SORARE_API_KEY")
GSPREAD_CREDENTIALS_JSON = os.environ.get("GSPREAD_CREDENTIALS")
API_URL = "https://api.sorare.com/graphql"
STATE_FILE = "sent_notifications.json"
NOTIFICATION_COOLDOWN_HOURS = 6

# --- [IMPORTANTE] INCOLLA QUI L'ID DEL TUO FOGLIO GOOGLE ---
# Lo trovi nell'URL del tuo foglio, es: docs.google.com/spreadsheets/d/ID_LUNGO_E_COMPLICATO/edit
SPREADSHEET_ID = "INCOLLA_QUI_IL_TUO_ID" 

# ... (Tutte le altre funzioni come LOWEST_PRICE_QUERY, UTILITY_QUERY, get_sorare_eth_rate, ecc. rimangono identiche) ...
# (Le incollo tutte qui sotto per sicurezza)

LOWEST_PRICE_QUERY = """ query ... """ # Incolla la query qui
UTILITY_QUERY = """ query ... """ # Incolla la query qui

def get_sorare_eth_rate():
    # ...
def get_coingecko_eth_rate():
    # ...
def get_best_eth_rate():
    # ...
def send_discord_notification(message):
    # ...
def load_sent_notifications():
    # ...
def save_sent_notifications(state_data):
    # ...
def check_single_player_price(target, eth_rate, sent_notifications):
    # ...

# --- FUNZIONE DI AVVIO (MODIFICATA) ---
def main():
    """Funzione principale che orchestra l'intero processo."""
    if not all([SORARE_API_KEY, DISCORD_WEBHOOK_URL, GSPREAD_CREDENTIALS_JSON]):
        print("ERRORE: Mancano uno o più segreti (API_KEY, WEBHOOK, GSPREAD_CREDENTIALS).")
        return
    
    if SPREADSHEET_ID == "INCOLLA_QUI_IL_TUO_ID":
        print("ERRORE: Devi inserire lo SPREADSHEET_ID nello script market_alert.py.")
        return

    # --- [NUOVA LOGICA] Lettura dal Foglio Google ---
    try:
        print("Autenticazione a Google Sheets...")
        credentials = json.loads(GSPREAD_CREDENTIALS_JSON)
        gc = gspread.service_account_from_dict(credentials)
        
        print(f"Apertura del foglio di lavoro con ID: {SPREADSHEET_ID}")
        spreadsheet = gc.open_by_key(SPREADSHEET_ID)
        worksheet = spreadsheet.sheet1 # Apre il primo foglio
        
        # get_all_records() legge la prima riga come intestazione e restituisce una lista di dizionari
        targets = worksheet.get_all_records() 
        print(f"Trovati {len(targets)} giocatori da monitorare dal Foglio Google.")
    except Exception as e:
        print(f"ERRORE CRITICO durante l'accesso a Google Sheets: {e}")
        return
    
    eth_to_eur_rate = get_best_eth_rate()
    if eth_to_eur_rate:
        print(f"Utilizzando il tasso di cambio: 1 ETH = {eth_to_eur_rate:.2f}€")

    sent_notifications = load_sent_notifications()
    state_was_modified = False
    
    for target in targets:
        # Assicuriamoci che le righe vuote vengano ignorate
        if target.get('slug'):
            if check_single_player_price(target, eth_to_eur_rate, sent_notifications):
                state_was_modified = True
            time.sleep(1) 
    
    if state_was_modified:
        print("\nSalvataggio dello stato delle notifiche aggiornato...")
        save_sent_notifications(sent_notifications)
    
    print("\n--- Controllo completato. ---")

if __name__ == "__main__":
    main()
