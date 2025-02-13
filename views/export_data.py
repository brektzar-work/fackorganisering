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


def create_overview_sheet(writer, cached_data):
    """Creates an overview sheet with hierarchical organization structure and color coding"""
    # Create workbook and add sheet
    workbook = writer.book
    sheet = workbook.create_sheet("Översikt")
    
    # Define styles
    styles = {
        'forvaltning': {
            'fill': openpyxl.styles.PatternFill(start_color='00A68A', end_color='00A68A', fill_type='solid'),
            'font': openpyxl.styles.Font(color='FFFFFF', bold=True)
        },
        'avdelning': {
            'fill': openpyxl.styles.PatternFill(start_color='4D3381', end_color='4D3381', fill_type='solid'),
            'font': openpyxl.styles.Font(color='FFFFFF', bold=True)
        },
        'enhet': {
            'fill': openpyxl.styles.PatternFill(start_color='210061', end_color='210061', fill_type='solid'),
            'font': openpyxl.styles.Font(color='FFFFFF', bold=True)
        },
        'arbetsplats': {
            'fill': openpyxl.styles.PatternFill(start_color='9080B0', end_color='9080B0', fill_type='solid'),
            'font': openpyxl.styles.Font(color='FFFFFF')
        },
        'visionombud': {
            'fill': openpyxl.styles.PatternFill(start_color='BCB3D0', end_color='BCB3D0', fill_type='solid'),
            'font': openpyxl.styles.Font(color='000000')
        },
        'skyddsombud': {
            'fill': openpyxl.styles.PatternFill(start_color='D3CCDF', end_color='D3CCDF', fill_type='solid'),
            'font': openpyxl.styles.Font(color='000000')
        }
    }
    
    # Add headers
    headers = ['Förvaltning', 'Avdelning', 'Enhet', 'Arbetsplats', 'Ombud']
    for col, header in enumerate(headers, 1):
        cell = sheet.cell(row=1, column=col, value=header)
        cell.font = openpyxl.styles.Font(bold=True)
    
    # Start writing data
    row = 2
    
    # Sort förvaltningar by name
    forvaltningar = sorted(cached_data['forvaltningar'], key=lambda x: x['namn'])
    
    for forv in forvaltningar:
        # Write förvaltning
        for col in range(1, 6):
            cell = sheet.cell(row=row, column=col)
            cell.fill = styles['forvaltning']['fill']
            cell.font = styles['forvaltning']['font']
            if col == 1:
                cell.value = forv['namn']
        row += 1
        
        # Get and sort avdelningar for this förvaltning
        avdelningar = sorted(
            [a for a in cached_data['avdelningar'] if str(a['forvaltning_id']) == str(forv['_id'])], 
            key=lambda x: x['namn']
        )
        
        for avd in avdelningar:
            # Write avdelning
            for col in range(1, 6):
                cell = sheet.cell(row=row, column=col)
                cell.fill = styles['avdelning']['fill']
                cell.font = styles['avdelning']['font']
                if col == 2:
                    cell.value = avd['namn']
            row += 1
            
            # Get and sort enheter for this avdelning
            enheter = sorted(
                [e for e in cached_data['enheter'] if str(e['avdelning_id']) == str(avd['_id'])], 
                key=lambda x: x['namn']
            )
            
            for enhet in enheter:
                # Write enhet
                for col in range(1, 6):
                    cell = sheet.cell(row=row, column=col)
                    cell.fill = styles['enhet']['fill']
                    cell.font = styles['enhet']['font']
                    if col == 3:
                        cell.value = enhet['namn']
                row += 1
                
                # Get arbetsplatser from the enhet's arbetsplatser array
                arbetsplatser = []
                if enhet.get('arbetsplatser'):
                    arbetsplatser = sorted(
                        [a for a in cached_data['arbetsplatser'] 
                         if str(a['_id']) in enhet['arbetsplatser']], 
                        key=lambda x: x['namn']
                    )
                
                # If no arbetsplatser, show placeholder
                if not arbetsplatser:
                    arbetsplatser = [{'namn': 'Ingen arbetsplats'}]
                
                for arbetsplats in arbetsplatser:
                    # Write arbetsplats
                    for col in range(1, 6):
                        cell = sheet.cell(row=row, column=col)
                        cell.fill = styles['arbetsplats']['fill']
                        cell.font = styles['arbetsplats']['font']
                        if col == 4:
                            cell.value = arbetsplats['namn']
                    row += 1
                    
                    # Get and sort personer for this arbetsplats
                    personer = []
                    if arbetsplats['namn'] != 'Ingen arbetsplats':
                        personer = sorted(
                            [p for p in cached_data['personer'] 
                             if arbetsplats['namn'] in p.get('arbetsplats', [])],
                            key=lambda x: x['namn']
                        )
                    
                    # Write Visionombud
                    visionombud = [p for p in personer if p.get('visionombud')]
                    for person in visionombud:
                        for col in range(1, 6):
                            cell = sheet.cell(row=row, column=col)
                            cell.fill = styles['visionombud']['fill']
                            cell.font = styles['visionombud']['font']
                            if col == 5:
                                cell.value = f"Visionombud: {person['namn']}"
                        row += 1
                    
                    # Write Skyddsombud
                    skyddsombud = [p for p in personer if p.get('skyddsombud')]
                    for person in skyddsombud:
                        for col in range(1, 6):
                            cell = sheet.cell(row=row, column=col)
                            cell.fill = styles['skyddsombud']['fill']
                            cell.font = styles['skyddsombud']['font']
                            if col == 5:
                                cell.value = f"Skyddsombud: {person['namn']}"
                        row += 1
    
    # Adjust column widths
    for col in range(1, 6):
        max_length = 0
        for cell in sheet[openpyxl.utils.get_column_letter(col)]:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        sheet.column_dimensions[openpyxl.utils.get_column_letter(col)].width = max_length + 2


def get_fresh_data(db):
    """Get fresh data directly from the database for export"""
    return {
        'forvaltningar': list(db.forvaltningar.find()),
        'avdelningar': list(db.avdelningar.find()),
        'enheter': list(db.enheter.find()),
        'arbetsplatser': list(db.arbetsplatser.find()),
        'personer': list(db.personer.find()),
        'boards': list(db.boards.find())
    }

def create_excel_file(db):
    """
    Skapar en Excel-fil med all data.
    
    Funktionen:
    1. Hämtar färsk data direkt från databasen
    2. Skapar en Excel-fil i minnet med alla flikar
    3. Applicerar anpassad formatering för olika organisationsnivåer
    4. Genererar hierarkisk data för hela organisationen
    
    Args:
        db: MongoDB-databasanslutning
    
    Returns:
        bytes: Excel-filens innehåll som bytes för nedladdning
    """
    # Get fresh data directly from DB
    data = get_fresh_data(db)
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Create overview sheet first
        create_overview_sheet(writer, data)
        
        # Personer
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
        } for p in data['personer']])
        df_personer.to_excel(writer, sheet_name='Personer', index=False)

        # Arbetsplatser
        df_arbetsplatser = pd.DataFrame([{
            'Namn': a['namn'],
            'Förvaltning': a.get('forvaltning_namn', ''),
            'Avdelning': a.get('avdelning_namn', ''),
            'Enhet': a.get('enhet_namn', ''),
            'Gatuadress': a.get('gatuadress', ''),
            'Postnummer': a.get('postnummer', ''),
            'Ort': a.get('ort', ''),
            'Global': 'Ja' if a.get('alla_forvaltningar') else 'Nej'
        } for a in data['arbetsplatser']])
        df_arbetsplatser.to_excel(writer, sheet_name='Arbetsplatser', index=False)

        # Förvaltningar
        df_forvaltningar = pd.DataFrame([{
            'Namn': f['namn'],
            'Chef': f.get('chef', ''),
            'Antal Avdelningar': len([a for a in data['avdelningar'] 
                                    if str(a.get('forvaltning_id')) == str(f['_id'])]),
            'Antal Enheter': len([e for e in data['enheter'] 
                                if str(e.get('forvaltning_id')) == str(f['_id'])]),
            'Antal Personer': len([p for p in data['personer'] 
                                 if str(p.get('forvaltning_id')) == str(f['_id'])])
        } for f in data['forvaltningar']])
        df_forvaltningar.to_excel(writer, sheet_name='Förvaltningar', index=False)

        # Avdelningar
        df_avdelningar = pd.DataFrame([{
            'Namn': a['namn'],
            'Förvaltning': a.get('forvaltning_namn', ''),
            'Chef': a.get('chef', ''),
            'Antal Enheter': len([e for e in data['enheter'] 
                                if str(e.get('avdelning_id')) == str(a['_id'])]),
            'Antal Personer': len([p for p in data['personer'] 
                                 if str(p.get('avdelning_id')) == str(a['_id'])])
        } for a in data['avdelningar']])
        df_avdelningar.to_excel(writer, sheet_name='Avdelningar', index=False)

        # Enheter
        df_enheter = pd.DataFrame([{
            'Namn': e['namn'],
            'Förvaltning': e.get('forvaltning_namn', ''),
            'Avdelning': e.get('avdelning_namn', ''),
            'Chef': e.get('chef', ''),
            'Arbetsplatser': ', '.join([
                next((ap['namn'] for ap in data['arbetsplatser'] if str(ap['_id']) == str(ap_id)), '')
                for ap_id in e.get('arbetsplatser', [])
            ])
        } for e in data['enheter']])
        df_enheter.to_excel(writer, sheet_name='Enheter', index=False)

        # Styrelser och Nämnder
        df_boards = pd.DataFrame([{
            'Namn': b['namn'],
            'Typ': b.get('typ', ''),
            'Förvaltning': b.get('forvaltning_namn', ''),
            'Ordinarie Ledamöter': ', '.join(b.get('ledamoter', [])),
            'Ersättare': ', '.join(b.get('ersattare', []))
        } for b in data.get('boards', [])])
        df_boards.to_excel(writer, sheet_name='Styrelser & Nämnder', index=False)

    return output.getvalue()


def show(db):
    """Visar exportgränssnittet i Streamlit och hanterar nedladdning av Excel-filen."""
    st.header("Exportera Data")

    st.markdown("""
    Här kan du exportera all data till en Excel-fil. Filen innehåller:
    - Komplett organisationsstruktur med alla personer och deras roller
    - Lista över alla arbetsplatser och deras förvaltningar
    - Översikt över styrelser och nämnder med ledamöter
    
    Filen kommer att innehålla följande flikar:
    1. **Översikt** - Hierarkisk översikt över hela organisationen
    2. **Personer** - Lista över alla personer och deras roller
    3. **Arbetsplatser** - Lista över alla arbetsplatser
    4. **Förvaltningar** - Översikt över alla förvaltningar
    5. **Avdelningar** - Lista över alla avdelningar
    6. **Enheter** - Lista över alla enheter och deras arbetsplatser
    7. **Styrelser & Nämnder** - Översikt över alla styrelser och nämnder
    """)

    # Ladda ner fil
    excel_data = create_excel_file(db)
    st.download_button(
        label="📥 Ladda ner Excel-fil",
        data=excel_data,
        file_name="vision_sektion10_export.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
