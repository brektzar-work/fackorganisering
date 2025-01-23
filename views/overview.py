"""
Översiktsmodul för Vision Sektion 10.

Detta system ger en omfattande översikt över organisationens struktur och representation:
1. Huvudskyddsombud - Visar alla huvudskyddsombud i organisationen
2. Förvaltningsvis översikt:
   - Uppdragstäckning per avdelning och enhet
   - Representation i styrelser och nämnder
   - Status för fackliga roller och uppdrag

Modulen tillhandahåller funktionalitet för att:
- Visa hierarkisk organisationsstruktur
- Spåra representation på alla nivåer
- Visualisera täckningsgrad för olika uppdrag
- Presentera styrelser och nämnder med representanter

Tekniska detaljer:
- Använder MongoDB för dataåtkomst
- Implementerar dynamisk filtrering och gruppering
- Hanterar komplex datavisualisering via Streamlit
- Tillhandahåller interaktiv användarupplevelse
"""

import streamlit as st
import pandas as pd


def show(db):
    """Visar huvudöversikten för Vision Sektion 10.
    
    Denna komplexa funktion hanterar tre huvudområden:
    1. Huvudskyddsombud
       - Visar alla aktiva huvudskyddsombud
       - Grupperar efter förvaltning
    
    2. Uppdragstäckning
       - Visar täckningsgrad per enhet för:
         * Visionombud
         * Skyddsombud
         * LSG/FSG-representanter
         * CSG-representanter
       - Implementerar filtrering per avdelning
    
    3. Styrelser och Nämnder
       - Visar representation i:
         * Beställarnämnder
         * Utförarnämnder
       - Hanterar både ordinarie och ersättare
    
    Args:
        db: MongoDB-databasanslutning med tillgång till collections för:
           - personer
           - forvaltningar
           - avdelningar
           - enheter
           - boards
    """
    st.header("Översikt")

    # Sektion för huvudskyddsombud
    # Visar alla aktiva huvudskyddsombud grupperade efter förvaltning
    st.subheader("Huvudskyddsombud")
    huvudskyddsombud = list(db.personer.find({"huvudskyddsombud": True}))
    if huvudskyddsombud:
        for person in huvudskyddsombud:
            st.write(f"- {person['namn']} ({person.get('forvaltning_namn', 'Okänd förvaltning')})")
    else:
        st.write("Inga huvudskyddsombud registrerade")

    st.markdown("---")

    # Hämta och validera förvaltningsdata
    # Detta är grunden för den hierarkiska visningen
    forvaltningar = list(db.forvaltningar.find())

    if not forvaltningar:
        st.warning("Inga förvaltningar tillagda än")
        return

    # Skapa dynamiska flikar för varje förvaltning
    # Detta möjliggör effektiv navigation mellan förvaltningar
    tabs = st.tabs([f["namn"] for f in forvaltningar])

    # Iterera över alla förvaltningar och skapa detaljvyer
    for i, tab in enumerate(tabs):
        with tab:
            # Sektion för uppdragstäckning
            # Visar detaljerad status för fackliga roller per enhet
            with st.expander(f"#{i + 1} Uppdragstäckning"):
                forv = forvaltningar[i]

                # Hämta och validera avdelningsdata
                avdelningar = list(db.avdelningar.find({"forvaltning_id": forv["_id"]}))

                if not avdelningar:
                    st.info(f"Inga avdelningar tillagda för {forv['namn']}")
                    continue

                # Implementera dynamisk filtrering per avdelning
                avd_namn = st.selectbox(
                    "Välj Avdelning",
                    options=[a["namn"] for a in avdelningar],
                    key=f"avd_select_{forv['_id']}"
                )

                vald_avd = next(a for a in avdelningar if a["namn"] == avd_namn)

                # Hämta och validera enhetsdata
                enheter = list(db.enheter.find({"avdelning_id": vald_avd["_id"]}))

                if not enheter:
                    st.info(f"Inga enheter tillagda för {avd_namn}")
                    continue

                # Skapa strukturerad tabell för statuspresentation
                # Detta ger en tydlig översikt över representation
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

                # Iterera över enheter och visa detaljerad status
                # Sorterar enheter alfabetiskt för konsekvent visning
                for enhet in sorted(enheter, key=lambda x: x['namn']):
                    col1, col2, col3, col4, col5 = st.columns(5)

                    with col1:
                        st.write(enhet['namn'])

                    # Visa Visionombud med status och namn
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

                    # Visa Skyddsombud med status och namn
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

                    # Visa LSG/FSG-representanter med status, namn och roll
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

                    # Visa CSG-representanter med status, namn och roll
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

            # Sektion för styrelser och nämnder
            # Visar detaljerad information om representation i olika styrelser
            st.markdown("---")
            with st.expander(f"Styrelser & Nämnder"):
                st.subheader("Styrelser och Nämnder")

                # Hämta och gruppera styrelser efter typ
                boards = list(db.boards.find({"forvaltning_id": forv["_id"]}))
                if boards:
                    # Separera styrelser i beställar- och utförarnämnder
                    bestallar_boards = [b for b in boards if b.get("typ") == "Beställare"]
                    utforar_boards = [b for b in boards if b.get("typ") == "Utförare"]

                    # Visa beställarnämnder med representanter
                    if bestallar_boards:
                        st.markdown("### Beställarnämnder")
                        for board in bestallar_boards:
                            st.markdown(f"#### {board['namn']}")
                            col1, col2 = st.columns(2)

                            # Visa ordinarie ledamöter
                            with col1:
                                st.markdown("**Ordinarie:**")
                                if board.get("ledamoter"):
                                    for ledamot in board["ledamoter"]:
                                        st.markdown(f"* {ledamot}")
                                else:
                                    st.markdown("*Inga ordinarie representanter*")

                            # Visa ersättare
                            with col2:
                                st.markdown("**Ersättare:**")
                                if board.get("ersattare"):
                                    for ersattare in board["ersattare"]:
                                        st.markdown(f"* {ersattare}")
                                else:
                                    st.markdown("*Inga ersättare*")

                            st.markdown("---")

                    # Visa utförarnämnder med representanter
                    if utforar_boards:
                        st.markdown("### Utförarnämnder")
                        for board in utforar_boards:
                            st.markdown(f"#### {board['namn']}")
                            col1, col2 = st.columns(2)

                            # Visa ordinarie ledamöter
                            with col1:
                                st.markdown("**Ordinarie:**")
                                if board.get("ledamoter"):
                                    for ledamot in board["ledamoter"]:
                                        st.markdown(f"* {ledamot}")
                                else:
                                    st.markdown("*Inga ordinarie representanter*")

                            # Visa ersättare
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
