"""Första-gångs-konfiguration för Vision Sektion 10."""

import streamlit as st
from views.cache_manager import get_cached_data, update_cache_after_change
from views.custom_logging import log_action


def show_first_time_setup(db):
    """Visar och hanterar första-gångs-konfigurationen."""
    st.header("Första-gångs-konfiguration")

    # Kontrollera om konfigurationen redan är gjord
    if db.forvaltningar.find_one():
        st.success("Systemet är redan konfigurerat!")
        st.info(
            "Om du behöver göra ändringar i grundkonfigurationen, "
            "använd de vanliga administrationssidorna."
        )
        return

    st.markdown("""
    ## Välkommen till Vision Sektion 10!
    
    Detta är första gången du startar systemet. Vi behöver göra några grundinställningar 
    för att komma igång. Följ stegen nedan för att konfigurera systemet.
    """)

    # Steg 1: Skapa grundläggande förvaltningsstruktur
    st.subheader("Steg 1: Skapa förvaltningsstruktur")
    with st.form("setup_forvaltningar"):
        st.markdown("Ange de förvaltningar som ska finnas i systemet (en per rad):")
        forvaltningar_text = st.text_area(
            "Förvaltningar",
            placeholder="Exempel:\nStadskontoret\nStadsbyggnadskontoret\nMiljöförvaltningen",
            height=150
        )
        
        if st.form_submit_button("Skapa förvaltningar"):
            if not forvaltningar_text.strip():
                st.error("Ange minst en förvaltning!")
            else:
                # Skapa förvaltningar
                forvaltningar = [f.strip() for f in forvaltningar_text.split('\n') if f.strip()]
                for forv_namn in forvaltningar:
                    result = db.forvaltningar.insert_one({
                        "namn": forv_namn,
                        "chef": "",
                        "beraknat_medlemsantal": 0
                    })
                    if result.inserted_id:
                        log_action("create", f"Skapade förvaltning: {forv_namn}", "setup")
                
                update_cache_after_change(db, 'forvaltningar', 'create')
                st.success("Förvaltningar skapade!")
                st.rerun()

    # Steg 2: Skapa globala arbetsplatser
    if db.forvaltningar.find_one():
        st.subheader("Steg 2: Skapa globala arbetsplatser")
        with st.form("setup_arbetsplatser"):
            st.markdown(
                "Ange de arbetsplatser som ska vara tillgängliga för alla förvaltningar (en per rad):"
            )
            arbetsplatser_text = st.text_area(
                "Globala arbetsplatser",
                placeholder="Exempel:\nHR-avdelningen\nEkonomiavdelningen\nIT-avdelningen",
                height=150
            )
            
            if st.form_submit_button("Skapa globala arbetsplatser"):
                if not arbetsplatser_text.strip():
                    st.error("Ange minst en global arbetsplats!")
                else:
                    # Skapa globala arbetsplatser
                    arbetsplatser = [a.strip() for a in arbetsplatser_text.split('\n') if a.strip()]
                    for arb_namn in arbetsplatser:
                        result = db.arbetsplatser.insert_one({
                            "namn": arb_namn,
                            "alla_forvaltningar": True,
                            "gatuadress": "",
                            "postnummer": "",
                            "ort": ""
                        })
                        if result.inserted_id:
                            log_action("create", f"Skapade global arbetsplats: {arb_namn}", "setup")
                    
                    update_cache_after_change(db, 'arbetsplatser', 'create')
                    st.success("Globala arbetsplatser skapade!")
                    st.rerun()

    # Steg 3: Skapa standardroller
    if db.arbetsplatser.find_one({"alla_forvaltningar": True}):
        st.subheader("Steg 3: Konfigurera standardroller")
        with st.form("setup_roles"):
            st.markdown("Bekräfta standardroller som ska finnas i systemet:")
            
            roles = {
                "visionombud": st.checkbox("Visionombud", value=True),
                "skyddsombud": st.checkbox("Skyddsombud", value=True),
                "huvudskyddsombud": st.checkbox("Huvudskyddsombud", value=True),
                "lsg_fsg": st.checkbox("LSG/FSG-representant", value=True),
                "csg": st.checkbox("CSG-representant", value=True)
            }
            
            if st.form_submit_button("Konfigurera roller"):
                # Spara rollkonfiguration
                config = {
                    "configured_roles": {k: v for k, v in roles.items() if v},
                    "setup_complete": True
                }
                db.config.insert_one(config)
                log_action("create", "Konfigurerade standardroller", "setup")
                
                st.success("Grundkonfiguration slutförd!")
                st.info("Du kan nu börja använda systemet. Använd administrationssidorna för att göra ytterligare ändringar.")
                st.rerun()

    # Visa instruktioner om nästa steg
    if not db.config.find_one({"setup_complete": True}):
        st.info(
            "När du är klar med grundkonfigurationen kan du börja lägga till "
            "avdelningar, enheter och personer i systemet via de vanliga administrationssidorna."
        )
