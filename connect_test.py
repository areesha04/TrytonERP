import sys
from proteus import config, Model

# ==========================================
# 1. CONNECTION CONFIGURATION
# ==========================================
# Toggle between 'local' and 'whm' depending on where you want to run it
ENVIRONMENT = 'local'  

try:
    if ENVIRONMENT == 'local':
        print("Connecting to Local Host...")
        # Your local development URL (using HTTP)
        cfg = config.set_xmlrpc('http://admin:admin@localhost:8000/tryton/')
        
    elif ENVIRONMENT == 'whm':
        print("Connecting to WHM Server...")
        # Your remote server URL
        cfg = config.set_xmlrpc('http://admin:admin789@5.161.214.209:8000/trytonRC/')

    print("Connection successful!")

except Exception as e:
    print(f"Failed to connect: {e}")
    sys.exit(1)

# ==========================================
# 2. YOUR SCRIPT LOGIC GOES HERE
# ==========================================
# Now that the connection is active, you can interact with your Tryton models:

print("\nFetching Party model...")
Party = Model.get('party.party')

# Quick test: Find the first 5 parties in the system
# PHASE 1: READ TEST
parties = Party.find([], limit=5)
print(f"Found {len(parties)} parties in the database:")
for party in parties:
    print(f"- {party.name} (ID: {party.id})")

# PHASE 2: WRITE (CREATE) TEST
print("\n[PHASE 2] Testing Database Write...")
test_name = "Proteus Local Test Partner"

# Check if our test party already exists from a previous run to avoid duplicates
duplicate_check = Party.find([('name', '=', test_name)])

if not duplicate_check:
    # Create a new record instance
    new_party = Party()
    new_party.name = test_name
    new_party.code = "TST-001"
    
    # Save commits it to your local PostgreSQL database
    new_party.save()
    print(f"Successfully created new party: '{new_party.name}' with ID: {new_party.id}")
    target_party = new_party
else:
    print(f"Test party '{test_name}' already exists. Using existing record.")
    target_party = duplicate_check[0]

# PHASE 3: UPDATE TEST
print("\n[PHASE 3] Testing Database Update...")
# Let's add or modify a comment field on our party record
Country = Model.get('country.country')
Subdivision = Model.get('country.subdivision')
parties = Party.find([('name', '=', 'Proteus Local Test Partner')])

if parties:
    party = parties[0]
    print(f"Updating address for: {party.name}")
    
    # 2. Check if the party already has an address, or create a new one
    if party.addresses:
        address = party.addresses[0]  # Grab the first existing address
        print("Updating existing address...")
    else:
        address = party.addresses.new()  # Create a brand new address line
        print("Creating a new address...")

    # =========================================================
    # 3. UPDATE THE FIELDS SEEN IN YOUR IMAGE
    # =========================================================
    
    # Text & Character Fields
    address.street = "123 Business Avenue\nFloor 4, Block C"
    address.city = "Karachi"
    address.postal_code = "74200"
    
    # Detailed modern address fields (from your screenshot)
    address.street_name = "Business Avenue"
    address.building_number = "123"
    address.floor_number = "4"
    address.room_number = "402"
    
    # Checkboxes (Booleans: True = Checked, False = Unchecked)
    address.invoice = True   # Checks the 'Invoice' box
    address.delivery = True  # Checks the 'Delivery' box
    address.active = True    # Keeps the address active

    # Many2One Relational Fields (Country & Subdivision/State)
    # Note: Tryton looks up countries by their ISO alpha-2 codes
    found_countries = Country.find([('code', '=', 'PK')])
    if found_countries:
        address.country = found_countries[0]
        
        # Look up a subdivision (e.g., Sindh province) linked to that country
        found_subs = Subdivision.find([
            ('country', '=', found_countries[0].id),
            ('name', '=', 'Sindh')
        ])
        if found_subs:
            address.subdivision = found_subs[0]

    # 4. Save the parent Party record (this commits the nested address changes)
    party.save()
    print("Address fields successfully updated inside Tryton!")

else:
    print("Target party record not found.")