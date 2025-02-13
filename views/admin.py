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
import pandas as pd
from io import BytesIO
from datetime import datetime


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

    with tab2:
        st.subheader("Användarhantering")
        
        # Visa befintliga användare
        users = list(db.users.find())
        st.markdown("### Befintliga användare")
        for user in users:
            with st.expander(f"👤 {user['username']} ({user.get('role', 'Användare')})"):
                col1, col2 = st.columns(2)
                
                # Form for role management
                with col1:
                    with st.form(f"edit_user_{user['_id']}"):
                        st.subheader("Hantera Roll")
                        new_role = st.selectbox(
                            "Roll",
                            options=["Admin", "Användare"],
                            index=0 if user.get('role') == "Admin" else 1
                        )
                        
                        col1_1, col1_2 = st.columns(2)
                        with col1_1:
                            if st.form_submit_button("Spara ändringar"):
                                result = db.users.update_one(
                                    {"_id": user["_id"]},
                                    {"$set": {"role": new_role}}
                                )
                                if result.modified_count > 0:
                                    log_action("update", f"Uppdaterade roll för användare: {user['username']}", "admin")
                                    st.success("Användarroll uppdaterad!")
                                    st.rerun()
                        
                        with col1_2:
                            if st.form_submit_button("Ta bort", type="secondary"):
                                if user['username'] != "admin":  # Skydda admin-kontot
                                    db.users.delete_one({"_id": user["_id"]})
                                    log_action("delete", f"Tog bort användare: {user['username']}", "admin")
                                    st.success("Användare borttagen!")
                                    st.rerun()
                                else:
                                    st.error("Kan inte ta bort admin-kontot!")
                
                # Form for password management
                with col2:
                    with st.form(f"change_password_{user['_id']}"):
                        st.subheader("Byt Lösenord")
                        new_password = st.text_input("Nytt lösenord", type="password")
                        confirm_password = st.text_input("Bekräfta nytt lösenord", type="password")
                        
                        if st.form_submit_button("Byt lösenord"):
                            if not new_password or not confirm_password:
                                st.error("Båda fälten måste fyllas i!")
                            elif new_password != confirm_password:
                                st.error("Lösenorden matchar inte!")
                            elif len(new_password) < 8:
                                st.error("Lösenordet måste vara minst 8 tecken långt!")
                            else:
                                # Import hash_password from auth module
                                from auth import hash_password
                                hashed_password = hash_password(new_password)
                                result = db.users.update_one(
                                    {"_id": user["_id"]},
                                    {"$set": {"password": hashed_password}}
                                )
                                if result.modified_count > 0:
                                    log_action("update", f"Bytte lösenord för användare: {user['username']}", "admin")
                                    st.success("Lösenord uppdaterat!")
                                    st.rerun()
        
        # Lägg till ny användare
        with st.expander("➕ Lägg till användare"):
            with st.form("add_user"):
                username = st.text_input("Användarnamn")
                password = st.text_input("Lösenord", type="password")
                confirm_password = st.text_input("Bekräfta lösenord", type="password")
                role = st.selectbox("Roll", ["Användare", "Admin"])
                
                if st.form_submit_button("Lägg till användare"):
                    if not username or not password or not confirm_password:
                        st.error("Alla fält måste fyllas i!")
                    elif password != confirm_password:
                        st.error("Lösenorden matchar inte!")
                    elif len(password) < 8:
                        st.error("Lösenordet måste vara minst 8 tecken långt!")
                    else:
                        if not db.users.find_one({"username": username}):
                            # Import hash_password from auth module
                            from auth import hash_password
                            hashed_password = hash_password(password)
                            db.users.insert_one({
                                "username": username,
                                "password": hashed_password,
                                "role": role
                            })
                            log_action("create", f"Skapade ny användare: {username}", "admin")
                            st.success("Användare tillagd!")
                            st.rerun()
                        else:
                            st.error("Användarnamnet är redan taget!")

    with tab3:
        st.subheader("Systemlogg")
        
        # Hämta och visa systemloggar
        logs = list(db.logs.find().sort("timestamp", -1).limit(100))
        
        # Add export and clear buttons in columns
        col1, col2, col3 = st.columns([1, 1, 4])
        with col1:
            if st.button("📥 Exportera loggar"):
                # Create a BytesIO object to store the Excel file
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    # Group logs by action type
                    for action_type in ["create", "update", "delete", "login", "logout", "failed_login"]:
                        action_logs = [log for log in logs if log.get('action') == action_type]
                        if action_logs:
                            # Convert logs to DataFrame
                            df = pd.DataFrame([{
                                'Tidstämpel': log.get('timestamp', ''),
                                'Typ': log.get('action', '').upper(),
                                'Användare': log.get('username', 'System'),
                                'Beskrivning': log.get('description', ''),
                                'Kategori': log.get('category', '')
                            } for log in action_logs])
                            
                            # Write to Excel sheet
                            df.to_excel(writer, sheet_name=action_type.capitalize(), index=False)
                
                # Prepare the file for download
                output.seek(0)
                
                # Get current timestamp for filename
                current_timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
                
                # Create download button
                st.download_button(
                    label="💾 Spara Excel-fil",
                    data=output,
                    file_name=f"systemloggar_{current_timestamp}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    help="Ladda ner loggarna som en Excel-fil med en flik per händelsetyp"
                )
        
        with col2:
            if st.button("🗑️ Rensa loggar", type="secondary", help="Ta bort alla loggar från systemet"):
                if st.session_state.get('confirm_delete_logs', False):
                    # Get the username of who is clearing the logs
                    username = st.session_state.get('username', 'System')
                    # Clear the logs
                    db.logs.delete_many({})
                    log_action("delete", f"Systemloggar rensade av {username}", "admin")
                    st.success(f"Alla loggar har rensats av {username}!")
                    st.session_state.confirm_delete_logs = False
                    st.rerun()
                else:
                    st.session_state.confirm_delete_logs = True
                    st.warning("Klicka igen för att bekräfta rensning av alla loggar")
        
        # Filtrera loggar
        log_filter = st.multiselect(
            "Filtrera efter kategori",
            options=["create", "update", "delete", "login", "logout", "failed_login"],
            default=["create", "update", "delete", "login", "logout", "failed_login"],
            help="Välj vilka typer av händelser som ska visas i loggen"
        )
        
        # Visa filtrerade loggar
        filtered_logs = [log for log in logs if log.get('action') in log_filter]
        if filtered_logs:
            for log in filtered_logs:
                # Handle timestamp as string since it's already formatted
                timestamp = log.get('timestamp', '')
                if isinstance(timestamp, str):
                    formatted_time = timestamp
                else:
                    try:
                        formatted_time = timestamp.strftime('%Y-%m-%d %H:%M:%S')
                    except AttributeError:
                        formatted_time = str(timestamp)
                
                # Get username with fallback to "System"
                username = log.get('username', 'System')
                
                st.markdown(
                    f"**{formatted_time}** - "
                    f"_{log.get('action', '').upper()}_ - "
                    f"👤 {username} - "
                    f"{log.get('description', '')}"
                )
        else:
            st.info("Inga loggar att visa med valda filter.")