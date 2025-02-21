"""
Första-gångs-konfiguration för Vision Sektion 10

Denna modul hjälper användaren att komma igång med systemet:
- Guidar genom grundinställningar
- Skapar första förvaltningarna
- Lägger till regionala arbetsplatser
- Konfigurerar standardroller

Modulen innehåller:
- Steg-för-steg guide
- Formulär för grunddata
- Validering av inmatning
- Hjälptexter och förklaringar

Tekniska detaljer:
- Använder Streamlit för gränssnittet
- Sparar data i MongoDB
- Loggar alla konfigurationsändringar
- Säkerställer att allt är korrekt inställt
"""

import streamlit as st
from views.cache_manager import get_cached_data, update_cache_after_change
from views.custom_logging import log_action
from datetime import datetime


def show_first_time_setup(db):
    """
    Visar och hanterar första-gångs-konfigurationen.
    
    Guidar användaren genom:
    - Skapande av förvaltningar
    - Inställning av regionala arbetsplatser
    - Val av standardroller i systemet
    - Bekräftelse av konfigurationen
    """
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

    # Steg 2: Skapa regionala arbetsplatser
    if not st.session_state.get('step2_done'):
        st.subheader("Steg 2: Skapa regionala arbetsplatser")
        with st.form("step2"):
            st.write("""
            Ange regionala arbetsplatser som ska finnas tillgängliga för alla förvaltningar.
            Exempel: Regionhuset, Stadshuset, etc.
            """)
            arbetsplatser = st.text_area(
                "Regionala arbetsplatser",
                help="Ange en arbetsplats per rad"
            ).strip()
            
            if st.form_submit_button("Skapa regionala arbetsplatser"):
                if not arbetsplatser:
                    st.error("Ange minst en regional arbetsplats!")
                else:
                    # Skapa regionala arbetsplatser
                    for arb_namn in arbetsplatser.split('\n'):
                        arb_namn = arb_namn.strip()
                        if arb_namn:
                            db.arbetsplatser.insert_one({
                                'namn': arb_namn,
                                'alla_forvaltningar': True,
                                'created_at': datetime.now()
                            })
                            log_action("create", f"Skapade regional arbetsplats: {arb_namn}", "setup")
                    
                    st.session_state.step2_done = True
                    st.success("Regionala arbetsplatser skapade!")
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
