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
import datetime


def create_excel_file(db):
    """
    Skapar en komplett Excel-fil med organisationsdata från databasen.
    
    Funktionen:
    1. Skapar en Excel-fil i minnet med flera flikar
    2. Applicerar anpassad formatering för olika organisationsnivåer
    3. Genererar hierarkisk data för hela organisationen
    4. Skapar separata flikar för arbetsplatser och styrelser/nämnder
    
    Args:
        db: MongoDB-databasanslutning med tillgång till alla collections
    
    Returns:
        bytes: Excel-filens innehåll som bytes för nedladdning
    
    Tekniska detaljer:
    - Använder BytesIO för minneshantering
    - Implementerar anpassade format för varje organisationsnivå
    - Optimerar kolumnbredder baserat på innehåll
    - Hanterar relationer mellan olika collections
    """
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        workbook = writer.book
        
        # Formatering för olika organisationsnivåer
        # Vision-blå (#210061) för rubriker
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#210061',
            'font_color': 'white',
            'border': 1
        })
        
        # Vision-grön (#00A68A) för förvaltningar
        forvaltning_format = workbook.add_format({
            'bold': True,
            'bg_color': '#00A68A',
            'border': 6
        })
        
        # Vision-lila (#7930AE) för avdelningar
        avdelning_format = workbook.add_format({
            'bold': True,
            'bg_color': '#7930AE',
            'font_color': 'white',
            'border': 1
        })
        
        # Ljuslila (#bc98d7) för enheter
        enhet_format = workbook.add_format({
            'bold': True,
            'bg_color': '#bc98d7',
            'border': 1
        })
        
        # Mycket ljuslila (#f2eaf7) för personal
        person_format = workbook.add_format({
            'bg_color': '#f2eaf7',
            'border': 1
        })
        
        # Hämta all nödvändig data från databasen
        forvaltningar = list(db.forvaltningar.find())
        avdelningar = list(db.avdelningar.find())
        enheter = list(db.enheter.find())
        personer = list(db.personer.find())
        arbetsplatser = list(db.arbetsplatser.find())
        boards = list(db.boards.find())

        # Skapa hierarkisk datastruktur
        hierarkisk_data = []
        row_formats = []  # Lista för radspecifik formatering
        
        # Bygg hierarkin: Förvaltning -> Nämnd -> Avdelning -> Enhet -> Personal
        for forv in forvaltningar:
            # Lägg till förvaltningsnivå
            hierarkisk_data.append({
                'Nivå': 'Förvaltning',
                'Namn': forv['namn'],
                'Chef': forv['chef'],
                'Yrkestitel': '',
                'Sitter i CSG?': '',
                'Sitter i FSG/LSG?': '',
                'Skyddsombud?': '',
                'Huvudskyddsombud?': '',
                'Visionombud?': '',
                'Arbetsplats': '',
                'Telefonnr': '',
                'Ordinarie Representant': '',
                'Ersättare': ''
            })
            row_formats.append(forvaltning_format)
            
            # Identifiera och lägg till nämnder kopplade till förvaltningen
            forv_boards = [b for b in boards if any(
                person['forvaltning_id'] == forv['_id'] 
                for person in personer 
                if person['namn'] in b.get('ledamoter', []) + b.get('ersattare', [])
            )]
            
            for board in forv_boards:
                # Filtrera ledamöter och ersättare för aktuell förvaltning
                forv_ledamoter = [
                    person['namn'] for person in personer 
                    if person['forvaltning_id'] == forv['_id'] 
                    and person['namn'] in board.get('ledamoter', [])
                ]
                forv_ersattare = [
                    person['namn'] for person in personer 
                    if person['forvaltning_id'] == forv['_id'] 
                    and person['namn'] in board.get('ersattare', [])
                ]
                
                if forv_ledamoter or forv_ersattare:
                    hierarkisk_data.append({
                        'Nivå': 'Nämnd',
                        'Namn': board['namn'],
                        'Chef': '',
                        'Yrkestitel': '',
                        'Sitter i CSG?': '',
                        'Sitter i FSG/LSG?': '',
                        'Skyddsombud?': '',
                        'Huvudskyddsombud?': '',
                        'Visionombud?': '',
                        'Arbetsplats': '',
                        'Telefonnr': '',
                        'Ordinarie Representant': ', '.join(forv_ledamoter),
                        'Ersättare': ', '.join(forv_ersattare)
                    })
                    row_formats.append(workbook.add_format({
                        'bg_color': '#EFE9E5',  # Ljusgrå för nämnder
                        'border': 9
                    }))
            
            # Lägg till avdelningar under förvaltningen
            forv_avd = [a for a in avdelningar if a['forvaltning_id'] == forv['_id']]
            for avd in forv_avd:
                hierarkisk_data.append({
                    'Nivå': 'Avdelning',
                    'Namn': avd['namn'],
                    'Chef': avd['chef'],
                    'Yrkestitel': '',
                    'Sitter i CSG?': '',
                    'Sitter i FSG/LSG?': '',
                    'Skyddsombud?': '',
                    'Huvudskyddsombud?': '',
                    'Visionombud?': '',
                    'Arbetsplats': '',
                    'Telefonnr': '',
                    'Ordinarie Representant': '',
                    'Ersättare': ''
                })
                row_formats.append(avdelning_format)
                
                # Lägg till enheter under avdelningen
                avd_enh = [e for e in enheter if e['avdelning_id'] == avd['_id']]
                for enh in avd_enh:
                    hierarkisk_data.append({
                        'Nivå': 'Enhet',
                        'Namn': enh['namn'],
                        'Chef': enh['chef'],
                        'Yrkestitel': '',
                        'Sitter i CSG?': '',
                        'Sitter i FSG/LSG?': '',
                        'Skyddsombud?': '',
                        'Huvudskyddsombud?': '',
                        'Visionombud?': '',
                        'Arbetsplats': '',
                        'Telefonnr': '',
                        'Ordinarie Representant': '',
                        'Ersättare': ''
                    })
                    row_formats.append(enhet_format)
                    
                    # Lägg till personal under enheten
                    enh_personer = [p for p in personer if p['enhet_id'] == enh['_id']]
                    for person in enh_personer:
                        hierarkisk_data.append({
                            'Nivå': 'Personal',
                            'Namn': person['namn'],
                            'Chef': '',
                            'Yrkestitel': person.get('yrkestitel', ''),
                            'Sitter i CSG?': f"{person.get('csg_roll', '')}" if person.get('csg') else 'Nej',
                            'Sitter i FSG/LSG?': f"{person.get('lsg_fsg_roll', '')}" if person.get('lsg_fsg') else 'Nej',
                            'Skyddsombud?': 'Ja' if person.get('skyddsombud') else 'Nej',
                            'Huvudskyddsombud?': 'Ja' if person.get('huvudskyddsombud') else 'Nej',
                            'Visionombud?': 'Ja' if person.get('visionombud') else 'Nej',
                            'Arbetsplats': ', '.join(person.get('arbetsplats', [])),
                            'Telefonnr': person.get('telefon', ''),
                            'Ordinarie Representant': '',
                            'Ersättare': ''
                        })
                        row_formats.append(person_format)

        # Skapa och formatera organisationsfliken
        df_hierarki = pd.DataFrame(hierarkisk_data)
        df_hierarki.to_excel(writer, sheet_name='Organisation', index=False)
        worksheet = writer.sheets['Organisation']
        
        # Optimera kolumnbredder baserat på innehåll
        for idx, col in enumerate(df_hierarki.columns):
            max_length = max(len(col) + 2, df_hierarki[col].astype(str).str.len().max() + 2)
            worksheet.set_column(idx, idx, max_length)
        
        # Applicera rubrikformatering
        for col_num, value in enumerate(df_hierarki.columns.values):
            worksheet.write(0, col_num, value, header_format)
        
        # Applicera radspecifik formatering
        for row_num, format in enumerate(row_formats, start=1):
            for col_num in range(len(df_hierarki.columns)):
                cell_value = df_hierarki.iloc[row_num-1, col_num]
                if pd.isna(cell_value):
                    cell_value = ''
                else:
                    cell_value = str(cell_value)
                worksheet.write(row_num, col_num, cell_value, format)

        # Skapa och formatera arbetsplatsfliken
        arbetsplats_data = [{
            'Arbetsplats': ap['namn'],
            'Förvaltning': next((f['namn'] for f in forvaltningar 
                               if f['_id'] == ap.get('forvaltning_id')), 'Alla förvaltningar')
        } for ap in arbetsplatser]
        
        df_arbetsplatser = pd.DataFrame(arbetsplats_data)
        df_arbetsplatser = df_arbetsplatser.fillna('')
        df_arbetsplatser.to_excel(writer, sheet_name='Arbetsplatser', index=False)
        
        # Formatera arbetsplatsfliken
        worksheet = writer.sheets['Arbetsplatser']
        for idx, col in enumerate(df_arbetsplatser.columns):
            max_length = max(len(col) + 2, df_arbetsplatser[col].astype(str).str.len().max() + 2)
            worksheet.set_column(idx, idx, max_length)
        
        for col_num, value in enumerate(df_arbetsplatser.columns.values):
            worksheet.write(0, col_num, value, header_format)

        # Skapa och formatera styrelser/nämnder-fliken
        boards_data = [{
            'Styrelse/Nämnd': board['namn'],
            'Ordinarie': ', '.join(board.get('ledamoter', [])),
            'Ersättare': ', '.join(board.get('ersattare', []))
        } for board in boards]
        
        df_boards = pd.DataFrame(boards_data)
        df_boards.to_excel(writer, sheet_name='Styrelser & Nämnder', index=False)
        
        # Formatera styrelser/nämnder-fliken
        worksheet = writer.sheets['Styrelser & Nämnder']
        for idx, col in enumerate(df_boards.columns):
            max_length = max(len(col) + 2, df_boards[col].astype(str).str.len().max() + 2)
            worksheet.set_column(idx, idx, max_length)
            
        for col_num, value in enumerate(df_boards.columns.values):
            worksheet.write(0, col_num, value, header_format)

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
    1. **Organisation** - Hierarkisk vy av hela organisationen
    2. **Arbetsplatser** - Lista över alla arbetsplatser
    3. **Styrelser & Nämnder** - Översikt över alla styrelser och nämnder
    """)
    
    # Skapa nedladdningsknapp
    if st.button("📥 Generera Excel-fil"):
        excel_data = create_excel_file(db)
        current_date = datetime.datetime.now().strftime("%Y-%m-%d")
        filename = f"Vision_Export_{current_date}.xlsx"
        
        st.download_button(
            label="⬇️ Ladda ner Excel-fil",
            data=excel_data,
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        st.success("✅ Excel-fil genererad! Klicka på knappen ovan för att ladda ner.")
