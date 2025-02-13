"""
Översiktsmodul för Vision Sektion 10.

Detta system ger en omfattande översikt över organisationens struktur och representation:
1. Huvudskyddsombud - Visar alla huvudskyddsombud i organisationen
2. Förvaltningsvis översikt:
   - Uppdragstäckning per avdelning och enhet
   - Representation i styrelser och nämnder
   - Status för fackliga roller och uppdrag

Modulen tillhandahåller funktionalitet för att:
- Visa hierarkisk organisationsstruktur
- Spåra representation på alla nivåer
- Visualisera täckningsgrad för olika uppdrag
- Presentera styrelser och nämnder med representanter

Tekniska detaljer:
- Använder MongoDB för dataåtkomst
- Implementerar dynamisk filtrering och gruppering
- Hanterar komplex datavisualisering via Streamlit
- Tillhandahåller interaktiv användarupplevelse
"""

import streamlit as st
import pandas as pd
from views.cache_manager import get_cached_data, update_cache_after_change


def show(db):
    """Visar översikt över organisationen."""
    # Ladda cachad data
    cached, indexes = get_cached_data(db)
    
    st.header("Översikt")

    # Skapa flikar för olika vyer
    tab1, tab2 = st.tabs(["Organisationsstruktur", "Sökfunktion"])

    with tab1:
        st.subheader("Organisationsstruktur")
        
        # Visa förvaltningar och deras struktur
        for forv in cached['forvaltningar']:
            with st.expander(f"📁 {forv['namn']} - Chef: {forv.get('chef', 'Ej angiven')}"):
                # Visa antal personer direkt under förvaltningen
                forv_personer = [p for p in cached['personer'] if p.get('forvaltning_id') == forv['_id']]
                if forv_personer:
                    st.markdown(f"**Personer direkt under förvaltningen:** {len(forv_personer)}")
                
                # Visa avdelningar under förvaltningen
                avdelningar = indexes['avdelningar_by_forv'].get(forv['_id'], [])
                for avd in avdelningar:
                    with st.expander(f"📂 {avd['namn']} - Chef: {avd.get('chef', 'Ej angiven')}"):
                        # Visa antal personer direkt under avdelningen
                        avd_personer = [p for p in cached['personer'] if p.get('avdelning_id') == avd['_id']]
                        if avd_personer:
                            st.markdown(f"**Personer direkt under avdelningen:** {len(avd_personer)}")
                        
                        # Visa enheter under avdelningen
                        enheter = indexes['enheter_by_avd'].get(avd['_id'], [])
                        for enhet in enheter:
                            with st.expander(f"📑 {enhet['namn']} - Chef: {enhet.get('chef', 'Ej angiven')}"):
                                # Visa personer i enheten
                                enhet_personer = [p for p in cached['personer'] if p.get('enhet_id') == enhet['_id']]
                                if enhet_personer:
                                    st.markdown(f"**Antal personer i enheten:** {len(enhet_personer)}")
                                    
                                    # Visa arbetsplatser kopplade till enheten
                                    arbetsplatser = [a for a in cached['arbetsplatser'] 
                                                   if a.get('enhet_id') == enhet['_id']]
                                    if arbetsplatser:
                                        st.markdown("**Arbetsplatser:**")
                                        for arbetsplats in arbetsplatser:
                                            st.markdown(f"- 🏢 {arbetsplats['namn']}")

    with tab2:
        st.subheader("Sök i organisationen")
        
        # Sökfält
        search_query = st.text_input("🔍 Sök efter person, arbetsplats eller enhet", "").lower()
        
        if search_query:
            # Sök i personer
            matching_personer = [p for p in cached['personer'] 
                               if search_query in p.get('namn', '').lower()]
            
            # Sök i arbetsplatser
            matching_arbetsplatser = [a for a in cached['arbetsplatser'] 
                                    if search_query in a.get('namn', '').lower()]
            
            # Sök i enheter
            matching_enheter = [e for e in cached['enheter'] 
                              if search_query in e.get('namn', '').lower()]
            
            # Visa sökresultat
            if matching_personer:
                st.markdown("### Personer")
                df_personer = pd.DataFrame([{
                    'Namn': p['namn'],
                    'Förvaltning': p.get('forvaltning_namn', ''),
                    'Avdelning': p.get('avdelning_namn', ''),
                    'Enhet': p.get('enhet_namn', ''),
                    'Arbetsplats': p.get('arbetsplats', '')
                } for p in matching_personer])
                st.dataframe(df_personer, hide_index=True)
            
            if matching_arbetsplatser:
                st.markdown("### Arbetsplatser")
                df_arbetsplatser = pd.DataFrame([{
                    'Namn': a['namn'],
                    'Förvaltning': a.get('forvaltning_namn', ''),
                    'Adress': f"{a.get('gatuadress', '')}, {a.get('postnummer', '')} {a.get('ort', '')}"
                } for a in matching_arbetsplatser])
                st.dataframe(df_arbetsplatser, hide_index=True)

            if matching_enheter:
                st.markdown("### Enheter")
                df_enheter = pd.DataFrame([{
                    'Namn': e['namn'],
                    'Förvaltning': e.get('forvaltning_namn', ''),
                    'Avdelning': e.get('avdelning_namn', ''),
                    'Chef': e.get('chef', '')
                } for e in matching_enheter])
                st.dataframe(df_enheter, hide_index=True)
            
            if not (matching_personer or matching_arbetsplatser or matching_enheter):
                st.info("Inga träffar hittades för din sökning.")
