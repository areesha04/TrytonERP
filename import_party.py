import openpyxl
from decimal import Decimal
from proteus import config, Model
import re
# ==========================================
# 1. TRYTON CONNECTION CONFIGURATION
# ==========================================
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

Party = Model.get('party.party')
Address = Model.get('party.address')  # Explicitly load the address model
Country = Model.get('country.country')
Account = Model.get('account.account')  # Load the account model

receivable_code = '1.2.5' 
payable_code = '2.1.1'

try:
    default_receivable = Account.find([('code', '=', receivable_code)])[0]
    print(f"Loaded Default Receivable Account: {default_receivable.name} ({receivable_code})")
except IndexError:
    default_receivable = None
    print(f"⚠️ Warning: Receivable Account with code '{receivable_code}' not found.")

try:
    default_payable = Account.find([('code', '=', payable_code)])[0]
    print(f"Loaded Default Payable Account: {default_payable.name} ({payable_code})\n")
except IndexError:
    default_payable = None
    print(f"⚠️ Warning: Payable Account with code '{payable_code}' not found.\n")
# Find Pakistan country record to link addresses properly
try:
    pk_country = Country.find([('code', '=', 'PK')])[0]
except IndexError:
    pk_country = None

# Define the file name of your modern Excel file
xlsx_file_path = "parties.xlsx"

print(f"Opening Excel file '{xlsx_file_path}' to import business partners...\n")

# 3. Load the workbook and select the active sheet
wb = openpyxl.load_workbook(xlsx_file_path, data_only=True)
sheet = wb.active

# 4. Iterate through rows starting from index 2 to completely skip the header row
# min_row=2 ensures we never look at row 1 (Tenant, Organization, Business Partner, etc.)
for row in sheet.iter_rows(min_row=55, values_only=True):
    if not row or len(row) < 4:
        continue
        
    name_val = row[2]
    address_val = row[3]
    phone_val = row[4] if len(row) > 4 else ""

    # Extra safety guard to ignore empty rows or accidental header duplicates
    if not name_val or str(name_val).strip().lower() in ['name', 'business partner', 'tenant', '']:
        continue
        
    name = str(name_val).strip()
    raw_address = str(address_val).strip() if address_val else ""
    
    # --- GLOBAL ERROR HANDLING PER RECORD ---
    try:
        print(f"➕ Processing: '{name}'...")
        
        # Format phone accurately
        if isinstance(phone_val, float):
            phone = str(int(phone_val)).strip()
        elif phone_val is not None:
            phone = str(phone_val).strip()
        else:
            phone = ""

        # --- ADDRESS PARSING ---
        clean_street = re.sub(r'(?i)\bkarachi\b', '', raw_address)
        clean_street = re.sub(r',\s*,', ',', clean_street)
        clean_street = clean_street.strip().strip(',')
        clean_street = clean_street.strip()

        if not clean_street:
            clean_street = name

        # --- PARTY FETCH OR CREATE ---
        existing_parties = Party.find([('name', '=', name)])
        if existing_parties:
            party = existing_parties[0]
            print(f"    -> Found existing party (ID: {party.id}). Updating configuration...")
        else:
            party = Party()
            party.name = name

        # Assign Account Defaults
        if default_receivable:
            party.account_receivable = default_receivable
        if default_payable:
            party.account_payable = default_payable

        # --- ADDRESS CHECK & UPDATE ---
        if party.addresses:
            address = party.addresses[0]
        else:
            address = party.addresses.new()

        address.street = clean_street
        address.city = 'Karachi'
        address.active = True      
        address.invoice = True     
        address.delivery = True    
        
        if pk_country:
            address.country = pk_country

        # --- CONTACT MECHANISM ---
        if phone and phone.lower() != 'phone':
            phone_cleaned = phone.replace(" ", "")
            if phone_cleaned.startswith('0'):
                phone_cleaned = '+92' + phone_cleaned[1:]
            elif phone_cleaned.startswith('92') and not phone_cleaned.startswith('+92'):
                phone_cleaned = '+' + phone_cleaned

            phone_exists = any(c.value == phone_cleaned for c in party.contact_mechanisms if c.type == 'phone')
            if not phone_exists:
                contact = party.contact_mechanisms.new()
                contact.type = 'phone'
                contact.value = phone_cleaned

        # Final save commits everything cleanly
        party.save()
        print(f"💾 Saved successfully! (ID: {party.id})\n")

    except Exception as e:
        # Catch any error (XML-RPC faults, verification breaks, etc.)
        print(f"❌ ERROR: Failed to process record '{name}'. Skipping to next.")
        print(f"    Details: {e}")
        print("-" * 50)
        # Continue to the next iteration of the loop without failing the whole execution block
        continue

print("Import process completed.")