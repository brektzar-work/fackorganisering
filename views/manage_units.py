"""
Hanteringsmodul för Organisationsstruktur i Vision Sektion 10.

Detta system hanterar den hierarkiska organisationsstrukturen:
- Förvaltningar (högsta nivån)
- Avdelningar (mellannivå)
- Enheter (lägsta nivån)

Modulen tillhandahåller funktionalitet för att:
- Skapa, redigera och ta bort organisationsenheter
- Beräkna och visa medlemsantal på alla nivåer
- Visa statistik över Visionombud och Skyddsombud
- Hantera relationer mellan olika organisationsnivåer

Tekniska detaljer:
- Använder MongoDB för hierarkisk datalagring
- Implementerar batch-uppdateringar för effektiv datahantering
- Hanterar dynamisk uppdatering av medlemsantal
- Tillhandahåller realtidsstatistik och rapportering
"""

import streamlit as st
from views.custom_logging import log_action, current_time
from pymongo import UpdateOne
from views.cache_manager import get_cached_data, update_cache_after_change
from bson.objectid import ObjectId


def calculate_member_counts(db):
    """Beräknar medlemsantal för alla organisationsnivåer i systemet.
    
    Denna komplexa funktion hanterar beräkning av medlemsantal genom att:
    1. Ladda all nödvändig data från databasen
    2. Beräkna medlemsantal för enheter baserat på arbetsplatser
    3. Aggregera enheternas antal upp till avdelningsnivå
    4. Aggregera avdelningarnas antal upp till förvaltningsnivå
    
    Funktionen hanterar två typer av arbetsplatser:
    - Specifika arbetsplatser: Kopplade till specifika enheter
    - Globala/regionala arbetsplatser: Kan ha medlemmar över flera förvaltningar
    
    Tekniska detaljer:
    - Använder batch-operationer för effektiv databashantering
    - Implementerar caching för att undvika onödiga beräkningar
    - Hanterar hierarkisk aggregering av data
    - Validerar datatyper för robust felhantering
    """
    # Kontrollera om omberäkning behövs
    if not st.session_state.get('needs_recalculation', True):
        return

    # Ladda all nödvändig data på en gång för effektivitet
    enheter = list(db.enheter.find())
    avdelningar = list(db.avdelningar.find())
    forvaltningar = list(db.forvaltningar.find())
    arbetsplatser = list(db.arbetsplatser.find())

    # Skapa uppslagstabeller för snabbare åtkomst
    enheter_by_id = {str(enhet["_id"]): enhet for enhet in enheter}
    avdelningar_by_id = {str(avd["_id"]): avd for avd in avdelningar}
    
    # Förbered batch-uppdateringar för alla nivåer
    enhet_updates = []
    avdelning_updates = []
    forvaltning_updates = []

    # Beräkna medlemsantal för enheter
    for enhet in enheter:
        total_members = 0
        enhet_id = str(enhet["_id"])
        
        # Beräkna från specifika arbetsplatser
        for arbetsplats in arbetsplatser:
            if not arbetsplats.get("alla_forvaltningar"):
                # Hantera specifika arbetsplatser
                medlemmar_per_enhet = arbetsplats.get("medlemmar_per_enhet", {})
                if isinstance(medlemmar_per_enhet, dict):
                    total_members += medlemmar_per_enhet.get(enhet_id, 0)
            else:
                # Hantera globala/regionala arbetsplatser
                medlemmar_per_forvaltning = arbetsplats.get("medlemmar_per_forvaltning", {})
                if isinstance(medlemmar_per_forvaltning, dict):
                    for forv_id, forv_data in medlemmar_per_forvaltning.items():
                        if isinstance(forv_data, dict) and "enheter" in forv_data:
                            enheter_data = forv_data["enheter"]
                            if isinstance(enheter_data, dict):
                                total_members += enheter_data.get(enhet_id, 0)

        # Loggning för felsökning
        if total_members > 0:
            print(f"Enhet {enhet['namn']}: {total_members} medlemmar")

        # Lägg till uppdatering i batch
        enhet_updates.append(UpdateOne(
            {"_id": enhet["_id"]},
            {"$set": {"beraknat_medlemsantal": total_members}}
        ))

    # Utför batch-uppdateringar för enheter
    if enhet_updates:
        db.enheter.bulk_write(enhet_updates)
    
    # Uppdatera data efter enhetsuppdateringar
    enheter = list(db.enheter.find())

    # Beräkna medlemsantal för avdelningar
    for avd in avdelningar:
        # Summera medlemsantal från tillhörande enheter
        avd_enheter = [e for e in enheter if str(e.get("avdelning_id")) == str(avd["_id"])]
        total_members = sum(e.get("beraknat_medlemsantal", 0) for e in avd_enheter)
        
        # Loggning för felsökning
        if total_members > 0:
            print(f"Avdelning {avd['namn']}: {total_members} medlemmar")
        
        # Lägg till uppdatering i batch
        avdelning_updates.append(UpdateOne(
            {"_id": avd["_id"]},
            {"$set": {"beraknat_medlemsantal": total_members}}
        ))

    # Utför batch-uppdateringar för avdelningar
    if avdelning_updates:
        db.avdelningar.bulk_write(avdelning_updates)
    
    # Uppdatera data efter avdelningsuppdateringar
    avdelningar = list(db.avdelningar.find())

    # Beräkna medlemsantal för förvaltningar
    for forv in forvaltningar:
        # Summera medlemsantal från tillhörande avdelningar
        forv_avdelningar = [a for a in avdelningar if str(a.get("forvaltning_id")) == str(forv["_id"])]
        total_members = sum(a.get("beraknat_medlemsantal", 0) for a in forv_avdelningar)
        
        # Loggning för felsökning
        if total_members > 0:
            print(f"Förvaltning {forv['namn']}: {total_members} medlemmar")
        
        # Lägg till uppdatering i batch
        forvaltning_updates.append(UpdateOne(
            {"_id": forv["_id"]},
            {"$set": {"beraknat_medlemsantal": total_members}}
        ))

    # Utför batch-uppdateringar för förvaltningar
    if forvaltning_updates:
        db.forvaltningar.bulk_write(forvaltning_updates)

    # Markera att beräkning är klar
    st.session_state.needs_recalculation = False


def fix_missing_forvaltning_ids(db, cached_data):
    """Fix missing forvaltning_id in enheter by looking up the ID from forvaltning_namn"""
    # Create lookup dictionary for förvaltning names to IDs
    forv_name_to_id = {f['namn']: f['_id'] for f in cached_data['forvaltningar']}
    
    # Find enheter missing forvaltning_id but having forvaltning_namn
    enheter_to_fix = [e for e in cached_data['enheter'] 
                     if not e.get('forvaltning_id') and e.get('forvaltning_namn')]
    
    for enhet in enheter_to_fix:
        if enhet['forvaltning_namn'] in forv_name_to_id:
            forv_id = forv_name_to_id[enhet['forvaltning_namn']]
            # Update the enhet with the correct forvaltning_id
            db.enheter.update_one(
                {"_id": enhet["_id"]},
                {"$set": {"forvaltning_id": forv_id}}
            )
            # Also update any associated arbetsplatser
            if enhet.get('arbetsplatser'):
                db.arbetsplatser.update_many(
                    {"_id": {"$in": [ObjectId(ap_id) for ap_id in enhet['arbetsplatser']]}},
                    {"$set": {"forvaltning_id": forv_id}}
                )


def show(db):
    """Visar och hanterar gränssnittet för organisationsstrukturen.
    
    Funktionen hanterar fyra huvudområden:
    1. Förvaltningar - Skapa, redigera och ta bort förvaltningar
    2. Avdelningar - Hantera avdelningar och deras koppling till förvaltningar
    3. Enheter - Hantera enheter och deras koppling till avdelningar
    4. Statistik - Visa statistik över medlemmar och ombud
    
    Args:
        db: MongoDB-databasanslutning med tillgång till collections för:
           - forvaltningar
           - avdelningar
           - enheter
           - arbetsplatser
           - personer
    
    Tekniska detaljer:
    - Använder session state för att cachea data
    - Implementerar dynamisk uppdatering av gränssnittet
    - Hanterar beroenden mellan olika organisationsnivåer
    - Tillhandahåller realtidsstatistik
    """
    # Säkerställ att medlemsantal är uppdaterade
    if st.session_state.get('needs_recalculation', True):
        calculate_member_counts(db)
        # Rensa cachad data för att tvinga omladdning
        st.session_state.pop('forvaltningar', None)
        st.session_state.pop('avdelningar', None)
        st.session_state.pop('enheter', None)
        st.session_state.needs_recalculation = False

    # Ladda cachad data
    cached, indexes = get_cached_data(db)
    
    # Fix any missing forvaltning_ids
    fix_missing_forvaltning_ids(db, cached)

    # Huvudflikar för separation av funktionalitet
    tab1, tab2, tab3 = st.tabs(["Förvaltningar", "Avdelningar", "Enheter"])

    with tab1:
        st.subheader("Förvaltningar")
        
        # Lägg till förvaltning
        with st.expander("Lägg till Förvaltning"):
            with st.form("add_forvaltning"):
                namn = st.text_input("Förvaltningsnamn")
                chef = st.text_input("Förvaltningschef")
                submitted = st.form_submit_button("Lägg till Förvaltning")

                if submitted and namn:
                    forvaltning = {
                        "namn": namn,
                        "chef": chef,
                        "beraknat_medlemsantal": 0
                    }
                    result = db.forvaltningar.insert_one(forvaltning)
                    if result.inserted_id:
                        forvaltning['_id'] = result.inserted_id
                        update_cache_after_change(db, 'forvaltningar', 'create', forvaltning)
                        log_action("create", f"Skapade förvaltning: {namn} med chef: {chef}", "unit")
                        st.success("Förvaltning tillagd!")
                        st.rerun()

        # Visa befintliga förvaltningar
        forvaltningar = cached['forvaltningar']
        for forv in forvaltningar:
            with st.expander(f"{forv['namn']} - Chef: {forv.get('chef', 'Ej angiven')}"):
                with st.form(f"edit_forvaltning_{forv['_id']}"):
                    nytt_namn = st.text_input("Namn", value=forv["namn"])
                    ny_chef = st.text_input("Chef", value=forv.get("chef", ""))
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.form_submit_button("Spara ändringar"):
                            result = db.forvaltningar.update_one(
                                {"_id": forv["_id"]},
                                {"$set": {"namn": nytt_namn, "chef": ny_chef}}
                            )
                            if result.modified_count > 0:
                                update_cache_after_change(db, 'forvaltningar', 'update')
                                log_action("update", f"Uppdaterade förvaltning: {forv['namn']}", "unit")
                                st.success("Förvaltning uppdaterad!")
                                st.rerun()

                    with col2:
                        if st.form_submit_button("Ta bort", type="secondary"):
                            avdelningar = indexes['avdelningar_by_forv'].get(forv["_id"], [])
                            if avdelningar:
                                st.error("Kan inte ta bort förvaltning som har avdelningar")
                            else:
                                db.forvaltningar.delete_one({"_id": forv["_id"]})
                                update_cache_after_change(db, 'forvaltningar', 'delete')
                                log_action("delete", f"Tog bort förvaltning: {forv['namn']}", "unit")
                                st.success("Förvaltning borttagen!")
                                st.rerun()

    with tab2:
        st.subheader("Avdelningar")
        
        # Lägg till avdelning
        with st.expander("Lägg till Avdelning"):
            with st.form("add_avdelning"):
                forvaltning = st.selectbox(
                    "Välj Förvaltning",
                    options=forvaltningar,
                    format_func=lambda x: x['namn']
                )
                
                if forvaltning:
                    namn = st.text_input("Avdelningsnamn")
                    chef = st.text_input("Avdelningschef")
                    submitted = st.form_submit_button("Lägg till Avdelning")

                    if submitted and namn:
                        avdelning = {
                            "namn": namn,
                            "chef": chef,
                            "forvaltning_id": forvaltning["_id"],
                            "forvaltning_namn": forvaltning["namn"],
                            "beraknat_medlemsantal": 0
                        }
                        result = db.avdelningar.insert_one(avdelning)
                        if result.inserted_id:
                            avdelning['_id'] = result.inserted_id
                            update_cache_after_change(db, 'avdelningar', 'create', avdelning)
                            log_action("create", f"Skapade avdelning: {namn} under {forvaltning['namn']}", "unit")
                            st.success("Avdelning tillagd!")
                            st.rerun()

        # Visa befintliga avdelningar
        for forv in forvaltningar:
            avdelningar = indexes['avdelningar_by_forv'].get(forv["_id"], [])
            if avdelningar:
                st.markdown(f"### {forv['namn']}")
                for avd in avdelningar:
                    with st.expander(f"{avd['namn']} - Chef: {avd.get('chef', 'Ej angiven')}"):
                        with st.form(f"edit_avdelning_{avd['_id']}"):
                            nytt_namn = st.text_input("Namn", value=avd["namn"])
                            ny_chef = st.text_input("Chef", value=avd.get("chef", ""))
                            ny_forvaltning = st.selectbox(
                                "Förvaltning",
                                options=forvaltningar,
                                format_func=lambda x: x['namn'],
                                index=next((i for i, f in enumerate(forvaltningar) 
                                          if str(f["_id"]) == str(avd["forvaltning_id"])), 0)
                            )
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                if st.form_submit_button("Spara ändringar"):
                                    result = db.avdelningar.update_one(
                                        {"_id": avd["_id"]},
                                        {"$set": {
                                            "namn": nytt_namn,
                                            "chef": ny_chef,
                                            "forvaltning_id": ny_forvaltning["_id"],
                                            "forvaltning_namn": ny_forvaltning["namn"]
                                        }}
                                    )
                                    if result.modified_count > 0:
                                        update_cache_after_change(db, 'avdelningar', 'update')
                                        log_action("update", f"Uppdaterade avdelning: {avd['namn']}", "unit")
                                        st.success("Avdelning uppdaterad!")
                                        st.rerun()

                            with col2:
                                if st.form_submit_button("Ta bort", type="secondary"):
                                    enheter = indexes['enheter_by_avd'].get(avd["_id"], [])
                                    if enheter:
                                        st.error("Kan inte ta bort avdelning som har enheter")
                                    else:
                                        db.avdelningar.delete_one({"_id": avd["_id"]})
                                        update_cache_after_change(db, 'avdelningar', 'delete')
                                        log_action("delete", f"Tog bort avdelning: {avd['namn']}", "unit")
                                        st.success("Avdelning borttagen!")
                                        st.rerun()

    with tab3:
        st.subheader("Enheter")
        
        # Lägg till enhet
        with st.expander("Lägg till Enhet"):
            with st.form("add_enhet"):
                forvaltning = st.selectbox(
                    "Välj Förvaltning",
                    options=forvaltningar,
                    format_func=lambda x: x['namn'],
                    key="add_enhet_forv"
                )
                
                if forvaltning:
                    avdelningar = indexes['avdelningar_by_forv'].get(forvaltning["_id"], [])
                    avdelning = st.selectbox(
                        "Välj Avdelning",
                        options=avdelningar,
                        format_func=lambda x: x['namn']
                    )
                    
                    if avdelning:
                        namn = st.text_input("Enhetsnamn")
                        chef = st.text_input("Enhetschef")
                        
                        # Get available arbetsplatser for this förvaltning
                        available_arbetsplatser = [ap for ap in cached['arbetsplatser'] 
                                                 if (not ap.get('alla_forvaltningar') and 
                                                     str(ap.get('forvaltning_id')) == str(forvaltning["_id"])) or
                                                 ap.get('alla_forvaltningar', False)]
                        
                        selected_arbetsplatser = st.multiselect(
                            "Välj Arbetsplatser",
                            options=available_arbetsplatser,
                            format_func=lambda x: f"{x['namn']} {'(Regional)' if x.get('alla_forvaltningar') else ''}"
                        )
                        
                        submitted = st.form_submit_button("Lägg till Enhet")

                        if submitted and namn:
                            # Convert selected arbetsplatser to list of IDs
                            arbetsplats_ids = [str(ap["_id"]) for ap in selected_arbetsplatser]
                            
                            enhet = {
                                "namn": namn,
                                "chef": chef,
                                "avdelning_id": avdelning["_id"],
                                "avdelning_namn": avdelning["namn"],
                                "forvaltning_id": forvaltning["_id"],
                                "forvaltning_namn": forvaltning["namn"],
                                "arbetsplatser": arbetsplats_ids,
                                "beraknat_medlemsantal": 0
                            }
                            result = db.enheter.insert_one(enhet)
                            if result.inserted_id:
                                enhet['_id'] = result.inserted_id
                                # Update arbetsplatser with enhet reference
                                for ap in selected_arbetsplatser:
                                    db.arbetsplatser.update_one(
                                        {"_id": ap["_id"]},
                                        {"$set": {
                                            "enhet_id": result.inserted_id,
                                            "forvaltning_id": forvaltning["_id"],
                                            "forvaltning_namn": forvaltning["namn"]
                                        }}
                                    )
                                update_cache_after_change(db, 'enheter', 'create', enhet)
                                update_cache_after_change(db, 'arbetsplatser', 'update')
                                log_action("create", f"Skapade enhet: {namn} under {avdelning['namn']}", "unit")
                                st.success("Enhet tillagd!")
                                st.rerun()

        # Visa befintliga enheter
        for forv in forvaltningar:
            avdelningar = indexes['avdelningar_by_forv'].get(forv["_id"], [])
            if avdelningar:
                st.markdown(f"### {forv['namn']}")
                for avd in avdelningar:
                    enheter = indexes['enheter_by_avd'].get(avd["_id"], [])
                    if enheter:
                        st.markdown(f"#### {avd['namn']}")
                        for enhet in enheter:
                            # Get current arbetsplatser for this enhet
                            current_arbetsplats_ids = set(enhet.get('arbetsplatser', []))
                            
                            with st.expander(f"{enhet['namn']} - Chef: {enhet.get('chef', 'Ej angiven')}"):
                                with st.form(f"edit_enhet_{enhet['_id']}"):
                                    nytt_namn = st.text_input("Namn", value=enhet["namn"])
                                    ny_chef = st.text_input("Chef", value=enhet.get("chef", ""))
                                    
                                    ny_forvaltning = st.selectbox(
                                        "Förvaltning",
                                        options=forvaltningar,
                                        format_func=lambda x: x['namn'],
                                        index=next((i for i, f in enumerate(forvaltningar) 
                                                  if str(f["_id"]) == str(enhet["forvaltning_id"])), 0),
                                        key=f"edit_enhet_forv_{enhet['_id']}"
                                    )
                                    
                                    if ny_forvaltning:
                                        avdelningar = indexes['avdelningar_by_forv'].get(ny_forvaltning["_id"], [])
                                        ny_avdelning = st.selectbox(
                                            "Avdelning",
                                            options=avdelningar,
                                            format_func=lambda x: x['namn'],
                                            index=next((i for i, a in enumerate(avdelningar) 
                                                      if str(a["_id"]) == str(enhet["avdelning_id"])), 0)
                                        )
                                        
                                        # Get available arbetsplatser for this förvaltning
                                        available_arbetsplatser = [ap for ap in cached['arbetsplatser'] 
                                                                 if (not ap.get('alla_forvaltningar') and 
                                                                     str(ap.get('forvaltning_id')) == str(ny_forvaltning["_id"])) or
                                                                 ap.get('alla_forvaltningar', False)]
                                        
                                        # Get current arbetsplatser based on the arbetsplatser list in enhet
                                        current_arbetsplatser = [ap for ap in available_arbetsplatser 
                                                               if str(ap["_id"]) in current_arbetsplats_ids]
                                        
                                        selected_arbetsplatser = st.multiselect(
                                            "Arbetsplatser",
                                            options=available_arbetsplatser,
                                            default=current_arbetsplatser,
                                            format_func=lambda x: f"{x['namn']} {'(Regional)' if x.get('alla_forvaltningar') else ''}"
                                        )
                                        
                                        col1, col2 = st.columns(2)
                                        with col1:
                                            if st.form_submit_button("Spara ändringar"):
                                                # Remove enhet_id from previously associated arbetsplatser
                                                db.arbetsplatser.update_many(
                                                    {"enhet_id": enhet["_id"]},
                                                    {"$unset": {"enhet_id": ""}}
                                                )
                                                
                                                # Convert selected arbetsplatser to list of IDs
                                                arbetsplats_ids = [str(ap["_id"]) for ap in selected_arbetsplatser]
                                                
                                                # Update the enhet
                                                result = db.enheter.update_one(
                                                    {"_id": enhet["_id"]},
                                                    {"$set": {
                                                        "namn": nytt_namn,
                                                        "chef": ny_chef,
                                                        "avdelning_id": ny_avdelning["_id"],
                                                        "avdelning_namn": ny_avdelning["namn"],
                                                        "forvaltning_id": ny_forvaltning["_id"],
                                                        "forvaltning_namn": ny_forvaltning["namn"],
                                                        "arbetsplatser": arbetsplats_ids
                                                    }}
                                                )
                                                
                                                # Update new arbetsplatser with enhet reference
                                                for ap in selected_arbetsplatser:
                                                    db.arbetsplatser.update_one(
                                                        {"_id": ap["_id"]},
                                                        {"$set": {
                                                            "enhet_id": enhet["_id"],
                                                            "forvaltning_id": ny_forvaltning["_id"],
                                                            "forvaltning_namn": ny_forvaltning["namn"]
                                                        }}
                                                    )
                                                
                                                if result.modified_count > 0:
                                                    update_cache_after_change(db, 'enheter', 'update')
                                                    update_cache_after_change(db, 'arbetsplatser', 'update')
                                                    log_action("update", f"Uppdaterade enhet: {enhet['namn']}", "unit")
                                                    st.success("Enhet uppdaterad!")
                                                    st.rerun()

                                        with col2:
                                            if st.form_submit_button("Ta bort", type="secondary"):
                                                # Remove enhet_id from associated arbetsplatser
                                                db.arbetsplatser.update_many(
                                                    {"enhet_id": enhet["_id"]},
                                                    {"$unset": {"enhet_id": ""}}
                                                )
                                                
                                                db.enheter.delete_one({"_id": enhet["_id"]})
                                                update_cache_after_change(db, 'enheter', 'delete')
                                                update_cache_after_change(db, 'arbetsplatser', 'update')
                                                log_action("delete", f"Tog bort enhet: {enhet['namn']}", "unit")
                                                st.success("Enhet borttagen!")
                                                st.rerun()

