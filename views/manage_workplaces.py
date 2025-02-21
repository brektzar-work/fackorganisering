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


def migrate_workplaces(db):
    """
    Migrerar arbetsplatser från persondata till egen collection.
    Identifierar och skapar regionala arbetsplatser.
    """
    # Hämta alla unika arbetsplatser från personer
    existing_workplaces = defaultdict(set)  # förvaltning_id -> set of arbetsplatser
    
    # Samla alla unika arbetsplatser per förvaltning
    # Använder set för att automatiskt eliminera dubletter
    for person in db.personer.find():
        if person.get('arbetsplats'):
            for ap in person['arbetsplats']:
                existing_workplaces[str(person['forvaltning_id'])].add(ap)
    
    # Kontrollera om arbetsplatser redan har migrerats
    # Detta förhindrar dubbelmigrering av data
    if db.arbetsplatser.count_documents({}) > 0:
        return
    
    # Iterera över alla förvaltningar och deras arbetsplatser
    for forv_id, arbetsplatser in existing_workplaces.items():
        forvaltning = db.forvaltningar.find_one({"_id": ObjectId(forv_id)})
        
        # Identifiera arbetsplatser som finns i flera förvaltningar
        for ap_namn in arbetsplatser:
            ap_count = sum(1 for f_id, aps in existing_workplaces.items() if ap_namn in aps)
            
            # Om arbetsplatsen finns i flera förvaltningar, gör den regional
            if ap_count > 1:
                if not db.arbetsplatser.find_one({"namn": ap_namn}):
                    db.arbetsplatser.insert_one({
                        "namn": ap_namn,
                        "alla_forvaltningar": True
                    })
            else:
                # Koppla arbetsplatsen till specifik förvaltning
                if not db.arbetsplatser.find_one({"namn": ap_namn}):
                    db.arbetsplatser.insert_one({
                        "namn": ap_namn,
                        "forvaltning_id": ObjectId(forv_id),
                        "forvaltning_namn": forvaltning["namn"]
                    })


def create_indexes(db):
    """
    Skapar index för snabbare sökningar i databasen.
    """
    # Skapa index för snabbare uppslag
    db.arbetsplatser.create_index([("namn", 1)], unique=True)
    db.arbetsplatser.create_index([("forvaltning_id", 1)])
    db.arbetsplatser.create_index([("alla_forvaltningar", 1)])
    
    # Indexera avdelningar per förvaltning
    db.avdelningar.create_index([("forvaltning_id", 1)])
    db.avdelningar.create_index([("namn", 1), ("forvaltning_id", 1)], unique=True)
    
    # Indexera enheter per avdelning
    db.enheter.create_index([("avdelning_id", 1)])
    db.enheter.create_index([("forvaltning_id", 1)])
    db.enheter.create_index([("namn", 1), ("avdelning_id", 1)], unique=True)
    
    # Indexera personer per arbetsplats
    db.personer.create_index([("arbetsplats", 1)])
    db.personer.create_index([("forvaltning_id", 1)])
    db.personer.create_index([("avdelning_id", 1)])
    db.personer.create_index([("enhet_id", 1)])


def show(db):
    """
    Visar och hanterar gränssnittet för arbetsplatser.
    Hanterar både regionala och förvaltningsspecifika arbetsplatser.
    """
    # Ladda cachad data
    cached, indexes = get_cached_data(db)
    
    # Initiera session state variabler
    if 'edit_arbetsplats' not in st.session_state:
        st.session_state.edit_arbetsplats = None
    if 'edit_medlemmar' not in st.session_state:
        st.session_state.edit_medlemmar = None
    if 'arbetsplats_typ' not in st.session_state:
        st.session_state.arbetsplats_typ = "Regional Arbetsplats"
    
    # Uppdatera session state med cachad data
    st.session_state.cached = cached
    
    # Huvudflikar för separation av funktionalitet
    tabs = st.tabs(["Hantera Arbetsplatser", "Hantera Medlemsantal"])
    
    # Använd cachad data
    with tabs[0]:
        st.header("Hantera Arbetsplatser")
        
        # Sektion för att lägga till ny arbetsplats
        with st.expander("Lägg till Arbetsplats", expanded=True):
            # Val av förvaltningsspecifik eller regional arbetsplats (utanför formuläret)
            is_forvaltningsspecifik = st.checkbox(
                "Förvaltningsspecifik arbetsplats",
                help="Markera om arbetsplatsen endast ska tillhöra en specifik förvaltning"
            )
            
            if is_forvaltningsspecifik:
                st.info("En förvaltningsspecifik arbetsplats är endast tillgänglig för den valda förvaltningen. Endast personer från den valda förvaltningen kan tillhöra denna arbetsplats.")
            else:
                st.info("En regional arbetsplats är tillgänglig för alla förvaltningar. Detta betyder att personer från vilken förvaltning som helst kan tillhöra denna arbetsplats.")

            with st.form("add_arbetsplats"):
                # Grundläggande information
                namn = st.text_input("Namn på arbetsplats")
                
                # Adressinformation i två kolumner för bättre layout
                col1, col2 = st.columns(2)
                with col1:
                    gatuadress = st.text_input("Gatuadress")
                    postnummer = st.text_input("Postnummer")
                with col2:
                    ort = st.text_input("Ort")
                    kommun = st.selectbox("Kommun", KOMMUNER)
                
                # Sektion för geografiska koordinater
                st.markdown("##### Geografiska Koordinater")
                st.markdown("*Används för att visa arbetsplatsen på kartan*")
                
                # Koordinatinmatning i två kolumner
                col1, col2 = st.columns(2)
                with col1:
                    lat = st.text_input(
                        "Latitud",
                        help="T.ex. 57.7089 (Göteborg)"
                    )
                with col2:
                    lon = st.text_input(
                        "Longitud",
                        help="T.ex. 11.9746 (Göteborg)"
                    )
                
                # Förvaltningsval om det är en förvaltningsspecifik arbetsplats
                if is_forvaltningsspecifik:
                    if not cached['forvaltningar']:
                        st.warning("Lägg till minst en förvaltning först")
                        forv_namn = None
                        vald_forv = None
                    else:
                        forv_namn = st.selectbox(
                            "Förvaltning",
                            options=[f["namn"] for f in cached['forvaltningar']]
                        )
                        vald_forv = next(f for f in cached['forvaltningar'] if f["namn"] == forv_namn)
                else:
                    forv_namn = None
                    vald_forv = None
                
                # Spara arbetsplats
                if st.form_submit_button("Lägg till arbetsplats"):
                    if not namn:
                        st.error("Namn på arbetsplats måste anges")
                    elif is_forvaltningsspecifik and not forv_namn:
                        st.error("Välj en förvaltning för arbetsplatsen")
                    else:
                        # Skapa arbetsplatsobjekt
                        arbetsplats = {
                            "namn": namn,
                            "gatuadress": gatuadress,
                            "postnummer": postnummer,
                            "ort": ort,
                            "kommun": kommun,
                            "lat": float(lat) if lat else None,
                            "lon": float(lon) if lon else None,
                            "alla_forvaltningar": not is_forvaltningsspecifik
                        }

                        # Lägg till förvaltningsinformation om det är en förvaltningsspecifik arbetsplats
                        if is_forvaltningsspecifik and vald_forv:
                            arbetsplats["forvaltning_id"] = vald_forv["_id"]
                            arbetsplats["forvaltning_namn"] = vald_forv["namn"]

                        # Spara till databasen
                        result = db.arbetsplatser.insert_one(arbetsplats)
                        if result.inserted_id:
                            arbetsplats['_id'] = result.inserted_id
                            update_cache_after_change(db, 'arbetsplatser', 'create', arbetsplats)
                            log_action("create", f"Skapade arbetsplats: {namn}", "arbetsplats")
                            st.success("Arbetsplats tillagd!")
                            st.rerun()
                        else:
                            st.error("Kunde inte lägga till arbetsplatsen")
        
        # Visa befintliga arbetsplatser
        st.markdown("### Befintliga Arbetsplatser")
        
        # Visa regionala arbetsplatser först i en egen sektion
        regionala = [ap for ap in cached['arbetsplatser'] if ap.get('alla_forvaltningar')]
        if regionala:
            st.write("### Regionala Arbetsplatser")
            for ap in sorted(regionala, key=lambda x: x['namn']):
                with st.expander(ap['namn']):
                    with st.form(f"edit_regional_{ap['_id']}"):
                        nytt_namn = st.text_input("Namn", value=ap['namn'])
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            ny_gatuadress = st.text_input("Gatuadress", value=ap.get('gatuadress', ''))
                            nytt_postnummer = st.text_input("Postnummer", value=ap.get('postnummer', ''))
                        with col2:
                            ny_ort = st.text_input("Ort", value=ap.get('ort', ''))
                            ny_kommun = st.selectbox("Kommun", KOMMUNER, index=KOMMUNER.index(ap.get('kommun', 'Göteborg')))
                        
                        # Knappar för att spara eller ta bort
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.form_submit_button("Spara Ändringar"):
                                if not nytt_namn:
                                    st.error("Ange ett namn för arbetsplatsen")
                                elif nytt_namn != ap['namn'] and any(a['namn'] == nytt_namn for a in cached['arbetsplatser']):
                                    st.error("En arbetsplats med detta namn finns redan")
                                else:
                                    db.arbetsplatser.update_one(
                                        {"_id": ap["_id"]},
                                        {"$set": {
                                            "namn": nytt_namn,
                                            "gatuadress": ny_gatuadress,
                                            "postnummer": nytt_postnummer,
                                            "ort": ny_ort,
                                            "kommun": ny_kommun
                                        }}
                                    )
                                    log_action("update", f"Uppdaterade regional arbetsplats: {ap['namn']} -> {nytt_namn}", "workplace")
                                    update_cache_after_change(db, 'arbetsplatser', 'update')
                                    st.success("Arbetsplats uppdaterad!")
                                    st.rerun()
                        
                        with col2:
                            if st.form_submit_button("Ta Bort", type="primary"):
                                if any(p.get('arbetsplats') and ap['namn'] in p['arbetsplats'] for p in cached['personer']):
                                    st.error("Kan inte ta bort arbetsplatsen eftersom den har kopplade personer")
                                else:
                                    db.arbetsplatser.delete_one({"_id": ap["_id"]})
                                    log_action("delete", f"Tog bort regional arbetsplats: {ap['namn']}", "workplace")
                                    update_cache_after_change(db, 'arbetsplatser', 'delete')
                                    st.success("Arbetsplats borttagen!")
                                    st.rerun()
        
        # Visa förvaltningsspecifika arbetsplatser
        st.markdown("### Förvaltningsspecifika Arbetsplatser")
        for forv in sorted(cached['forvaltningar'], key=lambda x: x['namn']):
            with st.expander(forv['namn']):
                arbetsplatser = sorted(
                    [ap for ap in cached['arbetsplatser'] 
                     if not ap.get('alla_forvaltningar') and str(ap.get('forvaltning_id')) == str(forv['_id'])],
                    key=lambda x: x['namn']
                )
                
                if not arbetsplatser:
                    st.info("Inga arbetsplatser i denna förvaltning")
                else:
                    for ap in arbetsplatser:
                        # Visa och möjliggör redigering av arbetsplatsdata
                        with st.form(f"edit_arbetsplats_{ap['_id']}"):
                            nytt_namn = st.text_input("Namn", value=ap['namn'])
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                ny_gatuadress = st.text_input("Gatuadress", value=ap.get('gatuadress', ''))
                                nytt_postnummer = st.text_input("Postnummer", value=ap.get('postnummer', ''))
                            with col2:
                                ny_ort = st.text_input("Ort", value=ap.get('ort', ''))
                                ny_kommun = st.selectbox("Kommun", KOMMUNER, index=KOMMUNER.index(ap.get('kommun', 'Göteborg')))
                            
                            # Koordinatinmatning
                            st.markdown("##### Geografiska Koordinater")
                            col1, col2 = st.columns(2)
                            with col1:
                                ny_lat = st.text_input(
                                    "Latitud",
                                    value=str(ap.get('lat', '')),
                                    help="T.ex. 57.7089 (Göteborg)"
                                )
                            with col2:
                                ny_lon = st.text_input(
                                    "Longitud",
                                    value=str(ap.get('lon', '')),
                                    help="T.ex. 11.9746 (Göteborg)"
                                )
                            
                            # Knappar för att spara eller ta bort
                            col1, col2 = st.columns(2)
                            with col1:
                                if st.form_submit_button("Spara Ändringar"):
                                    if not nytt_namn:
                                        st.error("Ange ett namn för arbetsplatsen")
                                    elif nytt_namn != ap['namn'] and any(a['namn'] == nytt_namn for a in cached['arbetsplatser']):
                                        st.error("En arbetsplats med detta namn finns redan")
                                    else:
                                        update_data = {
                                            "namn": nytt_namn,
                                            "gatuadress": ny_gatuadress,
                                            "postnummer": nytt_postnummer,
                                            "ort": ny_ort,
                                            "kommun": ny_kommun
                                        }
                                        
                                        if ny_lat and ny_lon:
                                            try:
                                                update_data["lat"] = float(ny_lat)
                                                update_data["lon"] = float(ny_lon)
                                            except ValueError:
                                                st.error("Ogiltigt format för koordinater")
                                                return
                                        
                                        db.arbetsplatser.update_one(
                                            {"_id": ap["_id"]},
                                            {"$set": update_data}
                                        )
                                        log_action("update", f"Uppdaterade arbetsplats: {ap['namn']} -> {nytt_namn}", "workplace")
                                        update_cache_after_change(db, 'arbetsplatser', 'update')
                                        st.success("Arbetsplats uppdaterad!")
                                        st.rerun()
                            
                            with col2:
                                if st.form_submit_button("Ta Bort", type="primary"):
                                    if any(p.get('arbetsplats') and ap['namn'] in p['arbetsplats'] for p in cached['personer']):
                                        st.error("Kan inte ta bort arbetsplatsen eftersom den har kopplade personer")
                                    else:
                                        db.arbetsplatser.delete_one({"_id": ap["_id"]})
                                        log_action("delete", f"Tog bort arbetsplats: {ap['namn']}", "workplace")
                                        update_cache_after_change(db, 'arbetsplatser', 'delete')
                                        st.success("Arbetsplats borttagen!")
                                        st.rerun()
    
    # Använd cachad data för optimerad prestanda
    # Detta minskar antalet databasanrop signifikant
    with tabs[1]:
        st.header("Hantera Medlemsantal")
        
        # Optimera gruppering av arbetsplatser
        # Samlar alla instanser av samma arbetsplats (både regionala och specifika)
        # för att möjliggöra effektiv hantering av medlemsantal
        arbetsplatser_by_namn = defaultdict(list)
        
        # Implementera avancerad cachning av organisationsstruktur
        # Detta är kritiskt för prestandan vid hantering av stora datamängder
        
        # Cache avdelningar per förvaltning
        # Skapar en hierarkisk struktur för snabb åtkomst
        avdelningar_by_forv = defaultdict(list)
        for avd in cached['avdelningar']:
            avdelningar_by_forv[str(avd['forvaltning_id'])].append(avd)
        
        # Cachea enheter per avdelning
        # Kompletterar den hierarkiska strukturen för komplett organisationsträd
        enheter_by_avd = defaultdict(list)
        for enhet in cached['enheter']:
            enheter_by_avd[str(enhet['avdelning_id'])].append(enhet)
        
        # Iterera över alla arbetsplatser och deras instanser
        # Hanterar både regionala och förvaltningsspecifika arbetsplatser
        for ap in cached['arbetsplatser']:
            arbetsplatser_by_namn[ap['namn']].append(ap)
        
        # Specialhantering för regionala arbetsplatser
        # Dessa kan ha medlemmar i flera förvaltningar samtidigt
        for ap_namn, instanser in arbetsplatser_by_namn.items():
            if any(ap.get('alla_forvaltningar') for ap in instanser):
                # Hantera medlemsantal för regional arbetsplats
                # Detta är mer komplext då det involverar flera förvaltningar
                regional_ap = next(ap for ap in instanser if ap.get('alla_forvaltningar'))
                
                st.write("### Regional arbetsplats")
                with st.expander(ap_namn):
                    # Komplex nästlad struktur för medlemshantering
                    # Hanterar förvaltningar -> avdelningar -> enheter
                    for forv in sorted(cached['forvaltningar'], key=lambda x: x['namn']):
                        total_medlemmar = 0
                        
                        # Beräkna och visa aktuellt medlemsantal för förvaltningen
                        personer_i_forv = [p for p in cached['personer'] 
                                         if str(p['forvaltning_id']) == str(forv['_id'])]
                        
                        # Expanderbar sektion per förvaltning
                        with st.expander(forv['namn']):
                            # Hämta och visa avdelningsstruktur
                            avdelningar = sorted(
                                avdelningar_by_forv[str(forv['_id'])],
                                key=lambda x: x['namn']
                            )
                            
                            # Nästlad struktur för avdelningar
                            for avd in avdelningar:
                                st.write(f"#### {avd['namn']}")
                                
                                # Hantera enheter inom avdelningen
                                enheter = sorted(enheter_by_avd[str(avd['_id'])], key=lambda x: x['namn'])
                                for enhet in enheter:
                                    # Inmatningsfält för medlemsantal per enhet
                                    personer_i_enhet = [
                                        p for p in personer_i_forv 
                                        if str(p['enhet_id']) == str(enhet['_id']) and 
                                        ap_namn in p.get('arbetsplats', [])
                                    ]
                                    
                                    antal = len(personer_i_enhet)
                                    total_medlemmar += antal
                                    
                                    st.write(f"##### {enhet['namn']}: {antal} medlemmar")
                            
                            # Uppdatera medlemsantal om det finns medlemmar
                            if total_medlemmar > 0:
                                st.write(f"**Totalt i {forv['namn']}: {total_medlemmar} medlemmar**")
                            else:
                                st.write("*Inga medlemmar i denna förvaltning*")
                        
                        # Spara medlemsdata för förvaltningen
                        if total_medlemmar > 0:
                            db.arbetsplatser.update_one(
                                {"_id": regional_ap["_id"]},
                                {"$set": {f"medlemmar_per_forv.{str(forv['_id'])}": total_medlemmar}}
                            )
                        
                        # Visa totalt antal medlemmar för förvaltningen
                        st.write(f"**{forv['namn']}: {total_medlemmar} medlemmar**")
            else:
                # Hantera uppdatering av medlemsantal
                for ap in instanser:
                    # Spåra ändringar för loggning
                    gamla_medlemmar = ap.get('beraknat_medlemsantal', 0)
                    nya_medlemmar = len([
                        p for p in cached['personer']
                        if ap['namn'] in p.get('arbetsplats', [])
                    ])
                    
                    # Identifiera och logga ändringar
                    if gamla_medlemmar != nya_medlemmar:
                        db.arbetsplatser.update_one(
                            {"_id": ap["_id"]},
                            {"$set": {"beraknat_medlemsantal": nya_medlemmar}}
                        )
                        
                        # Uppdatera databasen och logga ändringar
                        if gamla_medlemmar != nya_medlemmar:
                            log_action(
                                "update",
                                f"Uppdaterade medlemsantal för {ap['namn']}: {gamla_medlemmar} -> {nya_medlemmar}",
                                "workplace"
                            )
        
        # Hantering av förvaltningsspecifika arbetsplatser
        # Enklare struktur då de endast tillhör en förvaltning
        for forv in sorted(cached['forvaltningar'], key=lambda x: x['namn']):
            with st.expander(forv['namn']):
                # Hämta organisationsstruktur för förvaltningen
                avdelningar = sorted(
                    avdelningar_by_forv[str(forv['_id'])],
                    key=lambda x: x['namn']
                )
                
                # Hantera medlemsantal per enhet
                for avd in avdelningar:
                    st.write(f"#### {avd['namn']}")
                    
                    # Nästlad struktur för avdelningar och enheter
                    enheter = sorted(enheter_by_avd[str(avd['_id'])], key=lambda x: x['namn'])
                    for enhet in enheter:
                        # Inmatningsfält för medlemsantal per enhet
                        arbetsplatser = [ap for ap in cached['arbetsplatser'] 
                                       if str(ap.get('enhet_id')) == str(enhet['_id'])]
                        
                        if arbetsplatser:
                            st.write(f"##### {enhet['namn']}")
                            for ap in sorted(arbetsplatser, key=lambda x: x['namn']):
                                antal = len([p for p in cached['personer'] 
                                          if ap['namn'] in p.get('arbetsplats', [])])
                                st.write(f"- {ap['namn']}: {antal} medlemmar")
                        
                        # Uppdatera totaler om det finns medlemmar
                        total_medlemmar = sum(
                            len([p for p in cached['personer'] 
                                 if ap['namn'] in p.get('arbetsplats', [])])
                            for ap in arbetsplatser
                        )
                        
                        # Visa totalt antal medlemmar
                        if total_medlemmar > 0:
                            st.write(f"**Totalt i {enhet['namn']}: {total_medlemmar} medlemmar**")
                
                # Hantera uppdatering av medlemsantal
                for ap in [ap for ap in cached['arbetsplatser'] 
                          if str(ap.get('forvaltning_id')) == str(forv['_id'])]:
                    # Uppdatera databasen med nya medlemsantal
                    gamla_medlemmar = ap.get('beraknat_medlemsantal', 0)
                    nya_medlemmar = len([p for p in cached['personer'] 
                                       if ap['namn'] in p.get('arbetsplats', [])])
                    
                    # Logga ändringar
                    if gamla_medlemmar != nya_medlemmar:
                        db.arbetsplatser.update_one(
                            {"_id": ap["_id"]},
                            {"$set": {"beraknat_medlemsantal": nya_medlemmar}}
                        )
                        log_action(
                            "update",
                            f"Uppdaterade medlemsantal för {ap['namn']}: {gamla_medlemmar} -> {nya_medlemmar}",
                            "workplace"
                        )
