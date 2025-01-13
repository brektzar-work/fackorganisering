import streamlit as st
import pandas as pd


def show(db):
    st.header("Översikt")

    # Visa huvudskyddsombud överst
    st.subheader("Huvudskyddsombud")
    huvudskyddsombud = list(db.personer.find({"huvudskyddsombud": True}))
    if huvudskyddsombud:
        for person in huvudskyddsombud:
            st.write(f"- {person['namn']} ({person.get('forvaltning_namn', 'Okänd förvaltning')})")
    else:
        st.write("Inga huvudskyddsombud registrerade")

    st.markdown("---")

    # Hämta alla förvaltningar för flikar
    forvaltningar = list(db.forvaltningar.find())

    if not forvaltningar:
        st.warning("Inga förvaltningar tillagda än")
        return

    # Skapa flikar för varje förvaltning
    tabs = st.tabs([f["namn"] for f in forvaltningar])

    for i, tab in enumerate(tabs):
        with tab:
            with st.expander(f"#{i + 1} Uppdragstäckning"):
                forv = forvaltningar[i]

                # Hämta avdelningar för denna förvaltning
                avdelningar = list(db.avdelningar.find({"forvaltning_id": forv["_id"]}))

                if not avdelningar:
                    st.info(f"Inga avdelningar tillagda för {forv['namn']}")
                    continue

                # Dropdown för avdelningar
                avd_namn = st.selectbox(
                    "Välj Avdelning",
                    options=[a["namn"] for a in avdelningar],
                    key=f"avd_select_{forv['_id']}"
                )

                vald_avd = next(a for a in avdelningar if a["namn"] == avd_namn)

                # Hämta enheter för vald avdelning
                enheter = list(db.enheter.find({"avdelning_id": vald_avd["_id"]}))

                if not enheter:
                    st.info(f"Inga enheter tillagda för {avd_namn}")
                    continue

                # Skapa tabell med status
                col1, col2, col3, col4, col5 = st.columns(5)
                with col1:
                    st.markdown("### Enhet")
                with col2:
                    st.markdown("### Visionombud")
                with col3:
                    st.markdown("### Skyddsombud")
                with col4:
                    st.markdown("### LSG/FSG")
                with col5:
                    st.markdown("### CSG")

                st.markdown("---")

                for enhet in sorted(enheter, key=lambda x: x['namn']):
                    col1, col2, col3, col4, col5 = st.columns(5)

                    with col1:
                        st.write(enhet['namn'])

                    with col2:
                        visionombud = list(db.personer.find({
                            "enhet_id": enhet["_id"],
                            "visionombud": True
                        }))
                        if visionombud:
                            st.markdown("✅")
                            for person in visionombud:
                                st.markdown(f"*{person['namn']}*")
                        else:
                            st.markdown("❌")

                    with col3:
                        skyddsombud = list(db.personer.find({
                            "enhet_id": enhet["_id"],
                            "skyddsombud": True
                        }))
                        if skyddsombud:
                            st.markdown("✅")
                            for person in skyddsombud:
                                st.markdown(f"*{person['namn']}*")
                        else:
                            st.markdown("❌")

                    with col4:
                        lsg_personer = list(db.personer.find({
                            "enhet_id": enhet["_id"],
                            "lsg_fsg": True
                        }))
                        if lsg_personer:
                            st.markdown("✅")
                            for person in lsg_personer:
                                roll = f" ({person.get('lsg_fsg_roll', 'Okänd roll')})"
                                st.markdown(f"*{person['namn']}{roll}*")
                        else:
                            st.markdown("❌")

                    with col5:
                        csg_personer = list(db.personer.find({
                            "enhet_id": enhet["_id"],
                            "csg": True
                        }))
                        if csg_personer:
                            st.markdown("✅")
                            for person in csg_personer:
                                roll = f" ({person.get('csg_roll', 'Okänd roll')})"
                                st.markdown(f"*{person['namn']}{roll}*")
                        else:
                            st.markdown("❌")
                    st.divider()

            # Visa styrelser och nämnder för denna förvaltning
            st.markdown("---")
            st.subheader("Styrelser och Nämnder")

            boards = list(db.boards.find({"forvaltning_id": forv["_id"]}))
            if boards:
                # Gruppera efter typ
                bestallar_boards = [b for b in boards if b.get("typ") == "Beställare"]
                utforar_boards = [b for b in boards if b.get("typ") == "Utförare"]

                if bestallar_boards:
                    st.markdown("### Beställarnämnder")
                    for board in bestallar_boards:
                        st.markdown(f"#### {board['namn']}")
                        col1, col2 = st.columns(2)

                        with col1:
                            st.markdown("**Ordinarie:**")
                            if board.get("ledamoter"):
                                for ledamot in board["ledamoter"]:
                                    st.markdown(f"* {ledamot}")
                            else:
                                st.markdown("*Inga ordinarie representanter*")

                        with col2:
                            st.markdown("**Ersättare:**")
                            if board.get("ersattare"):
                                for ersattare in board["ersattare"]:
                                    st.markdown(f"* {ersattare}")
                            else:
                                st.markdown("*Inga ersättare*")

                        st.markdown("---")

                if utforar_boards:
                    st.markdown("### Utförarnämnder")
                    for board in utforar_boards:
                        st.markdown(f"#### {board['namn']}")
                        col1, col2 = st.columns(2)

                        with col1:
                            st.markdown("**Ordinarie:**")
                            if board.get("ledamoter"):
                                for ledamot in board["ledamoter"]:
                                    st.markdown(f"* {ledamot}")
                            else:
                                st.markdown("*Inga ordinarie representanter*")

                        with col2:
                            st.markdown("**Ersättare:**")
                            if board.get("ersattare"):
                                for ersattare in board["ersattare"]:
                                    st.markdown(f"* {ersattare}")
                            else:
                                st.markdown("*Inga ersättare*")

                        st.markdown("---")
            else:
                st.info("Inga styrelser eller nämnder registrerade för denna förvaltning")
