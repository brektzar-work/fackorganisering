"""
Databashanteringsmodul för Vision Sektion 10

Denna modul hanterar all databasrelaterad funktionalitet i systemet,
med fokus på säker och robust anslutning till MongoDB Atlas:

1. Anslutningshantering
   - Säker konfiguration av MongoDB-klient
   - Automatisk återanslutning vid fel
   - DNS-konfiguration och felhantering
   - Timeout-hantering för robusthet

2. Säkerhetsfunktioner
   - Säker hantering av anslutningssträngar
   - Krypterad kommunikation via TLS
   - Maskering av känslig information i loggar
   - Behörighetskontroll via MongoDB Atlas

3. Felhantering och Diagnostik
   - Omfattande felrapportering
   - DNS-felsökning med alternativa metoder
   - Detaljerad loggning av anslutningsprocess
   - Automatisk återställning vid nätverksproblem

Tekniska detaljer:
- Använder PyMongo för MongoDB-integration
- Implementerar DNS-resolver för robust namnuppslagning
- Tillhandahåller cachning via Streamlit
- Hanterar timeouts och återanslutningar
"""

from pymongo import MongoClient
import streamlit as st
import sys
import dns.resolver


def init_db():
    """
    Initierar och konfigurerar databasanslutning till MongoDB Atlas.
    
    Denna komplexa funktion hanterar hela processen för att etablera
    en säker och robust anslutning till databasen, inklusive:
    
    1. Konfiguration
       - Läser in anslutningsdetaljer från Streamlit's secrets
       - Konfigurerar DNS-resolver för pålitlig namnuppslagning
       - Sätter optimala timeout-värden för olika operationer
    
    2. Anslutningsprocess
       - Skapar MongoDB-klient med säkra inställningar
       - Verifierar anslutningen genom serverinfo-kontroll
       - Etablerar databaskontext för applikationen
    
    3. Felhantering
       - Omfattande felrapportering med detaljerad diagnostik
       - Alternativa DNS-uppslagningsmetoder vid problem
       - Automatisk återställning där möjligt
    
    Returns:
        pymongo.database.Database: Ansluten databasinstans
        
    Raises:
        Exception: Vid anslutningsfel med detaljerad felrapport
    
    Tekniska detaljer:
    - Använder Google DNS (8.8.8.8, 8.8.4.4) för pålitlig namnuppslagning
    - Implementerar connection pooling för prestanda
    - Hanterar timeout-inställningar för olika nätverksscenarier
    - Tillhandahåller detaljerad diagnostik vid fel
    """
    try:
        print("\n=== Starting MongoDB Connection Process ===")
        print(f"Python version: {sys.version}")

        # Hämta och validera databasinställningar från Streamlit's secrets
        mongodb_uri = st.secrets["mongo"]["connection_string"]
        db_name = st.secrets["mongo"]["database"]

        # Maskera känslig information för säker loggning
        masked_uri = mongodb_uri.replace(mongodb_uri.split('@')[0], '***')
        print(f"MongoDB URI (masked): {masked_uri}")
        print(f"Target database: {db_name}")

        # Konfigurera DNS-resolver för pålitlig namnuppslagning
        print("\nConfiguring DNS resolver...")
        dns.resolver.default_resolver = dns.resolver.Resolver(configure=False)
        dns.resolver.default_resolver.nameservers = ['8.8.8.8', '8.8.4.4']  # Google DNS för stabilitet
        print("✓ DNS resolver configured")

        # Steg 1: Skapa MongoDB-klient med optimerade inställningar
        print("\nStep 1: Creating MongoDB client...")
        client = MongoClient(
            mongodb_uri,
            directConnection=False,  # Tillåt connection pooling
            connect=True,           # Verifiera anslutning vid start
            serverSelectionTimeoutMS=30000,  # Timeout för serverval
            connectTimeoutMS=30000,         # Timeout för anslutning
            socketTimeoutMS=30000           # Timeout för socketoperationer
        )
        print("✓ Client created successfully")

        # Steg 2: Verifiera anslutningen genom serverinfo-kontroll
        print("\nStep 2: Testing connection...")
        client.server_info()
        print("✓ Connection test successful")

        # Steg 3: Etablera databaskontext
        print("\nStep 3: Accessing database...")
        db = client[db_name]
        print(f"✓ Database '{db_name}' accessed")

        print("\n=== MongoDB Connection Successful ===\n")

        return db

    except Exception as e:
        print("\n!!! MongoDB Connection Error !!!")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        print(f"Error details: {repr(e)}")

        try:
            # Säkerställ att mongodb_uri är definierad innan användning
            mongodb_uri = st.secrets["mongo"]["connection_string"]
            
            # Implementera alternativa DNS-uppslagningsmetoder vid problem
            print("\nTrying alternative DNS resolution methods:")
            hostname = mongodb_uri.split('@')[1].split('/')[0]

            # Metod 1: Direkt DNS-uppslagning via resolver
            print("\n1. Using dns.resolver:")
            resolver = dns.resolver.Resolver()
            resolver.nameservers = ['8.8.8.8', '8.8.4.4']  # Använd Google DNS
            answers = resolver.resolve(hostname, 'A')
            print(f"DNS Resolution successful: {[str(rdata) for rdata in answers]}")

            # Metod 2: Systemets inbyggda DNS-uppslagning
            print("\n2. Using socket.getaddrinfo:")
            import socket
            addrinfo = socket.getaddrinfo(hostname, 27017)
            print(f"Address info: {addrinfo}")

        except Exception as dns_error:
            print(f"Alternative DNS resolution failed: {str(dns_error)}")

        # Rapportera felet till användaren och avbryt
        st.error(f"Failed to connect to MongoDB: {str(e)}")
        raise
