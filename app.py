import streamlit as st
from views import overview, manage_people, manage_units, manage_boards, statistics, manage_workplaces, export_data
from database import init_db

# Konfigurera Streamlit
st.set_page_config(
    page_title="Vision Sektion 10 Organisationsöversikt",
    page_icon="📊",
    layout="wide"
)


def main():
    # Header
    st.markdown("""
        <div style="background: linear-gradient(90deg, #210061, #000000); padding: 1rem; display: flex; 
        align-items: center; margin-bottom: 2rem;">
            <img src="https://varumarke.vision.se/brandcenter/upload_path/visionbc/1561468181kx13j36au2.gif" 
                 style="max-width: 150px; width: 20%; height: auto; margin-right: 1rem;">
            <h1 style="color: #EFE9E5 !important; margin: 0;">Vision Sektion 10 - Organisationsöversikt</h1>
        </div>
    """, unsafe_allow_html=True)

    # Guide expander in sidebar - flyttad högst upp
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

    # Varning - flyttad direkt efter guiden
    st.sidebar.warning("""
    #### ❗ Viktigt att tänka på
    - Organisationsstrukturen måste finnas på plats innan man kan skapa personer
    - Personer måste vara visionombud för att kunna väljas till styrelser
    - En förvaltning kan inte tas bort om den har avdelningar
    - En avdelning kan inte tas bort om den har enheter
    - En enhet kan inte tas bort om den har personer
    """)

    st.sidebar.markdown("---")

    # Initiera databas
    db = init_db()
    if None:
        return

    # Definiera flikar med ikoner
    tab_titles = [
        "📊 Översikt",
        "🏢 Organisationsstruktur",
        "🏗️ Arbetsplatser",
        "👥 Personer",
        "⚖️ Styrelser & Nämnder",
        "📈 Statistik",
        "📥 Exportera Data"
    ]

    # Skapa flikar
    tabs = st.tabs(tab_titles)

    # Visa innehåll baserat på vald flik
    with tabs[0]:  # Översikt
        overview.show(db)
    with tabs[1]:  # Organisationsstruktur
        manage_units.show(db)
    with tabs[2]:  # Arbetsplatser
        manage_workplaces.show(db)
    with tabs[3]:  # Personer
        manage_people.show(db)
    with tabs[4]:  # Styrelser & Nämnder
        manage_boards.show(db)
    with tabs[5]:  # Statistik
        statistics.show(db)
    with tabs[6]:  # Exportera Data
        export_data.show(db)


if __name__ == "__main__":
    main()
