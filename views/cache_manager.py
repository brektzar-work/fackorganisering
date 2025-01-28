"""
Centraliserad cachningsmodul för Vision Sektion 10.

Denna modul hanterar all cachning av data från databasen för att optimera prestanda.
Implementerar både grundläggande datacachnig och avancerade indexeringsstrukturer.
"""

import streamlit as st
from collections import defaultdict


def load_base_data(db):
    """Laddar grundläggande data från databasen"""
    return {
        'forvaltningar': list(db.forvaltningar.find()),
        'avdelningar': list(db.avdelningar.find()),
        'enheter': list(db.enheter.find()),
        'arbetsplatser': list(db.arbetsplatser.find()),
        'personer': list(db.personer.find())
    }


def create_indexes(data):
    """Skapar indexstrukturer för snabb åtkomst till data"""
    indexes = {
        'avdelningar_by_forv': defaultdict(list),
        'enheter_by_avd': defaultdict(list),
        'arbetsplatser_by_forv': defaultdict(list),
        'personer_by_forv': defaultdict(list),
        'personer_by_arbetsplats': defaultdict(list),
        'globala_arbetsplatser': [],
        'id_lookup': {
            'forvaltningar': {},
            'avdelningar': {},
            'enheter': {},
            'arbetsplatser': {}
        }
    }

    # Indexera avdelningar per förvaltning
    for avd in data['avdelningar']:
        forv_id = avd['forvaltning_id']
        indexes['avdelningar_by_forv'][forv_id].append(avd)
        indexes['id_lookup']['avdelningar'][avd['_id']] = avd

    # Indexera enheter per avdelning
    for enhet in data['enheter']:
        avd_id = enhet['avdelning_id']
        indexes['enheter_by_avd'][avd_id].append(enhet)
        indexes['id_lookup']['enheter'][enhet['_id']] = enhet

    # Indexera arbetsplatser
    for ap in data['arbetsplatser']:
        if ap.get('alla_forvaltningar'):
            indexes['globala_arbetsplatser'].append(ap)
        else:
            forv_id = ap['forvaltning_id']
            indexes['arbetsplatser_by_forv'][forv_id].append(ap)
        indexes['id_lookup']['arbetsplatser'][ap['_id']] = ap

    # Indexera personer
    for person in data['personer']:
        forv_id = person['forvaltning_id']
        indexes['personer_by_forv'][forv_id].append(person)
        if person.get('arbetsplats'):
            for arbetsplats in person['arbetsplats']:
                indexes['personer_by_arbetsplats'][arbetsplats].append(person)

    # Indexera förvaltningar för snabb ID-lookup
    for forv in data['forvaltningar']:
        indexes['id_lookup']['forvaltningar'][forv['_id']] = forv

    return indexes


def get_cached_data(db, force_refresh=False):
    """Hämtar cachad data och index, uppdaterar vid behov"""
    if force_refresh or 'cached_data' not in st.session_state:
        st.session_state.cached_data = load_base_data(db)
        st.session_state.cached_indexes = create_indexes(st.session_state.cached_data)

    return st.session_state.cached_data, st.session_state.cached_indexes


def refresh_cache(db):
    """Tvingar uppdatering av cache"""
    if 'cached_data' in st.session_state:
        del st.session_state.cached_data
    if 'cached_indexes' in st.session_state:
        del st.session_state.cached_indexes
    return get_cached_data(db, force_refresh=True)


def update_cache_after_change(db, collection_name, operation, data=None):
    """Uppdaterar cachen efter en databasändring"""
    # För större ändringar, uppdatera hela cachen
    if operation in ['delete', 'update'] or collection_name in ['forvaltningar', 'avdelningar']:
        refresh_cache(db)
        return

    # För enkla tillägg, uppdatera bara relevant data
    if operation == 'create' and data:
        if collection_name not in st.session_state.cached_data:
            refresh_cache(db)
            return
            
        st.session_state.cached_data[collection_name].append(data)
        # Uppdatera relevanta index
        if collection_name == 'personer':
            forv_id = data['forvaltning_id']
            st.session_state.cached_indexes['personer_by_forv'][forv_id].append(data)
            if data.get('arbetsplats'):
                for arbetsplats in data['arbetsplats']:
                    st.session_state.cached_indexes['personer_by_arbetsplats'][arbetsplats].append(data) 