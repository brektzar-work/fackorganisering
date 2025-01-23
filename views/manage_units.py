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

    # Ladda data med caching
    if 'forvaltningar' not in st.session_state:
        st.session_state.forvaltningar = list(db.forvaltningar.find())
    if 'avdelningar' not in st.session_state:
        st.session_state.avdelningar = list(db.avdelningar.find())
    if 'enheter' not in st.session_state:
        st.session_state.enheter = list(db.enheter.find())
    
    # Ladda data för statistik
    arbetsplatser = list(db.arbetsplatser.find())
    personer = list(db.personer.find())
    
    # Använd cachad data
    forvaltningar = st.session_state.forvaltningar
    avdelningar = st.session_state.avdelningar
    enheter = st.session_state.enheter

    st.header("Hantera Organisationsstruktur")

    # Skapa flikar för olika sektioner
    tab1, tab2, tab3, tab4 = st.tabs(["Förvaltningar", "Avdelningar", "Enheter", "Statistik & Grafer"])

    with tab1:
        st.subheader("Förvaltningar")

        # Lägg till förvaltning
        with st.expander("Lägg till Förvaltning"):
            st.divider()
            with st.form("add_forvaltning"):
                namn = st.text_input("Förvaltningsnamn")
                chef = st.text_input("Förvaltningschef")
                submitted = st.form_submit_button("Lägg till Förvaltning")

                if submitted and namn:
                    db.forvaltningar.insert_one({
                        "namn": namn,
                        "chef": chef,
                        "beraknat_medlemsantal": 0
                    })
                    log_action("create", f"Skapade förvaltning: {namn} med chef: {chef}", "unit")
                    st.success("Förvaltning tillagd!")
                    st.rerun()
        st.divider()

        # Lista och redigera befintliga förvaltningar
        if not forvaltningar:
            st.info("Inga förvaltningar tillagda än")
        else:
            for forv in forvaltningar:
                with st.expander(f"{forv['namn']} (Medlemmar: {forv.get('beraknat_medlemsantal', 0)})"):
                    with st.form(f"edit_forv_{forv['_id']}"):
                        nytt_namn = st.text_input("Namn", value=forv["namn"])
                        ny_chef = st.text_input("Chef", value=forv["chef"])
                        st.info(
                            (f"Beräknat medlemsantal: "
                             f"{forv.get('beraknat_medlemsantal', 0)} (baserat på avdelningarnas antal)"))

                        col1, col2 = st.columns(2)
                        with col1:
                            if st.form_submit_button("Spara ändringar"):
                                changes = []
                                if nytt_namn != forv["namn"]:
                                    changes.append(f"namn från '{forv['namn']}' till '{nytt_namn}'")
                                if ny_chef != forv["chef"]:
                                    changes.append(f"chef från '{forv['chef']}' till '{ny_chef}'")

                                db.forvaltningar.update_one(
                                    {"_id": forv["_id"]},
                                    {"$set": {
                                        "namn": nytt_namn,
                                        "chef": ny_chef
                                    }}
                                )
                                if changes:
                                    log_action("update",
                                               (f"Uppdaterade förvaltning: "
                                                f"{forv['namn']} - Ändrade {', '.join(changes)}"),
                                               "unit")
                                st.success("Förvaltning uppdaterad!")
                                st.rerun()

                        with col2:
                            if st.form_submit_button("Ta bort", type="secondary"):
                                # Kontrollera om det finns beroende avdelningar
                                if db.avdelningar.find_one({"forvaltning_id": forv["_id"]}):
                                    st.error("Kan inte ta bort förvaltning som har avdelningar")
                                else:
                                    db.forvaltningar.delete_one({"_id": forv["_id"]})
                                    log_action("delete", f"Tog bort förvaltning: {forv['namn']}", "unit")
                                    st.success("Förvaltning borttagen!")
                                    st.rerun()

    with tab2:
        st.subheader("Avdelningar")

        # Lägg till avdelning
        with st.expander("Lägg till Avdelning"):
            st.divider()
            with st.form("add_avdelning"):
                if not forvaltningar:
                    st.warning("Lägg till minst en förvaltning först")
                else:
                    forv_namn = st.selectbox(
                        "Förvaltning",
                        options=[f["namn"] for f in forvaltningar]
                    )
                    namn = st.text_input("Avdelningsnamn")
                    chef = st.text_input("Avdelningschef")
                    submitted = st.form_submit_button("Lägg till Avdelning")

                    if submitted and namn and forv_namn:
                        forv_id = next(f["_id"] for f in forvaltningar if f["namn"] == forv_namn)
                        db.avdelningar.insert_one({
                            "namn": namn,
                            "chef": chef,
                            "forvaltning_id": forv_id,
                            "forvaltning_namn": forv_namn,
                            "beraknat_medlemsantal": 0
                        })
                        log_action("create",
                                   f"Skapade avdelning: {namn} med chef: {chef} under förvaltning: {forv_namn}",
                                   "unit")
                        st.success("Avdelning tillagd!")
                        st.rerun()
        st.divider()

        # Lista och redigera befintliga avdelningar
        if not avdelningar:
            st.info("Inga avdelningar tillagda än")
        else:
            # Gruppera avdelningar efter förvaltning
            for forv in forvaltningar:
                # Filtrera avdelningar för denna förvaltning
                forv_avdelningar = [avd for avd in avdelningar if avd["forvaltning_id"] == forv["_id"]]
                if forv_avdelningar:  # Visa bara förvaltningar som har avdelningar
                    with st.expander(f"{forv['namn']} - {len(forv_avdelningar)} avdelningar"):
                        for avd in forv_avdelningar:
                            with st.expander(f"{avd['namn']} - Medlemmar: {avd.get('beraknat_medlemsantal', 0)}"):
                                with st.form(f"edit_avd_{avd['_id']}"):
                                    nytt_namn = st.text_input("Namn", value=avd["namn"])
                                    ny_chef = st.text_input("Chef", value=avd.get("chef", ""))
                                    st.info((f"Beräknat medlemsantal: "
                                             f"{avd.get('beraknat_medlemsantal', 0)} (baserat på enheternas antal)"))

                                    # Dropdown för att välja förvaltning
                                    forv_index = next((i for i, f in enumerate(forvaltningar)
                                                       if f["_id"] == avd["forvaltning_id"]), 0)
                                    ny_forv = st.selectbox(
                                        "Förvaltning",
                                        options=[f["namn"] for f in forvaltningar],
                                        index=forv_index
                                    )
                                    ny_forv_id = next(f["_id"] for f in forvaltningar if f["namn"] == ny_forv)

                                    col1, col2 = st.columns(2)
                                    with col1:
                                        if st.form_submit_button("Spara ändringar"):
                                            changes = []
                                            if nytt_namn != avd["namn"]:
                                                changes.append(f"namn från '{avd['namn']}' till '{nytt_namn}'")
                                            if ny_chef != avd.get("chef", ""):
                                                changes.append(f"chef från '{avd.get('chef', '')}' till '{ny_chef}'")
                                            if ny_forv != avd["forvaltning_namn"]:
                                                changes.append(
                                                    f"förvaltning från '{avd['forvaltning_namn']}' till '{ny_forv}'")

                                            db.avdelningar.update_one(
                                                {"_id": avd["_id"]},
                                                {"$set": {
                                                    "namn": nytt_namn,
                                                    "chef": ny_chef,
                                                    "forvaltning_id": ny_forv_id,
                                                    "forvaltning_namn": ny_forv
                                                }}
                                            )
                                            if changes:
                                                log_action("update",
                                                           (f"Uppdaterade avdelning: "
                                                            f"{avd['namn']} - Ändrade {', '.join(changes)}"),
                                                           "unit")
                                            st.success("Avdelning uppdaterad!")
                                            st.rerun()

                                    with col2:
                                        if st.form_submit_button("Ta bort", type="secondary"):
                                            # Kontrollera om det finns beroende enheter
                                            if db.enheter.find_one({"avdelning_id": avd["_id"]}):
                                                st.error("Kan inte ta bort avdelning som har enheter")
                                            else:
                                                db.avdelningar.delete_one({"_id": avd["_id"]})
                                                log_action("delete",
                                                           f"Tog bort avdelning: {avd['namn']}",
                                                           "unit")
                                                st.success("Avdelning borttagen!")
                                                st.rerun()

    with tab3:
        st.subheader("Enheter")

        # Lägg till enhet
        with st.expander("Lägg till Enheter"):
            st.divider()
            with st.form("add_enhet"):
                if not avdelningar:
                    st.warning("Lägg till minst en avdelning först")
                else:
                    avd_namn = st.selectbox(
                        "Avdelning",
                        options=[f"{a['namn']} ({a['forvaltning_namn']})" for a in avdelningar]
                    )
                    namn = st.text_input("Enhetsnamn")
                    chef = st.text_input("Enhetschef")
                    submitted = st.form_submit_button("Lägg till Enhet")

                    if submitted and namn and avd_namn:
                        avd = next(a for a in avdelningar if f"{a['namn']} ({a['forvaltning_namn']})" == avd_namn)
                        db.enheter.insert_one({
                            "namn": namn,
                            "chef": chef,
                            "avdelning_id": avd["_id"],
                            "avdelning_namn": avd["namn"],
                            "forvaltning_id": avd["forvaltning_id"],
                            "forvaltning_namn": avd["forvaltning_namn"],
                            "beraknat_medlemsantal": 0
                        })
                        log_action("create", f"Skapade enhet: {namn} med chef: {chef} under avdelning: {avd['namn']}",
                                   "unit")
                        st.success("Enhet tillagd!")
                        st.rerun()
        st.divider()

        # Lista och redigera befintliga enheter
        if not enheter:
            st.info("Inga enheter tillagda än")
        else:
            # Gruppera enheter efter förvaltning och avdelning
            for forv in forvaltningar:
                # Filtrera avdelningar för denna förvaltning
                forv_avdelningar = [a for a in avdelningar if a["forvaltning_id"] == forv["_id"]]
                if forv_avdelningar:  # Visa bara förvaltningar som har avdelningar
                    with st.expander(f"{forv['namn']}"):
                        for avd in forv_avdelningar:
                            # Filtrera enheter för denna avdelning
                            avd_enheter = [e for e in enheter if e["avdelning_id"] == avd["_id"]]
                            if avd_enheter:  # Visa bara avdelningar som har enheter
                                with st.expander(f"{avd['namn']} - {len(avd_enheter)} enheter"):
                                    for enhet in avd_enheter:
                                        with st.expander((f"{enhet['namn']} - Medlemmar: "
                                                          f"{enhet.get('beraknat_medlemsantal', 0)}")):
                                            with st.form(f"edit_enhet_{enhet['_id']}"):
                                                nytt_namn = st.text_input("Namn", value=enhet["namn"])
                                                ny_chef = st.text_input("Chef", value=enhet.get("chef", ""))
                                                st.info(
                                                    (f"Beräknat medlemsantal: "
                                                     f"{enhet.get('beraknat_medlemsantal', 0)}"
                                                     f" (baserat på arbetsplatsernas antal)"))

                                                # Dropdown för att välja avdelning
                                                avdelningar = list(db.avdelningar.find())
                                                avd_index = next((i for i, a in enumerate(avdelningar)
                                                                  if a["_id"] == enhet["avdelning_id"]), 0)
                                                ny_avd = st.selectbox(
                                                    "Avdelning",
                                                    options=[f"{a['namn']} ({a['forvaltning_namn']})" for a in
                                                             avdelningar],
                                                    index=avd_index
                                                )
                                                vald_avd = next(a for a in avdelningar if
                                                                f"{a['namn']} ({a['forvaltning_namn']})" == ny_avd)

                                                col1, col2 = st.columns(2)
                                                with col1:
                                                    if st.form_submit_button("Spara ändringar"):
                                                        changes = []
                                                        if nytt_namn != enhet["namn"]:
                                                            changes.append(
                                                                f"namn från '{enhet['namn']}' till '{nytt_namn}'")
                                                        if ny_chef != enhet.get("chef", ""):
                                                            changes.append(
                                                                f"chef från '{enhet.get('chef', '')}' till '{ny_chef}'")
                                                        if vald_avd["namn"] != enhet["avdelning_namn"]:
                                                            changes.append(
                                                                f"avdelning från '{enhet['avdelning_namn']}"
                                                                f"' till '{vald_avd['namn']}'")

                                                        db.enheter.update_one(
                                                            {"_id": enhet["_id"]},
                                                            {"$set": {
                                                                "namn": nytt_namn,
                                                                "chef": ny_chef,
                                                                "avdelning_id": vald_avd["_id"],
                                                                "avdelning_namn": vald_avd["namn"],
                                                                "forvaltning_id": vald_avd["forvaltning_id"],
                                                                "forvaltning_namn": vald_avd["forvaltning_namn"]
                                                            }}
                                                        )
                                                        if changes:
                                                            log_action("update",
                                                                       f"Uppdaterade enhet: {enhet['namn']} - "
                                                                       f"Ändrade {', '.join(changes)}",
                                                                       "unit")
                                                        st.success("Enhet uppdaterad!")
                                                        st.rerun()

                                                with col2:
                                                    if st.form_submit_button("Ta bort", type="secondary"):
                                                        # Kontrollera om det finns personer i enheten
                                                        if db.personer.find_one({"enhet_id": enhet["_id"]}):
                                                            st.error("Kan inte ta bort enhet som har personer")
                                                        else:
                                                            db.enheter.delete_one({"_id": enhet["_id"]})
                                                            log_action("delete", f"Tog bort enhet: {enhet['namn']}",
                                                                       "unit")
                                                            st.success("Enhet borttagen!")
                                                            st.rerun()

    with tab4:
        st.subheader("Statistik & Grafer")
        
        stats_tab1, stats_tab2, stats_tab3 = st.tabs(["Visionombud", "Skyddsombud", "Grafer"])
        
        with stats_tab1:
            # Hjälpfunktion för att räkna Visionombud
            def count_vision_reps(personer_list, filter_func=None):
                """Räknar antalet Visionombud baserat på givna filter.
                
                Args:
                    personer_list: Lista med personer att analysera
                    filter_func: Valfri filterfunktion för att begränsa räkningen
                
                Returns:
                    int: Antal Visionombud som uppfyller filterkriterierna
                """
                if filter_func:
                    personer_list = [p for p in personer_list if filter_func(p)]
                return len([p for p in personer_list if p.get("is_vision_ombud", False)])

            # Översikt av totala antal
            st.markdown("### Total Översikt")
            total_members = sum(f.get('beraknat_medlemsantal', 0) for f in forvaltningar)
            total_reps = count_vision_reps(personer)
            
            # Visa totala mätvärden
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Totalt antal medlemmar", total_members)
            with col2:
                st.metric("Totalt antal Visionombud", total_reps)
            
            # Beräkna och visa medlemmar per ombud
            if total_members > 0:
                st.metric("Medlemmar per Visionombud", 
                         round(total_members / total_reps if total_reps > 0 else float('inf'), 1))
            
            # Statistik per förvaltning
            st.markdown("### Per Förvaltning")
            for forv in forvaltningar:
                if forv.get('beraknat_medlemsantal', 0) > 0:
                    with st.expander(f"{forv['namn']}"):
                        members = forv.get('beraknat_medlemsantal', 0)
                        reps = count_vision_reps(personer, 
                            lambda p: str(p.get('forvaltning_id')) == str(forv['_id']))
                        
                        # Visa mätvärden för förvaltningen
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("Antal medlemmar", members)
                        with col2:
                            st.metric("Antal Visionombud", reps)
                        
                        if members > 0:
                            st.metric("Medlemmar per Visionombud", 
                                round(members / reps if reps > 0 else float('inf'), 1))
            
            # Statistik per avdelning
            st.markdown("### Per Avdelning")
            for avd in avdelningar:
                if avd.get('beraknat_medlemsantal', 0) > 0:
                    with st.expander(f"{avd['namn']} ({avd['forvaltning_namn']})"):
                        members = avd.get('beraknat_medlemsantal', 0)
                        reps = count_vision_reps(personer, 
                            lambda p: str(p.get('avdelning_id')) == str(avd['_id']))
                        
                        # Visa mätvärden för avdelningen
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("Antal medlemmar", members)
                        with col2:
                            st.metric("Antal Visionombud", reps)
                        
                        if members > 0:
                            st.metric("Medlemmar per Visionombud", 
                                round(members / reps if reps > 0 else float('inf'), 1))
            
            # Statistik per enhet
            st.markdown("### Per Enhet")
            for enhet in enheter:
                if enhet.get('beraknat_medlemsantal', 0) > 0:
                    with st.expander(f"{enhet['namn']} ({enhet['avdelning_namn']}, {enhet['forvaltning_namn']})"):
                        members = enhet.get('beraknat_medlemsantal', 0)
                        reps = count_vision_reps(personer, 
                            lambda p: str(p.get('enhet_id')) == str(enhet['_id']))
                        
                        # Visa mätvärden för enheten
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("Antal medlemmar", members)
                        with col2:
                            st.metric("Antal Visionombud", reps)
                        
                        if members > 0:
                            st.metric("Medlemmar per Visionombud", 
                                round(members / reps if reps > 0 else float('inf'), 1))
            
            # Statistik per arbetsplats
            st.markdown("### Per Arbetsplats")
            for arbetsplats in arbetsplatser:
                # Beräkna totalt antal medlemmar för arbetsplatsen
                total_members = 0
                if arbetsplats.get("alla_forvaltningar"):
                    # Summera medlemmar för regionala arbetsplatser
                    medlemmar_per_forvaltning = arbetsplats.get("medlemmar_per_forvaltning", {})
                    for forv_data in medlemmar_per_forvaltning.values():
                        if isinstance(forv_data, dict) and "enheter" in forv_data:
                            total_members += sum(forv_data["enheter"].values())
                else:
                    # Summera medlemmar för specifika arbetsplatser
                    medlemmar_per_enhet = arbetsplats.get("medlemmar_per_enhet", {})
                    if isinstance(medlemmar_per_enhet, dict):
                        total_members = sum(medlemmar_per_enhet.values())
                
                # Visa statistik om arbetsplatsen har medlemmar
                if total_members > 0:
                    with st.expander(f"{arbetsplats['namn']}"):
                        reps = count_vision_reps(personer, 
                            lambda p: str(p.get('arbetsplats_id')) == str(arbetsplats['_id']))
                        
                        # Visa mätvärden för arbetsplatsen
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("Antal medlemmar", total_members)
                        with col2:
                            st.metric("Antal Visionombud", reps)
                        
                        st.metric("Medlemmar per Visionombud", 
                            round(total_members / reps if reps > 0 else float('inf'), 1))

        with stats_tab2:
            # Hjälpfunktion för att räkna Skyddsombud
            def count_safety_reps(personer_list, filter_func=None):
                """Räknar antalet Skyddsombud baserat på givna filter.
                
                Args:
                    personer_list: Lista med personer att analysera
                    filter_func: Valfri filterfunktion för att begränsa räkningen
                
                Returns:
                    int: Antal Skyddsombud som uppfyller filterkriterierna
                """
                if filter_func:
                    personer_list = [p for p in personer_list if filter_func(p)]
                return len([p for p in personer_list if p.get("is_skyddsombud", False)])

            # Översikt av totala antal
            st.markdown("### Total Översikt")
            total_members = sum(f.get('beraknat_medlemsantal', 0) for f in forvaltningar)
            total_reps = count_safety_reps(personer)
            
            # Visa totala mätvärden
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Totalt antal medlemmar", total_members)
            with col2:
                st.metric("Totalt antal Skyddsombud", total_reps)
            
            # Beräkna och visa medlemmar per ombud
            if total_members > 0:
                st.metric("Medlemmar per Skyddsombud", 
                         round(total_members / total_reps if total_reps > 0 else float('inf'), 1))
            
            # Statistik per förvaltning
            st.markdown("### Per Förvaltning")
            for forv in forvaltningar:
                if forv.get('beraknat_medlemsantal', 0) > 0:
                    with st.expander(f"{forv['namn']}"):
                        members = forv.get('beraknat_medlemsantal', 0)
                        reps = count_safety_reps(personer, 
                            lambda p: str(p.get('forvaltning_id')) == str(forv['_id']))
                        
                        # Visa mätvärden för förvaltningen
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("Antal medlemmar", members)
                        with col2:
                            st.metric("Antal Skyddsombud", reps)
                        
                        if members > 0:
                            st.metric("Medlemmar per Skyddsombud", 
                                round(members / reps if reps > 0 else float('inf'), 1))
            
            # Statistik per avdelning
            st.markdown("### Per Avdelning")
            for avd in avdelningar:
                if avd.get('beraknat_medlemsantal', 0) > 0:
                    with st.expander(f"{avd['namn']} ({avd['forvaltning_namn']})"):
                        members = avd.get('beraknat_medlemsantal', 0)
                        reps = count_safety_reps(personer, 
                            lambda p: str(p.get('avdelning_id')) == str(avd['_id']))
                        
                        # Visa mätvärden för avdelningen
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("Antal medlemmar", members)
                        with col2:
                            st.metric("Antal Skyddsombud", reps)
                        
                        if members > 0:
                            st.metric("Medlemmar per Skyddsombud", 
                                round(members / reps if reps > 0 else float('inf'), 1))
            
            # Statistik per enhet
            st.markdown("### Per Enhet")
            for enhet in enheter:
                if enhet.get('beraknat_medlemsantal', 0) > 0:
                    with st.expander(f"{enhet['namn']} ({enhet['avdelning_namn']}, {enhet['forvaltning_namn']})"):
                        members = enhet.get('beraknat_medlemsantal', 0)
                        reps = count_safety_reps(personer, 
                            lambda p: str(p.get('enhet_id')) == str(enhet['_id']))
                        
                        # Visa mätvärden för enheten
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("Antal medlemmar", members)
                        with col2:
                            st.metric("Antal Skyddsombud", reps)
                        
                        if members > 0:
                            st.metric("Medlemmar per Skyddsombud", 
                                round(members / reps if reps > 0 else float('inf'), 1))
            
            # Statistik per arbetsplats
            st.markdown("### Per Arbetsplats")
            for arbetsplats in arbetsplatser:
                # Beräkna totalt antal medlemmar för arbetsplatsen
                total_members = 0
                if arbetsplats.get("alla_forvaltningar"):
                    # Summera medlemmar för regionala arbetsplatser
                    medlemmar_per_forvaltning = arbetsplats.get("medlemmar_per_forvaltning", {})
                    for forv_data in medlemmar_per_forvaltning.values():
                        if isinstance(forv_data, dict) and "enheter" in forv_data:
                            total_members += sum(forv_data["enheter"].values())
                else:
                    # Summera medlemmar för specifika arbetsplatser
                    medlemmar_per_enhet = arbetsplats.get("medlemmar_per_enhet", {})
                    if isinstance(medlemmar_per_enhet, dict):
                        total_members = sum(medlemmar_per_enhet.values())
                
                # Visa statistik om arbetsplatsen har medlemmar
                if total_members > 0:
                    with st.expander(f"{arbetsplats['namn']}"):
                        reps = count_safety_reps(personer, 
                            lambda p: str(p.get('arbetsplats_id')) == str(arbetsplats['_id']))
                        
                        # Visa mätvärden för arbetsplatsen
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("Antal medlemmar", total_members)
                        with col2:
                            st.metric("Antal Skyddsombud", reps)
                        
                        st.metric("Medlemmar per Skyddsombud", 
                            round(total_members / reps if reps > 0 else float('inf'), 1))

        with stats_tab3:
            st.markdown("### Grafer kommer här")
            # TODO: Implementera grafer för visualisering av statistik
