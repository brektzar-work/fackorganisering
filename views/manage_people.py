"""Hanteringsmodul för Personer i Vision Sektion 10.

Detta system hanterar administration av personer inom organisationen.
Inkluderar registrering och hantering av medlemmar, roller och organisationstillhörighet.
"""

import streamlit as st
from views.custom_logging import log_action, current_time
from views.cache_manager import get_cached_data, update_cache_after_change


def show(db):
    """Visar och hanterar gränssnittet för administration av personer.

    Args:
        db: MongoDB-databasanslutning för personer och organisationsdata.
    """
    st.header("Hantera Personer")

    # Ladda cachad data
    cached, indexes = get_cached_data(db)
    
    # Uppdateringsknapp i sidofältet
    if st.sidebar.button("↻ Uppdatera data", key="refresh_people"):
        cached, indexes = get_cached_data(db, force_refresh=True)
        st.rerun()

    # Initiera session state
    if 'ny_arbetsplats' not in st.session_state:
        st.session_state.ny_arbetsplats = False
    if 'redigering_forvaltning' not in st.session_state:
        st.session_state.redigering_forvaltning = {}
    if 'redigering_avdelning' not in st.session_state:
        st.session_state.redigering_avdelning = {}

    # Hierarkisk navigering genom organisationen
    forvaltningar = cached['forvaltningar']

    if forvaltningar:
        forv_namn = st.selectbox(
            "Välj Förvaltning",
            options=[f["namn"] for f in forvaltningar],
            key="forv_select"
        )
        vald_forvaltning = next(f for f in forvaltningar if f["namn"] == forv_namn)

        # Visa avdelningar för vald förvaltning
        avdelningar = indexes['avdelningar_by_forv'].get(vald_forvaltning["_id"], [])
        if avdelningar:
            avd_namn = st.selectbox(
                "Välj Avdelning",
                options=[a["namn"] for a in avdelningar],
                key="avd_select"
            )
            vald_avdelning = next(a for a in avdelningar if a["namn"] == avd_namn)

            # Visa enheter för vald avdelning
            enheter = indexes['enheter_by_avd'].get(vald_avdelning["_id"], [])
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

    # Formulär för att lägga till ny person
    with st.expander("**Lägg till Person**"):
        # Hämta befintliga arbetsplatser för autokomplettering
        alla_arbetsplatser = sorted(list(set(
            arbetsplats for person in cached['personer']
            if person.get('arbetsplats')
            for arbetsplats in person['arbetsplats']
        )))

        with st.form("person_form"):
            # Grundläggande personuppgifter
            namn = st.text_input("Namn")
            yrkestitel = st.text_input("Yrkestitel")
            
            # Kontaktinformation
            col1, col2 = st.columns(2)
            with col1:
                telefon = st.text_input("Telefon (valfritt)")
            with col2:
                email = st.text_input("E-post (valfritt)")

            # Arbetsplatsval med filtrering
            if vald_forvaltning:
                arbetsplatser = indexes['arbetsplatser_by_forv'].get(vald_forvaltning["_id"], [])
                
                if arbetsplatser:
                    arbetsplats = st.multiselect(
                        "Arbetsplats",
                        options=[a["namn"] for a in arbetsplatser],
                        help="Välj en eller flera arbetsplatser"
                    )
                else:
                    st.warning("Inga arbetsplatser finns för den valda förvaltningen")
                    arbetsplats = []
            else:
                st.warning("Välj en förvaltning först")
                arbetsplats = []

            # Roller och uppdrag
            col1, col2, col3 = st.columns(3)
            with col1:
                # CSG (Central Samverkansgrupp)
                st.write("**CSG**")
                csg = st.checkbox("Sitter i CSG")
                if csg:
                    csg_roll = st.radio(
                        "Roll i CSG",
                        options=["Ordinarie", "Ersättare"],
                        key="csg_roll"
                    )

                # LSG/FSG (Lokal/Förvaltnings Samverkansgrupp)
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

            # Hantera formulärinlämning
            submitted = st.form_submit_button("Spara Person")

            if submitted:
                if not arbetsplats:
                    st.error("Arbetsplats måste anges")
                    return

                if vald_forvaltning and vald_avdelning and vald_enhet:
                    # Skapa persondokument
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
                        "email": email,
                        "csg": csg,
                        "csg_roll": csg_roll if csg else None,
                        "lsg_fsg": lsg_fsg,
                        "lsg_fsg_roll": lsg_fsg_roll if lsg_fsg else None,
                        "skyddsombud": skyddsombud,
                        "huvudskyddsombud": huvudskyddsombud,
                        "visionombud": visionombud,
                        "annat_fack": annat_fack
                    }

                    # Spara och logga
                    result = db.personer.insert_one(person)
                    if result.inserted_id:
                        person['_id'] = result.inserted_id  # Add _id for cache
                        update_cache_after_change(db, 'personer', 'create', person)
                        contact_info = []
                        if telefon:
                            contact_info.append(f"telefon: {telefon}")
                        if email:
                            contact_info.append(f"e-post: {email}")
                        contact_str = f" med {' och '.join(contact_info)}" if contact_info else ""
                        log_action("create", f"Skapade person: {namn}{contact_str}", "person")
                        st.success("Person sparad!")
                        st.rerun()
                    else:
                        st.error("Något gick fel när personen skulle sparas")
                else:
                    st.error("Kontrollera att förvaltning, avdelning och enhet är valda")

    st.divider()

    # Visa och redigera befintliga personer
    st.subheader("Befintliga Personer")

    # Visa förvaltningar som expanders istället för dropdown
    forvaltningar = cached['forvaltningar']
    for forvaltning in forvaltningar:
        with st.expander(f"{forvaltning['namn']}"):
            # Hämta personer för denna förvaltning
            personer = list(db.personer.find({"forvaltning_id": forvaltning["_id"]}))

            # Initiera session state för organisationstillhörighet
            for person in personer:
                person_id = str(person['_id'])
                if f"forv_{person_id}" not in st.session_state:
                    st.session_state[f"forv_{person_id}"] = person["forvaltning_id"]
                if f"avd_{person_id}" not in st.session_state:
                    st.session_state[f"avd_{person_id}"] = person["avdelning_id"]
                if f"enh_{person_id}" not in st.session_state:
                    st.session_state[f"enh_{person_id}"] = person["enhet_id"]

            # Skapa hierarkisk struktur för visning
            hierarki = {}
            for person in personer:
                avd_namn = person['avdelning_namn']
                enh_namn = person['enhet_namn']
                
                if avd_namn not in hierarki:
                    hierarki[avd_namn] = {}
                if enh_namn not in hierarki[avd_namn]:
                    hierarki[avd_namn][enh_namn] = []
                    
                hierarki[avd_namn][enh_namn].append(person)

            # Visa personer hierarkiskt
            for avd_namn, enheter in sorted(hierarki.items()):
                st.markdown(f"### {avd_namn}")
                
                sorterade_enheter = list(sorted(enheter.items()))
                for i, (enh_namn, personer) in enumerate(sorterade_enheter):
                    st.markdown(f"#### &nbsp;&nbsp;&nbsp;&nbsp;{enh_namn}")
                    
                    for person in sorted(personer, key=lambda x: x['namn']):
                        person_id = str(person['_id'])
                        with st.expander(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{person['namn']} - {person['yrkestitel']}"):
                            # Organisationstillhörighet
                            alla_forvaltningar = cached['forvaltningar']
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

                            # Avdelningar för vald förvaltning
                            avd_for_forv = indexes['avdelningar_by_forv'].get(vald_forv["_id"], [])
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

                                # Enheter för vald avdelning
                                enh_for_avd = indexes['enheter_by_avd'].get(vald_avd["_id"], [])
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

                            # Redigeringsformulär
                            with st.form(f"edit_person_{person['_id']}"):
                                nytt_namn = st.text_input("Namn", value=person["namn"])
                                ny_yrkestitel = st.text_input("Yrkestitel", value=person["yrkestitel"])
                                
                                # Kontaktinformation
                                col1, col2 = st.columns(2)
                                with col1:
                                    nytt_telefon = st.text_input("Telefon (valfritt)", value=person.get("telefon", ""))
                                with col2:
                                    ny_email = st.text_input("E-post (valfritt)", value=person.get("email", ""))

                                # Arbetsplatsval
                                arbetsplatser = indexes['arbetsplatser_by_forv'].get(person["forvaltning_id"], [])
                                arbetsplats_options = [a["namn"] for a in arbetsplatser]
                                # Filter out any default values that aren't in the options
                                current_arbetsplatser = [ap for ap in person.get("arbetsplats", []) if ap in arbetsplats_options]
                                ny_arbetsplats = st.multiselect(
                                    "Arbetsplats",
                                    options=arbetsplats_options,
                                    default=current_arbetsplatser,
                                    help="Välj en eller flera arbetsplatser"
                                )

                                # Roller och uppdrag
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

                                # Spara eller ta bort
                                col1, col2 = st.columns(2)
                                with col1:
                                    if st.form_submit_button("Spara ändringar"):
                                        # Identifiera ändringar
                                        changes = []
                                        if nytt_namn != person["namn"]:
                                            changes.append(f"namn från '{person['namn']}' till '{nytt_namn}'")
                                        if ny_yrkestitel != person["yrkestitel"]:
                                            changes.append(f"yrkestitel från '{person['yrkestitel']}' till '{ny_yrkestitel}'")
                                        if nytt_telefon != person.get("telefon", ""):
                                            changes.append(f"telefon från '{person.get('telefon', '')}' till '{nytt_telefon}'")
                                        if ny_email != person.get("email", ""):
                                            changes.append(f"e-post från '{person.get('email', '')}' till '{ny_email}'")
                                        
                                        # Uppdatera person
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
                                            "email": ny_email,
                                            "csg": ny_csg,
                                            "csg_roll": ny_csg_roll if ny_csg else None,
                                            "lsg_fsg": ny_lsg_fsg,
                                            "lsg_fsg_roll": ny_lsg_fsg_roll if ny_lsg_fsg else None,
                                            "skyddsombud": nytt_skyddsombud,
                                            "huvudskyddsombud": nytt_huvudskyddsombud,
                                            "visionombud": nytt_visionombud,
                                            "annat_fack": nytt_annat_fack
                                        }

                                        # Spara och logga
                                        result = db.personer.update_one(
                                            {"_id": person["_id"]},
                                            {"$set": uppdaterad_person}
                                        )
                                        
                                        if result.modified_count > 0 and changes:
                                            log_action("update", f"Uppdaterade person: {person['namn']} - Ändrade {', '.join(changes)}", "person")
                                            st.success("Person uppdaterad!")
                                            st.rerun()
                                        else:
                                            st.error("Inga ändringar gjordes")

                                with col2:
                                    if st.form_submit_button("Ta bort", type="secondary"):
                                        log_action("delete", f"Tog bort person: {person['namn']}", "person")
                                        result = db.personer.delete_one({"_id": person["_id"]})
                                        if result.deleted_count > 0:
                                            st.success(f"{person['namn']} borttagen!")
                                            st.rerun()
                                        else:
                                            st.error("Kunde inte ta bort personen")

                            # Visuell separator
                            st.markdown("---")
