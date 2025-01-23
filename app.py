"""
Vision Sektion 10 - Organisationsöversikt

Detta är huvudapplikationen för Vision Sektion 10's organisationshanteringssystem.
Systemet hanterar den kompletta organisationsstrukturen och dess funktioner:

1. Användarhantering och Säkerhet
   - Inloggningssystem med krypterade lösenord
   - Sessionhantering med Streamlit
   - Första-gångs-konfiguration av admin-konto

2. Organisationsstruktur
   - Hierarkisk hantering av förvaltningar, avdelningar och enheter
   - Arbetsplatshantering med geografisk visualisering
   - Dynamisk uppdatering av organisationsdata

3. Personalhantering
   - Registrering och hantering av medlemmar
   - Uppdragshantering (Visionombud, Skyddsombud, etc.)
   - Koppling mellan personer och organisationsenheter

4. Analys och Rapportering
   - Statistisk översikt och visualisering
   - Täckningsgrad för olika uppdrag
   - Exportfunktionalitet för data

Tekniska detaljer:
- Byggt med Streamlit för användargränssnittet
- MongoDB som databas för flexibel datalagring
- Implementerar säker autentisering och auktorisering
- Använder cachning för optimerad prestanda
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


def main():
    """
    Huvudfunktion som hanterar applikationens flöde och tillståndshantering.
    
    Funktionen implementerar följande huvudprocesser:
    1. Databasinitiering och anslutningshantering
    2. Autentisering och sessionshantering
    3. Första-gångs-konfiguration vid behov
    4. Huvudgränssnittet med navigationsflikar
    
    Tekniska detaljer:
    - Använder Streamlit's sessionshantering
    - Implementerar säker autentisering
    - Hanterar dynamisk sidladdning
    - Tillhandahåller användarguide och varningar
    """
    # Initiera databaskoppling med felhantering
    db = init_db()
    if db is None:
        return  # Avbryt om databasanslutning misslyckas

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
        if st.button("Logga ut"):
            logout()
            st.rerun()

    # Tillhandahåll användarguide i expanderbart sidofält
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

    # Definiera huvudnavigationsflikar med beskrivande ikoner
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

    # Skapa och hantera navigationsflikar
    tabs = st.tabs(tab_titles)

    # Rendera innehåll baserat på aktiv flik
    with tabs[0]:  # Översikt - huvuddashboard
        overview.show(db)
    with tabs[1]:  # Organisationsstruktur - hantera hierarkin
        manage_units.show(db)
    with tabs[2]:  # Arbetsplatser - geografisk och organisatorisk hantering
        manage_workplaces.show(db)
    with tabs[3]:  # Personer - medlems- och uppdragshantering
        manage_people.show(db)
    with tabs[4]:  # Styrelser & Nämnder - representationshantering
        manage_boards.show(db)
    with tabs[5]:  # Statistik - analyser och visualiseringar
        statistics.show(db)
    with tabs[6]:  # Exportera Data - dataexport och rapporter
        export_data.show(db)
    
    # Visa admin-flik om användaren är admin
    if st.session_state.get('is_admin', False) and len(tabs) > 7:
        with tabs[7]:  # Administration - endast för administratörer
            admin.show(db)


if __name__ == "__main__":
    main()
