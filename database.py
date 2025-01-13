from pymongo import MongoClient
import streamlit as st
import sys
import dns.resolver


def init_db():
    """Get MongoDB database connection with caching"""
    try:
        print("\n=== Starting MongoDB Connection Process ===")
        print(f"Python version: {sys.version}")

        # MongoDB configuration
        mongodb_uri = st.secrets["mongo"]["connection_string"]
        db_name = st.secrets["mongo"]["database"]

        # Mask URI for logging
        masked_uri = mongodb_uri.replace(mongodb_uri.split('@')[0], '***')
        print(f"MongoDB URI (masked): {masked_uri}")
        print(f"Target database: {db_name}")

        # Configure DNS resolver
        print("\nConfiguring DNS resolver...")
        dns.resolver.default_resolver = dns.resolver.Resolver(configure=False)
        dns.resolver.default_resolver.nameservers = ['8.8.8.8', '8.8.4.4']  # Google DNS
        print("✓ DNS resolver configured")

        print("\nStep 1: Creating MongoDB client...")
        client = MongoClient(
            mongodb_uri,
            directConnection=False,
            connect=True,
            serverSelectionTimeoutMS=30000,
            connectTimeoutMS=30000,
            socketTimeoutMS=30000
        )
        print("✓ Client created successfully")

        print("\nStep 2: Testing connection...")
        client.server_info()
        print("✓ Connection test successful")

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
            # Ensure mongodb_uri is defined before using it
            mongodb_uri = st.secrets["mongo"]["connection_string"]
            
            print("\nTrying alternative DNS resolution methods:")
            hostname = mongodb_uri.split('@')[1].split('/')[0]

            print("\n1. Using dns.resolver:")
            resolver = dns.resolver.Resolver()
            resolver.nameservers = ['8.8.8.8', '8.8.4.4']
            answers = resolver.resolve(hostname, 'A')
            print(f"DNS Resolution successful: {[str(rdata) for rdata in answers]}")

            print("\n2. Using socket.getaddrinfo:")
            import socket
            addrinfo = socket.getaddrinfo(hostname, 27017)
            print(f"Address info: {addrinfo}")

        except Exception as dns_error:
            print(f"Alternative DNS resolution failed: {str(dns_error)}")

        st.error(f"Failed to connect to MongoDB: {str(e)}")
        raise
