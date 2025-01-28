"""
Hanteringsmodul för Arbetsplatser i Vision Sektion 10.

Detta system hanterar arbetsplatser på två nivåer:
1. Regionala arbetsplatser (gäller alla förvaltningar)
2. Förvaltningsspecifika arbetsplatser (kopplade till en specifik förvaltning)

Modulen tillhandahåller funktionalitet för att:
- Skapa och redigera arbetsplatser med detaljerad information
- Hantera geografisk data (adress och koordinater)
- Beräkna och visa medlemsantal per arbetsplats
- Migrera existerande arbetsplatsdata
- Hantera relationer mellan arbetsplatser och förvaltningar

Tekniska detaljer:
- Använder MongoDB för datalagring
- Implementerar caching via Streamlit session state
- Hanterar geografisk data för kartvisning
- Tillhandahåller batch-uppdateringar för effektiv datahantering
"""

import streamlit as st
import streamlit_nested_layout
from collections import defaultdict
from views.custom_logging import log_action
from views.cache_manager import get_cached_data, update_cache_after_change

# Lista över alla kommuner i Västra Götaland, sorterad alfabetiskt
# Används för att säkerställa konsistent inmatning av kommunnamn
KOMMUNER = [
    "Välj kommun...",
    "Ale", "Alingsås", "Bengtsfors", "Bollebygd", "Borås",
    "Dals-Ed", "Essunga", "Falköping", "Färgelanda", "Grästorp",
    "Gullspång", "Göteborg", "Götene", "Herrljunga", "Hjo",
    "Härryda", "Karlsborg", "Kungälv", "Lerum", "Lidköping",
    "Lilla Edet", "Lysekil", "Mariestad", "Mark", "Mellerud",
    "Munkedal", "Mölndal", "Orust", "Partille", "Skara",
    "Skövde", "Sotenäs", "Stenungsund", "Strömstad", "Svenljunga",
    "Tanum", "Tibro", "Tidaholm", "Tjörn", "Tranemo",
    "Trollhättan", "Töreboda", "Uddevalla", "Ulricehamn", "Vara",
    "Vårgårda", "Vänersborg", "Åmål", "Öckerö"
]


def migrate_existing_workplaces(db):
    """Migrerar existerande arbetsplatsdata till det nya formatet.
    
    Denna komplexa funktion utför följande steg:
    1. Samlar alla unika arbetsplatser från persondatabasen
    2. Identifierar arbetsplatser som finns i flera förvaltningar
    3. Skapar nya arbetsplatsposter med korrekt struktur:
       - Regionala arbetsplatser för de som finns i flera förvaltningar
       - Förvaltningsspecifika för övriga
    
    Tekniska detaljer:
    - Använder defaultdict för effektiv gruppering
    - Implementerar upsert för att undvika dubletter
    - Hanterar relationer mellan arbetsplatser och förvaltningar
    
    Args:
        db: MongoDB-databasanslutning med collections för:
           - personer
           - arbetsplatser
           - forvaltningar
    """
    # Hämta alla unika arbetsplatser från personer
    personer = list(db.personer.find())
    existing_workplaces = defaultdict(set)  # förvaltning_id -> set of arbetsplatser

    # Samla alla unika arbetsplatser per förvaltning
    # Använder set för att automatiskt eliminera dubletter
    for person in personer:
        if person.get('arbetsplatser'):
            for arbetsplats in person['arbetsplatser']:
                existing_workplaces[person['forvaltning_id']].add(arbetsplats)

    # Kontrollera om arbetsplatser redan har migrerats
    # Detta förhindrar dubbelmigrering av data
    if db.arbetsplatser.count_documents({}) == 0:
        # Iterera över alla förvaltningar och deras arbetsplatser
        for forvaltning_id, arbetsplatser in existing_workplaces.items():
            forvaltning = db.forvaltningar.find_one({"_id": forvaltning_id})

            for arbetsplats in arbetsplatser:
                # Identifiera arbetsplatser som finns i flera förvaltningar
                forvaltningar_med_samma_arbetsplats = [
                    forv_id for forv_id, arb_set in existing_workplaces.items()
                    if arbetsplats in arb_set
                ]

                # Om arbetsplatsen finns i flera förvaltningar, gör den regional
                if len(forvaltningar_med_samma_arbetsplats) > 1:
                    db.arbetsplatser.update_one(
                        {"namn": arbetsplats},
                        {
                            "$set": {
                                "namn": arbetsplats,
                                "alla_forvaltningar": True,
                                "forvaltning_id": None,
                                "forvaltning_namn": "Alla förvaltningar"
                            }
                        },
                        upsert=True
                    )
                else:
                    # Koppla arbetsplatsen till specifik förvaltning
                    db.arbetsplatser.update_one(
                        {"namn": arbetsplats, "forvaltning_id": forvaltning_id},
                        {
                            "$set": {
                                "namn": arbetsplats,
                                "alla_forvaltningar": False,
                                "forvaltning_id": forvaltning_id,
                                "forvaltning_namn": forvaltning["namn"]
                            }
                        },
                        upsert=True
                    )


def load_cached_data(db):
    """Laddar och cachar data för att minska databasanrop"""
    if 'workplace_cached_data' not in st.session_state:
        st.session_state.workplace_cached_data = {
            'forvaltningar': list(db.forvaltningar.find()),
            'avdelningar': list(db.avdelningar.find()),
            'enheter': list(db.enheter.find()),
            'arbetsplatser': list(db.arbetsplatser.find()),
            'personer': list(db.personer.find())
        }

        # Skapa index för snabbare uppslag
        st.session_state.workplace_indexes = {
            'avdelningar_by_forv': {},
            'enheter_by_avd': {},
            'personer_by_arbetsplats': defaultdict(list)
        }

        # Indexera avdelningar per förvaltning
        for avd in st.session_state.workplace_cached_data['avdelningar']:
            forv_id = avd['forvaltning_id']
            if forv_id not in st.session_state.workplace_indexes['avdelningar_by_forv']:
                st.session_state.workplace_indexes['avdelningar_by_forv'][forv_id] = []
            st.session_state.workplace_indexes['avdelningar_by_forv'][forv_id].append(avd)

        # Indexera enheter per avdelning
        for enhet in st.session_state.workplace_cached_data['enheter']:
            avd_id = enhet['avdelning_id']
            if avd_id not in st.session_state.workplace_indexes['enheter_by_avd']:
                st.session_state.workplace_indexes['enheter_by_avd'][avd_id] = []
            st.session_state.workplace_indexes['enheter_by_avd'][avd_id].append(enhet)

        # Indexera personer per arbetsplats
        for person in st.session_state.workplace_cached_data['personer']:
            if person.get('arbetsplats'):
                for arbetsplats in person['arbetsplats']:
                    st.session_state.workplace_indexes['personer_by_arbetsplats'][arbetsplats].append(person)


def refresh_workplace_cache(db):
    """Uppdaterar cachad data"""
    if 'workplace_cached_data' in st.session_state:
        del st.session_state.workplace_cached_data
    if 'workplace_indexes' in st.session_state:
        del st.session_state.workplace_indexes
    load_cached_data(db)


def show(db):
    """Visar och hanterar huvudgränssnittet för arbetsplatshantering.
    
    Denna komplexa funktion hanterar tre huvudområden:
    1. Datahämtning och Cachning
       - Implementerar effektiv cachning via session state
       - Tillhandahåller uppdateringsmekanism för data
    
    2. Arbetsplatshantering (Tab 1)
       - Skapar nya arbetsplatser (regionala eller förvaltningsspecifika)
       - Hanterar adressinformation och geografiska koordinater
       - Validerar indata och förhindrar dubletter
    
    3. Medlemshantering (Tab 2)
       - Visar och uppdaterar medlemsantal
       - Hanterar medlemsfördelning mellan enheter
       - Beräknar statistik och summor
    
    Tekniska detaljer:
    - Använder Streamlit för UI-komponenter
    - Implementerar formulärvalidering
    - Hanterar MongoDB-operationer
    - Tillhandahåller realtidsuppdateringar
    
    Args:
        db: MongoDB-databasanslutning med tillgång till collections för:
           - forvaltningar
           - arbetsplatser
           - avdelningar
           - enheter
           - personer
    """
    st.header("Hantera Arbetsplatser")

    # Initiera session state variabler
    if 'arbetsplatser' not in st.session_state:
        st.session_state.arbetsplatser = []
    if 'forvaltningar' not in st.session_state:
        st.session_state.forvaltningar = []
    if 'ny_arbetsplats' not in st.session_state:
        st.session_state.ny_arbetsplats = False
    if 'redigering_forvaltning' not in st.session_state:
        st.session_state.redigering_forvaltning = {}
    if 'redigering_avdelning' not in st.session_state:
        st.session_state.redigering_avdelning = {}
    if 'redigering_enhet' not in st.session_state:
        st.session_state.redigering_enhet = {}

    # Ladda cachad data
    cached, indexes = get_cached_data(db)

    # Uppdatera session state med cachad data
    st.session_state.arbetsplatser = cached['arbetsplatser']
    st.session_state.forvaltningar = cached['forvaltningar']

    # Uppdateringsknapp i sidofältet
    if st.sidebar.button("↻ Uppdatera data", key="refresh_workplaces_sidebar"):
        cached, indexes = get_cached_data(db, force_refresh=True)
        st.rerun()

    # Huvudflikar för separation av funktionalitet
    tab1, tab2 = st.tabs(["Hantera Arbetsplatser", "Hantera Medlemsantal"])

    with tab1:
        # Använd cachad data
        forvaltningar = cached['forvaltningar']
        arbetsplatser = cached['arbetsplatser']
        globala_arbetsplatser = indexes['globala_arbetsplatser']

        # Sektion för att lägga till ny arbetsplats
        with st.expander("Lägg till Arbetsplats"):
            with st.form("add_workplace"):
                # Grundläggande information
                namn = st.text_input("Namn på arbetsplats")

                # Adressinformation i två kolumner för bättre layout
                col1, col2 = st.columns(2)
                with col1:
                    gatuadress = st.text_input("Gatuadress")
                    postnummer = st.text_input("Postnummer")
                with col2:
                    ort = st.text_input("Ort")
                    kommun = st.selectbox(
                        "Kommun",
                        options=KOMMUNER
                    )

                # Sektion för geografiska koordinater
                st.markdown("---")
                st.markdown("##### 📍 Koordinater (valfritt)")
                st.markdown("Om adressen inte hittas automatiskt kan du ange koordinater manuellt.")

                # Koordinatinmatning i två kolumner
                coord_col1, coord_col2 = st.columns(2)
                with coord_col1:
                    latitude = st.number_input("Latitud (t.ex. 57.7089)",
                                               min_value=55.0, max_value=62.0, value=58.0, step=0.0001,
                                               format="%.4f",
                                               help="Nordlig koordinat. För Västra Götaland mellan ca 57-59")
                with coord_col2:
                    longitude = st.number_input("Longitud (t.ex. 11.9746)",
                                                min_value=8.0, max_value=15.0, value=12.0, step=0.0001,
                                                format="%.4f",
                                                help="Östlig koordinat. För Västra Götaland mellan ca 11-14")

                use_coords = st.checkbox("✓ Använd dessa koordinater",
                                         help="Markera denna ruta om du vill använda koordinaterna ovan")

                # Val av förvaltning eller regional arbetsplats
                forvaltning = st.selectbox(
                    "Välj Förvaltning",
                    options=["Alla förvaltningar"] + [f["namn"] for f in forvaltningar],
                    key="forv_select_new"
                )

                if st.form_submit_button("Spara"):
                    if namn and gatuadress and postnummer and ort and kommun != "Välj kommun...":
                        with st.spinner('Sparar arbetsplats...'):
                            try:
                                if forvaltning == "Alla förvaltningar":
                                    # Kontrollera om arbetsplatsen redan finns som regional
                                    existing = next((ap for ap in globala_arbetsplatser if ap["namn"] == namn), None)

                                    if existing:
                                        st.error("Denna arbetsplats finns redan som regional arbetsplats")
                                    else:
                                        arbetsplats = {
                                            "namn": namn,
                                            "gatuadress": gatuadress,
                                            "postnummer": postnummer,
                                            "ort": ort,
                                            "kommun": kommun,
                                            "alla_forvaltningar": True,
                                            "forvaltning_id": None,
                                            "forvaltning_namn": "Alla förvaltningar",
                                            "coordinates": {"lat": latitude, "lng": longitude} if use_coords else None,
                                            "medlemsantal": 0
                                        }
                                        result = db.arbetsplatser.insert_one(arbetsplats)
                                        if result.inserted_id:
                                            arbetsplats['_id'] = result.inserted_id
                                            update_cache_after_change(db, 'arbetsplatser', 'create', arbetsplats)
                                            log_action("create", f"Skapade regional arbetsplats: {namn} i {kommun}",
                                                       "workplace")
                                            st.success("✅ Regional arbetsplats sparad!")
                                            st.rerun()
                                else:
                                    vald_forvaltning = next(f for f in forvaltningar if f["namn"] == forvaltning)
                                    forv_arbetsplatser = indexes['arbetsplatser_by_forv'].get(vald_forvaltning["_id"],
                                                                                              [])

                                    # Kontrollera om arbetsplatsen redan finns
                                    existing = next((ap for ap in forv_arbetsplatser if ap["namn"] == namn), None)
                                    if existing or any(ap["namn"] == namn for ap in globala_arbetsplatser):
                                        st.error("Denna arbetsplats finns redan")
                                    else:
                                        arbetsplats = {
                                            "namn": namn,
                                            "gatuadress": gatuadress,
                                            "postnummer": postnummer,
                                            "ort": ort,
                                            "kommun": kommun,
                                            "alla_forvaltningar": False,
                                            "forvaltning_id": vald_forvaltning["_id"],
                                            "forvaltning_namn": vald_forvaltning["namn"],
                                            "medlemsantal": 0
                                        }
                                        result = db.arbetsplatser.insert_one(arbetsplats)
                                        if result.inserted_id:
                                            arbetsplats['_id'] = result.inserted_id
                                            update_cache_after_change(db, 'arbetsplatser', 'create', arbetsplats)
                                            log_action("create", f"Skapade arbetsplats: {namn} i {kommun}", "workplace")
                                            st.success("✅ Arbetsplats sparad!")
                                            st.rerun()
                            except Exception as e:
                                st.error(f"❌ Ett fel uppstod: {str(e)}")

        st.divider()

        # Visa befintliga arbetsplatser
        st.subheader("Befintliga Arbetsplatser")

        # Visa regionala arbetsplatser först i en egen sektion
        if globala_arbetsplatser:
            with st.expander(f"Regionala Arbetsplatser ({len(globala_arbetsplatser)})"):
                st.markdown("##### Regionala Arbetsplatser")
                for arbetsplats in globala_arbetsplatser:
                    with st.expander(f"{arbetsplats['namn']}"):
                        with st.form(f"edit_global_workplace_{arbetsplats['_id']}"):
                            # Visa och möjliggör redigering av arbetsplatsdata
                            col1, col2 = st.columns(2)
                            with col1:
                                nytt_namn = st.text_input("Namn", 
                                    value=arbetsplats["namn"],
                                    key=f"namn_global_{arbetsplats['_id']}")
                                ny_gatuadress = st.text_input("Gatuadress", 
                                    value=arbetsplats.get("gatuadress", ""),
                                    key=f"gatuadress_global_{arbetsplats['_id']}")
                                nytt_postnummer = st.text_input("Postnummer", 
                                    value=arbetsplats.get("postnummer", ""),
                                    key=f"postnummer_global_{arbetsplats['_id']}")
                            with col2:
                                ny_ort = st.text_input("Ort", 
                                    value=arbetsplats.get("ort", ""),
                                    key=f"ort_global_{arbetsplats['_id']}")
                                ny_kommun = st.selectbox("Kommun",
                                    options=KOMMUNER,
                                    index=KOMMUNER.index(arbetsplats.get("kommun", "Välj kommun...")),
                                    key=f"kommun_global_{arbetsplats['_id']}")

                            # Koordinatinmatning
                            st.markdown("##### 📍 Koordinater")
                            coord_col1, coord_col2 = st.columns(2)
                            with coord_col1:
                                ny_lat = st.number_input("Latitud",
                                    value=float(arbetsplats.get("coordinates", {}).get("lat", 58.0)),
                                    min_value=55.0,
                                    max_value=62.0,
                                    step=0.0001,
                                    format="%.4f",
                                    help="Nordlig koordinat. För Västra Götaland mellan ca 57-59",
                                    key=f"lat_global_{arbetsplats['_id']}")
                            with coord_col2:
                                ny_lng = st.number_input("Longitud",
                                    value=float(arbetsplats.get("coordinates", {}).get("lng", 12.0)),
                                    min_value=8.0,
                                    max_value=15.0,
                                    step=0.0001,
                                    format="%.4f",
                                    help="Östlig koordinat. För Västra Götaland mellan ca 11-14",
                                    key=f"lng_global_{arbetsplats['_id']}")
                            
                            # Knappar för att spara eller ta bort
                            col1, col2 = st.columns(2)
                            with col1:
                                if st.form_submit_button("Spara ändringar"):
                                    update_data = {
                                        "namn": nytt_namn,
                                        "gatuadress": ny_gatuadress,
                                        "postnummer": nytt_postnummer,
                                        "ort": ny_ort,
                                        "kommun": ny_kommun,
                                        "coordinates": {
                                            "lat": ny_lat,
                                            "lng": ny_lng
                                        }
                                    }
                                    
                                    result = db.arbetsplatser.update_one(
                                        {"_id": arbetsplats["_id"]},
                                        {"$set": update_data}
                                    )
                                    
                                    if result.modified_count > 0:
                                        update_cache_after_change(db, 'arbetsplatser', 'update')
                                        log_action("update", f"Uppdaterade regional arbetsplats: {arbetsplats['namn']}", "workplace")
                                        st.success("✅ Regional arbetsplats uppdaterad!")
                                        st.rerun()
                            
                            with col2:
                                if st.form_submit_button("Ta bort", type="secondary"):
                                    personer_pa_arbetsplats = indexes['personer_by_arbetsplats'].get(arbetsplats["namn"], [])
                                    if personer_pa_arbetsplats:
                                        st.error("❌ Kan inte ta bort arbetsplats som har personer")
                                    else:
                                        db.arbetsplatser.delete_one({"_id": arbetsplats["_id"]})
                                        update_cache_after_change(db, 'arbetsplatser', 'delete')
                                        log_action("delete", f"Tog bort regional arbetsplats: {arbetsplats['namn']}", "workplace")
                                        st.success("✅ Regional arbetsplats borttagen!")
                                        st.rerun()

        # Visa förvaltningsspecifika arbetsplatser
        st.markdown("### Förvaltningsspecifika Arbetsplatser")
        for forv in forvaltningar:
            forv_arbetsplatser = indexes['arbetsplatser_by_forv'].get(forv["_id"], [])

            if forv_arbetsplatser:
                with st.expander(f"{forv['namn']} - {len(forv_arbetsplatser)} arbetsplatser"):
                    for arbetsplats in forv_arbetsplatser:
                        with st.expander(f"{arbetsplats['namn']}"):
                            with st.form(f"edit_workplace_{arbetsplats['_id']}"):
                                # Visa och möjliggör redigering av arbetsplatsdata
                                col1, col2 = st.columns(2)
                                with col1:
                                    nytt_namn = st.text_input("Namn",
                                                                  value=arbetsplats["namn"],
                                                                  key=f"namn_{arbetsplats['_id']}")
                                    ny_gatuadress = st.text_input("Gatuadress",
                                                                      value=arbetsplats.get("gatuadress", ""),
                                                                      key=f"gatuadress_{arbetsplats['_id']}")
                                    nytt_postnummer = st.text_input("Postnummer",
                                                                    value=arbetsplats.get("postnummer", ""),
                                                                    key=f"postnummer_{arbetsplats['_id']}")
                                with col2:
                                    ny_ort = st.text_input("Ort",
                                                           value=arbetsplats.get("ort", ""),
                                                           key=f"ort_{arbetsplats['_id']}")
                                    ny_kommun = st.selectbox("Kommun",
                                                                 options=KOMMUNER,
                                                                 index=KOMMUNER.index(
                                                                     arbetsplats.get("kommun", "Välj kommun...")),
                                                                 key=f"kommun_{arbetsplats['_id']}")

                                # Koordinatinmatning
                                st.markdown("##### 📍 Koordinater")
                                coord_col1, coord_col2 = st.columns(2)
                                with coord_col1:
                                    ny_lat = st.number_input("Latitud",
                                        value=float(arbetsplats.get("coordinates", {}).get("lat", 58.0)),
                                        min_value=55.0,
                                        max_value=62.0,
                                        step=0.0001,
                                        format="%.4f",
                                        help="Nordlig koordinat. För Västra Götaland mellan ca 57-59",
                                        key=f"lat_{arbetsplats['_id']}")
                                with coord_col2:
                                    ny_lng = st.number_input("Longitud",
                                        value=float(arbetsplats.get("coordinates", {}).get("lng", 12.0)),
                                        min_value=8.0,
                                        max_value=15.0,
                                        step=0.0001,
                                        format="%.4f",
                                        help="Östlig koordinat. För Västra Götaland mellan ca 11-14",
                                        key=f"lng_{arbetsplats['_id']}")

                                # Knappar för att spara eller ta bort
                                col1, col2 = st.columns(2)
                                with col1:
                                    if st.form_submit_button("Spara ändringar"):
                                        update_data = {
                                            "namn": nytt_namn,
                                            "gatuadress": ny_gatuadress,
                                            "postnummer": nytt_postnummer,
                                            "ort": ny_ort,
                                            "kommun": ny_kommun,
                                            "coordinates": {
                                                "lat": ny_lat,
                                                "lng": ny_lng
                                            }
                                        }

                                        result = db.arbetsplatser.update_one(
                                            {"_id": arbetsplats["_id"]},
                                            {"$set": update_data}
                                        )

                                        if result.modified_count > 0:
                                            update_cache_after_change(db, 'arbetsplatser', 'update')
                                            log_action("update", f"Uppdaterade arbetsplats: {arbetsplats['namn']}",
                                                       "workplace")
                                            st.success("✅ Arbetsplats uppdaterad!")
                                            st.rerun()

                                with col2:
                                    if st.form_submit_button("Ta bort", type="secondary"):
                                        personer_pa_arbetsplats = indexes['personer_by_arbetsplats'].get(
                                            arbetsplats["namn"], [])
                                        if personer_pa_arbetsplats:
                                            st.error("❌ Kan inte ta bort arbetsplats som har personer")
                                        else:
                                            db.arbetsplatser.delete_one({"_id": arbetsplats["_id"]})
                                            update_cache_after_change(db, 'arbetsplatser', 'delete')
                                            log_action("delete", f"Tog bort arbetsplats: {arbetsplats['namn']}",
                                                       "workplace")
                                            st.success("✅ Arbetsplats borttagen!")
                                            st.rerun()

    with tab2:
        st.subheader("Hantera Medlemsantal")

        # Använd cachad data för optimerad prestanda
        # Detta minskar antalet databasanrop signifikant
        arbetsplatser = st.session_state.arbetsplatser
        forvaltningar = st.session_state.forvaltningar

        # Optimera gruppering av arbetsplatser
        # Samlar alla instanser av samma arbetsplats (både regionala och specifika)
        # för att möjliggöra effektiv hantering av medlemsantal
        grouped_workplaces = defaultdict(list)
        for arbetsplats in arbetsplatser:
            grouped_workplaces[arbetsplats["namn"]].append(arbetsplats)

        # Implementera avancerad cachning av organisationsstruktur
        # Detta är kritiskt för prestandan vid hantering av stora datamängder

        # Cache avdelningar per förvaltning
        # Skapar en hierarkisk struktur för snabb åtkomst
        if 'avdelningar_per_forvaltning' not in st.session_state:
            st.session_state.avdelningar_per_forvaltning = {}
            for forv in forvaltningar:
                st.session_state.avdelningar_per_forvaltning[str(forv["_id"])] = list(
                    db.avdelningar.find({"forvaltning_id": forv["_id"]})
                )

        # Cache enheter per avdelning
        # Kompletterar den hierarkiska strukturen för komplett organisationsträd
        if 'enheter_per_avdelning' not in st.session_state:
            st.session_state.enheter_per_avdelning = {}
            for forv in forvaltningar:
                for avd in st.session_state.avdelningar_per_forvaltning[str(forv["_id"])]:
                    st.session_state.enheter_per_avdelning[str(avd["_id"])] = list(
                        db.enheter.find({"avdelning_id": avd["_id"]})
                    )

        # Iterera över alla arbetsplatser och deras instanser
        # Hanterar både regionala och förvaltningsspecifika arbetsplatser
        for arbetsplats_namn, instances in grouped_workplaces.items():
            with st.expander(f"{arbetsplats_namn}"):
                st.write("Medlemsantal per förvaltning:")

                # Specialhantering för globala/regionala arbetsplatser
                # Dessa kan ha medlemmar i flera förvaltningar samtidigt
                if any(instance.get("alla_forvaltningar", False) for instance in instances):
                    global_instance = next(
                        instance for instance in instances if instance.get("alla_forvaltningar", False))

                    # Hantera medlemsantal för global arbetsplats
                    # Detta är mer komplext då det involverar flera förvaltningar
                    forvaltningar = list(db.forvaltningar.find())
                    medlemmar_per_forv = global_instance.get("medlemmar_per_forvaltning", {})

                    with st.form(f"edit_global_members_{global_instance['_id']}"):
                        st.write("### Global arbetsplats")

                        # Komplex nästlad struktur för medlemshantering
                        # Hanterar förvaltningar -> avdelningar -> enheter
                        nya_medlemmar = {}
                        for forv in forvaltningar:
                            forv_id_str = str(forv["_id"])

                            # Beräkna och visa aktuellt medlemsantal för förvaltningen
                            current_total = sum(
                                medlemmar_per_forv.get(forv_id_str, {}).get("enheter", {}).values()
                            )

                            # Expanderbar sektion per förvaltning
                            with st.expander(f"{forv['namn']} - Medlemmar: {current_total}"):
                                # Hämta och visa avdelningsstruktur
                                avdelningar = list(db.avdelningar.find({"forvaltning_id": forv["_id"]}))
                                medlemmar_denna_forv = {}

                                # Nästlad struktur för avdelningar
                                for avd in avdelningar:
                                    with st.expander(f"{avd['namn']}"):
                                        # Hantera enheter inom avdelningen
                                        enheter = list(db.enheter.find({"avdelning_id": avd["_id"]}))

                                        # Inmatningsfält för medlemsantal per enhet
                                        for enhet in enheter:
                                            enhet_id_str = str(enhet["_id"])
                                            current_members = medlemmar_per_forv.get(forv_id_str, {}).get("enheter",
                                                                                                          {}).get(
                                                enhet_id_str, 0)

                                            medlemsantal = st.number_input(
                                                f"Antal medlemmar i {enhet['namn']}",
                                                min_value=0,
                                                value=int(current_members),
                                                key=f"medlemmar_global_{global_instance['_id']}_{forv_id_str}_{enhet_id_str}"
                                            )

                                            # Uppdatera medlemsantal om det finns medlemmar
                                            if medlemsantal > 0:
                                                if "enheter" not in medlemmar_denna_forv:
                                                    medlemmar_denna_forv["enheter"] = {}
                                                medlemmar_denna_forv["enheter"][enhet_id_str] = medlemsantal

                                # Spara medlemsdata för förvaltningen
                                if medlemmar_denna_forv:
                                    nya_medlemmar[forv_id_str] = medlemmar_denna_forv

                                # Visa totalt antal medlemmar för förvaltningen
                                total_forv = sum(
                                    medlemmar_denna_forv.get("enheter", {}).values()
                                )
                                if total_forv > 0:
                                    st.info(f"Totalt antal medlemmar i denna förvaltning: {total_forv}")

                        # Hantera uppdatering av medlemsantal
                        if st.form_submit_button("Uppdatera medlemsantal", use_container_width=True):
                            # Spåra ändringar för loggning
                            changes = []
                            for forv in forvaltningar:
                                forv_id_str = str(forv["_id"])
                                gamla_data = medlemmar_per_forv.get(forv_id_str, {})
                                nya_data = nya_medlemmar.get(forv_id_str, {})

                                # Identifiera och logga ändringar
                                if gamla_data != nya_data:
                                    gamla_total = sum(gamla_data.get("enheter", {}).values())
                                    nya_total = sum(nya_data.get("enheter", {}).values())
                                    changes.append(f"{forv['namn']}: {gamla_total} → {nya_total}")

                            # Uppdatera databasen och logga ändringar
                            if changes:
                                db.arbetsplatser.update_one(
                                    {"_id": global_instance["_id"]},
                                    {"$set": {"medlemmar_per_forvaltning": nya_medlemmar}}
                                )
                                log_action("update",
                                           f"Uppdaterade medlemsantal för global arbetsplats {arbetsplats_namn}. " +
                                           f"Ändringar: {', '.join(changes)}",
                                           "workplace"
                                           )
                                st.success("✅ Medlemsantal uppdaterat!")
                                st.rerun()

                else:
                    # Hantering av förvaltningsspecifika arbetsplatser
                    # Enklare struktur då de endast tillhör en förvaltning
                    for instance in instances:
                        with st.form(f"edit_members_{instance['_id']}"):
                            st.write(f"### {instance['forvaltning_namn']}")

                            # Hämta organisationsstruktur för förvaltningen
                            avdelningar = list(db.avdelningar.find({"forvaltning_id": instance["forvaltning_id"]}))
                            medlemmar_per_enhet = instance.get("medlemmar_per_enhet", {})

                            # Hantera medlemsantal per enhet
                            nya_medlemmar = {}
                            total_medlemmar = 0

                            # Nästlad struktur för avdelningar och enheter
                            for avd in avdelningar:
                                with st.expander(f"{avd['namn']}"):
                                    enheter = list(db.enheter.find({"avdelning_id": avd["_id"]}))

                                    # Inmatningsfält för medlemsantal per enhet
                                    for enhet in enheter:
                                        enhet_id_str = str(enhet["_id"])
                                        medlemsantal = st.number_input(
                                            f"Antal medlemmar i {enhet['namn']}",
                                            min_value=0,
                                            value=int(medlemmar_per_enhet.get(enhet_id_str, 0)),
                                            key=f"medlemmar_specific_{instance['_id']}_{enhet_id_str}_{avd['_id']}"
                                        )

                                        # Uppdatera totaler om det finns medlemmar
                                        if medlemsantal > 0:
                                            nya_medlemmar[enhet_id_str] = medlemsantal
                                            total_medlemmar += medlemsantal

                            # Visa totalt antal medlemmar
                            st.info(f"Totalt antal medlemmar: {total_medlemmar}")

                            # Hantera uppdatering av medlemsantal
                            if st.form_submit_button("Uppdatera medlemsantal", use_container_width=True):
                                if nya_medlemmar != medlemmar_per_enhet:
                                    # Uppdatera databasen med nya medlemsantal
                                    db.arbetsplatser.update_one(
                                        {"_id": instance["_id"]},
                                        {"$set": {
                                            "medlemmar_per_enhet": nya_medlemmar,
                                            "medlemsantal": total_medlemmar
                                        }}
                                    )
                                    # Logga ändringar
                                    log_action("update",
                                               f"Uppdaterade medlemsantal för arbetsplats {arbetsplats_namn} "
                                               f"under {instance['forvaltning_namn']} " +
                                               f"från {instance.get('medlemsantal', 0)} till {total_medlemmar}",
                                               "workplace"
                                               )
                                    st.success("✅ Medlemsantal uppdaterat!")
                                    st.rerun()
