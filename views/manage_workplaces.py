import streamlit as st
from collections import defaultdict

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
    # Hämta alla unika arbetsplatser från personer
    personer = list(db.personer.find())
    existing_workplaces = defaultdict(set)  # förvaltning_id -> set of arbetsplatser
    
    # Samla alla unika arbetsplatser per förvaltning
    for person in personer:
        if person.get('arbetsplatser'):  # Ändrat från 'arbetsplats' till 'arbetsplatser'
            for arbetsplats in person['arbetsplatser']:  # Iterera över listan av arbetsplatser
                existing_workplaces[person['forvaltning_id']].add(arbetsplats)
    
    # Kontrollera om arbetsplatser redan har migrerats
    if db.arbetsplatser.count_documents({}) == 0:
        # Lägg till alla arbetsplatser i den nya kollektionen
        for forvaltning_id, arbetsplatser in existing_workplaces.items():
            # Hämta förvaltningsinfo
            forvaltning = db.forvaltningar.find_one({"_id": forvaltning_id})
            
            for arbetsplats in arbetsplatser:
                # Kontrollera om samma arbetsplats finns i flera förvaltningar
                forvaltningar_med_samma_arbetsplats = [
                    forv_id for forv_id, arb_set in existing_workplaces.items()
                    if arbetsplats in arb_set
                ]
                
                # Om arbetsplatsen finns i flera förvaltningar, gör den global
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
                    # Annars, koppla till specifik förvaltning
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

def show(db):
    # Kör migrering först
    migrate_existing_workplaces(db)
    
    st.header("Hantera Arbetsplatser")
    
    # Hämta alla förvaltningar
    forvaltningar = list(db.forvaltningar.find())
    
    # Lägg till ny arbetsplats
    with st.expander("Lägg till Arbetsplats"):
        with st.form("add_workplace"):
            namn = st.text_input("Namn på arbetsplats")
            
            # Adressinformation
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
            
            st.markdown("---")
            st.markdown("##### 📍 Koordinater (valfritt)")
            st.markdown("Om adressen inte hittas automatiskt kan du ange koordinater manuellt.")
            
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
            
            # Välj förvaltning för arbetsplatsen, inklusive "Alla"
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
                                # Kontrollera om arbetsplatsen redan finns som global
                                existing = db.arbetsplatser.find_one({
                                    "namn": namn,
                                    "alla_forvaltningar": True
                                })
                                
                                if existing:
                                    st.error("Denna arbetsplats finns redan som global arbetsplats")
                                else:
                                    # Spara ny global arbetsplats
                                    arbetsplats = {
                                        "namn": namn,
                                        "gatuadress": gatuadress,
                                        "postnummer": postnummer,
                                        "ort": ort,
                                        "kommun": kommun,
                                        "alla_forvaltningar": True,
                                        "forvaltning_id": None,
                                        "forvaltning_namn": "Alla förvaltningar",
                                        "coordinates": {"lat": latitude, "lng": longitude} if use_coords else None
                                    }
                                    result = db.arbetsplatser.insert_one(arbetsplats)
                                    
                                    if result.inserted_id:
                                        st.success("✅ Global arbetsplats sparad!")
                                        st.rerun()
                                    else:
                                        st.error("❌ Något gick fel när arbetsplatsen skulle sparas")
                            else:
                                vald_forvaltning = next(f for f in forvaltningar if f["namn"] == forvaltning)
                                # Kontrollera om arbetsplatsen redan finns i den valda förvaltningen
                                existing = db.arbetsplatser.find_one({
                                    "namn": namn,
                                    "$or": [
                                        {"forvaltning_id": vald_forvaltning["_id"]},
                                        {"alla_forvaltningar": True}
                                    ]
                                })
                                
                                if existing:
                                    st.error("Denna arbetsplats finns redan i den valda förvaltningen eller som global arbetsplats")
                                else:
                                    # Spara ny arbetsplats för specifik förvaltning
                                    arbetsplats = {
                                        "namn": namn,
                                        "gatuadress": gatuadress,
                                        "postnummer": postnummer,
                                        "ort": ort,
                                        "kommun": kommun,
                                        "alla_forvaltningar": False,
                                        "forvaltning_id": vald_forvaltning["_id"],
                                        "forvaltning_namn": vald_forvaltning["namn"]
                                    }
                                    result = db.arbetsplatser.insert_one(arbetsplats)
                                    
                                    if result.inserted_id:
                                        st.success("✅ Arbetsplats sparad!")
                                        st.rerun()
                                    else:
                                        st.error("❌ Något gick fel när arbetsplatsen skulle sparas")
                        except Exception as e:
                            st.error(f"❌ Ett fel uppstod: {str(e)}")
                else:
                    st.error("❌ Alla fält måste fyllas i och en kommun måste väljas")

    # Lista och hantera befintliga arbetsplatser
    st.subheader("Befintliga Arbetsplatser")
    
    # Filter för förvaltning
    filter_forv = st.selectbox(
        "Filtrera på förvaltning",
        options=["Alla"] + [f["namn"] for f in forvaltningar],
        key="filter_forv"
    )
    
    # Hämta arbetsplatser baserat på filter
    if filter_forv == "Alla":
        arbetsplatser = list(db.arbetsplatser.find())
    else:
        vald_forv = next(f for f in forvaltningar if f["namn"] == filter_forv)
        # Inkludera både förvaltningsspecifika och globala arbetsplatser
        arbetsplatser = list(db.arbetsplatser.find({
            "$or": [
                {"forvaltning_id": vald_forv["_id"]},
                {"alla_forvaltningar": True}
            ]
        }))
    
    # Visa arbetsplatser
    for arbetsplats in arbetsplatser:
        with st.expander(f"{arbetsplats['namn']} - {arbetsplats['forvaltning_namn']}"):
            with st.form(f"edit_workplace_{arbetsplats['_id']}"):
                nytt_namn = st.text_input("Namn", value=arbetsplats["namn"])
                
                # Adressinformation
                col1, col2 = st.columns(2)
                with col1:
                    ny_gatuadress = st.text_input("Gatuadress", 
                        value=arbetsplats.get("gatuadress", ""))
                    nytt_postnummer = st.text_input("Postnummer", 
                        value=arbetsplats.get("postnummer", ""))
                with col2:
                    ny_ort = st.text_input("Ort", 
                        value=arbetsplats.get("ort", ""))
                    ny_kommun = st.selectbox(
                        "Kommun",
                        options=KOMMUNER,
                        index=max(0, [i for i, k in enumerate(KOMMUNER) 
                            if k == arbetsplats.get("kommun", "Välj kommun...")][0])
                    )
                
                # Välj förvaltning, inklusive "Alla förvaltningar"
                ny_forvaltning = st.selectbox(
                    "Förvaltning",
                    options=["Alla förvaltningar"] + [f["namn"] for f in forvaltningar],
                    index=0 if arbetsplats.get("alla_forvaltningar") else 
                          [i + 1 for i, f in enumerate(forvaltningar) 
                           if f["_id"] == arbetsplats["forvaltning_id"]][0],
                    key=f"forv_select_{arbetsplats['_id']}"
                )
                
                # Manuella koordinater
                st.markdown("---")
                st.markdown("##### 📍 Koordinater (valfritt)")
                st.markdown("Om adressen inte hittas automatiskt kan du ange koordinater manuellt.")
                
                coord_col1, coord_col2 = st.columns(2)
                with coord_col1:
                    latitude = st.number_input("Latitud", 
                        min_value=55.0, max_value=62.0, 
                        value=float(arbetsplats.get("coordinates", {}).get("lat", 58.0)),
                        step=0.0001,
                        format="%.4f",
                        help="Nordlig koordinat. För Västra Götaland mellan ca 57-59",
                        key=f"lat_{arbetsplats['_id']}")
                with coord_col2:
                    longitude = st.number_input("Longitud", 
                        min_value=8.0, max_value=15.0, 
                        value=float(arbetsplats.get("coordinates", {}).get("lng", 12.0)),
                        step=0.0001,
                        format="%.4f",
                        help="Östlig koordinat. För Västra Götaland mellan ca 11-14",
                        key=f"lng_{arbetsplats['_id']}")
                
                use_coords = st.checkbox("✓ Använd dessa koordinater", 
                    value=arbetsplats.get("coordinates") is not None,
                    help="Markera denna ruta om du vill använda koordinaterna ovan",
                    key=f"use_coords_{arbetsplats['_id']}")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.form_submit_button("Spara ändringar"):
                        if ny_forvaltning == "Alla förvaltningar":
                            # Uppdatera till global arbetsplats
                            db.arbetsplatser.update_one(
                                {"_id": arbetsplats["_id"]},
                                {"$set": {
                                    "namn": nytt_namn,
                                    "gatuadress": ny_gatuadress,
                                    "postnummer": nytt_postnummer,
                                    "ort": ny_ort,
                                    "kommun": ny_kommun,
                                    "alla_forvaltningar": True,
                                    "forvaltning_id": None,
                                    "forvaltning_namn": "Alla förvaltningar",
                                    "coordinates": {"lat": latitude, "lng": longitude} if use_coords else None
                                }}
                            )
                        else:
                            vald_ny_forv = next(f for f in forvaltningar if f["namn"] == ny_forvaltning)
                            # Uppdatera till specifik förvaltning
                            db.arbetsplatser.update_one(
                                {"_id": arbetsplats["_id"]},
                                {"$set": {
                                    "namn": nytt_namn,
                                    "gatuadress": ny_gatuadress,
                                    "postnummer": nytt_postnummer,
                                    "ort": ny_ort,
                                    "kommun": ny_kommun,
                                    "alla_forvaltningar": False,
                                    "forvaltning_id": vald_ny_forv["_id"],
                                    "forvaltning_namn": vald_ny_forv["namn"],
                                    "coordinates": {"lat": latitude, "lng": longitude} if use_coords else None
                                }}
                            )
                        st.success("Arbetsplats uppdaterad!")
                        st.rerun()
                
                with col2:
                    if st.form_submit_button("Ta bort", type="secondary"):
                        # Kontrollera om det finns personer på arbetsplatsen
                        personer = list(db.personer.find({
                            "arbetsplatser": arbetsplats["namn"]
                        }))
                        if personer:
                            st.error("Det finns personer kopplade till denna arbetsplats. Ta bort eller flytta dessa först.")
                        else:
                            db.arbetsplatser.delete_one({"_id": arbetsplats["_id"]})
                            st.success(f"{arbetsplats['namn']} borttagen!")
                            st.rerun() 