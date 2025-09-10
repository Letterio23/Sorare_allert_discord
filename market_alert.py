import os
import requests
import json

# --- CONFIGURAZIONE LETTA DAL WORKFLOW ---
PLAYER_SLUG = os.environ.get("PLAYER_SLUG")
TARGET_PRICE_EUR = float(os.environ.get("TARGET_PRICE_EUR", 0))
RARITY = os.environ.get("RARITY", "limited")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
SORARE_API_KEY = os.environ.get("SORARE_API_KEY") # Chiave API per le chiamate autenticate

API_URL = "https://api.sorare.com/graphql"

# --- QUERY GRAPHQL PER IL PREZZO PIÙ BASSO ---
# Chiede il prezzo più basso per un giocatore e rarità specifici
LOWEST_PRICE_QUERY = """
    query GetLowestPrice($playerSlug: String!, $rarity: Rarity!) {
      football {
        player(slug: $playerSlug) {
          displayName
          lowestPriceAnyCard(rarity: $rarity) {
            liveSingleSaleOffer {
              receiverSide {
                amounts {
                  eurCents
                  wei
                  referenceCurrency
                }
              }
            }
          }
        }
      }
    }
"""

def get_eth_to_eur_rate():
    """Recupera il tasso di cambio ETH/EUR da un'API pubblica."""
    try:
        response = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=eur")
        response.raise_for_status()
        return response.json()["ethereum"]["eur"]
    except Exception as e:
        print(f"Attenzione: Impossibile recuperare il tasso ETH/EUR. Errore: {e}")
        # Ritorna un valore di fallback in caso di errore
        return 2800.0

def send_discord_notification(message):
    """Invia un messaggio al webhook di Discord specificato."""
    if not DISCORD_WEBHOOK_URL:
        print("ERRORE: URL del Webhook di Discord non trovato.")
        return
        
    payload = {"content": message}
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload)
        response.raise_for_status()
        print("Notifica Discord inviata con successo!")
    except requests.exceptions.RequestException as e:
        print(f"ERRORE durante l'invio della notifica a Discord: {e}")

def check_market_price():
    """Funzione principale che controlla il prezzo di mercato."""
    if not all([PLAYER_SLUG, TARGET_PRICE_EUR, RARITY, SORARE_API_KEY]):
        print("ERRORE: Mancano una o più variabili d'ambiente (PLAYER_SLUG, TARGET_PRICE_EUR, RARITY, SORARE_API_KEY).")
        return

    print(f"Controllo del mercato per {PLAYER_SLUG} ({RARITY}) con prezzo obiettivo <= {TARGET_PRICE_EUR}€")

    headers = {"APIKEY": SORARE_API_KEY, "Content-Type": "application/json"}
    variables = {"playerSlug": PLAYER_SLUG, "rarity": RARITY}
    payload = {"query": LOWEST_PRICE_QUERY, "variables": variables}

    try:
        response = requests.post(API_URL, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

        if "errors" in data:
            print(f"Errore GraphQL: {data['errors']}")
            return

        card_data = data.get("data", {}).get("football", {}).get("player")
        if not card_data or not card_data.get("lowestPriceAnyCard"):
            print(f"Nessuna carta '{RARITY}' per {PLAYER_SLUG} trovata sul mercato.")
            return

        player_name = card_data.get("displayName", PLAYER_SLUG)
        amounts = card_data["lowestPriceAnyCard"]["liveSingleSaleOffer"]["receiverSide"]["amounts"]

        current_price = 0
        if amounts.get("eurCents"):
            current_price = amounts["eurCents"] / 100
        elif amounts.get("wei"):
            eth_to_eur = get_eth_to_eur_rate()
            eth_price = float(amounts["wei"]) / 1e18
            current_price = eth_price * eth_to_eur
            print(f"Prezzo in ETH convertito: {current_price:.2f}€")

        if current_price > 0:
            print(f"Prezzo più basso trovato: {current_price:.2f}€")
            if current_price <= TARGET_PRICE_EUR:
                print(f"CONDIZIONE SODDISFATTA! Prezzo ({current_price:.2f}€) <= Obiettivo ({TARGET_PRICE_EUR}€). Invio notifica...")
                
                # Link diretto alla pagina del giocatore per comodità
                market_url = f"https://sorare.com/football/players/{PLAYER_SLUG}/cards?rarity={RARITY}"
                
                message = (
                    f"🔥 **Allerta Prezzo Sorare!** 🔥\n\n"
                    f"Trovata carta per **{player_name}** ({RARITY.capitalize()}) sotto il tuo prezzo obiettivo!\n\n"
                    f"📉 **Prezzo Trovato: {current_price:.2f}€**\n"
                    f"🎯 **Prezzo Obiettivo: {TARGET_PRICE_EUR:.2f}€**\n\n"
                    f"➡️ Vai al mercato: {market_url}"
                )
                send_discord_notification(message)
            else:
                print("Prezzo attuale superiore all'obiettivo. Nessuna azione richiesta.")
        else:
            print(f"La carta per {player_name} è sul mercato ma non ha un prezzo in EUR o ETH.")

    except Exception as e:
        print(f"Si è verificato un errore imprevisto: {e}")


if __name__ == "__main__":
    check_market_price()
