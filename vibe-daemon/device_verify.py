import subprocess
import hashlib
import sys
import platform
import uuid

def get_hardware_uuid():
    """Retrieves a unique hardware identifier for the device (Windows focus)."""
    if platform.system() != "Windows":
        # Fallback for non-Windows systems using MAC address
        mac_num = hex(uuid.getnode()).replace('0x', '').upper()
        mac = '-'.join(mac_num[i: i + 2] for i in range(0, 11, 2))
        return mac

    try:
        # Get Motherboard UUID
        result = subprocess.check_output('wmic csproduct get uuid', shell=True, text=True)
        hw_uuid = result.split('\n')[1].strip()
        
        # In some VMs or systems, it might return 'FFFFFFFF-FFFF-FFFF-FFFF-FFFFFFFFFFFF' or be empty
        if not hw_uuid or "FFFFFFFF" in hw_uuid:
            # Fallback to getting disk drive serial number
            result = subprocess.check_output('wmic diskdrive get serialnumber', shell=True, text=True)
            hw_uuid = "".join(result.split('\n')[1:]).strip()
            
        return hw_uuid
    except Exception as e:
        print(f"Error retrieving hardware UUID: {e}")
        return None

def generate_device_hash(hardware_id):
    """Generates a secure hash from the hardware ID to be used as the Device ID."""
    if not hardware_id:
        return None
        
    # Salt the hardware ID slightly to prevent basic reverse-lookup
    salt = "PC_LINK_SALT_99"
    raw_string = f"{hardware_id}_{salt}".encode('utf-8')
    device_hash = hashlib.sha256(raw_string).hexdigest()
    return device_hash

def verify_device_license(device_id):
    """
    Placeholder for verifying the device ID against a backend (e.g. Firebase).
    In a real scenario, you would query Firebase to check if this device_id
    has an active license.
    """
    print(f"Verifying license for Device ID: {device_id}...")
    
    # TODO: Connect to Firebase (using non-admin client SDK or REST) 
    # to check if `licenses/{device_id}` exists and is valid.
    
    # Mocking validation
    is_valid = True # Set to False to simulate invalid license
    
    if is_valid:
        print("[SUCCESS] Device authorized.")
        return True
    else:
        print("[FAILED] Device not authorized. Please purchase a license.")
        return False

if __name__ == "__main__":
    hw_id = get_hardware_uuid()
    if not hw_id:
        print("Failed to generate hardware ID. Exiting.")
        sys.exit(1)
        
    device_id = generate_device_hash(hw_id)
    print(f"Hardware UUID: {hw_id}")
    print(f"Generated Device ID (Hash): {device_id}\n")
    
    authorized = verify_device_license(device_id)
    if not authorized:
        # Terminate the application if not authorized
        sys.exit(1)
