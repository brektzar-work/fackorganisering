import streamlit as st
from auth import hash_password, verify_password
from views.custom_logging import log_action, current_time


def show_first_time_setup(db):
    """Visar engångsformulär för att skapa admin-användare"""
    st.markdown("""
        <div style="text-align: center; margin-bottom: 2rem;">
            <img src="https://varumarke.vision.se/brandcenter/upload_path/visionbc/1561468181kx13j36au2.gif" 
                 style="max-width: 200px;">
            <h2 style="color: #EFE9E5;">Vision Sektion 10 - Första installation</h2>
        </div>
    """, unsafe_allow_html=True)

    st.info("### 👋 Välkommen till Vision Sektion 10!")
    st.write("För att komma igång behöver du skapa ett administratörskonto.")

    with st.form("create_admin"):
        username = st.text_input("Välj användarnamn för admin", value="admin")
        password = st.text_input("Välj lösenord", type="password")
        confirm_password = st.text_input("Bekräfta lösenord", type="password")

        submitted = st.form_submit_button("Skapa administratörskonto")

        if submitted:
            if password != confirm_password:
                st.error("Lösenorden matchar inte!")
                return

            if len(password) < 6:
                st.error("Lösenordet måste vara minst 6 tecken långt!")
                return

            if not any(c.isdigit() for c in password):
                st.error("Lösenordet måste innehålla minst en siffra!")
                return

            try:
                # Skapa users collection och index
                if 'users' not in db.list_collection_names():
                    db.create_collection('users')
                db.users.create_index([("username", 1)], unique=True)

                # Skapa admin-användare
                admin_user = {
                    "username": username,
                    "password": hash_password(password),
                    "role": "admin",
                    "created_at": current_time(),
                    "last_login": None,
                    "failed_login_attempts": 0,
                    "last_failed_login": None,
                    "account_locked": False,
                    "password_changed": True
                }

                db.users.insert_one(admin_user)
                st.success("✅ Administratörskonto skapat!")

                # Verifiera att användaren skapades korrekt
                created_user = db.users.find_one({"username": username})
                if created_user and verify_password(password, created_user["password"]):
                    log_action("create", f"Skapade administratörskonto: {username}", "user")
                    st.session_state.first_time_setup_done = True
                    st.rerun()
                else:
                    st.error("Något gick fel vid skapandet av kontot!")

            except Exception as e:
                st.error(f"Kunde inte skapa administratörskonto: {str(e)}")
