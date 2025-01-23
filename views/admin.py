"""
Administrationsmodul för Vision Sektion 10

Denna modul tillhandahåller administrativa funktioner för systemet:
- Användarhantering (skapa, redigera, radera)
- Loggvisning och analys
- Systemkonfiguration
"""

import streamlit as st
import pandas as pd
from auth import hash_password, create_user
from views.custom_logging import log_action, current_time


def show(db):
    """
    Visar administratörsgränssnittet med olika funktioner.
    
    Denna funktion hanterar den övergripande administrationen av systemet
    genom flera flikar för olika administrativa uppgifter.
    
    Args:
        db: MongoDB-databasanslutning
    """
    st.title("🔧 Administrationspanel")
    
    # Skapa flikar för olika administrativa funktioner
    tab1, tab2, tab3 = st.tabs([
        "👥 Användarhantering",
        "📋 Systemloggar",
        "⚙️ Systeminställningar"
    ])
    
    # Flik 1: Användarhantering
    with tab1:
        st.header("👥 Användarhantering")
        
        # Skapa ny användare
        with st.expander("➕ Skapa ny användare", expanded=False):
            with st.form("create_user_form"):
                new_username = st.text_input("Användarnamn")
                new_password = st.text_input("Lösenord", type="password")
                confirm_password = st.text_input("Bekräfta lösenord", type="password")
                role = st.selectbox("Roll", ["user", "admin"])
                
                if st.form_submit_button("Skapa användare"):
                    if new_password != confirm_password:
                        st.error("Lösenorden matchar inte!")
                    elif len(new_password) < 6:
                        st.error("Lösenordet måste vara minst 6 tecken långt!")
                    elif not any(c.isdigit() for c in new_password):
                        st.error("Lösenordet måste innehålla minst en siffra!")
                    else:
                        success, message = create_user(db, new_username, new_password, role)
                        if success:
                            st.success(f"✅ {message}")
                        else:
                            st.error(f"❌ {message}")
        
        # Lista och hantera befintliga användare
        st.subheader("Hantera befintliga användare")
        users = list(db.users.find({}, {'password': 0}))  # Exkludera lösenord
        
        if not users:
            st.warning("Inga användare hittades.")
        else:
            # Konvertera till DataFrame för bättre visning
            df_users = pd.DataFrame(users)
            df_users = df_users.drop('_id', axis=1)
            
            # Visa användartabell
            st.dataframe(df_users)
            
            # Redigera/radera användare
            col1, col2 = st.columns(2)
            
            with col1:
                with st.expander("✏️ Redigera användare"):
                    user_to_edit = st.selectbox(
                        "Välj användare att redigera",
                        [u['username'] for u in users]
                    )
                    
                    if user_to_edit:
                        with st.form("edit_user_form"):
                            new_role = st.selectbox(
                                "Ny roll",
                                ["user", "admin"],
                                index=0 if users[0]['role'] == 'user' else 1
                            )
                            new_pass = st.text_input(
                                "Nytt lösenord (lämna tomt för att behålla nuvarande)",
                                type="password"
                            )
                            
                            if st.form_submit_button("Uppdatera användare"):
                                update_data = {"role": new_role}
                                if new_pass:
                                    if len(new_pass) < 6:
                                        st.error("Lösenordet måste vara minst 6 tecken långt!")
                                        return
                                    if not any(c.isdigit() for c in new_pass):
                                        st.error("Lösenordet måste innehålla minst en siffra!")
                                        return
                                    update_data["password"] = hash_password(new_pass)
                                
                                try:
                                    db.users.update_one(
                                        {"username": user_to_edit},
                                        {"$set": update_data}
                                    )
                                    log_action("update", f"Uppdaterade användare: {user_to_edit}", "user")
                                    st.success("✅ Användare uppdaterad!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Kunde inte uppdatera användare: {str(e)}")
            
            with col2:
                with st.expander("🗑️ Radera användare"):
                    user_to_delete = st.selectbox(
                        "Välj användare att radera",
                        [u['username'] for u in users if u['username'] != st.session_state.username]
                    )
                    
                    if user_to_delete:
                        if st.button(f"Radera {user_to_delete}", type="primary"):
                            try:
                                db.users.delete_one({"username": user_to_delete})
                                log_action("delete", f"Raderade användare: {user_to_delete}", "user")
                                st.success(f"✅ Användare {user_to_delete} raderad!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Kunde inte radera användare: {str(e)}")
    
    # Flik 2: Systemloggar
    with tab2:
        st.header("📋 Systemloggar")
        
        # Hämta unika kategorier från loggar
        categories = list(db.logs.distinct("category"))
        selected_category = st.selectbox("Välj kategori", ["Alla"] + categories)
        
        # Hämta loggar baserat på vald kategori
        if selected_category == "Alla":
            logs = list(db.logs.find().sort("timestamp", -1).limit(1000))
        else:
            logs = list(db.logs.find({"category": selected_category}).sort("timestamp", -1).limit(1000))
        
        if not logs:
            st.warning("Inga loggar hittades.")
        else:
            # Konvertera till DataFrame för bättre visning
            df_logs = pd.DataFrame(logs)
            df_logs = df_logs.drop('_id', axis=1)
            
            # Visa loggtabell
            st.dataframe(df_logs)
            
            # Exportera loggar
            if st.button("📥 Exportera loggar till Excel"):
                try:
                    # Skapa Excel-fil i minnet
                    output = pd.ExcelWriter('logs_export.xlsx', engine='xlsxwriter')
                    df_logs.to_excel(output, index=False, sheet_name='Loggar')
                    output.close()
                    
                    # Erbjud nedladdning
                    with open('logs_export.xlsx', 'rb') as f:
                        st.download_button(
                            "⬇️ Ladda ner Excel-fil",
                            f,
                            file_name='logs_export.xlsx',
                            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                        )
                except Exception as e:
                    st.error(f"Kunde inte exportera loggar: {str(e)}")
    
    # Flik 3: Systeminställningar
    with tab3:
        st.header("⚙️ Systeminställningar")
        st.info("Framtida funktionalitet för systeminställningar kommer att implementeras här.")