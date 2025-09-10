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
NOTIFICATION_COOLDOWN_HOURS = 6 # Non inviare notifiche per lo stesso alert per 6 ore

# --- QUERY GRAPHQL ---
LOWEST_PRICE_QUERY = """
    query GetLowestPrice($playerSlug: String!, $rarity: Rarity!, $inSeason: Boolean) {
      football {
        player(slug: $playerSlug) {
          displayName
          lowestPriceAnyCard(rarity: $rarity, inSeason: $inSeason) {
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

def get_eth_to_eur_rate():
    """Recupera il tasso di cambio ETH/EUR."""
    try:
        response = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=eur")
        response.raise_for_status()
        return response.json()["ethereum"]["eur"]
    except Exception:
        return 2800.0 # Fallback

def send_discord_notification(message):
    """Invia un messaggio al webhook di Discord."""
    if not DISCORD_WEBHOOK_URL: return
    payload = {"content": message}
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload)
        response.raise_for_status()
        print("Notifica Discord inviata con successo!")
    except requests.exceptions.RequestException as e:
        print(f"ERRORE invio notifica Discord: {e}")

def load_sent_notifications():
    """Carica lo stato delle notifiche inviate dal file JSON."""
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
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
    alert_key = f"{player_slug}_{rarity}_{season_preference}"

    last_notified_str = sent_notifications.get(alert_key)
    if last_notified_str:
        last_notified_time = datetime.fromisoformat(last_notified_str)
        if datetime.utcnow() < last_notified_time + timedelta(hours=NOTIFICATION_COOLDOWN_HOURS):
            print(f"\n--- Saltando {player_slug} ({rarity}, {season_text}): notifica già inviata di recente. ---")
            return False

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

        card_data = data.get("data", {}).get("football", {}).get("player")
        if not card_data or not card_data.get("lowestPriceAnyCard"):
            print(f"Nessuna carta '{rarity}' ({season_text}) per {player_slug} trovata sul mercato.")
            return False

        player_name = card_data.get("displayName", player_slug)
        amounts = card_data["lowestPriceAnyCard"]["liveSingleSaleOffer"]["receiverSide"]["amounts"]
        current_price = 0

        if amounts and amounts.get("eurCents"):
            current_price = amounts["eurCents"] / 100
        elif amounts and amounts.get("wei"):
            eth_price = float(amounts["wei"]) / 1e18
            current_price = eth_price * eth_rate

        if current_price > 0:
            print(f"Prezzo più basso per {player_name}: {current_price:.2f}€")
            if current_price <= target_price:
                print(f"!!! CONDIZIONE SODDISFATTA !!! Invio notifica...")
                market_url = f"https://sorare.com/football/players/{player_slug}/cards?rarity={rarity}"
                message = (
                    f"🔥 **Allerta Prezzo Sorare!** 🔥\n\n"
                    f"Trovata carta per **{player_name}** ({rarity.capitalize()}) sotto il tuo prezzo obiettivo!\n\n"
                    f"**Tipo Carta: {season_text}**\n"
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
            print(f"Nessun prezzo valido trovato per {player_name}.")
            
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
