"""
Säkerhetsmodul för Vision Sektion 10

Denna modul hanterar all säkerhet i systemet:
- Inloggning och användarhantering
- Lösenordshantering (krypterade lösenord)
- Behörighetskontroll för olika delar
- Skydd mot obehörig åtkomst

Modulen innehåller:
- Funktioner för att skapa och hantera användare
- Säker lösenordshantering med kryptering
- Inloggnings- och utloggningsfunktioner
- Kontroll av behörigheter

Tekniska detaljer:
- Använder bcrypt för säker lösenordshantering
- Sparar användardata i MongoDB
- Loggar alla säkerhetshändelser
- Hanterar sessioner via Streamlit
"""

import streamlit as st
import bcrypt
from views.custom_logging import log_action, current_time


def init_auth():
    """
    Startar upp säkerhetssystemet.
    Kontrollerar att alla nödvändiga säkerhetsinställningar finns.
    """
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'user_role' not in st.session_state:
        st.session_state.user_role = None
    if 'username' not in st.session_state:
        st.session_state.username = None


def hash_password(password):
    """
    Krypterar ett lösenord på ett säkert sätt.
    Använder bcrypt som är en säker krypteringsmetod.
    """
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())


def verify_password(password, hashed_password):
    """
    Kontrollerar om ett lösenord matchar den krypterade versionen.
    Används vid inloggning för att verifiera användarens lösenord.
    """
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password)


def create_user(db, username, password, role='user'):
    """
    Skapar en ny användare i systemet.
    
    - Kontrollerar att användarnamnet är unikt
    - Krypterar lösenordet innan det sparas
    - Sätter grundläggande användarinformation
    - Loggar att användaren skapades
    """
    # Validera att användarnamnet är unikt
    if db.users.find_one({'username': username}):
        return False, "Användarnamnet finns redan"

    # Skapa användarobjekt med säkerhetsinformation
    user = {
        'username': username,
        'password': hash_password(password),
        'role': role,
        'created_at': current_time(),
        'last_login': None,
        'failed_login_attempts': 0,
        'last_failed_login': None,
        'account_locked': False,
        'password_changed': True
    }

    try:
        # Säkerställ att users-collection finns med rätt index
        if 'users' not in db.list_collection_names():
            db.create_collection('users')
        db.users.create_index([("username", 1)], unique=True)
        
        # Skapa användaren och logga händelsen
        db.users.insert_one(user)
        log_action("create", f"Skapade användare: {username} med roll: {role}", "user")
        return True, "Användare skapad"
    except Exception as e:
        return False, f"Kunde inte skapa användare: {str(e)}"


def login(db, username, password):
    """
    Hanterar inloggning av användare.
    
    - Kontrollerar användarnamn och lösenord
    - Uppdaterar inloggningsstatistik
    - Sätter behörigheter för sessionen
    - Loggar inloggningsförsöket
    """
    user = db.users.find_one({'username': username})

    if user and verify_password(password, user['password']):
        # Uppdatera inloggningsstatistik och återställ säkerhetsflaggor
        db.users.update_one(
            {'username': username},
            {'$set': {
                'last_login': current_time(),
                'failed_login_attempts': 0,
                'last_failed_login': None
            }}
        )

        # Sätt sessionsvariabler för behörighetskontroll
        st.session_state.authenticated = True
        st.session_state.user_role = user['role']
        st.session_state.username = username
        st.session_state.is_admin = user['role'].lower() == 'admin'
        
        # Logga lyckad inloggning
        log_action("login", f"Användare {username} loggade in", "auth")
        return True
    
    # Hantera misslyckad inloggning
    if user:
        log_action("failed_login", f"Misslyckat inloggningsförsök för användare: {username}", "auth")
    return False


def logout():
    """
    Loggar ut användaren från systemet.
    
    - Rensar sessionsinformation
    - Tar bort behörigheter
    - Loggar utloggningen
    """
    # Logga utloggningshändelsen om en användare var inloggad
    username = st.session_state.get('username')
    if username:
        log_action("logout", f"Användare {username} loggade ut", "auth")
    
    # Rensa alla säkerhetsrelaterade sessionsvariabler
    for key in ['authenticated', 'user_role', 'username', 'is_admin']:
        if key in st.session_state:
            del st.session_state[key]


def require_auth(role=None):
    """
    Kontrollerar att användaren har rätt behörighet.
    
    - Ser till att användaren är inloggad
    - Kontrollerar användarens roll om det behövs
    - Visar inloggningsformulär om det behövs
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Säkerställ att autentiseringssystemet är initierat
            init_auth()

            # Kontrollera om användaren är inloggad
            if not st.session_state.authenticated:
                from views.login import show_login
                show_login(kwargs.get('db'))
                return

            # Verifiera rollbehörighet om en specifik roll krävs
            if role and st.session_state.user_role != role:
                st.error("Du har inte behörighet till denna sida")
                return

            # Kör den skyddade funktionen
            return func(*args, **kwargs)
        return wrapper
    return decorator
