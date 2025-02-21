"""
Vision Sektion 10 - Organisationsöversikt

Detta är huvudapplikationen för Vision Sektion 10's organisationshanteringssystem.

1. Användarhantering och Säkerhet
   - Inloggningssystem med krypterade lösenord
   - Sessionshantering med Streamlit
   - Förstagångskonfiguration av admin-konto om det ej finns admin

2. Organisationsstruktur
   - Hierarkisk hantering av förvaltningar, avdelningar och enheter
   - Arbetsplatshantering
   - Dynamisk uppdatering av organisationsdata

3. Personalhantering
   - Registrering och hantering av ombud
   - Uppdragshantering (Visionombud, Skyddsombud, etc.)
   - Koppling mellan personer och organisationsenheter

4. Analys och Rapportering
   - Statistisk översikt och visualisering
   - Täckningsgrad för olika uppdrag
   - Exportfunktionalitet för data

Tekniska detaljer:
- Byggt med Streamlit för användargränssnittet och enkelheten(men det blev fort komplext...)
- MongoDB som databas för flexibel datalagring(gratis...)
- Implementerar säker autentisering och auktorisering(hashade lösenord, oklart exakt hur säker resten av appen är dock?)
- Använder cacheing för optimerad prestanda(Hoppas jag...)
"""

import streamlit as st
from views import overview, manage_people, manage_units, manage_boards, statistics, manage_workplaces, export_data, \
    login, first_time_setup, admin
from database import init_db
from auth import init_auth, logout
from views.custom_logging import log_action, current_time

# Konfigurera Streamlit för optimal användarupplevelse
st.set_page_config(
    page_title="Vision Sektion 10 Organisationsöversikt",
    page_icon="📊",
    layout="wide"  # Använd hela skärmbredden för bättre översikt
)


def ensure_indexes(db):
    """Skapar MongoDB index för, kanske(?), prestanda"""
    # Personer collection
    db.personer.create_index([("forvaltning_id", 1)])
    db.personer.create_index([("avdelning_id", 1)])
    db.personer.create_index([("enhet_id", 1)])
    db.personer.create_index([("arbetsplats", 1)])
    db.personer.create_index([("namn", 1)])

    # Arbetsplatser collection
    db.arbetsplatser.create_index([("forvaltning_id", 1)])
    db.arbetsplatser.create_index([("namn", 1)])
    db.arbetsplatser.create_index([("alla_forvaltningar", 1)])

    # Avdelningar collection
    db.avdelningar.create_index([("forvaltning_id", 1)])
    db.avdelningar.create_index([("namn", 1)])

    # Enheter collection
    db.enheter.create_index([("avdelning_id", 1)])
    db.enheter.create_index([("namn", 1)])


def main():
    """
    Huvudfunktion som hanterar applikationens flöde och tillståndshantering.
    
    Funktionen implementerar följande huvudprocesser:
    1. Databasinitiering och anslutningshantering
    2. Autentisering och sessionshantering
    3. Förstagångskonfiguration vid behov
    4. Huvudgränssnittet med flikar
    
    Tekniska detaljer:
    - Använder Streamlits sessionshantering
    - Implementerar säker autentisering
    - Hanterar dynamisk sidladdning
    - Tillhandahåller användarguide och varningar
    """
    # Initiera databaskoppling
    db = init_db()
    if db is None:
        return  # Avbryt om databasanslutning misslyckas

    # Säkerställ att index finns
    ensure_indexes(db)

    # Initiera autentiseringssystem och sessionshantering
    init_auth()

    # Kontrollera och hantera första-gångs-konfiguration
    if not st.session_state.get("first_time_setup_done"):
        # Verifiera om systemet behöver initieras med första användare
        if 'users' not in db.list_collection_names() or db.users.count_documents({}) == 0:
            first_time_setup.show_first_time_setup(db)
            return

        # Markera första-gångs-setup som genomförd
        st.session_state.first_time_setup_done = True

    # Säkerhetskontroll: verifiera användarautentisering
    if not st.session_state.get("authenticated", False):
        login.show_login(db)
        return

    # Rendera sidhuvud med Vision's grafiska profil
    st.markdown("""
        <div style="background: linear-gradient(90deg, #210061, #000000); padding: 1rem; display: flex; 
        align-items: center; margin-bottom: 2rem;">
            <img src="https://varumarke.vision.se/brandcenter/upload_path/visionbc/1561468181kx13j36au2.gif" 
                 style="max-width: 150px; width: 20%; height: auto; margin-right: 1rem;">
            <h1 style="color: #EFE9E5 !important; margin: 0;">Vision Sektion 10 - Organisationsöversikt</h1>
        </div>
    """, unsafe_allow_html=True)

    # Hantera användarinformation och utloggning i sidofältet
    with st.sidebar:
        st.write(f"Inloggad som: {st.session_state.username}")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Logga ut"):
                logout()
                st.rerun()
        with col2:
            if st.button("↻ Uppdatera data", help="Uppdatera all data från databasen"):
                # Force refresh of cached data
                if 'cached_data' in st.session_state:
                    del st.session_state.cached_data
                if 'cached_indexes' in st.session_state:
                    del st.session_state.cached_indexes
                st.session_state.needs_recalculation = True
                st.rerun()

    # Användarguide i sidofältet
    with st.sidebar.expander("📋 Kort Guide för Vision Organisationsöversikt"):
        st.info("""
        #### 1️⃣ Första steget - Skapa organisationsstruktur
        Börja med att skapa organisationsstrukturen under '🏢 Hantera Organisationsstruktur':
        1. Skapa förvaltningar
        2. Lägg till avdelningar under förvaltningarna
        3. Skapa enheter under avdelningarna""")

        st.info("""
        #### 2️⃣ Andra steget - Lägg till personer
        Under '👥 Hantera Personer':
        - Välj förvaltning, avdelning och enhet
        - Lägg till personer och deras uppdrag
        - Markera om de är visionombud, skyddsombud etc.""")

        st.info("""
        #### 3️⃣ Tredje steget - Styrelser & Nämnder
        Under '⚖️ Styrelser & Nämnder':
        - Förvaltningar måste finnas innan styrelser kan skapas
        - Endast visionombud kan väljas som representanter
        - Välj om det är en beställar- eller utförarnämnd""")

        st.info("""
        #### 📊 Översikt och Statistik
        - Se täckning av ombud i '📊 Översikt'
        - Följ utvecklingen i '📈 Statistik'""")

    # Visa viktiga systemvarningar och begränsningar
    st.sidebar.warning("""
    #### ❗ Viktigt att tänka på
    - Organisationsstrukturen måste finnas på plats innan man kan skapa personer
    - Personer måste vara visionombud för att kunna väljas till styrelser
    - En förvaltning kan inte tas bort om den har avdelningar
    - En avdelning kan inte tas bort om den har enheter
    - En enhet kan inte tas bort om den har personer
    """)

    st.sidebar.markdown("---")

    # Definiera huvudflikar med beskrivande ikoner
    tab_titles = [
        "📊 Översikt",
        "🏢 Organisationsstruktur",
        "🏗️ Arbetsplatser",
        "👥 Personer",
        "⚖️ Styrelser & Nämnder",
        "📈 Statistik",
        "📥 Exportera Data"
    ]

    # Lägg till admin-flik om användaren är admin
    if st.session_state.get('is_admin', False):
        tab_titles.append("🔧 Administration")

    # Skapa och hantera flikar
    tabs = st.tabs(tab_titles)

    # Innehåll baserat på aktiv flik
    with tabs[0]:  # Översikt - Dashboard
        overview.show(db)
    with tabs[1]:  # Organisationsstruktur - hantera hierarkin
        manage_units.show(db)
    with tabs[2]:  # Arbetsplatser - organisatorisk hantering
        manage_workplaces.show(db)
    with tabs[3]:  # Personer - medlems och uppdragshantering
        manage_people.show(db)
    with tabs[4]:  # Styrelser & Nämnder - representationshantering
        manage_boards.show(db)
    with tabs[5]:  # Statistik - analyser och visualiseringar
        statistics.show(db)
    with tabs[6]:  # Exportera Data - dataexport
        export_data.show(db)

    # Visa adminflik om användaren är admin
    if st.session_state.get('is_admin', False) and len(tabs) > 7:
        with tabs[7]:  # Administration - endast för administratörer
            admin.show(db)


if __name__ == "__main__":
    main()
