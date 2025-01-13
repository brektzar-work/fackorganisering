import streamlit as st
import pandas as pd
import plotly.express as px
import folium
from streamlit_folium import folium_static
import json
import colorsys


# Flytta generate_distinct_colors till modulnivå
def generate_distinct_colors(n):
    colors = []
    for i in range(n):
        hue = i / n
        # Använd ljusa, transparenta färger
        rgb = colorsys.hsv_to_rgb(hue, 0.3, 0.9)
        hex_color = '#{:02x}{:02x}{:02x}'.format(
            int(rgb[0] * 255),
            int(rgb[1] * 255),
            int(rgb[2] * 255)
        )
        colors.append(hex_color)
    return colors


# StyleFunction-klassen är redan på modulnivå
class StyleFunction:
    def __init__(self, color):
        self.color = color

    def __call__(self, feature):
        return {
            'fillColor': self.color,
            'fillOpacity': 0.3,
            'color': 'gray',
            'weight': 1,
            'dashArray': '5, 5'
        }

    def __getstate__(self):
        return {'color': self.color}

    def __setstate__(self, state):
        self.color = state['color']


@st.cache_data(ttl=3600)  # Cache i 1 timme
def load_map(_arbetsplatser, _personer, _db):
    # Skapa en karta centrerad över Västra Götaland med begränsningar
    m = folium.Map(
        location=[58.2, 13.0],  # Centrerad över VGR
        zoom_start=8,
        min_zoom=7,  # Förhindra för mycket utzoomning
        max_zoom=13,  # Begränsa max inzoomning
        max_bounds=True,  # Aktivera gränser
        min_lat=57.15,  # Södra gränsen för VGR
        max_lat=59.0,  # Norra gränsen för VGR
        min_lon=11.0,  # Västra gränsen för VGR
        max_lon=14.5,  # Östra gränsen för VGR
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    )

    # Sätt gränser för panorering
    m.fit_bounds([[57.15, 11.0], [59.0, 14.5]])

    # Lägg till kommungränser som ett eget lager med clipping
    kommun_layer = folium.FeatureGroup(name="🏛️ Kommuner")

    # Lista över kommuner i Västra Götaland (med alla vanliga namnvarianter)
    vg_kommuner_namn = [
        # Standard med 's'
        'Ale kommun', 'Alingsås kommun', 'Bengtsfors kommun', 'Bollebygds kommun', 'Borås kommun',
        'Dals-Eds kommun', 'Essunga kommun', 'Falköpings kommun', 'Färgelanda kommun', 'Grästorps kommun',
        'Gullspångs kommun', 'Göteborgs kommun', 'Götene kommun', 'Herrljunga kommun', 'Hjo kommun',
        'Härryda kommun', 'Karlsborgs kommun', 'Kungälvs kommun', 'Lerums kommun', 'Lidköpings kommun',
        'Lilla Edets kommun', 'Lysekils kommun', 'Mariestads kommun', 'Marks kommun', 'Melleruds kommun',
        'Munkedals kommun', 'Mölndals kommun', 'Orusts kommun', 'Partille kommun', 'Skara kommun',
        'Skövde kommun', 'Sotenäs kommun', 'Stenungsunds kommun', 'Strömstads kommun', 'Svenljunga kommun',
        'Tanums kommun', 'Tibro kommun', 'Tidaholms kommun', 'Tjörns kommun', 'Tranemo kommun',
        'Trollhättans kommun', 'Töreboda kommun', 'Uddevalla kommun', 'Ulricehamns kommun', 'Vara kommun',
        'Vårgårda kommun', 'Vänersborgs kommun', 'Åmåls kommun', 'Öckerö kommun',
        # Utan 's'
        'Ale kommun', 'Alingsås kommun', 'Bengtsfors kommun', 'Bollebygd kommun', 'Borås kommun',
        'Dals-Ed kommun', 'Essunga kommun', 'Falköping kommun', 'Färgelanda kommun', 'Grästorp kommun',
        'Gullspång kommun', 'Göteborg kommun', 'Götene kommun', 'Herrljunga kommun', 'Hjo kommun',
        'Härryda kommun', 'Karlsborg kommun', 'Kungälv kommun', 'Lerum kommun', 'Lidköping kommun',
        'Lilla Edet kommun', 'Lysekil kommun', 'Mariestad kommun', 'Mark kommun', 'Mellerud kommun',
        'Munkedal kommun', 'Mölndal kommun', 'Orust kommun', 'Partille kommun', 'Skara kommun',
        'Skövde kommun', 'Sotenäs kommun', 'Stenungsund kommun', 'Strömstad kommun', 'Svenljunga kommun',
        'Tanum kommun', 'Tibro kommun', 'Tidaholm kommun', 'Tjörn kommun', 'Tranemo kommun',
        'Trollhättan kommun', 'Töreboda kommun', 'Uddevalla kommun', 'Ulricehamn kommun', 'Vara kommun',
        'Vårgårda kommun', 'Vänersborg kommun', 'Åmål kommun', 'Öckerö kommun',
        # Specialfall
        'Göteborgs stad', 'Göteborg stad', 'Borås stad', 'Trollhättans stad', 'Vänersborgs stad',
        'Skövde stad', 'Lidköpings stad', 'Mölndals stad', 'Alingsås stad', 'Uddevalla stad'
    ]

    try:
        # Läs in GeoJSON-data
        with open('data/kommuner.geo.json', 'r', encoding='utf-8') as f:
            alla_kommuner = json.load(f)

        # Filtrera VG-kommuner
        vg_features = []
        for kommun in alla_kommuner:
            if isinstance(kommun, dict) and 'geometry' in kommun:
                namn = kommun.get('namn')
                if namn in vg_kommuner_namn:
                    vg_features.append({
                        "type": "Feature",
                        "properties": {
                            "name": namn,
                            "original": kommun
                        },
                        "geometry": kommun['geometry']
                    })

        # Generera färger och lägg till på kartan
        colors = generate_distinct_colors(len(vg_features))

        for feature, color in zip(vg_features, colors):
            kommun_namn = feature['properties']['name']
            style_function = StyleFunction(color)

            geojson = folium.GeoJson(
                feature,  # Använd hela feature-objektet direkt
                name=kommun_namn,
                style_function=style_function,
                tooltip=kommun_namn
            )
            geojson.add_to(kommun_layer)

    except Exception as e:
        st.error(f"Fel vid hantering av kommundata: {str(e)}")
        import traceback
        st.write("Detaljerat fel:", traceback.format_exc())

    kommun_layer.add_to(m)

    # Skapa feature groups för olika typer av markörer
    layers = {
        'visionombud': folium.FeatureGroup(name="👁️ Visionombud"),
        'skyddsombud': folium.FeatureGroup(name="🛡️ Skyddsombud")
    }

    # Lägg till alla lager till kartan direkt
    for layer in layers.values():
        m.add_child(layer)

    # Lista för misslyckade platser
    failed_locations = []

    for arbetsplats in _arbetsplatser:
        try:
            if not arbetsplats.get("coordinates"):
                failed_locations.append(f"{arbetsplats.get('namn', 'Okänd arbetsplats')} - Saknar koordinater")
                continue

            location_data = {
                "latitude": arbetsplats["coordinates"]["lat"],
                "longitude": arbetsplats["coordinates"]["lng"]
            }

            har_visionombud = any(
                p.get('visionombud') and arbetsplats['namn'] in p.get('arbetsplats', [])
                for p in _personer
            )

            har_skyddsombud = any(
                p.get('skyddsombud') and arbetsplats['namn'] in p.get('arbetsplats', [])
                for p in _personer
            )

            # Hitta alla ombud för denna arbetsplats med deras förvaltningar
            visionombud_list = [f"{p.get('namn', '')} ({p.get('forvaltning_namn', '')})"
                                for p in _personer
                                if p.get('visionombud') and arbetsplats['namn'] in p.get('arbetsplats', [])]

            skyddsombud_list = [f"{p.get('namn', '')} ({p.get('forvaltning_namn', '')})"
                                for p in _personer
                                if p.get('skyddsombud') and arbetsplats['namn'] in p.get('arbetsplats', [])]

            # Skapa baskoordinater och popup-text med bredare stil
            location = [location_data["latitude"], location_data["longitude"]]

            # Formatera popup-text med namn på ombuden och bredare stil
            visionombud_text = "<br>".join(visionombud_list) if visionombud_list else "Saknar Visionombud"
            skyddsombud_text = "<br>".join(skyddsombud_list) if skyddsombud_list else "Saknar Skyddsombud"

            popup_text = f"""
                <div style="min-width: 300px; max-width: 500px; white-space: nowrap;">
                    <h4 style="margin-bottom: 10px;">{arbetsplats['namn']}</h4>
                    <div style="margin-bottom: 15px;">
                        <strong>Visionombud:</strong><br>
                        {visionombud_text}
                    </div>
                    <div>
                        <strong>Skyddsombud:</strong><br>
                        {skyddsombud_text}
                    </div>
                </div>
            """

            # Uppdatera tooltip-texter också
            vision_tooltip = "Visionombud: " + (", ".join(visionombud_list) if visionombud_list else "Saknas")
            skydd_tooltip = "Skyddsombud: " + (", ".join(skyddsombud_list) if skyddsombud_list else "Saknas")

            # Skapa HTML för skyddsombud-markören
            check_html = f"""
                <div style="
                    font-family: Arial; 
                    font-size: 18px; 
                    color: {'green' if har_skyddsombud else 'red'};
                    text-shadow: 
                        -1px -1px 0 white,
                        1px -1px 0 white,
                        -1px 1px 0 white,
                        1px 1px 0 white;
                    font-weight: bold;
                ">
                    {'✓' if har_skyddsombud else '✕'}
                </div>
            """

            # Lägg till cirkelmarkör för Visionombud
            folium.CircleMarker(
                location=location,
                radius=8,
                popup=folium.Popup(popup_text, max_width=500),  # Använd Popup-objekt för bättre kontroll
                tooltip=vision_tooltip,
                color='green' if har_visionombud else 'red',
                fill=True
            ).add_to(layers['visionombud'])

            # Lägg till bock/kryss för Skyddsombud
            folium.Marker(
                location=[location[0] + 0.0003, location[1]],
                popup=folium.Popup(popup_text, max_width=500),  # Samma popup här
                tooltip=skydd_tooltip,
                icon=folium.DivIcon(
                    html=check_html,
                    icon_size=(20, 20),
                    icon_anchor=(10, 10)
                )
            ).add_to(layers['skyddsombud'])

        except Exception as e:
            failed_locations.append(f"{arbetsplats.get('namn', 'okänd arbetsplats')} - {str(e)}")
            continue

    # Lägg till lager-kontroll
    folium.LayerControl(
        position='topright',
        collapsed=False,
        autoZIndex=True
    ).add_to(m)

    return m, failed_locations


def show(db):
    st.header("Statistik")

    # Hämta all data
    personer = list(db.personer.find())
    forvaltningar = list(db.forvaltningar.find())

    # Skapa DataFrame för enklare analys
    df = pd.DataFrame(personer)

    # Skapa flikar för olika typer av statistik
    tab1, tab2, tab3 = st.tabs([
        "📊 Grundläggande statistik",
        "📈 Detaljerade grafer",
        "🗺️ Täckningskarta"
    ])

    with tab1:
        # Visa övergripande statistik
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Totalt antal med uppdrag", len(personer))

        with col2:
            antal_visionombud = len([p for p in personer if p.get('visionombud')])
            st.metric("Antal Visionombud", antal_visionombud)

        with col3:
            antal_skyddsombud = len([p for p in personer if p.get('skyddsombud')])
            st.metric("Antal Skyddsombud", antal_skyddsombud)

        # Fördelning per förvaltning
        st.subheader("Fördelning per förvaltning")

        forv_stats = df.groupby('forvaltning_namn').agg({
            '_id': 'count',
            'visionombud': 'sum',
            'skyddsombud': 'sum',
            'huvudskyddsombud': 'sum',
            'csg': 'sum',
            'lsg_fsg': 'sum'
        }).reset_index()

        forv_stats.columns = ['Förvaltning', 'Totalt', 'Visionombud', 'Skyddsombud',
                              'Huvudskyddsombud', 'CSG', 'LSG/FSG']

        # Skapa stapeldiagram
        fig = px.bar(forv_stats.melt(id_vars=['Förvaltning'],
                                     value_vars=['Visionombud', 'Skyddsombud', 'CSG', 'LSG/FSG']),
                     x='Förvaltning',
                     y='value',
                     color='variable',
                     title='Uppdrag per förvaltning',
                     labels={'value': 'Antal', 'variable': 'Uppdrag'})

        st.plotly_chart(fig, use_container_width=True)

        # Visa detaljerad statistik
        with st.expander("Visa detaljerad statistik"):
            # Lägg till totalsumma
            total_row = pd.DataFrame({
                'Förvaltning': ['Totalt'],
                'Totalt': [forv_stats['Totalt'].sum()],
                'Visionombud': [forv_stats['Visionombud'].sum()],
                'Skyddsombud': [forv_stats['Skyddsombud'].sum()],
                'Huvudskyddsombud': [forv_stats['Huvudskyddsombud'].sum()],
                'CSG': [forv_stats['CSG'].sum()],
                'LSG/FSG': [forv_stats['LSG/FSG'].sum()]
            })

            # Lägg till total-raden
            forv_stats = pd.concat([forv_stats, total_row], ignore_index=True)

            # Visa statistik utan styling
            st.dataframe(forv_stats)

        # Täckningsgrad
        st.subheader("Täckningsgrad")

        # Beräkna antal enheter och enheter med ombud
        enheter = list(db.enheter.find())
        antal_enheter = len(enheter)

        enheter_med_visionombud = len(set(p['enhet_id'] for p in personer if p.get('visionombud')))
        enheter_med_skyddsombud = len(set(p['enhet_id'] for p in personer if p.get('skyddsombud')))

        col1, col2 = st.columns(2)

        with col1:
            visionombud_tack = (enheter_med_visionombud / antal_enheter) * 100 if antal_enheter > 0 else 0
            st.metric("Täckningsgrad Visionombud", f"{visionombud_tack:.1f}%")

        with col2:
            skyddsombud_tack = (enheter_med_skyddsombud / antal_enheter) * 100 if antal_enheter > 0 else 0
            st.metric("Täckningsgrad Skyddsombud", f"{skyddsombud_tack:.1f}%")

    with tab2:
        st.subheader("Detaljerade analyser")

        # Graf 1: Täckningsgrad per förvaltning
        st.markdown("### Täckningsgrad per förvaltning")

        # Debug information
        st.write(f"Antal förvaltningar: {len(forvaltningar)}")

        # Kontrollera alla enheter först
        alla_enheter = list(db.enheter.find())
        st.write(f"Totalt antal enheter i databasen: {len(alla_enheter)}")

        # Visa några exempel på enheter för att se strukturen
        if alla_enheter:
            st.write("Exempel på en enhet:", alla_enheter[0])

        # Beräkna täckningsgrad per förvaltning
        forv_coverage = []
        for forv in forvaltningar:
            st.write(f"\nDebugging förvaltning: {forv['namn']}")
            st.write(f"Förvaltning ID: {forv['_id']}")

            # Visa alla enheter för denna förvaltning
            enheter = list(db.enheter.find({"forvaltning_namn": forv["namn"]}))
            st.write("Första enheten (om den finns):", enheter[0] if enheter else "Inga enheter hittades")

            forv_enheter = len(enheter)
            st.write(f"Förvaltning: {forv['namn']}, Antal enheter: {forv_enheter}")

            if forv_enheter > 0:
                vision_coverage = len(set(
                    p['enhet_id'] for p in personer
                    if p.get('visionombud') and p['forvaltning_namn'] == forv["namn"]
                )) / forv_enheter * 100

                skydd_coverage = len(set(
                    p['enhet_id'] for p in personer
                    if p.get('skyddsombud') and p['forvaltning_namn'] == forv["namn"]
                )) / forv_enheter * 100

                st.write(f"Vision täckning: {vision_coverage:.1f}%, Skydd täckning: {skydd_coverage:.1f}%")

                forv_coverage.append({
                    'Förvaltning': forv['namn'],
                    'Visionombud': vision_coverage,
                    'Skyddsombud': skydd_coverage
                })

        if forv_coverage:  # Kontrollera att vi har data
            coverage_df = pd.DataFrame(forv_coverage)
            melted_df = coverage_df.melt(
                id_vars='Förvaltning',  # Ändrat från lista till sträng
                value_vars=['Visionombud', 'Skyddsombud'],
                var_name='Typ',
                value_name='Täckningsgrad'
            )

            fig_coverage = px.bar(
                melted_df,
                x='Förvaltning',
                y='Täckningsgrad',
                color='Typ',
                title='Täckningsgrad av ombud per förvaltning',
                labels={'Täckningsgrad': 'Täckningsgrad (%)'})
            st.plotly_chart(fig_coverage, use_container_width=True)
        else:
            st.warning("Ingen data tillgänglig för täckningsgrad per förvaltning")

        # Graf 2: Fördelning av roller
        st.markdown("### Fördelning av roller")
        role_counts = {
            'Visionombud': len([p for p in personer if p.get('visionombud')]),
            'Skyddsombud': len([p for p in personer if p.get('skyddsombud')]),
            'Huvudskyddsombud': len([p for p in personer if p.get('huvudskyddsombud')]),
            'CSG': len([p for p in personer if p.get('csg')]),
            'LSG/FSG': len([p for p in personer if p.get('lsg_fsg')]),
            'Annat fack': len([p for p in personer if p.get('annat_fack')])
        }

        fig_roles = px.pie(
            values=list(role_counts.values()),
            names=list(role_counts.keys()),
            title='Fördelning av roller')
        st.plotly_chart(fig_roles, use_container_width=True)

        # Graf 3: Ordinarie vs Ersättare
        st.markdown("### Ordinarie vs Ersättare")

        csg_stats = {
            'Ordinarie': len([p for p in personer if p.get('csg') and p.get('csg_roll') == 'Ordinarie']),
            'Ersättare': len([p for p in personer if p.get('csg') and p.get('csg_roll') == 'Ersättare'])
        }

        lsg_stats = {
            'Ordinarie': len([p for p in personer if p.get('lsg_fsg') and p.get('lsg_fsg_roll') == 'Ordinarie']),
            'Ersättare': len([p for p in personer if p.get('lsg_fsg') and p.get('lsg_fsg_roll') == 'Ersättare'])
        }

        representation_data = pd.DataFrame({
            'Grupp': ['CSG', 'CSG', 'LSG/FSG', 'LSG/FSG'],
            'Roll': ['Ordinarie', 'Ersättare', 'Ordinarie', 'Ersättare'],
            'Antal': [csg_stats['Ordinarie'], csg_stats['Ersättare'],
                      lsg_stats['Ordinarie'], lsg_stats['Ersättare']]
        })

        fig_repr = px.bar(
            representation_data,
            x='Grupp',
            y='Antal',
            color='Roll',
            barmode='group',
            title='Fördelning Ordinarie/Ersättare i grupper')
        st.plotly_chart(fig_repr, use_container_width=True)

        # Graf 4: Antal personer per avdelning inom varje förvaltning
        st.markdown("### Personer per avdelning")

        dept_counts = df.groupby(['forvaltning_namn', 'avdelning_namn']).size().reset_index(name='Antal')
        fig_dept = px.bar(
            dept_counts,
            x='forvaltning_namn',
            y='Antal',
            color='avdelning_namn',
            title='Antal personer per avdelning inom förvaltningar',
            labels={'forvaltning_namn': 'Förvaltning', 'avdelning_namn': 'Avdelning'})
        st.plotly_chart(fig_dept, use_container_width=True)

    with tab3:
        st.subheader("Geografisk täckning av Visionombud")

        # Hämta alla arbetsplatser
        arbetsplatser = list(db.arbetsplatser.find())

        # Knapp för att uppdatera kartan
        if st.button("🔄 Uppdatera karta och geocoda saknade adresser", key="update_map"):
            # Rensa cache för att tvinga omräkning
            load_map.clear()
            st.session_state.map_loaded = True
            st.rerun()

        # Ladda och visa kartan
        if st.session_state.get('map_loaded', False):
            with st.spinner('Laddar karta...'):
                m, failed_locations = load_map(arbetsplatser, personer, db)

                # Visa förklaring först
                st.markdown("""
                ### Förklaring
                Använd kontrollerna i övre högra hörnet av kartan för att visa/dölja:
                
                - 🏛️ Kommuner
                  - Färgade områden visar kommungränser
                - 👁️ Visionombud
                  - 🟢 Grön cirkel: Har Visionombud
                  - 🔴 Röd cirkel: Saknar Visionombud
                - 🛡️ Skyddsombud
                  - ✓ Grön bock: Har Skyddsombud
                  - ✕ Rött kryss: Saknar Skyddsombud
                """)

                # Sedan visa kartan
                st.markdown("""
                    <style>
                        iframe {
                            width: 1200px;
                            height: 800px;
                            margin: auto;
                            display: block;
                        }
                    </style>
                """, unsafe_allow_html=True)
                folium_static(m)

                # Visa eventuella fel
                if failed_locations:
                    with st.expander("⚠️ Visa problem med geokodning"):
                        st.write("Följande platser kunde inte visas på kartan:")
                        for loc in failed_locations:
                            st.write(f"- {loc}")
        else:
            st.info("👆 Klicka på 'Uppdatera karta' för att ladda kartan")
