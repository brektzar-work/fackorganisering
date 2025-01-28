"""
Administrationsmodul för Vision Sektion 10

Denna modul tillhandahåller administrativa funktioner för systemet:
- Användarhantering (skapa, redigera, radera)
- Loggvisning och analys
- Systemkonfiguration
"""

import streamlit as st
from views.cache_manager import get_cached_data, update_cache_after_change
from views.custom_logging import log_action


def show(db):
    """
    Visar och hanterar administrativa funktioner.
    
    Denna funktion hanterar den övergripande administrationen av systemet
    genom flera flikar för olika administrativa uppgifter.
    
    Args:
        db: MongoDB-databasanslutning
    """
    st.header("Administration")

    # Ladda cachad data
    cached, indexes = get_cached_data(db)
    
    # Uppdateringsknapp i sidofältet
    if st.sidebar.button("↻ Uppdatera data", key="refresh_admin"):
        cached, indexes = get_cached_data(db, force_refresh=True)
        st.rerun()

    # Skapa flikar för olika administrativa funktioner
    tab1, tab2, tab3 = st.tabs(["Datahantering", "Användarhantering", "Systemlogg"])

    with tab1:
        st.subheader("Datahantering")
        
        # Visa databasstatistik
        st.markdown("### Databasstatistik")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Personer", len(cached['personer']))
            st.metric("Arbetsplatser", len(cached['arbetsplatser']))
        with col2:
            st.metric("Förvaltningar", len(cached['forvaltningar']))
            st.metric("Avdelningar", len(cached['avdelningar']))
        with col3:
            st.metric("Enheter", len(cached['enheter']))
            st.metric("Styrelser & Nämnder", len(cached.get('boards', [])))
        
        # Databasunderhåll
        st.markdown("### Databasunderhåll")
        with st.expander("Rensa bort oanvända referenser"):
            if st.button("🧹 Rensa databasen"):
                # Rensa bort oanvända arbetsplatser
                result = db.arbetsplatser.delete_many({
                    "_id": {"$nin": [p.get('arbetsplats_id') for p in cached['personer'] if p.get('arbetsplats_id')]}
                })
                if result.deleted_count > 0:
                    update_cache_after_change(db, 'arbetsplatser', 'delete')
                    log_action("maintenance", f"Rensade bort {result.deleted_count} oanvända arbetsplatser", "admin")
                
                # Rensa bort oanvända enheter
                result = db.enheter.delete_many({
                    "_id": {"$nin": [p.get('enhet_id') for p in cached['personer'] if p.get('enhet_id')]}
                })
                if result.deleted_count > 0:
                    update_cache_after_change(db, 'enheter', 'delete')
                    log_action("maintenance", f"Rensade bort {result.deleted_count} oanvända enheter", "admin")
                
                # Rensa bort oanvända avdelningar
                result = db.avdelningar.delete_many({
                    "_id": {"$nin": [e.get('avdelning_id') for e in cached['enheter'] if e.get('avdelning_id')]}
                })
                if result.deleted_count > 0:
                    update_cache_after_change(db, 'avdelningar', 'delete')
                    log_action("maintenance", f"Rensade bort {result.deleted_count} oanvända avdelningar", "admin")
                
                st.success("Databasen har rensats från oanvända referenser!")
                st.rerun()

    with tab2:
        st.subheader("Användarhantering")
        
        # Visa befintliga användare
        users = list(db.users.find())
        st.markdown("### Befintliga användare")
        for user in users:
            with st.expander(f"👤 {user['username']} ({user.get('role', 'Användare')})"):
                with st.form(f"edit_user_{user['_id']}"):
                    new_role = st.selectbox(
                        "Roll",
                        options=["Admin", "Användare"],
                        index=0 if user.get('role') == "Admin" else 1
                    )
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.form_submit_button("Spara ändringar"):
                            result = db.users.update_one(
                                {"_id": user["_id"]},
                                {"$set": {"role": new_role}}
                            )
                            if result.modified_count > 0:
                                log_action("update", f"Uppdaterade roll för användare: {user['username']}", "admin")
                                st.success("Användarroll uppdaterad!")
                                st.rerun()
                    
                    with col2:
                        if st.form_submit_button("Ta bort", type="secondary"):
                            if user['username'] != "admin":  # Skydda admin-kontot
                                db.users.delete_one({"_id": user["_id"]})
                                log_action("delete", f"Tog bort användare: {user['username']}", "admin")
                                st.success("Användare borttagen!")
                                st.rerun()
                            else:
                                st.error("Kan inte ta bort admin-kontot!")
        
        # Lägg till ny användare
        with st.expander("➕ Lägg till användare"):
            with st.form("add_user"):
                username = st.text_input("Användarnamn")
                password = st.text_input("Lösenord", type="password")
                role = st.selectbox("Roll", ["Användare", "Admin"])
                
                if st.form_submit_button("Lägg till användare"):
                    if username and password:
                        if not db.users.find_one({"username": username}):
                            db.users.insert_one({
                                "username": username,
                                "password": password,  # I praktiken bör detta hashas
                                "role": role
                            })
                            log_action("create", f"Skapade ny användare: {username}", "admin")
                            st.success("Användare tillagd!")
                            st.rerun()
                        else:
                            st.error("Användarnamnet är redan taget!")
                    else:
                        st.error("Både användarnamn och lösenord krävs!")

    with tab3:
        st.subheader("Systemlogg")
        
        # Hämta och visa systemloggar
        logs = list(db.logs.find().sort("timestamp", -1).limit(100))
        
        # Filtrera loggar
        log_filter = st.multiselect(
            "Filtrera efter kategori",
            options=["create", "update", "delete", "maintenance", "login"],
            default=["create", "update", "delete", "maintenance"]
        )
        
        # Visa filtrerade loggar
        filtered_logs = [log for log in logs if log.get('action') in log_filter]
        if filtered_logs:
            for log in filtered_logs:
                st.markdown(
                    f"**{log.get('timestamp').strftime('%Y-%m-%d %H:%M:%S')}** - "
                    f"_{log.get('action').upper()}_ - {log.get('message')}"
                )
        else:
            st.info("Inga loggar att visa med valda filter.")