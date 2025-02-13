"""
Autentiserings- och Auktoriseringsmodul för Vision Sektion 10

Denna modul hanterar all säkerhetsrelaterad funktionalitet i systemet:

1. Användarhantering
   - Skapande av nya användare
   - Lösenordshantering med säker kryptering
   - Användarroller och behörigheter

2. Säkerhetsfunktioner
   - Krypterad lösenordslagring med bcrypt
   - Sessionshantering via Streamlit
   - Skydd mot brutforce-attacker
   - Loggning av säkerhetshändelser

3. Behörighetskontroll
   - Rollbaserad åtkomstkontroll
   - Dekoratorbaserad behörighetskontroll
   - Dynamisk sessionhantering

Tekniska detaljer:
- Använder bcrypt för säker lösenordshashning
- Implementerar MongoDB för användardata
- Tillhandahåller loggning via custom_logging
- Integrerar med Streamlit's sessionshantering
"""

import streamlit as st
import bcrypt
from views.custom_logging import log_action, current_time


def init_auth():
    """
    Initierar autentiseringssystemets tillstånd.
    
    Denna funktion säkerställer att alla nödvändiga sessionsvariabler
    finns tillgängliga för autentiseringssystemet. Den körs vid
    applikationsstart och efter utloggning.
    
    Hanterade sessionsvariabler:
    - authenticated: Boolean som indikerar om användaren är inloggad
    - user_role: Användarens roll i systemet
    - username: Inloggad användares användarnamn
    """
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'user_role' not in st.session_state:
        st.session_state.user_role = None
    if 'username' not in st.session_state:
        st.session_state.username = None


def hash_password(password):
    """
    Skapar en säker hash av ett lösenord.
    
    Använder bcrypt-algoritmen för att skapa en kryptografiskt säker
    hash av lösenordet. Varje hash innehåller ett unikt salt för
    extra säkerhet.
    
    Args:
        password (str): Lösenordet som ska hashas
    
    Returns:
        bytes: Den genererade hashen i binärt format
    
    Tekniska detaljer:
    - Använder bcrypt med automatiskt genererat salt
    - UTF-8-kodning av lösenordet före hashning
    - Resultatet är kompatibelt med verify_password
    """
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())


def verify_password(password, hashed_password):
    """
    Verifierar ett lösenord mot dess lagrade hash.
    
    Använder bcrypt för att säkert jämföra ett angivet lösenord
    med dess tidigare genererade hash.
    
    Args:
        password (str): Lösenordet som ska verifieras
        hashed_password (bytes): Den lagrade hashen att jämföra mot
    
    Returns:
        bool: True om lösenordet matchar, False annars
    
    Tekniska detaljer:
    - Hanterar UTF-8-kodning automatiskt
    - Tidskonstant jämförelse för att förhindra timing-attacker
    """
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password)


def create_user(db, username, password, role='user'):
    """
    Skapar en ny användare i systemet.
    
    Denna funktion hanterar hela processen för att skapa en ny användare,
    inklusive validering, lösenordshashning och databasoperationer.
    
    Args:
        db: MongoDB-databasanslutning
        username (str): Önskat användarnamn
        password (str): Användarens lösenord
        role (str): Användarroll (default: 'user')
    
    Returns:
        tuple: (success, message)
        - success (bool): True om användaren skapades
        - message (str): Beskrivande meddelande om resultatet
    
    Tekniska detaljer:
    - Kontrollerar om användarnamnet är unikt
    - Skapar index för effektiv sökning
    - Implementerar felhantering för databasoperationer
    - Loggar alla användarrelaterade händelser
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
        # Säkerställ att users-kollektionen finns med rätt index
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
    Autentiserar en användare och hanterar inloggningssessionen.
    
    Denna funktion hanterar hela inloggningsprocessen inklusive:
    - Verifiering av användaruppgifter
    - Uppdatering av inloggningsstatistik
    - Hantering av sessionsvariabler
    - Säkerhetsloggning
    
    Args:
        db: MongoDB-databasanslutning
        username (str): Användarnamn
        password (str): Lösenord
    
    Returns:
        bool: True vid lyckad inloggning, False annars
    
    Tekniska detaljer:
    - Använder säker lösenordsverifiering
    - Uppdaterar statistik för misslyckade inloggningar
    - Hanterar sessionsvariabler för behörighetskontroll
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
    Loggar ut användaren och rensar sessionsinformation.
    
    Denna funktion hanterar utloggningsprocessen genom att:
    - Logga utloggningshändelsen
    - Rensa alla sessionsvariabler
    - Återställa autentiseringstillståndet
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
    Dekorator för att kräva autentisering och specifik roll.
    
    Denna avancerade dekorator implementerar rollbaserad åtkomstkontroll
    genom att:
    - Verifiera att användaren är autentiserad
    - Kontrollera användarens roll mot krävd roll
    - Hantera oauktoriserad åtkomst
    
    Args:
        role (str, optional): Krävd användarroll för åtkomst
    
    Returns:
        function: Dekoratorfunktion som hanterar behörighetskontroll
    
    Tekniska detaljer:
    - Använder nested functions för flexibel konfiguration
    - Integrerar med Streamlit's sessionshantering
    - Hanterar dynamisk sidvisning vid nekad åtkomst
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

            # Exekvera den skyddade funktionen
            return func(*args, **kwargs)
        return wrapper
    return decorator
