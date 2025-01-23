"""
Inloggningsmodul för Vision Sektion 10
Detta system hanterar användarautentisering och inloggningsgränssnittet.
Modulen tillhandahåller ett säkert och användarvänligt inloggningsformulär
med felhantering och loggning av inloggningsförsök.

Tekniska detaljer:
- Använder Streamlit för användargränssnittet
- Implementerar säker lösenordshantering
- Integrerar med custom_logging för spårning
- Hanterar sessionshantering via Streamlit
"""

import streamlit as st
from auth import login
from views.custom_logging import log_action, current_time


def show_login(db):
    """
    Visar och hanterar inloggningsformuläret för Vision Sektion 10.
    
    Funktionen:
    1. Visar Vision's logotyp och välkomstmeddelande
    2. Presenterar inloggningsformulär med användarnamn och lösenord
    3. Hanterar inloggningsförsök och visar relevant feedback
    4. Loggar både lyckade och misslyckade inloggningsförsök
    
    Args:
        db: MongoDB-databasanslutning för användarautentisering
    
    Tekniska detaljer:
    - Använder Streamlit's formulärhantering för säker inmatning
    - Döljer lösenord vid inmatning
    - Implementerar automatisk omladdning vid lyckad inloggning
    - Visar användarvänliga felmeddelanden vid misslyckade försök
    """
    # Visa Vision's logotyp och välkomstmeddelande
    st.markdown("""
        <div style="text-align: center; margin-bottom: 2rem;">
            <img src="https://varumarke.vision.se/brandcenter/upload_path/visionbc/1561468181kx13j36au2.gif" 
                 style="max-width: 200px;">
            <h2 style="color: #EFE9E5;">Vision Sektion 10 - Inloggning</h2>
        </div>
    """, unsafe_allow_html=True)

    # Skapa inloggningsformulär med säker lösenordsinmatning
    with st.form("login_form"):
        username = st.text_input("Användarnamn")
        password = st.text_input("Lösenord", type="password")  # Dölj lösenord vid inmatning
        submitted = st.form_submit_button("Logga in")

        if submitted:
            # Försök logga in och hantera resultatet
            if login(db, username, password):
                # Logga lyckad inloggning och uppdatera gränssnittet
                log_action("login", f"Användare {username} loggade in", "auth")
                st.success("Inloggning lyckades!")
                st.rerun()  # Ladda om sidan för att uppdatera sessionstillstånd
            else:
                # Logga misslyckat försök och visa felmeddelande
                log_action("failed_login", f"Misslyckat inloggningsförsök för användare: {username}", "auth")
                st.error("Felaktigt användarnamn eller lösenord")
