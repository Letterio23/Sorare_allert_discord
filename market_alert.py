import os
import requests
import json
import time

# --- CONFIGURAZIONE ---
# Ora leggiamo la lista JSON e i segreti
PLAYER_TARGETS_JSON = os.environ.get("PLAYER_TARGETS_JSON")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
SORARE_API_KEY = os.environ.get("SORARE_API_KEY")

API_URL = "https://api.sorare.com/graphql"

# --- QUERY GRAPHQL (rimane invariata) ---
LOWEST_PRICE_QUERY = """
    query GetLowestPrice($playerSlug: String!, $rarity: Rarity!) {
      football {
        player(slug: $playerSlug) {
          displayName
          lowestPriceAnyCard(rarity: $rarity) {
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

def check_single_player_price(target, eth_rate):
    """Controlla il prezzo di un singolo giocatore."""
    player_slug = target['slug']
    target_price = float(target['price'])
    rarity = target['rarity']
    
    print(f"\n--- Controllando {player_slug} ({rarity}) con obiettivo <= {target_price}€ ---")
    
    headers = {"APIKEY": SORARE_API_KEY, "Content-Type": "application/json"}
    variables = {"playerSlug": player_slug, "rarity": rarity}
    payload = {"query": LOWEST_PRICE_QUERY, "variables": variables}

    try:
        response = requests.post(API_URL, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

        if "errors" in data:
            print(f"Errore GraphQL per {player_slug}: {data['errors']}")
            return

        card_data = data.get("data", {}).get("football", {}).get("player")
        if not card_data or not card_data.get("lowestPriceAnyCard"):
            print(f"Nessuna carta '{rarity}' per {player_slug} trovata sul mercato.")
            return

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
                    f"📉 **Prezzo Trovato: {current_price:.2f}€**\n"
                    f"🎯 **Prezzo Obiettivo: {target_price:.2f}€**\n\n"
                    f"➡️ Vai al mercato: {market_url}"
                )
                send_discord_notification(message)
            else:
                print("Prezzo superiore all'obiettivo.")
        else:
            print(f"Nessun prezzo valido trovato per {player_name}.")
            
    except Exception as e:
        print(f"Errore imprevisto durante il controllo di {player_slug}: {e}")


def main():
    """Funzione principale che orchestra il processo."""
    if not all([PLAYER_TARGETS_JSON, SORARE_API_KEY, DISCORD_WEBHOOK_URL]):
        print("ERRORE: Mancano una o più variabili d'ambiente o segreti.")
        return

    try:
        targets = json.loads(PLAYER_TARGETS_JSON)
        print(f"Trovati {len(targets)} giocatori da monitorare.")
    except json.JSONDecodeError:
        print("ERRORE: Formato JSON non valido in PLAYER_TARGETS_JSON.")
        return
    
    # Recupera il tasso di cambio una sola volta all'inizio
    eth_to_eur_rate = get_eth_to_eur_rate()
    print(f"Tasso di cambio attuale: 1 ETH = {eth_to_eur_rate:.2f}€")

    # Cicla su ogni giocatore nella lista
    for target in targets:
        check_single_player_price(target, eth_to_eur_rate)
        # Aggiungiamo una piccola pausa per essere gentili con l'API di Sorare
        time.sleep(1) 
    
    print("\n--- Controllo completato. ---")

if __name__ == "__main__":
    main()
