import streamlit as st


def show(db):
    st.header("Styrelser och Nämnder")

    # Lägg till ny styrelse/nämnd
    with st.expander("Lägg till Styrelse/Nämnd"):
        with st.form("add_board"):
            namn = st.text_input("Namn på styrelse/nämnd")

            # Hämta alla visionombud
            visionombud = list(db.personer.find({"visionombud": True}))
            visionombud_namn = [p["namn"] for p in visionombud]

            # Ordinarie representanter
            st.subheader("Ordinarie representanter")
            valda_ledamoter = st.multiselect(
                "Välj visionombud",
                options=visionombud_namn,
                default=[]
            )

            # Ersättare
            st.subheader("Ersättare")
            valda_ersattare = st.multiselect(
                "Välj visionombud",
                options=visionombud_namn,
                default=[],
                key="ersattare_select"
            )

            if st.form_submit_button("Spara"):
                if namn and (valda_ledamoter or valda_ersattare):
                    board = {
                        "namn": namn,
                        "ledamoter": valda_ledamoter,
                        "ersattare": valda_ersattare
                    }
                    db.boards.insert_one(board)
                    st.success("Styrelse/Nämnd sparad!")
                    st.rerun()
                else:
                    st.error("Namn och minst en representant eller ersättare krävs")

    # Lista och redigera befintliga styrelser/nämnder
    st.subheader("Befintliga Styrelser och Nämnder")

    boards = list(db.boards.find())
    for board in boards:
        with st.expander(board["namn"]):
            with st.form(f"edit_board_{board['_id']}"):
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

                col1, col2 = st.columns(2)
                with col1:
                    if st.form_submit_button("Spara ändringar"):
                        db.boards.update_one(
                            {"_id": board["_id"]},
                            {"$set": {
                                "namn": nytt_namn,
                                "ledamoter": valda_ledamoter,
                                "ersattare": valda_ersattare
                            }}
                        )
                        st.success("Ändringar sparade!")
                        st.rerun()

                with col2:
                    if st.form_submit_button("Ta bort", type="secondary"):
                        db.boards.delete_one({"_id": board["_id"]})
                        st.success(f"{board['namn']} borttagen!")
                        st.rerun()
