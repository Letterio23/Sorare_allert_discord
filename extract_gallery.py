import os
import requests
import json
import time

# --- CONFIGURAZIONE ---
# Questi valori verranno presi dai GitHub Secrets per sicurezza
SORARE_API_KEY = os.environ.get("SORARE_API_KEY")
USER_SLUG = os.environ.get("USER_SLUG")
API_URL = "https://api.sorare.com/graphql"

# La stessa query GraphQL dal tuo script
ALL_CARDS_QUERY = """
    query AllCardsFromUser($userSlug: String!, $rarities: [Rarity!], $cursor: String) {
        user(slug: $userSlug) {
            cards(rarities: $rarities, after: $cursor) {
                nodes {
                    slug
                    ownerSince
                }
                pageInfo {
                    endCursor
                    hasNextPage
                }
            }
        }
    }
"""

def fetch_all_user_cards(user_slug, api_key):
    """
    Estrae tutte le carte di un utente dall'API di Sorare, gestendo la paginazione.
    """
    if not api_key or not user_slug:
        print("ERRORE: SORARE_API_KEY e USER_SLUG devono essere impostati.")
        return None

    user_cards = []
    cursor = None
    has_next_page = True
    
    headers = {
        "APIKEY": api_key,
        "Content-Type": "application/json",
        "X-Sorare-ApiVersion": "v1"
    }

    print(f"Inizio estrazione carte per l'utente: {user_slug}")

    while has_next_page:
        variables = {
            "userSlug": user_slug,
            "rarities": ["limited", "rare", "super_rare", "unique"],
            "cursor": cursor
        }
        
        payload = {
            "query": ALL_CARDS_QUERY,
            "variables": variables
        }

        try:
            response = requests.post(API_URL, headers=headers, json=payload)
            response.raise_for_status()

            data = response.json()

            if "errors" in data:
                print(f"Errore GraphQL ricevuto: {data['errors']}")
                break

            cards_data = data.get("data", {}).get("user", {}).get("cards")
            if not cards_data:
                print("Dati delle carte non trovati nella risposta.")
                break

            nodes = cards_data.get("nodes", [])
            user_cards.extend(nodes)
            print(f"Recuperate {len(nodes)} carte. Totale parziale: {len(user_cards)}")

            page_info = cards_data.get("pageInfo", {})
            has_next_page = page_info.get("hasNextPage", False)
            cursor = page_info.get("endCursor")

            if has_next_page:
                time.sleep(0.5)

        except requests.exceptions.RequestException as e:
            print(f"Errore durante la chiamata API: {e}")
            return None

    return user_cards


if __name__ == "__main__":
    all_cards = fetch_all_user_cards(USER_SLUG, SORARE_API_KEY)

    if all_cards is not None:
        print(f"\nEstrazione completata. Trovate in totale {len(all_cards)} carte.")
        
        output_filename = "gallery.json"
        with open(output_filename, "w") as f:
            json.dump(all_cards, f, indent=2)
            
        print(f"I dati della galleria sono stati salvati nel file '{output_filename}'.")
    else:
        print("\nEstrazione fallita. Controlla i log per errori.")
