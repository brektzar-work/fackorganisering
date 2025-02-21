"""
Inloggningsmodul för Vision Sektion 10

Denna modul hanterar inloggning i systemet:
- Visar inloggningsformulär
- Skapar första administratören
- Hanterar lösenordsåterställning
- Skyddar mot felaktiga inloggningar

Modulen innehåller:
- Formulär för inloggning
- Skapande av admin-konto
- Säker lösenordshantering
- Felmeddelanden och hjälptexter

Tekniska detaljer:
- Krypterar lösenord med bcrypt
- Sparar användardata i MongoDB
- Loggar alla inloggningsförsök
- Hanterar sessioner via Streamlit
"""

import streamlit as st
from views.custom_logging import log_action
import bcrypt


def hash_password(password: str) -> bytes:
    """
    Krypterar ett lösenord med bcrypt.
    Gör lösenordet säkert innan det sparas i databasen.
    """
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())


def verify_password(password: str, hashed: bytes) -> bool:
    """
    Kontrollerar om ett lösenord är korrekt.
    Jämför det angivna lösenordet med det sparade.
    """
    return bcrypt.checkpw(password.encode('utf-8'), hashed)


def show_login(db):
    """
    Visar inloggningsformuläret.
    
    - Kontrollerar om det finns användare i systemet
    - Skapar admin-konto om det behövs
    - Hanterar inloggningsförsök
    - Visar relevanta felmeddelanden
    """
    st.header("Logga in")

    # Kontrollera om det finns några användare
    if not db.users.find_one():
        st.warning("Inga användare finns i systemet. Skapa en administratör.")
        with st.form("create_admin"):
            username = st.text_input("Användarnamn")
            password = st.text_input("Lösenord", type="password")
            confirm_password = st.text_input("Bekräfta lösenord", type="password")
            
            if st.form_submit_button("Skapa administratör"):
                if not username or not password:
                    st.error("Både användarnamn och lösenord krävs!")
                elif password != confirm_password:
                    st.error("Lösenorden matchar inte!")
                elif len(password) < 8:
                    st.error("Lösenordet måste vara minst 8 tecken långt!")
                else:
                    # Skapa admin-användare
                    db.users.insert_one({
                        "username": username,
                        "password": hash_password(password),
                        "role": "admin"
                    })
                    log_action("create", f"Skapade administratörskonto: {username}", "admin")
                    st.success("Administratörskonto skapat! Du kan nu logga in.")
                    st.rerun()
        return

    # Visa inloggningsformulär
    with st.form("login"):
        username = st.text_input("Användarnamn")
        password = st.text_input("Lösenord", type="password")
        
        if st.form_submit_button("Logga in"):
            if not username or not password:
                st.error("Både användarnamn och lösenord krävs!")
                return
            
            # Hämta användare från databasen
            user = db.users.find_one({"username": username})
            if not user:
                st.error("Felaktigt användarnamn eller lösenord!")
                log_action("login", f"Misslyckad inloggning för användare: {username} (användare finns ej)", "auth")
                return
            
            # Verifiera lösenord
            if not verify_password(password, user["password"]):
                st.error("Felaktigt användarnamn eller lösenord!")
                log_action("login", f"Misslyckad inloggning för användare: {username} (fel lösenord)", "auth")
                return
            
            # Spara inloggningsinformation i session state
            st.session_state.authenticated = True
            st.session_state.username = username
            st.session_state.role = user.get("role", "Användare")
            # Set is_admin flag based on role
            st.session_state.is_admin = user.get("role", "").lower() == "admin"
            
            # Logga lyckad inloggning
            log_action("login", f"Lyckad inloggning för användare: {username}", "auth")
            st.success("Inloggning lyckades!")
            st.rerun()
    
    # Visa information om återställning av lösenord
    with st.expander("Glömt lösenord?"):
        st.info(
            "Kontakta en administratör för att återställa ditt lösenord. "
            "Om du är administratör och har glömt ditt lösenord, kontakta systemansvarig."
        )
