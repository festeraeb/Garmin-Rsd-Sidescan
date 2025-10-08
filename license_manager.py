"""
RSD Studio Professional - License Management System
Handles trial licenses, SAR licenses, and commercial licensing

License Types:
- TRIAL: 30-day free trial (auto-generated)
- SAR: Permanent free license for Search & Rescue operations
- COMMERCIAL: Paid commercial license
- ACADEMIC: Discounted academic license
"""

import os
import json
import hashlib
import datetime
from typing import Dict, Tuple, Optional
import uuid
import tkinter as tk
from tkinter import messagebox, simpledialog

class LicenseManager:
    def __init__(self):
        self.license_file = "rsd_studio_license.json"
        self.license_data = self.load_license()
        
    def load_license(self) -> Dict:
        """Load existing license or create trial license"""
        if os.path.exists(self.license_file):
            try:
                with open(self.license_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        
        # Create new trial license
        return self.create_trial_license()
    
    def save_license(self):
        """Save license data to file"""
        with open(self.license_file, 'w') as f:
            json.dump(self.license_data, f, indent=2)
    
    def create_trial_license(self) -> Dict:
        """Create a new 30-day trial license"""
        install_date = datetime.datetime.now()
        expiry_date = install_date + datetime.timedelta(days=30)
        
        machine_id = self.get_machine_id()
        trial_key = self.generate_trial_key(machine_id, install_date)
        
        license_data = {
            "license_type": "TRIAL",
            "license_key": trial_key,
            "machine_id": machine_id,
            "install_date": install_date.isoformat(),
            "expiry_date": expiry_date.isoformat(),
            "features": {
                "target_detection": True,
                "export_video": True,
                "export_kml": True,
                "export_mbtiles": True,
                "commercial_use": False,
                "priority_support": False
            },
            "user_info": {
                "organization": "Trial User",
                "email": "",
                "registered": False
            }
        }
        
        # Set license_data before saving
        self.license_data = license_data
        self.save_license()
        return license_data
    
    def get_machine_id(self) -> str:
        """Generate unique machine identifier"""
        import platform
        machine_info = f"{platform.machine()}-{platform.processor()}-{platform.system()}"
        return hashlib.md5(machine_info.encode()).hexdigest()[:16]
    
    def generate_trial_key(self, machine_id: str, install_date: datetime.datetime) -> str:
        """Generate trial license key"""
        date_str = install_date.strftime("%Y%m%d")
        key_data = f"TRIAL-{machine_id}-{date_str}"
        key_hash = hashlib.sha256(key_data.encode()).hexdigest()[:12].upper()
        return f"TRIAL-{key_hash}"
    
    def generate_sar_key(self, organization: str, email: str) -> str:
        """Generate SAR license key"""
        key_data = f"SAR-{organization}-{email}-{datetime.datetime.now().year}"
        key_hash = hashlib.sha256(key_data.encode()).hexdigest()[:12].upper()
        return f"SAR-{key_hash}"
    
    def generate_commercial_key(self, organization: str, email: str, purchase_id: str) -> str:
        """Generate commercial license key"""
        key_data = f"COMM-{organization}-{email}-{purchase_id}"
        key_hash = hashlib.sha256(key_data.encode()).hexdigest()[:12].upper()
        return f"COMM-{key_hash}"
    
    def verify_license_key(self, license_key: str, license_type: str, **kwargs) -> bool:
        """Verify if a license key is valid"""
        if license_type == "TRIAL":
            return license_key.startswith("TRIAL-")
        elif license_type == "SAR":
            return license_key.startswith("SAR-")
        elif license_type == "COMMERCIAL":
            return license_key.startswith("COMM-")
        return False
    
    def is_license_valid(self) -> Tuple[bool, str]:
        """Check if current license is valid"""
        license_type = self.license_data.get("license_type", "")
        
        if license_type == "TRIAL":
            expiry_str = self.license_data.get("expiry_date", "")
            try:
                expiry_date = datetime.datetime.fromisoformat(expiry_str)
                if datetime.datetime.now() > expiry_date:
                    days_expired = (datetime.datetime.now() - expiry_date).days
                    return False, f"Trial license expired {days_expired} days ago"
                else:
                    days_left = (expiry_date - datetime.datetime.now()).days
                    return True, f"Trial license valid - {days_left} days remaining"
            except:
                return False, "Invalid trial license date"
        
        elif license_type in ["SAR", "COMMERCIAL", "ACADEMIC"]:
            return True, f"{license_type} license active"
        
        return False, "No valid license found"
    
    def activate_license(self, license_key: str, organization: str = "", email: str = "") -> Tuple[bool, str]:
        """Activate a new license key"""
        license_key = license_key.strip().upper()
        
        if license_key.startswith("SAR-"):
            # SAR License activation
            self.license_data.update({
                "license_type": "SAR",
                "license_key": license_key,
                "activation_date": datetime.datetime.now().isoformat(),
                "expiry_date": None,  # Permanent
                "features": {
                    "target_detection": True,
                    "export_video": True,
                    "export_kml": True,
                    "export_mbtiles": True,
                    "commercial_use": False,
                    "priority_support": True,
                    "sar_specialized": True
                },
                "user_info": {
                    "organization": organization,
                    "email": email,
                    "registered": True,
                    "license_type": "Search and Rescue"
                }
            })
            self.save_license()
            return True, "SAR license activated successfully!"
        
        elif license_key.startswith("COMM-"):
            # Commercial License activation
            self.license_data.update({
                "license_type": "COMMERCIAL",
                "license_key": license_key,
                "activation_date": datetime.datetime.now().isoformat(),
                "expiry_date": None,  # Permanent
                "features": {
                    "target_detection": True,
                    "export_video": True,
                    "export_kml": True,
                    "export_mbtiles": True,
                    "commercial_use": True,
                    "priority_support": True,
                    "advanced_algorithms": True,
                    "custom_development": True
                },
                "user_info": {
                    "organization": organization,
                    "email": email,
                    "registered": True,
                    "license_type": "Commercial"
                }
            })
            self.save_license()
            return True, "Commercial license activated successfully!"
        
        elif license_key.startswith("ACAD-"):
            # Academic License activation
            self.license_data.update({
                "license_type": "ACADEMIC",
                "license_key": license_key,
                "activation_date": datetime.datetime.now().isoformat(),
                "expiry_date": (datetime.datetime.now() + datetime.timedelta(days=365)).isoformat(),
                "features": {
                    "target_detection": True,
                    "export_video": True,
                    "export_kml": True,
                    "export_mbtiles": True,
                    "commercial_use": False,
                    "priority_support": False,
                    "research_tools": True
                },
                "user_info": {
                    "organization": organization,
                    "email": email,
                    "registered": True,
                    "license_type": "Academic"
                }
            })
            self.save_license()
            return True, "Academic license activated successfully!"
        
        else:
            return False, "Invalid license key format"
    
    def show_license_dialog(self) -> bool:
        """Show license information and activation dialog"""
        is_valid, status_msg = self.is_license_valid()
        
        dialog = LicenseDialog(self, is_valid, status_msg)
        return dialog.result
    
    def get_license_info(self) -> Dict:
        """Get current license information for display"""
        is_valid, status = self.is_license_valid()
        
        info = {
            "valid": is_valid,
            "status": status,
            "type": self.license_data.get("license_type", "Unknown"),
            "organization": self.license_data.get("user_info", {}).get("organization", ""),
            "features": self.license_data.get("features", {}),
            "key": self.license_data.get("license_key", "")[:16] + "..." if self.license_data.get("license_key") else ""
        }
        
        return info

class LicenseDialog:
    def __init__(self, license_manager: LicenseManager, is_valid: bool, status_msg: str):
        self.license_manager = license_manager
        self.result = True  # Default to allowing continuation
        
        self.root = tk.Toplevel()
        self.root.title("RSD Studio Professional - License Manager")
        self.root.geometry("600x500")
        self.root.resizable(False, False)
        
        # Make dialog modal
        self.root.transient()
        self.root.grab_set()
        
        self.create_ui(is_valid, status_msg)
        
        # Center the dialog
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() // 2) - (self.root.winfo_width() // 2)
        y = (self.root.winfo_screenheight() // 2) - (self.root.winfo_height() // 2)
        self.root.geometry(f"+{x}+{y}")
        
        self.root.wait_window()
    
    def create_ui(self, is_valid: bool, status_msg: str):
        # Header
        header_frame = tk.Frame(self.root, bg="#2c3e50", height=80)
        header_frame.pack(fill="x")
        header_frame.pack_propagate(False)
        
        title_label = tk.Label(header_frame, text="🌊 RSD Studio Professional", 
                              font=("Arial", 16, "bold"), fg="white", bg="#2c3e50")
        title_label.pack(pady=20)
        
        # Status Frame
        status_frame = tk.Frame(self.root, bg="white", padx=20, pady=20)
        status_frame.pack(fill="x")
        
        status_color = "#27ae60" if is_valid else "#e74c3c"
        status_icon = "✅" if is_valid else "⚠️"
        
        status_label = tk.Label(status_frame, text=f"{status_icon} {status_msg}", 
                               font=("Arial", 12, "bold"), fg=status_color, bg="white")
        status_label.pack()
        
        # License Info
        info_frame = tk.Frame(self.root, bg="white", padx=20)
        info_frame.pack(fill="both", expand=True)
        
        license_info = self.license_manager.get_license_info()
        
        info_text = f"""
License Type: {license_info['type']}
Organization: {license_info['organization'] or 'Individual User'}
License Key: {license_info['key']}

Features Available:
• Target Detection: {'✅' if license_info['features'].get('target_detection') else '❌'}
• Video Export: {'✅' if license_info['features'].get('export_video') else '❌'}
• KML Export: {'✅' if license_info['features'].get('export_kml') else '❌'}
• MBTiles Export: {'✅' if license_info['features'].get('export_mbtiles') else '❌'}
• Commercial Use: {'✅' if license_info['features'].get('commercial_use') else '❌'}
• Priority Support: {'✅' if license_info['features'].get('priority_support') else '❌'}
        """
        
        info_label = tk.Label(info_frame, text=info_text, font=("Courier", 10), 
                             justify="left", bg="white")
        info_label.pack(anchor="w")
        
        # Buttons Frame
        buttons_frame = tk.Frame(self.root, bg="white", padx=20, pady=20)
        buttons_frame.pack(fill="x")
        
        if not is_valid:
            # Show upgrade options for expired/invalid licenses
            self.create_upgrade_buttons(buttons_frame)
        else:
            # Show continue button for valid licenses
            continue_btn = tk.Button(buttons_frame, text="Continue to RSD Studio", 
                                   command=self.continue_app, font=("Arial", 12),
                                   bg="#27ae60", fg="white", padx=20, pady=10)
            continue_btn.pack(side="right")
        
        # Always show license activation option
        activate_btn = tk.Button(buttons_frame, text="Activate License Key", 
                               command=self.show_activation_dialog, font=("Arial", 10),
                               bg="#3498db", fg="white", padx=15, pady=8)
        activate_btn.pack(side="left")
    
    def create_upgrade_buttons(self, parent):
        # For expired licenses, show upgrade options
        upgrade_frame = tk.Frame(parent, bg="white")
        upgrade_frame.pack(fill="x")
        
        # SAR License button
        sar_btn = tk.Button(upgrade_frame, text="🚁 Request SAR License (FREE)", 
                           command=self.request_sar_license, font=("Arial", 10),
                           bg="#e67e22", fg="white", padx=15, pady=8)
        sar_btn.pack(side="left", padx=(0, 10))
        
        # Commercial License button
        comm_btn = tk.Button(upgrade_frame, text="💼 Purchase Commercial License", 
                            command=self.request_commercial_license, font=("Arial", 10),
                            bg="#9b59b6", fg="white", padx=15, pady=8)
        comm_btn.pack(side="left", padx=(0, 10))
        
        # Continue with limited functionality
        limited_btn = tk.Button(upgrade_frame, text="Continue (Limited Features)", 
                               command=self.continue_limited, font=("Arial", 10),
                               bg="#95a5a6", fg="white", padx=15, pady=8)
        limited_btn.pack(side="right")
    
    def show_activation_dialog(self):
        # License key activation dialog
        key = simpledialog.askstring("License Activation", 
                                    "Enter your license key:", show='*')
        if key:
            organization = simpledialog.askstring("Organization", 
                                                "Organization name (optional):")
            email = simpledialog.askstring("Email", 
                                         "Email address (optional):")
            
            success, message = self.license_manager.activate_license(key, organization or "", email or "")
            
            if success:
                messagebox.showinfo("License Activated", message)
                self.result = True
                self.root.destroy()
            else:
                messagebox.showerror("Activation Failed", message)
    
    def request_sar_license(self):
        message = """To request a FREE Search & Rescue license:

1. Email: festeraeb@yahoo.com
2. Subject: "SAR License Request"
3. Include:
   - SAR organization name
   - Official email address
   - Brief description of SAR operations
   - Contact information

You will receive a permanent license key within 24-48 hours.
Emergency requests are processed immediately."""
        
        messagebox.showinfo("SAR License Request", message)
    
    def request_commercial_license(self):
        message = """For Commercial License pricing and purchase:

Email: festeraeb@yahoo.com
Subject: "Commercial License Inquiry"

Include:
- Organization name
- Intended use case
- Number of users
- Contact information

We offer:
• Individual licenses
• Volume discounts
• Enterprise solutions
• Custom development services"""
        
        messagebox.showinfo("Commercial License", message)
    
    def continue_app(self):
        self.result = True
        self.root.destroy()
    
    def continue_limited(self):
        # Allow limited functionality for expired trial
        self.result = True
        self.root.destroy()
        messagebox.showwarning("Limited Functionality", 
                             "Running with limited features. Some advanced capabilities may be disabled.")

def check_license_on_startup() -> bool:
    """Check license when application starts"""
    license_manager = LicenseManager()
    
    # Always show license dialog for now
    return license_manager.show_license_dialog()

if __name__ == "__main__":
    # Test the license system
    check_license_on_startup()