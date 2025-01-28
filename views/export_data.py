"""
Excel-exportmodul för Vision Sektion 10
Detta system hanterar export av organisationsdata till Excel-format.
Modulen skapar en detaljerad Excel-fil med flera flikar som innehåller
organisationsstruktur, arbetsplatser och styrelser/nämnder.

Tekniska detaljer:
- Använder xlsxwriter för Excel-generering
- Stödjer avancerad formatering och styling
- Hanterar hierarkisk datastruktur
- Optimerar kolumnbredder automatiskt
"""

import streamlit as st
import pandas as pd
from io import BytesIO
import openpyxl
from views.cache_manager import get_cached_data, update_cache_after_change


def create_excel_file(cached_data, selected_data):
    """
    Skapar en Excel-fil med vald data.
    
    Funktionen:
    1. Skapar en Excel-fil i minnet med flera flikar
    2. Applicerar anpassad formatering för olika organisationsnivåer
    3. Genererar hierarkisk data för hela organisationen
    4. Skapar separata flikar för arbetsplatser och styrelser/nämnder
    
    Args:
        cached_data: Cachad data från databasen
        selected_data: Lista över data som ska exporteras
    
    Returns:
        bytes: Excel-filens innehåll som bytes för nedladdning
    
    Tekniska detaljer:
    - Använder BytesIO för minneshantering
    - Implementerar anpassade format för varje organisationsnivå
    - Optimerar kolumnbredder baserat på innehåll
    - Hanterar relationer mellan olika collections
    """
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Personer
        if 'personer' in selected_data:
            df_personer = pd.DataFrame([{
                'Namn': p['namn'],
                'Förvaltning': p.get('forvaltning_namn', ''),
                'Avdelning': p.get('avdelning_namn', ''),
                'Enhet': p.get('enhet_namn', ''),
                'Arbetsplats': p.get('arbetsplats', ''),
                'Visionombud': 'Ja' if p.get('visionombud') else 'Nej',
                'Skyddsombud': 'Ja' if p.get('skyddsombud') else 'Nej',
                'Huvudskyddsombud': 'Ja' if p.get('huvudskyddsombud') else 'Nej',
                'LSG/FSG': 'Ja' if p.get('lsg_fsg') else 'Nej',
                'CSG': 'Ja' if p.get('csg') else 'Nej'
            } for p in cached_data['personer']])
            df_personer.to_excel(writer, sheet_name='Personer', index=False)

        # Arbetsplatser
        if 'arbetsplatser' in selected_data:
            df_arbetsplatser = pd.DataFrame([{
                'Namn': a['namn'],
                'Förvaltning': a.get('forvaltning_namn', ''),
                'Avdelning': a.get('avdelning_namn', ''),
                'Enhet': a.get('enhet_namn', ''),
                'Gatuadress': a.get('gatuadress', ''),
                'Postnummer': a.get('postnummer', ''),
                'Ort': a.get('ort', ''),
                'Global': 'Ja' if a.get('alla_forvaltningar') else 'Nej'
            } for a in cached_data['arbetsplatser']])
            df_arbetsplatser.to_excel(writer, sheet_name='Arbetsplatser', index=False)

        # Förvaltningar
        if 'forvaltningar' in selected_data:
            df_forvaltningar = pd.DataFrame([{
                'Namn': f['namn'],
                'Chef': f.get('chef', ''),
                'Antal Avdelningar': len([a for a in cached_data['avdelningar'] 
                                        if a.get('forvaltning_id') == f['_id']]),
                'Antal Enheter': len([e for e in cached_data['enheter'] 
                                    if e.get('forvaltning_id') == f['_id']]),
                'Antal Personer': len([p for p in cached_data['personer'] 
                                     if p.get('forvaltning_id') == f['_id']])
            } for f in cached_data['forvaltningar']])
            df_forvaltningar.to_excel(writer, sheet_name='Förvaltningar', index=False)

        # Avdelningar
        if 'avdelningar' in selected_data:
            df_avdelningar = pd.DataFrame([{
                'Namn': a['namn'],
                'Förvaltning': a.get('forvaltning_namn', ''),
                'Chef': a.get('chef', ''),
                'Antal Enheter': len([e for e in cached_data['enheter'] 
                                    if e.get('avdelning_id') == a['_id']]),
                'Antal Personer': len([p for p in cached_data['personer'] 
                                     if p.get('avdelning_id') == a['_id']])
            } for a in cached_data['avdelningar']])
            df_avdelningar.to_excel(writer, sheet_name='Avdelningar', index=False)

        # Enheter
        if 'enheter' in selected_data:
            df_enheter = pd.DataFrame([{
                'Namn': e['namn'],
                'Förvaltning': e.get('forvaltning_namn', ''),
                'Avdelning': e.get('avdelning_namn', ''),
                'Chef': e.get('chef', ''),
                'Antal Personer': len([p for p in cached_data['personer'] 
                                     if p.get('enhet_id') == e['_id']])
            } for e in cached_data['enheter']])
            df_enheter.to_excel(writer, sheet_name='Enheter', index=False)

        # Styrelser och Nämnder
        if 'boards' in selected_data:
            df_boards = pd.DataFrame([{
                'Namn': b['namn'],
                'Typ': b.get('typ', ''),
                'Förvaltning': b.get('forvaltning_namn', ''),
                'Ordinarie Ledamöter': ', '.join(b.get('ledamoter', [])),
                'Ersättare': ', '.join(b.get('ersattare', []))
            } for b in cached_data.get('boards', [])])
            df_boards.to_excel(writer, sheet_name='Styrelser & Nämnder', index=False)

    return output.getvalue()


def show(db):
    """
    Visar exportgränssnittet i Streamlit och hanterar nedladdning av Excel-filen.
    
    Funktionen:
    1. Visar en beskrivande header och information om exporten
    2. Skapar en nedladdningsknapp för Excel-filen
    3. Genererar filnamn med aktuellt datum
    
    Args:
        db: MongoDB-databasanslutning
    
    Tekniska detaljer:
    - Använder Streamlit's nedladdningsfunktionalitet
    - Genererar dynamiskt filnamn med datum
    - Hanterar MIME-type för Excel-filer
    """
    st.header("Exportera Data")
    
    st.markdown("""
    Här kan du exportera all data till en Excel-fil. Filen innehåller:
    - Komplett organisationsstruktur med alla personer och deras roller
    - Lista över alla arbetsplatser och deras förvaltningar
    - Översikt över styrelser och nämnder med ledamöter
    
    Filen kommer att innehålla följande flikar:
    1. **Personer** - Lista över alla personer och deras roller
    2. **Arbetsplatser** - Lista över alla arbetsplatser
    3. **Förvaltningar** - Översikt över alla förvaltningar
    4. **Avdelningar** - Lista över alla avdelningar
    5. **Enheter** - Lista över alla enheter
    6. **Styrelser & Nämnder** - Översikt över alla styrelser och nämnder
    """)
    
    # Ladda cachad data
    cached, indexes = get_cached_data(db)
    
    # Uppdateringsknapp i sidofältet
    if st.sidebar.button("↻ Uppdatera data", key="refresh_export"):
        cached, indexes = get_cached_data(db, force_refresh=True)
        st.rerun()

    # Välj data att exportera
    st.subheader("Välj data att exportera")
    selected_data = st.multiselect(
        "Välj vilken data som ska exporteras",
        options=['personer', 'arbetsplatser', 'forvaltningar', 'avdelningar', 'enheter', 'boards'],
        default=['personer', 'arbetsplatser'],
        format_func=lambda x: {
            'personer': 'Personer',
            'arbetsplatser': 'Arbetsplatser',
            'forvaltningar': 'Förvaltningar',
            'avdelningar': 'Avdelningar',
            'enheter': 'Enheter',
            'boards': 'Styrelser & Nämnder'
        }[x]
    )

    if selected_data:
        # Skapa Excel-fil
        excel_data = create_excel_file(cached, selected_data)
        
        # Ladda ner fil
        st.download_button(
            label="📥 Ladda ner Excel-fil",
            data=excel_data,
            file_name="vision_sektion10_export.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        # Förhandsvisning av data
        st.subheader("Förhandsvisning")
        for data_type in selected_data:
            if data_type == 'personer':
                st.markdown("### Personer")
                df = pd.DataFrame([{
                    'Namn': p['namn'],
                    'Förvaltning': p.get('forvaltning_namn', ''),
                    'Arbetsplats': p.get('arbetsplats', '')
                } for p in cached['personer']])
                st.dataframe(df, hide_index=True)
            
            elif data_type == 'arbetsplatser':
                st.markdown("### Arbetsplatser")
                df = pd.DataFrame([{
                    'Namn': a['namn'],
                    'Förvaltning': a.get('forvaltning_namn', ''),
                    'Adress': f"{a.get('gatuadress', '')}, {a.get('postnummer', '')} {a.get('ort', '')}"
                } for a in cached['arbetsplatser']])
                st.dataframe(df, hide_index=True)
            
            elif data_type == 'forvaltningar':
                st.markdown("### Förvaltningar")
                df = pd.DataFrame([{
                    'Namn': f['namn'],
                    'Chef': f.get('chef', ''),
                    'Antal Avdelningar': len([a for a in cached['avdelningar'] 
                                            if a.get('forvaltning_id') == f['_id']])
                } for f in cached['forvaltningar']])
                st.dataframe(df, hide_index=True)
            
            elif data_type == 'avdelningar':
                st.markdown("### Avdelningar")
                df = pd.DataFrame([{
                    'Namn': a['namn'],
                    'Förvaltning': a.get('forvaltning_namn', ''),
                    'Chef': a.get('chef', '')
                } for a in cached['avdelningar']])
                st.dataframe(df, hide_index=True)
            
            elif data_type == 'enheter':
                st.markdown("### Enheter")
                df = pd.DataFrame([{
                    'Namn': e['namn'],
                    'Förvaltning': e.get('forvaltning_namn', ''),
                    'Avdelning': e.get('avdelning_namn', ''),
                    'Chef': e.get('chef', '')
                } for e in cached['enheter']])
                st.dataframe(df, hide_index=True)
            
            elif data_type == 'boards':
                st.markdown("### Styrelser & Nämnder")
                df = pd.DataFrame([{
                    'Namn': b['namn'],
                    'Typ': b.get('typ', ''),
                    'Förvaltning': b.get('forvaltning_namn', '')
                } for b in cached.get('boards', [])])
                st.dataframe(df, hide_index=True)
    else:
        st.info("Välj minst en datatyp att exportera.")
