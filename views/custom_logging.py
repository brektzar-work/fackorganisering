from datetime import datetime
from pymongo import MongoClient, ASCENDING
import pytz
import streamlit as st
import pandas as pd
import os


# Loggningssystem för Vision Sektion 10
# Detta system hanterar all loggning av användaraktiviteter i applikationen.
# Systemet är designat för att spåra alla viktiga händelser och förändringar
# i systemet för att möjliggöra felsökning och revision.

###############################
# Actiontyper (alla i lowercase):
# "create"        - Skapande av nya objekt/poster i systemet
# "update"        - Modifiering av befintliga objekt/poster
# "delete"        - Borttagning av objekt/poster
# "login"         - Användarinloggningar (lyckade)
# "logout"        - Användarutloggningar
# "failed_login"  - Misslyckade inloggningsförsök (säkerhetsloggning)
###############################

###############################
# Kategorier (alla i lowercase):
# "person"  - Personrelaterade händelser (medlemmar, anställda)
# "board"   - Styrelse/kommittérelaterade händelser
# "unit"    - Organisationsenhetsrelaterade händelser
# "user"    - Användarhanteringsrelaterade händelser
# "auth"    - Autentiseringsrelaterade händelser
###############################

###############################
# Meddelandeformat och exempel (alla i uppercase):
# Create:  "Skapade [objekttyp]: [namn] med [detaljer]"
#          Ex: "Skapade person: Anna Andersson med roll: Visionombud"
#
# Update:  "Uppdaterade [objekttyp]: [namn] - Ändrade [ändringar]"
#          Ex: "Uppdaterade person: Anna Andersson - Ändrade telefonnummer från 123 till 456"
#
# Delete:  "Tog bort [objekttyp]: [namn]"
#          Ex: "Tog bort person: Anna Andersson"
#
# Login:   "Användare [användarnamn] loggade in"
#          Ex: "Användare admin@vision.se loggade in"
#
# Logout:  "Användare [användarnamn] loggade ut"
#          Ex: "Användare admin@vision.se loggade ut"
#
# Failed:  "Misslyckat inloggningsförsök för användare: [användarnamn]"
#          Ex: "Misslyckat inloggningsförsök för användare: unknown@test.com"
###############################


def initialize_logs_collection():
    """
    Initierar och konfigurerar loggsamlingen i databasen.
    
    Funktionen:
    1. Kontrollerar om 'logs' samlingen existerar i databasen
    2. Skapar samlingen om den inte finns
    3. Sätter upp nödvändiga index för optimerad prestanda
    
    Tekniska detaljer:
    - Skapar ett ASCENDING index på 'timestamp' fältet för snabbare tidbaserade sökningar
    - Hanterar databasanslutning via init_db() för att undvika cirkulära importberoenden
    """
    try:
        from database import init_db
        db = init_db()

        if "logs" not in db.list_collection_names():
            print("Logs collection does not exist. Creating it now.")
            db.create_collection("logs")
            # Indexering för optimerad prestanda vid tidbaserade sökningar
            db.logs.create_index([("timestamp", ASCENDING)])
            print("Logs collection created successfully.")
    except Exception as e:
        print(f"Error initializing logs collection: {e}")


def current_time():
    """
    Genererar en korrekt formaterad tidsstämpel för Stockholm/svensk tidszon.
    
    Funktionen:
    1. Använder pytz för att hantera svensk tidszon (Europe/Stockholm)
    2. Hanterar automatiskt sommar- och vintertid
    3. Formaterar tiden enligt svensk standard
    
    Returns:
        str: Formaterad tidsstämpel i formatet "Datum: ÅÅÅÅ-MM-DD Tid: HH:MM:SS"
    """
    timezone = pytz.timezone('Europe/Stockholm')
    stockholm_time = datetime.now(timezone)
    return stockholm_time.strftime("Datum: %Y-%m-%d Tid: %H:%M:%S")


def log_action(action, description, category):
    """
    Loggar en användarhandling i systemet med full felhantering och validering.
    
    Funktionen:
    1. Validerar och sparar handlingen i databasen
    2. Uppdaterar den lokala logg-cachen
    3. Hanterar eventuella fel vid databasoperationer
    
    Args:
        action (str): Typ av handling (se aktionstyper i huvudkommentaren)
        description (str): Detaljerad beskrivning av handlingen
        category (str): Kategori för handlingen (se kategorier i huvudkommentaren)
    
    Tekniska detaljer:
    - Använder lazy import av database för att undvika cirkulära beroenden
    - Validerar databasanslutning och collection-existens
    - Skriver loggmeddelanden till både stdout och stderr för felsökning
    """
    try:
        print("Trying to save logs")
        logs_df = load_logs()  # Uppdatera logg-cache
        from database import init_db
        db = init_db()

        initialize_logs_collection()

        if not hasattr(db, "logs"):
            raise AttributeError("Database object does not have a 'logs' attribute")

        # Get the current username from session state
        username = st.session_state.get('username', 'System')

        log_entry = {
            'action': action,
            'description': description,
            'category': category,
            'timestamp': current_time(),
            'username': username  # Add username to log entry
        }

        # Spara till databasen och logga resultatet
        log_print_success = f"Log saved successfully: {log_entry}"
        lps = str.encode(log_print_success)

        db.logs.insert_one(log_entry)
        print(f"Log saved successfully: {log_entry}")
        os.write(1, lps)
    except Exception as e:
        log_print_fail = f"Error saving data to MongoDB: {e}"
        lpf = str.encode(log_print_fail)
        print(f"Error saving data to MongoDB: {e}")
        os.write(1, lpf)


def load_logs():
    """
    Hämtar och formaterar alla loggar från databasen.
    
    Funktionen:
    1. Hämtar alla loggar från databasen
    2. Konverterar dem till en Pandas DataFrame för enkel hantering
    3. Hanterar edge cases som tom databas eller anslutningsfel
    
    Returns:
        pandas.DataFrame: DataFrame med kolumnerna:
            - action: Typ av handling
            - description: Beskrivning av handlingen
            - category: Handlingens kategori
            - timestamp: Tidpunkt för handlingen
    
    Tekniska detaljer:
    - Exkluderar MongoDB's _id fält från resultatet
    - Returnerar en tom DataFrame med korrekt schema vid fel
    """
    try:
        from database import init_db
        db = init_db()

        logs = list(db.logs.find({}, {'_id': 0}))

        if not logs:
            return pd.DataFrame(columns=['action', 'description', 'category', 'timestamp'])

        return pd.DataFrame(logs)
    except Exception as e:
        print(f"Error loading logs from MongoDB: {e}")
        return pd.DataFrame(columns=['action', 'description', 'category', 'timestamp'])


def get_logs_by_category():
    """
    Grupperar och aggregerar loggar efter kategori med MongoDB's aggregation pipeline.
    
    Funktionen:
    1. Definierar giltiga kategorier och aktioner
    2. Använder MongoDB's aggregation för effektiv gruppering
    3. Formaterar och presenterar resultatet via Streamlit
    
    Tekniska detaljer:
    - Använder $match för filtrering av giltiga kategorier
    - Använder $project för att exkludera _id fält
    - Använder $group med $push för att samla loggar per kategori
    - Hanterar resultatpresentation via Streamlit's API
    
    Returns:
        dict: Ordbok där nycklar är kategorier och värden är listor av loggar
    """
    category = [
        "person",
        "board",
        "unit",
        "user",
        "auth",
    ]
    actions = [
        "create",
        "update",
        "delete",
        "login",
        "logout",
        "failed_login"
    ]

    try:
        from database import init_db
        db = init_db()
        logs_collection = db.logs

        pipeline = [
            {"$match": {"category": {"$in": category}}},
            {"$project": {"_id": 0}},
            {"$group": {
                "_id": "$category",
                "logs": {"$push": "$$ROOT"}
            }}
        ]

        logs_by_category = {}
        for group in logs_collection.aggregate(pipeline):
            logs_by_category[group["_id"]] = group["logs"]

        st.write(f"Totalt {len(logs_by_category)} kategorier grupperades.")

        success = f"Hämtar loggar!"
        os.write(1, success.encode())

        for action, logs in logs_by_category.items():
            st.write(f"Kategori: {category} - Antal loggar: {len(logs)}")

        return logs_by_category

    except Exception as e:
        error_h = f"Error fetching logs by action:\n {e}"
        os.write(1, error_h.encode())
        print(f"Error fetching logs by action:\n {e}")
        return {}


def compare_and_log_changes(df, edited_data):
    """
    Jämför och loggar ändringar mellan original och redigerad data.
    
    Funktionen:
    1. Jämför varje cell i original-DataFrame med motsvarande redigerad data
    2. Identifierar och samlar alla ändringar
    3. Loggar varje ändring med detaljerad information
    
    Args:
        df (pandas.DataFrame): Original-DataFrame med befintlig data
        edited_data (dict): Dictionary med redigerad data, indexerad efter rad
    
    Returns:
        list: Lista med dictionaries som innehåller information om varje ändring:
            - index: Radindex som ändrades
            - column: Kolumn som ändrades
            - old_value: Ursprungligt värde
            - new_value: Nytt värde
    
    Tekniska detaljer:
    - Hanterar saknade index i original-DataFrame
    - Loggar ändringar med användarkontext från Streamlit session state
    - Formaterar ändringsmeddelanden för tydlig spårning
    """
    changes_made = []

    for index, new_data in edited_data.items():
        old_data = df.loc[index] if index in df.index else None

        for column in new_data:
            old_value = old_data[column] if old_data is not None else None
            new_value = new_data[column]

            if old_value != new_value:
                changes_made.append({
                    "index": index,
                    "column": column,
                    "old_value": old_value,
                    "new_value": new_value
                })

    if changes_made:
        for change in changes_made:
            log_action("update",
                       (f"{st.session_state.username} ändrade uppgiften {change['column']} \n"
                        f"för rad {change['index']} \n"
                        f"från {change['old_value']} \n"
                        f"till {change['new_value']}\n"),
                       "Planering/Redigera Mål och Uppgifter")
    return changes_made
