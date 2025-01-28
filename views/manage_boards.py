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
from views.cache_manager import get_cached_data, update_cache_after_change
from views.custom_logging import log_action


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
    st.header("Styrelser & Nämnder")

    # Ladda cachad data
    cached, indexes = get_cached_data(db)
    
    # Uppdateringsknapp i sidofältet
    if st.sidebar.button("↻ Uppdatera data", key="refresh_boards"):
        cached, indexes = get_cached_data(db, force_refresh=True)
        st.rerun()

    # Lägg till ny styrelse/nämnd
    with st.expander("Lägg till Styrelse/Nämnd"):
        with st.form("add_board"):
            # Grundläggande information
            namn = st.text_input("Namn på styrelse/nämnd")
            typ = st.selectbox("Typ", ["Beställare", "Utförare"])
            
            # Välj förvaltning
            if not cached['forvaltningar']:
                st.warning("Lägg till minst en förvaltning först")
            else:
                forv_namn = st.selectbox(
                    "Förvaltning",
                    options=[f["namn"] for f in cached['forvaltningar']]
                )
                
                # Representanter
                st.subheader("Representanter")
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**Ordinarie ledamöter**")
                    ledamoter = st.text_area("En per rad", height=100)
                
                with col2:
                    st.markdown("**Ersättare**")
                    ersattare = st.text_area("En per rad", height=100, key="ersattare")
                
                submitted = st.form_submit_button("Lägg till Styrelse/Nämnd")
                
                if submitted and namn and forv_namn:
                    vald_forv = next(f for f in cached['forvaltningar'] if f["namn"] == forv_namn)
                    board = {
                        "namn": namn,
                        "typ": typ,
                        "forvaltning_id": vald_forv["_id"],
                        "forvaltning_namn": vald_forv["namn"],
                        "ledamoter": [l.strip() for l in ledamoter.split("\n") if l.strip()],
                        "ersattare": [e.strip() for e in ersattare.split("\n") if e.strip()]
                    }
                    result = db.boards.insert_one(board)
                    if result.inserted_id:
                        board['_id'] = result.inserted_id
                        update_cache_after_change(db, 'boards', 'create', board)
                        log_action("create", f"Skapade styrelse/nämnd: {namn} under {forv_namn}", "board")
                        st.success("Styrelse/Nämnd tillagd!")
                        st.rerun()

    # Visa och hantera befintliga styrelser/nämnder
    st.subheader("Befintliga Styrelser & Nämnder")
    
    # Gruppera efter förvaltning
    for forv in cached['forvaltningar']:
        boards = [b for b in cached.get('boards', []) if b.get('forvaltning_id') == forv['_id']]
        if boards:
            st.markdown(f"### {forv['namn']}")
            
            # Separera efter typ
            bestallar_boards = [b for b in boards if b.get('typ') == 'Beställare']
            utforar_boards = [b for b in boards if b.get('typ') == 'Utförare']
            
            # Visa beställarnämnder
            if bestallar_boards:
                st.markdown("#### Beställarnämnder")
                for board in bestallar_boards:
                    with st.expander(f"{board['namn']}"):
                        with st.form(f"edit_board_{board['_id']}"):
                            nytt_namn = st.text_input("Namn", value=board["namn"])
                            ny_typ = st.selectbox(
                                "Typ",
                                options=["Beställare", "Utförare"],
                                index=0 if board["typ"] == "Beställare" else 1
                            )
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                st.markdown("**Ordinarie ledamöter**")
                                nya_ledamoter = st.text_area(
                                    "En per rad",
                                    value="\n".join(board.get("ledamoter", [])),
                                    height=100
                                )
                            
                            with col2:
                                st.markdown("**Ersättare**")
                                nya_ersattare = st.text_area(
                                    "En per rad",
                                    value="\n".join(board.get("ersattare", [])),
                                    height=100,
                                    key=f"ersattare_{board['_id']}"
                                )
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                if st.form_submit_button("Spara ändringar"):
                                    result = db.boards.update_one(
                                        {"_id": board["_id"]},
                                        {"$set": {
                                            "namn": nytt_namn,
                                            "typ": ny_typ,
                                            "ledamoter": [l.strip() for l in nya_ledamoter.split("\n") if l.strip()],
                                            "ersattare": [e.strip() for e in nya_ersattare.split("\n") if e.strip()]
                                        }}
                                    )
                                    if result.modified_count > 0:
                                        update_cache_after_change(db, 'boards', 'update')
                                        log_action("update", f"Uppdaterade styrelse/nämnd: {board['namn']}", "board")
                                        st.success("Styrelse/Nämnd uppdaterad!")
                                        st.rerun()
                            
                            with col2:
                                if st.form_submit_button("Ta bort", type="secondary"):
                                    db.boards.delete_one({"_id": board["_id"]})
                                    update_cache_after_change(db, 'boards', 'delete')
                                    log_action("delete", f"Tog bort styrelse/nämnd: {board['namn']}", "board")
                                    st.success("Styrelse/Nämnd borttagen!")
                                    st.rerun()
            
            # Visa utförarnämnder
            if utforar_boards:
                st.markdown("#### Utförarnämnder")
                for board in utforar_boards:
                    with st.expander(f"{board['namn']}"):
                        with st.form(f"edit_board_{board['_id']}"):
                            nytt_namn = st.text_input("Namn", value=board["namn"])
                            ny_typ = st.selectbox(
                                "Typ",
                                options=["Beställare", "Utförare"],
                                index=0 if board["typ"] == "Beställare" else 1
                            )
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                st.markdown("**Ordinarie ledamöter**")
                                nya_ledamoter = st.text_area(
                                    "En per rad",
                                    value="\n".join(board.get("ledamoter", [])),
                                    height=100
                                )
                            
                            with col2:
                                st.markdown("**Ersättare**")
                                nya_ersattare = st.text_area(
                                    "En per rad",
                                    value="\n".join(board.get("ersattare", [])),
                                    height=100,
                                    key=f"ersattare_{board['_id']}"
                                )
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                if st.form_submit_button("Spara ändringar"):
                                    result = db.boards.update_one(
                                        {"_id": board["_id"]},
                                        {"$set": {
                                            "namn": nytt_namn,
                                            "typ": ny_typ,
                                            "ledamoter": [l.strip() for l in nya_ledamoter.split("\n") if l.strip()],
                                            "ersattare": [e.strip() for e in nya_ersattare.split("\n") if e.strip()]
                                        }}
                                    )
                                    if result.modified_count > 0:
                                        update_cache_after_change(db, 'boards', 'update')
                                        log_action("update", f"Uppdaterade styrelse/nämnd: {board['namn']}", "board")
                                        st.success("Styrelse/Nämnd uppdaterad!")
                                        st.rerun()
                            
                            with col2:
                                if st.form_submit_button("Ta bort", type="secondary"):
                                    db.boards.delete_one({"_id": board["_id"]})
                                    update_cache_after_change(db, 'boards', 'delete')
                                    log_action("delete", f"Tog bort styrelse/nämnd: {board['namn']}", "board")
                                    st.success("Styrelse/Nämnd borttagen!")
                                    st.rerun()
