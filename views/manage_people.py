import streamlit as st


def show(db):
    st.header("Hantera Personer")

    # Initiera session state om det behövs
    if 'ny_arbetsplats' not in st.session_state:
        st.session_state.ny_arbetsplats = False
    if 'redigering_forvaltning' not in st.session_state:
        st.session_state.redigering_forvaltning = {}
    if 'redigering_avdelning' not in st.session_state:
        st.session_state.redigering_avdelning = {}

    # Hämta alla förvaltningar
    forvaltningar = list(db.forvaltningar.find())

    # Dropdown för förvaltning (utanför formuläret)
    if forvaltningar:
        forv_namn = st.selectbox(
            "Välj Förvaltning",
            options=[f["namn"] for f in forvaltningar],
            key="forv_select"
        )
        vald_forvaltning = next(f for f in forvaltningar if f["namn"] == forv_namn)

        # Filtrera avdelningar baserat på vald förvaltning
        avdelningar = list(db.avdelningar.find({"forvaltning_id": vald_forvaltning["_id"]}))
        if avdelningar:
            avd_namn = st.selectbox(
                "Välj Avdelning",
                options=[a["namn"] for a in avdelningar],
                key="avd_select"
            )
            vald_avdelning = next(a for a in avdelningar if a["namn"] == avd_namn)

            # Filtrera enheter baserat på vald avdelning
            enheter = list(db.enheter.find({"avdelning_id": vald_avdelning["_id"]}))
            if enheter:
                enh_namn = st.selectbox(
                    "Välj Enhet",
                    options=[e["namn"] for e in enheter],
                    key="enh_select"
                )
                vald_enhet = next(e for e in enheter if e["namn"] == enh_namn)
            else:
                st.warning("Inga enheter finns för den valda avdelningen")
                vald_enhet = None
        else:
            st.warning("Inga avdelningar finns för den valda förvaltningen")
            vald_avdelning = None
            vald_enhet = None
    else:
        st.warning("Inga förvaltningar finns. Lägg till minst en förvaltning först.")
        vald_forvaltning = None
        vald_avdelning = None
        vald_enhet = None

    # Lägg till ny person
    with st.expander("**Lägg till Person**"):
        # Hämta alla unika arbetsplatser från databasen
        alla_arbetsplatser = sorted(list(set(
            arbetsplats for person in db.personer.find()
            if person.get('arbetsplats')
            for arbetsplats in person['arbetsplats']
        )))

        # Form för att lägga till person
        with st.form("person_form"):
            namn = st.text_input("Namn")
            yrkestitel = st.text_input("Yrkestitel")

            # Hämta arbetsplatser baserat på vald förvaltning
            if vald_forvaltning:
                arbetsplatser = list(db.arbetsplatser.find({
                    "$or": [
                        {"forvaltning_id": vald_forvaltning["_id"]},
                        {"alla_forvaltningar": True}
                    ]
                }))
                
                if arbetsplatser:
                    arbetsplats = st.multiselect(
                        "Arbetsplats",
                        options=[a["namn"] for a in arbetsplatser],
                        help="Välj en eller flera arbetsplatser"
                    )
                else:
                    st.warning("Inga arbetsplatser finns för den valda förvaltningen. Lägg till arbetsplatser först.")
                    arbetsplats = []
            else:
                st.warning("Välj en förvaltning först för att se tillgängliga arbetsplatser")
                arbetsplats = []

            telefon = st.text_input("Telefon")

            # Checkboxar och val för olika roller
            col1, col2, col3 = st.columns(3)
            with col1:
                # CSG
                st.write("**CSG**")
                csg = st.checkbox("Sitter i CSG")
                if csg:
                    csg_roll = st.radio(
                        "Roll i CSG",
                        options=["Ordinarie", "Ersättare"],
                        key="csg_roll"
                    )

                # LSG/FSG
                st.write("**LSG/FSG**")
                lsg_fsg = st.checkbox("Sitter i LSG/FSG")
                if lsg_fsg:
                    lsg_fsg_roll = st.radio(
                        "Roll i LSG/FSG",
                        options=["Ordinarie", "Ersättare"],
                        key="lsg_fsg_roll"
                    )

            with col2:
                skyddsombud = st.checkbox("Skyddsombud")
                huvudskyddsombud = st.checkbox("Huvudskyddsombud")
                visionombud = st.checkbox("Visionombud")
            with col3:
                annat_fack = st.checkbox("Medlem i annat fack")

            submitted = st.form_submit_button("Spara Person")

            if submitted:
                if not arbetsplats:
                    st.error("Arbetsplats måste anges")
                    return

                if vald_forvaltning and vald_avdelning and vald_enhet:
                    # Skapa person-dokument
                    person = {
                        "namn": namn,
                        "yrkestitel": yrkestitel,
                        "forvaltning_id": vald_forvaltning["_id"],
                        "forvaltning_namn": vald_forvaltning["namn"],
                        "avdelning_id": vald_avdelning["_id"],
                        "avdelning_namn": vald_avdelning["namn"],
                        "enhet_id": vald_enhet["_id"],
                        "enhet_namn": vald_enhet["namn"],
                        "arbetsplats": arbetsplats,
                        "telefon": telefon,
                        "csg": csg,
                        "csg_roll": csg_roll if csg else None,
                        "lsg_fsg": lsg_fsg,
                        "lsg_fsg_roll": lsg_fsg_roll if lsg_fsg else None,
                        "skyddsombud": skyddsombud,
                        "huvudskyddsombud": huvudskyddsombud,
                        "visionombud": visionombud,
                        "annat_fack": annat_fack
                    }

                    # Spara till databasen
                    db.personer.insert_one(person)
                    st.success("Person sparad!")
                    st.session_state.ny_arbetsplats = False  # Återställ efter sparande
                    st.rerun()
                else:
                    st.error("Kontrollera att förvaltning, avdelning och enhet är valda")

    st.divider()

    # Lista och redigera befintliga personer
    st.subheader("Befintliga Personer")

    # Dropdown för att välja förvaltning att visa
    forvaltningar = list(db.forvaltningar.find())
    vald_visningsforvaltning = st.selectbox(
        "Välj förvaltning att visa",
        options=[f["namn"] for f in forvaltningar],
        key="visa_forvaltning"
    )
    
    # Hämta alla personer för vald förvaltning
    vald_forv = next(f for f in forvaltningar if f["namn"] == vald_visningsforvaltning)
    alla_personer = list(db.personer.find({"forvaltning_id": vald_forv["_id"]}))
    
    # Initiera session state för alla personer
    for person in alla_personer:
        person_id = str(person['_id'])
        if f"forv_{person_id}" not in st.session_state:
            st.session_state[f"forv_{person_id}"] = person["forvaltning_id"]
        if f"avd_{person_id}" not in st.session_state:
            st.session_state[f"avd_{person_id}"] = person["avdelning_id"]
        if f"enh_{person_id}" not in st.session_state:
            st.session_state[f"enh_{person_id}"] = person["enhet_id"]
    
    # Skapa hierarkisk struktur
    hierarki = {}
    for person in alla_personer:
        avd_namn = person['avdelning_namn']
        enh_namn = person['enhet_namn']
        
        if avd_namn not in hierarki:
            hierarki[avd_namn] = {}
        if enh_namn not in hierarki[avd_namn]:
            hierarki[avd_namn][enh_namn] = []
            
        hierarki[avd_namn][enh_namn].append(person)

    # Visa personer i hierarkisk struktur
    for avd_namn, enheter in sorted(hierarki.items()):
        st.markdown(f"### {avd_namn}")
        
        # Konvertera till lista för att kunna kolla sista enheten
        sorterade_enheter = list(sorted(enheter.items()))
        for i, (enh_namn, personer) in enumerate(sorterade_enheter):
            st.markdown(f"#### &nbsp;&nbsp;&nbsp;&nbsp;{enh_namn}")
            
            for person in sorted(personer, key=lambda x: x['namn']):
                person_id = str(person['_id'])
                with st.expander(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{person['namn']} - {person['yrkestitel']}"):
                    # Dropdowns utanför formuläret
                    alla_forvaltningar = list(db.forvaltningar.find())
                    forv_index = next((i for i, f in enumerate(alla_forvaltningar)
                                       if f["_id"] == st.session_state[f"forv_{person['_id']}"]), 0)

                    ny_forv = st.selectbox(
                        "Förvaltning",
                        options=[f["namn"] for f in alla_forvaltningar],
                        index=forv_index,
                        key=f"forv_select_{person['_id']}"
                    )
                    vald_forv = next(f for f in alla_forvaltningar if f["namn"] == ny_forv)
                    st.session_state[f"forv_{person['_id']}"] = vald_forv["_id"]

                    # Avdelning dropdown
                    avd_for_forv = list(db.avdelningar.find({"forvaltning_id": vald_forv["_id"]}))
                    if avd_for_forv:
                        try:
                            avd_index = next((i for i, a in enumerate(avd_for_forv)
                                              if a["_id"] == st.session_state[f"avd_{person['_id']}"]), 0)
                        except StopIteration:
                            avd_index = 0

                        ny_avd = st.selectbox(
                            "Avdelning",
                            options=[a["namn"] for a in avd_for_forv],
                            index=avd_index,
                            key=f"avd_select_{person['_id']}"
                        )
                        vald_avd = next(a for a in avd_for_forv if a["namn"] == ny_avd)
                        st.session_state[f"avd_{person['_id']}"] = vald_avd["_id"]

                        # Enhet dropdown
                        enh_for_avd = list(db.enheter.find({"avdelning_id": vald_avd["_id"]}))
                        if enh_for_avd:
                            try:
                                enh_index = next((i for i, e in enumerate(enh_for_avd)
                                                  if e["_id"] == st.session_state[f"enh_{person['_id']}"]), 0)
                            except StopIteration:
                                enh_index = 0

                            ny_enh = st.selectbox(
                                "Enhet",
                                options=[e["namn"] for e in enh_for_avd],
                                index=enh_index,
                                key=f"enh_select_{person['_id']}"
                            )
                            vald_enh = next(e for e in enh_for_avd if e["namn"] == ny_enh)
                            st.session_state[f"enh_{person['_id']}"] = vald_enh["_id"]
                        else:
                            st.warning("Inga enheter finns för den valda avdelningen")
                            vald_enh = None
                    else:
                        st.warning("Inga avdelningar finns för den valda förvaltningen")
                        vald_avd = None
                        vald_enh = None

                    # Formulär för övrig information
                    with st.form(f"edit_person_{person['_id']}"):
                        nytt_namn = st.text_input("Namn", value=person["namn"])
                        ny_yrkestitel = st.text_input("Yrkestitel", value=person["yrkestitel"])

                        # Välj arbetsplats
                        arbetsplatser = list(db.arbetsplatser.find({
                            "$or": [
                                {"forvaltning_id": person["forvaltning_id"]},
                                {"alla_forvaltningar": True}
                            ]
                        }))
                        ny_arbetsplats = st.multiselect(
                            "Arbetsplats",
                            options=[a["namn"] for a in arbetsplatser],
                            default=person.get("arbetsplats", []),
                            help="Välj en eller flera arbetsplatser"
                        )

                        nytt_telefon = st.text_input("Telefon", value=person.get("telefon", ""))

                        # Checkboxar och val för olika roller
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            # CSG
                            st.write("**CSG**")
                            ny_csg = st.checkbox("Sitter i CSG", value=person.get("csg", False))
                            if ny_csg:
                                ny_csg_roll = st.radio(
                                    "Roll i CSG",
                                    options=["Ordinarie", "Ersättare"],
                                    index=0 if person.get("csg_roll") == "Ordinarie" else 1,
                                    key=f"csg_roll_{person['_id']}"
                                )

                            # LSG/FSG
                            st.write("**LSG/FSG**")
                            ny_lsg_fsg = st.checkbox("Sitter i LSG/FSG", value=person.get("lsg_fsg", False))
                            if ny_lsg_fsg:
                                ny_lsg_fsg_roll = st.radio(
                                    "Roll i LSG/FSG",
                                    options=["Ordinarie", "Ersättare"],
                                    index=0 if person.get("lsg_fsg_roll") == "Ordinarie" else 1,
                                    key=f"lsg_fsg_roll_{person['_id']}"
                                )

                        with col2:
                            nytt_skyddsombud = st.checkbox("Skyddsombud",
                                                           value=person.get("skyddsombud", False))
                            nytt_huvudskyddsombud = st.checkbox("Huvudskyddsombud",
                                                                value=person.get("huvudskyddsombud", False))
                            nytt_visionombud = st.checkbox("Visionombud",
                                                           value=person.get("visionombud", False))
                        with col3:
                            nytt_annat_fack = st.checkbox("Medlem i annat fack",
                                                          value=person.get("annat_fack", False))

                        col1, col2 = st.columns(2)
                        with col1:
                            if st.form_submit_button("Spara ändringar"):
                                # Uppdatera person med de senaste värdena från session state
                                uppdaterad_person = {
                                    "namn": nytt_namn,
                                    "yrkestitel": ny_yrkestitel,
                                    "forvaltning_id": vald_forv["_id"],
                                    "forvaltning_namn": vald_forv["namn"],
                                    "avdelning_id": vald_avd["_id"],
                                    "avdelning_namn": vald_avd["namn"],
                                    "enhet_id": vald_enh["_id"],
                                    "enhet_namn": vald_enh["namn"],
                                    "arbetsplats": ny_arbetsplats,
                                    "telefon": nytt_telefon,
                                    "csg": ny_csg,
                                    "csg_roll": ny_csg_roll if ny_csg else None,
                                    "lsg_fsg": ny_lsg_fsg,
                                    "lsg_fsg_roll": ny_lsg_fsg_roll if ny_lsg_fsg else None,
                                    "skyddsombud": nytt_skyddsombud,
                                    "huvudskyddsombud": nytt_huvudskyddsombud,
                                    "visionombud": nytt_visionombud,
                                    "annat_fack": nytt_annat_fack
                                }

                                db.personer.update_one(
                                    {"_id": person["_id"]},
                                    {"$set": uppdaterad_person}
                                )
                                st.success("Person uppdaterad!")
                                st.rerun()

                        with col2:
                            if st.form_submit_button("Ta bort", type="secondary"):
                                db.personer.delete_one({"_id": person["_id"]})
                                st.success(f"{person['namn']} borttagen!")
                                st.rerun()

            # Divider efter varje enhet
            st.markdown("---")
