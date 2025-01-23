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
    m.fit_bounds([[56.0, 10.0], [60.0, 15.5]])  # Uppdatera också fit_bounds

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

            # Hitta alla ombud och medlemmar för denna arbetsplats
            visionombud_list = [f"{p.get('namn', '')} ({p.get('forvaltning_namn', '')})"
                                for p in _personer
                                if p.get('visionombud') and arbetsplats['namn'] in p.get('arbetsplats', [])]

            skyddsombud_list = [f"{p.get('namn', '')} ({p.get('forvaltning_namn', '')})"
                                for p in _personer
                                if p.get('skyddsombud') and arbetsplats['namn'] in p.get('arbetsplats', [])]

            # Räkna medlemmar per nivå
            medlemmar_total = 0
            medlemmar_per_enhet = {}
            medlemmar_per_avdelning = {}
            medlemmar_per_forvaltning = {}

            # Om arbetsplatsen har ett direkt medlemsantal
            if 'medlemsantal' in arbetsplats:
                medlemmar_total = arbetsplats['medlemsantal']
                if arbetsplats.get('forvaltning_namn'):
                    medlemmar_per_forvaltning[arbetsplats['forvaltning_namn']] = medlemmar_total

            # Om arbetsplatsen har medlemmar per förvaltning
            elif arbetsplats.get('medlemmar_per_forvaltning'):
                for forv_id, forv_data in arbetsplats['medlemmar_per_forvaltning'].items():
                    try:
                        # Hitta förvaltningsnamnet från databasen
                        forvaltning = _db.forvaltningar.find_one({"_id": ObjectId(forv_id)})
                        if forvaltning and isinstance(forv_data, dict):
                            # Räkna medlemmar från enheter under denna förvaltning
                            if 'enheter' in forv_data:
                                for enhet_id, antal in forv_data['enheter'].items():
                                    if isinstance(antal, (int, float)):
                                        medlemmar_total += antal
                                        # Hitta enhetsnamnet från databasen
                                        enhet = _db.enheter.find_one({"_id": ObjectId(enhet_id)})
                                        if enhet:
                                            medlemmar_per_enhet[enhet['namn']] = antal
                                            # Lägg till i avdelningsstatistiken
                                            if enhet.get('avdelning_namn'):
                                                medlemmar_per_avdelning[enhet['avdelning_namn']] = \
                                                    medlemmar_per_avdelning.get(enhet['avdelning_namn'], 0) + antal
                                            # Lägg till i förvaltningsstatistiken
                                            medlemmar_per_forvaltning[forvaltning['namn']] = \
                                                medlemmar_per_forvaltning.get(forvaltning['namn'], 0) + antal
                    except Exception as e:
                        st.error(f"Fel vid hämtning av data för förvaltning {forv_id}: {str(e)}")

            # Formatera medlemstext
            medlemmar_text = f"Antal Medlemmar: {medlemmar_total}<br>"
            
            if medlemmar_per_enhet:
                medlemmar_text += "<br>Antal Medlemmar per Enhet:<br>"
                for enhet, antal in sorted(medlemmar_per_enhet.items()):
                    medlemmar_text += f"&nbsp;&nbsp;{enhet}: {antal}<br>"
            
            if medlemmar_per_avdelning:
                medlemmar_text += "<br>Antal Medlemmar per Avdelning:<br>"
                for avd, antal in sorted(medlemmar_per_avdelning.items()):
                    medlemmar_text += f"&nbsp;&nbsp;{avd}: {antal}<br>"
            
            if medlemmar_per_forvaltning:
                medlemmar_text += "<br>Antal Medlemmar per Förvaltning:<br>"
                for forv, antal in sorted(medlemmar_per_forvaltning.items()):
                    medlemmar_text += f"&nbsp;&nbsp;{forv}: {antal}<br>"

            # Skapa baskoordinater
            location = [location_data["latitude"], location_data["longitude"]]

            # Formatera popup-text med namn på ombuden och bredare stil
            visionombud_text = "<br>".join(visionombud_list) if visionombud_list else "Saknar Visionombud"
            skyddsombud_text = "<br>".join(skyddsombud_list) if skyddsombud_list else "Saknar Skyddsombud"

            popup_text = f'''
                <div style="min-width: 300px; max-width: 500px;">
                    <h4 style="margin-bottom: 10px;">{arbetsplats['namn']}</h4>
                    <div style="margin-bottom: 15px;">
                        <strong>Visionombud:</strong><br>
                        {visionombud_text}
                    </div>
                    <div style="margin-bottom: 15px;">
                        <strong>Skyddsombud:</strong><br>
                        {skyddsombud_text}
                    </div>
                    <div>
                        {medlemmar_text}
                    </div>
                </div>
            '''

            # Uppdatera tooltip-texter också
            vision_tooltip = "Visionombud: " + (", ".join(visionombud_list) if visionombud_list else "Saknas")
            skydd_tooltip = "Skyddsombud: " + (", ".join(skyddsombud_list) if skyddsombud_list else "Saknas")

            # Skapa HTML för skyddsombud-markören
            check_html = f'''
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
            '''

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
    """Huvudfunktion för statistikvisualisering och analys.
    
    Denna funktion hanterar den övergripande presentationen av statistik
    och visualiseringar för Vision Sektion 10. Den är uppdelad i flera
    huvudområden för att ge en komplett översikt över organisationen.
    
    Funktionalitet:
    1. Datainsamling och Bearbetning
       - Hämtar aktuell data från MongoDB
       - Beräknar nyckeltal och statistik
       - Förbereder data för visualisering
    
    2. Visualiseringar
       - Interaktiv täckningskarta
       - Statistiska diagram och grafer
       - Trendanalyser och jämförelser
    
    3. Användarinteraktion
       - Filtreringsmöjligheter
       - Detaljerad information
       - Nedladdningsalternativ
    
    Args:
        db: MongoDB-databasanslutning
    
    Tekniska detaljer:
    - Använder Streamlit för UI
    - Plotly för interaktiva grafer
    - Folium för kartvisualisering
    - Implementerar cachning
    """
    # Konfigurera sidlayout och titel
    st.title("📊 Statistik")
    
    # Hämta aktuell data från databasen
    arbetsplatser = list(db.arbetsplatser.find())
    personer = list(db.personer.find())
    
    # Skapa huvudflikar för olika vyer
    tab1, tab2 = st.tabs(["🗺️ Täckningskarta", "📈 Statistik"])
    
    # Hantera täckningskarta
    with tab1:
        st.header("🗺️ Täckningskarta")
        st.markdown("""
        Kartan visar arbetsplatser och deras representation:
        - ⭕ Cirkel: Visionombud (grön = har ombud, röd = saknar ombud)
        - ✓/✕ Markör: Skyddsombud (grön ✓ = har ombud, röd ✕ = saknar ombud)
        
        Klicka på markörerna för att se detaljerad information om:
        - Visionombud
        - Skyddsombud
        - Antal medlemmar (totalt och per nivå)
        """)
        
        # Lägg till knapp för att uppdatera koordinater
        if st.button("🔄 Uppdatera och geocodea arbetsplatser"):
            with st.spinner("Uppdaterar koordinater för arbetsplatser..."):
                for arbetsplats in arbetsplatser:
                    if not arbetsplats.get("coordinates"):
                        # Skapa sökadress från arbetsplatsens information
                        address = f"{arbetsplats.get('gatuadress', '')}, {arbetsplats.get('postnummer', '')} {arbetsplats.get('ort', '')}"
                        
                        try:
                            # Använd Nominatim för att geocodea adressen
                            from geopy.geocoders import Nominatim
                            from geopy.exc import GeocoderTimedOut
                            
                            geolocator = Nominatim(user_agent="vision_section10")
                            location = geolocator.geocode(address)
                            
                            if location:
                                # Uppdatera databasen med nya koordinater
                                db.arbetsplatser.update_one(
                                    {"_id": arbetsplats["_id"]},
                                    {"$set": {
                                        "coordinates": {
                                            "lat": location.latitude,
                                            "lng": location.longitude
                                        }
                                    }}
                                )
                        except Exception as e:
                            st.error(f"Kunde inte uppdatera koordinater för {arbetsplats.get('namn', 'okänd arbetsplats')}: {str(e)}")
                            continue
                
                st.success("Koordinater uppdaterade! Ladda om sidan för att se ändringarna.")
                st.rerun()
        
        # Generera och visa interaktiv karta
        karta, saknar_koordinater = load_map(arbetsplatser, personer, db)
        folium_static(karta)
        
        # Visa information om saknade koordinater
        if saknar_koordinater:
            with st.expander("ℹ️ Arbetsplatser som saknar koordinater"):
                st.write("Följande arbetsplatser kunde inte visas på kartan då koordinater saknas:")
                for namn in saknar_koordinater:
                    st.write(f"- {namn}")
    
    # Hantera statistiköversikt
    with tab2:
        st.header("📈 Statistik")
        
        # Beräkna grundläggande statistik
        total_arbetsplatser = len(arbetsplatser)
        total_personer = len(personer)
        
        # Visa nyckeltal i kolumner
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Totalt antal arbetsplatser", total_arbetsplatser)
        with col2:
            st.metric("Totalt antal personer med uppdrag", total_personer)
        with col3:
            if total_arbetsplatser > 0:
                tackningsgrad = len([p for p in personer if p.get('uppdrag', {}).get('visionombud')]) / total_arbetsplatser * 100
                st.metric("Täckningsgrad Visionombud", f"{tackningsgrad:.1f}%")
        
        # Analysera uppdragsfördelning
        uppdrag_stats = defaultdict(int)
        for person in personer:
            for uppdrag_typ, data in person.get('uppdrag', {}).items():
                if data:  # Räkna endast aktiva uppdrag
                    uppdrag_stats[uppdrag_typ] += 1
        
        # Visualisera uppdragsstatistik
        if uppdrag_stats:
            st.subheader("Fördelning av uppdrag")
            df_uppdrag = pd.DataFrame([
                {"Uppdrag": uppdrag, "Antal": antal}
                for uppdrag, antal in uppdrag_stats.items()
            ])
            
            # Skapa interaktivt diagram
            fig = px.bar(df_uppdrag, 
                        x="Uppdrag", 
                        y="Antal",
                        title="Antal personer per uppdragstyp",
                        labels={"Uppdrag": "Typ av uppdrag", "Antal": "Antal personer"},
                        color="Uppdrag")
            
            # Optimera diagramlayout
            fig.update_layout(
                showlegend=False,
                xaxis_tickangle=-45,
                height=400
            )
            
            # Visa diagram med automatisk breddanpassning
            st.plotly_chart(fig, use_container_width=True)
            
            # Skapa fördjupad analys av representation
            st.subheader("Representationsanalys")
            
            # Beräkna täckningsgrad per förvaltning
            forvaltningar = defaultdict(lambda: {"total": 0, "med_ombud": 0})
            for arbetsplats in arbetsplatser:
                forv = arbetsplats.get('forvaltning', 'Okänd')
                forvaltningar[forv]["total"] += 1
                
                # Kontrollera om arbetsplatsen har ombud
                har_ombud = any(
                    p.get('uppdrag', {}).get('visionombud', {}).get('arbetsplats_id') == arbetsplats['_id']
                    for p in personer
                )
                if har_ombud:
                    forvaltningar[forv]["med_ombud"] += 1
            
            # Skapa dataframe för förvaltningsstatistik
            df_forvaltning = pd.DataFrame([
                {
                    "Förvaltning": forv,
                    "Täckningsgrad": (data["med_ombud"] / data["total"] * 100 if data["total"] > 0 else 0),
                    "Antal arbetsplatser": data["total"],
                    "Med ombud": data["med_ombud"]
                }
                for forv, data in forvaltningar.items()
                if forv != "Okänd"  # Exkludera okända förvaltningar
            ])
            
            if not df_forvaltning.empty:
                # Skapa interaktivt diagram för förvaltningsanalys
                fig_forv = px.bar(
                    df_forvaltning,
                    x="Förvaltning",
                    y="Täckningsgrad",
                    title="Täckningsgrad per förvaltning",
                    labels={
                        "Förvaltning": "Förvaltning",
                        "Täckningsgrad": "Täckningsgrad (%)"
                    },
                    color="Täckningsgrad",
                    color_continuous_scale="RdYlGn",  # Röd till gul till grön färgskala
                    hover_data=["Antal arbetsplatser", "Med ombud"]
                )
                
                # Optimera diagramlayout
                fig_forv.update_layout(
                    xaxis_tickangle=-45,
                    height=500,
                    yaxis_range=[0, 100]  # Sätt y-axeln till 0-100%
                )
                
                # Visa diagram med automatisk breddanpassning
                st.plotly_chart(fig_forv, use_container_width=True)
                
                # Visa detaljerad statistik i tabellform
                with st.expander("📋 Visa detaljerad statistik"):
                    st.dataframe(
                        df_forvaltning.sort_values("Täckningsgrad", ascending=False),
                        hide_index=True
                    )
            
            # Analysera trender över tid
            st.subheader("Tidsutveckling")
            
            # Hämta historisk data från loggar
            logs = list(db.logs.find(
                {"category": "person", "action": "create"},
                {"timestamp": 1}
            ).sort("timestamp", 1))
            
            if logs:
                # Skapa tidsserie för kumulativ tillväxt
                dates = [log['timestamp'] for log in logs]
                cumulative = range(1, len(dates) + 1)
                
                # Skapa dataframe för tidsanalys
                df_time = pd.DataFrame({
                    'Datum': dates,
                    'Antal': cumulative
                })
                
                # Skapa interaktivt linjediagram
                fig_time = px.line(
                    df_time,
                    x='Datum',
                    y='Antal',
                    title='Utveckling av antal personer med uppdrag över tid',
                    labels={
                        'Datum': 'Datum',
                        'Antal': 'Totalt antal personer'
                    }
                )
                
                # Optimera diagramlayout
                fig_time.update_layout(
                    height=400,
                    showlegend=False
                )
                
                # Visa diagram med automatisk breddanpassning
                st.plotly_chart(fig_time, use_container_width=True)
