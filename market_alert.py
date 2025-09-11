import os
import requests
import json
import time
from datetime import datetime, timedelta

# --- CONFIGURAZIONE (invariata) ---
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
SORARE_API_KEY = os.environ.get("SORARE_API_KEY")
API_URL = "https://api.sorare.com/graphql"
STATE_FILE = "sent_notifications.json"
NOTIFICATION_COOLDOWN_HOURS = 6

# --- QUERY GRAPHQL AGGIORNATA ---
# Aggiungiamo 'slug' per ottenere l'identificativo unico della carta
LOWEST_PRICE_QUERY = """
    query GetLowestPrice($playerSlug: String!, $rarity: Rarity!, $inSeason: Boolean) {
      football {
        player(slug: $playerSlug) {
          displayName
          lowestPriceAnyCard(rarity: $rarity, inSeason: $inSeason) {
            slug  # <-- MODIFICA CHIAVE: chiediamo lo slug unico della carta
            liveSingleSaleOffer {
              receiverSide {
                amounts { eurCents, wei }
              }
            }
          }
        }
      }
    }
"""

# ... (le funzioni get_eth_to_eur_rate, send_discord_notification, load/save_sent_notifications rimangono identiche) ...
def get_eth_to_eur_rate():
    try:
        response = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=eur")
        response.raise_for_status()
        return response.json()["ethereum"]["eur"]
    except Exception: return 2800.0

def send_discord_notification(message):
    if not DISCORD_WEBHOOK_URL: return
    payload = {"content": message}
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload)
        response.raise_for_status()
        print("Notifica Discord inviata con successo!")
    except requests.exceptions.RequestException as e: print(f"ERRORE invio notifica Discord: {e}")

def load_sent_notifications():
    try:
        with open(STATE_FILE, "r") as f: return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError): return {}

def save_sent_notifications(state_data):
    with open(STATE_FILE, "w") as f: json.dump(state_data, f, indent=2)


def check_single_player_price(target, eth_rate, sent_notifications):
    """Controlla il prezzo usando lo slug unico della carta per l'anti-spam."""
    player_slug = target['slug']
    target_price = float(target['price'])
    rarity = target['rarity']
    season_preference = target.get('season', 'classic')
    is_in_season = (season_preference == "in_season")
    season_text = "In Season" if is_in_season else "Classic"
    
    print(f"\n--- Controllando {player_slug} ({rarity}, {season_text}) con obiettivo <= {target_price}€ ---")
    
    headers = {"APIKEY": SORARE_API_KEY, "Content-Type": "application/json"}
    variables = {"playerSlug": player_slug, "rarity": rarity, "inSeason": is_in_season}
    payload = {"query": LOWEST_PRICE_QUERY, "variables": variables}

    try:
        response = requests.post(API_URL, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

        if "errors" in data:
            print(f"Errore GraphQL per {player_slug}: {data['errors']}")
            return False

        lowest_card_info = data.get("data", {}).get("football", {}).get("player", {}).get("lowestPriceAnyCard")
        if not lowest_card_info:
            print(f"Nessuna carta '{rarity}' ({season_text}) per {player_slug} trovata sul mercato.")
            return False

        # --- LOGICA ANTI-SPAM POTENZIATA ---
        unique_card_slug = lowest_card_info.get("slug")
        if not unique_card_slug:
            print("Attenzione: lo slug unico della carta non è stato trovato nella risposta API.")
            return False
            
        alert_key = unique_card_slug  # Usiamo lo slug della carta come chiave!

        last_notified_str = sent_notifications.get(alert_key)
        if last_notified_str:
            last_notified_time = datetime.fromisoformat(last_notified_str)
            if datetime.utcnow() < last_notified_time + timedelta(hours=NOTIFICATION_COOLDOWN_HOURS):
                print(f"--- Saltando la carta {unique_card_slug}: notifica già inviata di recente. ---")
                return False
        
        player_name = data["data"]["football"]["player"].get("displayName", player_slug)
        amounts = lowest_card_info.get("liveSingleSaleOffer", {}).get("receiverSide", {}).get("amounts")
        current_price = 0

        if amounts and amounts.get("eurCents"):
            current_price = amounts["eurCents"] / 100
        elif amounts and amounts.get("wei"):
            eth_price = float(amounts["wei"]) / 1e18
            current_price = eth_price * eth_rate

        if current_price > 0:
            print(f"Prezzo più basso ({unique_card_slug}): {current_price:.2f}€")
            if current_price <= target_price:
                print(f"!!! CONDIZIONE SODDISFATTA PER {unique_card_slug}!!! Invio notifica...")
                market_url = f"https://sorare.com/football/players/{player_slug}/cards?rarity={rarity}"
                message = (
                    f"🔥 **Allerta Prezzo Sorare!** 🔥\n\n"
                    f"Trovata carta per **{player_name}** ({rarity.capitalize()}) sotto il tuo prezzo obiettivo!\n\n"
                    f"**Carta Specifica:** `{unique_card_slug}`\n" # <-- Notifica migliorata
                    f"**Tipo Carta:** {season_text}\n"
                    f"📉 **Prezzo Trovato: {current_price:.2f}€**\n"
                    f"🎯 **Prezzo Obiettivo: {target_price:.2f}€**\n\n"
                    f"➡️ Vai al mercato: {market_url}"
                )
                send_discord_notification(message)
                sent_notifications[alert_key] = datetime.utcnow().isoformat()
                return True
            else:
                print("Prezzo superiore all'obiettivo.")
        else:
            print(f"Nessun prezzo valido trovato per {unique_card_slug}.")
            
    except Exception as e:
        print(f"Errore imprevisto durante il controllo di {player_slug}: {e}")

    return False

def main():
    if not all([SORARE_API_KEY, DISCORD_WEBHOOK_URL]):
        print("ERRORE: Mancano i segreti SORARE_API_KEY o DISCORD_WEBHOOK_URL.")
        return
    
    try:
        with open("players_list.json", "r") as f:
            targets = json.load(f)
        print(f"Trovati {len(targets)} giocatori da monitorare dal file players_list.json.")
    except FileNotFoundError:
        print("ERRORE: Il file 'players_list.json' non è stato trovato.")
        return
    except json.JSONDecodeError:
        print("ERRORE: Formato JSON non valido in players_list.json.")
        return
    
    sent_notifications = load_sent_notifications()
    eth_to_eur_rate = get_eth_to_eur_rate()
    
    state_was_modified = False
    for target in targets:
        if check_single_player_price(target, eth_to_eur_rate, sent_notifications):
            state_was_modified = True
        time.sleep(1) 
    
    if state_was_modified:
        print("\nSalvataggio dello stato delle notifiche aggiornato...")
        save_sent_notifications(sent_notifications)
    
    print("\n--- Controllo completato. ---")

if __name__ == "__main__":
    main()
