"""
Hanteringsmodul för Styrelser och Nämnder i Vision Sektion 10

Denna modul hanterar alla styrelser och nämnder i systemet:
- Skapar nya styrelser och nämnder
- Redigerar befintliga styrelser
- Hanterar representanter och ersättare
- Grupperar styrelser per förvaltning
- Skiljer på beställar- och utförarnämnder

Varje styrelse/nämnd har:
- Ett namn och en typ (beställare/utförare)
- Koppling till en förvaltning
- Lista på ordinarie representanter
- Lista på ersättare

Tekniska detaljer:
- Använder Streamlit för användargränssnittet
- Sparar data i MongoDB
- Loggar alla ändringar för spårbarhet
- Uppdaterar gränssnittet automatiskt vid ändringar
"""

import streamlit as st
from views.cache_manager import get_cached_data, update_cache_after_change
from views.custom_logging import log_action


def show(db):
    """
    Visar och hanterar gränssnittet för styrelser och nämnder.
    
    Funktionen låter användaren:
    - Se alla styrelser grupperade per förvaltning
    - Lägga till nya styrelser/nämnder
    - Välja representanter från förvaltningens personal
    - Redigera eller ta bort befintliga styrelser
    
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
                vald_forv = next(f for f in cached['forvaltningar'] if f["namn"] == forv_namn)
                
                # Hämta personer i förvaltningen
                personer_i_forv = [p for p in cached['personer'] 
                                 if str(p.get('forvaltning_id')) == str(vald_forv["_id"])]
                person_options = [(str(p["_id"]), f"{p['namn']} - {p.get('yrkestitel', 'Ingen titel')}") 
                                for p in personer_i_forv]
                
                # Representanter
                st.subheader("Representanter")
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**Ordinarie representanter**")
                    representanter = st.multiselect(
                        "Välj ordinarie representanter",
                        options=[opt[0] for opt in person_options],
                        format_func=lambda x: next(opt[1] for opt in person_options if opt[0] == x)
                    )
                
                with col2:
                    st.markdown("**Ersättare**")
                    ersattare = st.multiselect(
                        "Välj ersättare",
                        options=[opt[0] for opt in person_options],
                        format_func=lambda x: next(opt[1] for opt in person_options if opt[0] == x),
                        key="ersattare"
                    )
                
                submitted = st.form_submit_button("Lägg till Styrelse/Nämnd")
                
                if submitted and namn and forv_namn:
                    # Konvertera person IDs till namn för lagring
                    representant_namn = [next(p['namn'] for p in personer_i_forv if str(p['_id']) == l_id) 
                                  for l_id in representanter]
                    ersattare_namn = [next(p['namn'] for p in personer_i_forv if str(p['_id']) == e_id) 
                                    for e_id in ersattare]
                    
                    board = {
                        "namn": namn,
                        "typ": typ,
                        "forvaltning_id": vald_forv["_id"],
                        "forvaltning_namn": vald_forv["namn"],
                        "representanter": representant_namn,
                        "ersattare": ersattare_namn,
                        "representant_ids": representanter,
                        "ersattare_ids": ersattare
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
    
    # Debug information
    # st.write("Debug information:")
    # st.write(f"Number of förvaltningar: {len(cached['forvaltningar'])}")
    # st.write(f"Total boards in cache: {len(cached.get('boards', []))}")
    
    # Gruppera efter förvaltning
    for forv in cached['forvaltningar']:
        boards = [b for b in cached.get('boards', []) if b.get('forvaltning_id') == forv['_id']]
        #st.write(f"Boards for {forv['namn']}: {len(boards)}")
        if boards:
            with st.expander(f"{forv['namn']}"):
                # # Debug: Print board details
                # st.write("Board details:")
                # for b in boards:
                #     st.write(f"- {b.get('namn')} (Type: {b.get('typ')})")
                
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
                                
                                # Hämta personer i förvaltningen
                                personer_i_forv = [p for p in cached['personer'] 
                                                 if str(p.get('forvaltning_id')) == str(forv["_id"])]
                                person_options = [(str(p["_id"]), f"{p['namn']} - {p.get('yrkestitel', 'Ingen titel')}") 
                                                for p in personer_i_forv]
                                
                                col1, col2 = st.columns(2)
                                with col1:
                                    st.markdown("**Ordinarie representanter**")
                                    nya_representanter = st.multiselect(
                                        "Välj ordinarie representanter",
                                        options=[opt[0] for opt in person_options],
                                        default=board.get("representant_ids", []),
                                        format_func=lambda x: next(opt[1] for opt in person_options if opt[0] == x)
                                    )
                                
                                with col2:
                                    st.markdown("**Ersättare**")
                                    nya_ersattare = st.multiselect(
                                        "Välj ersättare",
                                        options=[opt[0] for opt in person_options],
                                        default=board.get("ersattare_ids", []),
                                        format_func=lambda x: next(opt[1] for opt in person_options if opt[0] == x),
                                        key=f"ersattare_{board['_id']}"
                                    )
                                
                                col1, col2 = st.columns(2)
                                with col1:
                                    if st.form_submit_button("Spara ändringar"):
                                        # Konvertera person IDs till namn för lagring
                                        nya_representant_namn = [next(p['namn'] for p in personer_i_forv if str(p['_id']) == l_id) 
                                                          for l_id in nya_representanter]
                                        nya_ersattare_namn = [next(p['namn'] for p in personer_i_forv if str(p['_id']) == e_id) 
                                                            for e_id in nya_ersattare]
                                        
                                        result = db.boards.update_one(
                                            {"_id": board["_id"]},
                                            {"$set": {
                                                "namn": nytt_namn,
                                                "typ": ny_typ,
                                                "representanter": nya_representant_namn,
                                                "ersattare": nya_ersattare_namn,
                                                "representant_ids": nya_representanter,
                                                "ersattare_ids": nya_ersattare
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
                                
                                # Hämta personer i förvaltningen
                                personer_i_forv = [p for p in cached['personer'] 
                                                 if str(p.get('forvaltning_id')) == str(forv["_id"])]
                                person_options = [(str(p["_id"]), f"{p['namn']} - {p.get('yrkestitel', 'Ingen titel')}") 
                                                for p in personer_i_forv]
                                
                                col1, col2 = st.columns(2)
                                with col1:
                                    st.markdown("**Ordinarie representanter**")
                                    nya_representanter = st.multiselect(
                                        "Välj ordinarie representanter",
                                        options=[opt[0] for opt in person_options],
                                        default=board.get("representant_ids", []),
                                        format_func=lambda x: next(opt[1] for opt in person_options if opt[0] == x)
                                    )
                                
                                with col2:
                                    st.markdown("**Ersättare**")
                                    nya_ersattare = st.multiselect(
                                        "Välj ersättare",
                                        options=[opt[0] for opt in person_options],
                                        default=board.get("ersattare_ids", []),
                                        format_func=lambda x: next(opt[1] for opt in person_options if opt[0] == x),
                                        key=f"ersattare_{board['_id']}"
                                    )
                                
                                col1, col2 = st.columns(2)
                                with col1:
                                    if st.form_submit_button("Spara ändringar"):
                                        # Konvertera person IDs till namn för lagring
                                        nya_representant_namn = [next(p['namn'] for p in personer_i_forv if str(p['_id']) == l_id) 
                                                          for l_id in nya_representanter]
                                        nya_ersattare_namn = [next(p['namn'] for p in personer_i_forv if str(p['_id']) == e_id) 
                                                            for e_id in nya_ersattare]
                                        
                                        result = db.boards.update_one(
                                            {"_id": board["_id"]},
                                            {"$set": {
                                                "namn": nytt_namn,
                                                "typ": ny_typ,
                                                "representanter": nya_representant_namn,
                                                "ersattare": nya_ersattare_namn,
                                                "representant_ids": nya_representanter,
                                                "ersattare_ids": nya_ersattare
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
