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
    - Regionala arbetsplatser: Kan ha medlemmar över flera förvaltningar
    
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
                # Hantera regionala arbetsplatser
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


def fix_missing_forvaltning_ids(db):
    """
    Åtgärdar saknade förvaltnings-ID i enheter.
    Uppdaterar även kopplade arbetsplatser.
    """
    # Skapa uppslagstabell för förvaltningsnamn till ID
    forv_lookup = {f['namn']: str(f['_id']) for f in db.forvaltningar.find()}
    
    # Hitta enheter som saknar förvaltning_id men har förvaltning_namn
    enheter_to_fix = db.enheter.find({
        'forvaltning_id': {'$exists': False},
        'forvaltning_namn': {'$exists': True}
    })
    
    for enhet in enheter_to_fix:
        if enhet['forvaltning_namn'] in forv_lookup:
            # Uppdatera enheten med korrekt förvaltning_id
            db.enheter.update_one(
                {'_id': enhet['_id']},
                {'$set': {'forvaltning_id': forv_lookup[enhet['forvaltning_namn']]}}
            )
            
            # Uppdatera även kopplade arbetsplatser
            if enhet.get('arbetsplatser'):
                db.arbetsplatser.update_many(
                    {'_id': {'$in': enhet['arbetsplatser']}},
                    {'$set': {'forvaltning_id': forv_lookup[enhet['forvaltning_namn']]}}
                )


def show(db):
    """
    Visar och hanterar gränssnittet för organisationsstruktur.
    Hanterar förvaltningar, avdelningar och enheter.
    """
    # Säkerställ att medlemsantal är uppdaterade
    if st.session_state.get('needs_member_count_update', True):
        calculate_member_counts(db)
        
    # Rensa cachad data för att tvinga omladdning
    if 'cached_data' in st.session_state:
        del st.session_state.cached_data
    
    # Ladda cachad data
    cached, indexes = get_cached_data(db)
    
    # Åtgärda eventuella saknade förvaltnings-ID
    fix_missing_forvaltning_ids(db)
    
    # Huvudflikar för separation av funktionalitet
    tabs = st.tabs([
        "Förvaltningar",
        "Avdelningar",
        "Enheter"
    ])
    
    # Lägg till förvaltning
    with tabs[0]:
        st.subheader("Lägg till Förvaltning")
        with st.form("add_forvaltning"):
            forv_namn = st.text_input("Namn på förvaltning")
            forv_chef = st.text_input("Chef (valfritt)")
            
            if st.form_submit_button("Lägg till"):
                if not forv_namn:
                    st.error("Ange ett namn för förvaltningen")
                elif any(f['namn'] == forv_namn for f in cached['forvaltningar']):
                    st.error("En förvaltning med detta namn finns redan")
                else:
                    result = db.forvaltningar.insert_one({
                        "namn": forv_namn,
                        "chef": forv_chef,
                        "beraknat_medlemsantal": 0
                    })
                    if result.inserted_id:
                        log_action("create", f"Skapade förvaltning: {forv_namn}", "unit")
                        update_cache_after_change(db, 'forvaltningar', 'create')
                        st.success("Förvaltning skapad!")
                        st.rerun()
        
        # Visa befintliga förvaltningar
        st.subheader("Befintliga Förvaltningar")
        for forv in sorted(cached['forvaltningar'], key=lambda x: x['namn']):
            with st.expander(forv['namn']):
                with st.form(f"edit_forv_{forv['_id']}"):
                    nytt_namn = st.text_input("Namn", value=forv['namn'])
                    ny_chef = st.text_input("Chef", value=forv.get('chef', ''))
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.form_submit_button("Spara Ändringar"):
                            if not nytt_namn:
                                st.error("Ange ett namn för förvaltningen")
                            elif nytt_namn != forv['namn'] and any(f['namn'] == nytt_namn for f in cached['forvaltningar']):
                                st.error("En förvaltning med detta namn finns redan")
                            else:
                                db.forvaltningar.update_one(
                                    {"_id": forv["_id"]},
                                    {"$set": {
                                        "namn": nytt_namn,
                                        "chef": ny_chef
                                    }}
                                )
                                log_action("update", f"Uppdaterade förvaltning: {forv['namn']} -> {nytt_namn}", "unit")
                                update_cache_after_change(db, 'forvaltningar', 'update')
                                st.success("Förvaltning uppdaterad!")
                                st.rerun()
                    
                    with col2:
                        if st.form_submit_button("Ta Bort", type="primary"):
                            # Kontrollera om det finns beroende data
                            has_avdelningar = any(a['forvaltning_id'] == forv['_id'] for a in cached['avdelningar'])
                            has_enheter = any(e['forvaltning_id'] == forv['_id'] for e in cached['enheter'])
                            has_personer = any(p['forvaltning_id'] == forv['_id'] for p in cached['personer'])
                            
                            if has_avdelningar or has_enheter or has_personer:
                                st.error("Kan inte ta bort förvaltningen eftersom den har kopplad data")
                            else:
                                db.forvaltningar.delete_one({"_id": forv["_id"]})
                                log_action("delete", f"Tog bort förvaltning: {forv['namn']}", "unit")
                                update_cache_after_change(db, 'forvaltningar', 'delete')
                                st.success("Förvaltning borttagen!")
                                st.rerun()
    
    # Lägg till avdelning
    with tabs[1]:
        st.subheader("Lägg till Avdelning")
        with st.form("add_avdelning"):
            if not cached['forvaltningar']:
                st.warning("Lägg till minst en förvaltning först")
            else:
                forv_namn = st.selectbox(
                    "Förvaltning",
                    options=[f["namn"] for f in cached['forvaltningar']]
                )
                vald_forv = next(f for f in cached['forvaltningar'] if f["namn"] == forv_namn)
                
                avd_namn = st.text_input("Namn på avdelning")
                avd_chef = st.text_input("Chef (valfritt)")
                
                if st.form_submit_button("Lägg till"):
                    if not avd_namn:
                        st.error("Ange ett namn för avdelningen")
                    elif any(a['namn'] == avd_namn and str(a['forvaltning_id']) == str(vald_forv['_id']) 
                           for a in cached['avdelningar']):
                        st.error("En avdelning med detta namn finns redan i förvaltningen")
                    else:
                        result = db.avdelningar.insert_one({
                            "namn": avd_namn,
                            "chef": avd_chef,
                            "forvaltning_id": vald_forv["_id"],
                            "forvaltning_namn": vald_forv["namn"],
                            "beraknat_medlemsantal": 0
                        })
                        if result.inserted_id:
                            log_action("create", f"Skapade avdelning: {avd_namn} i {vald_forv['namn']}", "unit")
                            update_cache_after_change(db, 'avdelningar', 'create')
                            st.success("Avdelning skapad!")
                            st.rerun()
        
        # Visa befintliga avdelningar
        st.subheader("Befintliga Avdelningar")
        for forv in sorted(cached['forvaltningar'], key=lambda x: x['namn']):
            with st.expander(forv['namn']):
                avdelningar = sorted(
                    [a for a in cached['avdelningar'] if str(a['forvaltning_id']) == str(forv['_id'])],
                    key=lambda x: x['namn']
                )
                
                if not avdelningar:
                    st.info("Inga avdelningar i denna förvaltning")
                else:
                    for avd in avdelningar:
                        with st.form(f"edit_avd_{avd['_id']}"):
                            nytt_namn = st.text_input("Namn", value=avd['namn'])
                            ny_chef = st.text_input("Chef", value=avd.get('chef', ''))
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                if st.form_submit_button("Spara Ändringar"):
                                    if not nytt_namn:
                                        st.error("Ange ett namn för avdelningen")
                                    elif nytt_namn != avd['namn'] and any(
                                        a['namn'] == nytt_namn and str(a['forvaltning_id']) == str(forv['_id'])
                                        for a in cached['avdelningar']
                                    ):
                                        st.error("En avdelning med detta namn finns redan i förvaltningen")
                                    else:
                                        db.avdelningar.update_one(
                                            {"_id": avd["_id"]},
                                            {"$set": {
                                                "namn": nytt_namn,
                                                "chef": ny_chef
                                            }}
                                        )
                                        log_action("update", f"Uppdaterade avdelning: {avd['namn']} -> {nytt_namn}", "unit")
                                        update_cache_after_change(db, 'avdelningar', 'update')
                                        st.success("Avdelning uppdaterad!")
                                        st.rerun()
                            
                            with col2:
                                if st.form_submit_button("Ta Bort", type="primary"):
                                    # Kontrollera om det finns beroende data
                                    has_enheter = any(e['avdelning_id'] == avd['_id'] for e in cached['enheter'])
                                    has_personer = any(p['avdelning_id'] == avd['_id'] for p in cached['personer'])
                                    
                                    if has_enheter or has_personer:
                                        st.error("Kan inte ta bort avdelningen eftersom den har kopplad data")
                                    else:
                                        db.avdelningar.delete_one({"_id": avd["_id"]})
                                        log_action("delete", f"Tog bort avdelning: {avd['namn']}", "unit")
                                        update_cache_after_change(db, 'avdelningar', 'delete')
                                        st.success("Avdelning borttagen!")
                                        st.rerun()
    
    # Lägg till enhet
    with tabs[2]:
        st.subheader("Lägg till Enhet")
        with st.form("add_enhet"):
            if not cached['forvaltningar']:
                st.warning("Lägg till minst en förvaltning först")
            elif not cached['avdelningar']:
                st.warning("Lägg till minst en avdelning först")
            else:
                forv_namn = st.selectbox(
                    "Förvaltning",
                    options=[f["namn"] for f in cached['forvaltningar']],
                    key="add_enhet_forv"
                )
                vald_forv = next(f for f in cached['forvaltningar'] if f["namn"] == forv_namn)
                
                avdelningar = [a for a in cached['avdelningar'] 
                             if str(a['forvaltning_id']) == str(vald_forv['_id'])]
                
                if not avdelningar:
                    st.warning("Lägg till minst en avdelning i den valda förvaltningen först")
                else:
                    avd_namn = st.selectbox(
                        "Avdelning",
                        options=[a["namn"] for a in avdelningar]
                    )
                    vald_avd = next(a for a in avdelningar if a["namn"] == avd_namn)
                    
                    enhet_namn = st.text_input("Namn på enhet")
                    enhet_chef = st.text_input("Chef (valfritt)")
                    
                    # Hämta tillgängliga arbetsplatser för denna förvaltning
                    arbetsplatser = [
                        ap for ap in cached['arbetsplatser']
                        if (str(ap.get('forvaltning_id')) == str(vald_forv['_id']) or ap.get('alla_forvaltningar', False))
                        and not any(e.get('arbetsplatser', []) and str(ap['_id']) in e['arbetsplatser'] 
                                  for e in cached['enheter'])
                    ]
                    
                    if arbetsplatser:
                        valda_arbetsplatser = st.multiselect(
                            "Koppla arbetsplatser",
                            options=[ap['namn'] for ap in arbetsplatser],
                            help="Välj arbetsplatser som ska kopplas till denna enhet"
                        )
                        
                        # Konvertera valda arbetsplatser till lista med ID
                        arbetsplats_ids = [
                            str(ap['_id']) for ap in arbetsplatser 
                            if ap['namn'] in valda_arbetsplatser
                        ]
                    
                    if st.form_submit_button("Lägg till"):
                        if not enhet_namn:
                            st.error("Ange ett namn för enheten")
                        elif any(e['namn'] == enhet_namn and str(e['avdelning_id']) == str(vald_avd['_id']) 
                               for e in cached['enheter']):
                            st.error("En enhet med detta namn finns redan i avdelningen")
                        else:
                            enhet_data = {
                                "namn": enhet_namn,
                                "chef": enhet_chef,
                                "forvaltning_id": vald_forv["_id"],
                                "forvaltning_namn": vald_forv["namn"],
                                "avdelning_id": vald_avd["_id"],
                                "avdelning_namn": vald_avd["namn"],
                                "beraknat_medlemsantal": 0
                            }
                            
                            if arbetsplatser and arbetsplats_ids:
                                enhet_data["arbetsplatser"] = arbetsplats_ids
                            
                            result = db.enheter.insert_one(enhet_data)
                            if result.inserted_id:
                                log_action("create", f"Skapade enhet: {enhet_namn} i {vald_avd['namn']}", "unit")
                                
                                # Uppdatera arbetsplatser med enhet-referens
                                if arbetsplatser and arbetsplats_ids:
                                    db.arbetsplatser.update_many(
                                        {"_id": {"$in": [ObjectId(ap_id) for ap_id in arbetsplats_ids]}},
                                        {"$set": {
                                            "enhet_id": result.inserted_id,
                                            "enhet_namn": enhet_namn
                                        }}
                                    )
                                
                                update_cache_after_change(db, 'enheter', 'create')
                                st.success("Enhet skapad!")
                                st.rerun()
        
        # Visa befintliga enheter
        st.subheader("Befintliga Enheter")
        for forv in sorted(cached['forvaltningar'], key=lambda x: x['namn']):
            with st.expander(forv['namn']):
                avdelningar = sorted(
                    [a for a in cached['avdelningar'] if str(a['forvaltning_id']) == str(forv['_id'])],
                    key=lambda x: x['namn']
                )
                
                if not avdelningar:
                    st.info("Inga avdelningar i denna förvaltning")
                else:
                    for avd in avdelningar:
                        enheter = sorted(
                            [e for e in cached['enheter'] if str(e['avdelning_id']) == str(avd['_id'])],
                            key=lambda x: x['namn']
                        )
                        
                        if not enheter:
                            st.info(f"Inga enheter i {avd['namn']}")
                        else:
                            st.write(f"#### {avd['namn']}")
                            for enhet in enheter:
                                with st.form(f"edit_enhet_{enhet['_id']}"):
                                    nytt_namn = st.text_input("Namn", value=enhet['namn'])
                                    ny_chef = st.text_input("Chef", value=enhet.get('chef', ''))
                                    
                                    # Hämta nuvarande arbetsplatser för denna enhet
                                    nuvarande_arbetsplatser = [
                                        ap for ap in cached['arbetsplatser']
                                        if str(ap['_id']) in enhet.get('arbetsplatser', [])
                                    ]
                                    
                                    # Hämta tillgängliga arbetsplatser för denna förvaltning
                                    arbetsplatser = [
                                        ap for ap in cached['arbetsplatser']
                                        if (str(ap.get('forvaltning_id')) == str(forv['_id']) or ap.get('alla_forvaltningar', False))
                                        and (not any(e.get('arbetsplatser', []) and str(ap['_id']) in e['arbetsplatser'] 
                                                   for e in cached['enheter'])
                                             or str(ap['_id']) in enhet.get('arbetsplatser', []))
                                    ]
                                    
                                    # Hämta nuvarande arbetsplatser baserat på arbetsplatser-listan i enhet
                                    if arbetsplatser:
                                        valda_arbetsplatser = st.multiselect(
                                            "Kopplade arbetsplatser",
                                            options=[ap['namn'] for ap in arbetsplatser],
                                            default=[ap['namn'] for ap in nuvarande_arbetsplatser],
                                            help="Välj arbetsplatser som ska kopplas till denna enhet"
                                        )
                                        
                                        # Ta bort enhet_id från tidigare kopplade arbetsplatser
                                        tidigare_ap_ids = set(enhet.get('arbetsplatser', []))
                                        nya_ap_ids = set(str(ap['_id']) for ap in arbetsplatser if ap['namn'] in valda_arbetsplatser)
                                        
                                        borttagna_ap_ids = tidigare_ap_ids - nya_ap_ids
                                        if borttagna_ap_ids:
                                            db.arbetsplatser.update_many(
                                                {"_id": {"$in": [ObjectId(ap_id) for ap_id in borttagna_ap_ids]}},
                                                {"$unset": {"enhet_id": "", "enhet_namn": ""}}
                                            )
                                        
                                        # Konvertera valda arbetsplatser till lista med ID
                                        arbetsplats_ids = [
                                            str(ap['_id']) for ap in arbetsplatser 
                                            if ap['namn'] in valda_arbetsplatser
                                        ]
                                    
                                    col1, col2 = st.columns(2)
                                    with col1:
                                        if st.form_submit_button("Spara Ändringar"):
                                            if not nytt_namn:
                                                st.error("Ange ett namn för enheten")
                                            elif nytt_namn != enhet['namn'] and any(
                                                e['namn'] == nytt_namn and str(e['avdelning_id']) == str(avd['_id'])
                                                for e in cached['enheter']
                                            ):
                                                st.error("En enhet med detta namn finns redan i avdelningen")
                                            else:
                                                update_data = {
                                                    "namn": nytt_namn,
                                                    "chef": ny_chef
                                                }
                                                
                                                if arbetsplatser:
                                                    update_data["arbetsplatser"] = arbetsplats_ids
                                                
                                                # Uppdatera enheten
                                                db.enheter.update_one(
                                                    {"_id": enhet["_id"]},
                                                    {"$set": update_data}
                                                )
                                                
                                                # Uppdatera nya arbetsplatser med enhet-referens
                                                if arbetsplatser and arbetsplats_ids:
                                                    db.arbetsplatser.update_many(
                                                        {"_id": {"$in": [ObjectId(ap_id) for ap_id in arbetsplats_ids]}},
                                                        {"$set": {
                                                            "enhet_id": enhet["_id"],
                                                            "enhet_namn": nytt_namn
                                                        }}
                                                    )
                                                
                                                log_action("update", f"Uppdaterade enhet: {enhet['namn']} -> {nytt_namn}", "unit")
                                                update_cache_after_change(db, 'enheter', 'update')
                                                st.success("Enhet uppdaterad!")
                                                st.rerun()
                                    
                                    with col2:
                                        if st.form_submit_button("Ta Bort", type="primary"):
                                            # Kontrollera om det finns beroende data
                                            has_personer = any(p['enhet_id'] == enhet['_id'] for p in cached['personer'])
                                            
                                            if has_personer:
                                                st.error("Kan inte ta bort enheten eftersom den har kopplad data")
                                            else:
                                                # Ta bort enhet_id från kopplade arbetsplatser
                                                if enhet.get('arbetsplatser'):
                                                    db.arbetsplatser.update_many(
                                                        {"_id": {"$in": [ObjectId(ap_id) for ap_id in enhet['arbetsplatser']]}},
                                                        {"$unset": {"enhet_id": "", "enhet_namn": ""}}
                                                    )
                                                
                                                db.enheter.delete_one({"_id": enhet["_id"]})
                                                log_action("delete", f"Tog bort enhet: {enhet['namn']}", "unit")
                                                update_cache_after_change(db, 'enheter', 'delete')
                                                st.success("Enhet borttagen!")
                                                st.rerun()

