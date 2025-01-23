"""
Hanteringsmodul för Styrelser och Nämnder i Vision Sektion 10
Detta system hanterar administration av styrelser och nämnder, inklusive
hantering av ledamöter och ersättare. Modulen tillhandahåller funktionalitet
för att skapa, redigera och ta bort styrelser/nämnder samt hantera deras
medlemmar.

Tekniska detaljer:
- Använder Streamlit för användargränssnittet
- Integrerar med MongoDB för datalagring
- Implementerar loggning av alla ändringar
- Hanterar dynamisk uppdatering av gränssnittet
"""

import streamlit as st
from views.custom_logging import log_action, current_time


def show(db):
    """
    Visar och hanterar gränssnittet för administration av styrelser och nämnder.
    
    Funktionen:
    1. Visar formulär för att skapa nya styrelser/nämnder
    2. Listar befintliga styrelser/nämnder med redigeringsmöjligheter
    3. Hanterar val av ledamöter och ersättare
    4. Loggar alla ändringar i systemet
    
    Args:
        db: MongoDB-databasanslutning med tillgång till boards och personer collections
    
    Tekniska detaljer:
    - Använder Streamlit's expander och forms för strukturerad visning
    - Implementerar multiselect för val av medlemmar
    - Hanterar databasoperationer med felhantering
    - Uppdaterar gränssnittet automatiskt vid ändringar
    """
    st.header("Styrelser och Nämnder")

    # Sektion för att lägga till ny styrelse/nämnd
    with st.expander("Lägg till Styrelse/Nämnd"):
        with st.form("add_board"):
            namn = st.text_input("Namn på styrelse/nämnd")

            # Hämta alla visionombud för val av representanter
            visionombud = list(db.personer.find({"visionombud": True}))
            visionombud_namn = [p["namn"] for p in visionombud]

            # Val av ordinarie representanter
            st.subheader("Ordinarie representanter")
            valda_ledamoter = st.multiselect(
                "Välj visionombud",
                options=visionombud_namn,
                default=[]
            )

            # Val av ersättare
            st.subheader("Ersättare")
            valda_ersattare = st.multiselect(
                "Välj visionombud",
                options=visionombud_namn,
                default=[],
                key="ersattare_select"
            )

            # Hantera sparande av ny styrelse/nämnd
            if st.form_submit_button("Spara"):
                if namn and (valda_ledamoter or valda_ersattare):
                    # Skapa ny styrelse/nämnd i databasen
                    board = {
                        "namn": namn,
                        "ledamoter": valda_ledamoter,
                        "ersattare": valda_ersattare
                    }
                    db.boards.insert_one(board)
                    
                    # Logga skapandet och uppdatera gränssnittet
                    log_action("create", 
                             f"Skapade styrelse/nämnd: {namn} med ledamöter: {', '.join(valda_ledamoter)} "
                             f"och ersättare: {', '.join(valda_ersattare)}", 
                             "board")
                    st.success("Styrelse/Nämnd sparad!")
                    st.rerun()
                else:
                    st.error("Namn och minst en representant eller ersättare krävs")

    # Sektion för att visa och redigera befintliga styrelser/nämnder
    st.subheader("Befintliga Styrelser och Nämnder")

    # Hämta och visa alla styrelser/nämnder
    boards = list(db.boards.find())
    for board in boards:
        with st.expander(board["namn"]):
            with st.form(f"edit_board_{board['_id']}"):
                # Redigera grundläggande information
                nytt_namn = st.text_input("Namn", value=board["namn"])

                # Redigera ordinarie representanter
                st.subheader("Ordinarie representanter")
                valda_ledamoter = st.multiselect(
                    "Välj visionombud",
                    options=visionombud_namn,
                    default=[led for led in board.get("ledamoter", []) if led in visionombud_namn],
                    key=f"ledamoter_{board['_id']}"
                )

                # Redigera ersättare
                st.subheader("Ersättare")
                valda_ersattare = st.multiselect(
                    "Välj visionombud",
                    options=visionombud_namn,
                    default=[ers for ers in board.get("ersattare", []) if ers in visionombud_namn],
                    key=f"ersattare_{board['_id']}"
                )

                # Knappar för att spara ändringar eller ta bort styrelse/nämnd
                col1, col2 = st.columns(2)
                with col1:
                    if st.form_submit_button("Spara ändringar"):
                        # Identifiera vilka ändringar som gjorts
                        changes = []
                        if nytt_namn != board["namn"]:
                            changes.append(f"namn från '{board['namn']}' till '{nytt_namn}'")
                        if valda_ledamoter != board.get("ledamoter", []):
                            changes.append(f"ledamöter från '{', '.join(board.get('ledamoter', []))}' "
                                        f"till '{', '.join(valda_ledamoter)}'")
                        if valda_ersattare != board.get("ersattare", []):
                            changes.append(f"ersättare från '{', '.join(board.get('ersattare', []))}' "
                                        f"till '{', '.join(valda_ersattare)}'")
                            
                        # Uppdatera databasen med ändringarna
                        db.boards.update_one(
                            {"_id": board["_id"]},
                            {"$set": {
                                "namn": nytt_namn,
                                "ledamoter": valda_ledamoter,
                                "ersattare": valda_ersattare
                            }}
                        )
                        
                        # Logga ändringar och uppdatera gränssnittet
                        if changes:
                            log_action("update", 
                                     f"Uppdaterade styrelse/nämnd: {board['namn']} - Ändrade {', '.join(changes)}", 
                                     "board")
                        st.success("Ändringar sparade!")
                        st.rerun()

                with col2:
                    if st.form_submit_button("Ta bort", type="secondary"):
                        # Ta bort styrelse/nämnd och logga händelsen
                        log_action("delete", f"Tog bort styrelse/nämnd: {board['namn']}", "board")
                        db.boards.delete_one({"_id": board["_id"]})
                        st.success(f"{board['namn']} borttagen!")
                        st.rerun()
