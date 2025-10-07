"""
License Key Generator for RSD Studio Professional
Tool for generating license keys for different license types

Usage:
python license_generator.py --type SAR --org "Coast Guard" --email "sar@coastguard.gov"
python license_generator.py --type COMMERCIAL --org "Marine Surveys Inc" --email "sales@marinesurveys.com"
"""

import argparse
import hashlib
import datetime
import uuid
from license_manager import LicenseManager

class LicenseGenerator:
    def __init__(self):
        self.license_manager = LicenseManager()
    
    def generate_sar_key(self, organization: str, email: str) -> str:
        """Generate SAR license key"""
        key_data = f"SAR-{organization}-{email}-{datetime.datetime.now().year}"
        key_hash = hashlib.sha256(key_data.encode()).hexdigest()[:12].upper()
        return f"SAR-{key_hash}"
    
    def generate_commercial_key(self, organization: str, email: str, purchase_id: str = None) -> str:
        """Generate commercial license key"""
        if not purchase_id:
            purchase_id = str(uuid.uuid4())[:8].upper()
        key_data = f"COMM-{organization}-{email}-{purchase_id}"
        key_hash = hashlib.sha256(key_data.encode()).hexdigest()[:12].upper()
        return f"COMM-{key_hash}"
    
    def generate_academic_key(self, organization: str, email: str) -> str:
        """Generate academic license key"""
        key_data = f"ACAD-{organization}-{email}-{datetime.datetime.now().year}"
        key_hash = hashlib.sha256(key_data.encode()).hexdigest()[:12].upper()
        return f"ACAD-{key_hash}"
    
    def verify_key(self, license_key: str, license_type: str, organization: str, email: str) -> bool:
        """Verify a generated license key"""
        if license_type.upper() == "SAR":
            expected = self.generate_sar_key(organization, email)
        elif license_type.upper() == "COMMERCIAL":
            # For verification, we need the purchase ID
            return license_key.startswith("COMM-")
        elif license_type.upper() == "ACADEMIC":
            expected = self.generate_academic_key(organization, email)
        else:
            return False
        
        return license_key == expected

def main():
    parser = argparse.ArgumentParser(description="Generate RSD Studio license keys")
    parser.add_argument("--type", required=True, choices=["SAR", "COMMERCIAL", "ACADEMIC"], 
                       help="License type")
    parser.add_argument("--org", required=True, help="Organization name")
    parser.add_argument("--email", required=True, help="Email address")
    parser.add_argument("--purchase-id", help="Purchase ID for commercial licenses")
    parser.add_argument("--verify", help="Verify an existing license key")
    
    args = parser.parse_args()
    
    generator = LicenseGenerator()
    
    if args.verify:
        # Verify mode
        is_valid = generator.verify_key(args.verify, args.type, args.org, args.email)
        print(f"License key verification: {'VALID' if is_valid else 'INVALID'}")
        return
    
    # Generate mode
    if args.type == "SAR":
        license_key = generator.generate_sar_key(args.org, args.email)
        print(f"SAR License Key Generated:")
        print(f"Organization: {args.org}")
        print(f"Email: {args.email}")
        print(f"License Key: {license_key}")
        print(f"\nThis key provides:")
        print("• Permanent free license for Search & Rescue operations")
        print("• All target detection features")
        print("• Priority support")
        print("• Specialized SAR algorithms")
        
    elif args.type == "COMMERCIAL":
        license_key = generator.generate_commercial_key(args.org, args.email, args.purchase_id)
        print(f"Commercial License Key Generated:")
        print(f"Organization: {args.org}")
        print(f"Email: {args.email}")
        print(f"Purchase ID: {args.purchase_id or 'Auto-generated'}")
        print(f"License Key: {license_key}")
        print(f"\nThis key provides:")
        print("• Permanent commercial license")
        print("• All features including commercial use rights")
        print("• Priority support")
        print("• Advanced algorithms")
        print("• Custom development options")
        
    elif args.type == "ACADEMIC":
        license_key = generator.generate_academic_key(args.org, args.email)
        print(f"Academic License Key Generated:")
        print(f"Institution: {args.org}")
        print(f"Email: {args.email}")
        print(f"License Key: {license_key}")
        print(f"\nThis key provides:")
        print("• 1-year renewable academic license")
        print("• All features except commercial use")
        print("• Research tools and documentation")
        print("• Educational support")

if __name__ == "__main__":
    main()