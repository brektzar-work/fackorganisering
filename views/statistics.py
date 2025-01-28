"""
Statistikmodul för Vision Sektion 10.

Detta system hanterar avancerad statistik och visualisering av organisationsdata:
1. Grundläggande statistik
   - Totalt antal personer med uppdrag
   - Fördelning av olika uppdragstyper
   - Täckningsgrad för ombud

2. Detaljerade analyser
   - Fördelning per förvaltning
   - Interaktiva grafer och diagram
   - Trendanalyser och jämförelser

3. Geografisk visualisering
   - Täckningskarta med arbetsplatser
   - Visualisering av ombud och representation
   - Kommungränser och regional indelning

4. Medlemsstatistik
   - Fördelning av medlemmar
   - Analys av representation
   - Demografiska översikter

Tekniska detaljer:
- Använder Plotly för interaktiva visualiseringar
- Implementerar Folium för kartfunktionalitet
- Hanterar komplex databearbetning med Pandas
- Tillhandahåller cachning för optimerad prestanda
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import folium
from streamlit_folium import folium_static
import json
import colorsys
from collections import defaultdict
from bson import ObjectId
from views.cache_manager import get_cached_data, update_cache_after_change
import plotly.graph_objects as go
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
import time


def generate_distinct_colors(n):
    """Genererar en uppsättning visuellt distinkta färger.
    
    Funktionen skapar färger med jämn fördelning i färghjulet för optimal
    visuell separation mellan närliggande färger. Använder HSV-färgrymd
    för bättre kontroll över färgmättnad och ljusstyrka.
    
    Args:
        n (int): Antal färger att generera
    
    Returns:
        list: Lista med hex-färgkoder
    
    Tekniska detaljer:
    - Använder HSV-färgrymd för bättre färgkontroll
    - Implementerar transparens för bättre visualisering
    - Konverterar till hex-format för webbkompatibilitet
    """
    colors = []
    for i in range(n):
        hue = i / n
        # Använd ljusa, transparenta färger för bättre visualisering
        rgb = colorsys.hsv_to_rgb(hue, 0.3, 0.9)
        hex_color = '#{:02x}{:02x}{:02x}'.format(
            int(rgb[0] * 255),
            int(rgb[1] * 255),
            int(rgb[2] * 255)
        )
        colors.append(hex_color)
    return colors


class StyleFunction:
    """Hanterar stilsättning för geografiska element på kartan.
    
    Denna klass definierar utseendet för geografiska områden som
    kommuner och regioner på kartan. Den implementerar en callable
    interface för användning med Folium's style_function.
    
    Attribut:
        color (str): Hex-färgkod för området
    
    Tekniska detaljer:
    - Implementerar __call__ för användning som callback
    - Hanterar serialisering för cachning
    - Definierar standardvärden för kartvisualisering
    """
    def __init__(self, color):
        self.color = color

    def __call__(self, feature):
        """Returnerar stilattribut för ett geografiskt element.
        
        Args:
            feature: GeoJSON-feature som ska stilsättas
        
        Returns:
            dict: Stilattribut för elementet
        """
        return {
            'fillColor': self.color,
            'fillOpacity': 0.3,
            'color': 'gray',
            'weight': 1,
            'dashArray': '5, 5'
        }

    def __getstate__(self):
        """Serialiserar objektet för cachning."""
        return {'color': self.color}

    def __setstate__(self, state):
        """Återställer objektet från cachad data."""
        self.color = state['color']


@st.cache_data(ttl=3600)  # Cache i 1 timme
def load_map(_arbetsplatser, _personer, _db):
    """Laddar och skapar kartan med alla arbetsplatser och ombud."""
    # Skapa en karta centrerad över Västra Götaland med begränsningar
    m = folium.Map(
        location=[58.2, 13.0],  # Centrerad över VGR
        zoom_start=8,
        min_zoom=7,  # Förhindra för mycket utzoomning
        max_zoom=18,  # Ökat från 13 till 18 för att tillåta närmare inzoomning
        max_bounds=True,  # Aktivera gränser
        min_lat=56.0,  # Södra gränsen
        max_lat=60.0,  # Norra gränsen
        min_lon=10.0,  # Västra gränsen
        max_lon=15.5,  # Östra gränsen
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    )

    # Sätt gränser för panorering
    m.fit_bounds([[56.0, 10.0], [60.0, 15.5]])

    # Lägg till kommungränser som ett eget lager
    kommun_layer = folium.FeatureGroup(name="🏛️ Kommuner")

    # Lista över kommuner i Västra Götaland
    vg_kommuner_namn = [
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
        # Specialfall
        'Göteborgs stad', 'Göteborg stad', 'Borås stad', 'Trollhättans stad', 'Vänersborgs stad',
        'Skövde stad', 'Lidköpings stad', 'Mölndals stad', 'Alingsås stad', 'Uddevalla stad'
    ]

    try:
        # Läs in GeoJSON-data för kommuner
        with open('data/kommuner.geo.json', 'r', encoding='utf-8') as f:
            alla_kommuner = json.load(f)

        # Filtrera VG-kommuner och lägg till på kartan
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
                feature,
                name=kommun_namn,
                style_function=style_function,
                tooltip=kommun_namn
            )
            geojson.add_to(kommun_layer)

    except Exception as e:
        st.error(f"Fel vid hantering av kommundata: {str(e)}")

    # Lägg till kommunlagret till kartan
    kommun_layer.add_to(m)

    # Skapa feature groups för olika typer av markörer
    layers = {
        'visionombud': folium.FeatureGroup(name="👁️ Visionombud"),
        'skyddsombud': folium.FeatureGroup(name="🛡️ Skyddsombud")
    }

    # Lägg till alla lager till kartan
    for layer in layers.values():
        m.add_child(layer)

    # Lista för misslyckade platser
    failed_locations = []

    # Räkna arbetsplatser med koordinater
    arbetsplatser_med_koordinater = [ap for ap in _arbetsplatser if ap.get('coordinates')]
    
    for arbetsplats in arbetsplatser_med_koordinater:
        try:
            # Kontrollera att koordinaterna är giltiga
            if not arbetsplats.get("coordinates") or \
               not isinstance(arbetsplats["coordinates"].get("lat"), (int, float)) or \
               not isinstance(arbetsplats["coordinates"].get("lng"), (int, float)):
                failed_locations.append(f"{arbetsplats.get('namn', 'Okänd arbetsplats')} - Ogiltiga koordinater")
                continue

            # Hämta koordinater
            location = [
                arbetsplats["coordinates"]["lat"],
                arbetsplats["coordinates"]["lng"]
            ]

            # Kontrollera att koordinaterna är inom rimliga gränser
            if not (56.0 <= location[0] <= 60.0 and 10.0 <= location[1] <= 15.5):
                failed_locations.append(f"{arbetsplats.get('namn', 'Okänd arbetsplats')} - Koordinater utanför VG-regionen")
                continue

            # Hitta ombud för denna arbetsplats
            visionombud_list = [
                f"{p.get('namn', '')} ({p.get('forvaltning_namn', '')})"
                for p in _personer
                if p.get('visionombud') and arbetsplats['namn'] in p.get('arbetsplats', [])
            ]
            
            skyddsombud_list = [
                f"{p.get('namn', '')} ({p.get('forvaltning_namn', '')})"
                for p in _personer
                if p.get('skyddsombud') and arbetsplats['namn'] in p.get('arbetsplats', [])
            ]

            har_visionombud = len(visionombud_list) > 0
            har_skyddsombud = len(skyddsombud_list) > 0

            # Skapa popup-innehåll
            popup_text = f"""
            <div style='min-width: 200px'>
                <h4>{arbetsplats['namn']}</h4>
                <p><strong>Adress:</strong><br>
                {arbetsplats.get('gatuadress', '')}<br>
                {arbetsplats.get('postnummer', '')} {arbetsplats.get('ort', '')}</p>
                <p><strong>Kommun:</strong> {arbetsplats.get('kommun', '')}</p>
                <p><strong>Förvaltning:</strong> {arbetsplats.get('forvaltning_namn', 'Alla förvaltningar')}</p>
                
                <div style='margin-top: 10px'>
                    <strong>Visionombud:</strong><br>
                    {'<br>'.join(visionombud_list) if visionombud_list else 'Saknas'}
                </div>
                
                <div style='margin-top: 10px'>
                    <strong>Skyddsombud:</strong><br>
                    {'<br>'.join(skyddsombud_list) if skyddsombud_list else 'Saknas'}
                </div>
            </div>
            """

            # Skapa tooltips
            vision_tooltip = f"{arbetsplats['namn']} - {'Har' if har_visionombud else 'Saknar'} Visionombud"
            skydd_tooltip = f"{arbetsplats['namn']} - {'Har' if har_skyddsombud else 'Saknar'} Skyddsombud"

            # HTML för bock/kryss
            check_html = f"""
                <div style='text-align: center; line-height: 20px; font-size: 16px; color: {'green' if har_skyddsombud else 'red'};'>
                    {'✓' if har_skyddsombud else '✗'}
                </div>
            """

            # Lägg till cirkelmarkör för Visionombud
            folium.CircleMarker(
                location=location,
                radius=8,
                popup=folium.Popup(popup_text, max_width=500),
                tooltip=vision_tooltip,
                color='green' if har_visionombud else 'red',
                fill=True
            ).add_to(layers['visionombud'])

            # Lägg till bock/kryss för Skyddsombud
            folium.Marker(
                location=[location[0] + 0.0003, location[1]],
                popup=folium.Popup(popup_text, max_width=500),
                tooltip=skydd_tooltip,
                icon=folium.DivIcon(
                    html=check_html,
                    icon_size=(20, 20),
                    icon_anchor=(10, 10)
                )
            ).add_to(layers['skyddsombud'])

        except Exception as e:
            failed_locations.append(f"{arbetsplats.get('namn', 'Okänd arbetsplats')} - {str(e)}")
            continue

    # Lägg till lager-kontroll
    folium.LayerControl(
        position='topright',
        collapsed=False,
        autoZIndex=True
    ).add_to(m)

    return m, failed_locations


def geocode_address(address, city, municipality):
    """Konverterar en adress till koordinater med hjälp av Nominatim."""
    try:
        geolocator = Nominatim(user_agent="vision_sektion10")
        # Kombinera adress med stad och kommun för bättre träffsäkerhet
        full_address = f"{address}, {city}, {municipality}, Västra Götaland, Sweden"
        location = geolocator.geocode(full_address)
        
        if location:
            return {"lat": location.latitude, "lng": location.longitude}
        return None
    except GeocoderTimedOut:
        time.sleep(1)  # Vänta en sekund och försök igen
        return geocode_address(address, city, municipality)
    except Exception as e:
        st.error(f"Fel vid geokodning av {address}: {str(e)}")
        return None


def generate_missing_coordinates(db, arbetsplatser):
    """Genererar koordinater för arbetsplatser som saknar dem."""
    updated_count = 0
    failed_count = 0
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    total = len([ap for ap in arbetsplatser if not ap.get('coordinates')])
    current = 0
    
    for arbetsplats in arbetsplatser:
        if not arbetsplats.get('coordinates'):
            current += 1
            progress = current / total
            progress_bar.progress(progress)
            status_text.text(f"Bearbetar {current} av {total} arbetsplatser...")
            
            if arbetsplats.get('gatuadress') and arbetsplats.get('ort') and arbetsplats.get('kommun'):
                coordinates = geocode_address(
                    arbetsplats['gatuadress'],
                    arbetsplats['ort'],
                    arbetsplats['kommun']
                )
                
                if coordinates:
                    # Uppdatera databasen med de nya koordinaterna
                    result = db.arbetsplatser.update_one(
                        {"_id": arbetsplats["_id"]},
                        {"$set": {"coordinates": coordinates}}
                    )
                    if result.modified_count > 0:
                        updated_count += 1
                else:
                    failed_count += 1
            else:
                failed_count += 1
    
    progress_bar.empty()
    status_text.empty()
    
    return updated_count, failed_count


def show(db):
    """Visar statistik och grafer för organisationen."""
    st.header("Statistik och Grafer")

    # Ladda cachad data
    cached, indexes = get_cached_data(db)
    
    # Uppdateringsknapp i sidofältet
    if st.sidebar.button("↻ Uppdatera data", key="refresh_stats"):
        cached, indexes = get_cached_data(db, force_refresh=True)
        st.rerun()

    # Skapa flikar för olika typer av statistik
    tab1, tab2, tab3, tab4 = st.tabs([
        "Översikt",
        "Detaljerad Statistik",
        "Ombudsstatistik",
        "Karta"
    ])

    with tab1:
        st.subheader("Översikt")
        
        # Beräkna totala antalet och nyckeltal
        total_personer = len(cached['personer'])
        total_arbetsplatser = len(cached['arbetsplatser'])
        total_forvaltningar = len(cached['forvaltningar'])
        total_avdelningar = len(cached['avdelningar'])
        total_enheter = len(cached['enheter'])
        total_visionombud = len([p for p in cached['personer'] if p.get('visionombud', False)])
        total_skyddsombud = len([p for p in cached['personer'] if p.get('skyddsombud', False)])
        total_members = sum(f.get('beraknat_medlemsantal', 0) for f in cached['forvaltningar'])

        # Visa nyckeltal i kolumner
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Totalt antal medlemmar", total_members)
            st.metric("Visionombud", total_visionombud)
            st.metric("Medlemmar per Visionombud", round(total_members / total_visionombud if total_visionombud > 0 else 0, 1))
        with col2:
            st.metric("Antal Arbetsplatser", total_arbetsplatser)
            st.metric("Skyddsombud", total_skyddsombud)
            st.metric("Medlemmar per Skyddsombud", round(total_members / total_skyddsombud if total_skyddsombud > 0 else 0, 1))
        with col3:
            st.metric("Förvaltningar", total_forvaltningar)
            st.metric("Avdelningar", total_avdelningar)
            st.metric("Enheter", total_enheter)

        # Skapa en pie chart för fördelning av medlemmar per förvaltning
        medlemmar_per_forv = {
            f['namn']: f.get('beraknat_medlemsantal', 0) 
            for f in cached['forvaltningar'] 
            if f.get('beraknat_medlemsantal', 0) > 0
        }
        if medlemmar_per_forv:
            fig = px.pie(
                values=list(medlemmar_per_forv.values()),
                names=list(medlemmar_per_forv.keys()),
                title="Fördelning av medlemmar per förvaltning"
            )
            st.plotly_chart(fig, key="pie_medlemmar_per_forv")

        # Skapa stapeldiagram för ombud per förvaltning
        ombud_data = []
        for forv in cached['forvaltningar']:
            forv_personer = [p for p in cached['personer'] if str(p.get('forvaltning_id')) == str(forv['_id'])]
            vision_count = len([p for p in forv_personer if p.get('visionombud', False)])
            skydd_count = len([p for p in forv_personer if p.get('skyddsombud', False)])
            if vision_count > 0 or skydd_count > 0:
                ombud_data.append({
                    'Förvaltning': forv['namn'],
                    'Visionombud': vision_count,
                    'Skyddsombud': skydd_count
                })

        if ombud_data:
            df = pd.DataFrame(ombud_data)
            fig = px.bar(
                df,
                x='Förvaltning',
                y=['Visionombud', 'Skyddsombud'],
                title="Fördelning av ombud per förvaltning",
                barmode='group'
            )
            st.plotly_chart(fig, key="bar_ombud_per_forv")

    with tab2:
        st.subheader("Detaljerad Statistik")
        
        # Skapa stapeldiagram för arbetsplatser per förvaltning
        arbetsplatser_per_forv = {}
        for arbetsplats in cached['arbetsplatser']:
            if arbetsplats.get('alla_forvaltningar'):
                arbetsplatser_per_forv['Regionala'] = arbetsplatser_per_forv.get('Regionala', 0) + 1
            else:
                forv_namn = arbetsplats.get('forvaltning_namn', 'Okänd')
                arbetsplatser_per_forv[forv_namn] = arbetsplatser_per_forv.get(forv_namn, 0) + 1

        if arbetsplatser_per_forv:
            fig = px.bar(
                x=list(arbetsplatser_per_forv.keys()),
                y=list(arbetsplatser_per_forv.values()),
                title="Antal arbetsplatser per förvaltning",
                labels={'x': 'Förvaltning', 'y': 'Antal arbetsplatser'}
            )
            st.plotly_chart(fig, key="bar_arbetsplatser_per_forv")

        # Ny graf: Jämförelse av ombud per arbetsplats
        arbetsplats_ombud_data = []
        for arbetsplats in cached['arbetsplatser']:
            vision_count = len([p for p in cached['personer'] 
                              if p.get('visionombud', False) and 
                              arbetsplats['namn'] in p.get('arbetsplats', [])])
            skydd_count = len([p for p in cached['personer'] 
                             if p.get('skyddsombud', False) and 
                             arbetsplats['namn'] in p.get('arbetsplats', [])])
            
            if vision_count > 0 or skydd_count > 0:
                arbetsplats_ombud_data.append({
                    'Arbetsplats': arbetsplats['namn'],
                    'Visionombud': vision_count,
                    'Skyddsombud': skydd_count,
                    'Förvaltning': arbetsplats.get('forvaltning_namn', 'Regionala')
                })

        if arbetsplats_ombud_data:
            # Sortera efter totalt antal ombud (Vision + Skydd)
            arbetsplats_ombud_data.sort(
                key=lambda x: x['Visionombud'] + x['Skyddsombud'], 
                reverse=True
            )
            
            df = pd.DataFrame(arbetsplats_ombud_data)
            fig = px.bar(
                df,
                x='Arbetsplats',
                y=['Visionombud', 'Skyddsombud'],
                title="Antal ombud per arbetsplats",
                barmode='group',
                color_discrete_sequence=['#2ecc71', '#e74c3c'],
                hover_data=['Förvaltning']
            )
            fig.update_layout(
                xaxis_tickangle=-45,
                height=600,
                showlegend=True,
                xaxis_title="Arbetsplats",
                yaxis_title="Antal ombud"
            )
            st.plotly_chart(fig, key="bar_ombud_per_arbetsplats")

        # Ny graf: Detaljerad jämförelse av ombud per förvaltning
        forvaltning_ombud_data = []
        for forv in cached['forvaltningar']:
            forv_personer = [p for p in cached['personer'] if str(p.get('forvaltning_id')) == str(forv['_id'])]
            vision_count = len([p for p in forv_personer if p.get('visionombud', False)])
            skydd_count = len([p for p in forv_personer if p.get('skyddsombud', False)])
            total_arbetsplatser = len([ap for ap in cached['arbetsplatser'] 
                                     if ap.get('forvaltning_id') == forv['_id']])
            
            if vision_count > 0 or skydd_count > 0:
                forvaltning_ombud_data.append({
                    'Förvaltning': forv['namn'],
                    'Visionombud': vision_count,
                    'Skyddsombud': skydd_count,
                    'Antal arbetsplatser': total_arbetsplatser,
                    'Visionombud per arbetsplats': round(vision_count / total_arbetsplatser if total_arbetsplatser > 0 else 0, 2),
                    'Skyddsombud per arbetsplats': round(skydd_count / total_arbetsplatser if total_arbetsplatser > 0 else 0, 2)
                })

        if forvaltning_ombud_data:
            df = pd.DataFrame(forvaltning_ombud_data)
            
            # Skapa två grafer: en för totala antalet och en för per arbetsplats
            col1, col2 = st.columns(2)
            
            with col1:
                fig1 = px.bar(
                    df,
                    x='Förvaltning',
                    y=['Visionombud', 'Skyddsombud'],
                    title="Totalt antal ombud per förvaltning",
                    barmode='group',
                    color_discrete_sequence=['#2ecc71', '#e74c3c']
                )
                fig1.update_layout(
                    xaxis_tickangle=-45,
                    height=400,
                    showlegend=True,
                    xaxis_title="Förvaltning",
                    yaxis_title="Antal ombud"
                )
                st.plotly_chart(fig1, key="bar_total_ombud_per_forv")
            
            with col2:
                fig2 = px.bar(
                    df,
                    x='Förvaltning',
                    y=['Visionombud per arbetsplats', 'Skyddsombud per arbetsplats'],
                    title="Genomsnittligt antal ombud per arbetsplats och förvaltning",
                    barmode='group',
                    color_discrete_sequence=['#2ecc71', '#e74c3c']
                )
                fig2.update_layout(
                    xaxis_tickangle=-45,
                    height=400,
                    showlegend=True,
                    xaxis_title="Förvaltning",
                    yaxis_title="Genomsnittligt antal ombud per arbetsplats"
                )
                st.plotly_chart(fig2, key="bar_ombud_per_arbetsplats_forv")

        # Skapa jämförelsediagram för medlemmar och ombud per förvaltning
        comparison_data = []
        for forv in cached['forvaltningar']:
            members = forv.get('beraknat_medlemsantal', 0)
            if members > 0:
                forv_personer = [p for p in cached['personer'] if str(p.get('forvaltning_id')) == str(forv['_id'])]
                vision_count = len([p for p in forv_personer if p.get('visionombud', False)])
                skydd_count = len([p for p in forv_personer if p.get('skyddsombud', False)])
                
                comparison_data.append({
                    'Förvaltning': forv['namn'],
                    'Medlemmar per Visionombud': round(members / vision_count if vision_count > 0 else 0, 1),
                    'Medlemmar per Skyddsombud': round(members / skydd_count if skydd_count > 0 else 0, 1)
                })

        if comparison_data:
            df = pd.DataFrame(comparison_data)
            fig = px.bar(
                df,
                x='Förvaltning',
                y=['Medlemmar per Visionombud', 'Medlemmar per Skyddsombud'],
                title="Medlemmar per ombud per förvaltning",
                barmode='group'
            )
            st.plotly_chart(fig, key="bar_medlemmar_per_ombud")

        # Visa täckningsgrad för ombud
        st.subheader("Täckningsgrad för ombud")
        
        # Beräkna täckningsgrad för arbetsplatser
        arbetsplatser_med_vision = set()
        arbetsplatser_med_skydd = set()
        
        for person in cached['personer']:
            if person.get('visionombud') and person.get('arbetsplats'):
                arbetsplatser_med_vision.update(person['arbetsplats'])
            if person.get('skyddsombud') and person.get('arbetsplats'):
                arbetsplatser_med_skydd.update(person['arbetsplats'])

        total_arbetsplatser = len(set(ap['namn'] for ap in cached['arbetsplatser']))
        
        coverage_data = [{
            'Typ': 'Arbetsplatser med Visionombud',
            'Antal': len(arbetsplatser_med_vision),
            'Procent': round(len(arbetsplatser_med_vision) / total_arbetsplatser * 100, 1)
        }, {
            'Typ': 'Arbetsplatser med Skyddsombud',
            'Antal': len(arbetsplatser_med_skydd),
            'Procent': round(len(arbetsplatser_med_skydd) / total_arbetsplatser * 100, 1)
        }, {
            'Typ': 'Arbetsplatser utan ombud',
            'Antal': total_arbetsplatser - len(arbetsplatser_med_vision.union(arbetsplatser_med_skydd)),
            'Procent': round((total_arbetsplatser - len(arbetsplatser_med_vision.union(arbetsplatser_med_skydd))) / total_arbetsplatser * 100, 1)
        }]

        df = pd.DataFrame(coverage_data)
        fig = px.bar(
            df,
            x='Typ',
            y='Procent',
            title="Täckningsgrad för ombud på arbetsplatser",
            text='Procent',
            labels={'Procent': 'Procent av arbetsplatser'}
        )
        fig.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
        st.plotly_chart(fig, key="bar_tackningsgrad")

    with tab3:
        st.subheader("Ombudsstatistik")
        
        stats_tab1, stats_tab2 = st.tabs(["Visionombud", "Skyddsombud"])
        
        with stats_tab1:
            # Hjälpfunktion för att räkna Visionombud
            def count_vision_reps(personer_list, filter_func=None):
                """Räknar antalet Visionombud baserat på givna filter."""
                if filter_func:
                    personer_list = [p for p in personer_list if filter_func(p)]
                return len([p for p in personer_list if p.get("visionombud", False)])

            # Översikt av totala antal
            st.markdown("### Total Översikt")
            total_members = sum(f.get('beraknat_medlemsantal', 0) for f in cached['forvaltningar'])
            total_reps = count_vision_reps(cached['personer'])
            
            # Visa totala mätvärden
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Totalt antal medlemmar", total_members)
            with col2:
                st.metric("Totalt antal Visionombud", total_reps)
            
            if total_members > 0:
                st.metric("Medlemmar per Visionombud", 
                         round(total_members / total_reps if total_reps > 0 else float('inf'), 1))
            
            # Statistik per förvaltning
            st.markdown("### Per Förvaltning")
            for forv in cached['forvaltningar']:
                # Räkna ombud för denna förvaltning
                reps = count_vision_reps(cached['personer'], 
                    lambda p: str(p.get('forvaltning_id')) == str(forv['_id']))
                
                # Visa om det finns ombud eller medlemmar
                if reps > 0 or forv.get('beraknat_medlemsantal', 0) > 0:
                    with st.expander(f"{forv['namn']}"):
                        members = forv.get('beraknat_medlemsantal', 0)
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("Antal medlemmar", members)
                        with col2:
                            st.metric("Antal Visionombud", reps)
                        
                        if members > 0:
                            st.metric("Medlemmar per Visionombud", 
                                round(members / reps if reps > 0 else float('inf'), 1))
            
            # Statistik per avdelning
            st.markdown("### Per Avdelning")
            for avd in cached['avdelningar']:
                # Räkna ombud för denna avdelning
                reps = count_vision_reps(cached['personer'], 
                    lambda p: str(p.get('avdelning_id')) == str(avd['_id']))
                
                # Visa om det finns ombud eller medlemmar
                if reps > 0 or avd.get('beraknat_medlemsantal', 0) > 0:
                    with st.expander(f"{avd['namn']} ({avd['forvaltning_namn']})"):
                        members = avd.get('beraknat_medlemsantal', 0)
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("Antal medlemmar", members)
                        with col2:
                            st.metric("Antal Visionombud", reps)
                        
                        if members > 0:
                            st.metric("Medlemmar per Visionombud", 
                                round(members / reps if reps > 0 else float('inf'), 1))
            
            # Statistik per enhet
            st.markdown("### Per Enhet")
            for enhet in cached['enheter']:
                # Räkna ombud för denna enhet
                reps = count_vision_reps(cached['personer'], 
                    lambda p: str(p.get('enhet_id')) == str(enhet['_id']))
                
                # Visa om det finns ombud eller medlemmar
                if reps > 0 or enhet.get('beraknat_medlemsantal', 0) > 0:
                    with st.expander(f"{enhet['namn']} ({enhet['avdelning_namn']}, {enhet['forvaltning_namn']})"):
                        members = enhet.get('beraknat_medlemsantal', 0)
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("Antal medlemmar", members)
                        with col2:
                            st.metric("Antal Visionombud", reps)
                        
                        if members > 0:
                            st.metric("Medlemmar per Visionombud", 
                                round(members / reps if reps > 0 else float('inf'), 1))

        with stats_tab2:
            # Hjälpfunktion för att räkna Skyddsombud
            def count_safety_reps(personer_list, filter_func=None):
                """Räknar antalet Skyddsombud baserat på givna filter."""
                if filter_func:
                    personer_list = [p for p in personer_list if filter_func(p)]
                return len([p for p in personer_list if p.get("skyddsombud", False)])

            # Översikt av totala antal
            st.markdown("### Total Översikt")
            total_members = sum(f.get('beraknat_medlemsantal', 0) for f in cached['forvaltningar'])
            total_reps = count_safety_reps(cached['personer'])
            
            # Visa totala mätvärden
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Totalt antal medlemmar", total_members)
            with col2:
                st.metric("Totalt antal Skyddsombud", total_reps)
            
            if total_members > 0:
                st.metric("Medlemmar per Skyddsombud", 
                         round(total_members / total_reps if total_reps > 0 else float('inf'), 1))
            
            # Statistik per förvaltning
            st.markdown("### Per Förvaltning")
            for forv in cached['forvaltningar']:
                # Räkna ombud för denna förvaltning
                reps = count_safety_reps(cached['personer'], 
                    lambda p: str(p.get('forvaltning_id')) == str(forv['_id']))
                
                # Visa om det finns ombud eller medlemmar
                if reps > 0 or forv.get('beraknat_medlemsantal', 0) > 0:
                    with st.expander(f"{forv['namn']}"):
                        members = forv.get('beraknat_medlemsantal', 0)
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("Antal medlemmar", members)
                        with col2:
                            st.metric("Antal Skyddsombud", reps)
                        
                        if members > 0:
                            st.metric("Medlemmar per Skyddsombud", 
                                round(members / reps if reps > 0 else float('inf'), 1))
            
            # Statistik per avdelning
            st.markdown("### Per Avdelning")
            for avd in cached['avdelningar']:
                # Räkna ombud för denna avdelning
                reps = count_safety_reps(cached['personer'], 
                    lambda p: str(p.get('avdelning_id')) == str(avd['_id']))
                
                # Visa om det finns ombud eller medlemmar
                if reps > 0 or avd.get('beraknat_medlemsantal', 0) > 0:
                    with st.expander(f"{avd['namn']} ({avd['forvaltning_namn']})"):
                        members = avd.get('beraknat_medlemsantal', 0)
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("Antal medlemmar", members)
                        with col2:
                            st.metric("Antal Skyddsombud", reps)
                        
                        if members > 0:
                            st.metric("Medlemmar per Skyddsombud", 
                                round(members / reps if reps > 0 else float('inf'), 1))
            
            # Statistik per enhet
            st.markdown("### Per Enhet")
            for enhet in cached['enheter']:
                # Räkna ombud för denna enhet
                reps = count_safety_reps(cached['personer'], 
                    lambda p: str(p.get('enhet_id')) == str(enhet['_id']))
                
                # Visa om det finns ombud eller medlemmar
                if reps > 0 or enhet.get('beraknat_medlemsantal', 0) > 0:
                    with st.expander(f"{enhet['namn']} ({enhet['avdelning_namn']}, {enhet['forvaltning_namn']})"):
                        members = enhet.get('beraknat_medlemsantal', 0)
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("Antal medlemmar", members)
                        with col2:
                            st.metric("Antal Skyddsombud", reps)
                        
                        if members > 0:
                            st.metric("Medlemmar per Skyddsombud", 
                                round(members / reps if reps > 0 else float('inf'), 1))

    with tab4:
        st.subheader("Geografisk Översikt")
        
        # Ladda och visa kartan
        arbetsplatser = cached['arbetsplatser']
        personer = cached['personer']
        
        # Knapp för att ladda om kartan
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("🔄 Ladda om kartan"):
                # Rensa cache för kartan
                load_map.clear()
                st.rerun()
        
        # Visa statistik om arbetsplatser på kartan
        with col2:
            total_arbetsplatser = len(arbetsplatser)
            arbetsplatser_med_koordinater = len([ap for ap in arbetsplatser if ap.get('coordinates')])
            st.info(f"Visar {arbetsplatser_med_koordinater} av {total_arbetsplatser} arbetsplatser på kartan")
        
        # Visa kartan med arbetsplatser och ombud
        karta, failed_locations = load_map(arbetsplatser, personer, db)
        folium_static(karta)

        # Visa eventuella platser som saknar koordinater
        st.markdown("### Arbetsplatser som saknar koordinater")
        saknar_koordinater = [ap['namn'] for ap in arbetsplatser if not ap.get('coordinates')]
        
        if saknar_koordinater:
            col1, col2 = st.columns([1, 4])
            with col1:
                # Knapp för att generera koordinater
                if st.button("🌍 Generera koordinater"):
                    with st.spinner('Genererar koordinater...'):
                        updated, failed = generate_missing_coordinates(db, arbetsplatser)
                        if updated > 0:
                            st.success(f"✅ Genererade koordinater för {updated} arbetsplatser!")
                            if failed > 0:
                                st.warning(f"⚠️ Kunde inte generera koordinater för {failed} arbetsplatser")
                            # Uppdatera cachen och ladda om sidan
                            update_cache_after_change(db, 'arbetsplatser', 'update')
                            # Rensa cache för kartan
                            load_map.clear()
                            st.rerun()
                        else:
                            st.error("❌ Kunde inte generera några koordinater")
            
            with col2:
                for plats in saknar_koordinater:
                    st.warning(f"⚠️ {plats}")
        else:
            st.success("✅ Alla arbetsplatser har koordinater")

        # Visa eventuella fel vid kartgenerering
        if failed_locations:
            st.markdown("### Problem vid kartgenerering")
            for error in failed_locations:
                st.error(f"❌ {error}")
