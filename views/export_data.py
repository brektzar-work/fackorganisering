import streamlit as st
import pandas as pd
from io import BytesIO
import datetime

def create_excel_file(db):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        workbook = writer.book
        
        # Formatering för olika nivåer
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#210061',
            'font_color': 'white',
            'border': 1
        })
        
        forvaltning_format = workbook.add_format({
            'bg_color': '#cce5ff',  # Basfärg för förvaltning
            'border': 1
        })
        
        avdelning_format = workbook.add_format({
            'bg_color': '#e6f2ff',  # Ljusare för avdelning
            'border': 1
        })
        
        enhet_format = workbook.add_format({
            'bg_color': '#f2f8ff',  # Ännu ljusare för enhet
            'border': 1
        })
        
        person_format = workbook.add_format({
            'bg_color': '#ffffff',  # Vit för personer
            'border': 1
        })
        
        # Hämta all data
        forvaltningar = list(db.forvaltningar.find())
        avdelningar = list(db.avdelningar.find())
        enheter = list(db.enheter.find())
        personer = list(db.personer.find())
        arbetsplatser = list(db.arbetsplatser.find())
        boards = list(db.boards.find())

        # Skapa hierarkisk översikt
        hierarkisk_data = []
        row_formats = []  # Lista för att hålla reda på formateringen för varje rad
        
        # Lägg till förvaltningar och deras nämnder
        for forv in forvaltningar:
            # Lägg till förvaltning
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
            
            # Lägg till nämnder för denna förvaltning
            forv_boards = [b for b in boards if any(
                person['forvaltning_id'] == forv['_id'] 
                for person in personer 
                if person['namn'] in b.get('ledamoter', []) + b.get('ersattare', [])
            )]
            
            for board in forv_boards:
                # Filtrera ledamöter och ersättare för denna förvaltning
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
                        'bg_color': '#d9ebff',  # Ljusblå för nämnder
                        'border': 1
                    }))
            
            # Lägg till avdelningar
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
                
                # Lägg till enheter
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
                    
                    # Lägg till personer
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

        # Skapa DataFrame och skriv till Excel
        df_hierarki = pd.DataFrame(hierarkisk_data)
        df_hierarki.to_excel(writer, sheet_name='Organisation', index=False)
        
        # Formatera Organisation-fliken
        worksheet = writer.sheets['Organisation']
        
        # Sätt kolumnbredder
        for idx, col in enumerate(df_hierarki.columns):
            worksheet.set_column(idx, idx, max(len(col) + 2, df_hierarki[col].astype(str).str.len().max() + 2))
        
        # Lägg till headers med formatering
        for col_num, value in enumerate(df_hierarki.columns.values):
            worksheet.write(0, col_num, value, header_format)
        
        # Applicera rad-formatering
        for row_num, format in enumerate(row_formats, start=1):
            for col_num in range(len(df_hierarki.columns)):
                cell_value = df_hierarki.iloc[row_num-1, col_num]
                # Konvertera värdet till sträng och hantera NaN/None
                if pd.isna(cell_value):
                    cell_value = ''
                else:
                    cell_value = str(cell_value)
                worksheet.write(row_num, col_num, cell_value, format)

        # Skapa flik för arbetsplatser
        arbetsplats_data = [{
            'Arbetsplats': ap['namn'],
            'Förvaltning': next((f['namn'] for f in forvaltningar 
                               if f['_id'] == ap.get('forvaltning_id')), 'Alla förvaltningar')
        } for ap in arbetsplatser]
        
        df_arbetsplatser = pd.DataFrame(arbetsplats_data)
        df_arbetsplatser = df_arbetsplatser.fillna('')  # Ersätt NaN med tomma strängar
        df_arbetsplatser.to_excel(writer, sheet_name='Arbetsplatser', index=False)
        
        # Formatera Arbetsplatser-fliken
        worksheet = writer.sheets['Arbetsplatser']
        for idx, col in enumerate(df_arbetsplatser.columns):
            worksheet.set_column(idx, idx, max(len(col) + 2, df_arbetsplatser[col].astype(str).str.len().max() + 2))
        
        # Lägg till headers med formatering
        for col_num, value in enumerate(df_arbetsplatser.columns.values):
            worksheet.write(0, col_num, value, header_format)

        # Skapa flik för styrelser/nämnder
        boards_data = []
        for board in boards:
            boards_data.append({
                'Styrelse/Nämnd': board['namn'],
                'Ordinarie': ', '.join(board.get('ledamoter', [])),
                'Ersättare': ', '.join(board.get('ersattare', []))
            })
        
        df_boards = pd.DataFrame(boards_data)
        df_boards.to_excel(writer, sheet_name='Styrelser & Nämnder', index=False)
        
        # Formatera Styrelser & Nämnder-fliken
        worksheet = writer.sheets['Styrelser & Nämnder']
        for idx, col in enumerate(df_boards.columns):
            worksheet.set_column(idx, idx, max(len(col) + 2, df_boards[col].astype(str).str.len().max() + 2))
            
        # Lägg till headers med formatering
        for col_num, value in enumerate(df_boards.columns.values):
            worksheet.write(0, col_num, value, header_format)

    return output.getvalue()

def show(db):
    st.header("Exportera Data")
    
    st.markdown("""
    Här kan du exportera all data till en Excel-fil. Filen innehåller:
    - Komplett organisationsstruktur med alla personer och deras roller
    - Översikt över styrelser och nämnder med representanter
    
    Organisationsfliken visar:
    - Hierarkisk struktur (Förvaltning → Avdelning → Enhet → Personal)
    - Alla roller och uppdrag för varje person
    - Kontaktinformation och arbetsplatser
    """)
    
    if st.button("📥 Ladda ner Excel-fil"):
        excel_data = create_excel_file(db)
        
        current_date = datetime.datetime.now().strftime("%Y-%m-%d")
        filename = f"Vision_Organisation_{current_date}.xlsx"
        
        st.download_button(
            label="📎 Klicka här för att ladda ner",
            data=excel_data,
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        st.success("Excel-filen är klar för nedladdning!") 