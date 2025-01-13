import streamlit as st


def show(db):
    st.header("Hantera Organisationsstruktur")

    tab1, tab2, tab3 = st.tabs(["Förvaltningar", "Avdelningar", "Enheter"])

    with tab1:
        st.subheader("Förvaltningar")

        # Lägg till förvaltning
        with st.form("add_forvaltning"):
            namn = st.text_input("Förvaltningsnamn")
            chef = st.text_input("Förvaltningschef")
            submitted = st.form_submit_button("Lägg till Förvaltning")

            if submitted and namn:
                db.forvaltningar.insert_one({
                    "namn": namn,
                    "chef": chef
                })
                st.success("Förvaltning tillagd!")
                st.rerun()

        # Lista och redigera befintliga förvaltningar
        forvaltningar = list(db.forvaltningar.find())
        if not forvaltningar:
            st.info("Inga förvaltningar tillagda än")
        else:
            for forv in forvaltningar:
                with st.expander(forv["namn"]):
                    with st.form(f"edit_forv_{forv['_id']}"):
                        nytt_namn = st.text_input("Namn", value=forv["namn"])
                        ny_chef = st.text_input("Chef", value=forv["chef"])
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.form_submit_button("Spara ändringar"):
                                db.forvaltningar.update_one(
                                    {"_id": forv["_id"]},
                                    {"$set": {"namn": nytt_namn, "chef": ny_chef}}
                                )
                                st.success("Förvaltning uppdaterad!")
                                st.rerun()
                        with col2:
                            if st.form_submit_button("Ta bort", type="secondary"):
                                # Kontrollera om det finns beroende avdelningar
                                if db.avdelningar.find_one({"forvaltning_id": forv["_id"]}):
                                    st.error("Kan inte ta bort förvaltning som har avdelningar")
                                else:
                                    db.forvaltningar.delete_one({"_id": forv["_id"]})
                                    st.success("Förvaltning borttagen!")
                                    st.rerun()

    with tab2:
        st.subheader("Avdelningar")

        # Lägg till avdelning
        with st.form("add_avdelning"):
            forvaltningar = list(db.forvaltningar.find())
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
                        "forvaltning_namn": forv_namn
                    })
                    st.success("Avdelning tillagd!")
                    st.rerun()

        # Lista och redigera befintliga avdelningar
        avdelningar = list(db.avdelningar.find())
        if not avdelningar:
            st.info("Inga avdelningar tillagda än")
        else:
            for avd in avdelningar:
                with st.expander(f"{avd['namn']} ({avd.get('forvaltning_namn', 'Okänd förvaltning')})"):
                    with st.form(f"edit_avd_{avd['_id']}"):
                        forv_namn = st.selectbox(
                            "Förvaltning",
                            options=[f["namn"] for f in forvaltningar],
                            index=[i for i, f in enumerate(forvaltningar) if f["_id"] == avd["forvaltning_id"]][0],
                            key=f"forv_select_{avd['_id']}"
                        )
                        nytt_namn = st.text_input("Namn", value=avd["namn"])
                        ny_chef = st.text_input("Chef", value=avd["chef"])

                        col1, col2 = st.columns(2)
                        with col1:
                            if st.form_submit_button("Spara ändringar"):
                                forv_id = next(f["_id"] for f in forvaltningar if f["namn"] == forv_namn)
                                db.avdelningar.update_one(
                                    {"_id": avd["_id"]},
                                    {"$set": {
                                        "namn": nytt_namn,
                                        "chef": ny_chef,
                                        "forvaltning_id": forv_id,
                                        "forvaltning_namn": forv_namn
                                    }}
                                )
                                st.success("Avdelning uppdaterad!")
                                st.rerun()
                        with col2:
                            if st.form_submit_button("Ta bort", type="secondary"):
                                if db.enheter.find_one({"avdelning_id": avd["_id"]}):
                                    st.error("Kan inte ta bort avdelning som har enheter")
                                else:
                                    db.avdelningar.delete_one({"_id": avd["_id"]})
                                    st.success("Avdelning borttagen!")
                                    st.rerun()

    with tab3:
        st.subheader("Enheter")

        # Lägg till enhet
        with st.form("add_enhet"):
            avdelningar = list(db.avdelningar.find())
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
                        "forvaltning_namn": avd["forvaltning_namn"]
                    })
                    st.success("Enhet tillagd!")
                    st.rerun()

        # Lista och redigera befintliga enheter
        enheter = list(db.enheter.find())
        if not enheter:
            st.info("Inga enheter tillagda än")
        else:
            for enhet in enheter:
                with st.expander(f"{enhet['namn']} ({enhet.get('avdelning_namn', 'Okänd avdelning')})"):
                    with st.form(f"edit_enhet_{enhet['_id']}"):
                        avd_namn = st.selectbox(
                            "Avdelning",
                            options=[f"{a['namn']} ({a['forvaltning_namn']})" for a in avdelningar],
                            index=[i for i, a in enumerate(avdelningar)
                                   if a["_id"] == enhet["avdelning_id"]][0],
                            key=f"avd_select_{enhet['_id']}"
                        )
                        nytt_namn = st.text_input("Namn", value=enhet["namn"])
                        ny_chef = st.text_input("Chef", value=enhet["chef"])

                        col1, col2 = st.columns(2)
                        with col1:
                            if st.form_submit_button("Spara ändringar"):
                                avd = next(a for a in avdelningar
                                           if f"{a['namn']} ({a['forvaltning_namn']})" == avd_namn)
                                db.enheter.update_one(
                                    {"_id": enhet["_id"]},
                                    {"$set": {
                                        "namn": nytt_namn,
                                        "chef": ny_chef,
                                        "avdelning_id": avd["_id"],
                                        "avdelning_namn": avd["namn"],
                                        "forvaltning_namn": avd["forvaltning_namn"]
                                    }}
                                )
                                st.success("Enhet uppdaterad!")
                                st.rerun()
                        with col2:
                            if st.form_submit_button("Ta bort", type="secondary"):
                                if db.personer.find_one({"enhet_id": enhet["_id"]}):
                                    st.error("Kan inte ta bort enhet som har personer")
                                else:
                                    db.enheter.delete_one({"_id": enhet["_id"]})
                                    st.success("Enhet borttagen!")
                                    st.rerun()
